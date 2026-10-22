"""Realistic cloud physics (referee Part VII item 10).

Tests the paper's most important NEGATIVE claim — that rotational
phase-locking defeats cadence gains — against non-OU weather models:
  (a) Markov cloud-STATE field (discrete clear/cloudy/overcast cells)
  (b) Hawkes/self-excited cluster model
  (c) Topographically anchored field (mountain-locked clouds), offset 0.5
  (d) the same anchored field with the offset doubled.  This arm is NOT a
      phase-locking test and used to be labelled ``phase_lock``; the anchor is
      a static offset, so doubling it changes the orographic bias only.

Each model is duck-typed to match CloudModel's interface (.step_to(t),
.opacity()) so it can be passed to simulate_dataset without editing sglsim.py.

WHAT THIS MODULE CAN AND CANNOT SAY
The spine's collapse case (r = 0.144) is produced by ``ExtendedCloudModel``
with ``surf_coupling``: the cloud field's EVOLUTION is locked to the rotating
surface, so the same longitude is cloudy at the same rotational phase and the
per-slot nuisance profiling cannot separate weather from surface.  The
topographically anchored model implemented here is OU noise plus a STATIC
orographic offset: it breaks spatial homogeneity but the field still
decorrelates with tau, so it is NOT the same mechanism and cannot reproduce (or
refute) the collapse.  The honest outputs of this module are therefore
(i) a weather-model sensitivity range for the headline fidelity and (ii) the
statement that the collapse is mechanism-specific.  The archived collapse
reference is read out of ``results/audit.json`` and reported next to these
numbers rather than being re-derived here.

WHY EVERY ARM CARRIES A COVER COLUMN
``sigma_cl`` is the OU-calibrated value and is not recalibrated per model, so
the arms realize different cloud fractions and their absolute ``r`` values are
not matched-weather comparisons.  The final-frame cover of each arm is recorded
alongside ``r`` so the reader can see how much of the spread is weather
structure and how much is simply a different amount of cloud.
"""

import sys
import time
import os

import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.insert(0, os.path.dirname(__file__))
import extcommon as X
import expcommon as E
import sglsim as S

log = X.log

NLATF, NLONF = 72, 144
NLAT, NLON = 36, 72


# =====================================================================
# Cloud model implementations (duck-typed to match CloudModel interface)
# =====================================================================

class MarkovCloudModel:
    """Discrete-state Markov cloud model.

    Each cell is in one of 3 states: clear (0), cloudy (1), overcast (2).
    Transition matrix per timestep:
      P(i->j) depends on current state and spatially correlated noise.
    """

    def __init__(self, nlat, nlon, fc=0.55, tau_days=4.0, corr_deg=12.0,
                 seed=101, transition_rate=0.05):
        self.nlat, self.nlon = nlat, nlon
        self.fc = fc
        self.tau = tau_days * 86400.0
        self.sig_cells = corr_deg / (180.0 / nlat)
        self.rng = np.random.default_rng(seed)
        self.transition_rate = transition_rate
        self.t = 0.0

        # Transition matrix: P[i,j] = P(state i -> state j)
        # States: 0=clear, 1=cloudy, 2=overcast
        # Tuned so stationary distribution matches fc
        p_clear = 1.0 - fc
        p_cloudy = fc * 0.7
        p_overcast = fc * 0.3
        self.T_mat = np.array([
            [1 - transition_rate, transition_rate * 0.7, transition_rate * 0.3],
            [transition_rate * 0.5, 1 - transition_rate, transition_rate * 0.5],
            [transition_rate * 0.3, transition_rate * 0.4, 1 - transition_rate * 0.7],
        ])

        # Initialize state field
        self.state = self._init_state(p_clear, p_cloudy, p_overcast)
        # Spatially correlated noise field
        self.noise = self._fresh_noise()

    def _init_state(self, p_clear, p_cloudy, p_overcast):
        u = self.rng.random((self.nlat, self.nlon))
        state = np.zeros((self.nlat, self.nlon), dtype=int)
        state[u < p_clear] = 0
        state[(u >= p_clear) & (u < p_clear + p_cloudy)] = 1
        state[u >= p_clear + p_cloudy] = 2
        return state

    def _fresh_noise(self):
        f = gaussian_filter(self.rng.standard_normal((self.nlat, self.nlon)),
                            self.sig_cells, mode=("nearest", "wrap"))
        return (f - f.mean()) / (f.std() + 1e-10)

    def step_to(self, t_new, pass_idx=None):
        dt = t_new - self.t
        if dt <= 0:
            return
        # OU-decayed transition rate
        a = np.exp(-dt / self.tau)
        eff_rate = self.transition_rate * (1 - a) + self.transition_rate * a * 0.5
        # Update transition matrix
        T = np.array([
            [1 - eff_rate, eff_rate * 0.7, eff_rate * 0.3],
            [eff_rate * 0.5, 1 - eff_rate, eff_rate * 0.5],
            [eff_rate * 0.3, eff_rate * 0.4, 1 - eff_rate * 0.7],
        ])
        # Transition each cell
        new_noise = self._fresh_noise()
        for s in range(3):
            mask = self.state == s
            u = self.rng.random(mask.shape)
            cumT = np.cumsum(T[s])
            for j in range(3):
                lo = cumT[j - 1] if j > 0 else 0.0
                hi = cumT[j]
                # Spatially modulate transition probability
                thresh = lo + (hi - lo) * (0.5 + 0.3 * new_noise)
                transition = mask & (u >= lo) & (u < hi + 0.3 * new_noise * (hi - lo))
                self.state[transition] = j
        self.noise = new_noise
        self.t = t_new

    def opacity(self):
        # Map states to opacity: clear=0, cloudy=0.5, overcast=0.9
        op = np.zeros((self.nlat, self.nlon))
        op[self.state == 1] = 0.5
        op[self.state == 2] = 0.9
        return op


