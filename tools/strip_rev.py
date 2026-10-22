#!/usr/bin/env python3
"""Unwrap every \\rev{...} span in a LaTeX file by brace matching.

A regex cannot do this: \\rev{...} wraps nested braces, mathematics, blank
lines, itemize environments, a whole table body and one entire \\subsection{}.
The matcher walks the argument token by token, counting braces and honouring
LaTeX escaped braces (\\{ and \\}), and replaces \\rev{BODY} with BODY.

Usage: tools/strip_rev.py paper/main.tex [--backup /tmp/main.tex.bak]
"""
from __future__ import annotations

import pathlib
import sys

MARK = "\\rev{"


def strip(text: str) -> tuple[str, int]:
    out, i, n = [], 0, 0
    while True:
        j = text.find(MARK, i)
        if j < 0:
            out.append(text[i:])
            break
        k = j + len(MARK)
        depth = 1
        while depth:
            if text[k] == "\\":          # escaped brace: \{ or \}
                k += 2
                continue
            if text[k] == "{":
                depth += 1
            elif text[k] == "}":
                depth -= 1
            k += 1
        out.append(text[i:j])
        out.append(text[j + len(MARK):k - 1])
        i = k
        n += 1
    return "".join(out), n


def main() -> int:
    src = pathlib.Path(sys.argv[1])
    backup = None
    if "--backup" in sys.argv:
        backup = pathlib.Path(sys.argv[sys.argv.index("--backup") + 1])
    text = src.read_text()
    if backup is not None:
        backup.write_text(text)
    total, passes = 0, 0
    while MARK in text:
        # one pass unwraps outermost spans only: a \rev{...\rev{...}...} exposes
        # its inner span in the output, so the pass must repeat to a fixed point
        text, n = strip(text)
        total += n
        passes += 1
    src.write_text(text)
    left = text.count(MARK) + text.count("\\ifrevflag") + text.count("\\revflag")
    print(f"unwrapped {total} spans in {passes} passes; "
          f"{left} markup tokens remain")
    return 1 if left else 0


if __name__ == "__main__":
    sys.exit(main())
