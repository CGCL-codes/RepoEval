---
name: cpp-directed-input-verification-skill
description: Executes tests with specific binary input files to generate standardized JSON code coverage reports for validating directed inputs in C/C++ projects using LLVM coverage tools.
---

# cpp-directed-input-verification-skill

This skill is designed specifically for **validating directed binary inputs** in integration testing scenarios for C/C++ projects. It automates the collection of code coverage using LLVM's instrumentation-based coverage tools and generates structured JSON reports. The skill leverages the OSS-Fuzz infrastructure with the `helper.py coverage` command to execute fuzz targets with provided binary input files, ultimately producing a machine-readable JSON report suitable for verifying if specific target lines were hit.

## When to Use This Skill

- Directed Input Generation: Call this skill when generating directed test inputs for a specific C/C++ project to verify if the generated payload successfully triggers target code paths.

- Input Validation: Use this skill when you need to verify the effectiveness of a generated binary input for a C/C++ program by analyzing the resulting code coverage.

- Coverage Reporting: Use this skill when coverage data needs to be converted into a structured JSON format to confirm whether specific target lines (e.g., in fuzzing or directed testing scenarios) were executed.


## Prerequisites

- OSS-Fuzz environment must be set up at `./oss-fuzz`
- Docker access with `sg docker -c` command capability
- The C/C++ project must be configured in the OSS-Fuzz structure with coverage instrumentation
- LLVM toolchain available in the `gcr.io/oss-fuzz-base/base-runner` Docker image


## Key Parameters (Customizable Variables)

Before executing the coverage workflow, you need to prepare the following **parameterizable** variables:

- **`{project}`**: The OSS-Fuzz project name (e.g., `jansson`, `libpng`, `curl`, `zlib`)
- **`{fuzz_target}`**: The fuzz target binary name for the project (e.g., `json_load_dump_fuzzer`, `png_read_fuzzer`)
- **`{input_file}`**: The absolute path to the **binary input file** you want to validate (the core scenario for this skill)
- **`{corpus_dir}`**: A temporary directory path for storing the single input file as a corpus (e.g., `/tmp/corpus_single_input_cpp`)
- **`{output_json}`**: The absolute path where the final JSON coverage report will be saved (e.g., `/tmp/cpp_coverage_output.json`)

> **Important**: Replace all `{variable}` placeholders with your actual values when executing the commands.


## How to Generate Coverage Report

### Step 1: Prepare Single Input Corpus

Create a temporary corpus directory and copy your target input file into it. The OSS-Fuzz coverage tool expects a corpus directory, so we create one containing only the single input file.

**Execution Command:**

```bash
INPUT_FILE={input_file}
CORPUS_DIR={corpus_dir}
mkdir -p "$CORPUS_DIR"
cp "$INPUT_FILE" "$CORPUS_DIR/seed.bin"
```

**Parameter Explanation:**

- `INPUT_FILE={input_file}`: Your binary input file to validate
- `CORPUS_DIR={corpus_dir}`: Temporary directory to hold the corpus
- The input is copied as `seed.bin` (name can be arbitrary)

> **Note**: Ensure the `{input_file}` path is correct and readable. The corpus directory should contain only this single file for isolated input validation.


### Step 2: Execute Coverage Collection

Run the OSS-Fuzz `helper.py coverage` command to execute the fuzz target with the prepared corpus and collect LLVM instrumentation-based coverage data.

**Execution Command:**

```bash
PROJECT={project}
FUZZ_TARGET={fuzz_target}
CORPUS_DIR={corpus_dir}

sg docker -c "cd ./oss-fuzz && \
python3 infra/helper.py coverage ${PROJECT} \
  --fuzz-target ${FUZZ_TARGET} \
  --corpus-dir ${CORPUS_DIR} \
  --no-serve --no-corpus-download --port 18080"
```

**Parameter Explanation:**

- `PROJECT={project}`: Your OSS-Fuzz project name
- `FUZZ_TARGET={fuzz_target}`: Your fuzz target binary name
- `--corpus-dir ${CORPUS_DIR}`: Points to the corpus directory created in Step 1
- `--no-serve`: Disables the HTTP server (we only need the coverage files)
- `--no-corpus-download`: Skips downloading the default corpus
- `--port 18080`: Specifies an available port (change if 18080 is occupied)

**What This Does:**
- Executes the fuzz target binary with the input file
- Collects LLVM profiling data during execution
- Generates merged profdata and HTML reports

