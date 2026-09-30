"""Target list for an SGL imaging mission: nearest confirmed temperate planets
plus one solar-type RV candidate, with focal-line placements, image-plane
geometry/dynamics and an EXPLICITLY DEFINED nominal photon proxy.

Rewritten for the revised manuscript (referee comments 10 / R27-R29).  The v2
version of this file presented its output as a propagated uncertainty table and
the numbers did not survive reproduction:

  * the radii were (M sin i)^0.28 with NO inclination adjustment, while the
    text claimed <1/sin i> = 1.27 had been applied (and 1.27 is in fact
    1/E[sin i], which is not the same operation);
  * the stated 15% "intrinsic dispersion" is not the Terran-branch value of
    Chen & Kipping (2017), which is ~4.03% for R propto M^0.279 (14.6% is their
    NEPTUNIAN branch);
  * the SNR brackets were neither the [0.425, 1.725] implied by the quoted
    albedo/radius ranges nor any stated distribution (they were ~1.875x nominal
    on top and 0.425x below);
  * the tracking budget used a scalar acc x 90 d with an "eccentricity
    uncertainty" of 2 e x Delta v, which is not a projection.

This module now separates three things that must not be conflated:

  1. NOMINAL PROXY  -- equation (R27) of the referee report, a bolometric scalar
     scaling, stated as a rule with its reference point.  It is not a
     wavelength-integrated photon forecast; that would need the spectral SGL
     treatment (Turyshev & Toth 2022c, PRD 106 044059; Turyshev & Toth 2023b,
     PRD 107 104063).
  2. GEOMETRIC DE-INCLINATION FACTORS -- conditional, closed-form, isotropic
     inclinations, fixed minimum mass, single power-law branch.  Computed here
     exactly (mean 1.0978 for alpha = 0.279; the referee's 1.0982 is alpha =
     0.28), together with median and 95th-percentile factors, and labelled as
     NOT a posterior.
  3. TRACKING -- the face-on circular magnitude (R29) and the edge-on average
     reduction 2/pi, with the eccentric anomaly sampled over the actual window
     instead of an invented error bar.

Writes ../results/targets.json, ../paper/figures/fig_targets.pdf and
../paper/targets_table.tex.
"""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sglsim as S

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
EPS = np.deg2rad(23.43928)   # obliquity J2000
Z = 650.0 * S.AU

# ----------------------------------------------------------------------
# mass-radius relation: Chen & Kipping (2017) Terran branch
# ----------------------------------------------------------------------
CK_ALPHA = 0.279             # R / R_earth = C * (M / M_earth)^0.279
CK_C = 1.01                  # Terran-branch normalisation
CK_SIGMA_TERRAN = 0.0403     # intrinsic dispersion of the TERRAN branch (4.03%)
CK_SIGMA_NEPTUNIAN = 0.146   # quoted here only to show what 15% actually is
CK_TRANSITION = 2.04         # M_earth, nominal branch transition
CK_TRANS_ERR = (0.59, 0.66)  # -0.59 / +0.66

# ----------------------------------------------------------------------
# nominal proxy (referee eq. R27).  SNR_C for a z0 = 30 pc, S = S_earth,
# A = 0.30, Rp = R_earth planet at 1800 s with the background of sglsim.
# ----------------------------------------------------------------------
SNR_C_1800 = float(1.0 / S.noise_sigma(1.0, 1800.0))     # 43.1589
ALBEDO_RANGE = (0.15, 0.45)     # bounded, uniform-in-range assumption
RADIUS_FACTOR_RANGE = (0.85, 1.15)   # +-1 sigma of the Terran branch is 4.03%;
                                     # +-15% is the adopted CONSERVATIVE allowance
                                     # (see the note in the tex table)


def nominal_snr(inst, rp, dpc, albedo=0.30):
    """eq. R27 as a literal function: SNR scales as A * S * Rp / z0 relative to
    the 30 pc, S_earth, A = 0.30, R_earth reference."""
    return (SNR_C_1800 * (albedo / 0.30) * inst * rp * (30.0 / dpc))


