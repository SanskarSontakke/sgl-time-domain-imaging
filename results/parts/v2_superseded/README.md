# results/parts/v2_superseded/

Checkpoint part files of the **v2 (pre-revision) pipeline**, kept in the
repository only so that the audit trail of what was withdrawn stays inspectable.

They are **not** inputs to anything in the revised suite:

* `src/run_experiments.py` writes and reads its checkpoints as
  `results/parts/v3_<name>.npz` (`expcommon.PART_PREFIX`), so no v3 skip-if-done
  test can ever be satisfied by a file in this directory.
* Before this move the v2 files sat in `results/parts/` under the *bare* names
  (`clouds_f3_s0.npz`, `cad_c2_s1.npz`, `robust_tau.npz`, ...) that the v3 suite
  uses with its prefix. Anyone auditing a number by name could open a v2
  checkpoint and read `gls_pearson = 0.9906` — the superseded 3-node-quadrature,
  approximate-deflation result — and take it for the shipped value. The naming
  collision, not the merge, was the hazard.
* The one script that did read them was `src/make_app_maps.py`, for the demo
  cloud overlay. It now regenerates that overlay from the v3 OU conventions
  instead, so this directory has no consumers at all.

What each group is:

| Files | v2 content | Why superseded |
|---|---|---|
| `clouds_f{0..4}_s{0,1,2}` | 3 seeds per cover, 3-node exposure quadrature, approximate slot deflation | §3 quadrature convergence shows 3 nodes mis-signs the rotational response; the revised sweep uses 16 nodes and 10 seeds (`v3_clouds_*`) |
| `cad_c*_s*`, `cadm_c4_s0_*` | single-arm cadence points, one-method-per-process workers | cadence is now run per resource arm A/B with explicit overheads (`v3_cad_*`) |
| `robust_tau`, `robust_sig`, `robust_prot_{0,1}` | v2 robustness scans | replaced by `robust_clim`, `sigma_sens`, `robust_geom`, `robust_prof` |

Do not add new files here. Regenerate the shipped archives with
`python3 src/run_experiments.py merge`, and note that `results/audit.json`
records which numbers were produced by how many seeds.
