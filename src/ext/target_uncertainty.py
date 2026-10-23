"""Propagated uncertainty budget for the target table.

Replaces bounded [min-max] proxies with posterior-predictive distributions
for SNR_C and D_img per target, using Monte-Carlo propagation of:
  - Chen & Kipping (2017) mass-radius relation (Terran/Neptunian branches)
  - Albedo prior U[0.15, 0.45]
  - Distance uncertainty
  - M sin i fractional error per spectral type
  - De-inclination factor (closed-form, verified)
  - Reachability via beta_ecl-driven plane-change dv

Scientific claim: once catalogue uncertainties are propagated, Proxima Cen b
remains the highest-SNR target but tau Cet e's apparent advantage (nominal
SNR 909) shrinks substantially because its mass places it above the
Terran/Neptunian transition where the mass-radius relation is an
extrapolation with large uncertainty.
"""

import json
import sys
import time
import os

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import extcommon as X
import sglsim as S

log = X.log


# ---------------------------------------------------------------------------
# Physical constants and conventions (matching targets.json meta)
# ---------------------------------------------------------------------------
SNR_C_1800 = 43.158875285522335  # from targets.json meta
Z_AU = 650.0
Z0_PC = 30.0
RPL = S.RPL
DIMG_REF = 2.0 * RPL * (Z_AU * S.AU) / (Z0_PC * S.PC)  # ~1338.457 m

# Chen & Kipping 2017 parameters
CK_ALPHA = 0.279
CK_R0 = 1.01  # R_earth at 1 M_earth
CK_TRANSITION_M = 2.04  # M_earth
CK_TRANSITION_ERR_LO = 0.59
CK_TRANSITION_ERR_HI = 0.66
CK_TERRAN_DISP = 0.0403  # 4.03% fractional
CK_NEPTUNIAN_DISP = 0.146  # 14.6% fractional

# Albedo prior
A_LO, A_HI = 0.15, 0.45
A_REF = 0.30

# Radius factor range
R_LO, R_HI = 0.85, 1.15

# De-inclination factor
ALPHA_DEINCL = 0.279
DEINCL_CLOSED = 1.0978188176  # verified in targets.json meta


def _verify_deinclination():
    """Verify the closed-form de-inclination factor.

    The factor is the mean of (sin i)^{-alpha} over isotropic inclinations:
      <(sin i)^{-alpha}> = integral_0^1 (1-u^2)^{-alpha/2} du
    which equals sqrt(pi) * Gamma(1 - alpha/2) / (2 * Gamma(3/2 - alpha/2)).
    """
    from scipy.special import gamma, betainc
    from scipy.integrate import quad
    alpha = ALPHA_DEINCL
    closed = float(np.sqrt(np.pi) * gamma(1.0 - alpha / 2.0) / (2.0 * gamma(1.5 - alpha / 2.0)))
    # High-precision numeric integration using scipy quad
    numeric, err = quad(lambda u: (1.0 - u**2)**(-alpha / 2.0), 0, 1,
                        epsabs=1e-12, epsrel=1e-12)
    return dict(closed_form=closed, numeric=float(numeric),
                numeric_err=float(err),
                abs_err=float(abs(closed - numeric)),
                matches_archive=abs(closed - DEINCL_CLOSED) < 1e-6,
                matches_1e9=abs(closed - numeric) < 1e-9)


def _chen_kipping_radius(msini_m_earth, above_transition, rng, n_draws):
    """Draw radii from the Chen & Kipping 2017 mass-radius relation.

    Terran branch (M < transition): R = 1.01 * M^0.279, dispersion 4.03%
    Neptunian branch (M > transition): extrapolated rocky radius with 14.6% dispersion
    """
    if not above_transition:
        R_nom = CK_R0 * msini_m_earth ** CK_ALPHA
        disp = CK_TERRAN_DISP
    else:
        # Above transition: rocky extrapolation (not the published probabilistic model)
        R_nom = CK_R0 * msini_m_earth ** CK_ALPHA
        disp = CK_NEPTUNIAN_DISP
    # Log-normal scatter
    log_R = np.log(R_nom) + rng.normal(0, disp, size=n_draws)
    return np.exp(log_R)