def deinclination_factors(alpha=CK_ALPHA):
    """Conditional isotropic-orientation factors for R/R_min = (sin i)^-alpha.

    cos i is uniform on [0, 1].  With u = cos i, sin i = (1 - u^2)^(1/2) and

        E[(sin i)^-alpha] = int_0^1 (1 - u^2)^(-alpha/2) du
                          = (1/2) B(1/2, 1 - alpha/2)
                          = sqrt(pi) Gamma(1 - alpha/2) / (2 Gamma(3/2 - alpha/2)),

    finite for alpha < 1; for alpha = 0.279 it is 1.0978 (the referee's 1.0982
    corresponds to alpha = 0.28).  1/E[sin i]^alpha = (pi/4)^-alpha = 1.070 is a
    DIFFERENT number (mean of the ratio vs ratio of the means) and is reported
    only to show the difference.  These are geometric ratios conditional on a
    fixed minimum mass and a single power-law branch -- NOT a posterior: an RV
    mass prior, selection effects, branch transitions and measurement errors all
    change them.
    """
    from scipy.special import gamma
    from scipy.integrate import quad

    closed = np.sqrt(np.pi) * gamma(1.0 - alpha / 2.0) / (
        2.0 * gamma(1.5 - alpha / 2.0))
    # numerical check of the same integral over u = cos i ~ U(0,1)
    mean_num, err = quad(lambda u: (1.0 - u * u) ** (-alpha / 2.0), 0.0, 1.0,
                         limit=400)
    # percentile factors: f = (sin i)^-alpha is DECREASING in sin i and
    # P(sin i <= s) = 1 - sqrt(1 - s^2), so P(f <= x) = (1 - x^(-2/alpha))^(1/2)
    # and the q-th percentile of the FACTOR is (sqrt(1 - q^2))^-alpha.  The
    # large-tail values come from face-on-ish orbits, i.e. small sin i.
    def pf(q):
        return (np.sqrt(1.0 - q * q)) ** (-alpha)
    return dict(alpha=float(alpha), mean=float(closed),
                mean_numeric=float(mean_num), numeric_abs_err=float(err),
                naive_inv_mean_sine=float((np.pi / 4.0) ** (-alpha)),
                median=float(pf(0.5)), p95=float(pf(0.95)),
                p99=float(pf(0.99)),
                note=("mean of the RATIO, not ratio of the means; the mean "
                      "diverges for alpha >= 1"))


def kepler_E(M, e, tol=1e-13, itmax=100):
    """Eccentric anomaly from mean anomaly, vectorised Newton solve."""
    M = np.asarray(M, float)
    E = M + e * np.sin(M)
    for _ in range(itmax):
        f = E - e * np.sin(E) - M
        dE = f / (1.0 - e * np.cos(E))
        E = E - dE
        if np.max(np.abs(dE)) < tol:
            break
    return E


def transverse_accel(e, M, a_m, GM, cos_i):
    """Sky-plane (transverse) acceleration magnitude at mean anomaly M.

    Orbital plane with node and periastron both along the sky x-axis (no loss of
    generality: the line of sight fixes z, and a rotation about it is free):
        x = a (cos E - e),  y = a sqrt(1-e^2) sin E,  r = a (1 - e cos E),
        a_vec = -GM (x, y) / r^3,
    and the sky components are (a_x, a_y cos i).  Checks: i = 0 gives GM/r^2
    exactly (the full acceleration is transverse); i = 90 deg, e = 0 gives
    (GM/a^2)|cos E|, whose orbit average is 2/pi of the face-on value -- the
    factor the referee's eq. R29 discussion quotes.
    """
    M = np.asarray(M, float) % (2 * np.pi)
    E = kepler_E(M, e)
    s = np.sqrt(max(1.0 - e * e, 0.0))
    a0 = GM / a_m ** 2                            # circular-orbit acceleration
    d3 = (1.0 - e * np.cos(E)) ** 3
    ax = -a0 * (np.cos(E) - e) / d3
    ay = -a0 * s * np.sin(E) / d3
    return np.hypot(ax, ay * cos_i)


