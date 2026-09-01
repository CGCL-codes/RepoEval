---
name: python-fault-inject-skill
description: Injects faults into Python source code by inserting raise statements at specific locations to forcibly trigger exceptions, verifying exception handling logic, system resilience, and test coverage.
---

# Python-Fault-Inject-SKILL

This skill involves inserting `raise <ExceptionType>` statements (or minimal state overrides) at
strategic points in Python source code to forcibly execute specific lines that are unreachable
under normal inputs. It is primarily used to cover error-handling branches, format-validation
`raise` paths, and graceful-degradation logic.

## When to Use This Skill

Use this skill when:

- **Covering error-handling branches**: `except` clauses, `if not ok: raise` guards, and
  re-raise logic are never reached by well-formed inputs.
- **Validating exception propagation**: Decorators such as `@convert_error(IOError, DomainError)`
  must be verified to convert exceptions correctly.
- **Improving negative-path coverage**: Directed-input generation cannot easily craft binary
  files that trigger specific internal format-validation errors.
- **Verifying graceful degradation**: Fallback containers (e.g., `_failed_items`) must be shown
  to be populated when parsing fails.

## Fault Injection Categories

Six distinct patterns arise when analyzing real-world Python parsers and I/O libraries. See
`examples.md` in this skill directory for full annotated code examples for each category.

### Category 1 — Loop Guard Injection

**Trigger condition**: A counter-based `break` inside a `for`/`while` loop is the target line,
but the counter never exhausts under normal inputs.

**Injection**: Assign the counter to `1` (or the minimum value that triggers the guard)
immediately before the loop.

```python
# Before injection
attempts = MAX_RETRIES
for item in stream:
    attempts -= 1
    if attempts <= 0:
        break          # target line

# After injection
attempts = 1  # Fault Injection: force loop-guard break on first iteration
for item in stream:
    attempts -= 1
    if attempts <= 0:
        break          # target line — now reached
```

### Category 2 — Silent `except … pass` Branch Injection

**Trigger condition**: An optional operation is wrapped in `try/except SomeError: pass`. The
`except` line is a target that is skipped when the operation always succeeds.

**Injection**: Insert `raise <MatchingException>(...)` as the first statement inside the `try`
block. The exception type must exactly match the `except` clause.

```python
# After injection
try:
    raise ValueError("Fault Injection: simulated decode failure")  # injected
    data = decode_optional(raw_bytes)
except ValueError:
    pass   # target line — now reached
```

### Category 3 — `IOError`/`OSError` with `errno` Discrimination

**Trigger condition**: A `try/except IOError` handler inspects `e.errno` to distinguish a
recoverable "file too small" error (`errno.EINVAL`) from fatal I/O errors. The discriminating
`if e.errno == errno.EINVAL:` line is the target.

**Injection**: Replace the risky `seek`/`read` with `raise IOError(errno.EINVAL, "...")`. The
two-argument form is required to set `e.errno` correctly.

```python
import errno
try:
    raise IOError(errno.EINVAL, "Fault Injection: file too small for seek")  # injected
    fileobj.seek(-TAIL_SIZE, 2)
except IOError as e:
    if e.errno == errno.EINVAL:   # target line — now reached
        fileobj.seek(0, 0)
    else:
        raise
```

> To cover the re-raise branch instead, use any `errno` value other than `EINVAL`
> (e.g., `errno.EIO`).

### Category 4 — Explicit `raise` on Format / Header Validation

**Trigger condition**: After reading binary header bytes, one or more `if <check>: raise
FormatError(...)` guards validate the data. These `raise` lines are unreachable with valid files.

**Injection**: Overwrite the parsed variable with an invalid value immediately after it is
assigned, so the guard condition becomes true.

```python
# After injection
magic = data[:8]
magic = b"\x00" * 8  # Fault Injection: force magic-bytes mismatch
if magic != EXPECTED_MAGIC:
    raise FormatError("Invalid magic bytes")   # target line — now reached
```

For numeric-size guards:

```python
chunk_size = struct.unpack(">I", data[4:8])[0]
chunk_size = MAX_SIZE + 1  # Fault Injection: force oversized chunk
if chunk_size > MAX_SIZE:
    raise FormatError("Chunk too large")   # target line — now reached
```

### Category 5 — Graceful Degradation via `except` with Side Effects

**Trigger condition**: Inside a loop, each item is parsed in a `try` block. On failure the
`except` clause stores raw data in a fallback container (`_failed_items`, `unknown_chunks`, etc.)
instead of propagating the error. The `except` body is the target.

