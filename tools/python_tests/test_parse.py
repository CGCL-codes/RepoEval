#!/usr/bin/env python3
"""
Direct test script for sqlparse coverage collection.
"""

import sys

import sqlparse


def test_one_input(data: bytes) -> None:
    try:
        sql_string = data.decode("utf-8", errors="ignore")
        sqlparse.parse(sql_string)
    except RecursionError:
        pass


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_parse.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    with open(input_file, "rb") as f:
        input_data = f.read()

    test_one_input(input_data)
    print(f"Successfully processed input file: {input_file}")


if __name__ == "__main__":
    main()
