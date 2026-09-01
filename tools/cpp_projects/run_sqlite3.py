#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.run_cpp_coverage import main_for_project


if __name__ == "__main__":
    raise SystemExit(main_for_project("sqlite3"))
