"""
sglsim -- End-to-end simulation of exoplanet imaging with the solar
gravitational lens (SGL) for a rotating planet with a dynamic (time-varying)
cloud cover, and a covariance-aware joint inversion for the surface map.

Physical conventions follow the published SGL imaging literature:
  * aperture-averaged SGL kernel  K(0)=1, K(rho>0) = d/(4 rho),
    renormalized so the mean convolved disk signal is unity
    (Turyshev & Toth 2020, PRD 102, 024038; Turyshev 2026, arXiv:2606.14899)
  * fiducial photon rates for an Earth-radius planet at z0 = 30 pc observed
    from z = 650 AU with a d = 1 m telescope at lambda = 1 um:
        Q_exo = 8.01e4 ph/s, Q_cor = 6.20e9 ph/s
    (Turyshev & Toth 2022, MNRAS 515, 6122)
  * normalized scene units: 1.0 == disk-mean signal of a fully illuminated,
    albedo-0.3 Lambertian planet.

All random processes are seeded and reproducible.
Author: Sanskar Sontakke, 2026.
"""

import numpy as np
from dataclasses import dataclass
from scipy import sparse
from scipy.ndimage import gaussian_filter
from scipy.linalg import cholesky, solve_triangular

# ----------------------------------------------------------------------
# physical constants (SI)
# ----------------------------------------------------------------------
AU   = 1.495978707e11
PC   = 3.0856775814913673e16
RSUN = 6.957e8
GMS  = 1.32712440018e20
CC   = 299792458.0
RG   = 2.0 * GMS / CC**2          # solar Schwarzschild radius, 2953.25 m

Z    = 650.0 * AU
Z0   = 30.0 * PC
DTEL = 1.0
LAM  = 1.0e-6
RPL  = 6.371e6
DIMG = 2.0 * RPL * Z / Z0         # image-cylinder diameter ~ 1338 m
QEXO = 8.01e4
QCOR = 6.20e9

PROT   = 86400.0
PORB   = 3.1557e7
ALPHA0 = np.deg2rad(-42.0)
ACLOUD = 0.65
AREF   = 0.3
MU_NORM = AREF * (2.0 / 3.0)


@dataclass
class Campaign:
    n: int = 64
    nsc: int = 16
    ts: float = 1800.0
    mp: int = 16
    gap_max: float = 43200.0
    seed: int = 2026
    static: bool = False
    prot: float = PROT

    def __post_init__(self):
        rng = np.random.default_rng(self.seed)
        n2 = self.n * self.n
        assert n2 % self.nsc == 0
        self.nbin = n2 // self.nsc
        self.nbins_tot = self.nbin * self.mp
        order = []
        for iy in range(self.n):
            xs = range(self.n) if iy % 2 == 0 else range(self.n - 1, -1, -1)
            order += [iy * self.n + ix for ix in xs]
        self.order = np.array(order)
        self.bin_pix = self.order.reshape(self.nbin, self.nsc)
        gaps = rng.uniform(0.0, self.gap_max, size=self.mp)
        gaps[0] = 0.0
        pass_dur = self.nbin * self.ts
        t0 = np.cumsum(gaps) + np.arange(self.mp) * pass_dur
        slot_t = (np.arange(self.nbin) + 0.5) * self.ts
        self.bins_t = (t0[:, None] + slot_t[None, :]).ravel()
        self.bin_pix_all = np.tile(self.bin_pix, (self.mp, 1))
        self.sample_pix = self.bin_pix_all.ravel()
        self.sample_t = np.repeat(self.bins_t, self.nsc)
        self.nsamp = self.sample_pix.size
        idx = np.argsort(self.sample_pix, kind="stable")
        self.pix_samples = idx.reshape(n2, self.mp)
        self.wallclock_days = (self.bins_t[-1] + 0.5 * self.ts) / 86400.0


