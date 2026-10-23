#!/usr/bin/env bash
# tools/verify_numbers.sh -- the whole proof stack, in one command.
#
# This is the research equivalent of `npm run build && npm test`: it re-runs
# every deterministic check the repository makes about itself, in the order a
# build would, and prints PASS / FAIL / SKIP for each layer.  It exits non-zero
# if anything failed, so it drops into CI unchanged -- the `numbers` job of
# .github/workflows/verify.yml runs these steps in this order.
#
#   bash tools/verify_numbers.sh              # every layer, offline-safe
#   bash tools/verify_numbers.sh --with-pdf   # also rebuild and re-audit the paper
#   bash tools/verify_numbers.sh --quick      # numbers only, skip pytest and gates
#
# Deliberately offline-safe: with no TeX in the container the structural audit
# falls back to the tracked build record, so the script still answers "is the
# paper the shape we say it is?" -- it answers it from what was shipped rather
# than from a build that happened here, and says which it did.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

PY=${PYTHON:-python3}
fails=0; skips=0; passes=0

step() { printf '\n== %s ==\n' "$1"; }
pass() { printf 'PASS   %s\n' "$1"; passes=$((passes+1)); }
fail() { printf 'FAIL   %s\n' "$1"; fails=$((fails+1)); }
skip() { printf 'SKIP   %s\n' "$1"; skips=$((skips+1)); }

# run <label> <command...>: the command's own output is shown only on failure,
# and only the last $TAIL lines of it on success, so the stack stays readable
# while a red step still carries the evidence.
TAIL=3
run() {
  local label="$1"; shift
  local out
  if out=$("$@" 2>&1); then
    pass "$label"
    printf '%s\n' "$out" | sed 's/^/       /' | tail -n "$TAIL"
  else
    fail "$label"
    printf '%s\n' "$out" | sed 's/^/       /' | tail -n 30
  fi
  TAIL=3
}

WITH_PDF=0; QUICK=0
for a in "$@"; do
  [ "$a" = "--with-pdf" ] && WITH_PDF=1
  [ "$a" = "--quick" ] && QUICK=1
done

# --------------------------------------------------------------------------- #
step "N-1  build step: the derived statistics regenerate from the archives"
TAIL=1 run "$PY tools/derive_stats.py --check" \
    "$PY" tools/derive_stats.py --check

# --------------------------------------------------------------------------- #
step "N-2  ledger: every number printed in the paper traces to an archived value"
TAIL=4 run "$PY tools/claims.py --check (>= 620 claims, 0 untraceable)" \
    "$PY" tools/claims.py --check --min-claims 620 --max-untraceable 0
echo "       traceability counters:"
if "$PY" tools/claims.py --coverage 2>&1 | tail -n 6 | sed 's/^/       /'; then
    :
else
    fail "tools/claims.py --coverage did not run"
fi

# --------------------------------------------------------------------------- #
step "N-3  structure: the document is the shape its own abstract claims"
if [ -f paper/main.aux ]; then
    TAIL=2 run "manuscript_outline: audit of this tree's build" \
        "$PY" tools/manuscript_outline.py --strict-metadata
    TAIL=2 run "manuscript_outline: the tracked record says the same" \
        "$PY" tools/manuscript_outline.py --record \
            tools/manuscript_build_record.json
else
    TAIL=2 run "manuscript_outline: tracked build record (no paper/main.aux here)" \
        "$PY" tools/manuscript_outline.py --record \
            tools/manuscript_build_record.json
fi

# --------------------------------------------------------------------------- #
step "N-4  documentation: README, tests/README, Appendix D and CI state the tree"
TAIL=2 run "$PY tools/doc_numbers.py (>= 34 claims, 0 findings)" \
    "$PY" tools/doc_numbers.py --min-claims 34

# --------------------------------------------------------------------------- #
if [ "$QUICK" -eq 0 ]; then
  step "N-5  the suites that test the testers"
  TAIL=1 run "pytest: ledger + derived stats, outline, documentation" \
      "$PY" -m pytest tests/test_claims_ledger.py \
          tests/test_manuscript_outline.py tests/test_doc_numbers.py \
          -q -p no:cacheprovider --strict-markers --strict-config -rfs
fi

# --------------------------------------------------------------------------- #
step "N-6  mirrors: public/docs are byte-identical to the shipped documents"
TAIL=1 run "python3 src/make_app_docs.py --check" \
    "$PY" src/make_app_docs.py --check

# --------------------------------------------------------------------------- #
if [ "$WITH_PDF" -eq 1 ]; then
  step "N-7  rebuild both documents from scratch and re-audit the result"
  if ! command -v latexmk >/dev/null 2>&1 || ! command -v pdftotext >/dev/null 2>&1; then
    skip "no latexmk / pdftotext in PATH"
  else
    # Built in a scratch tree, never in the checkout: pdfTeX stamps a creation
    # date, so compiling into the working tree would break the mirror gate above
    # on a rebuild that proved nothing.
    scratch=$(mktemp -d "${TMPDIR:-/tmp}/verify-numbers.XXXXXX") || exit 1
    if TAIL=2 run "bash tools/check_pdf_build.sh (scratch tree)" \
        bash tools/check_pdf_build.sh "$scratch"; then
      pdftotext "$scratch/paper/main.pdf" "$scratch/main.txt" 2>/dev/null
      TAIL=2 run "structural audit of the fresh build" \
          "$PY" tools/manuscript_outline.py --build-dir "$scratch/paper" \
              --pdf-text "$scratch/main.txt" --strict-metadata
      TAIL=4 run "fresh build vs the tracked build record" \
          "$PY" tools/manuscript_outline.py --compare-record \
              tools/manuscript_build_record.json --build-dir "$scratch/paper"
    fi
    rm -rf "$scratch"
  fi
else
  step "N-7  PDF rebuild (opt-in)"
  skip "add --with-pdf to compile both documents and audit the fresh build"
fi

# --------------------------------------------------------------------------- #
if [ "$QUICK" -eq 0 ]; then
  step "N-8  consolidation gates G-1..G-7 (single-version contract)"
  TAIL=1 run "bash tools/verify_flat.sh" bash tools/verify_flat.sh
fi

printf '\n---- verify_numbers: %d passed, %d failed, %d skipped ----\n' \
    "$passes" "$fails" "$skips"
[ "$fails" -eq 0 ] || exit 1
