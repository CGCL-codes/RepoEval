#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.config import DEFAULT_TARGETS_FILE, RESULTS_DIR
from pipeline.core import run_pipeline
from pipeline.utils import load_targets
from scripts.check_env import collect_environment_problems


PROMPT_STYLES = ["callchain", "singlefile", "agentcontext"]
LLM_OUTPUT_MODES = ["seed_base64", "python_code", "base64_json_v1", "python_codegen_v1"]


def _write_index(run_root: Path, style_to_dir: dict[str, Path]) -> None:
    payload = {
        "run_root": str(run_root),
        "prompt_styles": {style: str(path) for style, path in style_to_dir.items()},
    }
    (run_root / "index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_style_with_retry(targets, mode, model, llm_output_mode, results_dir, style_dir, style, max_attempts=3):
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        if style_dir.exists():
            shutil.rmtree(style_dir, ignore_errors=True)
        try:
            return run_pipeline(
                targets,
                mode,
                model,
                results_dir,
                prompt_style=style,
                run_dir=style_dir,
                llm_output_mode=llm_output_mode,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < max_attempts:
                time.sleep(1)
    assert last_exc is not None
    raise last_exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the minimal RepoEval and AgenticDIG artifact example")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS_FILE, help="Path to test.json")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR, help="Directory for outputs")
    parser.add_argument("--mode", choices=["auto", "prebuilt", "llm"], default="prebuilt")
    parser.add_argument("--model", default=None, help="Model name to use in llm mode")
    parser.add_argument("--llm-output-mode", choices=LLM_OUTPUT_MODES, default="seed_base64")
    parser.add_argument("--language", choices=["python", "java", "cpp"], default=None, help="Only run one language")
    parser.add_argument("--prompt-style", choices=PROMPT_STYLES + ["all"], default="all")
    parser.add_argument("--skip-env-check", action="store_true", help="Skip environment validation")
    args = parser.parse_args()

    targets = load_targets(args.targets)
    if args.language:
        targets = [t for t in targets if t["language"] == args.language]
    if not targets:
        raise SystemExit("No targets selected")

    if not args.skip_env_check:
        problems = collect_environment_problems(targets)
        if problems:
            raise SystemExit(f"Environment check failed: {problems}")

    styles = PROMPT_STYLES if args.prompt_style == "all" else [args.prompt_style]
    run_root = args.results_dir / datetime.now().strftime("example_%Y%m%d_%H%M%S")
    run_root.mkdir(parents=True, exist_ok=True)
    style_to_dir = {}
    for style in styles:
        style_dir = run_root / style
        run_dir = _run_style_with_retry(
            targets,
            args.mode,
            args.model,
            args.llm_output_mode,
            args.results_dir,
            style_dir,
            style,
        )
        style_to_dir[style] = run_dir
    _write_index(run_root, style_to_dir)
    print(run_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