def disk_geometry(n):
    x = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    X, Y = np.meshgrid(x, x, indexing="xy")
    r2 = X**2 + Y**2
    mask = r2 < 1.0
    Zc = np.sqrt(np.clip(1.0 - r2, 0.0, None))
    lat = np.arcsin(np.clip(Y, -1, 1))
    lon0 = np.arctan2(X, Zc)
    return dict(n=n, X=X, Y=Y, Zc=Zc, mask=mask, lat=lat, lon0=lon0)


def illum(geo, t):
    alpha = ALPHA0 + 2.0 * np.pi * t / PORB
    mu = np.sin(alpha) * geo["X"] + np.cos(alpha) * geo["Zc"]
    return np.clip(mu, 0.0, None) * geo["mask"]


def bilinear_weights(lat, lon, nlat, nlon):
    fy = (lat / np.pi + 0.5) * nlat - 0.5
    fx = (np.mod(lon, 2.0 * np.pi) / (2.0 * np.pi)) * nlon - 0.5
    iy0 = np.floor(fy).astype(int)
    ix0 = np.floor(fx).astype(int)
    wy = fy - iy0
    wx = fx - ix0
    iy0c = np.clip(iy0, 0, nlat - 1)
    iy1c = np.clip(iy0 + 1, 0, nlat - 1)
    ix0m = np.mod(ix0, nlon)
    ix1m = np.mod(ix0 + 1, nlon)
    idx4 = np.stack([iy0c * nlon + ix0m, iy0c * nlon + ix1m,
                     iy1c * nlon + ix0m, iy1c * nlon + ix1m], axis=-1)
    w4 = np.stack([(1 - wy) * (1 - wx), (1 - wy) * wx,
                   wy * (1 - wx), wy * wx], axis=-1)
    return idx4, w4


def render_disk(map_flat, geo, t, nlat, nlon, prot=PROT, static=False):
    tt = 0.0 if static else t
    lon = geo["lon0"] + 2.0 * np.pi * tt / prot
    idx4, w4 = bilinear_weights(geo["lat"].ravel(), lon.ravel(), nlat, nlon)
    A = (map_flat[idx4] * w4).sum(axis=-1).reshape(geo["lat"].shape)
    mu = illum(geo, 0.0 if static else t)
    return A * mu / MU_NORM


def make_kernel(n, pitch, d=DTEL):
    ax = np.arange(2 * n) - n
    dy, dx = np.meshgrid(ax, ax, indexing="ij")
    rho = pitch * np.hypot(dy, dx)
    with np.errstate(divide="ignore"):
        K = d / (4.0 * rho)
    K[n, n] = 1.0
    return K


class SGLOperator:
    def __init__(self, n, pitch=None, d=DTEL):
        self.n = n
        self.pitch = DIMG / n if pitch is None else pitch
        geo = disk_geometry(n)
        Kraw = make_kernel(n, self.pitch, d)
        ref = AREF * geo["Zc"] * geo["mask"] / MU_NORM
        c0 = self._conv_raw(ref, Kraw).mean(where=geo["mask"])
        self.K = Kraw / c0
        self.Khat = np.fft.rfft2(np.roll(self.K, (-n, -n), axis=(0, 1)))
        self.geo = geo

    def _conv_raw(self, img, Kimg):
        n = self.n
        K0 = np.roll(Kimg, (-n, -n), axis=(0, 1))
        pad = np.zeros((2 * n, 2 * n))
        pad[:n, :n] = img
        out = np.fft.irfft2(np.fft.rfft2(pad) * np.fft.rfft2(K0),
                            s=(2 * n, 2 * n))
        return out[:n, :n]

    def conv(self, img):
        n = self.n
        pad = np.zeros((2 * n, 2 * n))
        pad[:n, :n] = img
        out = np.fft.irfft2(np.fft.rfft2(pad) * self.Khat, s=(2 * n, 2 * n))
        return out[:n, :n]

    def wiener(self, raster, Kw):
        n = self.n
        pad = np.zeros((2 * n, 2 * n))
        pad[:n, :n] = raster
        Y = np.fft.rfft2(pad)
        H = self.Khat
        X = np.conj(H) * Y / (np.abs(H) ** 2 + Kw)
        out = np.fft.irfft2(X, s=(2 * n, 2 * n))
        return out[:n, :n]


