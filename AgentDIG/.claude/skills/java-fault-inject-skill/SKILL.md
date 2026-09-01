---
name: java-fault-inject-skill
description: Performs source-level fault injection on Java applications by instrumenting code with explicit exception-throwing statements. By forcing failure scenarios at critical execution points, it verifies the correctness of catch blocks, evaluates system resilience under stress, and identifies gaps in test coverage.
---

# Java-Fault-Inject-SKILL

This skill involves inserting `throw new <ExceptionType>(...)` statements (or minimal state overrides) at strategic points in Java source code to forcibly execute specific lines that are unreachable under normal inputs. It is primarily used to cover error-handling branches, validate exception propagation, and improve negative-path coverage.

## When to Use This Skill

Use this skill when:

- **Covering error-handling branches**: `catch` blocks, `if (!ok) throw` guards, and re-throw logic are never reached by well-formed inputs.
- **Validating exception propagation**: Annotations such as `@ConvertError(IOException.class)` must be verified to convert exceptions correctly.
- **Improving negative-path coverage**: Directed-input generation cannot easily craft binary files that trigger specific internal format-validation errors.
- **Verifying graceful degradation**: Fallback containers (e.g., `_failedItems`) must be shown to be populated when parsing fails.

## How to Use This Skill

### Step 1: Identify Target Lines

Analyze the source code to find lines that are never reached under normal inputs but are critical for error handling or graceful degradation. Common targets include:

- `catch` blocks that handle specific exceptions.
- `if (!ok) throw new SomeException(...)` guards.
- Re-throw statements that propagate exceptions up the call stack.

### Step 2: Insert Fault Injection Statements

Before inserting fault statements, please copy the source code to a separate file with the suffix `.java.bak` to preserve the original code. Then, insert `throw new <ExceptionType>(...)` statements at the identified target lines. Ensure that the injected exception type matches the expected exception for that code path.

Example:

```java// Before injection
public void processData(InputStream input) {
    try {
        // Normal processing logic
    } catch (IOException e) {
        // This block is never reached under normal inputs
    }
} 

// After injection
public void processData(InputStream input) {
    try {
        throw new IOException("Fault Injection: forced exception"); // Fault Injection: force catch block execution
        // Normal processing logic
    } catch (IOException e) { 
        // This block is now reached due to the injected exception
    } 
```

### Step 3: Re-Compile the Whole Project

After modifying the source code, re-compile the entire project to ensure that the injected faults are included in the build. This step is crucial for the changes to take effect and for the tests to execute against the modified code.

To help you build the project, you can refer to the provided build script. Notice: If you want to modify the build script, please make a copy of the original build script with the suffix `.bak` to preserve it.

Notice: Fault injection may introduce dead code or unused variables, causing the build to fail during static analysis. To bypass these checks and proceed with compilation, you can skip the relevant plugins by adding the following flags to your Maven command:

```bash
-Dpmd.skip=true -Dcheckstyle.skip=true -Dspotbugs.skip=true -DskipTests
```

### Step 4: Run Tests and Analyze Results

See `Java-Directed-Input-Verification-skill` for details.

Execute the test suite against the modified code and analyze the results to verify that the injected faults have triggered the expected error-handling paths. Specifically, check that:
- The targeted `catch` blocks are executed.
- The expected exceptions are thrown and propagated correctly.
- Any fallback mechanisms are activated as intended.

