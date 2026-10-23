#!/bin/bash
# Regenerate the extension archives at the FULL tier, in dependency
# order: the cheap analytic modules first, the simulation-heavy ones last, so
# the memory-hungry runs never overlap.  Only results/ext_* is written.
#
# The order below is hand-picked (it encodes which archives the others lean on),
# but the SET is not: it is checked against reproduce_all.EXT_MODULES, so a
# module added to the registry without being added here fails loudly instead of
# silently shipping a stale archive.  truth_ensemble is the expensive one and
# runs last.
cd "$(dirname "$0")/.." || exit 1
ROOT="$PWD"
cd src || exit 1
LOG=${LOG:-/tmp/ext_full.log}
: > "$LOG"

ORDER="evidence_lambda corona_screen disk_kernel ephemeris telemetry \
target_uncertainty scheduling observable_roc fisher_bounds portability swarm \
priors truth_ensemble cloud_physics"

# Fail if the ordered list and the registry disagree in either direction.
python3 - "$ROOT" $ORDER <<'PY' || exit 1
import pathlib, re, sys
root = pathlib.Path(sys.argv[1])
want = set(sys.argv[2:])
src = (root / "reproduce_all.py").read_text()
reg = set(re.findall(r'"(\w+)"', src.split("EXT_MODULES = (", 1)[1].split(")", 1)[0]))
if want != reg:
    sys.exit(f"tools/run_ext_full.sh disagrees with reproduce_all.EXT_MODULES: "
             f"missing here {sorted(reg - want)}, extra here {sorted(want - reg)}")
PY

run() {
  echo "=== $1 start $(date -u +%T) ===" >> "$LOG"
  python3 -m "ext.$1" >> "$LOG" 2>&1
  echo "=== $1 rc=$? end $(date -u +%T) ===" >> "$LOG"
}

for m in $ORDER; do run "$m"; done
echo "ALL DONE ($(echo $ORDER | wc -w) modules) -> $LOG" >> "$LOG"
tail -1 "$LOG"