def noise_sigma(val, ts):
    return np.sqrt((QCOR + QEXO * np.clip(val, 0.0, None)) * ts) / (QEXO * ts)


def make_truth_map(nlat, nlon, seed=7, land_frac=0.30):
    rng = np.random.default_rng(seed)
    def octave(s):
        f = gaussian_filter(rng.standard_normal((nlat, nlon)), s,
                            mode=("nearest", "wrap"))
        return (f - f.mean()) / f.std()
    fld = 1.0 * octave(nlat / 6) + 0.5 * octave(nlat / 14) \
        + 0.25 * octave(nlat / 30)
    fld /= fld.std()
    q = np.quantile(fld, 1.0 - land_frac)
    land = fld > q
    tex = 0.10 * octave(nlat / 20)
    A = np.where(land, 0.32 + tex, 0.06)
    lat = (np.arange(nlat) + 0.5) / nlat * np.pi - np.pi / 2
    polar = np.abs(lat)[:, None] > np.deg2rad(66.0)
    A = np.where(polar & land, 0.60, A)
    A = np.where(polar & ~land, 0.45, A)
    return np.clip(A, 0.02, 0.85)


class CloudModel:
    """Advected Ornstein-Uhlenbeck Gaussian random field -> opacity [0,1]."""

    def __init__(self, nlat, nlon, fc=0.55, tau_days=4.0, u_deg_day=6.0,
                 corr_deg=12.0, seed=101):
        self.nlat, self.nlon = nlat, nlon
        self.fc = fc
        self.tau = tau_days * 86400.0
        self.u = u_deg_day / 86400.0
        self.sig_cells = corr_deg / (180.0 / nlat)
        self.rng = np.random.default_rng(seed)
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
        self.t = 0.0

    def _fresh(self):
        f = gaussian_filter(self.rng.standard_normal((self.nlat, self.nlon)),
                            self.sig_cells, mode=("nearest", "wrap"))
        return (f - f.mean()) / f.std()

    def _advect(self, g, dt):
        cells = self.u * dt / (360.0 / self.nlon)
        k = int(np.floor(cells))
        fr = cells - k
        return (1 - fr) * np.roll(g, k, axis=1) + fr * np.roll(g, k + 1, axis=1)

    def step_to(self, t_new):
        dt = t_new - self.t
        if dt > 0:
            a = np.exp(-dt / self.tau)
            self.g = a * self._advect(self.g, dt) \
                + np.sqrt(1 - a * a) * self._fresh()
            self.t = t_new

    def opacity(self):
        if self.fc <= 0:
            return np.zeros((self.nlat, self.nlon))
        return np.clip((self.g - self.q) / self.w, 0.0, 1.0)