**Injection**: Insert `raise <DomainError>(...)` as the first statement in the `try` block body
so the fallback path executes for every (or the first) iteration.

```python
# After injection
for item in collection:
    try:
        raise ContainerError("Fault Injection: simulated parse failure")  # injected
        self._parse(item, raw_data)
    except ContainerError:
        self._failed_items[item.name] = raw_data   # target line — now reached
```

### Category 6 — Incomplete-Read Guard (`if not ok: raise`)

**Trigger condition**: After a `read()` call the code checks a boolean `ok` flag or the buffer
length. The `raise` on failure is the target line, never triggered by well-formed files.

**Injection**: Override the `ok` flag to `False` (or shorten the buffer) immediately after the
`read()` call, before the guard is evaluated.

```python
# After injection
ok, data = record.read(fileobj)
ok = False  # Fault Injection: force incomplete-read condition
if not ok:
    raise ContainerError("Not enough data")   # target line — now reached
```

For raw-buffer variants:

```python
data = fileobj.read(RECORD_SIZE)
data = b""  # Fault Injection: simulate truncated read
if len(data) != RECORD_SIZE:
    raise ContainerError("Record truncated")   # target line — now reached
```

---

## Full Workflow

### Step 0: Identify Injection Category

Inspect the target line and its surrounding context to determine which of the six categories
applies. Key signals:

| Signal at or near target line | Category |
|-------------------------------|----------|
| `if counter <= 0: break` | 1 — Loop Guard |
| `except SomeError: pass` | 2 — Silent Pass |
| `if e.errno == errno.EINVAL:` | 3 — errno Discrimination |
| `if <format_check>: raise FormatError(...)` | 4 — Format Validation |
| `except DomainError:` body writes to fallback container | 5 — Graceful Degradation |
| `if not ok: raise ...` or `if len(data) != N: raise ...` | 6 — Incomplete-Read Guard |

### Step 1: Exception Path Analysis

- **Static analysis**: Read the full function/method containing the target line. Identify all
  `try/except` blocks, decorators (`@convert_error`, `@contextmanager`), and re-raise patterns.
- **Exception matching**: Determine the exact exception type needed. Raising a base class when
  the handler catches a specific subclass will **not** trigger the target handler.
- **Injection point**: Select the line immediately before the risky operation or guard condition.

### Step 2: Back Up the Target File

```bash
cp path/to/target_module.py path/to/target_module.py.bak
```

Always back up before any modification. Store the backup with `.bak` extension in the same
directory so it is easy to restore.

### Step 3: Inject the Fault

Edit the file and insert the injection code at the selected point. Follow these rules:

1. **Match indentation exactly** — Python is whitespace-sensitive.
2. **Prefix the injected line** with `# Fault Injection:` and a short description.
3. **Do not delete the original line** — leave it in place (unreachable) for reference.
4. **Minimise scope** — inject as late as possible (just before the guard) to avoid
   side effects on unrelated code paths in the same function.

### Step 4: Verify Coverage

Run the test with coverage instrumentation and confirm the target line is marked as covered:

```bash
python -m coverage run --source=<repo_path> --data-file=<cov_data> <test_script> <input_file>
python -m coverage json --data-file=<cov_data> -o <cov_report.json>
```

Check that the target file/line appears in the JSON report with `executed_lines` containing the
target line number.

### Step 5: Restore the Original File

```bash
cp path/to/target_module.py.bak path/to/target_module.py
```

Always restore after verification. Never leave injected faults in production or shared
environments.

---

## Important Cautions

- **Exception type precision**: `raise Exception(...)` is not caught by `except ValueError:`.
  Always use the exact type (or a subclass) named in the `except` clause.
- **Two-argument `IOError`**: For Category 3, `IOError(errno_code, message)` is required.
  Single-argument `IOError("message")` sets `e.errno = None` and will miss the discriminating
  branch.
- **Decorator-wrapped methods**: Functions decorated with `@convert_error(IOError, DomainError)`
  convert `IOError` into `DomainError` before the caller sees it. The injection still works;
  just ensure the injected `raise IOError(...)` is inside the decorated function body.
- **Loop-guard injections are not `raise` statements**: Category 1 modifies an assignment, not
  inserts a `raise`. This is intentional — the target line is a `break`, not an exception handler.
- **One injection per target**: Run a separate coverage verification cycle for each target line.
  Combining multiple injections in one run risks masking interactions between them.

---

## Reference: Examples

See `examples.md` in this skill directory for complete, annotated before/after code examples
for all six categories.
