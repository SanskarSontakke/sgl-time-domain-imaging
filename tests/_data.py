"""Shared data-loading helpers for the test suite.

All paths are relative to the repository root.  Archives are read-only.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PARTS = RESULTS / "parts"
CACHE = RESULTS / "cache"
PAPER = ROOT / "paper"
TOOLS = ROOT / "tools"


def load_audit():
    return json.loads((RESULTS / "audit.json").read_text())


def load_npz(name):
    return np.load(RESULTS / name, allow_pickle=True)


def load_cache_npz(name):
    return np.load(CACHE / name, allow_pickle=True)