def simulate_dataset(camp, truthF, cloud, sgl, seed=11, nsub=3,
                     record_snapshots=(0, 0.5, 1.0)):
    rng = np.random.default_rng(seed)
    nlatF, nlonF = truthF.shape
    tf = truthF.ravel()
    y = np.zeros(camp.nsamp)
    covers = np.zeros(camp.nbins_tot)
    snaps = []
    snap_marks = [int(f * (camp.nbins_tot - 1)) for f in record_snapshots]
    offs = (np.arange(nsub) - (nsub - 1) / 2) / nsub * camp.ts
    for b in range(camp.nbins_tot):
        t = camp.bins_t[b]
        if cloud is not None and not camp.static:
            cloud.step_to(t)
            op = cloud.opacity()
            covers[b] = op.mean()
            Aeff = (truthF * (1.0 - op) + ACLOUD * op).ravel()
        else:
            op = None
            Aeff = tf
        acc = 0.0
        for dt in offs:
            acc = acc + render_disk(Aeff, sgl.geo, t + dt, nlatF, nlonF,
                                    prot=camp.prot, static=camp.static)
        conv = sgl.conv(acc / nsub)
        pix = camp.bin_pix_all[b]
        s = b * camp.nsc
        y[s:s + camp.nsc] = conv.ravel()[pix]
        if b in snap_marks:
            snaps.append(dict(t=t, scene=(acc / nsub).copy(),
                              conv=conv.copy(),
                              opac=(op.copy() if op is not None else None)))
    sig = noise_sigma(y, camp.ts)
    y_noisy = y + rng.standard_normal(camp.nsamp) * sig
    return dict(y=y_noisy, y_clean=y, sigma=sig, covers=covers, snaps=snaps)


def estimate_cloud_sigma(camp, truthF, sgl, fc, tau_days, seed=999,
                         nprobe=400):
    if fc <= 0:
        return 0.0
    nlatF, nlonF = truthF.shape
    cloud = CloudModel(nlatF, nlonF, fc=fc, tau_days=tau_days, seed=seed)
    rng = np.random.default_rng(seed + 1)
    diffs = []
    for k in range(nprobe):
        t = rng.uniform(0, camp.bins_t[-1])
        cloud.step_to(cloud.t + camp.ts * 20)
        op = cloud.opacity()
        Aeff = (truthF * (1 - op) + ACLOUD * op).ravel()
        d_clean = render_disk(truthF.ravel(), sgl.geo, t, nlatF, nlonF)
        d_cloud = render_disk(Aeff, sgl.geo, t, nlatF, nlonF)
        dv = sgl.conv(d_cloud - d_clean)
        pick = rng.integers(0, camp.n * camp.n, size=8)
        diffs.append(dv.ravel()[pick])
    return float(np.std(np.concatenate(diffs)))


def build_F(camp, sgl, nlat, nlon, prot_assumed=PROT, out=None):
    """Dense forward matrix F (nsamp x nlat*nlon), float32. Pass out= a
    memmapped array to build without holding F in RAM."""
    n = camp.n
    ns = nlat * nlon
    geo = sgl.geo
    Kfull = sgl.K
    latf = geo["lat"].ravel()
    F = np.zeros((camp.nsamp, ns), dtype=np.float32) if out is None else out
    npix = n * n
    for b in range(camp.nbins_tot):
        t = camp.bins_t[b]
        tt = 0.0 if camp.static else t
        lon = (geo["lon0"] + 2.0 * np.pi * tt / prot_assumed).ravel()
        idx4, w4 = bilinear_weights(latf, lon, nlat, nlon)
        mu = illum(geo, tt).ravel() / MU_NORM
        w4m = w4 * mu[:, None]
        rows = np.repeat(np.arange(npix), 4)
        P = sparse.csr_matrix((w4m.ravel(), (rows, idx4.ravel())),
                              shape=(npix, ns))
        pix = camp.bin_pix_all[b]
        jy, jx = pix // n, pix % n
        Krows = np.empty((camp.nsc, npix), dtype=np.float64)
        for k in range(camp.nsc):
            Krows[k] = Kfull[n - jy[k]:2 * n - jy[k],
                             n - jx[k]:2 * n - jx[k]].ravel()
        F[b * camp.nsc:(b + 1) * camp.nsc] = (Krows @ P).astype(np.float32)
    return F


