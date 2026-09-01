---
name: java-directed-input-verification-skill
description: Executes tests with specific binary input files to generate standardized JSON code coverage reports for validating directed inputs in Java projects using JaCoCo.
---

# Java-Directed-Input-Verification-skill

This skill is designed specifically for **validating directed binary inputs** in integration testing scenarios for Java projects. It automates the collection of code coverage using JaCoCo and generates structured JSON reports. The skill leverages the OSS-Fuzz infrastructure with the `helper.py coverage` command to execute fuzz targets with provided binary input files, ultimately producing a machine-readable JSON report suitable for verifying if specific target lines were hit.

## When to Use This Skill

- Directed Input Generation: Call this skill when generating directed test inputs for a specific Java project to verify if the generated payload successfully triggers target code paths.

- Input Validation: Use this skill when you need to verify the effectiveness of a generated binary input for a Java program by analyzing the resulting code coverage.

- Coverage Reporting: Use this skill when coverage data needs to be converted into a structured JSON format to confirm whether specific target lines (e.g., in fuzzing or directed testing scenarios) were executed.


## Prerequisites

- OSS-Fuzz environment must be set up at `.//oss-fuzz`
- Docker access with `sg docker -c` command capability
- The Java project must be configured in the OSS-Fuzz structure
- Python 3 with xml.etree.ElementTree library (available by default)


## Key Parameters (Customizable Variables)

Before executing the coverage workflow, you need to prepare the following **parameterizable** variables:

- **`{project}`**: The OSS-Fuzz project name (e.g., `jsoup`, `gson`, `jackson-databind`)
- **`{fuzz_target}`**: The fuzz target name for the project (e.g., `HtmlFuzzer`, `JsonParserFuzzer`)
- **`{input_file}`**: The absolute path to the **binary input file** you want to validate (the core scenario for this skill)
- **`{corpus_dir}`**: A temporary directory path for storing the single input file as a corpus (e.g., `/tmp/corpus_single_input_java`)
- **`{output_json}`**: The absolute path where the final JSON coverage report will be saved (e.g., `/tmp/java_coverage_output.json`)

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

Run the OSS-Fuzz `helper.py coverage` command to execute the fuzz target with the prepared corpus and collect JaCoCo coverage data.

**Execution Command:**

```bash
PROJECT={project}
FUZZ_TARGET={fuzz_target}
CORPUS_DIR={corpus_dir}

sg docker -c "cd .//oss-fuzz && \
python3 infra/helper.py coverage ${PROJECT} \
  --fuzz-target ${FUZZ_TARGET} \
  --corpus-dir ${CORPUS_DIR} \
  --no-serve --no-corpus-download --port 18080"
```

**Parameter Explanation:**

- `PROJECT={project}`: Your OSS-Fuzz project name
- `FUZZ_TARGET={fuzz_target}`: Your fuzz target binary/class name
- `--corpus-dir ${CORPUS_DIR}`: Points to the corpus directory created in Step 1
- `--no-serve`: Disables the HTTP server (we only need the coverage files)
- `--no-corpus-download`: Skips downloading the default corpus
- `--port 18080`: Specifies an available port (change if 18080 is occupied)

**What This Does:**
- Executes the fuzz target with the input file
- Collects JaCoCo coverage data during execution
- Generates coverage reports in multiple formats

> **Note**: This command requires Docker and may take a few seconds to minutes depending on the target complexity.


### Step 3: Verify Coverage Artifacts

Check that the JaCoCo coverage files have been generated successfully.

**Execution Command:**

```bash
PROJECT={project}
ls -l .//oss-fuzz/build/out/${PROJECT}/report/linux/index.xml
ls -l .//oss-fuzz/build/out/${PROJECT}/report/linux/summary.json
ls -l .//oss-fuzz/build/out/${PROJECT}/dumps/jacoco.merged.exec
```

**Expected Output Locations:**

- **JaCoCo XML**: `.//oss-fuzz/build/out/{project}/report/linux/index.xml`
- **HTML Report**: `.//oss-fuzz/build/out/{project}/report/linux/*.html`
- **Summary JSON**: `.//oss-fuzz/build/out/{project}/report/linux/summary.json`
- **JaCoCo Exec**: `.//oss-fuzz/build/out/{project}/dumps/jacoco.merged.exec`

> **Note**: If `index.xml` does not exist, the coverage collection may have failed. Check Docker logs and ensure the fuzz target runs successfully.


### Step 4: Convert JaCoCo XML to Line-Level JSON

Parse the JaCoCo XML report and convert it to a structured JSON format containing line-level coverage information.

**Execution Command:**

```bash
PROJECT={project}
XML=.//oss-fuzz/build/out/${PROJECT}/report/linux/index.xml
OUT_JSON={output_json}
export XML OUT_JSON

python3 - <<'PY'
import json, xml.etree.ElementTree as ET, os

xml_path = os.environ["XML"]
out_json = os.environ["OUT_JSON"]

tree = ET.parse(xml_path)
root = tree.getroot()
cov = {}

for pkg in root.findall(".//package"):
    pkg_name = pkg.get("name", "").replace(".", "/")
    for src in pkg.findall("sourcefile"):
        key = f"{pkg_name}/{src.get('name','')}"
        lines = {}
        for line in src.findall("line"):
            nr = int(line.get("nr", "0"))
            ci = int(line.get("ci", "0"))
            lines[nr] = {"ci": ci, "hit": ci > 0}
        cov[key] = lines

with open(out_json, "w") as f:
    json.dump(cov, f, ensure_ascii=False, indent=2)

print(f"Coverage JSON saved to: {out_json}")
PY
```

