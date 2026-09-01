#!/usr/bin/env python3
"""
Direct test script for scapy coverage collection.
"""

import io
import sys

import scapy.error
import scapy.layers.all  # noqa: F401
import scapy.utils


def test_one_input(data: bytes) -> None:
    try:
        for packet in scapy.utils.rdpcap(io.BytesIO(data)):
            packet.summary()
    except scapy.error.Scapy_Exception:
        pass


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python test_pcap.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    with open(input_file, "rb") as f:
        input_data = f.read()

    test_one_input(input_data)
    print(f"Successfully processed input file: {input_file}")


if __name__ == "__main__":
    main()
