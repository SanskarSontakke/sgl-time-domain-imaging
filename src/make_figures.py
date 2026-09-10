"""Publication figures. Reads ../results/*.npz, writes ../paper/figures/."""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sglsim as S

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
COL = {"gls": "#0173b2", "white": "#de8f05", "b2": "#029e73", "cf": "#56b4e9", "iid": "#cc79a7"}
LBL = {"gls": "TDI (deflated, covariance-aware)",
       "white": "clouds-as-white-noise GLS",
       "b2": "phase-binned coadd + Wiener"}
NLAT, NLON = 36, 72


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
                   extent=(-S.DIMG/2, S.DIMG/2, -S.DIMG/2, S.DIMG/2))
    ax.set_xticks([]); ax.set_yticks([])
    if title:
        ax.set_title(title, pad=3)
    return im


def fig1_model():
    d = np.load(DATA / "clouds.npz")
    sgl = S.SGLOperator(64)
    n = 64
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
    im = show_disk(axs[1, 0], d["snap1_scene_fc3"],
                   title=r"(c) instantaneous scene, $f_c\simeq0.55$")
    plt.colorbar(im, ax=axs[1, 0], fraction=0.046,
                 label="normalized intensity")
    im = show_disk(axs[1, 1], d["snap1_conv_fc3"],
                   title="(d) SGL-convolved measurement raster")
    plt.colorbar(im, ax=axs[1, 1], fraction=0.046, label="normalized signal")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_model.pdf")
    plt.close(fig)


def fig2_validation():
    d = np.load(DATA / "validation.npz")
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    ax.loglog(d["ns"], d["theory"], "s--", color="0.35", ms=5,
              label=r"$0.891\,D/(d\sqrt{N})$ (analytic)")
    ax.loglog(d["ns"], d["measured"], "o-", color="#0173b2", ms=5,
              label="measured (discrete forward operator)")
    ax.set_xlabel(r"linear raster dimension $n$")
    ax.set_ylabel(r"$\mathrm{SNR_R/SNR_C}$")
    ax.xaxis.set_minor_locator(plt.NullLocator())
    ax.xaxis.set_minor_formatter(plt.NullFormatter())
    ax.set_xticks([32, 64, 128])
    ax.set_xticklabels(["32", "64", "128"])
    ax.set_xlim(25, 160)
    ax.set_ylim(0.04, 1.4)
    ax.annotate(r"$\Delta \approx 45\%$ due to discrete pixel low-pass",
                xy=(128, d["measured"][2]), xytext=(55, 0.05),
                arrowprops=dict(arrowstyle="->", lw=0.6, color="0.3"),
                fontsize=7, color="0.3")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_validation.pdf")
    plt.close(fig)


def fig3_gallery():
    d = np.load(DATA / "clouds.npz")
    ss = d["ssim"]; pr = d["pearson"]
    fig, axs = plt.subplots(2, 3, figsize=(7.0, 4.6))
    show_map(axs[0, 0], d["truth_c"], title="truth surface albedo")
    show_map(axs[0, 1], d["map_gls_fc0"],
             title="TDI, cloud-free\n$r$=%.2f, SSIM=%.2f" % (pr[0,0,0], ss[0,0,0]))
    show_disk(axs[0, 2], d["b1img_fc3"], cmap="cividis",
              title="B1 static Wiener image, $f_c$=0.55")
    show_map(axs[1, 0], d["map_b2_fc3"],
             title="B2 phase-binned, $f_c$=0.55\n$r$=%.2f" % pr[2,3,0])
    show_map(axs[1, 1], d["map_white_fc3"],
             title="B3 white-noise GLS, $f_c$=0.55\n$r$=%.2f" % pr[1,3,0])
    show_map(axs[1, 2], d["map_gls_fc3"],
             title="TDI, $f_c$=0.55\n$r$=%.2f" % pr[0,3,0])
    for ax in axs.ravel():
        ax.set_xlabel(""); ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_gallery.pdf")
    plt.close(fig)