> **Note**: This command requires Docker and may take a few seconds to minutes depending on the target complexity.


### Step 3: Verify Coverage Artifacts

Check that the LLVM coverage files have been generated successfully.

**Execution Command:**

```bash
PROJECT={project}
ls -l ./oss-fuzz/build/out/${PROJECT}/dumps/merged.profdata
ls -l ./oss-fuzz/build/out/${PROJECT}/report/linux/summary.json
ls -l ./oss-fuzz/build/out/${PROJECT}/textcov_reports/*.covreport
```

**Expected Output Locations:**

- **Merged Profile Data**: `./oss-fuzz/build/out/{project}/dumps/merged.profdata`
- **HTML Report**: `./oss-fuzz/build/out/{project}/report/linux/*.html`
- **Summary JSON**: `./oss-fuzz/build/out/{project}/report/linux/summary.json`
- **Text Coverage**: `./oss-fuzz/build/out/{project}/textcov_reports/*.covreport`

> **Note**: If `merged.profdata` does not exist, the coverage collection may have failed. Check Docker logs and ensure the fuzz target runs successfully with coverage instrumentation.


### Step 4: Export Coverage to JSON using llvm-cov

Use the LLVM `llvm-cov export` command within a Docker container to convert the profile data to JSON format.

**Execution Command:**

```bash
PROJECT={project}
FUZZ_TARGET={fuzz_target}
OUT_DIR=./oss-fuzz/build/out/${PROJECT}
OUT_JSON={output_json}

docker run --rm --privileged --shm-size=2g --platform linux/amd64 \
  -v "${OUT_DIR}:/out" \
  gcr.io/oss-fuzz-base/base-runner:latest \
  bash -lc "llvm-cov export /out/${FUZZ_TARGET} \
    -instr-profile=/out/dumps/merged.profdata > /out/dumps/coverage_full.json"

# Copy to your desired output location
cp "${OUT_DIR}/dumps/coverage_full.json" "${OUT_JSON}"
```

**Parameter Explanation:**

- `OUT_DIR`: The build output directory for the project
- `-v "${OUT_DIR}:/out"`: Mounts the build directory into the Docker container
- `llvm-cov export`: LLVM command to export coverage data
- `/out/${FUZZ_TARGET}`: The instrumented binary inside the container
- `-instr-profile=/out/dumps/merged.profdata`: The profile data to read
- `> /out/dumps/coverage_full.json`: Output JSON file

> **Important**: The current OSS-Fuzz environment's `llvm-cov export` outputs JSON format by default. Do NOT use the `-format=json` flag as it may not be supported in your LLVM version.

**Output JSON Format:**

The JSON output follows LLVM's standard coverage export format:

```json
{
  "data": [
    {
      "files": [
        {
          "filename": "/src/project/source.c",
          "segments": [
            [10, 15, 5, true, true],
            [20, 30, 0, false, false]
          ],
          "summary": {
            "lines": {
              "count": 150,
              "covered": 95,
              "percent": 63.33
            },
            "functions": {
              "count": 10,
              "covered": 8,
              "percent": 80.0
            }
          }
        }
      ]
    }
  ],
  "type": "llvm.coverage.json.export",
  "version": "2.0.1"
}
```

**Output JSON Format:**

The JSON output follows LLVM's standard coverage export format:

```json
{
  "data": [
    {
      "files": [
        {
          "filename": "/src/project/source.c",
          "segments": [
            [10, 15, 5, true, true, false],
            [20, 30, 0, true, true, false],
            [25,  1, 0, false, false, false]
          ],
          "summary": {
            "lines": {
              "count": 150,
              "covered": 95,
              "percent": 63.33
            },
            "functions": {
              "count": 10,
              "covered": 8,
              "percent": 80.0
            }
          }
        }
      ]
    }
  ],
  "type": "llvm.coverage.json.export",
  "version": "2.0.1"
}
```

**Format Explanation:**
- `data[].files[]`: Array of source files with coverage information
- `filename`: Absolute path to the source file
- `segments`: Coverage segments, each with 6 fields: `[line, col, count, hasCount, isRegionEntry, isGapRegion]`
- `summary.lines`: Line-level coverage statistics (count, covered, percent)
- `summary.functions`: Function-level coverage statistics

**Correct Segment Parsing Algorithm:**

Each segment describes the start of a coverage region. Its `count` stays active until the next `isRegionEntry=True` segment. To determine whether a line `L` was executed:

