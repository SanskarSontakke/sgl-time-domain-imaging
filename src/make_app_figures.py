"""Refresh the demo site's figure mirrors from the manuscript PDFs.

public/figures/ is what the web app displays, and it is a *copy* of
paper/figures/ -- so it silently goes stale the moment a figure is regenerated
for the paper.  This happened in the v2 -> v3 transition: the shipped PNGs were
still rendered from the v2 PDFs and contradicted the manuscript captions.

The script copies each vector PDF and rasterises a 200 dpi PNG next to it, so
the gallery always shows exactly what paper/main.tex includes.  It shells out to
poppler's pdftoppm rather than adding a Python PDF dependency.

Run from the repository root, after python3 src/make_figures.py and
python3 src/targets.py:  python3 src/make_app_figures.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "paper" / "figures"
DST = ROOT / "public" / "figures"
DPI = 200


def main():
    if not SRC.is_dir():
        sys.exit(f"missing {SRC} -- run src/make_figures.py and src/targets.py first")
    try:
        subprocess.run(["pdftoppm", "-v"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        sys.exit("pdftoppm (poppler-utils) is required to rasterise the mirrors")
    DST.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(SRC.glob("*.pdf"))
    if not pdfs:
        sys.exit(f"no PDFs in {SRC}")
    for pdf in pdfs:
        shutil.copy2(pdf, DST / pdf.name)
        out = DST / (pdf.stem + ".png")
        subprocess.run(["pdftoppm", "-png", "-singlefile", "-r", str(DPI),
                        str(pdf), str(out.with_suffix(""))], check=True)
        print(f"{pdf.name}: {pdf.stat().st_size / 1024:.0f} kB PDF, "
              f"{out.stat().st_size / 1024:.0f} kB PNG")
    # Drop mirrors whose source figure no longer exists in the paper.
    keep = {p.stem for p in pdfs}
    for stale in list(DST.glob("*.pdf")) + list(DST.glob("*.png")):
        if stale.stem not in keep:
            stale.unlink()
            print("removed stale mirror", stale.name)


if __name__ == "__main__":
    main()