**Parameter Explanation:**

- `XML`: Path to the JaCoCo XML report
- `OUT_JSON={output_json}`: Your desired output JSON path
- The Python script parses XML and extracts line-level coverage

**Output JSON Format:**

```json
{
  "org/jsoup/parser/Parser.java": {
    "1": {"ci": 5, "hit": true},
    "2": {"ci": 0, "hit": false},
    "3": {"ci": 12, "hit": true}
  },
  "org/jsoup/nodes/Element.java": {
    "10": {"ci": 3, "hit": true},
    "11": {"ci": 0, "hit": false}
  }
}
```

**Format Explanation:**
- Keys: Source file paths (package path + filename)
- Values: Dictionary of line numbers
- `ci`: Coverage instruction count (number of times executed)
- `hit`: Boolean indicating whether the line was executed

> **Result Verification**: The generated JSON file can be directly parsed to verify if specific target lines were covered by the directed binary input.


### Step 5: Cleanup Temporary Files

After generating the JSON report and confirming the data is correct, clean up the temporary corpus directory.

**Execution Command:**

```bash
CORPUS_DIR={corpus_dir}
rm -rf ${CORPUS_DIR}
```

**Optional Cleanup** (if disk space is a concern):
```bash
PROJECT={project}
rm -rf .//oss-fuzz/build/out/${PROJECT}/report
rm -rf .//oss-fuzz/build/out/${PROJECT}/dumps
```

> **Warning**: Only remove the build outputs if you no longer need the HTML reports or raw JaCoCo exec files.


## Complete Example Workflow

Here's a complete example for the `jsoup` project with the `HtmlFuzzer` target:

```bash
# Define parameters
INPUT_FILE=/path/to/my_test_input.bin
CORPUS_DIR=/tmp/corpus_jsoup_validation
PROJECT=jsoup
FUZZ_TARGET=HtmlFuzzer
OUTPUT_JSON=/tmp/jsoup_coverage_report.json

# Step 1: Prepare corpus
mkdir -p "$CORPUS_DIR"
cp "$INPUT_FILE" "$CORPUS_DIR/seed.bin"

# Step 2: Execute coverage
sg docker -c "cd .//oss-fuzz && \
python3 infra/helper.py coverage ${PROJECT} \
  --fuzz-target ${FUZZ_TARGET} \
  --corpus-dir ${CORPUS_DIR} \
  --no-serve --no-corpus-download --port 18080"

# Step 3: Verify artifacts
ls -l .//oss-fuzz/build/out/${PROJECT}/report/linux/index.xml

# Step 4: Convert to JSON
XML=.//oss-fuzz/build/out/${PROJECT}/report/linux/index.xml
export XML OUTPUT_JSON
python3 - <<'PY'
import json, xml.etree.ElementTree as ET, os
xml_path = os.environ["XML"]
out_json = os.environ["OUTPUT_JSON"]
tree = ET.parse(xml_path)
root = tree.getroot()
cov = {}
for pkg in root.findall(".//package"):
    pkg_name = pkg.get("name", "").replace(".", "/")
    for src in pkg.findall("sourcefile"):
        key = f"{pkg_name}/{src.get('name','')}"
        lines = {}
        for line in src.findall("line"):
            nr = int(line.get("nr", "0"))
            ci = int(line.get("ci", "0"))
            lines[nr] = {"ci": ci, "hit": ci > 0}
        cov[key] = lines
with open(out_json, "w") as f:
    json.dump(cov, f, ensure_ascii=False, indent=2)
print(f"Coverage JSON saved to: {out_json}")
PY

# Step 5: Cleanup
rm -rf ${CORPUS_DIR}

echo "Coverage report available at: ${OUTPUT_JSON}"
```


## Important Notes

1. **Docker Requirement**: This workflow requires Docker access and the OSS-Fuzz environment. Ensure you have proper permissions to run `sg docker -c` commands.

2. **Port Availability**: The default port is 18080. If you encounter "port already allocated" errors, change `--port 18080` to another available port (e.g., `--port 18081`).

3. **OSS-Fuzz Path**: The skill assumes OSS-Fuzz is installed at `.//oss-fuzz`. If your installation is elsewhere, you need to adjust the path accordingly.

4. **Single Input Validation**: This workflow is designed for validating a **single binary input**. The corpus directory should contain only one file for accurate isolated coverage measurement.

5. **Target Line Hit Verification**: The JSON output format is optimized for verifying if specific target lines were hit. You can programmatically check `cov[filename][line_number]["hit"]` to validate coverage.

6. **Fuzz Target Names**: Ensure the `{fuzz_target}` name exactly matches the target defined in the project's OSS-Fuzz configuration. Check the project's `build.sh` or fuzzing documentation for the correct name.

7. **Coverage Scope**: This measures line coverage for the specific input, not the entire project's test coverage. Different inputs will produce different coverage reports.

8. **JaCoCo Limitations**: JaCoCo coverage is instruction-based. The `ci` (coverage instruction) count may not directly correspond to line execution counts in all cases, but `hit: true/false` reliably indicates whether a line was executed.
