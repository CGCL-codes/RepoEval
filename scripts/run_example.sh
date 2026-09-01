#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

cd "$ROOT_DIR"

CALLCHAIN_DIR="$(python3 scripts/run_test.py --mode prebuilt --prompt-style callchain)"
SINGLEFILE_DIR="$(python3 scripts/run_test.py --mode prebuilt --prompt-style singlefile)"
AGENTCONTEXT_DIR="$(python3 scripts/run_test.py --mode prebuilt --prompt-style agentcontext)"

MANIFEST_PATH="results/example_manifest_$(date +%Y%m%d_%H%M%S).json"
python3 - <<PY
import json
from pathlib import Path

payload = {
    "callchain": "${CALLCHAIN_DIR}",
    "singlefile": "${SINGLEFILE_DIR}",
    "agentcontext": "${AGENTCONTEXT_DIR}",
}
path = Path("${MANIFEST_PATH}")
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(path)
PY
