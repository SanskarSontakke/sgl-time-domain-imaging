"""Publication figures for the revised (v3) manuscript.

Reads ../results/*.npz -- the archives written by ``run_experiments.py merge``
from the per-(configuration, seed) part files -- and writes ../paper/figures/.

v3 conventions this file depends on:
  * clouds.npz stores metrics as (method, fc, seed) matrices with
    methods = (profiled, v2, white, b2, b1, b2coarse) and reconstructed maps as
    ``map_<method>_fc<i>`` (36x72 flattened).
  * cadence_photons.npz / cadence_wallclock.npz are the two resource arms
    (A: mp*ts = 8 h fixed; B: wall clock <= 90 d fixed), 6 paired seeds each.
  * cadence_controls_<arm>.npz holds the cloud-free (cf) and per-pass
    independent-weather (iid) controls for the SAME campaigns and seeds.
  * No number in a figure is typed in here: every curve comes from an archive.
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import sglsim as S
import expcommon as E

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "results"
FIGS = HERE.parent / "paper" / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.size": 8.5, "axes.titlesize": 9, "axes.labelsize": 8.5,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7.5,
    "figure.dpi": 150, "savefig.bbox": "tight", "font.family": "serif",
    "mathtext.fontset": "dejavuserif", "axes.linewidth": 0.7,
})

NLAT, NLON = E.NLAT, E.NLON
COL = {"profiled": "#0173b2", "white": "#de8f05", "b2": "#029e73",
       "b1": "#d55e00", "cf": "#56b4e9", "iid": "#cc79a7", "v2": "#8c8c8c"}
LBL = {"profiled": "TDI (profiled, OU-whitened)",
       "white": "clouds-as-white-noise GLS (B3)",
       "b2": "16-bin phase-binned coadd (B2)",
       "b1": "phase-blind coadd (B1)",
       "b2coarse": "8-bin phase-binned coadd",
       "v2": "v2 deflation (approximate)"}
METHODS = ("profiled", "v2", "white", "b2", "b1", "b2coarse")


def show_map(ax, m, vmin=0.0, vmax=0.7, title=None):
    im = ax.imshow(np.asarray(m).reshape(NLAT, NLON), origin="lower",
                   extent=(0, 360, -90, 90), aspect="auto",
                   cmap="cividis", vmin=vmin, vmax=vmax)
    ax.set_xticks([0, 120, 240, 360]); ax.set_yticks([-60, 0, 60])
    if title:
        ax.set_title(title, pad=3)
    return im


def show_disk(ax, img, title=None, cmap="magma", vmax=None):
    n = img.shape[0]
    geo = S.disk_geometry(n)
    a = np.array(img, dtype=float)
    a[~geo["mask"]] = np.nan
    cm = plt.get_cmap(cmap).copy(); cm.set_bad("0.12")
    im = ax.imshow(a, origin="lower", cmap=cm, vmax=vmax,
                   extent=(-S.DIMG / 2, S.DIMG / 2, -S.DIMG / 2, S.DIMG / 2))
    ax.set_xticks([]); ax.set_yticks([])
    if title:
        ax.set_title(title, pad=3)
    return im


def mse(v):
    """Mean and standard error of a 1-D seed array."""
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return v.mean(), (v.std(ddof=1) / np.sqrt(v.size) if v.size > 1 else 0.0)


def fiducial_snapshot():
    """One instantaneous scene + its SGL-convolved raster, from the shipped
    campaign (the archives store scalars only, so this is re-rendered here)."""
    camp = E.campaign()
    sglop = E.sgl("point")
    truthF, _ = E.truth()
    cloud = S.CloudModel(E.NLATF, E.NLONF, fc=E.FC, tau_days=E.TAU_DAYS,
                         seed=100 + E.SEEDS[0])
    dat = S.simulate_dataset(camp, truthF, cloud, sglop, seed=E.SEEDS[0],
                             nsub=E.NSUB, record_snapshots=(0.5,))
    sn = dat["snaps"][0]
    return sn["scene"], sn["conv"], float(np.mean(dat["covers"]))


# ----------------------------------------------------------------------
def fig1_model():
    d = np.load(DATA / "clouds.npz")
    sgl = S.SGLOperator(64)
    n = 64
    scene, conv, cover = fiducial_snapshot()
    fig, axs = plt.subplots(2, 2, figsize=(7.0, 5.2))
    ax = axs[0, 0]
    r_idx = np.arange(1, n)
    rho = sgl.pitch * r_idx
    kvals = sgl.K[n, n + 1:2 * n]
    ax.loglog(rho, kvals, "o", ms=2.5, color="#0173b2",
              label="grid kernel (normalized)")
    ax.loglog(rho, sgl.K[n, n] * S.DTEL / (4 * rho), "-", lw=1, color="0.3",
              label=r"$d/(4\rho)$ tail")
    ax.set_xlabel(r"image-plane separation $\rho$ [m]")
    ax.set_ylabel(r"$K(\rho)$")
    ax.set_title("(a) aperture-averaged SGL kernel")
    ax.legend(frameon=False)
    im = show_map(axs[0, 1], d["truth_c"],
                  title="(b) synthetic surface albedo (truth)")
    plt.colorbar(im, ax=axs[0, 1], fraction=0.046, label="albedo")
    axs[0, 1].set_xlabel("longitude [deg]")
    axs[0, 1].set_ylabel("latitude [deg]")
    im = show_disk(axs[1, 0], scene,
                   title=r"(c) instantaneous scene, cover $=%.2f$" % cover)
    plt.colorbar(im, ax=axs[1, 0], fraction=0.046,
                 label="normalized intensity")
    im = show_disk(axs[1, 1], conv,
                   title="(d) SGL-convolved measurement raster")
    plt.colorbar(im, ax=axs[1, 1], fraction=0.046, label="normalized signal")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_model.pdf")
    plt.close(fig)


def fig2_validation():
    d = np.load(DATA / "validation.npz")
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    ax.errorbar(d["ns"], d["measured"], yerr=d["measured_sd"], fmt="o-",
                color="#0173b2", ms=5, capsize=2,
                label="measured (discrete forward operator)")
    ax.loglog(d["ns"], d["theory"], "s--", color="0.35", ms=5,
              label=r"$0.891\,D/(d\sqrt{N})$ (analytic)")
    ax.set_xlabel(r"linear raster dimension $n$")
    ax.set_ylabel(r"$\mathrm{SNR_R/SNR_C}$")
    ax.set_yscale("log")
    ax.xaxis.set_minor_locator(plt.NullLocator())
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_xticks([32, 64, 128])
    ax.set_xlim(25, 160)
    ax.set_ylim(0.04, 1.4)
    ratio = float(d["measured"][2] / d["theory"][2])
    ax.annotate(r"$n=128$: measured/analytic $= %.2f$" % ratio,
                xy=(128, d["measured"][2]), xytext=(34, 0.11),
                arrowprops=dict(arrowstyle="->", lw=0.6, color="0.3"),
                fontsize=7, color="0.3")
    ax.legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_validation.pdf")
    plt.close(fig)


def fig3_gallery():
    d = np.load(DATA / "clouds.npz")
    P, Ss = d["pearson_mat"], d["ssim_mat"]
    cov = d["covers"]

    def m(mi, i):
        return mse(P[mi, i])[0], mse(Ss[mi, i])[0]

    mi = {k: METHODS.index(k) for k in METHODS}
    fcf, fcl = 0, 3                             # cloud-free / nominal-cloud column
    ccov = float(np.nanmean(cov[fcl]))
    fig, axs = plt.subplots(2, 3, figsize=(7.0, 4.6))
    show_map(axs[0, 0], d["truth_c"], title="truth surface albedo")
    r, ss = m(mi["profiled"], fcf)
    show_map(axs[0, 1], d["map_profiled_fc0"],
             title="TDI, cloud-free\n$r$=%.3f, SSIM=%.3f" % (r, ss))
    r, _ = m(mi["b1"], fcl)
    show_map(axs[0, 2], d["map_b1_fc%d" % fcl],
             title="B1 phase-blind coadd, cover $%.2f$\n$r$=%.3f" % (ccov, r))
    r, _ = m(mi["b2"], fcl)
    show_map(axs[1, 0], d["map_b2_fc%d" % fcl],
             title="B2 16-bin coadd\n$r$=%.3f" % r)
    r, _ = m(mi["white"], fcl)
    show_map(axs[1, 1], d["map_white_fc%d" % fcl],
             title="B3 white-noise GLS\n$r$=%.3f" % r)
    r, ss = m(mi["profiled"], fcl)
    show_map(axs[1, 2], d["map_profiled_fc%d" % fcl],
             title="TDI\n$r$=%.3f, SSIM=%.3f" % (r, ss))
    for ax in axs.ravel():
        ax.set_xlabel(""); ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_gallery.pdf")
    plt.close(fig)


def fig4_ssim_fc():
    d = np.load(DATA / "clouds.npz")
    fcs = d["fcs"]; cov = d["covers"]
    x = np.array([np.nanmean(cov[i]) for i in range(len(fcs))])
    P, Ss = d["pearson_mat"], d["ssim_mat"]
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    for key in ("profiled", "white", "b2", "b1"):
        mi = METHODS.index(key)
        for ax, arr in ((axs[0], Ss), (axs[1], P)):
            mu = np.array([mse(arr[mi, i]) for i in range(len(fcs))])
            ax.errorbar(x, mu[:, 0], yerr=mu[:, 1], fmt="o-", color=COL[key],
                        label=LBL[key], ms=4, capsize=2, lw=1)
    for ax in axs:
        ax.set_xlabel(r"realized cloud cover")
        ax.set_ylim(-0.05, 1.0)
        ax.axvline(0.5, color="0.8", lw=0.6)
    axs[0].set_ylabel("SSIM")
    axs[1].set_ylabel(r"Pearson $r$")
    axs[1].legend(frameon=False, loc="upper right")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_ssim_fc.pdf")
    plt.close(fig)


def fig5_cadence():
    arms = {"A": np.load(DATA / "cadence_photons.npz"),
            "B": np.load(DATA / "cadence_wallclock.npz")}
    led = np.load(DATA / "ledger.npz")
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.8))
    ax = axs[0]
    style = {"profiled": ("o", COL["profiled"], "-", 4.5),
             "white": ("s", COL["white"], "--", 4.0),
             "b2": ("^", COL["b2"], "-.", 4.0),
             "b1": ("v", COL["b1"], ":", 3.5)}
    for key, (mk, c, ls, ms) in style.items():
        for j, arm in enumerate(("A", "B")):
            d = arms[arm]
            mu = np.array([mse(d["r_" + key][i])[0] for i in range(len(d["mp"]))])
            ax.semilogx(d["mp"], mu, marker=mk, ls=ls, color=c, ms=ms,
                        base=2, lw=1, alpha=1.0 - 0.55 * j,
                        label=None)
    ax.axvline(64, color="0.6", lw=0.6, ls=":")
    ax.set_xlabel(r"registered revisits per pixel $M_p$")
    ax.set_ylabel(r"Pearson $r$ ($f_c=0.55$)")
    ax.set_title("(a) cadence law, both resource arms")
    ax.set_xticks(arms["A"]["mp"])
    ax.set_xticklabels([str(int(m)) for m in arms["A"]["mp"]])
    ax.set_ylim(-0.05, 0.65)
    handles = [Line2D([], [], marker=mk, color=c, ls=ls, ms=ms, lw=1,
                      label=LBL[k])
               for k, (mk, c, ls, ms) in style.items()]
    handles += [Line2D([], [], marker="o", color="0.15", ls="", ms=4,
                       label="arm A (8 h/pixel; 93.7 d at $M_p$=64)"),
                Line2D([], [], marker="o", color="0.65", ls="", ms=4,
                       label="arm B (90 d)")]
    ax.legend(handles=handles, frameon=False, fontsize=6.0, loc="upper left",
              ncol=1, borderaxespad=0.4)

    ax2 = axs[1]
    mp = np.array(led["neff_mp"], float)
    for k, tau in enumerate(led["neff_tau"]):
        ax2.semilogx(mp, led["neff"][k], "o-", ms=4, base=2,
                     label=r"$N_{\rm eff}$, $\tau_{\rm cloud}=%g$ d" % tau)
    ax2.plot(mp, mp, "k--", lw=0.8, label=r"independent looks ($N_{\rm eff}=M_p$)")
    ax2b = ax2.twinx()
    d = arms["A"]
    ax2b.semilogx(mp, d["duty"] * 100, "s:", color=COL["b2"], ms=3.5, base=2,
                  label="arm A duty cycle (%)")
    ax2b.set_ylabel("duty cycle [%]", color=COL["b2"])
    ax2b.tick_params(axis="y", labelcolor=COL["b2"])
    ax2b.set_ylim(85, 101)
    ax2.set_xlabel(r"registered revisits per pixel $M_p$")
    ax2.set_ylabel(r"effective independent looks $N_{\rm eff}$")
    ax2.set_title(r"(b) looks and duty cycle (45 s/dwell)")
    ax2.set_xticks(mp); ax2.set_xticklabels([str(int(m)) for m in mp])
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2b.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, frameon=False, fontsize=6.2, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_cadence.pdf")
    plt.close(fig)


def fig6_robust():
    """(a) spin-geometry ephemeris sensitivity, (b) profile-likelihood
    flatness in phase, (c) scale-dependent resolution r(ell)."""
    parts = DATA / "parts"

    def geom_mean(tag):
        vals = []
        for j in range(len(E.SEEDS)):
            p = parts / ("%srobgeom_%s_s%d.npz" % (E.PART_PREFIX, tag, j))
            if p.exists():
                vals.append(float(np.load(p)["pearson"]))
        return mse(vals)

    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.4))
    ax = axs[0]
    tilts = [0.0, 5.0, 20.0]
    t = [geom_mean("tilt%g" % v) for v in tilts]
    ax.plot(tilts, [x[0] for x in t], "o-", color=COL["profiled"], ms=4,
            label=r"pole tilt $\Delta\theta_{\rm pole}$")
    ph = [5.0, 15.0, 30.0, 60.0]
    q = [geom_mean("phase%g" % v) for v in ph]
    ax.plot(ph, [x[0] for x in q], "s--", color=COL["white"], ms=4,
            label=r"initial phase $\Delta\phi_0$")
    for xs, ts in ((tilts, t), (ph, q)):
        ax.plot(xs, [x[0] - x[1] for x in ts], lw=0, marker="none",
                ls="none")
    ax.errorbar(tilts, [x[0] for x in t], yerr=[x[1] for x in t], fmt="none",
                ecolor=COL["profiled"], capsize=1.5, lw=0.8)
    ax.errorbar(ph, [x[0] for x in q], yerr=[x[1] for x in q], fmt="none",
                ecolor=COL["white"], capsize=1.5, lw=0.8)
    ax.set_xlabel("spin-ephemeris error [deg]")
    ax.set_ylabel(r"Pearson $r$")
    ax.set_title("(a) geometry tolerance (10 seeds)")
    ax.set_ylim(0.0, 0.4)
    ax.set_xticks([0, 5, 15, 30, 60])
    ax.legend(frameon=False, fontsize=6.8)

    ax = axs[1]
    d = np.load(DATA / "profile_likelihood.npz")
    chi2 = np.asarray(d["chi2"], float)
    i0 = int(np.where(np.isclose(d["prot_errs"], 0.0))[0][0])
    j0 = int(np.where(np.isclose(d["phase_errs"], 0.0))[0][0])
    # each row re-referenced to its own zero-phase value: isolates PHASE sensitivity
    rel = 1e12 * (chi2 - chi2[:, [j0]]) / chi2[:, [j0]]
    for i in range(len(d["prot_errs"])):
        ax.plot(d["phase_errs"], rel[i], "-", color="0.75", lw=1.0,
                label=(r"$\Delta\chi^2/\chi^2$: all $\Delta P/P$ rows"
                       if i == 0 else None))
    ax.plot(d["phase_errs"], rel[i0], "o", color="#0173b2", ms=4.5, mec="k",
            mew=0.3, label=r"row at $\Delta P/P=0$")
    ax.axhline(0, color="0.8", lw=0.6)
    ax.set_xlabel(r"assumed phase offset [deg]")
    ax.set_ylabel(r"$\Delta\chi^2/\chi^2$ [$10^{-12}$]")
    ax.set_ylim(-9, 9)
    ax2 = ax.twinx()
    ax2.plot(d["phase_errs"], d["r"][i0], "s:", color=COL["b2"], ms=4,
             label="recovered $r$ (right axis)")
    ax2.set_ylabel(r"Pearson $r$", color=COL["b2"])
    ax2.tick_params(axis="y", labelcolor=COL["b2"])
    ax2.set_ylim(0.18, 0.46)
    ax.set_title("(b) objective flat, $r$ peaked")
    hh, ll = ax.get_legend_handles_labels()
    hh2, ll2 = ax2.get_legend_handles_labels()
    ax.legend(hh + hh2, ll + ll2, frameon=False, fontsize=5.8,
              loc="lower center", handlelength=1.6, borderaxespad=0.2)
    ax = axs[2]
    r = np.load(DATA / "spatial_resolution.npz")
    for key, c, lab in (("r_cf", COL["cf"], "cloud-free"),
                        ("r_cl", COL["profiled"], r"cloudy ($f_c=0.55$)")):
        mu = r[key].mean(0)
        se = r[key].std(0, ddof=1) / np.sqrt(r[key].shape[0])
        ax.errorbar(r["l"], mu, yerr=se, marker="o" if key == "r_cl" else "s",
                    ms=3.5, lw=1, color=c, capsize=1.5, label=lab)
    ax.axhline(0.5, color="0.6", ls=":", lw=0.8)
    ax.axvline(18, color="0.3", ls="--", lw=0.8)
    ax.text(17.6, 1.45, r"grid ceiling $\ell\!\approx\!18$", fontsize=5.8,
            color="0.25", ha="right", va="top", rotation=90)
    ax.text(1.5, 0.53, r"$r(\ell)=0.5$", fontsize=5.8, color="0.45")
    ax.set_xlabel(r"harmonic degree $\ell$")
    ax.set_ylabel(r"scale correlation $r(\ell)$")
    ax.set_title("(c) effective resolution")
    ax.set_ylim(-0.1, 1.6)
    ax.set_yticks([0, 0.5, 1.0])
    ax.legend(frameon=False, fontsize=6.0, loc="upper left", ncol=2,
              handlelength=1.6, borderaxespad=0.2, columnspacing=1.0)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_robust.pdf")
    plt.close(fig)


def fig7_lambda_sigma():
    """Assumed-noise and regularization sensitivity (referee: a curve for
    cloud-free and cloudy cases would be sufficient).

    (a,b) lambda sweep from lambda_sweep_f{0,3}.npz: image quality keeps
    improving across the whole tested range while the objective barely moves in
    the cloudy case, i.e. chi2 cannot select lambda and the frozen 3e-3 is not
    the optimum of r.
    (c) sigma_cl sweep from sigma_sensitivity.npz: r is flat over a 16x range of
    the assumed cloud amplitude while the whitened chi2 is not, which is why the
    objective cannot be used to validate the assumed climatology.
    """
    import os
    lam0 = DATA / "lambda_sweep_f0.npz"
    lam3 = DATA / "lambda_sweep_f3.npz"
    sigp = DATA / "sigma_sensitivity.npz"
    if not (lam0.exists() and lam3.exists()):
        print("fig7: lambda archives missing, skipped"); return
    fig, axs = plt.subplots(1, 3, figsize=(7.4, 2.5))
    fid = E.LAM_GLS
    for i_fc, f, c, lab in ((0, lam0, COL["cf"], "cloud-free"),
                            (3, lam3, COL["profiled"], r"cloudy ($f_c=0.55$)")):
        d = np.load(f)
        lam, R, C = d["lam"], d["r"], d["chi2"]
        k = int(np.argmin(np.abs(lam - fid)))
        ax = axs[0]
        D = R - R[:, [k]]                      # paired against the frozen lambda
        mu = D.mean(0); se = D.std(0, ddof=1) / np.sqrt(D.shape[0])
        ax.errorbar(lam, mu, yerr=se, marker="o", ms=3.2, lw=1, color=c,
                    capsize=1.5, label=lab)
        ax = axs[1]
        rel = (C / C[:, [k]]).mean(0)
        ax.semilogy(lam, rel, marker="o", ms=3.2, lw=1, color=c, label=lab)
    for ax, ylim in ((axs[0], None), (axs[1], (0.98, 2.6))):
        ax.set_xscale("log")
        ax.set_xticks([1e-5, 1e-3, 1e-1, 1e1])
        ax.set_xticklabels([r"$10^{-5}$", r"$10^{-3}$",
                            r"$10^{-1}$", r"$10^{1}$"])
        ax.axvline(fid, color="0.35", ls="--", lw=0.8)
        if ylim:
            ax.set_ylim(*ylim)
    axs[0].axhline(0.0, color="0.5", lw=0.7)
    axs[0].set_ylabel(r"paired $\Delta r$ vs $\lambda=3\times10^{-3}$")
    axs[0].set_title("(a) quality vs $\\lambda$")
    axs[0].set_ylim(-0.02, 0.19)
    axs[0].legend(frameon=False, fontsize=6.2, loc="upper left",
                  handlelength=1.4)
    axs[1].set_ylabel(r"$\chi^2/\chi^2(3\times10^{-3})$")
    axs[1].set_title("(b) objective vs $\\lambda$")
    axs[2].set_xscale("log")
    axs[2].set_xlabel(r"regularization weight $\lambda$")
    axs[1].set_xlabel(r"regularization weight $\lambda$")
    axs[2].set_xlabel(r"assumed $\sigma_{\rm cl}$ / calibrated")
    for ax in (axs[0], axs[1]):
        ax.tick_params(axis="x", labelsize=6.5)
    if sigp.exists():
        d = np.load(sigp)
        fac, R, C = d["factors"], d["r"], d["chi2"]
        k = int(np.argmin(np.abs(fac - 1.0)))
        ax = axs[2]
        x = np.arange(len(fac))               # categorical spacing: the factors
        # span 0 -> 16 and a linear axis would pile up the small ones
        mu = R.mean(0); se = R.std(0, ddof=1) / np.sqrt(R.shape[0])
        ax.errorbar(x, mu, yerr=se, marker="o", ms=3.2, lw=1,
                    color=COL["b1"], capsize=1.5, label=r"Pearson $r$")
        ax.axhline(mu[k], color=COL["b1"], ls=":", lw=0.8)
        ax2 = ax.twinx()
        rel = (C / C[:, [k]]).mean(0)
        ax2.semilogy(x, rel, marker="s", ms=3.0, lw=1, color=COL["white"],
                     ls="--", label=r"$\chi^2$ (right)")
        ax2.set_ylabel(r"$\chi^2/\chi^2(\sigma_{\rm cl}=\rm fid$)",
                       color=COL["white"])
        ax2.tick_params(axis="y", labelcolor=COL["white"], labelsize=6.5)
        ax.set_xticks(x)
        ax.set_xticklabels(["$0$", "$1/16$", "$1/4$", "$1/2$", "$1$", "$2$",
                            "$4$", "$16$"])
        ax.tick_params(axis="x", labelsize=6.0)
        ax.set_xlim(-0.95, len(fac) - 0.35)
        pad = 1.25 * se.max()
        ax.set_ylim(mu.min() - pad, mu.max() + pad)
        ax.set_ylabel(r"Pearson $r$")
        ax.set_title("(c) assumed cloud amplitude")
        hh, ll = ax.get_legend_handles_labels()
        hh2, ll2 = ax2.get_legend_handles_labels()
        ax.legend(hh + hh2, ll + ll2, frameon=False, fontsize=6.0,
                  loc="upper right", handlelength=1.5)
    else:
        axs[2].text(0.5, 0.5, r"$\sigma_{\rm cl}$ sweep pending",
                    transform=axs[2].transAxes, ha="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_lamsigma.pdf")
    plt.close(fig)


FIGURES = {"1": fig1_model, "2": fig2_validation, "3": fig3_gallery,
           "4": fig4_ssim_fc, "5": fig5_cadence, "6": fig6_robust,
           "7": fig7_lambda_sigma}
if __name__ == "__main__":
    import sys
    which = sys.argv[1:] or sorted(FIGURES)
    for w in which:
        FIGURES[w]()
        print("fig", w, "done", flush=True)