def build_laplacian(nlat, nlon):
    ns = nlat * nlon
    rows, cols, vals = [], [], []
    for a in range(nlat):
        for o in range(nlon):
            i = a * nlon + o
            nb = [a * nlon + (o - 1) % nlon, a * nlon + (o + 1) % nlon]
            if a > 0:
                nb.append((a - 1) * nlon + o)
            if a < nlat - 1:
                nb.append((a + 1) * nlon + o)
            rows += [i] * (len(nb) + 1)
            cols += [i] + nb
            vals += [float(len(nb))] + [-1.0] * len(nb)
    L = sparse.csr_matrix((vals, (rows, cols)), shape=(ns, ns))
    return (L.T @ L).toarray()


def solve_gls(F, y, camp, sigma, sigma_cl, tau_days, lam, LtL,
              white=False, deflate=False, block=256):
    """Covariance-aware regularized GLS for the surface map.
    white=True : clouds treated as white noise (the Toth 2025 assumption).
    white=False: exponential temporal covariance kernel (covariance-aware).
    deflate=True: project out the per-dwell-slot mean (removes the globally
    correlated cloud mode injected by the 1/rho kernel wings)."""
    ns = F.shape[1]
    n2 = camp.n * camp.n
    nb, nsc = camp.nbins_tot, camp.nsc
    tau = tau_days * 86400.0
    if deflate:
        Fbar = np.zeros((nb, ns), dtype=np.float32)
        for b0 in range(0, nb, 512):
            b1 = min(b0 + 512, nb)
            Fbar[b0:b1] = np.asarray(
                F[b0 * nsc:b1 * nsc]).reshape(b1 - b0, nsc, ns).mean(axis=1)
        ybar = y.reshape(nb, nsc).mean(axis=1)
        defl_fac = np.sqrt(1.0 - 1.0 / nsc)
    A = np.zeros((ns, ns), dtype=np.float64)
    bvec = np.zeros(ns, dtype=np.float64)
    sample_bins = np.arange(camp.nsamp) // nsc
    for p0 in range(0, n2, block):
        p1 = min(p0 + block, n2)
        rows_w = []
        y_w = []
        for p in range(p0, p1):
            si = camp.pix_samples[p]
            tt = camp.sample_t[si]
            sg = sigma[si]
            Fp = np.asarray(F[si], dtype=np.float64)
            yp = y[si].copy()
            if deflate:
                bb = sample_bins[si]
                Fp = Fp - Fbar[bb]
                yp = yp - ybar[bb]
                sg = sg * defl_fac
            if white or sigma_cl == 0.0:
                Cd = np.diag(sg**2 + sigma_cl**2)
            else:
                T = np.exp(-np.abs(tt[:, None] - tt[None, :]) / tau)
                Cd = sigma_cl**2 * T + np.diag(sg**2)
            Lc = cholesky(Cd, lower=True)
            rows_w.append(solve_triangular(Lc, Fp, lower=True))
            y_w.append(solve_triangular(Lc, yp, lower=True))
        Fw = np.vstack(rows_w).astype(np.float32)
        yw = np.concatenate(y_w)
        A += (Fw.T @ Fw).astype(np.float64)
        bvec += Fw.T @ yw.astype(np.float32)
    lam_eff = lam * np.trace(A) / np.trace(LtL)
    A += lam_eff * LtL
    s = np.linalg.solve(A, bvec)
    return s


def debias_cloud(map_flat, fc):
    """Remove the known climatological mean-cloud bias."""
    if fc <= 0:
        return map_flat
    return (map_flat - ACLOUD * fc) / (1.0 - fc)


