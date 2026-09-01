#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import socket
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OSS_FUZZ_ROOT = ROOT / "oss-fuzz"

CPP_PROJECT_CONFIGS = {
    "cpp-httplib": {
        "fuzz_target": "server_fuzzer",
        "source_root": OSS_FUZZ_ROOT / "build" / "out" / "cpp-httplib" / "src" / "cpp-httplib",
        "source_prefix": "/src/cpp-httplib",
    },
    "exiv2": {
        "fuzz_target": "fuzz-read-write",
        "source_root": OSS_FUZZ_ROOT / "build" / "out" / "exiv2" / "src" / "exiv2",
        "source_prefix": "/src/exiv2",
    },
    "jansson": {
        "fuzz_target": "json_load_dump_fuzzer",
        "source_root": OSS_FUZZ_ROOT / "build" / "out" / "jansson" / "src" / "jansson",
        "source_prefix": "/src/jansson",
    },
    "sqlite3": {
        "fuzz_target": "ossfuzz",
        "source_root": OSS_FUZZ_ROOT / "build" / "out" / "sqlite3" / "src" / "sqlite3",
        "source_prefix": "/src/sqlite3",
    },
}


def parse_target_line(target_line_str: str):
    rel_path, _, line_str = target_line_str.rpartition(":")
    if not rel_path or not line_str:
        raise SystemExit("target_line must be '<relative-path>:<line>'")
    try:
        return rel_path, int(line_str)
    except ValueError as exc:
        raise SystemExit(f"invalid line number: {line_str}") from exc


def _run_with_docker_access(cmd: str) -> subprocess.CompletedProcess:
    direct = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if direct.returncode == 0:
        return direct
    return subprocess.run(["sg", "docker", "-c", cmd], capture_output=True, text=True)


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_coverage(project: str, fuzz_target: str, out_dir: Path, input_file: str, corpus_dir: str, output_json: str) -> bool:
    os.makedirs(corpus_dir, exist_ok=True)
    shutil.copy2(input_file, os.path.join(corpus_dir, "seed.bin"))
    last_error = ""
    for _ in range(3):
        clean_cmd = (
            f"docker run --rm --privileged -v {out_dir}:/out "
            "gcr.io/oss-fuzz-base/base-runner:latest "
            "bash -c 'rm -rf /out/dumps && find /out -maxdepth 1 -name \"*.profraw\" -delete'"
        )
        _run_with_docker_access(clean_cmd)
        port = pick_free_port()
        coverage_cmd = (
            f"cd {OSS_FUZZ_ROOT} && "
            f"python3 infra/helper.py coverage {project} "
            f"--fuzz-target {fuzz_target} "
            f"--corpus-dir {corpus_dir} "
            f"--no-serve --no-corpus-download --port {port}"
        )
        proc = _run_with_docker_access(coverage_cmd)

        profdata = out_dir / "dumps" / "merged.profdata"
        if not profdata.exists():
            last_error = (proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or "")
            time.sleep(1)
            continue

        coverage_full = out_dir / "dumps" / "coverage_full.json"
        export_cmd = (
            "docker run --rm --privileged --shm-size=2g --platform linux/amd64 "
            f"-v {out_dir}:/out "
            "gcr.io/oss-fuzz-base/base-runner:latest "
            f"bash -lc 'llvm-cov export /out/{fuzz_target} "
            "-instr-profile=/out/dumps/merged.profdata > /out/dumps/coverage_full.json'"
        )
        export_proc = _run_with_docker_access(export_cmd)
        if coverage_full.exists():
            shutil.copy2(coverage_full, output_json)
            return True
        last_error = (export_proc.stdout or "") + ("\n" if export_proc.stdout and export_proc.stderr else "") + (export_proc.stderr or "")
        time.sleep(1)
    if last_error:
        sys.stderr.write(last_error.strip() + "\n")
    return False


def segments_to_executed_lines(segments: list) -> set:
    executed = set()
    if not segments:
        return executed
    sorted_segs = sorted(segments, key=lambda item: (item[0], item[1]))
    active_count = 0
    entry_counts = {}
    for seg in sorted_segs:
        line = seg[0]
        count = seg[2]
        has_count = seg[3]
        is_entry = seg[4] if len(seg) > 4 else False
        is_gap = seg[5] if len(seg) > 5 else False
        if has_count and is_entry and not is_gap:
            entry_counts.setdefault(line, []).append(count)
    for line in range(sorted_segs[0][0], sorted_segs[-1][0] + 1):
        if line in entry_counts:
            active_count = max(entry_counts[line])
        if active_count > 0:
            executed.add(line)
    return executed


def extract_coverage_for_file(coverage_json_path: str, source_key: str) -> set:
    with open(coverage_json_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    for item in payload["data"][0].get("files", []):
        filename = item.get("filename", "")
        if filename.endswith(source_key):
            return segments_to_executed_lines(item.get("segments", []))
    return set()


def find_function_range_from_coverage(coverage_json_path: str, source_key: str, target_line: int):
    with open(coverage_json_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    best = None
    best_size = float("inf")
    for func in payload["data"][0].get("functions", []):
        filenames = func.get("filenames", [])
        if not any(source_key in name for name in filenames):
            continue
        regions = func.get("regions", [])
        if not regions or len(regions[0]) < 4:
            continue
        start = regions[0][0]
        end = regions[0][2]
        if start <= target_line <= end and (end - start) < best_size:
            best_size = end - start
            best = (func.get("name", "<unknown>"), start, end)
    return best if best else ("<unknown>", target_line, target_line)


def find_function_range_from_source(source_path: Path, target_line: int):
    if not source_path.exists():
        return "<unknown>", target_line, target_line
    lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
    pattern = re.compile(r"^[\\w\\s\\*]+\\s+(\\w+)\\s*\\(")
    func_name = "<unknown>"
    func_start = target_line
    for idx in range(target_line - 1, -1, -1):
        line = lines[idx]
        match = pattern.match(line)
        if match and "{" in "".join(lines[idx:idx + 5]):
            func_name = match.group(1)
            func_start = idx + 1
            break
    brace_depth = 0
    func_end = target_line
    for idx in range(func_start - 1, len(lines)):
        brace_depth += lines[idx].count("{")
        brace_depth -= lines[idx].count("}")
        if brace_depth == 0 and idx + 1 >= target_line:
            func_end = idx + 1
            break
    return func_name, func_start, func_end


def print_function_coverage(source_path: Path, func_name: str, start_line: int, end_line: int, executed_lines: set):
    lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
    width = len(str(end_line))
    print(f"# function: {func_name} ({source_path.name} lines {start_line}-{end_line})")
    print()
    for lineno in range(start_line, end_line + 1):
        covered = 1 if lineno in executed_lines else 0
        raw = lines[lineno - 1] if lineno <= len(lines) else ""
        print(f"{covered}||{lineno:{width}}||{raw}")


def main_for_project(project: str) -> int:
    if project not in CPP_PROJECT_CONFIGS:
        raise SystemExit(f"unsupported C++ project: {project}")
    if len(sys.argv) != 3:
        raise SystemExit("usage: python tools/cpp_projects/run_<project>.py <target_line> <input_file>")

    rel_path, target_line = parse_target_line(sys.argv[1])
    input_file = sys.argv[2]
    if not os.path.exists(input_file):
        raise SystemExit(f"input file not found: {input_file}")

    cfg = CPP_PROJECT_CONFIGS[project]
    fuzz_target = cfg["fuzz_target"]
    out_dir = OSS_FUZZ_ROOT / "build" / "out" / project
    source_path = cfg["source_root"] / rel_path
    source_key = f"{cfg['source_prefix']}/{rel_path}"

    with tempfile.TemporaryDirectory() as tmpdir:
        corpus_dir = os.path.join(tmpdir, "corpus")
        output_json = os.path.join(tmpdir, "coverage_full.json")
        if not run_coverage(project, fuzz_target, out_dir, input_file, corpus_dir, output_json):
            raise SystemExit("failed to generate coverage json")
        func_name, start_line, end_line = find_function_range_from_coverage(output_json, source_key, target_line)
        if func_name == "<unknown>":
            func_name, start_line, end_line = find_function_range_from_source(source_path, target_line)
        executed_lines = extract_coverage_for_file(output_json, source_key)
        print_function_coverage(source_path, func_name, start_line, end_line, executed_lines)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python tools/run_cpp_coverage.py <project> <target_line> <input_file>")
    project = sys.argv[1]
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    return main_for_project(project)


if __name__ == "__main__":
    raise SystemExit(main())
