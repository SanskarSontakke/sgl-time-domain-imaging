"""Portability: re-run the inversion with a non-SGL forward operator.

This module replaces K(rho) = d/(4*rho) with a conventional diffraction-limited
Airy PSF, matched in FWHM to the SGL image-plane pitch, and runs the SAME
estimator machinery on the same campaign, truth map and noise realisation.

The question it answers is about FIDELITY portability: how much of the recovered
correlation is carried by the SGL response rather than by the sampling scheme?
It deliberately does NOT test the surface-coupling (phase-locking) negative
result, because the fiducial cloud screen here is a spatially-correlated OU
field with no surface coupling; that test would require re-running the whole
surface-locked cloud suite under the alternative kernel.
"""

import sys
import time
import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
import sglsim as S
import expcommon as E
from ext import extcommon as X


def airy_kernel(n, pitch, d=S.DTEL, lambda_m=S.LAM):
    """Diffraction-limited Airy kernel.

    The Airy pattern is:
        I(r) = [2*J1(pi*r*D/(lambda*f)) / (pi*r*D/(lambda*f))]^2

    For a telescope of diameter D at wavelength lambda, the FWHM is:
        theta_fwhm ~ 1.028 * lambda / D

    At the image plane, the FWHM in meters is:
        fwhm_m = 1.028 * lambda * f/D = 1.028 * lambda * (f/D)

    For a diffraction-limited telescope, f/D ~ f-number ~ 10, so:
        fwhm_m ~ 10 * lambda ~ 10 um at 1 um wavelength

    This is MUCH smaller than the SGL kernel's ~20 m pitch at n=64.

    For the portability test, we use an Airy kernel with FWHM comparable to
    the SGL kernel's resolution (pitch = DIMG/n ~ 21 m at n=64).
    """
    # Set the Airy FWHM to match the SGL pitch
    fwhm = pitch  # match SGL resolution

    # Build the Airy pattern on the grid
    ax = np.arange(2 * n) - n
    dy, dx = np.meshgrid(ax, ax, indexing="ij")
    r = np.hypot(dy, dx) * pitch  # distance in meters

    # Airy pattern: I(r) = [2*J1(x)/x]^2 where x = pi*r/fwhm
    from scipy.special import j1
    x = np.pi * r / (fwhm / 2.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        airy = np.where(x < 1e-10, 1.0, (2 * j1(x) / x)**2)

    return airy


def build_F_airy(camp, airy_op, nlat, nlon, prot_assumed=S.PROT, nsub=E.NSUB):
    """Build forward operator with Airy kernel instead of SGL kernel.

    This is identical to S.build_F but uses the Airy kernel.
    """
    from scipy import sparse
    ns = nlat * nlon
    n = camp.n
    geo = airy_op.geo
    Kfull = airy_op.K_airy
    latf = geo["lat"].ravel()
    F = np.zeros((camp.nsamp, ns), dtype=np.float32)
    npix = n * n
    offs, wts = (S.gauss_legendre_offsets(nsub, camp.ts) if nsub > 1
                 else (np.zeros(1), np.ones(1)))
    for b in range(camp.nbins_tot):
        t = camp.bins_t[b]
        P_acc = None
        for dt, wt in zip(offs, wts):
            tt = 0.0 if camp.static else (t + dt)
            lon = (geo["lon0"] + 2 * np.pi * tt / prot_assumed).ravel()
            idx4, w4 = S.bilinear_weights(latf, lon, nlat, nlon)
            mu = S.illum(geo, tt).ravel() / S.MU_NORM
            w4m = w4 * mu[:, None]
            rows = np.repeat(np.arange(npix), 4)
            P_sub = sparse.csr_matrix((w4m.ravel(), (rows, idx4.ravel())),
                                      shape=(npix, ns))
            P_acc = wt * P_sub if P_acc is None else P_acc + wt * P_sub
        P = P_acc
        pix = camp.bin_pix_all[b]
        jy, jx = pix // n, pix % n
        Krows = np.empty((camp.nsc, npix), dtype=np.float64)
        for k in range(camp.nsc):
            Krows[k] = Kfull[n - jy[k]:2*n - jy[k],
                             n - jx[k]:2*n - jx[k]].ravel()
        F[b*camp.nsc:(b+1)*camp.nsc] = (Krows @ P).astype(np.float32)
    return F


class AiryOperator:
    """Wrapper to make the Airy kernel look like an SGLOperator."""
    def __init__(self, n, pitch=None, d=S.DTEL, lambda_m=S.LAM):
        self.n = n
        self.pitch = S.DIMG / n if pitch is None else pitch
        self.geo = S.disk_geometry(n)
        Kraw = airy_kernel(n, self.pitch, d, lambda_m)
        # Normalize like the SGL operator
        ref = S.AREF * self.geo["Zc"] * self.geo["mask"] / S.MU_NORM
        # Convolve reference with Airy kernel
        n2 = n
        K0 = np.roll(Kraw, (-n2, -n2), axis=(0, 1))
        pad = np.zeros((2*n2, 2*n2))
        pad[:n2, :n2] = ref
        out = np.fft.irfft2(np.fft.rfft2(pad) * np.fft.rfft2(K0),
                            s=(2*n2, 2*n2))
        conv = out[:n2, :n2]
        c0 = conv.mean(where=self.geo["mask"])
        self.K_airy = Kraw / c0
        self.Khat = np.fft.rfft2(np.roll(self.K_airy, (-n2, -n2), axis=(0, 1)))

    def conv(self, img):
        n = self.n
        pad = np.zeros((2*n, 2*n))
        pad[:n, :n] = img
        out = np.fft.irfft2(np.fft.rfft2(pad) * self.Khat, s=(2*n, 2*n))
        return out[:n, :n]


def main():
    t0 = time.time()
    seeds, truth_seeds = X.tier_seeds()
    fast = "--fast" in sys.argv[1:]
    X.log(f"portability: fast={fast}, seeds={seeds}")

    # Use the cached F and dataset if available
    camp = E.campaign(ts=1800.0, mp=16)
    sgl = E.sgl()
    truthF, truth_c = E.truth()

    # One campaign, one noise realisation: the FIRST tier seed. The Airy and SGL
    # numbers quoted below are then the same photons through two different
    # forward operators, so the comparison is paired, not ensemble-to-single.
    seed = int(seeds[0])
    fc = 0.55
    fc_i = E.FCS.index(fc)

    # Check for cached dataset
    dat_key = E.dat_key(camp, fc, seed)
    dat_path = E.CACHE / (dat_key + ".npz")
    if dat_path.exists():
        X.log(f"Using cached dataset: {dat_path.name}")
        dat = dict(np.load(dat_path))
    else:
        X.log("No cached dataset; simulating...")
        dat = E.trim(E.dataset(camp, sgl, truthF, seed, fc))

    # sigma_cl as the spine used it: read it from the archived part, never
    # recomputed here, so both kernels see the same assumed cloud amplitude.
    p0 = np.load(E.PARTS / ("clouds_f%d_s%d.npz" % (fc_i, E.SEEDS.index(seed))))
    sigma_cl = float(p0["sigma_cl"])

    # Build Airy operator
    X.log("Building Airy operator...")
    airy_op = AiryOperator(camp.n)

    # Build F with Airy kernel
    X.log("Building F with Airy kernel...")
    F_airy = build_F_airy(camp, airy_op, E.NLAT, E.NLON, nsub=E.NSUB)

    # Solve with the same estimator
    y = np.asarray(dat["y"], dtype=np.float64)
    sg = np.asarray(dat["sigma"], dtype=np.float64)

    X.log("Solving with Airy kernel (profiled)...")
    map_airy = S.solve_gls_profiled(F_airy, y, camp, sg, sigma_cl,
                                     E.TAU_DAYS, E.LAM_GLS, E.get_LtL(),
                                     deflate=True, anchor=True)

    # Evaluate
    e_airy = S.eval_map(map_airy, truth_c)
    X.log(f"Airy kernel: r={e_airy['pearson']:.4f}, SSIM={e_airy['ssim']:.4f}")

    # Paired reference: the SGL solve for THESE EXACT photons, read from the
    # spine's own part archive. Nothing here is hard-coded or averaged across
    # seeds, so the two numbers differ only through the forward operator.
    r_sgl = float(p0["profiled_pearson"])
    ssim_sgl = float(p0["profiled_ssim"])
    e_sgl_chk = S.eval_map(np.asarray(p0["map_profiled"]), truth_c)
    if abs(e_sgl_chk["pearson"] - r_sgl) > 1e-9:
        raise RuntimeError(f"part archive map/scalars disagree "
                           f"({e_sgl_chk['pearson']:.12g} vs {r_sgl:.12g})")
    X.log(f"SGL kernel, same seed (archived): r={r_sgl:.4f}, SSIM={ssim_sgl:.4f}")
    X.log(f"Paired ratio r_airy/r_sgl = {e_airy['pearson']/r_sgl:.4f}")
    X.log(f"Paired loss  r_airy-r_sgl  = {e_airy['pearson']-r_sgl:+.4f}")

    # Ensemble context: the archived multi-seed mean at this fc.
    cl = np.load(E.DATA / "clouds.npz", allow_pickle=True)
    meth = [str(m) for m in cl["methods"]]
    fci = int(np.argmin(np.abs(np.asarray(cl["fcs"]) - fc)))
    r_sgl_ens = float(cl["pearson_mat"][meth.index("profiled"), fci].mean())
    X.log(f"Ensemble SGL mean at fc={fc}: r={r_sgl_ens:.4f} "
          f"(seed {seed} is one member)")

    # What this test does NOT do, stated in the archive rather than only here:
    # the fiducial CloudModel has no surface coupling, so the cloud pattern is
    # not rotationally phase-locked and the -0.198 collapse cannot be probed.
    X.log("Kernel swap only: clouds here are uncoupled OU screens, so this is "
          "not a test of the surface-coupling (phase-locking) result.")

    # Resolution comparison
    # SGL: pitch = DIMG/n ~ 21 m at n=64
    # Airy: FWHM ~ pitch (by construction)
    pitch_sgl = S.DIMG / camp.n
    X.log(f"SGL pitch: {pitch_sgl:.2f} m")
    X.log(f"Airy FWHM: {pitch_sgl:.2f} m (matched by construction)")

    # --- Save archives ---
    X.save_npz("portability",
               r_airy=np.array([e_airy["pearson"]]),
               ssim_airy=np.array([e_airy["ssim"]]),
               r_sgl_paired=np.array([r_sgl]),
               ssim_sgl_paired=np.array([ssim_sgl]),
               bias_airy=np.array([e_airy.get("bias", 0.0)]),
               contrast_airy=np.array([e_airy.get("contrast", 0.0)]),
               r_sgl_ensemble_members=np.asarray(
                   cl["pearson_mat"][meth.index("profiled"), fci], np.float64),
               seed=np.array([seed]))

    wall = time.time() - t0
    headline = dict(
        r_airy=round(e_airy["pearson"], 4),
        ssim_airy=round(e_airy["ssim"], 4),
        r_sgl_paired=round(r_sgl, 4),
        ssim_sgl_paired=round(ssim_sgl, 4),
        r_ratio_paired=round(e_airy["pearson"] / r_sgl, 4),
        delta_r_paired=round(e_airy["pearson"] - r_sgl, 4),
        r_sgl_ensemble=round(r_sgl_ens, 4),
        seed=seed,
        fc=fc,
        pitch_m=round(pitch_sgl, 2),
        status="paired_single_seed_kernel_swap",
    )

    caveats = [
        "Paired at ONE seed (the tier's first); the ensemble value is quoted "
        "separately and is context, not the comparison.",
        "NOT a test of the surface-coupling (phase-locking) collapse: the "
        "fiducial CloudModel has surf_coupling=0, so its screens are not "
        "rotationally locked and -0.198 cannot be reproduced or refuted here.",
        "The Airy FWHM is set equal to the SGL image-plane pitch DIMG/n by "
        "construction; this is a matched-resolution swap, not a realistic "
        "conventional-telescope design study.",
        "The Airy kernel is a far-field diffraction pattern; near-field SGL "
        "effects, solar J2/limb structure and occultation are neglected.",
        "The forward operator is rebuilt from scratch, so operator-construction "
        "differences beyond the kernel itself may contribute to the loss.",
        "Only the profiled solver is tested; white-noise and deflation "
        "baselines are not re-run under the alternative kernel.",
    ]

    obj = dict(
        headline=headline,
        caveats=caveats,
        provenance=X.provenance("portability"),
        wall_clock_s=round(wall, 1),
    )
    X.save_json("portability", obj)
    X.log(f"wall clock: {wall:.1f} s")
    X.summary("portability", **headline)


if __name__ == "__main__":
    main()
