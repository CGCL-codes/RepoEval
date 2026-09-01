# Third-Party Notices

This project distributes unmodified third-party source trees under
`python_packages/` so that the Python benchmark targets can run from a pinned,
self-contained environment. These components are the intellectual property of
their respective copyright holders and are redistributed under their **own**
licenses (they are not covered by the Apache-2.0 license that applies to the
artifact code in this repository). Their license texts are retained in the
corresponding project distributions.

## Vendored Python packages (`python_packages/`)

| Component | Copyright / Author | License | Project |
| --- | --- | --- | --- |
| `scapy` | Philippe Biondi and Scapy contributors | GPL-2.0-only | https://scapy.net/ |
| `sqlparse` | Andi Albrecht and sqlparse contributors | BSD-3-Clause | https://github.com/andialbrecht/sqlparse |
| `mutagen` | Joe Wreschnig and mutagen contributors | GPL-2.0-or-later | https://mutagen.readthedocs.io/ |
| `pycparser` | Eli Bendersky | BSD-3-Clause | https://github.com/eliben/pycparser |

> Note: `scapy` and `mutagen` are licensed under the GNU GPL. Redistribution of
> this artifact does not change the licensing terms of those components; they
> remain governed by the GPL.

## Runtime infrastructure referenced (not vendored)

| Component | License | Purpose |
| --- | --- | --- |
| OSS-Fuzz (`infra/helper.py`, base-runner images) | Apache-2.0 | Builds and runs the Java/C++ coverage builds used by the example pipeline |
| Jazzer (via OSS-Fuzz Java base image) | Apache-2.0 | Java fuzz driver runtime used by `AsyncHttpClientFuzzer`, `JedisURIFuzzer`, `HtmlFuzzer`, `ImageMetadataReaderFuzzer` |

The Java/C++ driver sources and build scripts under `tools/` and in the OSS-Fuzz
project layouts follow OSS-Fuzz conventions (Apache-2.0).

## Dependency notice

Python runtime dependencies declared in `requirements.txt` (`openai`, `coverage`,
and the pinned package versions) are fetched from PyPI at install time and are
subject to their own licenses.
