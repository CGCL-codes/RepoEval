#!/usr/bin/env python3
"""
Direct test script for mutagen coverage collection.
"""

import io
import sys

import mutagen


def test_one_input(data: bytes) -> int:
    try:
        audio_file = mutagen.File(io.BytesIO(data))
        if audio_file is None:
            return 0
        if audio_file.tags:
            audio_file.tags.pprint()
        if audio_file.info:
            audio_file.info.pprint()

        out = io.BytesIO()
        audio_file.delete(out)
        audio_file.save(out)
        mutagen.File(out)
    except mutagen.MutagenError:
        return 0
    return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_parser.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    with open(input_file, "rb") as f:
        input_data = f.read()

    result = test_one_input(input_data)
    if result != 0:
        raise SystemExit(result)
    print(f"Successfully processed input file: {input_file}")


if __name__ == "__main__":
    main()