def fig4_ssim_fc():
    d = np.load(DATA / "clouds.npz")
    fcs = d["fcs"]; ss = d["ssim"]; pr = d["pearson"]
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    for m, nm in enumerate(["gls", "white", "b2"]):
        for ax, arr in ((axs[0], ss), (axs[1], pr)):
            mu = np.nanmean(arr[m], axis=1)
            lo = np.nanmin(arr[m], axis=1); hi = np.nanmax(arr[m], axis=1)
            ax.plot(fcs, mu, "o-", color=COL[nm], label=LBL[nm], ms=4)
            ax.fill_between(fcs, lo, hi, color=COL[nm], alpha=0.18, lw=0)
    axs[0].set_ylabel("SSIM"); axs[1].set_ylabel("Pearson $r$")
    for ax in axs:
        ax.set_xlabel(r"mean cloud cover fraction $f_c$")
        ax.set_ylim(-0.05, 1)
    axs[1].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIGS / "fig_ssim_fc.pdf")
    plt.close(fig)


def fig5_cadence():
    # Load factorial cadence ablation results
    p_abl = DATA / "cadence_ablation.npz"
    if p_abl.exists():
        da = np.load(p_abl)
        mp = da["mp"]
        r_inst = da["r_inst_ou"]
        r_smear = da["r_smear_modeled_ou"]
        r_cf = da["r_cloud_free"]
        r_iid = da["r_iid_clouds"]
        duty = da["duty_cycle"]
    else:
        d = np.load(DATA / "cadence.npz")
        mp = d["mp"]
        r_inst = np.nanmean(d["pearson"][0], axis=1)
        r_smear = r_inst
        r_cf = np.ones_like(r_inst) * 0.99
        r_iid = r_inst
        duty = np.array([0.99, 0.99, 0.98, 0.95, 0.91])

    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.8))
    
    # Panel (a): Factorial mechanism decomposition
    ax = axs[0]
    ax.semilogx(mp, r_cf, "s--", color="#56b4e9", label=r"cloud-free control ($f_c=0$)", ms=4, base=2)
    ax.semilogx(mp, r_iid, "^-.", color="#cc79a7", label=r"independent i.i.d. clouds", ms=4, base=2)
    ax.semilogx(mp, r_inst, "o-", color="#0173b2", label=r"TDI (OU clouds, instant $\mathbf{F}$)", ms=4, base=2)
    ax.semilogx(mp, r_smear, "d:", color="#d55e00", label=r"TDI (OU clouds, smear-modeled $\mathbf{F}$)", ms=4, base=2)
    ax.set_xlabel(r"revisits per pixel $M_p$ (fixed photons & 90 d)")
    ax.set_ylabel("Pearson $r$")
    ax.set_title("(a) factorial cadence mechanism")
    ax.set_xticks(mp); ax.set_xticklabels([str(int(m)) for m in mp])
    ax.set_ylim(0.0, 1.05)
    ax.legend(frameon=False, fontsize=6.8, loc="center left")
    
    # Panel (b): Duty cycle and overhead tradeoff
    ax2 = axs[1]
    ax2.plot(mp, duty * 100, "o-", color="#029e73", label="duty cycle (%)", ms=4)
    ax2.set_xlabel(r"revisits per pixel $M_p$")
    ax2.set_ylabel("photon duty cycle [%]", color="#029e73")
    ax2.set_xticks(mp); ax2.set_xticklabels([str(int(m)) for m in mp])
    ax2.set_ylim(50, 105)
    ax2.tick_params(axis="y", labelcolor="#029e73")
    ax2.set_title(r"(b) overhead tradeoff ($\tau_{\rm slew}=45$ s)")
    
    ax2_r = ax2.twinx()
    ax2_r.semilogx(mp, r_inst, "o-", color="#0173b2", ms=4, base=2)
    ax2_r.set_ylabel("recovered $r$", color="#0173b2")
    ax2_r.tick_params(axis="y", labelcolor="#0173b2")
    ax2_r.set_ylim(0.0, 0.7)
    
    fig.tight_layout()
    fig.savefig(FIGS / "fig_cadence.pdf")
    plt.close(fig)