1. Collect all segments on line `L` where `hasCount=True`, `isRegionEntry=True`, and `isGapRegion=False`
2. Take the **maximum** count among them as the representative count for line `L`
3. If no such segment exists on line `L`, inherit the `active_count` from the previous region entry
4. Line `L` is **executed** if its representative count > 0

> **Warning**: Do NOT simply mark every line in the range `[segment_start_line, next_segment_start_line]` as executed when `count > 0`. This is incorrect because multiple segments can appear on the same line representing different branches (e.g., an `if` condition and its taken/not-taken branches). Only `isRegionEntry=True` segments define the actual execution count for a line.

Example reference implementation:

```python
from collections import defaultdict

def segments_to_executed_lines(segments):
    executed = set()
    if not segments:
        return executed

    sorted_segs = sorted(segments, key=lambda s: (s[0], s[1]))

    # Collect region-entry counts per line
    line_entry_counts = defaultdict(list)
    for seg in sorted_segs:
        line, count, has_count = seg[0], seg[2], seg[3]
        is_entry = seg[4] if len(seg) > 4 else False
        is_gap   = seg[5] if len(seg) > 5 else False
        if has_count and is_entry and not is_gap:
            line_entry_counts[line].append(count)

    # Sweep lines, propagating active_count
    active_count = 0
    for ln in range(sorted_segs[0][0], sorted_segs[-1][0] + 1):
        if ln in line_entry_counts:
            active_count = max(line_entry_counts[ln])
        if active_count > 0:
            executed.add(ln)

    return executed
```

> **Result Verification**: The generated JSON file contains comprehensive line and function coverage data that can be parsed to verify if specific target lines were covered by the directed binary input.


### Step 5: Cleanup Temporary Files

After generating the JSON report and confirming the data is correct, clean up the temporary corpus directory.

**Execution Command:**

```bash
CORPUS_DIR={corpus_dir}
rm -rf ${CORPUS_DIR}
```

**Recommended Cleanup** (strongly advised to run before the next coverage collection):
```bash
PROJECT={project}
# The dumps/ directory is written by Docker (root-owned), so delete via container
sg docker -c "docker run --rm --privileged \
  -v ./oss-fuzz/build/out/${PROJECT}:/out \
  gcr.io/oss-fuzz-base/base-runner:latest \
  bash -c 'rm -rf /out/dumps && find /out -maxdepth 1 -name \"*.profraw\" -delete'"
rm -rf ./oss-fuzz/build/out/${PROJECT}/report
rm -rf ./oss-fuzz/build/out/${PROJECT}/textcov_reports
```

> **Warning**: The `dumps/` directory accumulates profdata across multiple runs. If not cleaned before each new coverage collection, `merged.profdata` will contain data from **all previous inputs**, not just the current one. This causes false positives where lines covered by earlier runs appear as covered even when the current input does not reach them. Always clean `dumps/` before running a new single-input validation.


## Complete Example Workflow

Here's a complete example for the `jansson` project with the `json_load_dump_fuzzer` target:

```bash
# Define parameters
INPUT_FILE=/path/to/my_test_input.bin
CORPUS_DIR=/tmp/corpus_jansson_validation
PROJECT=jansson
FUZZ_TARGET=json_load_dump_fuzzer
OUTPUT_JSON=/tmp/jansson_coverage_report.json

# Step 1: Prepare corpus
mkdir -p "$CORPUS_DIR"
cp "$INPUT_FILE" "$CORPUS_DIR/seed.bin"

# Step 1.5: Clean up previous coverage data (REQUIRED for single-input isolation)
sg docker -c "docker run --rm --privileged \
  -v ${OUT_DIR}:/out \
  gcr.io/oss-fuzz-base/base-runner:latest \
  bash -c 'rm -rf /out/dumps && find /out -maxdepth 1 -name \"*.profraw\" -delete'"

# Step 2: Execute coverage
sg docker -c "cd ./oss-fuzz && \
python3 infra/helper.py coverage ${PROJECT} \
  --fuzz-target ${FUZZ_TARGET} \
  --corpus-dir ${CORPUS_DIR} \
  --no-serve --no-corpus-download --port 18080"

# Step 3: Verify artifacts
ls -l ./oss-fuzz/build/out/${PROJECT}/dumps/merged.profdata

# Step 4: Export to JSON
OUT_DIR=./oss-fuzz/build/out/${PROJECT}
docker run --rm --privileged --shm-size=2g --platform linux/amd64 \
  -v "${OUT_DIR}:/out" \
  gcr.io/oss-fuzz-base/base-runner:latest \
  bash -lc "llvm-cov export /out/${FUZZ_TARGET} \
    -instr-profile=/out/dumps/merged.profdata > /out/dumps/coverage_full.json"

cp "${OUT_DIR}/dumps/coverage_full.json" "${OUTPUT_JSON}"

# Step 5: Cleanup
rm -rf ${CORPUS_DIR}

echo "Coverage report available at: ${OUTPUT_JSON}"
```


