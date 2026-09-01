# Python Fault Injection Examples

This document provides concrete, project-agnostic examples for each of the six fault injection
categories identified through analysis of real-world Python projects. Each example demonstrates
the injection pattern, the target control-flow path, and expected behavior after injection.

---

## Category 1: Loop Guard Injection

**Pattern**: A loop uses a decremented counter to cap maximum iterations. The `break` statement
at the guard is a target line that is never reached under normal inputs (counter never exhausts).

**Injection strategy**: Force the counter to `1` (or the minimum value that triggers the guard)
immediately before the loop begins so that the `break` is reached on the first iteration.

### Original code

```python
MAX_RETRIES = 100
attempts = MAX_RETRIES

for item in data_stream:
    attempts -= 1
    if attempts <= 0:
        break          # target line — never reached with normal inputs

    result = process(item)
    if result.is_valid():
        return result
```

### Injected code

```python
MAX_RETRIES = 100
attempts = 1  # Fault Injection: force loop-guard break on first iteration

for item in data_stream:
    attempts -= 1
    if attempts <= 0:
        break          # target line — now guaranteed to execute

    result = process(item)
    if result.is_valid():
        return result
```

**Notes**:
- The original line is not a `raise`; the injection modifies a preceding assignment.
- No `try/except` is involved; this covers a branch that is reachable only under resource
  exhaustion or adversarial input conditions.
- After injection the loop exits early; verify that downstream code handles the case where no
  valid result was produced (e.g., a subsequent `if result is None: raise SomeError`).

---

## Category 2: Silent `except … pass` Branch Injection

**Pattern**: A `try` block wraps an optional parsing or decoding operation. The `except` clause
uses `pass`, meaning failure is acceptable and execution continues with the raw/unprocessed data.
The `except` line itself is a target that is skipped when the operation always succeeds.

**Injection strategy**: Insert `raise <MatchingException>(...)` as the first statement inside the
`try` block so the handler is guaranteed to execute.

### Original code

```python
try:
    data = decode_optional_encoding(raw_bytes)   # rarely fails in practice
except ValueError:
    pass                   # target line — skipped when decode always succeeds

process(data)
```

### Injected code

```python
try:
    raise ValueError("Fault Injection: simulated decode failure")  # injected
    data = decode_optional_encoding(raw_bytes)
except ValueError:
    pass                   # target line — now guaranteed to execute

process(data)
```

**Notes**:
- The exception type in the `raise` must exactly match (or be a subclass of) the type named in
  `except`. Raising the base `Exception` will **not** be caught by `except ValueError`.
- After injection `data` remains in its pre-`try` state (undefined or its prior value). Confirm
  the surrounding code handles this correctly.
- This pattern commonly appears around optional decoders, format auto-detection, and VBR header
  parsers in binary format libraries.

---

## Category 3: `IOError` / `OSError` with `errno` Discrimination

**Pattern**: A `seek` or `read` call is wrapped in `try/except IOError`. The handler inspects
`e.errno` to distinguish "file too small" (`EINVAL`) — a recoverable condition — from all other
I/O errors which are re-raised. The `if e.errno == errno.EINVAL:` line is a target that requires
a very specific error to be simulated.

**Injection strategy**: Replace the risky `seek`/`read` call with a `raise IOError(errno.EINVAL, …)`
carrying the precise errno value so the discriminating branch is entered.

### Original code

```python
import errno

old_pos = fileobj.tell()
try:
    fileobj.seek(-TAIL_SIZE, 2)      # fails when file is shorter than TAIL_SIZE
except IOError as e:
    if e.errno == errno.EINVAL:      # target line — file-too-small recovery path
        fileobj.seek(0, 0)           # fall back to beginning of file
    else:
        raise                        # genuine I/O error — propagate

data = fileobj.read(TAIL_SIZE)
fileobj.seek(old_pos, 0)
```

### Injected code

```python
import errno

old_pos = fileobj.tell()
try:
    raise IOError(errno.EINVAL, "Fault Injection: file too small for tail seek")  # injected
    fileobj.seek(-TAIL_SIZE, 2)
except IOError as e:
    if e.errno == errno.EINVAL:      # target line — now guaranteed to execute
        fileobj.seek(0, 0)
    else:
        raise

data = fileobj.read(TAIL_SIZE)
fileobj.seek(old_pos, 0)
```

**Notes**:
- `IOError` and `OSError` are the same class in Python 3; either name works.
- The two-argument form `IOError(errno_code, message)` sets `e.errno` correctly. Using the
  single-argument form `IOError("message")` leaves `e.errno` as `None` and the injection will
  **not** enter the target branch.
- To cover the *re-raise* branch instead, inject `IOError(errno.EIO, …)` (any errno ≠ EINVAL).

---

## Category 4: Explicit `raise` on Format / Header Validation

**Pattern**: After reading a fixed-size header or magic bytes from a binary stream, the code
performs one or more sanity checks and raises a domain-specific error if any check fails. The
`raise` itself is the target line, reachable only when the data is malformed.

**Injection strategy**: Force the pre-condition of the `if` guard to be true by overwriting the
validated field with an invalid value immediately after it is parsed.

### Original code