def fig6_robust():
    p_ext = DATA / "robust_extended.npz"
    p_res = DATA / "spatial_resolution.npz"
    d_ext = np.load(p_ext) if p_ext.exists() else None
    d_res = np.load(p_res) if p_res.exists() else None
    d = np.load(DATA / "robust.npz")
    
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.4))
    
    # 1. Spin Pole Tilt & Phase Errors
    if d_ext is not None:
        ax = axs[0]
        ax.plot(d_ext["pole_tilts_deg"], d_ext["r_pole"], "o-", color="#0173b2", ms=4, label=r"pole tilt $\Delta\theta_{\rm pole}$")
        ax.plot(d_ext["phases_deg"][:4], d_ext["r_phase"][:4], "s--", color="#de8f05", ms=4, label=r"initial phase $\Delta\phi_0$")
        ax.set_xlabel("ephemeris angular error [deg]")
        ax.set_ylabel("Pearson $r$")
        ax.set_title("(a) spin geometry sensitivity")
        ax.set_ylim(0.0, 0.40)
        ax.legend(frameon=False, fontsize=7)
    else:
        axs[0].semilogx(d["tau"], d["ssim_tau"], "o-", color=COL["gls"])
        axs[0].set_title("(a) assumed cloud tau")
        
    # 2. Profile likelihood 2D contour over Prot and Phase
    if d_ext is not None:
        ax = axs[1]
        chi2 = d_ext["prof_chi2"]
        chi2_norm = (chi2 - np.min(chi2)) / (np.max(chi2) - np.min(chi2))
        im = ax.imshow(chi2_norm, origin="lower", aspect="auto", cmap="viridis_r",
                       extent=[d_ext["phase_errs_deg"][0], d_ext["phase_errs_deg"][-1],
                               d_ext["prot_errs"][0] * 1e4, d_ext["prot_errs"][-1] * 1e4])
        ax.plot(0, 0, "r*", ms=8, label="truth")
        ax.set_xlabel(r"phase error $\Delta\phi_0$ [deg]")
        ax.set_ylabel(r"period error $\Delta P/P$ [$10^{-4}$]")
        ax.set_title(r"(b) profile $\chi^2$ landscape")
        plt.colorbar(im, ax=ax, fraction=0.046, label=r"norm. $\chi^2$")
        ax.legend(frameon=False, loc="upper right", fontsize=7)
    else:
        axs[1].semilogx(d["sig"], d["ssim_sig"], "o-", color=COL["gls"])
        axs[1].set_title("(b) assumed cloud sigma")
        
    # 3. Spatial Harmonic Resolution r(l) & Detection d'
    if d_res is not None:
        ax = axs[2]
        ax.plot(d_res["l_deg"], d_res["r_l_cf"], "s-", color="#56b4e9", ms=3.5, label="cloud-free")
        ax.plot(d_res["l_deg"], d_res["r_l_cl"], "o-", color="#0173b2", ms=3.5, label=r"cloudy ($f_c=0.55$)")
        ax.axhline(0.5, color="0.6", ls=":", lw=0.8, label=r"$r=0.5$ limit")
        ax.set_xlabel(r"harmonic degree $\ell$")
        ax.set_ylabel(r"scale correlation $r(\ell)$")
        ax.set_title(r"(c) effective spatial resolution")
        ax.set_ylim(-0.2, 1.05)
        ax.legend(frameon=False, fontsize=6.8)
    else:
        x = np.arange(len(d["prot"]))
        axs[2].plot(x, d["ssim_prot"], "o-", color=COL["gls"])
        axs[2].set_xticks(x)
        axs[2].set_xticklabels(["0", r"$10^{-4}$", r"$10^{-3}$"])
        axs[2].set_title("(c) rotation period error")
        
    fig.tight_layout()
    fig.savefig(FIGS / "fig_robust.pdf")
    plt.close(fig)


if __name__ == "__main__":
    import sys
    which = sys.argv[1:] or ["1", "2", "3", "4", "5", "6"]
    fns = {"1": fig1_model, "2": fig2_validation, "3": fig3_gallery,
           "4": fig4_ssim_fc, "5": fig5_cadence, "6": fig6_robust}
    for w in which:
        fns[w]()
        print("fig", w, "done", flush=True)