def tracking(e, P_s, a_m, ratio, T=90.0 * 86400.0, nph=480, nstep=1440):
    """Transverse velocity BUDGET over a window T, by explicit projection.

    v2 quoted acc x T with an "uncertainty" of 2 e x (acc x T), which is neither
    a projection nor a propagation.  Here:

      * dv_face_on_ref = the face-on circular magnitude of eq. R29,
        (4 pi^2 a / P^2) T (z/z0) -- the reference value, reported separately;
      * face_on / edge_on = integral of the PROJECTED transverse acceleration
        magnitude over the window, averaged over the starting mean anomaly, with
        the starting-phase range as an explicit min/max.  For e = 0 the face-on
        value reproduces R29 and the edge-on value is 2/pi of it, which is the
        reduction the referee's eq. R29 discussion states;
      * the acceleration quoted is the physical (target-system) mean magnitude,
        and the velocity is the image-plane value after multiplying by ratio.

    This is a continuous-thrust velocity BUDGET (the time-integral of the
    magnitude the formation must cancel), not the net Keplerian velocity change
    over T, which for T >> P stays bounded by 2 v_orb and does not accumulate.
    """
    GM = 4 * np.pi ** 2 * a_m ** 3 / P_s ** 2
    a_circ = GM / a_m ** 2                       # circular orbit acceleration
    dv_face_ref = a_circ * T * ratio
    dt = T / nstep                               # step in SECONDS
    out = {}
    for tag, cos_i in (("face_on", 1.0), ("edge_on", 0.0)):
        dw = np.empty(nph)
        a_ph = np.empty(nph)
        for k in range(nph):
            M = 2 * np.pi * k / nph + np.linspace(0.0, 2 * np.pi * T / P_s, nstep)
            at = transverse_accel(e, M, a_m, GM, cos_i)
            dw[k] = np.trapezoid(at, dx=dt) * ratio
            a_ph[k] = dw[k] / (T * ratio)
        out[tag] = dict(dv_kms=float(dw.mean() / 1e3),
                        dv_min_kms=float(dw.min() / 1e3),
                        dv_max_kms=float(dw.max() / 1e3),
                        accel_uu_ms2=float(a_ph.mean() * 1e6))
    return dict(dv_face_on_ref_kms=float(dv_face_ref / 1e3),
                edge_on_over_face=float(out["edge_on"]["dv_kms"] /
                                        max(out["face_on"]["dv_kms"], 1e-30)),
                edge_on_factor_theory=2.0 / np.pi,
                window_days=float(T / 86400.0),
                face_on=out["face_on"], edge_on=out["edge_on"])


# name, host, SpT, dist_pc, RA(h), Dec(deg), Msini(ME), P(d), a(AU), S(S_earth), note, ecc
# Inputs are quoted from the discovery/validation literature as in v2; the
# revision changes what is DONE with them, not the catalogue itself.
TARGETS = [
 ("Proxima Cen b","Proxima Centauri","M5.5V",1.301,14+29.7/60,-(62+41/60.),1.07,11.19,0.04857,0.65,"closest; ESPRESSO-confirmed",0.11),
 ("Ross 128 b","Ross 128","M4V",3.375,11+47.7/60,0+48/60.,1.35,9.87,0.0496,1.38,"quiet host; near inner CHZ",0.12),
 ("GJ 1061 d","GJ 1061","M5.5V",3.67,3+36.0/60,-(44+31/60.),1.64,13.03,0.054,0.69,"temperate; compact multi-planet",0.06),
 ("Teegarden c","Teegarden's Star","M7V",3.831,2+53.0/60,16+53/60.,1.11,11.41,0.0443,0.37,"conservative HZ; low-flare host",0.04),
 ("GJ 273 b (Luyten b)","GJ 273","M3.5V",3.80,7+27.4/60,5+14/60.,2.89,18.65,0.0911,1.06,"near inner CHZ edge",0.10),
 ("tau Cet e (alt.)","tau Ceti","G8.5V",3.603,1+44.1/60,-(15+56/60.),3.93,162.9,0.538,1.71,"RV signal refuted (Figueira+ 25); illustrative dynamics row only",0.18),
]