class HawkesCloudModel:
    """Hawkes/self-excited cloud model.

    Cloud formation is self-exciting: a cloudy cell increases the probability
    of nearby cells becoming cloudy. This creates spatial clustering.
    """

    def __init__(self, nlat, nlon, fc=0.55, tau_days=4.0, corr_deg=12.0,
                 seed=101, excitation=0.3):
        self.nlat, self.nlon = nlat, nlon
        self.fc = fc
        self.tau = tau_days * 86400.0
        self.sig_cells = corr_deg / (180.0 / nlat)
        self.rng = np.random.default_rng(seed)
        self.excitation = excitation
        self.t = 0.0

        # Initialize cloud field
        self.g = self._fresh()
        # Calibrate threshold for target fc
        if fc > 0:
            ens = np.concatenate([self._fresh().ravel() for _ in range(4)])
            self.w = 0.6
            lo, hi = -4.0, 4.0
            for _ in range(60):
                q = 0.5 * (lo + hi)
                cov = np.clip((ens - q) / self.w, 0, 1).mean()
                if cov > fc:
                    lo = q
                else:
                    hi = q
            self.q = 0.5 * (lo + hi)
        else:
            self.q = np.inf

    def _fresh(self):
        f = gaussian_filter(self.rng.standard_normal((self.nlat, self.nlon)),
                            self.sig_cells, mode=("nearest", "wrap"))
        return (f - f.mean()) / f.std()

    def step_to(self, t_new, pass_idx=None):
        dt = t_new - self.t
        if dt <= 0:
            return
        a = np.exp(-dt / self.tau)
        # Self-excitation: cloudy regions boost nearby formation
        op_current = np.clip((self.g - self.q) / self.w, 0.0, 1.0)
        excitation_field = gaussian_filter(op_current, self.sig_cells * 0.5,
                                           mode=("nearest", "wrap"))
        # OU update with excitation
        self.g = a * self.g + np.sqrt(1 - a * a) * self._fresh()
        self.g += self.excitation * (1 - a) * excitation_field
        self.t = t_new

    def opacity(self):
        if self.fc <= 0:
            return np.zeros((self.nlat, self.nlon))
        return np.clip((self.g - self.q) / self.w, 0.0, 1.0)


