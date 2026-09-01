#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.config import DEFAULT_TARGETS_FILE
from config.project_paths import CPP_RUNNER_PATHS, JAVA_RUNNER_PATHS, PYTHON_TEST_INTERPRETER
from pipeline.utils import load_targets, resolve_existing_path


def get_python_package_version(python_interpreter: Path, package_name: str) -> str:
    proc = subprocess.run(
        [
            str(python_interpreter),
            "-c",
            "import importlib.metadata as m, sys; print(m.version(sys.argv[1]))",
            package_name,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "version query failed")
    return proc.stdout.strip()


def collect_environment_problems(targets: List[Dict]) -> List[Dict]:
    problems: List[Dict] = []

    for target in targets:
        source_path, source_checked = resolve_existing_path(target.get("target_source_path"))
        if source_path is None and not target.get("target_source_snippet"):
            problems.append({"target": target["id"], "kind": "missing_source", "checked": source_checked})

        if target["language"] == "python":
            harness_path, harness_checked = resolve_existing_path(target.get("test_script_path"))
            python_path, python_checked = resolve_existing_path(
                target.get("python_interpreter_path"),
                PYTHON_TEST_INTERPRETER,
            )
            coverage_source_path, coverage_checked = resolve_existing_path(target.get("coverage_source_path"))
            coverage_source_spec = None
            if coverage_source_path is None and target.get("package_name"):
                coverage_source_spec = target["package_name"]
            version_expected = target.get("package_version")
            version_actual = None
            if python_path and target.get("package_name") and version_expected:
                try:
                    version_actual = get_python_package_version(python_path, target["package_name"])
                except Exception as exc:
                    version_actual = f"ERROR: {exc}"

            if python_path is None:
                problems.append({"target": target["id"], "kind": "missing_python_interpreter", "checked": python_checked})
            if coverage_source_path is None and coverage_source_spec is None:
                problems.append({"target": target["id"], "kind": "missing_python_cov_source", "checked": coverage_checked})
            if harness_path is None and not target.get("test_script_snippet"):
                problems.append({"target": target["id"], "kind": "missing_python_test_script", "checked": harness_checked})
            if version_expected and version_actual != version_expected:
                problems.append(
                    {
                        "target": target["id"],
                        "kind": "python_version_mismatch",
                        "expected": version_expected,
                        "actual": version_actual,
                    }
                )
        else:
            driver_path, driver_checked = resolve_existing_path(target.get("driver_path"))
            default_runner = JAVA_RUNNER_PATHS.get(target["project"]) if target["language"] == "java" else CPP_RUNNER_PATHS.get(target["project"])
            runner_path, runner_checked = resolve_existing_path(target.get("coverage_runner_path"), default_runner)
            if runner_path is None:
                problems.append({"target": target["id"], "kind": "missing_runner", "checked": runner_checked})
            if driver_path is None and not target.get("driver_snippet"):
                problems.append({"target": target["id"], "kind": "missing_driver", "checked": driver_checked})

    return problems


def main() -> int:
    targets = load_targets(DEFAULT_TARGETS_FILE)
    problems = collect_environment_problems(targets)
    java_runner_example = JAVA_RUNNER_PATHS.get("jsoup")
    cpp_runner_example = CPP_RUNNER_PATHS.get("jansson")

    print(f"targets_file: {DEFAULT_TARGETS_FILE}")
    print(f"project_config: {ROOT / 'config' / 'project_paths.py'}")
    print(f"java_runner_example: {java_runner_example}")
    print(f"cpp_runner_example: {cpp_runner_example}")
    print(f"default_python_interpreter: {PYTHON_TEST_INTERPRETER}")
    print()

    for target in targets:
        print(f"[{target['id']}]")
        print(f"  language: {target['language']}")
        print(f"  project:  {target['project']}")
        source_path, _ = resolve_existing_path(target.get("target_source_path"))
        print(f"  source_path: {'OK ' + str(source_path) if source_path else 'INLINE_SNIPPET'}")

        if target["language"] == "python":
            harness_path, _ = resolve_existing_path(target.get("test_script_path"))
            python_path, _ = resolve_existing_path(target.get("python_interpreter_path"), PYTHON_TEST_INTERPRETER)
            coverage_source_path, _ = resolve_existing_path(target.get("coverage_source_path"))
            coverage_source_desc = str(coverage_source_path) if coverage_source_path else target.get("package_name", "MISSING")
            print(f"  test_script: {'OK ' + str(harness_path) if harness_path else 'INLINE_SNIPPET'}")
            print(f"  interpreter: {'OK ' + str(python_path) if python_path else 'MISSING'}")
            print(f"  coverage_source: {'OK ' + coverage_source_desc if coverage_source_desc != 'MISSING' else 'MISSING'}")
            version_expected = target.get("package_version")
            if python_path and target.get("package_name") and version_expected:
                try:
                    version_actual = get_python_package_version(python_path, target['package_name'])
                except Exception as exc:
                    version_actual = f"ERROR: {exc}"
                print(f"  version: actual={version_actual} expected={version_expected}")
        else:
            driver_path, _ = resolve_existing_path(target.get("driver_path"))
            default_runner = JAVA_RUNNER_PATHS.get(target["project"]) if target["language"] == "java" else CPP_RUNNER_PATHS.get(target["project"])
            runner_path, _ = resolve_existing_path(target.get("coverage_runner_path"), default_runner)
            print(f"  driver: {'OK ' + str(driver_path) if driver_path else 'INLINE_SNIPPET'}")
            print(f"  runner: {'OK ' + str(runner_path) if runner_path else 'MISSING'}")
        print()

    print("problems:", json.dumps(problems, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
