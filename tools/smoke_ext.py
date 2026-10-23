#!/usr/bin/env python3
"""Dry-run an extension module WITHOUT touching results/.

Two failures this exists to prevent, both of which happened:

* a module computes for an hour and then crashes in its own save block, so the
  expensive run is wasted and the shipped archive is left stale;
* a test harness monkeypatches the archive writers on the wrong module object
  (``ext.extcommon`` vs the flat ``extcommon`` the modules actually import) and
  writes stub numbers straight into ``results/ext_<name>.{npz,json}``.

Here the archive writers are redirected to a temporary directory, so whatever
the module does it cannot reach the shipped files.  With ``--stub`` the
per-seed solver is replaced by a deterministic fake, which exercises the whole
statistics/JSON/npz path in milliseconds.

    python3 tools/smoke_ext.py cloud_physics --stub

Note: --stub does NOT validate any number.  It validates that the archive
block is constructible.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(1, str(SRC / "ext"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("module")
    ap.add_argument("--stub", action="store_true",
                    help="replace the per-seed solver with a fake (path check only)")
    ap.add_argument("--fast", action="store_true", default=True,
                    help="run the module's fast tier (default)")
    args = ap.parse_args()

    import importlib
    m = importlib.import_module(f"ext.{args.module}")

    # The ext modules do NOT agree on how they import their own helper layer:
    # some use ``import extcommon as X`` (flat, after a sys.path insert) and
    # some use ``from ext import extcommon as X``.  Those are two different
    # module objects holding two different copies of save_npz, so patching one
    # leaves the other writing straight into results/.  Patch both.
    helper_modules = []
    for modname in ("extcommon", "ext.extcommon"):
        try:
            helper_modules.append(importlib.import_module(modname))
        except ModuleNotFoundError:
            pass
    if not helper_modules:
        sys.exit("could not import the extcommon helper under either name")

    out = Path(tempfile.mkdtemp(prefix=f"smoke_{args.module}_"))
    written = {}

    def save_npz(name, **arrays):
        written[name] = {k: getattr(v, "shape", None) or len(v) for k, v in arrays.items()}
        return out / f"ext_{name}.npz"

    def save_json(name, obj):
        text = json.dumps(obj, default=str)
        (out / f"ext_{name}.json").write_text(text)
        written[name] = json.loads(text)
        return out / f"ext_{name}.json"

    for X in helper_modules:
        X.save_npz, X.save_json = save_npz, save_json

    if args.stub:
        worker = getattr(m, "_run_reconstruction_with_cloud", None)
        if worker is None:
            sys.exit("--stub needs a module-level _run_reconstruction_with_cloud")
        n = [0]

        def fake(cloud_model, camp, truthF, truth_c, sgl, sigma_cl, seed, nsub=16):
            n[0] += 1
            return dict(ssim=0.11, nrmse=0.8, pearson=0.40 + 0.001 * (n[0] % 3),
                        cover=0.5 + 0.01 * (n[0] % 3))
        m._run_reconstruction_with_cloud = fake

    sys.argv = [args.module, "--fast"]
    m.main()

    for name, payload in written.items():
        if isinstance(payload, dict):
            missing = {"headline", "caveats", "provenance"} - set(payload)
            if missing:
                sys.exit(f"ext_{name}.json is missing contract blocks: {missing}")
            if not payload["caveats"]:
                sys.exit(f"ext_{name}.json has an empty caveats list")
            print(f"OK ext_{name}.json blocks={sorted(payload)} "
                  f"caveats={len(payload['caveats'])}")
            print(json.dumps(payload["headline"], indent=1)[:900])
        else:
            print(f"OK ext_{name}.npz arrays={sorted(payload)}")
    print(f"redirected to {out} -- results/ untouched")


if __name__ == "__main__":
    main()
