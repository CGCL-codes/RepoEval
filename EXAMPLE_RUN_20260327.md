# Example Run Record

This artifact has been validated in the benchmark server environment with:

- a pinned Python benchmark environment
- an OSS-Fuzz checkout placed at `<repo-root>/oss-fuzz`

## Commands

```bash
<activate your pinned Python benchmark environment>
python3 scripts/check_env.py
bash scripts/run_example.sh
```

The example script launches three separate runs:

- `callchain`
- `singlefile`
- `agentcontext`

and writes a manifest file under `results/example_manifest_*.json`.

## Targets

- `1`
- `2`
- `3`

## Outcome

- `1`: returncode `0`, covered `false`
- `2`: returncode `0`, covered `false`
- `3`: returncode `0`, covered `false`

## Sanitized Snapshot

The repository includes a sanitized summary of one successful example run under:

- `results/example_run/summary.json`
