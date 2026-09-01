---
name: python-directed-input-verification-skill
description: Executes tests with specific binary input files to generate standardized JSON code coverage reports for validating directed inputs in Python projects.
---

# Python-Directed-Input-Verification-SKILL

This skill is designed specifically for **validating directed binary inputs** in integration testing scenarios. It automates the collection of code coverage and the generation of structured reports for Python projects. Leveraging the `coverage.py` tool, it monitors source code execution while running designated test scripts with provided binary input arguments, ultimately producing a machine-readable JSON report suitable for verifying if specific target lines were hit.

## When to Use This Skill

- Directed Input Generation: Call this skill when generating directed test inputs for a specific Python project to verify if the generated payload successfully triggers target code paths.

- Input Validation: Use this skill when you need to verify the effectiveness of a generated binary input for a Python program by analyzing the resulting code coverage.

- Coverage Reporting: Use this skill when coverage data needs to be converted into a structured JSON format to confirm whether specific target lines (e.g., in fuzzing or directed testing scenarios) were executed.


## How to Generate Coverage Report

The `coverage` library has already been installed; you do not need to install it again. Please prepare the following key path variables:

- `{repo_path}`: The root directory path of the source code to be tested.
- `{test_script_path}`: The full path to the test script.
- `{input_file}`: The path to the **binary input file** required by the test script (the core scenario for this skill).
- `{coverage_saved_path}`: The save path for the temporary coverage data file (e.g., `.coverage`).
- `{json_coverage_saved_path}`: The save path for the final generated JSON report.

### Step 1: Execute Tests with Inputs and Collect Coverage Data

Wrap your test execution command with `coverage run`. This step initiates a monitoring process that specifically records which lines of code in `{repo_path}` are hit when the test script is executed with the specified `{input_file}`.

**Execution Command:**

```bash
python -m coverage run --source={repo_path} --data-file={coverage_saved_path} {test_script_path} {input_file}
```

**Parameter Explanation:**

- `--source={repo_path}`: Limits the statistics scope to only the specified source code directory.
- `--data-file={coverage_saved_path}`: Specifies the storage path for the raw binary coverage data to prevent conflicts with default files.
- `{test_script_path} {input_file}`: **Critical Step**. Passes the test script path and the specific binary input file path as arguments. `coverage` takes control of the interpreter to execute this command, ensuring the input file is loaded correctly and the entire execution process is monitored.

> **Note**: Ensure that the `{input_file}` path is correct and readable. If the test script fails to find the input file, the execution will fail, resulting in empty or incomplete coverage data.

### Step 2: Convert Coverage Data to JSON Report

Once the test execution is successful, use the `coverage json` command to convert the binary data file generated in Step 1 into the standard JSON format, fulfilling the "Report Generation" requirement.

**Execution Command:**

```bash
python -m coverage json --data-file={coverage_saved_path} -o {json_coverage_saved_path}
```

**Parameter Explanation:**

- `--data-file={coverage_saved_path}`: Points to the raw data file generated in Step 1, which contains the results of the test with the specific input.
- `-o {json_coverage_saved_path}`: Specifies the output path for the JSON report file.

**Result Verification:** The generated JSON file will contain detailed file coverage information (hit lines, missing lines, etc.). It can be directly parsed to verify if specific target lines were covered by the directed binary input.

### Step 3: Clean Up Temporary Files

After generating the JSON report and confirming the data is correct, it is recommended to delete the temporary `.coverage` data file to keep the environment clean.

```bash
rm {coverage_saved_path}
```
