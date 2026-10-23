# Test Suite for SGL Time-Domain Imaging

Comprehensive pytest test suite covering the simulation pipeline, physics constants, statistical methods, archive integrity, and LaTeX manuscript consistency.

## Test Modules

| Module | Purpose | Count |
|--------|---------|-------|
| `test_constants.py` | First-principles physics re-derivations (z_min, D_img, kernel, SNR_C, noise floor F-01) | 11 |
| `test_statistics.py` | Paired stats harness, exact sign-test floors, audit.json p-value consistency | 8 |
| `test_quadrature.py` | Gauss-Legendre convergence, equal-spaced 3-node defect | 4 |
| `test_kernel.py` | Cellmean kernel formula, F-14 homogeneity defect | 4 |
| `test_geometry.py` | Ecliptic latitudes for 6 targets, Chen & Kipping de-inclination, grid sizes F-16 | 12 |
| `test_archive_schema.py` | Method/component labels, version pattern, PART_PREFIX | 10 |
| `test_audit_consistency.py` | Profiled vs deflate, component ablation F vs C, cloud-free r(l) min F-15, lambda sweep F-07/F-09b, l_eff null F-20 | 8 |
| `test_defect_regression.py` | Pins defects F-01, F-07, F-15, F-20, F-22 | 6 |
| `test_pipeline_tools.py` | Pure functions from tools/*.py (flat_name, remap, strip_rev, digest) plus the byte-level archive manifest, its path-portability contract, and the shape of the CI LaTeX and float-tolerance gates in `tools/check_pdf_build.sh` and `.github/workflows/verify.yml`, plus the one-command proof stack in `tools/verify_numbers.sh`, the `npm test` entry points in `package.json`, the three-job split (gates / numbers / paper) with its ceilings, concurrency and artifact upload, the capped, retrying TeX Live install step that keeps a stalled package mirror from spending the paper job's whole ceiling, and the build-convergence passes latexmk skips | 63 |
| `test_pipeline_live.py` | Slow tier: re-runs the fiducial estimator on the cached dataset and compares against the shipped checkpoints; proves `results/` is read-only, with a cold tree's memoisation rebuild classified apart from a write into the shipped evidence | 19 |
| `test_ledger_resource.py` | Analytic resource-ledger and `N_eff` arithmetic: OU pair weights, Arm A/B photon-vs-wall-clock conservation, dose accounting | 12 |
| `test_latex_integrity.py` | No \rev markup, ref/label integrity, cite keys, F-12/F-18/F-05 repairs, brace/environment balance, generated-table shape, document-mirror freshness, no revision-tracker IDs in reader-facing text | 30 |
| `test_ext_archives.py` | Contract for the 14 computed extensions in `src/ext/`: every `ext_*.{npz,json}` pair exists, carries a schema, a `provenance` block with tier and argv, headline strings within length limits, and values that agree with the manuscript | 163 |
| `test_claims_ledger.py` | Provenance of every number the manuscript prints: `tools/claims.py` harvests the printed decimals, `tools/derive_stats.py` reduces the shipped archives to deterministic statistics, and each claim must resolve to an archived value or to an arithmetic relation that is re-evaluated rather than remembered. Includes tamper proofs, so the gate cannot be satisfied by an empty ledger | 138 |
| `test_manuscript_outline.py` | Structural audit of the document itself, from `main.aux`/`main.log` or from the tracked build record: chapter order and the documented spine, page monotonicity, float numbering, captions, citations and placement, equation numbers, unresolved references, log ceilings, PDF metadata, and the counts the README, the arXiv listing and the demo app claim, plus the diff between a freshly distilled build record and the tracked one | 93 |
| `test_doc_numbers.py` | Documentation audit: every count the README, this file, Appendix D and the CI workflow state is re-measured from the tree -- pytest collection, an AST walk, `np.load` over `results/`, the ledger and the build record -- with tamper proofs for each claim family, the per-module table audited in both directions, and the workflow checked against its own ceiling, install-step cap, tier and mirror-order comments | 118 |
| `test_reproduce_entrypoint.py` | `reproduce_all.py` CLI surface: stage registry (8 fast / 70 full), subcommand <-> module mapping, scratch isolation, baseline freeze/check, `--figures`/`--ext` plumbing, and the slow tier's read-only guard -- its cold-rebuild classification driven through the fixture itself, so a guard that cannot fire cannot be trusted | 54 |

**Total: 567 test functions, 753 collected checks** (732 in the default fast
tier, 21 marked `slow`).

## Running the Tests

### Full suite
```bash
cd /data/workspace/sgl-time-domain-imaging
python3 -m pytest tests -q
```

### Exclude slow tests (default CI tier; 732 of 753 checks)
```bash
python3 -m pytest tests -q -m "not slow"
```

### Slow tier only (the 21 end-to-end re-simulation checks)
```bash
python3 -m pytest tests -q -m slow
```

### Verbose output
```bash
python3 -m pytest tests -v
```

### Run specific module
```bash
python3 -m pytest tests/test_constants.py -v
```

## Test Tiers

- **Fast (default)**: 732 checks. No simulation is re-run; every value is read
  from a shipped archive, `results/audit.json`, or the manuscript source.
- **Slow (> 5s)**: 21 checks marked `@pytest.mark.slow` — 19 in
  `test_pipeline_live.py`, which re-runs GLS solves against the shipped
  checkpoints and is the tier that catches drift between `src/` and `results/`,
  and 2 in `test_reproduce_entrypoint.py`, which invoke the real
  `reproduce_all` entry point in a scratch directory.

## Configuration

- `pytest.ini`: Defines the `slow` marker and test paths
- `conftest.py`: Adds `src/` to sys.path for flat imports

## Data Dependencies

Tests read from (but never write to):
- `results/*.npz` (45 shipped archives, 14 of them `ext_*` extension archives)
- `results/*.json` (22 headline files — all 14 `ext_*` archives ship an
  `npz`/`json` pair, plus `audit`, `precision`, `targets`, `kinematics`,
  `core_ablation`, `deflation_diag`, `kernel_convergence`, `uniform_disk`)
- `results/parts/*.npz` (582 checkpoint files)
- `results/cache/` (memoised forward operators and photon streams)
- `paper/main.tex`
- `paper/targets_table.tex`
- `paper/main.pdf` and the `public/docs/` mirrors (freshness gate)
- `tools/*.py` (verification utilities)

## Defect Coverage

The suite pins the following defects from the revision record:

| Defect | Test | Status |
|--------|------|--------|
| F-01 (noise floor t_b) | `test_constants.py::TestNoiseFloor`, `test_defect_regression.py::TestF01NoiseFloor` | ✓ Fixed |
| F-07 (lambda sweep chi2) | `test_defect_regression.py::TestF07LambdaSweep` | ✓ Documented |
| F-12 (Toth 2025 citation) | `test_latex_integrity.py::TestF12Toth2025` | ✓ Fixed |
| F-14 (kernel homogeneity) | `test_kernel.py::TestF14Homogeneity` | ✓ Documented |
| F-15 (cloud-free r(l) min) | `test_audit_consistency.py::TestCloudFreeRlMinimum`, `test_defect_regression.py::TestF15CloudFreeRLower` | ✓ Documented |
| F-16 (grid sizes) | `test_geometry.py::TestGridSizes` | ✓ Fixed |
| F-18 (missing 2026c) | `test_latex_integrity.py::TestF18NoMissing2026c` | ✓ Fixed |
| F-20 (l_eff null vs NaN) | `test_audit_consistency.py::TestLeffNullHandling`, `test_defect_regression.py::TestF20LeffNullNotNaN` | ✓ Fixed |
| F-22 (orphan array definition) | `test_defect_regression.py::TestF22OrphanArrayDefinition` | ✓ Fixed |

## Runtime Performance

Measured on the four-core / 7 GB sandbox the archive was audited in, with the
memoised forward operators present under `results/cache/`:

- **Fast tier** (`-m "not slow"`, 732 checks): ~5 s
- **Slow tier** (`-m slow`, 21 checks): ~147 s
- **Both tiers**: ~3 min

`results/cache/` is 731 MB and is deliberately *not* shipped (`.gitignore`), so on
a fresh clone the slow tier rebuilds it first and costs hours rather than minutes.
The `results_read_only` guard in `test_pipeline_live.py` knows the difference: a
new key under `results/cache/` is reported as a rebuild, while any created,
deleted or modified file anywhere else under `results/` -- or a cache key outside
the four memoisation families -- fails the tier. The fast tier never touches the
cache, which is why CI runs only the fast tier plus `reproduce_all --fast`.

## Notes

- All tests are deterministic (no wall-clock or random dependence)
- expcommon.paired_stats uses nboot=20000, seed=42 (bootstrap is seeded)
- Tests use cached objects from results/cache where available
- No tests modify src/, results/, or paper/ (read-only against repository data)
