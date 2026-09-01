# ✨ RepoEval and AgenticDIG Artifact

![Python](https://img.shields.io/badge/Python-fixed--env-blue)
![Java](https://img.shields.io/badge/Java-docker-orange)
![C++](https://img.shields.io/badge/C%2B%2B-docker-brightgreen)

This repository is the artifact repo for:

**From Function to Repository: Towards Understanding and an Agentic Approach for Repo-Level Directed Input Generation**

It provides reproducible pipeline for the **Python + Java + C++** experiments used in the paper.


## 📖 Table of Contents

- [Docker Image](#docker-image-self-contained-recommended)
  - [Apple Silicon (arm64) hosts](#apple-silicon-arm64-hosts)
  - [Timeout configuration](#timeout-configuration)
- [Quick Start](#quick-start)
  - [Step 1: Installation](#step-1-installation)
  - [Step 2: Python-only smoke test](#step-2-python-only-smoke-test-recommended-first-check)
  - [Step 3: Prepare the Expected Environment](#step-3-prepare-the-expected-environment)
  - [Step 4: Prepare Java / C++ Coverage Builds](#step-4-prepare-java--c-coverage-builds)
  - [Step 5: Run the Example Pipeline](#step-5-run-the-example-pipeline)
  - [Step 6: Outputs](#step-6-outputs)
- [Test Dataset](#test-dataset)
- [Benchmark Extension](#benchmark-extension)
  - [Current scale](#current-scale)
  - [Planned expansion](#planned-expansion)
  - [How extensions are added](#how-extensions-are-added)
  - [Contributing](#contributing)
- [Example Results](#example-results)
- [Environment Summary](#environment-summary)
  - [Python](#python)
  - [Java / C++](#java--c)
- [AgenticDIG](#agenticdig)
- [License](#license)


# 🐳 Docker Image (Self-Contained, Recommended)

A fully self-contained `linux/amd64` Docker image is provided for running the
example pipeline. It includes the Python 3.13 environment with pinned packages,
the OSS-Fuzz checkout with prebuilt coverage builds for the 8 Java/C++ projects,
and an embedded Docker daemon.

> **Why `--privileged` is required.** The artifact container starts an **embedded
> Docker daemon** (DinD). That daemon is used to launch the OSS-Fuzz
> `base-runner` containers that perform Java and C++ coverage collection. Starting
> a nested Docker daemon inside a container requires `--privileged`. The pure
> Python targets do **not** need any of this — see the Python-only smoke test in
> [Quick Start](#-quick-start).

```bash
docker pull why9853/repo-dig:latest

docker run --privileged --platform linux/amd64 --rm \
  -v $PWD/results:/opt/repo-dig/results why9853/repo-dig:latest
```

The image is published as `latest` for convenience; for reproducible archival
please pin an immutable version tag, e.g. `why9853/repo-dig:v1.0`, once you have
pulled it.

This runs `scripts/run_example.sh` (3 prompt styles × 3 targets: `sqlparse`
/Python, `jsoup`/Java, `jansson`/C++) and writes outputs under
`/opt/repo-dig/results`.

To run a single prompt style / language:

```bash
docker run --privileged --platform linux/amd64 --rm why9853/repo-dig:latest \
  python3 scripts/run_test.py --mode prebuilt --prompt-style callchain --language python
```

To run the full 422-target dataset:

```bash
docker run --privileged --platform linux/amd64 --rm \
  -v $PWD/results:/opt/repo-dig/results why9853/repo-dig:latest \
  python3 scripts/run_test.py --mode prebuilt --prompt-style all \
  --targets data/full_targets.json --skip-env-check
```

### 🍎 Apple Silicon (arm64) hosts

The image is built for `linux/amd64`. On Apple Silicon (and other arm64 hosts)
Docker runs it under x86-64 emulation, which is **significantly slower** — the
Java/C++ coverage stages can take several times longer than on an x86-64 host and
may hit the runner timeout. Recommendations:

- For a quick check on Apple Silicon, run the **Python-only smoke test** (below),
  which needs no Docker at all.
- Run the full Java/C++ example on an x86-64 host (bare metal, VM, or CI) for
  realistic timings.
- Always pass `--platform linux/amd64` explicitly (as in the commands above).

### ⏱️ Timeout configuration

Each Java/C++ coverage run has a timeout (default 600 s). If a stage times out,
the pipeline **kills the whole spawned process group and removes any nested
OSS-Fuzz containers it started** before retrying, so retries never overlap with
orphaned work. You can tune the timeout and the results directory via environment
variables:

```bash
export REPRO_RUNNER_TIMEOUT_SEC=1200   # seconds, default 600
export REPRO_RESULTS_DIR=/path/to/results
```

If the Java/C++ example times out on a slow or emulated host, increase
`REPRO_RUNNER_TIMEOUT_SEC` (e.g. to 1200–1800) and rerun.

## 📋 Quick Start

### Step 1: Installation

```bash
cd <repo-root>/
conda create -n repo-dig python=3.13.9 -y
conda activate repo-dig
python3 -m pip install -r requirements.txt
```

You can clone this repository into any directory name. The commands below assume the default folder name `Repo-DIG-26`.

### Step 2: Python-only smoke test (recommended first check)

Before touching OSS-Fuzz or Docker, verify the Python side end-to-end with the
bundled `sqlparse` target. This needs **no OSS-Fuzz checkout, no Docker, and no
API key**:

```bash
cd <repo-root>/
python3 scripts/run_test.py --mode prebuilt --prompt-style callchain --language python
```

A successful run prints the timestamped run directory and writes
`prompt.txt`, `input.bin`, `runner.stdout.txt`, `runner.stderr.txt`,
`result.json` and `summary.json` under `results/`. The prebuilt seed
(`SELECT 1;`) is *not* expected to cover `sqlparse/utils.py:96`, so
`covered: false` with `returncode: 0` is the **expected** outcome for the
prebuilt example targets. The smoke test passes when the command prints the run
directory and writes `summary.json`.

You can also run `python3 scripts/check_env.py` to print the resolved environment
for all bundled targets and any problems found.

### Step 3: Prepare the Expected Environment

This artifact does not ask reviewers to fill machine-specific path templates.
Instead, it assumes a fixed project layout:

- Python runs from an activated benchmark-style environment
- Java / C++ run from an OSS-Fuzz checkout placed at:
  - `<repo-root>/oss-fuzz`

The repository conventions for all 12 benchmark projects are encoded in:

- `config/project_paths.py`

All benchmark repositories covered by the artifact are:

- Python: `pycparser`, `scapy`, `mutagen`, `sqlparse`
- Java: `async-http-client`, `jedis`, `jsoup`, `metadata-extractor`
- C++: `cpp-httplib`, `exiv2`, `jansson`, `sqlite3`

The Python section is intended for a **fixed package environment**.
The current shell should use that pinned Python environment before running any artifact command.
`atheris` should also be available for the `pycparser` test script.

Each Java/C++ project also has its own dedicated runner script in the repository:

- Java:
  - `tools/java_projects/run_async_http_client.py`
  - `tools/java_projects/run_jedis.py`
  - `tools/java_projects/run_jsoup.py`
  - `tools/java_projects/run_metadata_extractor.py`
- C++:
  - `tools/cpp_projects/run_cpp_httplib.py`
  - `tools/cpp_projects/run_exiv2.py`
  - `tools/cpp_projects/run_jansson.py`
  - `tools/cpp_projects/run_sqlite3.py`

### Step 4: Prepare Java / C++ Coverage Builds

The Java and C++ examples assume an OSS-Fuzz checkout that has already been built in coverage mode.

Expected layout:

```text
Repo-DIG-26/
  oss-fuzz/
    infra/
    build/
    projects/
```

RUN the build script:

```bash
cd <repo-root>/
bash scripts/oss_fuzz_build.sh
```



The bundled example targets use the standard OSS-Fuzz layout under `<repo-root>/oss-fuzz`.

### Step 5: Run the Example Pipeline

Run the deterministic example pipeline with one command:

```bash
bash scripts/run_example.sh
```

This script:

- loads `data/test.json`
- checks the required project paths
- builds prompts
- writes one input file per example target
- runs the Python/Java/C++ test pipeline
- runs three example invocations, one per prompt style:
  - `callchain`
  - `singlefile`
  - `agentcontext`
- saves the outputs under `results/`
- writes a manifest file `results/example_manifest_*.json`

The bundled example script is the recommended artifact entrypoint.
It is designed for reviewers who want one command that checks the environment and runs one example target for each language.

**What a successful run looks like:** the script prints the three run directories
and writes `results/example_manifest_*.json`. For the bundled prebuilt seeds,
`covered: false` with `returncode: 0` is the **expected** outcome — exit code 0
means the pipeline executed the coverage runner, not that the target line was
reached. Rough runtimes: the Python-only smoke test takes about 10–30 s; the full
nine-run example takes roughly 15–40 min on a fast x86-64 host and can be several
times longer under arm64 emulation (raise `REPRO_RUNNER_TIMEOUT_SEC` if needed).

To run with a live model instead of the prebuilt seed, you must supply your **own
API key** — the artifact does not bundle or provide one:

```bash
export DEEPSEEK_API_KEY=<your-key>   # required in llm mode
python3 scripts/run_test.py --mode llm --model deepseek-v3 --prompt-style all
```

Only `prebuilt` mode runs without an API key. The supported models and the
environment variables for their keys are: `deepseek-v3` / `deepseek-r1`
(`DEEPSEEK_API_KEY`), `gpt-5-mini` (`OPENAI_API_KEY`), and `qwen3-coder-flash`
(`QWEN_API_KEY`) — see `config/config.py`.

The artifact supports four `--llm-output-mode` values; the first two are
canonical names and the last two are accepted aliases that normalize to them:

- `--llm-output-mode seed_base64`: the model returns a JSON object with `seed_base64` (alias: `base64_json_v1`)
- `--llm-output-mode python_code`: the model returns Python code that writes the seed bytes to `output_file` (alias: `python_codegen_v1`)

Example:

```bash
export DEEPSEEK_API_KEY=<your-key>
python3 scripts/run_test.py --mode llm --model deepseek-v3 --llm-output-mode python_code --prompt-style all
```

### Step 6: Outputs

Each run creates a timestamped directory under `results/`.

Per target, the pipeline writes:

- `prompt.txt`
- `llm_response.txt` in `llm` mode
- `input.bin`
- `runner.stdout.txt`
- `runner.stderr.txt`
- `result.json`

Each per-style run root contains `summary.json`.
The top-level example script also writes a manifest file that maps prompt style to run directory.


## Test Dataset

The artifact ships with exactly one test dataset:

- `data/test.json`

It contains exactly three example targets:

- Python: `1`
- Java: `2`
- C++: `3`

Each target entry includes:

- target metadata
- call-chain metadata
- one prebuilt seed for deterministic example execution
- embedded source snippet
- embedded harness snippet
- single-file prompt context
- agent-context prompt context

The complete targets are stored in `data/full_targets.json`.


## Benchmark Extension

This artifact is a **living benchmark**: the bundled dataset is the first
release, and we will keep expanding its scale in follow-up releases.

### Current scale

The first release covers **422 target lines across 12 real-world repositories**
in three languages:

- **Python (108 targets, 4 repos):** `pycparser`, `scapy`, `mutagen`, `sqlparse`
- **Java (152 targets, 4 repos):** `async-http-client`, `jedis`, `jsoup`, `metadata-extractor`
- **C++ (162 targets, 4 repos):** `cpp-httplib`, `exiv2`, `jansson`, `sqlite3`

Each target is a specific source line that reaches a complex input-parsing
routine, together with its call chain, prebuilt seed, and prompt context
(`data/full_targets.json`).

### Planned expansion

We plan to continuously extend the benchmark along several dimensions:

- **More repositories and target lines.** Add new upstream projects (and more
  target lines in the existing 12) so that coverage spans a broader, more
diverse set of parsing and deserialization code.
- **More languages.** Extend the pipeline beyond Python / Java / C++ to other
  ecosystems supported by OSS-Fuzz-style coverage builds.
- **Deeper call chains.** Include targets whose call chains cross package
  boundaries and require longer, multi-step repository-level reasoning.
- **More prompt styles and models.** Keep the prompt-construction and
  evaluation interfaces stable while adding new prompt styles and evaluated
  models as they become available.

### How extensions are added

New targets are added purely as **data**: each entry in
`data/full_targets.json` (schema versioned via `metadata.schema_version`)
carries its own metadata, call chain, prebuilt seed, and prompt snippets, so
**no pipeline code changes are required** to evaluate a newly added target.
The per-project runner scripts live in `tools/` and are referenced by
`target.test_script_path`. Releases that add targets bump the dataset version
and record per-project counts in `metadata.project_counts`.

### Contributing

We welcome benchmark extensions from the community. If you would like to add
repositories, target lines, or new evaluation dimensions, please open an issue
or a pull request against this repository; see `LICENSE` for the terms under
which the benchmark is released.


## Example Results

The repository includes a sanitized example-run snapshot under:

- `results/example_run/`

This snapshot shows the structure and outcome of a successful server-side run without exposing machine-specific absolute paths.

> The tracked snapshot records `covered: false` for all three example targets.
> This is expected in prebuilt mode: the bundled seeds exercise the harness but
> are not designed to reach the exact target lines. The success criterion is a
> completed run (exit code 0) with `prompt.txt`, `input.bin` and `result.json`
> written per target and a `summary.json` per prompt style.


## Environment Summary

### Python

- **Interpreter**: `Python 3.13.9`
- **Execution mode**: direct project-specific test scripts, no docker
- **Pinned packages**:
  - `pycparser == 2.23`
  - `scapy == 2.6.1`
  - `mutagen == 1.47.0`
  - `sqlparse == 0.5.5`
- **Bundled project scripts**:

| Project | Script |
| --- | --- |
| `pycparser` | `tools/python_tests/test_c_parser.py` |
| `scapy` | `tools/python_tests/test_pcap.py` |
| `mutagen` | `tools/python_tests/test_parser.py` |
| `sqlparse` | `tools/python_tests/test_parse.py` |

### Java / C++

- **Docker**: tested with `Docker version 26.1.3`
- **Build style**: OSS-Fuzz coverage builds driven by `infra/helper.py`
- **Base image used by the runner scripts**: `gcr.io/oss-fuzz-base/base-runner:latest`
- **OSS-Fuzz location**: place the OSS-Fuzz checkout at `<repo-root>/oss-fuzz`
- **Docker access**: the current user should be able to run docker commands directly or via the `docker` group
- **Per-project repository scripts**:

| Language | Project | Script |
| --- | --- | --- |
| Java | `async-http-client` | `tools/java_projects/run_async_http_client.py` |
| Java | `jedis` | `tools/java_projects/run_jedis.py` |
| Java | `jsoup` | `tools/java_projects/run_jsoup.py` |
| Java | `metadata-extractor` | `tools/java_projects/run_metadata_extractor.py` |
| C++ | `cpp-httplib` | `tools/cpp_projects/run_cpp_httplib.py` |
| C++ | `exiv2` | `tools/cpp_projects/run_exiv2.py` |
| C++ | `jansson` | `tools/cpp_projects/run_jansson.py` |
| C++ | `sqlite3` | `tools/cpp_projects/run_sqlite3.py` |


# AgenticDIG

The `AgenticDIG` directory contains the code for the agentic approach described in the paper.

## License

The artifact code in this repository is released under the Apache-2.0 license —
see `LICENSE`. Third-party source trees vendored under `python_packages/`
(`scapy`, `sqlparse`, `mutagen`, `pycparser`) are redistributed unmodified under
their own licenses (some GPL); see `THIRD_PARTY_NOTICES.md` for details.