## Optional: Generate LCOV Format

If you need LCOV format instead of JSON (e.g., for integration with other tools), you can use:

**Execution Command:**

```bash
PROJECT={project}
FUZZ_TARGET={fuzz_target}
OUT_DIR=./oss-fuzz/build/out/${PROJECT}
OUT_LCOV=/tmp/coverage_output.lcov

docker run --rm --privileged --shm-size=2g --platform linux/amd64 \
  -v "${OUT_DIR}:/out" \
  gcr.io/oss-fuzz-base/base-runner:latest \
  bash -lc "llvm-cov export -format=lcov /out/${FUZZ_TARGET} \
    -instr-profile=/out/dumps/merged.profdata > /out/dumps/coverage_full.lcov"

cp "${OUT_DIR}/dumps/coverage_full.lcov" "${OUT_LCOV}"
```

> **Note**: LCOV format is widely supported by coverage visualization tools but contains less detailed information than the JSON export.


## Optional: Access Text Coverage Reports

OSS-Fuzz also generates human-readable text coverage reports:

```bash
PROJECT={project}
ls ./oss-fuzz/build/out/${PROJECT}/textcov_reports/*.covreport
cat ./oss-fuzz/build/out/${PROJECT}/textcov_reports/*.covreport | head -100
```

These `.covreport` files provide line-by-line coverage in a text format, useful for quick manual inspection.


## Important Notes

1. **Docker Requirement**: This workflow requires Docker access and the OSS-Fuzz environment. Ensure you have proper permissions to run `sg docker -c` commands.

2. **Port Availability**: The default port is 18080. If you encounter "port already allocated" errors, change `--port 18080` to another available port (e.g., `--port 18081`).

3. **OSS-Fuzz Path**: The skill assumes OSS-Fuzz is installed at `./oss-fuzz`. If your installation is elsewhere, you need to adjust the path accordingly.

4. **LLVM Version**: The `llvm-cov export` command format may vary slightly between LLVM versions. The current environment uses LLVM's default JSON export without the `-format=json` flag.

5. **Single Input Validation**: This workflow is designed for validating a **single binary input**. The corpus directory should contain only one file for accurate isolated coverage measurement.

6. **Target Line Hit Verification**: The JSON output format contains detailed segment and line coverage data. Each segment has 6 fields: `[line, col, count, hasCount, isRegionEntry, isGapRegion]`. To correctly determine if a line was executed, use the algorithm described in Step 4 — take the maximum count among all `isRegionEntry=True`, non-gap segments on that line, propagating the active count across lines with no region entry. Do NOT naively mark entire line ranges as executed based on a segment's count; this produces incorrect results for branch-heavy code.

7. **Historical Data Accumulation**: The `dumps/` directory is **not** automatically cleared between runs. OSS-Fuzz merges new profdata with existing data, so if `dumps/` contains data from previous runs, the coverage report will reflect the union of all inputs ever run — not just the current input. Always delete `dumps/` (via Docker, since it is root-owned) before each single-input validation.

7. **Fuzz Target Names**: Ensure the `{fuzz_target}` name exactly matches the binary target defined in the project's OSS-Fuzz configuration. Check the project's `build.sh` for the correct binary name.

8. **Coverage Instrumentation**: The fuzz target must be built with coverage instrumentation (`-fprofile-instr-generate -fcoverage-mapping` flags). OSS-Fuzz's coverage mode handles this automatically.

9. **Coverage Scope**: This measures line and function coverage for the specific input, not the entire project's test coverage. Different inputs will produce different coverage reports.

10. **Performance**: The Docker-based `llvm-cov export` step may take some time for large binaries. Be patient and monitor Docker logs if needed.

11. **Binary Location**: The fuzz target binary must be accessible inside the Docker container at `/out/${FUZZ_TARGET}`. The `-v` mount ensures this is correctly set up.
