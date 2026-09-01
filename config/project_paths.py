import sys
from pathlib import Path
from typing import Dict, Optional

from .config import ROOT


# This module encodes the repository's default project layout.
# Reviewers only need to prepare the expected environment:
# - activate the pinned Python environment before running Python targets
# - place OSS-Fuzz under <repo-root>/oss-fuzz for Java/C++

OSS_FUZZ_ROOT = ROOT / "oss-fuzz"
PYTHON_TEST_INTERPRETER = Path(sys.executable)

PYTHON_PACKAGE_ROOTS: Dict[str, Optional[Path]] = {
    "pycparser": "your_conda_env/envs/agentic_dig/lib/python3.13/site-packages/pycparser",
    "scapy": "your_conda_env/envs/agentic_dig/lib/python3.13/site-packages/scapy",
    "mutagen": "your_conda_env/envs/agentic_dig/lib/python3.13/site-packages/mutagen",
    "sqlparse": "your_conda_env/envs/agentic_dig/lib/python3.13/site-packages/sqlparse",
}

PYTHON_TEST_SCRIPT_PATHS: Dict[str, Optional[Path]] = {
    "pycparser": ROOT / "tools" / "python_tests" / "test_c_parser.py",
    "scapy": ROOT / "tools" / "python_tests" / "test_pcap.py",
    "mutagen": ROOT / "tools" / "python_tests" / "test_parser.py",
    "sqlparse": ROOT / "tools" / "python_tests" / "test_parse.py",
}

PYTHON_PACKAGE_VERSIONS: Dict[str, str] = {
    "pycparser": "2.23",
    "scapy": "2.6.1",
    "mutagen": "1.47.0",
    "sqlparse": "0.5.5",
}

JAVA_RUNNER_PATHS: Dict[str, Path] = {
    "async-http-client": ROOT / "tools" / "java_projects" / "run_async_http_client.py",
    "jedis": ROOT / "tools" / "java_projects" / "run_jedis.py",
    "jsoup": ROOT / "tools" / "java_projects" / "run_jsoup.py",
    "metadata-extractor": ROOT / "tools" / "java_projects" / "run_metadata_extractor.py",
}

JAVA_SOURCE_ROOTS: Dict[str, Optional[Path]] = {
    "async-http-client": OSS_FUZZ_ROOT / "build" / "out" / "async-http-client" / "src" / "project-parent" / "async-http-client" / "client" / "src" / "main" / "java",
    "jedis": OSS_FUZZ_ROOT / "build" / "out" / "jedis" / "src" / "jedis" / "src" / "main" / "java",
    "jsoup": OSS_FUZZ_ROOT / "build" / "out" / "jsoup" / "src" / "jsoup" / "src" / "main" / "java",
    "metadata-extractor": OSS_FUZZ_ROOT / "build" / "out" / "metadata-extractor" / "src" / "metadata-extractor" / "Source",
}

JAVA_DRIVER_PATHS: Dict[str, Optional[Path]] = {
    "async-http-client": OSS_FUZZ_ROOT / "projects" / "async-http-client" / "project-parent" / "fuzz-targets" / "src" / "test" / "java" / "com" / "example" / "AsyncHttpClientFuzzer.java",
    "jedis": OSS_FUZZ_ROOT / "projects" / "jedis" / "JedisURIFuzzer.java",
    "jsoup": OSS_FUZZ_ROOT / "projects" / "jsoup" / "HtmlFuzzer.java",
    "metadata-extractor": OSS_FUZZ_ROOT / "projects" / "metadata-extractor" / "ImageMetadataReaderFuzzer.java",
}

CPP_RUNNER_PATHS: Dict[str, Path] = {
    "cpp-httplib": ROOT / "tools" / "cpp_projects" / "run_cpp_httplib.py",
    "exiv2": ROOT / "tools" / "cpp_projects" / "run_exiv2.py",
    "jansson": ROOT / "tools" / "cpp_projects" / "run_jansson.py",
    "sqlite3": ROOT / "tools" / "cpp_projects" / "run_sqlite3.py",
}

CPP_SOURCE_ROOTS: Dict[str, Optional[Path]] = {
    "cpp-httplib": OSS_FUZZ_ROOT / "build" / "out" / "cpp-httplib" / "src" / "cpp-httplib",
    "exiv2": OSS_FUZZ_ROOT / "build" / "out" / "exiv2" / "src" / "exiv2",
    "jansson": OSS_FUZZ_ROOT / "build" / "out" / "jansson" / "src" / "jansson",
    "sqlite3": OSS_FUZZ_ROOT / "build" / "out" / "sqlite3" / "src" / "sqlite3",
}

CPP_DRIVER_PATHS: Dict[str, Optional[Path]] = {
    "cpp-httplib": OSS_FUZZ_ROOT / "projects" / "cpp-httplib" / "src" / "cpp-httplib" / "test" / "fuzzing" / "server_fuzzer.cc",
    "exiv2": OSS_FUZZ_ROOT / "build" / "out" / "exiv2" / "src" / "exiv2" / "fuzz" / "fuzz-read-write.cpp",
    "jansson": OSS_FUZZ_ROOT / "build" / "out" / "jansson" / "src" / "jansson" / "test" / "ossfuzz" / "json_load_dump_fuzzer.cc",
    "sqlite3": OSS_FUZZ_ROOT / "build" / "out" / "sqlite3" / "src" / "sqlite3" / "test" / "ossfuzz.c",
}