DEI = deinclination_factors()
rows = []
for (nm, host, spt, dpc, ra, dec, msini, P, a_au, inst, note, ecc) in TARGETS:
    z0 = dpc * S.PC
    ratio = Z / z0
    above = msini > CK_TRANSITION
    # nominal-proxy radius: minimum mass treated AS the mass (no de-inclination
    # correction is folded into the nominal value), Terran-branch power law,
    # extrapolated where the minimum mass already exceeds the branch transition.
    Rp = CK_C * msini ** CK_ALPHA
    # photon rate at the reference albedo A = 0.30 (QEXO is defined for A = 0.30,
    # S = 1, Rp = 1 R_earth at z0 = 30 pc), scaled by S, Rp and 30 pc / z0.
    Q = S.QEXO * inst * Rp * (30.0 / dpc)
    # Two SNR numbers, deliberately kept side by side: the exact count SNR with
    # the sglsim coronal background at 1800 s, and the background-limited scalar
    # rule of eq. R27.  QCOR >> Q for every target here, so they agree to
    # rounding -- which is the reproduction check the referee asked to be made
    # explicit rather than left to the reader.
    snr_exact = float(Q * 1800.0 / np.sqrt((S.QCOR + Q) * 1800.0))
    snr_nom = nominal_snr(inst, Rp, dpc)
    # bounded bracket implied by eq. R27 alone over the stated albedo x radius
    # ranges; a product of two bounded ranges, NOT a confidence interval.
    snr_rule_lo = snr_nom * (ALBEDO_RANGE[0] / 0.30) * RADIUS_FACTOR_RANGE[0]
    snr_rule_hi = snr_nom * (ALBEDO_RANGE[1] / 0.30) * RADIUS_FACTOR_RANGE[1]

    Dimg = 2 * Rp * S.RPL * ratio
    a_m = a_au * S.AU
    Ps = P * 86400.0
    r_img = a_m * ratio
    v_img = 2 * np.pi * a_m / Ps * ratio

    trk = tracking(ecc, Ps, a_m, ratio)
    trk30 = tracking(ecc, Ps, a_m, ratio, T=30.0 * 86400.0)
    raf = (ra + 12.0) % 24.0

    def ecl_lat(ra_h, dec_d):
        A = np.deg2rad(ra_h * 15.0)
        D = np.deg2rad(dec_d)
        sb = np.sin(D) * np.cos(EPS) - np.cos(D) * np.sin(EPS) * np.sin(A)
        return float(np.rad2deg(np.arcsin(sb)))

    rows.append(dict(
        name=nm, host=host, spt=spt, d_pc=dpc, ra_h=ra, dec_d=dec,
        msini=msini, P_d=P, a_au=a_au, S=inst, ecc=ecc, note=note,
        above_ck_transition=bool(above),
        Rp_nominal_R=round(float(Rp), 3),
        Rp_terr_1sigma_R=round(float(Rp * CK_SIGMA_TERRAN), 3),
        Rp_deincl_mean=round(float(Rp * DEI["mean"]), 3),
        Rp_deincl_median=round(float(Rp * DEI["median"]), 3),
        Rp_deincl_p95=round(float(Rp * DEI["p95"]), 3),
        Dimg_km=round(Dimg / 1e3, 1),
        pix64_m=round(Dimg / 64, 2),
        # photon rate at the reference albedo A = 0.30 (QEXO is defined for
        # A = 0.30, S = 1, Rp = 1 R_earth at 30 pc), so no extra albedo factor.
        Qexo=float(f"{Q:.3g}"),
        SNRC_nominal=round(float(snr_nom), 1),
        SNRC_exact=round(snr_exact, 1),
        SNRC_rule_bounded=[round(float(snr_rule_lo), 1), round(float(snr_rule_hi), 1)],
        foc_ra_h=round(raf, 3),
        foc_dec_d=round(-dec, 3),
        foc_ecl_lat=round(ecl_lat(raf, -dec), 1),
        r_img_km=round(r_img / 1e3, 1),
        v_img_ms=round(v_img, 1),
        dv90_face_on_ref_kms=round(trk["dv_face_on_ref_kms"], 2),
        dv90_face_on_kms=round(trk["face_on"]["dv_kms"], 2),
        dv90_face_on_range_kms=[round(trk["face_on"]["dv_min_kms"], 2),
                                round(trk["face_on"]["dv_max_kms"], 2)],
        dv90_edge_on_kms=round(trk["edge_on"]["dv_kms"], 2),
        dv90_edge_on_range_kms=[round(trk["edge_on"]["dv_min_kms"], 2),
                                round(trk["edge_on"]["dv_max_kms"], 2)],
        edge_on_over_face=round(trk["edge_on_over_face"], 4),
        dv30_face_on_kms=round(trk30["face_on"]["dv_kms"], 2),
        accel_uu_ms2=round(trk["face_on"]["accel_uu_ms2"], 1),
    ))