def reconstruct_phasebin(dat, camp, sgl, nlat, nlon, nbins=8, Kw=3e-3):
    """Baseline B2: phase-registered coadds -> Wiener per phase bin ->
    back-projection to the map (simplified emulation of Turyshev 2026)."""
    n = camp.n
    n2 = n * n
    phase = np.mod(camp.sample_t / camp.prot, 1.0)
    binid = np.minimum((phase * nbins).astype(int), nbins - 1)
    geo = sgl.geo
    latf = geo["lat"].ravel()
    acc = np.zeros(nlat * nlon)
    wacc = np.zeros(nlat * nlon)
    for b in range(nbins):
        selb = binid == b
        if not np.any(selb):
            continue
        raster = np.zeros(n2)
        cnt = np.zeros(n2)
        tsum = np.zeros(n2)
        np.add.at(raster, camp.sample_pix[selb], dat["y"][selb])
        np.add.at(cnt, camp.sample_pix[selb], 1.0)
        np.add.at(tsum, camp.sample_pix[selb], camp.sample_t[selb])
        have = cnt > 0
        raster[have] /= cnt[have]
        raster[~have] = raster[have].mean()
        dec = sgl.wiener(raster.reshape(n, n), Kw).ravel()
        t_rep = np.where(have, tsum / np.maximum(cnt, 1), np.nan)
        t_med = np.nanmedian(t_rep)
        t_use = np.where(have, t_rep, t_med)
        lon = (geo["lon0"].ravel() + 2 * np.pi * t_use / camp.prot)
        mu = illum(geo, t_med).ravel()
        idx4, w4 = bilinear_weights(latf, lon, nlat, nlon)
        wgt = (mu * geo["Zc"].ravel() * geo["mask"].ravel())
        est_A = np.where(mu > 0.15, dec * MU_NORM / np.maximum(mu, 0.15), 0.0)
        for k in range(4):
            np.add.at(acc, idx4[:, k], w4[:, k] * wgt * est_A)
            np.add.at(wacc, idx4[:, k], w4[:, k] * wgt)
    return np.where(wacc > 1e-3 * wacc.max(), acc / np.maximum(wacc, 1e-12),
                    0.0)


def static_wiener_image(dat, camp, sgl, Kw=3e-3):
    """Baseline B1: static Wiener inverse of the all-visit mean raster."""
    n2 = camp.n * camp.n
    raster = np.zeros(n2)
    cnt = np.zeros(n2)
    np.add.at(raster, camp.sample_pix, dat["y"])
    np.add.at(cnt, camp.sample_pix, 1.0)
    raster /= np.maximum(cnt, 1)
    return sgl.wiener(raster.reshape(camp.n, camp.n), Kw)


def coarsen(fine, f=2):
    nlat, nlon = fine.shape
    return fine.reshape(nlat // f, f, nlon // f, f).mean(axis=(1, 3))


def ssim_2d(x, y, data_range, sigma=1.5):
    """Gaussian-weighted SSIM (Wang et al. 2004) fallback, mean over map."""
    C1 = (0.01 * data_range) ** 2
    C2 = (0.03 * data_range) ** 2
    f = lambda im: gaussian_filter(im, sigma, mode=("nearest", "wrap"))
    mx, my = f(x), f(y)
    vx = f(x * x) - mx * mx
    vy = f(y * y) - my * my
    cxy = f(x * y) - mx * my
    s = ((2 * mx * my + C1) * (2 * cxy + C2)) / (
        (mx**2 + my**2 + C1) * (vx + vy + C2))
    return float(s.mean())


def eval_map(s_hat, truth_c, lat_max_deg=60.0):
    nlat, nlon = truth_c.shape
    lat = (np.arange(nlat) + 0.5) / nlat * 180.0 - 90.0
    sel = np.abs(lat) <= lat_max_deg
    a = s_hat.reshape(nlat, nlon)[sel]
    b = truth_c[sel]
    rng_b = b.max() - b.min()
    try:
        from skimage.metrics import structural_similarity as ssim_fn
        ssim = float(ssim_fn(b, a, data_range=rng_b))
    except Exception:
        ssim = ssim_2d(b, a, rng_b)
    nrmse = float(np.sqrt(np.mean((a - b) ** 2)) / rng_b)
    r = float(np.corrcoef(a.ravel(), b.ravel())[0, 1])
    return dict(ssim=ssim, nrmse=nrmse, pearson=r)

# end of module