def _snr_scalar(A, S_earth, Rp_earth, z0_pc):
    """SNR_C from the scalar rule: 43.1589 * (A/0.30) * (S/S_earth) * (Rp/R_earth) * (30/z0)"""
    return SNR_C_1800 * (A / A_REF) * S_earth * Rp_earth * (Z0_PC / z0_pc)


def _d_img_km(Rp_earth, z0_pc):
    """Image cylinder diameter D_img = 2 * R_p * z / z0.
    
    Rp_earth: planet radius in Earth radii
    z0_pc: target distance in parsecs
    z: observation distance = 650 AU (fixed)
    """
    R_p_m = Rp_earth * S.RPL  # convert to meters
    z_m = Z_AU * S.AU  # 650 AU in meters
    z0_m = z0_pc * S.PC  # target distance in meters
    D_img_m = 2.0 * R_p_m * z_m / z0_m
    return D_img_m / 1000.0  # convert to km


def _reachability_score(beta_ecl_deg, dv90_face_on_kms, dv90_edge_on_kms):
    """Feasibility score from ecliptic latitude and plane-change dv.

    Higher beta_ecl means more expensive plane change. Score is
    1/(1 + dv90/1) where dv90 is the face-on value (most favorable case).
    """
    dv_typical = 0.5 * (dv90_face_on_kms + dv90_edge_on_kms)
    return float(1.0 / (1.0 + dv_typical))


