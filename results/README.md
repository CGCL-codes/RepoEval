Tracked files under `results/` are sanitized examples only.

Actual example runs are written to timestamped directories such as `results/example_YYYYMMDD_HHMMSS/`.
Those live run directories are ignored by git because they contain machine-specific paths and raw execution logs.

The tracked snapshot under `results/example_run/` mirrors the multi-style example layout:

- `index.json`
- `callchain/summary.json`
- `singlefile/summary.json`
- `agentcontext/summary.json`