class TopoAnchoredCloudModel:
    """Topographically anchored cloud model.

    Cloud formation probability is enhanced over high-albedo (land/mountain)
    regions, simulating orographic cloud locking.
    """

    def __init__(self, nlat, nlon, fc=0.55, tau_days=4.0, corr_deg=12.0,
                 seed=101, anchor_strength=0.5, truth_map=None):
        self.nlat, self.nlon = nlat, nlon
        self.fc = fc
        self.tau = tau_days * 86400.0
        self.sig_cells = corr_deg / (180.0 / nlat)
        self.rng = np.random.default_rng(seed)
        self.anchor_strength = anchor_strength
        self.t = 0.0

        # Orographic proxy from truth map
        if truth_map is not None:
            # High albedo = land = enhanced cloud formation
            topo = (truth_map - truth_map.mean()) / (truth_map.std() + 1e-10)
            self.orographic = np.clip(topo * anchor_strength, -1, 1)
        else:
            self.orographic = np.zeros((nlat, nlon))

        # Initialize
        self.g = self._fresh()
        if fc > 0:
            ens = np.concatenate([self._fresh().ravel() for _ in range(4)])
            self.w = 0.6
            lo, hi = -4.0, 4.0
            for _ in range(60):
                q = 0.5 * (lo + hi)
                cov = np.clip((ens - q) / self.w, 0, 1).mean()
                if cov > fc:
                    lo = q
                else:
                    hi = q
            self.q = 0.5 * (lo + hi)
        else:
            self.q = np.inf

    def _fresh(self):
        f = gaussian_filter(self.rng.standard_normal((self.nlat, self.nlon)),
                            self.sig_cells, mode=("nearest", "wrap"))
        return (f - f.mean()) / f.std()

    def step_to(self, t_new, pass_idx=None):
        dt = t_new - self.t
        if dt <= 0:
            return
        a = np.exp(-dt / self.tau)
        self.g = a * self.g + np.sqrt(1 - a * a) * self._fresh()
        # Add orographic enhancement
        self.g += self.orographic * (1 - a) * 0.3
        self.t = t_new

    def opacity(self):
        if self.fc <= 0:
            return np.zeros((self.nlat, self.nlon))
        return np.clip((self.g - self.q) / self.w, 0.0, 1.0)


# =====================================================================
# Main analysis
# =====================================================================

def _run_reconstruction_with_cloud(cloud_model, camp, truthF, truth_c, sgl,
                                    sigma_cl, seed, nsub=16):
    """Run a single reconstruction with a custom cloud model.

    Returns the usual metrics plus ``cover``: the fraction of the cloud field
    counted as cloudy in the final frame of the campaign.  Every arm here is
    driven at the OU-calibrated ``sigma_cl`` and is NOT renormalised to the
    fiducial realized cover, so cover is the variable that actually explains
    the spread between arms; without it the sensitivity range reads as a
    weather-model effect when part of it is an aperture effect.
    """
    dat = S.simulate_dataset(camp, truthF, cloud_model, sgl, seed=seed, nsub=nsub)
    LtL = S.build_laplacian(NLAT, NLON)
    s_hat = S.solve_gls_profiled(
        E.get_F(camp, sgl), dat["y"], camp, dat["sigma"],
        sigma_cl, 4.0, 3e-3, LtL, deflate=True, anchor=True)
    out = S.eval_map(s_hat, truth_c)
    out["cover"] = float(np.mean(cloud_model.opacity() > 0.5))
    return out