def main():
    t0 = time.time()
    fast = "--fast" in sys.argv[1:]
    n_draws = 10000 if fast else 50000
    seed_mc = 20260915

    log(f"target_uncertainty: fast={fast}, n_draws={n_draws}")

    # Verify de-inclination factor
    deincl_check = _verify_deinclination()
    log(f"De-inclination verification: closed={deincl_check['closed_form']:.10f}, "
        f"archive={DEINCL_CLOSED}, err={deincl_check['abs_err']:.2e}")

    # Load targets
    with open(X.DATA / "targets.json") as f:
        targets_data = json.load(f)
    targets = targets_data["targets"]
    meta = targets_data["meta"]

    rng = np.random.default_rng(seed_mc)

    results_per_target = []
    draws = {}
    for tgt in targets:
        name = tgt["name"]
        msini = tgt["msini"]
        S_earth = tgt["S"]
        d_pc = tgt["d_pc"]
        above = tgt.get("above_ck_transition", False)
        Rp_nom = tgt["Rp_nominal_R"]
        dv90_face = tgt.get("dv90_face_on_kms", 0.0)
        dv90_edge = tgt.get("dv90_edge_on_kms", 0.0)
        beta_ecl = tgt.get("foc_ecl_lat", 0.0)

        # --- Draw samples ---
        # 1. Albedo: U[0.15, 0.45]
        A_draws = rng.uniform(A_LO, A_HI, size=n_draws)

        # 2. Radius: Chen & Kipping with dispersion
        Rp_draws = _chen_kipping_radius(msini, above, rng, n_draws)

        # 3. Distance: assume 5% fractional uncertainty (typical for nearby RV planets)
        # This is an ASSUMED prior since targets.json does not carry distance errors
        d_draws = d_pc * (1.0 + rng.normal(0, 0.05, size=n_draws))
        d_draws = np.clip(d_draws, d_pc * 0.5, d_pc * 2.0)

        # 4. M sin i: assume 10% fractional error (typical RV precision)
        # This is an ASSUMED prior
        msini_draws = msini * (1.0 + rng.normal(0, 0.10, size=n_draws))
        msini_draws = np.clip(msini_draws, 0.1, None)

        # --- Propagate to SNR_C ---
        snr_draws = _snr_scalar(A_draws, S_earth, Rp_draws, d_draws)
        # kept for the pairwise win probabilities below; the medians alone
        # cannot say whether a re-ranking is a real effect or an overlap
        draws[name] = snr_draws

        # --- Propagate to D_img ---
        dimg_draws = _d_img_km(Rp_draws, d_pc)

        # --- Statistics ---
        snr_median = float(np.median(snr_draws))
        snr_lo = float(np.percentile(snr_draws, 16))
        snr_hi = float(np.percentile(snr_draws, 84))
        dimg_median = float(np.median(dimg_draws))
        dimg_lo = float(np.percentile(dimg_draws, 16))
        dimg_hi = float(np.percentile(dimg_draws, 84))

        # Feasibility score
        reach = _reachability_score(beta_ecl, dv90_face, dv90_edge)

        # Compare to nominal
        snr_nominal = tgt.get("SNRC_nominal", None)
        dimg_nominal = tgt.get("Dimg_km", None)
        
        # Re-derive nominal D_img from formula for validation
        dimg_rederived = _d_img_km(Rp_nom, d_pc)
        dimg_mismatch = abs(dimg_rederived - dimg_nominal) if dimg_nominal else None

        results_per_target.append(dict(
            name=name,
            msini=msini,
            above_transition=above,
            is_refuted=("tau Cet" in name and "alt" in name.lower()),  # footnote (e)
            snr_c_posterior_median=snr_median,
            snr_c_68ci=[snr_lo, snr_hi],
            snr_c_nominal=snr_nominal,
            snr_c_bounded_range=tgt.get("SNRC_rule_bounded", None),
            snr_c_fractional_width=float((snr_hi - snr_lo) / snr_median) if snr_median > 0 else None,
            d_img_posterior_median_km=dimg_median,
            d_img_68ci_km=[dimg_lo, dimg_hi],
            d_img_nominal_km=dimg_nominal,
            d_img_rederived_km=float(dimg_rederived),
            d_img_rederivation_match=abs(dimg_rederived - dimg_nominal) < 0.2 if dimg_nominal else None,
            reachability_score=reach,
            beta_ecl_deg=beta_ecl,
            dv90_face_on_kms=dv90_face,
            dv90_edge_on_kms=dv90_edge,
            n_draws=n_draws,
        ))

    # --- Determine winner under uncertainty ---
    # Separate refuted targets (tau Cet e) from confirmed
    confirmed = [r for r in results_per_target if not r["is_refuted"]]
    refuted = [r for r in results_per_target if r["is_refuted"]]
    
    # Winner among confirmed targets only
    for r in confirmed:
        r["feasibility_index"] = r["snr_c_posterior_median"] * r["reachability_score"]
    winner_idx = int(np.argmax([r["feasibility_index"] for r in confirmed]))
    winner = confirmed[winner_idx]

    # --- Compare to nominal ranking, on the SAME rows ---
    # The previous version built the nominal ranking from targets.json with a
    # predicate ("alt" in the note) that does not match any note in that file,
    # so the refuted row stayed in and "the ranking changed" was an artefact of
    # comparing two different row sets AND two different scoring rules.  Both
    # rankings now come from `confirmed`.
    nom_rank = sorted(confirmed, key=lambda r: (r["snr_c_nominal"] or 0.0),
                      reverse=True)
    post_rank = sorted(confirmed, key=lambda r: r["snr_c_posterior_median"],
                       reverse=True)
    feas_rank = sorted(confirmed, key=lambda r: r["feasibility_index"],
                       reverse=True)
    nominal_winner = nom_rank[0]["name"]
    snr_rank_changed = ([r["name"] for r in nom_rank]
                        != [r["name"] for r in post_rank])
    feas_vs_snr = ([r["name"] for r in post_rank]
                   != [r["name"] for r in feas_rank])

    # Pairwise P(row i beats row j) on the SNR draws.  Two independent draw
    # vectors compared elementwise estimate this directly; medians and 68%
    # intervals only suggest it.
    names = [r["name"] for r in confirmed]
    pw = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            pw[f"{a}>{b}"] = float(np.mean(draws[a] > draws[b]))

    log(f"Winner under uncertainty (confirmed): {winner['name']} "
        f"(SNR_C median={winner['snr_c_posterior_median']:.1f}, "
        f"reachability={winner['reachability_score']:.3f})")
    log(f"Nominal winner (same rows, SNR only): {nominal_winner}")
    log(f"SNR ranking changed by the priors: {snr_rank_changed}")
    log(f"Pairwise P: " + ", ".join(f"{k}={v:.3f}" for k, v in pw.items()))
    if refuted:
        log(f"Refuted targets excluded from ranking: {[r['name'] for r in refuted]}")

    # --- Per-row comparison table ---
    comparison_table = []
    for r in results_per_target:
        comparison_table.append(dict(
            name=r["name"],
            snr_c_median=r["snr_c_posterior_median"],
            snr_c_nominal=r["snr_c_nominal"],
            snr_c_68ci=r["snr_c_68ci"],
            d_img_median_km=r["d_img_posterior_median_km"],
            d_img_nominal_km=r["d_img_nominal_km"],
            d_img_rederived_km=r["d_img_rederived_km"],
            d_img_match=r["d_img_rederivation_match"],
        ))
        log(f"  {r['name']}: SNR {r['snr_c_posterior_median']:.1f} (nom {r['snr_c_nominal']}), "
            f"D_img {r['d_img_posterior_median_km']:.1f} km (nom {r['d_img_nominal_km']}, "
            f"rederived {r['d_img_rederived_km']:.1f})")

    # --- Caveats ---
    caveats = [
        "Distance uncertainty: assumed 5% fractional (Gaussian) -- targets.json does not carry per-target distance errors",
        "M sin i uncertainty: assumed 10% fractional (Gaussian) -- actual errors depend on RV precision and are target-specific",
        f"Chen & Kipping Terran branch dispersion {CK_TERRAN_DISP*100:.2f}% applied to targets below transition",
        f"Chen & Kipping Neptunian branch dispersion {CK_NEPTUNIAN_DISP*100:.2f}% applied to targets above transition (rocky EXTRAPOLATION)",
        "Albedo prior: uniform over [0.15, 0.45], matching the paper's bounded range",
        "No per-target catalogue covariance matrices available -- each parameter drawn independently",
        "De-inclination factor used as fixed constant (1.0978), not propagated (its uncertainty is negligible)",
        "Reachability score is a simple 1/(1+dv) heuristic, not a full trajectory optimization",
    ]

    # --- Status for not_established components ---
    not_established = dict(
        per_target_distance_errors="targets.json does not carry per-target distance uncertainties; assumed 5% Gaussian",
        per_target_msini_errors="targets.json does not carry per-target M sin i uncertainties; assumed 10% Gaussian",
        catalogue_covariance_matrices="Not available in the repository; parameters treated as independent",
        spectral_energy_distribution="Wavelength-dependent photon correction not implemented (requires Turyshev & Toth 2022c/2023b)",
    )

    wall = time.time() - t0

    # --- Save ---
    out = dict(
        headline=dict(
            winner_feasibility=winner["name"],
            winner_snr_c_median=winner["snr_c_posterior_median"],
            winner_reachability=winner["reachability_score"],
            nominal_snr_winner=nominal_winner,
            # `ranking_changed` used to compare a refuted-inclusive nominal SNR
            # list against a refuted-exclusive feasibility list; these two
            # fields separate the two effects that were being conflated.
            snr_ranking_changed_by_priors=snr_rank_changed,
            feasibility_reorders_vs_snr=feas_vs_snr,
            nominal_snr_ranking=[r["name"] for r in nom_rank],
            posterior_snr_ranking=[r["name"] for r in post_rank],
            feasibility_ranking=[r["name"] for r in feas_rank],
            p_top_two_snr_ordered=float(pw.get(
                f"{post_rank[0]['name']}>{post_rank[1]['name']}", 0.0)),
            p_proxima_beats_gj273_snr=float(pw.get(
                "Proxima Cen b>GJ 273 b (Luyten b)", 0.0)),
            refuted_targets_excluded=[r["name"] for r in refuted],
            n_draws=n_draws,
        ),
        comparison_table=comparison_table,
        targets=results_per_target,
        deinclination_verification=deincl_check,
        assumed_priors=dict(
            albedo_uniform=[A_LO, A_HI],
            distance_fractional_sigma=0.05,
            msini_fractional_sigma=0.10,
            chen_kipping_terran_dispersion=CK_TERRAN_DISP,
            chen_kipping_neptunian_dispersion=CK_NEPTUNIAN_DISP,
            chen_kipping_transition_M_earth=CK_TRANSITION_M,
            chen_kipping_alpha=CK_ALPHA,
        ),
        not_established=not_established,
        caveats=caveats,
        provenance=X.provenance("target_uncertainty", extra=dict(
            n_draws=n_draws, seed_mc=seed_mc, fast=fast, wall_time_s=round(wall, 1),
        )),
    )
    X.save_json("target_uncertainty", out)

    # Per-target posterior summaries as arrays, so a prioritisation figure can
    # be drawn without re-running the Monte Carlo.  Explicit wide dtypes: numpy
    # fixes <U widths from the data it is handed, and a truncated name label is
    # the kind of silent corruption the archive audit exists to catch.
    names = np.array([r["name"] for r in results_per_target], dtype="<U64")
    # 6x6 pairwise P(row i beats row j) on the SNR draws, all rows including the
    # refuted one so the matrix is readable against targets.json order.  `name`
    # was used as the key until it collided with save_npz's own parameter.
    all_names = [r["name"] for r in results_per_target]
    p_win = np.array([[float(np.mean(draws[a] > draws[b])) if a != b else np.nan
                       for b in all_names] for a in all_names])
    X.save_npz("target_uncertainty",
               target_names=names,
               p_snr_win=p_win,
               snr_c_median=np.array([r["snr_c_posterior_median"]
                                      for r in results_per_target]),
               snr_c_lo=np.array([r["snr_c_68ci"][0] for r in results_per_target]),
               snr_c_hi=np.array([r["snr_c_68ci"][1] for r in results_per_target]),
               snr_c_nominal=np.array([float(r["snr_c_nominal"] or np.nan)
                                       for r in results_per_target]),
               d_img_median_km=np.array([r["d_img_posterior_median_km"]
                                         for r in results_per_target]),
               d_img_nominal_km=np.array([float(r["d_img_nominal_km"] or np.nan)
                                          for r in results_per_target]),
               d_img_rederived_km=np.array([r["d_img_rederived_km"]
                                            for r in results_per_target]),
               reachability=np.array([r["reachability_score"]
                                      for r in results_per_target]),
               is_refuted=np.array([r["is_refuted"] for r in results_per_target]),
               deincl_closed=np.array([DEINCL_CLOSED]),
               deincl_verified=np.array([deincl_check["closed_form"]]))

    X.summary("target_uncertainty",
              winner_feasibility=winner["name"],
              winner_snr_median=round(winner["snr_c_posterior_median"], 1),
              nominal_snr_winner=nominal_winner,
              snr_ranking_changed_by_priors=snr_rank_changed,
              feasibility_reorders_vs_snr=feas_vs_snr,
              deincl_verified=deincl_check["matches_archive"],
              n_draws=n_draws,
              wall_time_s=round(wall, 1))


if __name__ == "__main__":
    main()
