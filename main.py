#!/usr/bin/env python3
import argparse
from pathlib import Path

from config.config import DEFAULT_TARGETS_FILE, RESULTS_DIR
from pipeline.core import run_pipeline
from pipeline.utils import load_targets

LLM_OUTPUT_MODES = ["seed_base64", "python_code", "base64_json_v1", "python_codegen_v1"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Minimal reproducible RepoEval and AgenticDIG artifact pipeline")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS_FILE, help="Path to test.json")
    parser.add_argument("--results-dir", type=Path, default=RESULTS_DIR, help="Directory for outputs")
    parser.add_argument("--mode", choices=["auto", "prebuilt", "llm"], default="prebuilt")
    parser.add_argument("--model", default=None, help="Model name to use in llm mode")
    parser.add_argument("--llm-output-mode", choices=LLM_OUTPUT_MODES, default="seed_base64")
    parser.add_argument("--language", choices=["java", "cpp", "python"], default=None, help="Only run one language")
    parser.add_argument("--prompt-style", choices=["callchain", "singlefile", "agentcontext"], default="callchain")
    args = parser.parse_args()

    targets = load_targets(args.targets)
    if args.language:
        targets = [t for t in targets if t["language"] == args.language]
    if not targets:
        raise SystemExit("No targets selected")

    run_dir = run_pipeline(
        targets,
        args.mode,
        args.model,
        args.results_dir,
        prompt_style=args.prompt_style,
        llm_output_mode=args.llm_output_mode,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