def main():
    t0 = time.time()
    fast = "--fast" in sys.argv[1:]
    seeds = X.EXT_SEEDS if fast else X.FULL_SEEDS

    log(f"cloud_physics: fast={fast}, seeds={seeds}")

    # Setup
    camp = E.campaign(ts=1800, mp=16, mode="photons")
    sgl = E.sgl(core="point")
    truthF, truth_c = E.truth(morphology="earthlike", seed=7)

    # Get sigma_cl from archive
    sigma_cl = float(np.load(X.DATA / "parts" / "clouds_f3_s0.npz")["sigma_cl"])
    log(f"sigma_cl = {sigma_cl:.6f}")

    # Get OU reference from archive
    clouds = np.load(X.DATA / "clouds.npz")
    methods = list(clouds["methods"])
    r_ou = clouds["pearson_mat"][methods.index("profiled"), 3, :len(seeds)]
    r_ou_mean = float(r_ou.mean())
    r_ou_se = float(r_ou.std(ddof=1) / np.sqrt(len(r_ou)))
    # The fiducial realized cover, on the same seed slice, so the alternative
    # models below can be compared at matched weather, not just matched sigma_cl.
    cover_ou = float(np.asarray(clouds["covers"], dtype=float)[3, :len(seeds)].mean())
    # The ARCHIVED collapse case lives in audit.robust_clim, not here: read it
    # so the comparison is against the paper's own number rather than a copy of
    # the fiducial run.  (An earlier version of this module re-derived nothing
    # and stored the fiducial run a second time under the name ``r_surf_ou``,
    # which made the archived collapse look like it had been reproduced.)
    import json as _json
    _au = _json.loads((X.DATA / "audit.json").read_text())
    _rc = _au["robust_clim"]
    _surf_key = next((k for k in _rc if "surf" in k.lower()), None)
    archived_surf = _rc[_surf_key] if _surf_key else None
    archived_collapse_r = (((archived_surf or {}).get("pearson") or {}).get("mean"))

    # ------------------------------------------------------------------
    # (a) Markov cloud model
    # ------------------------------------------------------------------
    log("Running Markov cloud model...")
    r_markov = []
    c_markov = []
    for seed in seeds:
        cloud = MarkovCloudModel(NLATF, NLONF, fc=0.55, tau_days=4.0, seed=100 + seed)
        try:
            e = _run_reconstruction_with_cloud(cloud, camp, truthF, truth_c, sgl,
                                                sigma_cl, seed)
            r_markov.append(e["pearson"])
            c_markov.append(e["cover"])
        except Exception as ex:
            log(f"  Markov seed={seed}: failed ({ex})")
    r_markov = np.array(r_markov) if r_markov else np.array([])
    c_markov = np.array(c_markov) if c_markov else np.array([])
    log(f"  Markov: r = {r_markov.mean():.4f} +/- "
        f"{r_markov.std(ddof=1)/np.sqrt(len(r_markov)):.4f}, "
        f"final-frame cover = {c_markov.mean():.4f} (fiducial {cover_ou:.4f})")

    # ------------------------------------------------------------------
    # (b) Hawkes cloud model
    # ------------------------------------------------------------------
    log("Running Hawkes cloud model...")
    r_hawkes = []
    c_hawkes = []
    for seed in seeds:
        cloud = HawkesCloudModel(NLATF, NLONF, fc=0.55, tau_days=4.0, seed=100 + seed)
        try:
            e = _run_reconstruction_with_cloud(cloud, camp, truthF, truth_c, sgl,
                                                sigma_cl, seed)
            r_hawkes.append(e["pearson"])
            c_hawkes.append(e["cover"])
        except Exception as ex:
            log(f"  Hawkes seed={seed}: failed ({ex})")
    r_hawkes = np.array(r_hawkes) if r_hawkes else np.array([])
    c_hawkes = np.array(c_hawkes) if c_hawkes else np.array([])
    if len(r_hawkes) > 1:
        log(f"  Hawkes: r = {r_hawkes.mean():.4f} +/- "
            f"{r_hawkes.std(ddof=1)/np.sqrt(len(r_hawkes)):.4f}, "
            f"final-frame cover = {c_hawkes.mean():.4f}")
    else:
        log(f"  Hawkes: r = {r_hawkes.mean():.4f}")

    # ------------------------------------------------------------------
    # (c) Topographically anchored cloud model
    # ------------------------------------------------------------------
    log("Running topographically anchored cloud model...")
    # Coarsen truth map for orographic proxy
    truth_c_full = truthF  # fine grid
    r_topo = []
    c_topo = []
    for seed in seeds:
        cloud = TopoAnchoredCloudModel(NLATF, NLONF, fc=0.55, tau_days=4.0,
                                        seed=100 + seed, anchor_strength=0.5,
                                        truth_map=truth_c_full)
        try:
            e = _run_reconstruction_with_cloud(cloud, camp, truthF, truth_c, sgl,
                                                sigma_cl, seed)
            r_topo.append(e["pearson"])
            c_topo.append(e["cover"])
        except Exception as ex:
            log(f"  Topo seed={seed}: failed ({ex})")
    r_topo = np.array(r_topo) if r_topo else np.array([])
    c_topo = np.array(c_topo) if c_topo else np.array([])
    log(f"  Topo: r = {r_topo.mean():.4f} +/- "
        f"{r_topo.std(ddof=1)/np.sqrt(len(r_topo)):.4f}, "
        f"final-frame cover = {c_topo.mean():.4f}")

    # ------------------------------------------------------------------
    # (d) Same anchored model with the offset doubled.
    # ------------------------------------------------------------------
    # This arm used to be called ``phase_lock``. It is not one: the anchor here
    # is a STATIC offset added to a decorrelating OU field, so nothing rotates
    # with the planet. Doubling it only strengthens the orographic bias, which
    # is a legitimate arm to measure but cannot reproduce or refute the spine's
    # surface-coupled collapse.
    log("Running strong-anchor arm (static orographic offset x2)...")
    r_anchor = []
    c_anchor = []
    for seed in seeds:
        cloud = TopoAnchoredCloudModel(NLATF, NLONF, fc=0.55, tau_days=4.0,
                                        seed=100 + seed, anchor_strength=1.0,
                                        truth_map=truth_c_full)
        try:
            e = _run_reconstruction_with_cloud(cloud, camp, truthF, truth_c, sgl,
                                                sigma_cl, seed)
            r_anchor.append(e["pearson"])
            c_anchor.append(e["cover"])
        except Exception as ex:
            log(f"  strong-anchor seed={seed}: failed ({ex})")
    r_anchor = np.array(r_anchor) if r_anchor else np.array([])
    c_anchor = np.array(c_anchor) if c_anchor else np.array([])
    log(f"  strong-anchor: r = {np.mean(r_anchor):.4f}, "
        f"final-frame cover = {np.mean(c_anchor):.4f}")

    wall = time.time() - t0

    # ------------------------------------------------------------------
    # Paired statistics vs OU reference
    # ------------------------------------------------------------------
    def _paired(x, y_ref):
        n = min(len(x), len(y_ref))
        if n < 2:
            return dict(delta=float("nan"), se=float("nan"), p_sign=float("nan"))
        d = x[:n] - y_ref[:n]
        return dict(
            delta_r=float(d.mean()),
            se=float(d.std(ddof=1) / np.sqrt(n)),
            n=n,
        )

    paired_markov = _paired(r_markov, r_ou)
    paired_hawkes = _paired(r_hawkes, r_ou)
    paired_topo = _paired(r_topo, r_ou)
    paired_anchor = _paired(r_anchor, r_ou)

    # ------------------------------------------------------------------
    # Does any arm reach the ARCHIVED collapse?
    # ------------------------------------------------------------------
    # The spine's surface-coupled case sits at audit.robust_clim.surf. An arm
    # "reproduces" it only if it lands near that level AND loses a comparable
    # amount against its own OU reference. Being merely below the OU mean is a
    # different weather model, not a collapse.
    collapse_reproduced = bool(
        len(r_anchor) and archived_collapse_r is not None
        and r_anchor.mean() < archived_collapse_r + 0.05
        and (r_anchor.mean() - r_ou_mean) < -0.05)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    npz_data = dict(
        r_markov=r_markov,
        r_hawkes=r_hawkes,
        r_topo=r_topo,
        r_anchor_strong=r_anchor,
        r_ou_ref=r_ou,
        cover_markov=c_markov,
        cover_hawkes=c_hawkes,
        cover_topo=c_topo,
        cover_anchor_strong=c_anchor,
    )
    X.save_npz("cloud_physics", **{k: v for k, v in npz_data.items() if v.size > 0})

    caveats = [
        "Markov model uses simplified 3-state transition matrix; real cloud physics is more complex",
        "Hawkes excitation parameter (0.3) is assumed; not calibrated to Earth data",
        "Topographic anchor uses albedo as proxy for orography; real mountains have different signatures",
        "sigma_cl is the OU-calibrated value and is NOT recalibrated per model, so the "
        f"realized final-frame cover differs by arm (OU {cover_ou:.4f}, Markov "
        f"{np.mean(c_markov):.4f}, Hawkes {np.mean(c_hawkes):.4f}, topo "
        f"{np.mean(c_topo):.4f}, strong anchor {np.mean(c_anchor):.4f}); absolute r "
        "across arms is therefore a sensitivity range, not a controlled A/B test",
        "Each model runs simulate_dataset independently; cloud fields are not shared across models",
        "The anchored arm is OU noise plus a STATIC orographic offset; it has no "
        "rotational phase locking, so it neither reproduces nor refutes the spine's "
        "surf_coupling collapse case (read from audit.robust_clim instead)",
        f"{len(seeds)} noise seeds; the collapse reference is the spine's 10-seed "
        "ensemble, so the two are not paired",
    ]
    if len(r_hawkes) < len(seeds):
        caveats.append(f"Hawkes model failed for {len(seeds) - len(r_hawkes)} seeds")

    out = dict(
        headline=dict(
            status=("weather_model_sensitivity_range;_archived_collapse_not_reached"
                    if not collapse_reproduced else
                    "archived_collapse_reproduced"),
            collapse_reproduced=collapse_reproduced,
            r_ou_mean=r_ou_mean,
            r_ou_se=r_ou_se,
            cover_ou=round(cover_ou, 4),
            r_markov_mean=(float(r_markov.mean()) if len(r_markov) else None),
            cover_markov=(round(float(np.mean(c_markov)), 4) if len(c_markov) else None),
            r_hawkes_mean=(float(r_hawkes.mean()) if len(r_hawkes) else None),
            cover_hawkes=(round(float(np.mean(c_hawkes)), 4) if len(c_hawkes) else None),
            r_topo_mean=(float(r_topo.mean()) if len(r_topo) else None),
            cover_topo=(round(float(np.mean(c_topo)), 4) if len(c_topo) else None),
            r_anchor_strong_mean=(float(r_anchor.mean()) if len(r_anchor) else None),
            cover_anchor_strong=(round(float(np.mean(c_anchor)), 4)
                                 if len(c_anchor) else None),
            delta_r_markov_vs_ou=paired_markov.get("delta_r", None),
            delta_r_hawkes_vs_ou=paired_hawkes.get("delta_r", None),
            delta_r_topo_vs_ou=paired_topo.get("delta_r", None),
            delta_r_anchor_strong_vs_ou=paired_anchor.get("delta_r", None),
            archived_collapse_r=archived_collapse_r,
        ),
        markov=dict(
            r_per_seed=r_markov.tolist(),
            r_mean=(float(r_markov.mean()) if len(r_markov) else None),
            r_se=float(r_markov.std(ddof=1) / np.sqrt(len(r_markov))) if len(r_markov) > 1 else 0.0,
            cover_per_seed=c_markov.tolist(),
            paired_vs_ou=paired_markov,
        ),
        hawkes=dict(
            r_per_seed=r_hawkes.tolist(),
            r_mean=(float(r_hawkes.mean()) if len(r_hawkes) else None),
            r_se=float(r_hawkes.std(ddof=1) / np.sqrt(len(r_hawkes))) if len(r_hawkes) > 1 else 0.0,
            cover_per_seed=c_hawkes.tolist(),
            paired_vs_ou=paired_hawkes,
        ),
        topo_anchored=dict(
            r_per_seed=r_topo.tolist(),
            r_mean=(float(r_topo.mean()) if len(r_topo) else None),
            r_se=float(r_topo.std(ddof=1) / np.sqrt(len(r_topo))) if len(r_topo) > 1 else 0.0,
            cover_per_seed=c_topo.tolist(),
            paired_vs_ou=paired_topo,
        ),
        strong_anchor_arm=dict(
            note=("static orographic offset doubled; NOT a phase-locking test",),
            r_per_seed=r_anchor.tolist(),
            r_mean=(float(r_anchor.mean()) if len(r_anchor) else None),
            cover_per_seed=c_anchor.tolist(),
            paired_vs_ou=paired_anchor,
            collapse_reproduced=collapse_reproduced,
        ),
        ou_reference=dict(
            r_per_seed=r_ou.tolist(),
            r_mean=r_ou_mean,
            r_se=r_ou_se,
            cover_mean=cover_ou,
        ),
        # The paper's collapse case, quoted from the archive rather than
        # re-derived: the models above cannot reach it.
        archived_collapse_reference=dict(
            source="results/audit.json:robust_clim." + str(_surf_key),
            r_mean=(((archived_surf or {}).get("pearson") or {}).get("mean")),
            r_se=(((archived_surf or {}).get("pearson") or {}).get("se")),
            n_seeds=(archived_surf or {}).get("n_seeds"),
        ),
        caveats=caveats,
        provenance=X.provenance("cloud_physics", extra=dict(
            seeds_used=seeds, fast=fast, wall_time_s=round(wall, 1),
        )),
    )
    X.save_json("cloud_physics", out)
    X.summary("cloud_physics",
              collapse_reproduced=collapse_reproduced,
              r_ou=r_ou_mean,
              r_markov=float(r_markov.mean()),
              r_hawkes=float(r_hawkes.mean()),
              r_topo=float(r_topo.mean()),
              r_anchor_strong=float(r_anchor.mean()),
              wall_time_s=round(wall, 1))


if __name__ == "__main__":
    main()
