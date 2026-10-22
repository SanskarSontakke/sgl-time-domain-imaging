# Test Suite for SGL Time-Domain Imaging

Comprehensive pytest test suite covering the simulation pipeline, physics constants, statistical methods, archive integrity, and LaTeX manuscript consistency.

## Test Modules

| Module | Purpose | Count |
|--------|---------|-------|
| `test_constants.py` | First-principles physics re-derivations (z_min, D_img, kernel, SNR_C, noise floor F-01) | 9 |
| `test_statistics.py` | Paired stats harness, exact sign-test floors, audit.json p-value consistency | 8 |
| `test_quadrature.py` | Gauss-Legendre convergence, equal-spaced 3-node defect | 4 |
| `test_kernel.py` | Cellmean kernel formula, F-14 homogeneity defect | 4 |
| `test_geometry.py` | Ecliptic latitudes for 6 targets, Chen & Kipping de-inclination, grid sizes F-16 | 11 |
| `test_archive_schema.py` | Method/component labels, version pattern, PART_PREFIX | 10 |
| `test_audit_consistency.py` | Profiled vs deflate, component ablation F vs C, cloud-free r(l) min F-15, lambda sweep F-07/F-09b, l_eff null F-20 | 8 |
| `test_defect_regression.py` | Pins defects F-01, F-07, F-15, F-20, F-22 | 6 |
| `test_pipeline_tools.py` | Pure functions from tools/*.py (flat_name, remap, strip_rev, digest) | 16 |
| `test_latex_integrity.py` | No \rev markup, ref/label integrity, cite keys, F-12/F-18/F-05 repairs | 7 |

**Total: 86 tests**

## Running the Tests

### Full suite
```bash
cd /data/workspace/sgl-time-domain-imaging
python3 -m pytest tests -q
```

### Exclude slow tests (none currently marked slow)
```bash
python3 -m pytest tests -q -m "not slow"
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

- **Fast (< 1s)**: All current tests. No simulation runs required.
- **Slow (> 5s)**: Mark with `@pytest.mark.slow`. None currently.

## Configuration

- `pytest.ini`: Defines the `slow` marker and test paths
- `conftest.py`: Adds `src/` to sys.path for flat imports

## Data Dependencies

Tests read from (but never write to):
- `results/*.npz` (39 shipped archives)
- `results/audit.json`
- `results/targets.json`
- `results/kernel_convergence.json`
- `results/parts/*.npz` (checkpoint files)
- `paper/main.tex`
- `paper/targets_table.tex`
- `tools/*.py` (verification utilities)

## Defect Coverage

The suite pins the following defects from the referee report:

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

- **Full suite**: ~0.8 seconds
- **With -m "not slow"**: ~0.8 seconds (no slow tests currently)
- **Well within 4-minute budget**

## Notes

- All tests are deterministic (no wall-clock or random dependence)
- expcommon.paired_stats uses nboot=20000, seed=42 (bootstrap is seeded)
- Tests use cached objects from results/cache where available
- No tests modify src/, results/, or paper/ (read-only against repository data)
