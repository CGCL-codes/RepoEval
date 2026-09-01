import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Set

from config.config import RUNNER_TIMEOUT_SEC
from config.project_paths import CPP_RUNNER_PATHS, JAVA_RUNNER_PATHS, PYTHON_TEST_INTERPRETER
from .utils import parse_target_hit_from_runner_output, resolve_existing_path

DOCKER_PROBE_TIMEOUT_SEC = 15


def resolve_runner_path(target: dict) -> Path:
    default_runner = JAVA_RUNNER_PATHS.get(target["project"]) if target["language"] == "java" else CPP_RUNNER_PATHS.get(target["project"])
    runner_path, checked = resolve_existing_path(target.get("coverage_runner_path"), default_runner)
    if runner_path is None:
        raise FileNotFoundError(f"Unable to resolve coverage runner for {target['id']}. Checked: {checked}")
    return runner_path


def resolve_python_interpreter(target: dict) -> Path:
    python_path, checked = resolve_existing_path(target.get("python_interpreter_path"), PYTHON_TEST_INTERPRETER)
    if python_path is None:
        raise FileNotFoundError(f"Unable to resolve Python interpreter for {target['id']}. Checked: {checked}")
    return python_path


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=DOCKER_PROBE_TIMEOUT_SEC,
        )
        return result.returncode == 0
    except Exception:
        return False


def _list_container_ids() -> Set[str]:
    try:
        result = subprocess.run(
            ["docker", "ps", "-q"],
            capture_output=True,
            text=True,
            timeout=DOCKER_PROBE_TIMEOUT_SEC,
        )
    except Exception:
        return set()
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _kill_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _cleanup_nested_containers(before: Set[str]) -> None:
    after = _list_container_ids()
    orphaned = after - before
    for cid in sorted(orphaned):
        try:
            subprocess.run(
                ["docker", "rm", "-f", cid],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
            )
        except Exception:
            pass
    if orphaned:
        sys.stderr.write(f"[cleanup] removed orphaned nested containers: {sorted(orphaned)}\n")


def run_command_with_timeout(cmd, timeout: int, track_containers: bool = False) -> subprocess.CompletedProcess:
    """Run a command, and on timeout kill the whole spawned process group.

    Java/C++ coverage runners start nested OSS-Fuzz Docker containers. When the
    runner is killed on timeout, those containers survive independently, so the
    process group kill is followed by removing every container that was spawned
    while the command was running (track_containers=True). This prevents
    overlapping orphaned coverage runs on retry.
    """
    containers_before = _list_container_ids() if track_containers else set()
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_group(proc)
        try:
            stdout, stderr = proc.communicate(timeout=DOCKER_PROBE_TIMEOUT_SEC)
        except subprocess.TimeoutExpired:
            stdout = proc.stdout.read() if proc.stdout else ""
            stderr = proc.stderr.read() if proc.stderr else ""
            _kill_process_group(proc)
        if track_containers:
            _cleanup_nested_containers(containers_before)
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout, output=stdout, stderr=stderr) from None
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


def run_external_coverage_runner(target: dict, input_file: Path) -> dict:
    runner = resolve_runner_path(target)
    cmd = [sys.executable, str(runner), target["target_line_spec"], str(input_file)]
    try:
        proc = run_command_with_timeout(cmd, RUNNER_TIMEOUT_SEC, track_containers=True)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(
            f"Coverage runner for {target['id']} exceeded {RUNNER_TIMEOUT_SEC}s "
            f"and was terminated. Its process group was killed and any nested "
            f"Docker containers it spawned were removed.\n"
            f"runner: {runner}\n"
            f"STDOUT tail:\n{(exc.output or '')[-2000:]}\n"
            f"STDERR tail:\n{(exc.stderr or '')[-2000:]}"
        ) from exc
    covered = parse_target_hit_from_runner_output(proc.stdout, int(target["target_line"]))
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "covered": covered,
    }


def check_python_target_line_covered(python_interpreter: Path, coverage_file: Path, target_line_spec: str) -> bool:
    script = """
import coverage
import sys

cov = coverage.Coverage(data_file=sys.argv[1])
cov.load()
target_suffix, line_str = sys.argv[2].rsplit(":", 1)
target_suffix = target_suffix.replace("\\\\", "/")
line_no = int(line_str)
matched = None
for measured in cov.get_data().measured_files():
    if measured.replace("\\\\", "/").endswith(target_suffix):
        matched = measured
        break
if not matched:
    print("0")
    raise SystemExit(0)
analysis = cov.analysis2(matched)
statements = analysis[1]
missing = analysis[3]
print("1" if (line_no in statements and line_no not in missing) else "0")
"""
    proc = subprocess.run(
        [str(python_interpreter), "-c", script, str(coverage_file), target_line_spec],
        capture_output=True,
        text=True,
        timeout=RUNNER_TIMEOUT_SEC,
    )
    return proc.returncode == 0 and proc.stdout.strip().endswith("1")


def run_python_target(target: dict, input_file: Path) -> dict:
    python_interpreter = resolve_python_interpreter(target)
    test_script_path, checked = resolve_existing_path(target.get("test_script_path"))
    if test_script_path is None:
        raise FileNotFoundError(f"Unable to resolve Python test script for {target['id']}. Checked: {checked}")
    source_path, checked = resolve_existing_path(target.get("coverage_source_path"))
    coverage_source_arg = str(source_path) if source_path is not None else target.get("package_name")
    if not coverage_source_arg:
        raise FileNotFoundError(f"Unable to resolve Python coverage source for {target['id']}. Checked: {checked}")

    coverage_file = input_file.with_suffix(".coverage")
    cmd = [
        str(python_interpreter),
        "-m",
        "coverage",
        "run",
        "--data-file",
        str(coverage_file),
        "--source",
        coverage_source_arg,
        str(test_script_path),
        str(input_file),
    ]
    proc = run_command_with_timeout(cmd, RUNNER_TIMEOUT_SEC, track_containers=False)
    covered = False
    if coverage_file.exists():
        covered = check_python_target_line_covered(
            python_interpreter, coverage_file, target["target_line_spec"]
        )
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "covered": covered,
    }


def run_target(target: dict, input_file: Path) -> dict:
    language = target["language"]
    if language in {"java", "cpp"}:
        return run_external_coverage_runner(target, input_file)
    if language == "python":
        return run_python_target(target, input_file)
    raise ValueError(f"Unsupported language: {language}")
