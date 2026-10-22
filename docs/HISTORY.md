# History — Single-Version Consolidation

## Background

This project previously shipped parallel version trees (`paper/v1/`, `paper/v2/`, `paper/v3/`) and carried a `v2` estimator label for the approximate per-slot deflation solver. The repository also contained `src/v2_superseded/`, `results/superseded_v2/`, `results/parts/v2_superseded/`, `submission/archive_v2/`, and `reviews/v2_superseded/` directories holding pre-revision scripts, checkpoints, letters, and metadata.

## The Refactor

A pre-submission review — commissioned by the author and written in the *Open Journal of
Astrophysics* referee-report format, not a journal referee report — drove the refactor that
collapsed the parallel version trees into a single standalone version. The longer report that
scheduled that work is not shipped with the repository; what the record here refers to by ID
(defect-register entries F-16, F-17, F-19, F-21 and Stage 6 of the consolidation plan) resolves
into two things that are shipped: the point-by-point responses in
`reviews/response_to_editor.md`, and a named regression test for each repaired value
(`tests/README.md`, "Defect Coverage"). That review identified the version proliferation as a
reviewability hazard: three manuscripts, two cover letters, two marked PDFs, and 21 MB of prefixed
checkpoints in a single repository made it difficult to determine which numbers were live and
which were historical.

The refactor deleted all superseded directories and renamed the estimator baseline from `v2` to `deflate` throughout the code, archives, and prose. The renamed baseline `deflate` is the approximate per-slot deflation solver that was previously labelled `v2`; it is now documented as "the approximate-deflation baseline" in the paper and code.

## Key and Label Rename Map

The `tools/flatten_archives.py` script performed the following renames on checkpoint keys and labels:

| Old key | New key |
|---------|---------|
| `v2_pearson` | `deflate_pearson` |
| `v2_ssim` | `deflate_ssim` |
| `v2_nrmse` | `deflate_nrmse` |
| `v2_bias` | `deflate_bias` |
| `v2_contrast` | `deflate_contrast` |
| `map_v2` | `map_deflate` |
| `C_v2_deflate_pearson` | `C_deflate_pearson` |
| `C_v2_deflate_ssim` | `C_deflate_ssim` |
| `C_v2_deflate_nrmse` | `C_deflate_nrmse` |
| `C_v2_deflate_bias` | `C_deflate_bias` |
| `C_v2_deflate_contrast` | `C_deflate_contrast` |
| `reldev_C_v2_deflate` | `reldev_C_deflate` |
| `norm_C_v2_deflate` | `norm_C_deflate` |

Part file names embed the estimator label, so the stem needed its own map:

| Old name token | New name token |
|----------------|----------------|
| `sigclv2` | `sigcldeflate` |

The audit JSON rename map (from `tools/verify_flat.py`):

| Old JSON path segment | New JSON path segment |
|-----------------------|----------------------|
| `v2` | `deflate` |
| `C_v2_deflate` | `C_deflate` |
| `r_v2` | `r_deflate` |
| `fiducial_profiled_vs_v2_rel_diff` | `fiducial_profiled_vs_deflate_rel_diff` |
| `sigma_sensitivity_v2` | `sigma_sensitivity_deflate` |

Additionally, the orphan keys `reldev_F_minus_C`, `mean_reldev_F_minus_C`, and `sem_reldev_F_minus_C` (which the shipped archive carried without a writer — see defect F-22) were renamed to `reldev_F_vs_C`, `mean_reldev_F_vs_C`, and `sem_reldev_F_vs_C` to clarify that they represent ||F − C|| / ||F||, the per-seed relative deviation of the full-TDI map from the approximate-deflation baseline.

## Verification Tooling

Two scripts verify that the refactor changed no reported numbers:

- `tools/verify_flat.py` — Gate G-3: proves that the single-version refactor changed no reported number. Walks the pre-refactor audit JSON and the pre-refactor archives and compares every numeric leaf with the current tree, following the documented key renames. Tolerance is tiered: tier 0 for deterministic reductions (mean/SE/counts/derived ratios) requires exact match; tier 1 for linear-algebra reductions (BLAS / summation order) allows 1e-12.

- `tools/array_manifest.py` — Byte-level content manifest for the shipped `.npz` / `.json` archives. For every array in every archive it records shape, dtype, and the SHA-256 of the raw buffer, so "the refactor changed no numbers" is a machine check, not a promise.

The `tools/flatten_archives.py` script itself verifies per-array that the bytes of every numeric payload are identical before and after the transform.

## Withdrawn Claims

Several claims from the earlier version trees were withdrawn rather than updated with new numbers. These are documented in `reviews/response_to_editor.md` and include:

- In-flight ephemeris refinement via profile likelihood (the whitened χ² is phase-invariant to 10⁻¹¹)
- "93.75% of spatial information retained" by deflation (replaced by the nullity-288 audit)
- "14–23×" noise inflation (measured 12.8–21.0× in σ, 163–440× in variance)
- "~2 GB" telemetry (2.10 MB campaign / 10.4 kB map)
- Unproduced `r_smear`/`r_cf`/`r_iid` cadence columns
- Unmeasured coronal-robustness and λ-insensitivity assertions

## AASTeX Port

The AASTeX port that used to sit at `paper/main_emulateapj.tex` was still the earlier text and carried the withdrawn claims listed above. It was moved out of the live paper directory rather than left in place as an apparently-live second manuscript. If the journal needs an AASTeX port, it should be generated from the current `paper/main.tex`.

## Note on PDF Recompilation

The LaTeX PDFs (`paper/main.pdf`, `paper/sgl_time_domain_imaging.pdf`, `submission/cover_letter.pdf`) are compiled in the audit environment from their own sources (`latexmk -pdf main.tex` in `paper/`, `latexmk -pdf cover_letter.tex` in `submission/`), and the `paper` job of `.github/workflows/verify.yml` re-compiles both on every push and fails the build on unresolved references. `paper/sgl_time_domain_imaging.pdf`, `public/docs/sgl_time_domain_imaging.pdf` and `public/docs/cover_letter.pdf` are byte mirrors of those builds, and `public/docs/response_to_editor.md` is a byte mirror of `reviews/response_to_editor.md`; all of them are written by `python3 src/make_app_docs.py` after each compile, and `tests/test_latex_integrity.py::TestDocumentMirrorsAreFresh` checks they still match. The toolchain is TeX Live (`texlive-latex-base`, `-recommended`, `-extra`, `texlive-fonts-recommended`, `latexmk`, `poppler-utils`); the manuscript needs no class or style file beyond it.
