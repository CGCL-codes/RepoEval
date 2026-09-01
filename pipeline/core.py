from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config.config import MODEL_CONFIGS, RESULTS_DIR
from .prompting import build_prompt, normalize_llm_output_mode
from .runners import resolve_python_interpreter, run_target
from .utils import decode_bytes, encode_bytes, ensure_dir, extract_seed_base64


def call_llm(prompt: str, model_name: str) -> str:
    from openai import OpenAI

    if model_name not in MODEL_CONFIGS:
        raise ValueError(f"Unknown model: {model_name}")
    cfg = MODEL_CONFIGS[model_name]
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError(f"Missing API key for model {model_name}")

    client = OpenAI(api_key=api_key, base_url=cfg.get("base_url") or None)
    resp = client.chat.completions.create(
        model=cfg["model_name"],
        messages=[{"role": "user", "content": prompt}],
        temperature=cfg.get("temperature", 0.7),
    )
    text = resp.choices[0].message.content or ""
    return text


def extract_python_code(response: str) -> Optional[str]:
    code_match = re.search(r"```python\s*\n(.*?)```", response, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    code_match = re.search(r"```\s*\n(.*?)```", response, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    if "output_file" in response and ("open(" in response or "Path(" in response):
        return response.strip()
    return None


def run_generated_python_code(
    code: str,
    output_file: Path,
    code_file: Path,
    python_interpreter: Path,
) -> None:
    wrapped = (
        "from pathlib import Path\n"
        f"output_file = Path(r\"{output_file}\")\n"
        "output_file.parent.mkdir(parents=True, exist_ok=True)\n\n"
        f"{code}\n"
    )
    code_file.write_text(wrapped, encoding="utf-8")
    proc = subprocess.run(
        [str(python_interpreter), str(code_file)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise ValueError(
            "Generated Python code failed to execute:\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
    if not output_file.exists():
        raise ValueError("Generated Python code did not create input.bin")


def _generate_seed_from_llm(
    target: Dict,
    prompt: str,
    model_name: str,
    target_dir: Path,
    llm_output_mode: str,
) -> Tuple[str, bytes, str]:
    llm_response = call_llm(prompt, model_name)
    resolved_output_mode = normalize_llm_output_mode(target.get("llm_output_mode", llm_output_mode))
    if resolved_output_mode == "python_code":
        code = extract_python_code(llm_response)
        if not code:
            raise ValueError("LLM response does not contain executable Python code")
        input_file = target_dir / "input.bin"
        code_file = target_dir / "generated_input.py"
        python_interpreter = resolve_python_interpreter(target)
        run_generated_python_code(code, input_file, code_file, python_interpreter)
        return llm_response, input_file.read_bytes(), f"{model_name}:python_code"

    seed_b64 = extract_seed_base64(llm_response)
    if not seed_b64:
        raise ValueError("LLM response does not contain seed_base64")
    return llm_response, decode_bytes(seed_b64), model_name


def get_seed_bytes(
    target: Dict,
    prompt: str,
    mode: str,
    model_name: Optional[str],
    target_dir: Path,
    llm_output_mode: str,
) -> Tuple[Optional[str], bytes, str]:
    if mode == "prebuilt":
        seed = decode_bytes(target["prebuilt_seed_base64"])
        return None, seed, "prebuilt_seed_base64"
    if mode == "llm":
        if not model_name:
            raise ValueError("--model is required in llm mode")
        return _generate_seed_from_llm(target, prompt, model_name, target_dir, llm_output_mode)
    if mode == "auto":
        if target.get("prebuilt_seed_base64"):
            seed = decode_bytes(target["prebuilt_seed_base64"])
            return None, seed, "prebuilt_seed_base64"
        if not model_name:
            raise ValueError("--model is required when auto mode falls back to llm")
        return _generate_seed_from_llm(target, prompt, model_name, target_dir, llm_output_mode)
    raise ValueError(f"Unsupported mode: {mode}")


def run_pipeline(
    targets: List[Dict],
    mode: str,
    model_name: Optional[str],
    results_root: Optional[Path] = None,
    prompt_style: str = "callchain",
    run_dir: Optional[Path] = None,
    llm_output_mode: str = "seed_base64",
) -> Path:
    results_root = results_root or RESULTS_DIR
    run_dir = ensure_dir(run_dir or (results_root / datetime.now().strftime("example_%Y%m%d_%H%M%S")))
    summary_items = []

    for target in targets:
        target_dir = ensure_dir(run_dir / target["id"])
        prompt = build_prompt(target, prompt_style=prompt_style, llm_output_mode=llm_output_mode)
        (target_dir / "prompt.txt").write_text(prompt, encoding="utf-8")

        llm_response, seed_bytes, seed_source = get_seed_bytes(
            target, prompt, mode, model_name, target_dir, llm_output_mode
        )
        if llm_response is not None:
            (target_dir / "llm_response.txt").write_text(llm_response, encoding="utf-8")

        input_file = target_dir / "input.bin"
        if not input_file.exists():
            input_file.write_bytes(seed_bytes)

        runner_result = run_target(target, input_file)
        (target_dir / "runner.stdout.txt").write_text(runner_result["stdout"], encoding="utf-8", errors="replace")
        (target_dir / "runner.stderr.txt").write_text(runner_result["stderr"], encoding="utf-8", errors="replace")

        result = {
            "id": target["id"],
            "language": target["language"],
            "project": target["project"],
            "target_line_spec": target["target_line_spec"],
            "prompt_style": prompt_style,
            "seed_source": seed_source,
            "llm_output_mode": normalize_llm_output_mode(target.get("llm_output_mode", llm_output_mode)),
            "seed_base64": encode_bytes(seed_bytes),
            "covered": runner_result["covered"],
            "returncode": runner_result["returncode"],
            "command": runner_result["command"],
        }
        (target_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        summary_items.append(result)

    summary = {
        "run_dir": str(run_dir),
        "mode": mode,
        "model": model_name,
        "prompt_style": prompt_style,
        "llm_output_mode": normalize_llm_output_mode(llm_output_mode),
        "target_count": len(targets),
        "results": summary_items,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir
