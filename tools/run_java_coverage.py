#!/usr/bin/env python3
from __future__ import annotations

import os
import socket
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OSS_FUZZ_ROOT = ROOT / "oss-fuzz"

JAVA_PROJECT_CONFIGS = {
    "async-http-client": {
        "fuzz_target": "AsyncHttpClientFuzzer",
        "source_root": OSS_FUZZ_ROOT / "build" / "out" / "async-http-client" / "src" / "project-parent" / "async-http-client" / "client" / "src" / "main" / "java",
    },
    "jedis": {
        "fuzz_target": "JedisURIFuzzer",
        "source_root": OSS_FUZZ_ROOT / "build" / "out" / "jedis" / "src" / "jedis" / "src" / "main" / "java",
    },
    "jsoup": {
        "fuzz_target": "HtmlFuzzer",
        "source_root": OSS_FUZZ_ROOT / "build" / "out" / "jsoup" / "src" / "jsoup" / "src" / "main" / "java",
    },
    "metadata-extractor": {
        "fuzz_target": "ImageMetadataReaderFuzzer",
        "source_root": OSS_FUZZ_ROOT / "build" / "out" / "metadata-extractor" / "src" / "metadata-extractor" / "Source",
    },
}


def parse_target_line(source_root: Path, target_line_str: str):
    path_part, _, line_str = target_line_str.rpartition(":")
    if not path_part or not line_str:
        raise SystemExit("target_line must be '<relative-path>:<line>'")
    try:
        target_line = int(line_str)
    except ValueError as exc:
        raise SystemExit(f"invalid line number: {line_str}") from exc

    if os.path.isabs(path_part):
        source_path = Path(path_part)
        text = str(source_path).replace("\\", "/")
        marker = "src/main/java/"
        idx = text.find(marker)
        if idx != -1:
            pkg_key = text[idx + len(marker):]
        else:
            alt_marker = "/Source/"
            idx = text.find(alt_marker)
            pkg_key = text[idx + len(alt_marker):] if idx != -1 else source_path.name
    else:
        pkg_key = path_part
        source_path = source_root / pkg_key

    if not source_path.exists():
        raise SystemExit(f"source file not found: {source_path}")
    return source_path, pkg_key, target_line


def _run_with_docker_access(cmd: str) -> subprocess.CompletedProcess:
    direct = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if direct.returncode == 0:
        return direct
    return subprocess.run(["sg", "docker", "-c", cmd], capture_output=True, text=True)


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run_coverage(project: str, fuzz_target: str, out_dir: Path, jacoco_xml: Path, input_file: str, corpus_dir: str) -> bool:
    os.makedirs(corpus_dir, exist_ok=True)
    shutil.copy2(input_file, os.path.join(corpus_dir, "seed.bin"))
    last_error = ""
    for _ in range(3):
        clean_cmd = (
            f"docker run --rm --privileged -v {out_dir}:/out "
            "gcr.io/oss-fuzz-base/base-runner:latest "
            "bash -c 'rm -rf /out/report /out/dumps'"
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
        if jacoco_xml.exists():
            return True
        last_error = (proc.stdout or "") + ("\n" if proc.stdout and proc.stderr else "") + (proc.stderr or "")
        time.sleep(1)
    if last_error:
        sys.stderr.write(last_error.strip() + "\n")
    return False


def jacoco_xml_to_coverage(xml_path: Path):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    coverage = {}
    for pkg in root.findall(".//package"):
        pkg_name = pkg.get("name", "")
        for src in pkg.findall("sourcefile"):
            key = f"{pkg_name}/{src.get('name', '')}"
            lines = {}
            for line in src.findall("line"):
                nr = int(line.get("nr", "0"))
                ci = int(line.get("ci", "0"))
                lines[nr] = {"ci": ci, "hit": ci > 0}
            coverage[key] = lines
    return coverage


def find_method_range(xml_path: Path, pkg_key: str, target_line: int):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    src_filename = os.path.basename(pkg_key)
    pkg_dir = os.path.dirname(pkg_key)
    methods = []

    for cls in root.findall(".//class"):
        if cls.get("sourcefilename", "") != src_filename:
            continue
        cls_name = cls.get("name", "")
        if pkg_dir and not cls_name.startswith(pkg_dir):
            continue
        for method in cls.findall("method"):
            mline = method.get("line")
            if mline is not None:
                methods.append((method.get("name", "<unknown>"), int(mline)))

    methods.sort(key=lambda item: item[1])
    for idx, (name, start) in enumerate(methods):
        end = methods[idx + 1][1] - 1 if idx + 1 < len(methods) else target_line + 50
        if start <= target_line <= end:
            return name, start, end
    return "<unknown>", target_line, target_line


def print_function_coverage(source_path: Path, func_name: str, start_line: int, end_line: int, coverage: dict):
    lines = source_path.read_text(encoding="utf-8", errors="replace").splitlines()
    actual_end = min(end_line, len(lines))
    width = len(str(actual_end))
    print(f"# function: {func_name} ({source_path.name} lines {start_line}-{actual_end})")
    print()
    for lineno in range(start_line, actual_end + 1):
        line_info = coverage.get(lineno, {})
        covered = 1 if line_info.get("hit", False) else 0
        raw = lines[lineno - 1] if lineno <= len(lines) else ""
        print(f"{covered}||{lineno:{width}}||{raw}")


def main_for_project(project: str) -> int:
    if project not in JAVA_PROJECT_CONFIGS:
        raise SystemExit(f"unsupported Java project: {project}")
    if len(sys.argv) != 3:
        raise SystemExit("usage: python tools/java_projects/run_<project>.py <target_line> <input_file>")

    target_line_arg = sys.argv[1]
    input_file = sys.argv[2]
    if not os.path.exists(input_file):
        raise SystemExit(f"input file not found: {input_file}")

    cfg = JAVA_PROJECT_CONFIGS[project]
    out_dir = OSS_FUZZ_ROOT / "build" / "out" / project
    jacoco_xml = out_dir / "report" / "linux" / "index.xml"
    source_root = cfg["source_root"]
    fuzz_target = cfg["fuzz_target"]

    source_path, pkg_key, target_line = parse_target_line(source_root, target_line_arg)
    with tempfile.TemporaryDirectory() as tmpdir:
        corpus_dir = os.path.join(tmpdir, "corpus")
        if not run_coverage(project, fuzz_target, out_dir, jacoco_xml, input_file, corpus_dir):
            raise SystemExit(f"failed to generate JaCoCo XML: {jacoco_xml}")
        all_coverage = jacoco_xml_to_coverage(jacoco_xml)
        file_coverage = all_coverage.get(pkg_key, {})
        func_name, start_line, end_line = find_method_range(jacoco_xml, pkg_key, target_line)
        print_function_coverage(source_path, func_name, start_line, end_line, file_coverage)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: python tools/run_java_coverage.py <project> <target_line> <input_file>")
    project = sys.argv[1]
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    return main_for_project(project)


if __name__ == "__main__":
    raise SystemExit(main())
