#!/usr/bin/env python3
"""Independent check that the parts transform preserved every numeric array.

Compares a pre-transform parts directory against the post-transform one,
following the file-name and key mappings defined in flatten_archives.py, and
hashing the raw buffer of every numeric array.  Label arrays are compared as
strings, with the same v2 -> deflate substitution applied to the reference side.

Usage: tools/verify_parts_transform.py <before_dir> <after_dir>
Exit 0 only if every array in every file matches.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flatten_archives import KEY_MAP, TOKEN, flat_name  # noqa: E402

INV = {v: k for k, v in KEY_MAP.items()}


def sha(a) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(a)).tobytes()).hexdigest()


def old_key(new: str) -> str:
    if new in INV:
        return INV[new]
    m = TOKEN.search(new)
    if m is None:
        return new
    # inverse of the word-boundary substitution: first "deflate" token back to v2
    return new.replace("deflate", "v2", 1)


def main() -> int:
    before, after = Path(sys.argv[1]), Path(sys.argv[2])
    nfiles = narr = 0
    problems: list[str] = []
    for p in sorted(after.glob("*.npz")):
        q = None
        for cand in before.glob("*.npz"):
            if flat_name(cand.name) == p.name:
                q = cand
                break
        if q is None:
            problems.append(f"{p.name}: no pre-transform ancestor")
            continue
        nfiles += 1
        a, b = np.load(p, allow_pickle=True), np.load(q, allow_pickle=True)
        extra = {old_key(k) for k in a.files} ^ set(b.files)
        if extra:
            problems.append(f"{p.name}: key-set differs {sorted(extra)}")
            continue
        for k in a.files:
            x, y = np.asarray(a[k]), np.asarray(b[old_key(k)])
            narr += 1
            if x.shape != y.shape:
                problems.append(f"{p.name}:{k}: shape {x.shape} vs {y.shape}")
                continue
            if x.dtype.kind in "OSU":
                u = [str(v) for v in x.ravel()]
                v = [TOKEN.sub("deflate", str(w)) for w in y.ravel()]
                if u != v:
                    problems.append(f"{p.name}:{k}: label {u} vs {v}")
            elif sha(x) != sha(y):
                problems.append(f"{p.name}:{k}: NUMERIC BYTES DIFFER")
    print(f"{nfiles} file pairs, {narr} arrays compared")
    if problems:
        print(f"{len(problems)} PROBLEM(S):")
        for x in problems[:40]:
            print("  ", x)
        return 1
    print("OK: transform is numerically exact and label-consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
