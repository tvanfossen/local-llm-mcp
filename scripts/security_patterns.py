#!/usr/bin/env python3
"""Custom security pattern checker."""

import re
import sys

PATTERNS = [
    (r"eval\(", "Dangerous eval() usage"),
    (r"exec\(", "Dangerous exec() usage"),
    (r"__import__", "Dynamic import detected"),
]


def main():
    for filename in sys.argv[1:]:
        with open(filename) as f:
            content = f.read()
        for pattern, msg in PATTERNS:
            if re.search(pattern, content):
                print(f"{filename}: {msg}")
                sys.exit(1)


if __name__ == "__main__":
    main()
