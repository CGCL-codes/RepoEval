---
name: python-directed-test-skill
description: "Generate targeted test inputs to reach specific code paths and hard-to-reach behaviors in Python code. Use when: (1) Targeting uncovered branches or specific execution paths, (2) Need coverage-guided test generation, (3) Want to leverage LLM understanding of code semantics for meaningful test inputs, (4) Testing boundary conditions and edge cases systematically. Provides program analysis, coverage-guided strategies, and fault injection for comprehensive test input creation."

---

# python-directed-test-skill

Generate test inputs that target specific code paths and hard-to-reach behaviors using program analysis, coverage feedback and fault injection for Python program.

## Overview

Directed test input generation combines multiple techniques to create test inputs that explore specific execution paths:

1. **Program Analysis**: Analyze the program context along a **given call chain** leading to a target location.
    The analysis extracts relevant semantic information, including: path constraints, dependencies and control-flow conditions along the path.
2. **Intention Summary**: Follow the call chain, summary the intentions for the functions and the constraints with natural language.
3. **Coverage Feedback**: Use execution feedback to **iteratively refine test inputs**.
4. **Fault Injection**: Use **fault injection strategies** to explore error-handling logic and exception-triggering behaviors.

## How to Use

### Step 1: Program Analysis

Given a **call chain** from an entry function to a **target line or target branch**, analyze the program context.

Tasks in this step:

1. Identify the sequence of functions along the call chain.
2. Extract relevant code context for each function.
3. Analyze control-flow conditions along the path.
4. Derive **path constraints** that must be satisfied to reach the target.

The result of this step is a **set of inferred input requirements** for reaching the target location.

### Step 2: Intention Summary

See `Constraint-Intention-Analysis-skill` for details.

Follow the call chain, summary the intentions for the functions and the constraints with natural language. This step provides insights into the purpose of each function and the role of constraints in guiding execution toward the target. The summaried intentions should be saved into repo_path/dig_summaries/ with the task id as suffix for future reference and use.

### Step 3: Test Input Generation

Given the **test script**, which takes a **binary file as input**, generate a Python script that constructs the required binary input file.

1. Ensure the generated binary data **matches the format expected by the test script**.
2. Ensure the generated binary data **satisfies the path constraints required to reach and cover the target line**.

### Step 4: Coverage-Guided Iterative Refinement

See `Python-Directed-Input-Verification-skill` for details.

Execute the generated test and collect the corresponding **coverage file**. The coverage results are then analyzed to understand the program’s execution behavior and determine whether the target location has been reached.

Specifically, this step includes:

1. Running the test script with the generated binary input.
2. Collecting the coverage report produced during execution.
3. Analyzing the coverage information to determine:
    - whether the **target line** has been covered,
    - which branches or conditions along the target path were executed,
    - where the execution **diverged from the intended path**.
4. Analyzing the uncovered conditions and constraints to identify which input requirements were not satisfied, this includes:
    - Summarizing the intentions for the uncovered conditions and constraints using `Constraint-Intention-Analysis-skill` to understand why the generated input did not satisfy them.
    - Saved the summaries into repo_path/dig_summaries/ with the task id as suffix for future reference and use.
5. Based on the analysis, **refining the generated test input** to better satisfy the path constraints and increase the likelihood of reaching the target line in subsequent executions.

The coverage analysis provides feedback that is used to **iteratively refine the generated inputs**, guiding subsequent test generation toward satisfying the remaining path constraints and eventually reaching the target location.

### Step 5: Fault Injection (Optional)

See `Python-Fault-Inject-skill` for details.

When the **target line is located within an exception-handling block**, normal inputs may not be sufficient to trigger the desired execution path. In such cases, fault injection techniques are applied to deliberately construct abnormal or unexpected inputs that can drive the program into error-handling logic.

Specifically, this step may include:

- Injecting faults into the program under test.
- Executing the test script with the inputs to trigger exception-handling behavior and attempt to reach the target line.

By intentionally injecting faults into the input, this step increases the likelihood of triggering the **exception-handling path** and reaching the target location.

This step helps explore **rare failure scenarios** that normal inputs may not trigger.

## Reference Skills

Python-Directed-Input-Verification-skill

Python-Fault-Inject-skill

Constraint-Intention-Analysis-skill