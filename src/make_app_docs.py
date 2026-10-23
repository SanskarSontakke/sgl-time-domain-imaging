"""Refresh the demo site's document mirrors from the repository's own sources.

public/docs/ is what the web app links, and every file in it is a *copy* of a
source that lives elsewhere in the repository -- paper/main.pdf,
submission/cover_letter.pdf and reviews/response_to_editor.md.  Copies go stale
silently: the shipped mirror of the manuscript was an 11-page build of an
earlier draft while paper/main.pdf was already 36 pages, and the letter mirror
was two pages of a letter that is now an eight-page point-by-point record.  A
reader following a link on the site was therefore reading a document that the
repository no longer contains.

Byte-identical copies, so the gate in tools/verify_flat.sh, the test in
tests/test_latex_integrity.py and the CI paper job can compare each mirror with
its source by checksum instead of by judgement -- and all three read the mapping
below rather than repeating it.

Run from the repository root, after compiling paper/main.tex and
submission/cover_letter.tex:  python3 src/make_app_docs.py
Check without writing:  python3 src/make_app_docs.py --check
"""

import hashlib
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

#: source -> mirror names, as (relative-to-root) paths.
#:
#: The pre-submission review record is shipped as Markdown, not as a second PDF
#: copy of the cover letter: the letter is a submission document, the review
#: record is the item-by-item audit behind it, and mirroring one file under two
#: names made them look like two documents that say the same thing.
MIRRORS = {
    "paper/main.pdf": ["web/public/docs/sgl_time_domain_imaging.pdf"],
}


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def stale():
    """Mirror names whose bytes differ from (or which lack) their source."""
    bad = []
    for src, mirrors in MIRRORS.items():
        sp = ROOT / src
        if not sp.exists():
            raise SystemExit(f"missing source {src}; compile it first")
        for rel in mirrors:
            dp = ROOT / rel
            if not dp.exists() or digest(rel) != digest(src):
                bad.append(rel)
    return bad


def sync():
    for src, mirrors in MIRRORS.items():
        for rel in mirrors:
            dp = ROOT / rel
            dp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / src, dp)
            size = dp.stat().st_size / 1024
            print(f"{rel} <- {src} ({size:.0f} kB)")
    print("mirrors are byte-identical to their sources")


def main():
    if "--check" in sys.argv[1:]:
        bad = stale()
        if bad:
            sys.exit("stale document mirrors (run src/make_app_docs.py): "
                     + ", ".join(bad))
        print("document mirrors match their sources")
        return
    sync()


if __name__ == "__main__":
    main()