```python
EXPECTED_MAGIC = b"\x89PNG\r\n\x1a\n"
HEADER_SIZE = 8

data = fileobj.read(HEADER_SIZE)
if len(data) != HEADER_SIZE:
    raise FormatError("File too short to contain header")

magic = data[:8]
if magic != EXPECTED_MAGIC:
    raise FormatError("Invalid magic bytes: not a PNG file")  # target line A

chunk_length = struct.unpack(">I", data[0:4])[0]
if chunk_length > MAX_CHUNK_SIZE:
    raise FormatError("Chunk size exceeds maximum allowed value")  # target line B
```

### Injected code (covering target line A)

```python
EXPECTED_MAGIC = b"\x89PNG\r\n\x1a\n"
HEADER_SIZE = 8

data = fileobj.read(HEADER_SIZE)
if len(data) != HEADER_SIZE:
    raise FormatError("File too short to contain header")

magic = b"\x00\x00\x00\x00\x00\x00\x00\x00"  # Fault Injection: force magic mismatch
if magic != EXPECTED_MAGIC:
    raise FormatError("Invalid magic bytes: not a PNG file")  # target line A — now reached
```

### Injected code (covering target line B)

```python
chunk_length = struct.unpack(">I", data[0:4])[0]
chunk_length = MAX_CHUNK_SIZE + 1  # Fault Injection: force oversized chunk
if chunk_length > MAX_CHUNK_SIZE:
    raise FormatError("Chunk size exceeds maximum allowed value")  # target line B — now reached
```

**Notes**:
- Overwrite the *parsed* variable rather than the raw bytes; this avoids changes to the `read`
  call and keeps the injection minimal and reversible.
- Each conditional `raise` in the same function is a separate target and requires a separate
  injection.
- This pattern is ubiquitous in binary format parsers (audio, image, archive, network protocol).

---

## Category 5: Graceful Degradation via `except` with Side Effects (`_failed_atoms` / Fallback Storage)

**Pattern**: Inside a loop that processes a collection of items (e.g., metadata atoms, record
chunks, plugin handlers), each item is parsed inside a `try` block. On failure the `except` clause
stores the raw data in a fallback container (e.g., `self._failed_items`) rather than propagating
the error. The target line is inside the `except` body — a non-trivial handler that is skipped
when all items parse successfully.

**Injection strategy**: Insert `raise <DomainError>(…)` as the first statement in the `try` block
body (after any setup that must succeed) so the `except` path is taken for at least one iteration.

### Original code

```python
self._failed_items = {}   # initialized in __init__

for item in collection:
    ok, raw_data = item.read(fileobj)
    if not ok:
        raise ContainerError("Incomplete read for item")

    try:
        if item.name in self._known_handlers:
            self._known_handlers[item.name](self, item, raw_data)
        else:
            self._parse_generic(item, raw_data)   # target line — skipped when all parses succeed
    except ContainerError:
        # graceful degradation: preserve raw data for round-trip write
        self._failed_items.setdefault(item.name, []).append(raw_data)  # target line
```

### Injected code

```python
self._failed_items = {}

for item in collection:
    ok, raw_data = item.read(fileobj)
    if not ok:
        raise ContainerError("Incomplete read for item")

    try:
        raise ContainerError("Fault Injection: simulated parse failure for item")  # injected
        if item.name in self._known_handlers:
            self._known_handlers[item.name](self, item, raw_data)
        else:
            self._parse_generic(item, raw_data)
    except ContainerError:
        # target lines — now guaranteed to execute for every item
        self._failed_items.setdefault(item.name, []).append(raw_data)
```

**Notes**:
- The injected `raise` must use the exact exception type caught by the `except` clause; base-class
  exceptions will be caught but unrelated subclasses will not (unless the handler uses a broad
  base class like `Exception`).
- Verify post-injection that `self._failed_items` is non-empty and that a subsequent save/write
  operation correctly re-emits the preserved raw data.
- This pattern appears in metadata libraries, plugin loaders, configuration parsers, and any
  system that must tolerate partially corrupt input.

---

## Category 6: Incomplete-Read Guard (`if not ok: raise`)

**Pattern**: After a `read()` call the code checks whether the returned buffer has the expected
size (or a boolean `ok` flag). If the check fails an explicit `raise` is executed. This line is
a target that is unreachable with well-formed input files.

**Injection strategy**: Override the `ok` flag (or the length check variable) to `False` / an
incorrect value immediately after the `read()` call, before the conditional is evaluated.

### Original code

```python
for record in container.records:
    ok, data = record.read(fileobj)
    if not ok:
        raise ContainerError("Not enough data")   # target line — skipped with valid files

    self._process_record(record, data)
```

### Injected code

```python
for record in container.records:
    ok, data = record.read(fileobj)
    ok = False  # Fault Injection: force incomplete-read condition
    if not ok:
        raise ContainerError("Not enough data")   # target line — now guaranteed to execute

    self._process_record(record, data)
```

**Alternative** (when no `ok` flag is returned, only a raw buffer):

```python
data = fileobj.read(RECORD_SIZE)
data = b""  # Fault Injection: simulate truncated read
if len(data) != RECORD_SIZE:
    raise ContainerError("Record truncated")   # target line — now guaranteed to execute
```

**Notes**:
- Overriding `ok` or the buffer variable is preferred over patching `fileobj.read` because it is
  more surgical and does not affect unrelated reads elsewhere in the same method.
- Be aware that subsequent code that uses `data` will now receive the real (not empty) data unless
  `data` is also overridden; choose the minimal injection that only triggers the target `raise`.
- This pattern appears wherever streaming parsers read variable-length records, binary chunks, or
  network packets from a file-like object.
