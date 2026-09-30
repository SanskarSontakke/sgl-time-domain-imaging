"""Rebuild data/codeSnippets.json from the shipped sources.

The demo "Source Code" viewer used to read a hand-copied JSON blob that still
held the v2-era text (including a `cad_solve_one.py` worker whose APIs no longer
exist anywhere in `src/`).  This script makes that panel a pure projection of the
repository: each listed file is read verbatim from `src/` and embedded, so the
site cannot show code the archive was not produced by.

Run from the repository root:  python3 src/make_app_code.py
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Viewer order matters: components/CodeViewer.tsx lists tabs in key order.
# These are the files the manuscript cites; sglsim.py alone is the physics and
# the estimators, so it stays first.
FILES = ["sglsim.py", "expcommon.py", "run_experiments.py", "targets.py",
         "make_figures.py"]


def main():
    snippets = {}
    for name in FILES:
        p = HERE / name
        if not p.exists():
            raise SystemExit(f"missing src/{name}")
        snippets[name] = p.read_text()
    out = ROOT / "data" / "codeSnippets.json"
    out.write_text(json.dumps(snippets, ensure_ascii=True, indent=1) + "\n")
    total = sum(len(v) for v in snippets.values())
    print(f"wrote {out} :: {len(snippets)} files, {total / 1e3:.0f} kB of source")


if __name__ == "__main__":
    main()