meta = dict(
    conventions=dict(
        snr_rule=("SNR_C = %.4f * (A/0.30) * (S/S_earth) * (Rp/R_earth) * "
                  "(30 pc / z0)" % SNR_C_1800),
        snr_c_1800=SNR_C_1800, ts_s=1800.0, d_tel_m=S.DTEL, lambda_um=1.0,
        z_au=650.0, qcor=S.QCOR, qexo_ref=S.QEXO,
        albedo_range=list(ALBEDO_RANGE),
        radius_factor_range=list(RADIUS_FACTOR_RANGE),
        intrinsic_dispersion_percent=dict(
            terran_branch=100 * CK_SIGMA_TERRAN,
            neptunian_branch=100 * CK_SIGMA_NEPTUNIAN,
            adopted_allowance_percent=15.0,
            transition_M_earth=CK_TRANSITION,
            transition_err_M_earth=list(CK_TRANS_ERR)),
        mass_radius=dict(model="Chen & Kipping 2017 Terran branch",
                         R_over_Rearth=CK_C, alpha=CK_ALPHA),
    ),
    deinclination=DEI,
    disclaimer=("Nominal proxies only.  eq. R27 is a bolometric scalar, not a "
                "wavelength-integrated photon forecast (that needs the spectral "
                "SGL treatment, Turyshev & Toth 2022c PRD 106 044059; "
                "Turyshev & Toth 2023b PRD 107 104063).  "
                "De-inclination factors are conditional geometric ratios at "
                "fixed minimum mass on a single branch, not a posterior; radii "
                "above the 2.04 M_earth Terran/Neptunian transition are rocky "
                "EXTRAPOLATIONS, not the published probabilistic model.  The "
                "albedo x radius brackets are bounded intervals over stated "
                "ranges and carry no confidence level."),
)

(OUT / "results" / "targets.json").write_text(
    json.dumps(dict(meta=meta, targets=rows), indent=1))

print(f"de-inclination (alpha={CK_ALPHA}): mean {DEI['mean']:.4f} "
      f"(numeric {DEI['mean_numeric']:.4f} +- {DEI['numeric_abs_err']:.0e}), "
      f"median {DEI['median']:.4f}, p95 {DEI['p95']:.4f}, p99 {DEI['p99']:.4f}; "
      f"1/E[sin i]^a = {DEI['naive_inv_mean_sine']:.4f}")
for r in rows:
    print(f"{r['name']:22s} Rp={r['Rp_nominal_R']:.3f} D={r['Dimg_km']:6.1f}km "
          f"Q={r['Qexo']:.3g} SNR={r['SNRC_nominal']:6.1f} (exact {r['SNRC_exact']:.1f}) "
          f"rule {r['SNRC_rule_bounded'][0]:.0f}-{r['SNRC_rule_bounded'][1]:.0f}  "
          f"dv90 face {r['dv90_face_on_kms']:.2f} [{r['dv90_face_on_range_kms'][0]:.2f},"
          f"{r['dv90_face_on_range_kms'][1]:.2f}] edge {r['dv90_edge_on_kms']:.2f} "
          f"(R29 ref {r['dv90_face_on_ref_kms']:.2f}) ratio e/f "
          f"{r['edge_on_over_face']:.4f}  "
          f"{'[above CK transition]' if r['above_ck_transition'] else ''}")

# ---------------------------------------------------------------- figures ----
plt.rcParams.update({"font.size": 8.5, "font.family": "serif",
                     "savefig.bbox": "tight"})
fig = plt.figure(figsize=(7.0, 3.6))
ax = fig.add_subplot(111, projection="mollweide")


def towrap(ra_h):
    x = np.deg2rad(ra_h * 15.0)
    return np.where(x > np.pi, x - 2 * np.pi, x)


for r in rows[:5]:
    xt, yt = towrap(r["ra_h"]), np.deg2rad(r["dec_d"])
    xf, yf = towrap(r["foc_ra_h"]), np.deg2rad(r["foc_dec_d"])
    ax.plot(xt, yt, "o", color="#0173b2", ms=5)
    ax.plot(xf, yf, "*", color="#d55e00", ms=10)
    lab = r["name"].split(" (")[0]
    ax.annotate(lab, (xt, yt), textcoords="offset points", xytext=(4, 4), fontsize=7)
    ax.annotate(lab + " focus", (xf, yf), textcoords="offset points", xytext=(4, -9),
                fontsize=7, color="#a04000")

