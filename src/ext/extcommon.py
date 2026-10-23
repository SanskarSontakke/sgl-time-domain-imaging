"""Shared plumbing for the extension modules.

Import style: run as ``python3 -m ext.<name>`` from ``src/``, because the spine
(``sglsim`` / ``expcommon``) uses flat imports and expects ``src/`` on the path.

Archives
--------
Every module writes exactly one of

    results/ext_<name>.npz     numeric arrays
    results/ext_<name>.json    scalars, tables, provenance

and nothing else.  ``results/parts/`` and the shipped top-level archives belong
to the fiducial pipeline; extensions must not write there (deleting every
``ext_*`` archive has to leave the original paper standing).

Two run tiers are standard:
``--fast`` uses EXT_SEEDS (4 noise seeds) and is what CI runs; the default tier
uses FULL_SEEDS (10) so the numbers can be quoted in the manuscript alongside
the fiducial statistics.
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent          # src/ext
SRC = HERE.parent                               # src
# Honours the same redirect as expcommon.DATA, so `reproduce_all` can run the
# extension modules against a scratch copy of the archives.
DATA = Path(os.environ.get("SGL_RESULTS_DIR") or (SRC.parent / "results"))

# Noise-seed sets.  The shipped suite uses expcommon.SEEDS (11..20); an
# extension that must stay cheap uses the first four, which are a subset, so a
# fast-tier number is always a sub-sample of the full-tier number.
FULL_SEEDS = [11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
EXT_SEEDS = FULL_SEEDS[:4]
CAD_SEEDS = FULL_SEEDS[:6]

# Truth-map seeds for the external-validity ensemble.  7 is the shipped
# fiducial map (expcommon.TRUTH_SEED), so the ensemble always CONTAINS the
# headline configuration and the fiducial numbers are directly comparable.
TRUTH_SEEDS = [7, 31, 32, 33, 34, 35, 36, 37, 38, 39]
TRUTH_SEEDS_FAST = TRUTH_SEEDS[:4]


def log(*a):
    print(f"[ext {time.strftime('%H:%M:%S')}]", *a, flush=True)


def tier_seeds(argv=None):
    """Return (seeds, truth_seeds, fast) for the usual --fast flag."""
    fast = "--fast" in (argv if argv is not None else sys.argv[1:])
    return (EXT_SEEDS, TRUTH_SEEDS_FAST) if fast else (FULL_SEEDS, TRUTH_SEEDS)


def arg(argv, name, default=None, cast=str):
    """Very small CLI helper: ``--nmax 96`` -> 96. No argparse dependency."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if name in argv:
        return cast(argv[argv.index(name) + 1])
    return default


def save_npz(name, **arr):
    """Write results/ext_<name>.npz atomically and return the path."""
    p = DATA / f"ext_{name}.npz"
    tmp = p.with_suffix(".tmp.npz")
    np.savez(tmp, **arr)
    os.replace(tmp, p)
    log(f"wrote {p.name} ({len(arr)} arrays, {p.stat().st_size / 1e6:.2f} MB)")
    return p


def save_json(name, obj):
    p = DATA / f"ext_{name}.json"
    tmp = p.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(obj, indent=2, default=float))
    os.replace(tmp, p)
    log(f"wrote {p.name} ({p.stat().st_size} B)")
    return p


def summary(name, **kv):
    """Machine-readable progress line the orchestrator can grep.

    Every extension module ends with ``summary(name, **headline_numbers)`` so
    `reproduce_all` and the tests can assert the archive and the printed claim
    agree without importing numpy internals.
    """
    clean = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in kv.items()}
    print("SUMMARY_JSON " + name + " " + json.dumps(clean, default=float), flush=True)
    return clean


def sha(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()[:16]


def provenance(module, extra=None):
    """Standard provenance block written into every ext_*.json.

    ``tier`` and ``argv`` are recorded automatically, because a manuscript
    number taken from a four-seed ``--fast`` archive is not the same claim as one
    taken from the ten-seed default tier.  An archive that does not say which
    tier produced it cannot be quoted without a caveat.
    """
    import sglsim as S
    import expcommon as E
    p = dict(
        module=module,
        tier=("fast" if "--fast" in sys.argv[1:] else "full"),
        argv=list(sys.argv[1:]),
        generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        numpy=np.__version__,
        python=sys.version.split()[0],
        fiducial=dict(nlat=E.NLAT, nlon=E.NLON, nlat_fine=E.NLATF,
                      nlon_fine=E.NLONF, ts=E.campaign().ts, mp=E.campaign().mp,
                      fc=E.FC, tau_days=E.TAU_DAYS, lam=E.LAM_GLS,
                      nsub=E.NSUB, truth_seed=E.TRUTH_SEED,
                      campaign_seed=E.CAMPAIGN_SEED),
        constants=dict(dtel=S.DTEL, dimg=S.DIMG, z=S.Z, z0=S.Z0,
                       rpl=S.RPL, prot=S.PROT, qexo=S.QEXO, qcor=S.QCOR),
    )
    if extra:
        p.update(extra)
    return p
