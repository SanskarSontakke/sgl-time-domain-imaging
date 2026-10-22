#!/usr/bin/env python3
"""Byte-level content manifest for the shipped `.npz` / `.json` archives.

This is the object the single-version refactor is measured against: for every
array in every archive it records shape, dtype and the SHA-256 of the raw
buffer, so "the refactor changed no numbers" is a machine check, not a promise.

Usage:
    tools/array_manifest.py write results            # -> /tmp/manifest_before.json
    tools/array_manifest.py check results /tmp/manifest_before.json [--rename OLD:NEW]

`--rename` maps an old archive path onto the new one so a de-versioned tree can
still be compared element-for-element with its prefixed ancestor.

Exit code is 0 only when every array in every archive matches.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np


def digest(arr) -> str:
    a = np.ascontiguousarray(np.asarray(arr))
    return hashlib.sha256(a.tobytes()).hexdigest()


def manifest_npz(path: Path) -> dict:
    out = {}
    with np.load(path, allow_pickle=True) as d:
        for k in sorted(d.files):
            a = np.asarray(d[k])
            entry = {"shape": list(a.shape), "dtype": str(a.dtype)}
            if a.dtype.kind == "O":
                # object arrays hold Python labels; hash their repr so a label
                # rename is visible but a reordering is not silently accepted
                flat = [repr(v) for v in a.ravel()]
                entry["values"] = flat
                entry["sha"] = hashlib.sha256(
                    "\n".join(flat).encode()).hexdigest() if flat else digest(a)
            elif a.dtype.kind in "SU":
                flat = [str(v) for v in a.ravel()]
                entry["values"] = flat
                entry["sha"] = hashlib.sha256("\n".join(flat).encode()).hexdigest()
            else:
                entry["sha"] = digest(a)
                if a.size and a.dtype.kind in "fc":
                    finite = a[np.isfinite(a)]
                    entry["max_abs"] = float(np.abs(finite).max()) if finite.size else 0.0
            out[k] = entry
    return out


def manifest(root: str) -> dict:
    rootp = Path(root)
    m = {}
    for p in sorted(rootp.rglob("*.npz")):
        if "cache" in p.parts:
            continue
        m[str(p)] = manifest_npz(p)
    for p in sorted(rootp.rglob("*.json")):
        if "cache" in p.parts:
            continue
        m[str(p)] = json.loads(p.read_text())
    return m


def compare(new_root: str, before: dict, rename: dict) -> tuple[list, int]:
    """Return (problems, n_compared_arrays)."""
    m_new = manifest(new_root)
    problems, n = [], 0
    for path, old in before.items():
        key = rename.get(path, path)
        if key not in m_new:
            problems.append(f"MISSING ARCHIVE {key}")
            continue
        new = m_new[key]
        if path.endswith(".json"):
            if json.dumps(old, sort_keys=True) != json.dumps(new, sort_keys=True):
                problems.append(f"JSON differs: {key}")
            n += 1
            continue
        okl = set(old) ^ set(new)
        # a renamed key is only acceptable if it is a known label change
        for k in sorted(okl):
            problems.append(f"{key}: key set differs at {k}")
        for k in sorted(set(old) & set(new)):
            n += 1
            if old[k].get("sha") != new[k].get("sha"):
                problems.append(
                    f"{key}:{k} content differs (old {old[k].get('sha')[:12]} "
                    f"new {new[k].get('sha')[:12]})")
            elif old[k]["shape"] != new[k]["shape"]:
                problems.append(f"{key}:{k} shape differs")
    return problems, n


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    cmd = argv[1]
    if cmd == "write":
        root = argv[2] if len(argv) > 2 else "results"
        out = Path(argv[3]) if len(argv) > 3 else Path("/tmp/manifest.json")
        m = manifest(root)
        out.write_text(json.dumps(m, indent=1, sort_keys=True))
        print(f"wrote {out}: {len(m)} archives")
        return 0
    if cmd == "check":
        root = argv[2]
        before = json.loads(Path(argv[3]).read_text())
        rename = {}
        for spec in argv[4:]:
            if spec.startswith("--rename"):
                continue
            if ":" in spec:
                a, b = spec.split(":", 1)
                rename[a] = b
        problems, n = compare(root, before, rename)
        print(f"compared {n} arrays/archives")
        if problems:
            print(f"{len(problems)} PROBLEM(S):")
            for p in problems[:60]:
                print("  ", p)
            return 1
        print("OK: every array matches byte-for-byte")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