rc = rows[5]
xt, yt = towrap(rc["ra_h"]), np.deg2rad(rc["dec_d"])
xf, yf = towrap(rc["foc_ra_h"]), np.deg2rad(rc["foc_dec_d"])
ax.plot(xt, yt, "s", color="#029e73", ms=4, mfc="none")
ax.plot(xf, yf, "^", color="#cc79a7", ms=7, mfc="none")
ax.annotate("tau Cet e (refuted)", (xt, yt), textcoords="offset points", xytext=(4, 4),
            fontsize=6.5, color="#029e73")

lam = np.linspace(0, 2 * np.pi, 361)
ra_e = np.arctan2(np.sin(lam) * np.cos(EPS), np.cos(lam))
de_e = np.arcsin(np.sin(EPS) * np.sin(lam))
o = np.argsort(((ra_e + 2 * np.pi) % (2 * np.pi)))
xe = np.where(ra_e > np.pi, ra_e - 2 * np.pi, ra_e)
ax.plot(xe[o], de_e[o], "-", color="0.7", lw=0.8, label="ecliptic plane")

ax.plot([], [], "o", color="#0173b2", label="confirmed target planet")
ax.plot([], [], "*", color="#d55e00", label="SGL focal direction (650 AU)")
ax.plot([], [], "s", color="#029e73", mfc="none", label="solar-type candidate")
ax.legend(loc="lower right", fontsize=6.5, frameon=False)
ax.grid(alpha=0.3, lw=0.4)
ax.set_xticklabels(["14h", "16h", "18h", "20h", "22h", "0h", "2h", "4h", "6h",
                    "8h", "10h"], fontsize=7)
fig.savefig(OUT / "paper" / "figures" / "fig_targets.pdf")

# ------------------------------------------------------------------ table ----
lines = [
    "% Generated by src/targets.py -- do not edit by hand.",
    "% Nominal-proxy table (referee comment 10).  Intervals are bounded ranges",
    "% over the stated albedo and radius-factor assumptions, NOT confidence",
    "% levels; rows marked (a) have M sin i above the Chen & Kipping (2017)",
    "% Terran/Neptunian transition and use a rocky extrapolation.",
    r"\begin{table*}[t]",
    r"\centering",
    r"\caption{\rev{Nearest confirmed temperate planets (plus one solar-type RV",
    r"signal whose planet interpretation has since been refuted) as SGL imaging",
    r"targets -- explicitly a \emph{nominal-proxy} ",
    r"table, not a propagated uncertainty budget.  Radii use the Chen \&",
    r"Kipping (2017) Terran branch $R = 1.01\,(M\sin i/M_\oplus)^{0.279}",
    r"\,R_\oplus$ evaluated at $M\sin i$ (no de-inclination correction is",
    r"folded into the nominal value; the conditional isotropic factors are",
    r"given in the text); $\pm$ values are the $4.03\%$ intrinsic dispersion of",
    r"that branch.  $\mathrm{SNR_C}$ follows the scalar rule of eq.~\ref{eq:snrrule}",
    r"and the bracket is the bounded product of $A\in[0.15,0.45]$ with a",
    r"$\pm15\%$ radius allowance -- an assumption, not a confidence interval.",
    r"$\Delta v_{90}$ is the time-integral of the projected transverse",
    r"acceleration over 90\,d for a face-on orbit, with the range over starting",
    r"mean anomaly and the corresponding edge-on value in parentheses.",
    r"Observing geometry $z=650$\,AU, $d=1$\,m, $\lambda=1\,\mu$m, 1800\,s.}}",
    r"\label{tab:targets}",
    r"\scriptsize",
    r"\setlength{\tabcolsep}{2.0pt}",
    r"{\bfseries % entire table body is revised material (editor: bold changes)",
    r"\resizebox{\textwidth}{!}{%",
    r"\begin{tabular}{lcccccccccccc}",
    r"Planet & Host (SpT) & $z_0$ & $M\sin i$ & $R_p$\,$\pm$\,disp.$^{d}$ & $S$ & $P$ &",
    r"$D_{\rm img}$ & $\mathrm{SNR_C}$\,[range]$^{b}$ & Focal direction$^{c}$ & $\beta_{\rm ecl}$ &",
    r"$\Delta v_{90}$ (face)$^{b}$ \\",
    r"& & (pc) & ($M_\oplus$) & ($R_\oplus$) & ($S_\oplus$) & (d) & (km) &",
    r"(1800\,s) & (J2000) & (deg) & ($\mathrm{km\,s^{-1}}$ [range], edge) \\",
    r"\midrule",
]
for r in rows:
    nm = r["name"].replace(" (Luyten b)", "").replace(" (alt.)", "")
    nm = nm.replace("tau Cet", r"$\tau$ Cet")
    flag = "\\textsuperscript{a}" if r["above_ck_transition"] else ""
    if r["name"].startswith("tau Cet"):
        # the 162.9 d signal is a refuted detection (Figueira+ 25), so the row
        # is an illustrative dynamics case, not a candidate target
        flag += "\\textsuperscript{e}"
    lo, hi = r["dv90_face_on_range_kms"]
    rah = int(r["foc_ra_h"]); ram = int(round(60.0 * (r["foc_ra_h"] - rah)))
    dec = r["foc_dec_d"]
    sign = "-" if dec < 0.0 else "+"
    adec = abs(dec); decd = int(adec); decm = int(round(60.0 * (adec - decd)))
    radec = ("%02d$^{\\rm h}$%02d$^{\\rm m}$, $%s%02d^{\\circ}%02d'$"
             % (rah, ram, sign, decd, decm))
    host = r["host"].replace("tau Cet", r"$\tau$ Cet")
    snrlo, snrhi = r["SNRC_rule_bounded"]
    lines.append("%s%s & %s (%s) & %.2f & %.2f & %.2f\\,$\\pm$\\,%.2f & %.2f & "
                 "%.2f & %.1f & %.0f\\,[%.0f--%.0f] & %s & %+.1f & "
                 "%.2f (%.2f)\\\\" % (
                     nm, flag, host, r["spt"], r["d_pc"], r["msini"],
                     r["Rp_nominal_R"], r["Rp_terr_1sigma_R"], r["S"], r["P_d"],
                     r["Dimg_km"], r["SNRC_nominal"], snrlo, snrhi, radec,
                     r["foc_ecl_lat"], r["dv90_face_on_kms"],
                     r["dv90_edge_on_kms"]))
