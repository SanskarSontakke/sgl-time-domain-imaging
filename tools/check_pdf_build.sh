#!/usr/bin/env bash
# Build the manuscript and the submission letter from scratch, then assert that
# what comes out is the document the repository actually ships.
#
# Two properties of LaTeX make this worth scripting rather than eyeballing:
#
#   1. A PDF build is not byte-reproducible.  pdfTeX embeds a CreationDate and a
#      file ID, so recompiling paper/main.tex changes the bytes of paper/main.pdf
#      without changing a single word.  CI therefore must not build in the working
#      tree: it would break the byte-for-byte mirror gate
#      (src/make_app_docs.py --check) on a rebuild that proved nothing.  Here the
#      sources are copied to a scratch directory and built there.
#
#   2. latexmk is happy to declare a target up to date.  A fresh checkout contains
#      the shipped main.pdf, which is newer than or the same age as main.tex, so an
#      unguarded `latexmk -pdf` can "succeed" in zero seconds without running
#      pdfTeX at all -- and every assertion afterwards would then be checking the
#      artifact it just claimed to reproduce.  The copy's built PDFs and aux files
#      are deleted first, so a real compile is forced.
#
# What is asserted, per document: the build reported no error, no unresolved
# cross-reference or citation, no duplicate label; the text contains a phrase only
# the true title page can supply; and the fresh page count equals the shipped page
# count.  Page count rather than bytes for the last comparison, for reason 1, and
# rather than a full text diff because hyphenation and line breaking legitimately
# differ between TeX Live versions.
#
# Usage:  bash tools/check_pdf_build.sh [scratch-dir]
# The scratch directory is created with mktemp -d when omitted and is not removed.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build="${1:-$(mktemp -d)}"
mkdir -p "$build"

echo "== copying paper/ to $build =="
cp -a "$root/paper" "$build"/
if [ -d "$root/submission" ]; then
  cp -a "$root/submission" "$build"/
fi
for d in paper submission; do
  [ -d "$build/$d" ] || continue
  # drop every built artifact, but keep the figures, which are sources
  find "$build/$d" -mindepth 1 -maxdepth 1 \
    \( -name '*.pdf' -o -name '*.aux' -o -name '*.log' -o -name '*.out' \
       -o -name '*.fls' -o -name '*.fdb_latexmk' -o -name '*.bbl' -o -name '*.blg' \) \
    -delete
done

# Phrases each document must contain.  Deliberately not the subtitle: the
# manuscript was retitled once and will be retitled again, and a gate that greps
# for a subtitle breaks on a retitle rather than on a real defect.  What is
# pinned instead is the running head (which appears on every page of the built
# document), one phrase from the abstract, and the journal the letter addresses.
main_needles=("Solar Gravitational Lens"
              "generalized least squares"
              "Time-domain SGL imaging of cloudy exoplanets")
cover_letter_needles=("Open Journal of Astrophysics"
                      "Solar Gravitational Lens")

check_doc() {
  # $1 = directory, $2 = job name, remaining args = phrases the PDF must contain
  local dir="$1" job="$2"
  shift 2
  local pdf="$dir/$job.pdf" log="$dir/$job.log"
  local shipped="$root/$(basename "$dir")/$job.pdf"

  echo
  echo "== $job =="

  # the engine must have run: a log that does not exist means nothing was built
  test -s "$log" || { echo "$job.log was not produced -- the build did not run"; exit 1; }
  if grep -qE "^! " "$log"; then
    echo "$job: LaTeX errors"
    grep -nE "^! " "$log" | head -5
    exit 1
  fi
  if grep -Eiq "undefined (references|citations)|multiply defined" "$log"; then
    echo "$job: unresolved cross-references or citations"
    grep -Ei "undefined (references|citations)|multiply defined" "$log" | head -5
    exit 1
  fi
  # Convergence, not just error-freedom: a log that still says "Rerun to get
  # cross-references right" after the loop above means the PDF a reader downloads
  # cites one pass out of date.  The structure audit calls the same pattern
  # log.rerun and ceilings it at zero, so the two gates agree.
  if grep -q "Rerun to get" "$log"; then
    echo "$job: still asking for another pass -- cross-references are one pass stale"
    exit 1
  fi

  test -s "$pdf" || { echo "$job.pdf was not produced"; exit 1; }
  local fresh
  fresh="$(pdfinfo "$pdf" | awk '/^Pages/{print $2}')"
  test -n "$fresh" || { echo "$job.pdf is unreadable"; exit 1; }

  # pdftotext lays the running title over two lines ("... with the Solar /
  # Gravitational Lens: ..."), so a grep on the raw text stream fails on a
  # perfectly good PDF; flatten all whitespace to single spaces first.
  local text
  text="$(pdftotext "$pdf" - | tr '[:space:]' ' ' | tr -s ' ')"
  local needle
  for needle in "$@"; do
    grep -qF -- "$needle" <<<"$text" || {
      echo "$job.pdf does not contain '$needle' -- not the document the repository claims"
      exit 1
    }
    echo "text check: found '$needle'"
  done

  if [ -f "$shipped" ]; then
    local pages
    pages="$(pdfinfo "$shipped" | awk '/^Pages/{print $2}')"
    echo "pages: fresh=$fresh shipped=$pages"
    [ "$fresh" = "$pages" ] || {
      echo "the shipped $job.pdf is $pages pages but a fresh build is $fresh;"
      echo "recompile it and refresh the mirrors with src/make_app_docs.py"
      exit 1
    }
  else
    echo "no shipped $job.pdf in the repository to compare against"
    exit 1
  fi
}

compile_doc() {
  # $1 = scratch directory holding the sources, $2 = the .tex file.  The engine's
  # own chatter goes to a log per document: the first pdfTeX pass of a real
  # from-scratch build lists every citation as undefined -- that is what the later
  # passes are for -- so showing it live would look like a failure.
  #
  # latexmk can stop with the last pass still asking for one more.  Prose that
  # reflows moves a float, which changes the page stored in \newlabel; the
  # auxiliary-file hash latexmk compares was taken before that pass, so it
  # declares the target up to date while the document's cross-references are one
  # pass stale.  The shipped PDF of this manuscript did exactly that after a
  # three-digit edit in Appendix D, so the loop forces the passes latexmk skipped
  # and check_doc below refuses anything that still has not converged.
  local dir="$1" tex="$2" out job log pass
  job="$(basename "$tex" .tex)"
  out="$build/compile-$job.log"
  log="$dir/$job.log"
  if ! (cd "$dir" && latexmk -pdf -interaction=nonstopmode "$tex") >"$out" 2>&1; then
    echo "latexmk failed for $tex"
    tail -40 "$out"
    exit 1
  fi
  for pass in 1 2 3; do
    grep -q "Rerun to get" "$log" || break
    echo "$job: the log asks for another pass, forcing pass $pass"
    if ! (cd "$dir" && latexmk -pdf -g -interaction=nonstopmode "$tex") >>"$out" 2>&1; then
      echo "latexmk -g failed for $tex"
      tail -40 "$out"
      exit 1
    fi
  done
}

echo
echo "== compiling (from scratch, in $build) =="
compile_doc "$build/paper" main.tex
check_doc "$build/paper" main "${main_needles[@]}"

if [ -d "$build/submission" ]; then
  compile_doc "$build/submission" cover_letter.tex
  check_doc "$build/submission" cover_letter "${cover_letter_needles[@]}"
fi

echo
echo "RESULT: OK (paper builds clean and matches the shipped page counts)"
