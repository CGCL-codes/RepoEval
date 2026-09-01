---
name: cpp-fault-inject-skill
description: description: Performs source-level fault injection on C/C++ applications by instrumenting code to force specific exceptions or error conditions, thereby validating the robustness of error handling logic or covering unreachable error-handling branches.
---

# cpp-fault-inject-skill

In C/C++, error handling is typically implemented via return codes, errno, or custom error-handling functions. This technique involves instrumenting the source code with fault injection statements at strategic points—such as forcing specific return values or modifying errno—to simulate failures. This ensures the execution of error-handling paths that are rarely triggered under normal operating conditions.

## When to Use This Skill

Use this skill when:

- **Covering error-handling branches**: To force execution of error handling code that is never reached under normal inputs, such as specific `if` conditions or error-checking functions.
- **Validating exception propagation**: To verify that deep-layer errors are correctly caught and propagated up the call stack without being swallowed.
- **Improving negative-path coverage**: To test rare internal validation failures that are difficult or impossible to trigger via crafted external inputs.
- **Verifying graceful degradation**: To ensure fallback mechanisms (e.g., _failedItems lists, safe modes) activate correctly when primary operations fail.

## How to Use This Skill

### Step 1: Identify Target Lines

Analyze the source code to find lines that are never reached under normal inputs but are critical for error handling or graceful degradation. Common targets include:

- `if` conditions that check for error states (e.g., `if (result != SUCCESS) { ... }`).
- Functions that return error codes or set `errno` on failure.
- Custom error-handling functions that are called when an error condition is detected.

### Step 2: Insert Fault Injection Statements

Before inserting fault statements, please copy the source code to a separate file with the suffix `.bak` to preserve the original code. Then, insert `return <error_code>;` or `errno = <error_value>;` statements at the identified target lines to simulate the desired failure conditions.
Example:

```C/C++
// Before injection
int processData(const char* input) {
    // Normal processing logic
    return SUCCESS;
}

int main() {
    int result = processData("valid_input");
    if (result != SUCCESS) {
        // This block is never reached under normal inputs
        error_handling();
    }
    return 0;
}

// After injection
int processData(const char* input) {
    return ERROR_CODE; // Fault Injection: force error handling path execution
    return SUCCESS;
}

int main() {
    int result = processData("valid_input");
    if (result != SUCCESS) {
        // This block is now reached due to the injected error code
        error_handling();
    }
    return 0;
}
```

### Step 3: Re-Compile the Whole Project

After modifying the source code, re-compile the entire project to ensure that the injected faults are included in the build. This step is crucial for the changes to take effect and for the tests to execute against the modified code.

To help you build the project, you can refer to the provided build script. Notice: If you want to modify the build script, please make a copy of the original build script with the suffix `.bak` to preserve it.

### Step 4: Run Tests and Analyze Results

See `C++-Directed-Input-Verification-skill` for details.

Execute the test suite against the modified code and analyze the results to verify that the injected faults have triggered the expected error-handling paths. Specifically, check that:
- The targeted error-handling blocks are executed.
- The expected error codes or `errno` values are set correctly.
- Any fallback mechanisms are activated as intended.