lines += [r"\bottomrule", r"\end{tabular}", r"}", r"}", "", r"\vspace{1mm}",
          r"\parbox{0.96\textwidth}{\footnotesize",
          r"\textbf{$^{a}$}\,$M\sin i$ lies above the Chen \& Kipping (2017) Terran/"
          r"Neptunian transition ($2.04^{+0.66}_{-0.59}\,M_\oplus$), so the "
          r"rocky-branch radius used here is an extrapolation, not a "
          r"measurement.",
          r"\textbf{$^{b}$}The $\mathrm{SNR_C}$ bracket is a \emph{bounded range} over "
          r"the stated albedo ($A\in[0.15,0.45]$) and radius allowance "
          r"($\pm15\%$), not a confidence level and not propagated from "
          r"catalogue uncertainties. The $\Delta v_{90}$ entries give the "
          r"face-on value with the corresponding edge-on value in parentheses; "
          r"the spread over the starting mean anomaly inside a 90-day window is "
          r"below $0.02\,\mathrm{km\,s^{-1}}$ for every row except "
          r"$\tau$~Cet~e ($0.09$--$0.13\,\mathrm{km\,s^{-1}}$).",
          r"\textbf{$^{c}$}Focal direction is the antipodal celestial coordinate of the "
          r"host; $\beta_{\rm ecl}$ is its ecliptic latitude, which sets the "
          r"departure plane-change cost.",
          r"\textbf{$^{d}$}Radii, stellar parameters and orbital elements are from the "
          r"references in Section~\ref{sec:targets}; none of these planets "
          r"transits, so $M\sin i$ (not $M$) is the observed quantity.",
          r"\textbf{$^{e}$}\,$\tau$~Cet~e is listed for dynamics illustration only. "
          r"The NASA Exoplanet Archive carries its 162.9-day signal as a "
          r"\emph{false positive} after \citet{figueira25}, who attribute the "
          r"$\tau$~Ceti RV signals to stellar activity; it is therefore not a "
          r"confirmed target and its radius, $S$, SNR and $\Delta v$ inherit the "
          r"assumed $M\sin i = 3.93\,M_\oplus$ of a refuted ephemeris.",
          r"}", r"\end{table*}", ""]
(OUT / "paper" / "targets_table.tex").write_text("\n".join(lines))
print("wrote results/targets.json, paper/figures/fig_targets.pdf, paper/targets_table.tex")
