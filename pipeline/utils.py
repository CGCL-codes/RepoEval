from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from config.project_paths import (
    CPP_RUNNER_PATHS,
    CPP_DRIVER_PATHS,
    CPP_SOURCE_ROOTS,
    JAVA_RUNNER_PATHS,
    JAVA_DRIVER_PATHS,
    JAVA_SOURCE_ROOTS,
    PYTHON_PACKAGE_ROOTS,
    PYTHON_PACKAGE_VERSIONS,
    PYTHON_TEST_SCRIPT_PATHS,
    PYTHON_TEST_INTERPRETER,
)


def _join_optional(root: Optional[Path], relative: Optional[str]) -> Optional[Path]:
    if root is None or not relative:
        return None
    return root / Path(relative)


def _enrich_target_from_project_config(target: Dict) -> Dict:
    merged = dict(target)
    language = str(merged.get("language", "")).strip()
    project = str(merged.get("project", "")).strip()

    if language == "python":
        package_root = PYTHON_PACKAGE_ROOTS.get(project)
        test_script = PYTHON_TEST_SCRIPT_PATHS.get(project)
        package_version = PYTHON_PACKAGE_VERSIONS.get(project)
        if not merged.get("python_interpreter_path") and PYTHON_TEST_INTERPRETER:
            merged["python_interpreter_path"] = PYTHON_TEST_INTERPRETER
        if not merged.get("target_source_path"):
            merged["target_source_path"] = _join_optional(package_root, merged.get("target_file"))
        if not merged.get("coverage_source_path") and package_root:
            merged["coverage_source_path"] = package_root
        if not merged.get("test_script_path") and test_script:
            merged["test_script_path"] = test_script
        if not merged.get("package_version") and package_version:
            merged["package_version"] = package_version
        return merged

    if language == "java":
        source_root = JAVA_SOURCE_ROOTS.get(project)
        driver_path = JAVA_DRIVER_PATHS.get(project)
        if not merged.get("target_source_path"):
            merged["target_source_path"] = _join_optional(source_root, merged.get("target_file"))
        if not merged.get("driver_path") and driver_path:
            merged["driver_path"] = driver_path
        runner_path = JAVA_RUNNER_PATHS.get(project)
        if not merged.get("coverage_runner_path") and runner_path:
            merged["coverage_runner_path"] = runner_path
        return merged

    if language == "cpp":
        source_root = CPP_SOURCE_ROOTS.get(project)
        driver_path = CPP_DRIVER_PATHS.get(project)
        if not merged.get("target_source_path"):
            merged["target_source_path"] = _join_optional(source_root, merged.get("target_file"))
        if not merged.get("driver_path") and driver_path:
            merged["driver_path"] = driver_path
        runner_path = CPP_RUNNER_PATHS.get(project)
        if not merged.get("coverage_runner_path") and runner_path:
            merged["coverage_runner_path"] = runner_path
        return merged

    return merged


def load_targets(path: Path) -> List[Dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    targets = payload.get("targets", [])
    if not isinstance(targets, list) or not targets:
        raise ValueError(f"No targets found in {path}")
    merged_targets = []
    for target in targets:
        if not isinstance(target, dict):
            raise ValueError(f"Invalid target entry in {path}: {target!r}")
        merged_targets.append(_enrich_target_from_project_config(target))
    return merged_targets


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_existing_path(*candidates: Union[str, Path, None]) -> Tuple[Optional[Path], List[str]]:
    checked: List[str] = []
    for candidate in candidates:
        if candidate is None:
            continue
        text = str(candidate).strip()
        if not text:
            continue
        checked.append(text)
        path = Path(text)
        if path.exists():
            return path, checked
    return None, checked


def encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def decode_bytes(seed_b64: str) -> bytes:
    return base64.b64decode(seed_b64)


def read_text_snippet(path: Path, target_line: int, radius: int) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, target_line - radius)
    end = min(len(lines), target_line + radius)
    rendered = []
    for line_no in range(start, end + 1):
        marker = ">>>" if line_no == target_line else "   "
        rendered.append(f"{marker} {line_no:4d}: {lines[line_no - 1]}")
    return "\n".join(rendered)


def read_full_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def trim_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...<trimmed>..."


def extract_seed_base64(response: str) -> Optional[str]:
    try:
        obj_match = re.search(r'\{.*?"seed_base64"\s*:\s*".*?"\s*\}', response, re.DOTALL)
        if obj_match:
            obj = json.loads(obj_match.group(0))
            seed = obj.get("seed_base64")
            if isinstance(seed, str) and seed:
                return seed
    except Exception:
        pass

    direct = re.search(r'"seed_base64"\s*:\s*"([A-Za-z0-9+/=]+)"', response)
    if direct:
        return direct.group(1)
    return None


def parse_target_hit_from_runner_output(stdout: str, target_line: int) -> bool:
    pattern = re.compile(rf"^([01])\|\|\s*{target_line}\|\|", re.MULTILINE)
    match = pattern.search(stdout)
    return bool(match and match.group(1) == "1")
