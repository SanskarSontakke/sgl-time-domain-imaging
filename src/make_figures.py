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
COL = {"gls": "#0173b2", "white": "#de8f05", "b2": "#029e73"}
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
    fig, ax = plt.subplots(figsize=(3.4, 2.7))
    ax.loglog(d["ns"], d["theory"], "s--", color="0.35", ms=5,
              label=r"$0.891\,D/(d\sqrt{N})$ (analytic)")
    ax.loglog(d["ns"], d["measured"], "o-", color="#0173b2", ms=5,
              label="measured (this work)")
    ax.set_xlabel(r"linear raster dimension $n$")
    ax.set_ylabel(r"$\mathrm{SNR_R/SNR_C}$")
    ax.set_xticks([32, 64, 128]); ax.set_xticklabels(["32", "64", "128"])
    ax.legend(frameon=False)
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
    d = np.load(DATA / "cadence.npz")
    fig, axs = plt.subplots(1, 2, figsize=(7.0, 2.7))
    mp = d["mp"]
    for m, nm in enumerate(["gls", "white", "b2"]):
        for ax, arr in ((axs[0], d["ssim"]), (axs[1], d["pearson"])):
            mu = np.nanmean(arr[m], axis=1)
            lo = np.nanmin(arr[m], axis=1); hi = np.nanmax(arr[m], axis=1)
            ax.semilogx(mp, mu, "o-", color=COL[nm], label=LBL[nm], ms=4,
                        base=2)
            ax.fill_between(mp, lo, hi, color=COL[nm], alpha=0.18, lw=0)
    for ax in axs:
        ax.set_xlabel(r"revisits per pixel $M_p$ (fixed photons & 90 d)")
        ax.set_xticks(mp); ax.set_xticklabels([str(int(m)) for m in mp])
        ax.set_ylim(-0.05, 0.75)
    axs[0].set_ylabel("SSIM"); axs[1].set_ylabel("Pearson $r$")
    axs[1].legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(FIGS / "fig_cadence.pdf")
    plt.close(fig)


def fig6_robust():
    d = np.load(DATA / "robust.npz")
    dc = np.load(DATA / "clouds.npz")
    ref_white = float(np.nanmean(dc["ssim"][1, 3]))
    fig, axs = plt.subplots(1, 3, figsize=(7.0, 2.3))
    axs[0].semilogx(d["tau"], d["ssim_tau"], "o-", color=COL["gls"])
    axs[0].axvline(4.0, color="0.6", ls=":", lw=0.8)
    axs[0].set_xlabel(r"assumed $\tau_c$ [d] (true: 4)")
    axs[1].semilogx(d["sig"], d["ssim_sig"], "o-", color=COL["gls"])
    axs[1].axvline(1.0, color="0.6", ls=":", lw=0.8)
    axs[1].set_xlabel(r"assumed $\sigma_{\rm cl}$ / true")
    x = np.arange(len(d["prot"]))
    axs[2].plot(x, d["ssim_prot"], "o-", color=COL["gls"])
    axs[2].set_xticks(x)
    axs[2].set_xticklabels(["0", r"$10^{-4}$", r"$10^{-3}$"])
    axs[2].set_xlabel("fractional rotation-period error")
    for ax in axs:
        ax.set_ylim(0, 0.2)
        ax.axhline(ref_white, color=COL["white"], ls="--", lw=0.9)
        ax.set_ylabel("SSIM")
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
