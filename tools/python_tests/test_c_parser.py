#!/usr/bin/env python3
"""
Direct test script for pycparser coverage collection.
"""

import sys

import atheris
import pycparser


def test_one_input(
    c_source: str,
    lex_optimize: bool = True,
    yacc_debug: bool = False,
    yacc_optimize: bool = True,
) -> None:
    parser = pycparser.c_parser.CParser(
        lex_optimize=lex_optimize,
        yacc_debug=yacc_debug,
        yacc_optimize=yacc_optimize,
    )
    try:
        parser.parse(c_source, "")
    except pycparser.c_parser.ParseError:
        pass
    except AssertionError:
        pass


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_c_parser.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    with open(input_file, "rb") as f:
        input_data = f.read()

    fdp = atheris.FuzzedDataProvider(input_data)
    lex_optimize = fdp.ConsumeBool()
    yacc_debug = fdp.ConsumeBool()
    yacc_optimize = fdp.ConsumeBool()
    c_source = fdp.ConsumeUnicodeNoSurrogates(sys.maxsize)

    test_one_input(c_source, lex_optimize, yacc_debug, yacc_optimize)
    print(f"Successfully processed input file: {input_file}")


if __name__ == "__main__":
    main()
