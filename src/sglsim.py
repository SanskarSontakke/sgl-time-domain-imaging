"""
sglsim -- End-to-end simulation of exoplanet imaging with the solar
gravitational lens (SGL) for a rotating planet with a dynamic (time-varying)
cloud cover, and a covariance-aware joint inversion for the surface map.

Physical conventions follow the published SGL imaging literature:
  * aperture-averaged SGL kernel  K(0)=1, K(rho>0) = d/(4 rho),
    renormalized so the mean convolved disk signal is unity
    (Turyshev & Toth 2020, PRD 102, 024038; Turyshev 2026b, arXiv:2606.14899)
  * fiducial photon rates for an Earth-radius planet at z0 = 30 pc observed
    from z = 650 AU with a d = 1 m telescope at lambda = 1 um:
        Q_exo = 8.01e4 ph/s, Q_cor = 6.20e9 ph/s
    (Turyshev & Toth 2022a, MNRAS 515, 6122)
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

# Operational overhead per dwell slot (s): translation slew, pointing settling,
# inter-spacecraft metrology/synchronization.  These are BUDGET ASSUMPTIONS, not
# a validated trajectory solution -- see Comment 6 of the referee report and
# `kinematic_check()` below, which shows the allocated rest-to-rest time is not
# achievable for the physical raster pitch.
T_SLEW, T_SETTLE, T_SYNC = 30.0, 10.0, 5.0
T_OVERHEAD = T_SLEW + T_SETTLE + T_SYNC


def gauss_legendre_offsets(nsub, ts):
    """Sub-exposure nodes/weights on [-ts/2, ts/2] (Gauss-Legendre).

    The previous implementation used equally spaced nodes, which is not a
    convergent quadrature for the rotational smearing kernel: it reproduces
    neither the zeros nor the sign of the exact response
    H_m = sinc(m*Omega*ts/2) at long dwells.  Gauss-Legendre of order >= 16
    keeps |H_num - H_exact| < 1e-3 for every harmonic m <= 40 at every dwell
    used in this work (see `exposure_quadrature_convergence`).
    """
    x, w = np.polynomial.legendre.leggauss(nsub)
    return 0.5 * ts * x, 0.5 * w


def exposure_response(ts, m, prot=PROT, nsub=None):
    """Rotational-harmonic response of a dwell of length `ts`.

    nsub=None -> exact continuous average sinc(m*Omega*ts/2);
    otherwise the Gauss-Legendre nsub-node approximation actually used.
    """
    Om = 2.0 * np.pi / prot
    if nsub is None:
        x = m * Om * ts / 2.0
        return 1.0 if abs(x) < 1e-14 else np.sin(x) / x
    offs, wts = gauss_legendre_offsets(nsub, ts)
    return float(np.sum(wts * np.cos(m * Om * offs)))


def exposure_quadrature_convergence(ts_list, mmax=40, nsubs=(3, 5, 8, 16, 32)):
    """Max |response error| vs the exact sinc over harmonics m=1..mmax."""
    out = {}
    for nsub in nsubs:
        out[nsub] = [max(abs(exposure_response(ts, m, nsub=nsub)
                              - exposure_response(ts, m))
                         for m in range(1, mmax + 1)) for ts in ts_list]
    return out


def kinematic_check(pitch=DIMG / 64.0, t_avail=T_OVERHEAD):
    """Idealised lower bound on the cost of a raster translation.

    A neighbouring raster position is a *transverse displacement* of `pitch`,
    not merely an angular slew.  For a rest-to-rest maneuver of duration
    `t_avail`, peak speed >= 2*Delta/t (impulsive lower bound), so
    Delta_v >= 2*Delta/t; a symmetric constant-acceleration profile costs
    4*Delta/t and 4*Delta/t^2.
    """
    return dict(pitch_m=pitch, t_avail_s=t_avail,
                dv_lower_ms=2.0 * pitch / t_avail,
                dv_symmetric_ms=4.0 * pitch / t_avail,
                acc_symmetric_ms2=4.0 * pitch / t_avail ** 2)


@dataclass
class Campaign:
    """Observing campaign with an EXPLICIT, resource-consistent time ledger.

    Two mutually exclusive resource conventions are used in this work and are
    named explicitly, because they cannot both hold (referee Comment 6):

      * ``mode="photons"``  -- keep ``mp*ts`` fixed (fixed exposure hours per
        raster position).  The campaign then needs ``nbin*mp*(ts+T_OVERHEAD)``
        of wall clock before any inter-pass gap, which EXCEEDS 90 d for
        large ``mp``.  ``wallclock_days`` reports the true value.
      * ``mode="wallclock"`` -- force the campaign to fit in
        ``wall_target`` days including overheads and gaps, and let the
        per-position exposure ``ts`` FALL.  Photons are then not fixed.

    ``gap_total_s`` is the total inter-pass dead time charged to the ledger
    (split evenly over the ``mp-1`` gaps); it is no longer drawn randomly, so
    the time list is exactly reproducible and auditable.
    """
    n: int = 64
    nsc: int = 16
    ts: float = 1800.0
    mp: int = 16
    gap_max: float = 43200.0        # legacy; ignored unless mode="legacy"
    seed: int = 2026
    static: bool = False
    prot: float = PROT
    mode: str = "photons"
    wall_target: float = 90.0       # days, only used by mode="wallclock"
    gap_total_s: float = 0.0        # total inter-pass dead time, seconds
    overhead: float = T_OVERHEAD

    def __post_init__(self):
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

        if self.mode == "legacy":
            rng = np.random.default_rng(self.seed)
            gaps = rng.uniform(0.0, self.gap_max, size=self.mp)
            gaps[0] = 0.0
            slot_t = (np.arange(self.nbin) + 0.5) * self.ts
            t0 = np.cumsum(gaps) + np.arange(self.mp) * self.nbin * self.ts
        else:
            if self.mode == "wallclock":
                budget = self.wall_target * 86400.0 - self.gap_total_s
                self.ts = max(budget / (self.nbin * self.mp) - self.overhead, 0.0)
                assert self.ts > 0, "wall_target too small for this (n, nsc, mp)"
            elif self.mode != "photons":
                raise ValueError(f"unknown mode {self.mode!r}")
            self.slot_wall = self.ts + self.overhead
            gaps = np.full(self.mp, self.gap_total_s / max(self.mp - 1, 1))
            gaps[0] = 0.0
            if self.mp == 1:
                gaps = np.zeros(1)
            slot_t = (np.arange(self.nbin) + 0.5) * self.ts
            t0 = np.cumsum(gaps) + np.arange(self.mp) * self.nbin * self.slot_wall
        self.bins_t = (t0[:, None] + slot_t[None, :]).ravel()
        self.bin_pix_all = np.tile(self.bin_pix, (self.mp, 1))
        self.sample_pix = self.bin_pix_all.ravel()
        self.sample_t = np.repeat(self.bins_t, self.nsc)
        self.nsamp = self.sample_pix.size
        idx = np.argsort(self.sample_pix, kind="stable")
        self.pix_samples = idx.reshape(n2, self.mp)
        self.exposure_days = self.nbin * self.mp * self.ts / 86400.0
        self.overhead_days = self.nbin * self.mp * self.overhead / 86400.0
        self.gap_days = float(np.sum(gaps)) / 86400.0
        self.wallclock_days = (self.bins_t[-1] + 0.5 * self.ts) / 86400.0
        self.duty_cycle = self.ts / (self.ts + self.overhead)


def disk_geometry(n, theta_pole=0.0, psi_pole=0.0, phi0=0.0):
    """Compute projected visible disk coordinates, latitude, and longitude.
    Supports arbitrary spin pole orientation:
      theta_pole: pole tilt angle toward/away from line of sight (obliquity/inclination)
      psi_pole: sky-plane position angle of rotation axis
      phi0: initial rotational phase offset at t=0
    """
    x = (np.arange(n) + 0.5) / n * 2.0 - 1.0
    X, Y = np.meshgrid(x, x, indexing="xy")
    r2 = X**2 + Y**2
    mask = r2 < 1.0
    Zc = np.sqrt(np.clip(1.0 - r2, 0.0, None))
    if theta_pole == 0.0 and psi_pole == 0.0 and phi0 == 0.0:
        lat = np.arcsin(np.clip(Y, -1, 1))
        lon0 = np.arctan2(X, Zc)
    else:
        # 1. Sky-plane rotation by -psi_pole
        cp, sp = np.cos(psi_pole), np.sin(psi_pole)
        X1 = cp * X + sp * Y
        Y1 = -sp * X + cp * Y
        Z1 = Zc
        # 2. Line-of-sight tilt by -theta_pole (rotation around X1)
        ct, st = np.cos(theta_pole), np.sin(theta_pole)
        Y_prime = ct * Y1 - st * Z1
        Z_prime = st * Y1 + ct * Z1
        lat = np.arcsin(np.clip(Y_prime, -1, 1))
        lon0 = np.arctan2(X1, Z_prime) + phi0
    return dict(n=n, X=X, Y=Y, Zc=Zc, mask=mask, lat=lat, lon0=lon0,
                theta_pole=theta_pole, psi_pole=psi_pole, phi0=phi0)


def illum(geo, t, decl=0.0):
    """Lambert illumination factor: cos of the zenith angle of the star.

    The sub-stellar unit vector in the sky frame (X, Y, Zc) is
        s = (cos(decl) sin(alpha), sin(decl), cos(decl) cos(alpha)),
    with alpha the orbital phase angle.  `decl`=0 reproduces the v2 behaviour,
    in which the sub-stellar point is pinned to the equator and never moves in
    latitude; a nonzero `decl` supplies the seasonal migration that obliquity
    implies, so that illumination and the spin-pole geometry are transformed
    consistently (referee Comment 2).
    """
    alpha = ALPHA0 + 2.0 * np.pi * t / PORB
    cd = np.cos(decl)
    mu = (cd * np.sin(alpha) * geo["X"] + np.sin(decl) * geo["Y"]
          + cd * np.cos(alpha) * geo["Zc"])
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


def render_disk(map_flat, geo, t, nlat, nlon, prot=PROT, static=False,
                theta_pole=None, psi_pole=None, phi0=None):
    if theta_pole is not None or psi_pole is not None or phi0 is not None:
        geo = disk_geometry(geo["n"],
                            theta_pole=0.0 if theta_pole is None else theta_pole,
                            psi_pole=0.0 if psi_pole is None else psi_pole,
                            phi0=0.0 if phi0 is None else phi0)
    tt = 0.0 if static else t
    lon = geo["lon0"] + 2.0 * np.pi * tt / prot
    idx4, w4 = bilinear_weights(geo["lat"].ravel(), lon.ravel(), nlat, nlon)
    A = (map_flat[idx4] * w4).sum(axis=-1).reshape(geo["lat"].shape)
    mu = illum(geo, 0.0 if static else t)
    return A * mu / MU_NORM


def make_kernel(n, pitch, d=DTEL, core="point"):
    """Discrete aperture-averaged SGL kernel.

    core="point"    : v2 behaviour, K(0)=1 with a d/(4 rho) tail.  The central
                      value is a POINT sample of the singular kernel, whereas
                      every other entry is also a point sample of a function
                      whose cell average is far smaller; the resulting
                      diagonal/off-diagonal imbalance is a discretization
                      error that no global renormalization can remove.
    core="cellmean" : the central cell carries the cell AVERAGE of d/(4 rho)
                      over one square raster cell,
                          K00 = d ln(1+sqrt(2)) / pitch,
                      which is the asymptotically correct finite-cell weight
                      (referee eq. R21).
    """
    ax = np.arange(2 * n) - n
    dy, dx = np.meshgrid(ax, ax, indexing="ij")
    rho = pitch * np.hypot(dy, dx)
    with np.errstate(divide="ignore"):
        K = d / (4.0 * rho)
    K[n, n] = 1.0 if core == "point" else d * np.log(1.0 + np.sqrt(2.0)) / pitch
    return K


class SGLOperator:
    def __init__(self, n, pitch=None, d=DTEL, core="point"):
        self.n = n
        self.core = core
        self.pitch = DIMG / n if pitch is None else pitch
        geo = disk_geometry(n)
        Kraw = make_kernel(n, self.pitch, d, core=core)
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


def make_truth_map(nlat, nlon, seed=7, land_frac=0.30, morphology="earthlike"):
    """Generate truth surface albedo map.
    morphology:
      - 'earthlike': fragmented continents, oceans, polar caps
      - 'supercontinent': concentrated single landmass (Pangaea-like)
      - 'archipelago': highly fragmented island chains
    """
    rng = np.random.default_rng(seed)
    def octave(s):
        f = gaussian_filter(rng.standard_normal((nlat, nlon)), s,
                            mode=("nearest", "wrap"))
        return (f - f.mean()) / f.std()
    
    if morphology == "supercontinent":
        fld = 1.8 * octave(nlat / 3) + 0.3 * octave(nlat / 12)
    elif morphology == "archipelago":
        fld = 0.4 * octave(nlat / 6) + 1.2 * octave(nlat / 16) + 0.8 * octave(nlat / 32)
    else: # earthlike
        fld = 1.0 * octave(nlat / 6) + 0.5 * octave(nlat / 14) + 0.25 * octave(nlat / 30)
    
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


class ExtendedCloudModel:
    """Advected Ornstein-Uhlenbeck Gaussian random field with extended
    climatology options:
      - lat_profile: latitudinal cloud banding (ITCZ peak, desert troughs,
        mid-latitude storm tracks)
      - surf_truth, surf_coupling: surface-correlated cloud formation
      - multi_tau: (tau1, tau2, w1) multi-timescale temporal covariance
      - iid_per_pass: temporally independent cloud realizations per pass
    """
    def __init__(self, nlat, nlon, fc=0.55, tau_days=4.0, u_deg_day=6.0,
                 corr_deg=12.0, seed=101, lat_profile=False,
                 surf_truth=None, surf_coupling=0.0,
                 multi_tau=None, iid_per_pass=False):
        self.nlat, self.nlon = nlat, nlon
        self.fc = fc
        self.tau = tau_days * 86400.0
        self.u = u_deg_day / 86400.0
        self.sig_cells = corr_deg / (180.0 / nlat)
        self.rng = np.random.default_rng(seed)
        self.lat_profile = lat_profile
        self.surf_coupling = surf_coupling
        self.multi_tau = multi_tau
        self.iid_per_pass = iid_per_pass
        
        # Latitudinal modulation profile: ITCZ at equator, subtropical dip at 25 deg, storm tracks at 55 deg
        lat = (np.arange(nlat) + 0.5) / nlat * np.pi - np.pi / 2
        if lat_profile:
            self.lat_mod = 1.0 + 0.35 * np.cos(2 * lat) - 0.25 * np.cos(4 * lat)
            self.lat_mod = (self.lat_mod / self.lat_mod.mean())[:, None]
        else:
            self.lat_mod = 1.0
            
        # Surface coupling modulation
        if surf_truth is not None and surf_coupling != 0.0:
            s_norm = (surf_truth - surf_truth.mean()) / (surf_truth.std() + 1e-6)
            self.surf_mod = (-surf_coupling * s_norm)  # lower albedo (ocean) -> higher cloudiness
        else:
            self.surf_mod = 0.0

        self.g = self._fresh()
        if multi_tau is not None:
            self.tau1 = multi_tau[0] * 86400.0
            self.tau2 = multi_tau[1] * 86400.0
            self.w1 = multi_tau[2]
            self.g1 = self._fresh()
            self.g2 = self._fresh()
            self.g = np.sqrt(self.w1) * self.g1 + np.sqrt(1.0 - self.w1) * self.g2

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
        self.last_pass = -1

    def _fresh(self):
        f = gaussian_filter(self.rng.standard_normal((self.nlat, self.nlon)),
                            self.sig_cells, mode=("nearest", "wrap"))
        return (f - f.mean()) / f.std()

    def _advect(self, g, dt):
        cells = self.u * dt / (360.0 / self.nlon)
        k = int(np.floor(cells))
        fr = cells - k
        return (1 - fr) * np.roll(g, k, axis=1) + fr * np.roll(g, k + 1, axis=1)

    def step_to(self, t_new, pass_idx=None):
        dt = t_new - self.t
        if self.iid_per_pass and pass_idx is not None and pass_idx != self.last_pass:
            self.g = self._fresh()
            self.last_pass = pass_idx
            self.t = t_new
            return
        if dt > 0:
            if self.multi_tau is not None:
                a1 = np.exp(-dt / self.tau1)
                a2 = np.exp(-dt / self.tau2)
                self.g1 = a1 * self._advect(self.g1, dt) + np.sqrt(1 - a1 * a1) * self._fresh()
                self.g2 = a2 * self._advect(self.g2, dt) + np.sqrt(1 - a2 * a2) * self._fresh()
                self.g = np.sqrt(self.w1) * self.g1 + np.sqrt(1.0 - self.w1) * self.g2
            else:
                a = np.exp(-dt / self.tau)
                self.g = a * self._advect(self.g, dt) + np.sqrt(1 - a * a) * self._fresh()
            self.t = t_new

    def opacity(self):
        if self.fc <= 0:
            return np.zeros((self.nlat, self.nlon))
        eff_g = (self.g + self.surf_mod) * self.lat_mod
        return np.clip((eff_g - self.q) / self.w, 0.0, 1.0)


def simulate_dataset(camp, truthF, cloud, sgl, seed=11, nsub=3,
                     record_snapshots=(0, 0.5, 1.0),
                     theta_pole=0.0, psi_pole=0.0, phi0=0.0):
    rng = np.random.default_rng(seed)
    nlatF, nlonF = truthF.shape
    tf = truthF.ravel()
    y = np.zeros(camp.nsamp)
    covers = np.zeros(camp.nbins_tot)
    snaps = []
    snap_marks = [int(f * (camp.nbins_tot - 1)) for f in record_snapshots]
    offs, wts = (gauss_legendre_offsets(nsub, camp.ts) if nsub > 1
                 else (np.zeros(1), np.ones(1)))
    geo_use = disk_geometry(camp.n, theta_pole=theta_pole, psi_pole=psi_pole, phi0=phi0)
    for b in range(camp.nbins_tot):
        t = camp.bins_t[b]
        pass_idx = b // camp.nbin
        if cloud is not None and not camp.static:
            if hasattr(cloud, "step_to") and "pass_idx" in cloud.step_to.__code__.co_varnames:
                cloud.step_to(t, pass_idx=pass_idx)
            else:
                cloud.step_to(t)
            op = cloud.opacity()
            covers[b] = op.mean()
            Aeff = (truthF * (1.0 - op) + ACLOUD * op).ravel()
        else:
            op = None
            Aeff = tf
        acc = 0.0
        for dt, wt in zip(offs, wts):
            acc = acc + wt * render_disk(Aeff, geo_use, t + dt, nlatF, nlonF,
                                         prot=camp.prot, static=camp.static)
        conv = sgl.conv(acc)
        pix = camp.bin_pix_all[b]
        s = b * camp.nsc
        y[s:s + camp.nsc] = conv.ravel()[pix]
        if b in snap_marks:
            snaps.append(dict(t=t, scene=acc.copy(),
                              conv=conv.copy(),
                              opac=(op.copy() if op is not None else None)))
    sig = noise_sigma(y, camp.ts)
    y_noisy = y + rng.standard_normal(camp.nsamp) * sig
    return dict(y=y_noisy, y_clean=y, sigma=sig, covers=covers, snaps=snaps)


def estimate_cloud_sigma(camp, truthF, sgl, fc, tau_days, seed=999,
                         nprobe=400, geometry="fixed",
                         corr_deg=12.0, u_deg_day=6.0):
    """Per-sample cloud-induced standard deviation in normalized signal units.

    Two different quantities are commonly conflated (referee Comment 3):

      geometry="fixed"   -- stochastic ensemble variance of the cloudy-minus-
        clean convolved signal at ONE fixed illumination/viewing geometry.
        This is the quantity the working covariance C is meant to represent.
      geometry="varying" -- the v2 behaviour, which also integrates the
        DETERMINISTIC variation of the cloud contrast across illumination
        phase.  That is not stochastic scatter about the ensemble mean and
        inflates sigma_cl.

    The v2 pipeline used "varying"; the revised pipeline uses "fixed" and
    reports both so the difference is auditable.
    """
    if fc <= 0:
        return 0.0
    nlatF, nlonF = truthF.shape
    cloud = CloudModel(nlatF, nlonF, fc=fc, tau_days=tau_days, seed=seed,
                       corr_deg=corr_deg, u_deg_day=u_deg_day)
    rng = np.random.default_rng(seed + 1)
    t_fixed = float(camp.bins_t[0])
    diffs = []
    for k in range(nprobe):
        cloud.step_to(cloud.t + camp.ts * 20)
        op = cloud.opacity()
        Aeff = (truthF * (1 - op) + ACLOUD * op).ravel()
        t = t_fixed if geometry == "fixed" else rng.uniform(0, camp.bins_t[-1])
        d_clean = render_disk(truthF.ravel(), sgl.geo, t, nlatF, nlonF)
        d_cloud = render_disk(Aeff, sgl.geo, t, nlatF, nlonF)
        dv = sgl.conv(d_cloud - d_clean)
        diffs.append(dv.ravel()[rng.integers(0, camp.n * camp.n, size=8)])
    return float(np.std(np.concatenate(diffs)))


def build_F(camp, sgl, nlat, nlon, prot_assumed=PROT, theta_pole=0.0,
            psi_pole=0.0, phi0=0.0, nsub=1, out=None):
    """Dense forward matrix F (nsamp x nlat*nlon), float32. Pass out= a
    memmapped array to build without holding F in RAM.
    nsub: number of sub-exposure integration points per dwell slot
          (defaults to 1; set to 3 to model exposure smear matching data).
    """
    n = camp.n
    ns = nlat * nlon
    geo = (sgl.geo if (theta_pole == 0.0 and psi_pole == 0.0 and phi0 == 0.0)
           else disk_geometry(n, theta_pole=theta_pole, psi_pole=psi_pole, phi0=phi0))
    Kfull = sgl.K
    latf = geo["lat"].ravel()
    F = np.zeros((camp.nsamp, ns), dtype=np.float32) if out is None else out
    npix = n * n
    offs, wts = (gauss_legendre_offsets(nsub, camp.ts) if nsub > 1
                 else (np.zeros(1), np.ones(1)))
    for b in range(camp.nbins_tot):
        t = camp.bins_t[b]
        P_acc = None
        for dt, wt in zip(offs, wts):
            tt = 0.0 if camp.static else (t + dt)
            lon = (geo["lon0"] + 2.0 * np.pi * tt / prot_assumed).ravel()
            idx4, w4 = bilinear_weights(latf, lon, nlat, nlon)
            mu = illum(geo, tt).ravel() / MU_NORM
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


def _pixel_cov(tt, sg, sigma_cl, tau, white):
    """Working covariance for the Mp visits of one image-plane pixel."""
    if white or sigma_cl == 0.0:
        return np.diag(sg ** 2 + sigma_cl ** 2)
    T = np.exp(-np.abs(tt[:, None] - tt[None, :]) / tau)
    return sigma_cl ** 2 * T + np.diag(sg ** 2)


def effective_independent_looks(ts, mp, tau_days, nbin=None, camp=None,
                                overhead=None):
    """Number of statistically INDEPENDENT cloud looks among the ``mp`` revisits
    of one raster position.

    Revisits of a fixed image-plane pixel are separated by the FULL pass time
    ``nbin * (ts + T_OVERHEAD)`` -- not by ``ts`` -- because the raster must be
    traversed once between looks.  With an OU cloud field of correlation time
    ``tau``, lag k has correlation ``rho_k = exp(-k*dt/tau)``, and

        Var(mean) = sigma^2/mp^2 * [mp + 2 sum_{k=1}^{mp-1} (mp-k) rho_k]
                  = sigma^2 / N_eff,

    so ``N_eff = mp^2 / (mp + 2 sum_k (mp-k) rho_k)``.  The (mp-k) pair weight is
    not optional: omitting it understates the correlated variance by a factor
    that grows with mp, which would wrongly suggest that even mp = 64 revisits
    are effectively independent.
    """
    if camp is None:
        camp = Campaign(ts=ts, mp=mp)
    nbin = camp.nbin if nbin is None else nbin
    overhead = T_OVERHEAD if overhead is None else overhead
    dt = (camp.ts + overhead) * nbin / 86400.0
    k = np.arange(1, camp.mp)
    rho = np.exp(-k * dt / tau_days)
    pair = float(np.sum((camp.mp - k) * rho))
    return dict(spacing_days=float(dt), rho_lag1=float(rho[0]) if mp > 1 else 1.0,
                n_eff=float(camp.mp ** 2 / (camp.mp + 2.0 * pair)),
                mp=int(camp.mp), fraction=float(camp.mp ** 2 / (camp.mp + 2.0 * pair)
                                               / camp.mp))


def raster_stack(camp):
    """Cached index/time helpers for batched assembly over raster positions.

    Sample index of (pass k, raster position j, slot member q) is
    (k*nbin + j)*nsc + q, and the pixel it reads is bin_pix[j, q].  Both were
    verified against Campaign.pix_samples for every mode.  The inter-pass time
    offsets dt[k, k', j] depend on the slot time inside a pass, so they are
    stored per raster position.
    """
    key = (camp.n, camp.nsc, camp.mp, camp.ts, camp.mode, camp.gap_total_s,
           camp.seed, camp.static)
    st = getattr(raster_stack, "_cache", {})
    if key in st:
        return st[key]
    nbin, mp, nsc = camp.nbin, camp.mp, camp.nsc
    idx = ((np.arange(mp)[:, None, None] * nbin
            + np.arange(nbin)[None, :, None]) * nsc
           + np.arange(nsc)[None, None, :])
    bt = camp.bins_t.reshape(mp, nbin)
    dt = bt[:, None, :] - bt[None, :, :]
    # sample (k, j, q) reads pixel bin_pix[j, q]; its mp partners over k are one
    # image-plane pixel, which is the covariance block assembled below.
    assert np.array_equal(camp.sample_pix,
                          np.tile(camp.bin_pix, (mp, 1)).ravel())
    assert np.array_equal(idx.ravel(), np.arange(mp * nbin * nsc))
    st[key] = dict(idx=idx, dt=dt)
    raster_stack._cache = st
    return st[key]


def solve_gls(F, y, camp, sigma, sigma_cl, tau_days, lam, LtL,
              white=False, deflate=False, block=256, return_cov=False):
    """Covariance-aware regularized GLS for the surface map.

    deflate=True uses the ORIGINAL approximate procedure (subtract the
    per-slot mean of F and y and rescale the marginal noise by
    sqrt(1-1/N_sc)).  Kept only so the published v2 numbers remain
    reproducible; it is NOT statistically exact -- see solve_gls_profiled.
    """
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
            Cd = _pixel_cov(tt, sg, sigma_cl, tau, white)
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
    if return_cov:
        return s, np.linalg.inv(A)
    return s


def solve_gls_profiled(F, y, camp, sigma, sigma_cl, tau_days, lam, LtL,
                       white=False, deflate=True, anchor=True, jchunk=None,
                       return_diag=False, chunk_mb=220.0):
    """Regularized GLS with EXACT slot-offset nuisance profiling.

    Model:  y = F s + B alpha + eps,  B = per-dwell-slot indicator columns,
    eps ~ N(0, C) with C block diagonal over IMAGE-PLANE PIXELS (the working
    covariance).  The block for pixel p holds its ``mp`` samples, one per
    pass, and those samples sit in ``mp`` DIFFERENT slots (bin index
    k*nbin + j, where j is the raster position of p).  Consequently

        H = B^T C^-1 B

    is block diagonal with nbin blocks of size mp x mp (one per raster
    position), NOT diagonal -- slots are coupled through the shared temporal
    cloud covariance of a single pixel.  Profiling alpha (referee eq. R11)
    therefore requires inverting those mp x mp blocks.  With

        G_j = B_j^T C^-1 F,   g_j = B_j^T C^-1 y,   H_j = B_j^T C^-1 B_j,
        v_j = H_j^-1 1_mp,    q = sum_j G_j^T v_j,   S = sum_j 1_mp^T v_j,
        m = sum_j v_j^T g_j,

    the free (unconstrained) profile gives

        A_free = F^T C^-1 F - sum_j G_j^T H_j^-1 G_j,
        b_free = F^T C^-1 y - sum_j G_j^T H_j^-1 g_j.

    ANCHORING.  A small print of the v2 discussion said the offsets "remove
    6.25% of the rank".  Both before and after profiling the normal matrix here
    has the SAME nullity (the unobservable polar cap of the equirectangular
    basis), so slot profiling removes NO rank at all -- see
    profiling_information_audit.  What it does remove is the RESPONSE along the
    mean-albedo direction: the constant-mode gain ||A 1||/||1|| falls by a
    factor ~49 at the fiducial campaign.  (The identity W_perp B = 0 is exact
    and trivial for a profile likelihood; it is NOT evidence of a surface-mode
    degeneracy, and an earlier version of this module confused the two.)  The
    offsets therefore have to be ANCHORED rather than merely projected out, and
    with the standard sum_b alpha_b = 0 constraint the Lagrange system collapses
    to a rank-one correction

        A = A_free + q q^T / S,     b = b_free + q m / S,

    which is exact and costs nothing beyond the block inversions already done.
    anchor=False reproduces the un-anchored projection (the mean-albedo mode is
    then heavily attenuated); it is exposed so the two can be compared directly.
    """
    ns = F.shape[1]
    nbin, mp, nsc = camp.nbin, camp.mp, camp.nsc
    tau = tau_days * 86400.0
    st = raster_stack(camp)
    idx, dtabs = st["idx"], st["dt"]                    # (mp,nbin,nsc), (mp,mp,nbin)
    di = np.arange(mp)
    A0 = np.zeros((ns, ns))
    b0 = np.zeros(ns)
    qvec = np.zeros(ns) if (deflate and anchor) else None
    S_tot = 0.0
    m_tot = 0.0
    if jchunk is None:
        # Size the raster-position chunk so the transient (cj, nsc, mp, ns)
        # float64 tensors stay under chunk_mb; the products are BLAS-bound, so
        # anything from 32 to 256 positions gives the same ~4 s at n = 64.
        per_pos = nsc * mp * ns * 8.0 * 4.0
        jchunk = max(8, min(nbin, int(chunk_mb * 1e6 // per_pos)))
    for j0 in range(0, nbin, jchunk):
        j1 = min(j0 + jchunk, nbin)
        cj = j1 - j0
        # Every product below is either a batched (mp x mp) x (mp x ns) matmul or
        # a single 2-D gemm, so that the ns x ns accumulation runs at BLAS speed;
        # einsum is deliberately avoided (it fell back to an elementwise loop and
        # made the fiducial solve intractable).
        rows = idx[:, j0:j1, :].reshape(-1)             # (mp*cj*nsc,)
        sgT = np.ascontiguousarray(
            sigma[idx[:, j0:j1]].transpose(1, 2, 0), dtype=np.float64)   # (cj,nsc,mp)
        yT = np.ascontiguousarray(y[idx[:, j0:j1]].transpose(1, 2, 0),
                                  dtype=np.float64)                      # (cj,nsc,mp)
        Fq = np.ascontiguousarray(
            np.asarray(F[rows]).reshape(mp, cj, nsc, ns).transpose(1, 2, 0, 3),
            dtype=np.float64)                            # (cj,nsc,mp,ns)
        if white or sigma_cl == 0.0:
            Ci = np.zeros((cj, nsc, mp, mp))
            Ci[:, :, di, di] = 1.0 / (sgT ** 2 + (sigma_cl ** 2 if white else 0.0))
        else:
            # the mp samples of one image-plane pixel sit at the SAME slot
            # position in every pass, so the OU correlation depends on the
            # raster position j only, not on the slot member q.
            corr = np.exp(-np.abs(dtabs[:, :, j0:j1]) / tau).transpose(2, 0, 1)
            var = np.broadcast_to(sigma_cl ** 2 * corr[:, None],
                                  (cj, nsc, mp, mp)).copy()
            var[:, :, di, di] += sgT ** 2
            Ci = np.linalg.inv(var)                                   # (cj,nsc,mp,mp)
        Cf = np.matmul(Ci, Fq)                                       # (cj,nsc,mp,ns)
        Cy = np.matmul(Ci, yT[:, :, :, None])[:, :, :, 0]            # (cj,nsc,mp)
        Fq2 = Fq.reshape(cj * nsc * mp, ns)
        A0 += Fq2.T @ Cf.reshape(cj * nsc * mp, ns)
        b0 += Fq2.T @ Cy.reshape(cj * nsc * mp)
        del Fq, Fq2
        if not deflate:
            continue
        Hj = Ci.sum(axis=1)                             # (cj, mp, mp) = B^T C^-1 B
        Gj = Cf.sum(axis=1)                             # (cj, mp, ns)
        gj = Cy.sum(axis=1)                             # (cj, mp)
        del Ci, Cf, Cy
        Sj = np.linalg.inv(Hj)
        Gj2 = Gj.reshape(cj * mp, ns)
        A0 -= Gj2.T @ np.matmul(Sj, Gj).reshape(cj * mp, ns)
        b0 -= Gj2.T @ np.matmul(Sj, gj[:, :, None]).reshape(cj * mp)
        if anchor:
            v1 = Sj.sum(axis=2).reshape(cj * mp)        # H_j^-1 1_mp
            S_tot += float(Sj.sum())
            qvec += Gj2.T @ v1
            m_tot += float(v1 @ gj.ravel())
    A, b = A0, b0
    if deflate and anchor:
        A = A + np.outer(qvec, qvec) / S_tot
        b = b + qvec * (m_tot / S_tot)
    lam_eff = lam * np.trace(A) / np.trace(LtL)
    A = A + lam_eff * LtL
    s = np.linalg.solve(A, b)
    if return_diag:
        return s, dict(lam_eff=lam_eff, A=A, b=b, eig=np.linalg.eigvalsh(A),
                       cond=float(np.linalg.cond(A)))
    return s


def whitened_chi2(F, y, camp, sigma, sigma_cl, tau_days, s, white=False):
    """chi^2 = sum_p r_p^T C_p^-1 r_p  with  r_p = y_p - F_p s.

    The mp x mp covariance blocks are assembled in the SAME batched layout the
    profiler uses, so the whole sum costs one batched inversion plus a few
    matrix products instead of n^2 Python loops (the loop version takes minutes
    per grid point and made the profile-likelihood grid infeasible).
    """
    tau = tau_days * 86400.0
    nbin, mp, nsc = camp.nbin, camp.mp, camp.nsc
    ns = F.shape[1]
    st = raster_stack(camp)
    idx, dtabs = st["idx"], st["dt"]
    # F rows are in (pass k, raster position j, slot member q) order, so a plain
    # reshape is a free view; only the float64 CHUNKS are materialised.
    Fv = np.asarray(F, np.float32).reshape(mp, nbin, nsc, ns)
    yv = np.asarray(y, np.float64).reshape(mp, nbin, nsc)
    sv = np.asarray(s, np.float64)
    r = np.empty((mp, nbin, nsc), dtype=np.float64)
    for j0 in range(0, nbin, 32):
        j1 = min(j0 + 32, nbin)
        Fc = np.asarray(Fv[:, j0:j1], np.float64).reshape(mp, -1, ns)
        r[:, j0:j1] = yv[:, j0:j1] - np.matmul(Fc, sv).reshape(mp, j1 - j0, nsc)
    # samples (k, j, q) over k are one image-plane pixel -> the mp x mp block
    rt = np.ascontiguousarray(r.transpose(1, 2, 0)[:, :, :, None])  # (nbin,nsc,mp,1)
    sg2 = np.asarray(sigma, np.float64)[idx].transpose(1, 2, 0) ** 2
    if white or sigma_cl == 0.0:
        iv = 1.0 / (sg2 + (sigma_cl ** 2 if white else 0.0))
        return float((iv * rt[:, :, :, 0] ** 2).sum())
    corr = np.exp(-np.abs(dtabs) / tau).transpose(2, 0, 1)       # (nbin,mp,mp)
    var = np.broadcast_to(sigma_cl ** 2 * corr[:, None],
                          (nbin, nsc, mp, mp)).copy()
    di = np.arange(mp)
    var[:, :, di, di] += sg2
    Cr = np.linalg.solve(var, rt)[:, :, :, 0]
    return float((Cr * rt[:, :, :, 0]).sum())


def deflation_diagnostics(F, camp, sigma, sigma_cl, tau_days, white=False):
    """Mode-dependent diagnostics that replace the '6.25% rank / 93.75%
    information' claim, which is not a statement about surface information.

    Reports, for the ACTUAL sampling groups:
      * how many scalar directions the slot projection removes;
      * whether the constant surface mode survives (||P F 1|| / ||F 1||);
      * the rank and spectrum of the (regularized) deflated normal matrix;
      * the alignment between the dominant cloud-covariance direction and the
        per-slot all-ones vector that the projection removes.
    """
    ns = F.shape[1]
    nb, nsc = camp.nbins_tot, camp.nsc
    ones = np.ones(ns)
    # Chunked accumulation: F at n=64 is 0.68 GB float32, and materialising it
    # twice in float64 plus the deflated copy exceeds the memory a paper
    # reproducibility container should need.
    A_und = np.zeros((ns, ns))
    A_def = np.zeros((ns, ns))
    n1_und = 0.0
    n1_def = 0.0
    step = max(1, int(2e7 // (nsc * ns)))          # ~20 MB of float64 per chunk
    for b0 in range(0, nb, step):
        b1 = min(b0 + step, nb)
        Fb = np.asarray(F[b0 * nsc:b1 * nsc], dtype=np.float64).reshape(b1 - b0,
                                                                        nsc, ns)
        Fbar = Fb.mean(axis=1, keepdims=True)
        Fc = Fb.reshape(-1, ns)
        Fd = (Fb - Fbar).reshape(-1, ns)
        A_und += Fc.T @ Fc
        A_def += Fd.T @ Fd
        F1 = Fb @ ones
        n1_und += float((F1 ** 2).sum())
        n1_def += float(((F1 - F1.mean(axis=1, keepdims=True)) ** 2).sum())
    survive = float(np.sqrt(n1_def / n1_und))
    ev_und = np.linalg.eigvalsh(A_und)
    ev_def = np.linalg.eigvalsh(A_def)
    tol = max(A_def.shape) * max(ev_def.max(), 1.0) * 1e-12
    frob = float(np.trace(A_def) / np.trace(A_und))
    return dict(removed_directions=int(nb), nsc=int(nsc),
                ns=int(ns), nsamp=int(nb * nsc),
                constant_mode_survival=survive,
                rank_undef=int(np.sum(ev_und > tol)), rank_defl=int(np.sum(ev_def > tol)),
                frobenius_ratio=frob,
                ev_defl_top5=ev_def[-5:][::-1].tolist(),
                ev_defl_smallest_nonzero=float(ev_def[ev_def > tol].min())
                if np.any(ev_def > tol) else 0.0)


def whitened_normal(F, camp, sigma, sigma_cl, tau_days, white=False, chunk=64):
    """A = F^T C^-1 F, assembled in the same batched pixel-block layout the
    profiler uses (no regularization, no profiling)."""
    ns = F.shape[1]
    nbin, mp, nsc = camp.nbin, camp.mp, camp.nsc
    tau = tau_days * 86400.0
    st = raster_stack(camp)
    idx, dtabs = st["idx"], st["dt"]
    di = np.arange(mp)
    A = np.zeros((ns, ns))
    for j0 in range(0, nbin, chunk):
        j1 = min(j0 + chunk, nbin)
        cj = j1 - j0
        sgT = np.ascontiguousarray(np.asarray(sigma, float)[idx[:, j0:j1]]
                                   .transpose(1, 2, 0))
        Fq = np.ascontiguousarray(
            np.asarray(F[idx[:, j0:j1]]).reshape(mp, cj, nsc, ns)
            .transpose(1, 2, 0, 3), dtype=np.float64)
        if white or sigma_cl == 0.0:
            Ci = np.zeros((cj, nsc, mp, mp))
            Ci[:, :, di, di] = 1.0 / (sgT ** 2 + (sigma_cl ** 2 if white else 0.0))
        else:
            corr = np.exp(-np.abs(dtabs[:, :, j0:j1]) / tau).transpose(2, 0, 1)
            var = np.broadcast_to(sigma_cl ** 2 * corr[:, None],
                                  (cj, nsc, mp, mp)).copy()
            var[:, :, di, di] += sgT ** 2
            Ci = np.linalg.inv(var)
        F2 = Fq.reshape(cj * nsc * mp, ns)
        A += F2.T @ np.matmul(Ci, Fq).reshape(cj * nsc * mp, ns)
    return A


def profiling_information_audit(F, camp, sigma, sigma_cl, tau_days, lam, LtL,
                                nlon=None):
    """What slot-offset profiling actually costs, replacing the v2 claim that
    deflation "removes 6.25% of the rank and preserves 93.75% of the
    information".

    That sentence was wrong in three ways, and the corrections matter:

      1. It counted SCALAR directions (one per dwell slot) against a surface
         basis, which is not a statement about surface information at all.
      2. The un-profiled design matrix is ALREADY rank deficient here, by
         ``nullity_unprofiled`` directions, because the polar latitude cells of
         the equirectangular basis are never sampled by a circular raster.
         Profiling removes no further rank at all.
      3. What profiling does remove is the response of the normal matrix to the
         CONSTANT surface mode -- the mean-albedo direction -- and it removes
         far more than 6.25% of it.  The ratio of constant-mode gains below is
         the honest version of the number, and it is why the offsets must be
         ANCHORED (sum_b alpha_b = 0) rather than merely projected out.

    Returns the gains, nullities, and the overlap between the null space and the
    constant mode for the un-profiled, free-profiled and anchored matrices.
    """
    ns = F.shape[1]
    nlon = int(nlon or ns)
    ones = np.ones(ns)
    A_und = whitened_normal(F, camp, sigma, sigma_cl, tau_days)
    diag = {}
    for tag, kw in (("unprofiled", None),
                    ("free", dict(anchor=False)),
                    ("anchored", dict(anchor=True))):
        if kw is None:
            A = A_und
            lam_eff = lam * np.trace(A_und) / np.trace(LtL)
        else:
            _, d = solve_gls_profiled(F, np.zeros(camp.nsamp), camp, sigma,
                                      sigma_cl, tau_days, lam, LtL,
                                      return_diag=True, **kw)
            lam_eff = d["lam_eff"]
            A = d["A"] - lam_eff * LtL
        ev, V = np.linalg.eigh(A)
        scale = float(ev.max())
        nullity = int(np.sum(np.abs(ev) < 1e-8 * scale))
        O = V[:, :nullity] if nullity else np.zeros((ns, 0))
        diag[tag] = dict(
            nullity=nullity,
            eig_min=float(ev[0]), eig_max=scale,
            constant_mode_gain=float(np.linalg.norm(A @ ones) / np.linalg.norm(ones)),
            null_const_overlap=float(np.linalg.norm(O.T @ ones) / np.linalg.norm(ones)),
            lam_eff=float(lam_eff))
    g = diag["unprofiled"]["constant_mode_gain"]
    diag["retained_fraction_free"] = diag["free"]["constant_mode_gain"] / g
    diag["retained_fraction_anchored"] = diag["anchored"]["constant_mode_gain"] / g
    # the null space is the polar cap of the equirectangular basis, which the
    # circular image-plane raster never samples; report that explicitly.
    col = np.sqrt((np.asarray(F, np.float32) ** 2).sum(axis=0))
    dead = np.where(col < 1e-12 * max(col.max(), 1e-30))[0]
    rows = sorted({int(i) // nlon for i in dead}) if nlon else []
    diag["zero_columns"] = int(dead.size)
    diag["zero_column_lat_rows"] = rows
    diag["nullity_note"] = ("the un-profiled null space is a property of the grid "
                            "and the circular raster, not of the nuisance "
                            "profiling; profiling adds no null directions")
    return diag


def debias_cloud(map_flat, fc):
    """Remove the known climatological mean-cloud bias."""
    if fc <= 0:
        return map_flat
    return (map_flat - ACLOUD * fc) / (1.0 - fc)


def debias_cloud_err(map_flat, fc_true, delta_fc=0.0, delta_acl=0.0):
    """Debias surface map with potentially misestimated cloud fraction or albedo."""
    fc_assumed = np.clip(fc_true + delta_fc, 0.0, 0.95)
    acl_assumed = np.clip(ACLOUD + delta_acl, 0.05, 0.95)
    if fc_assumed <= 0:
        return map_flat
    return (map_flat - acl_assumed * fc_assumed) / (1.0 - fc_assumed)


def reconstruct_phasebin(dat, camp, sgl, nlat, nlon, nbins=8, Kw=3e-3):
    """Baseline B2: phase-registered coadds -> Wiener per phase bin ->
    back-projection to the map (simplified emulation of Turyshev 2026b)."""
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


def real_sphalm_basis(nlat, nlon, lmax):
    """Orthonormal real spherical harmonics Y_lm sampled at cell centres of an
    nlat x nlon equal-area-in-longitude grid, plus the solid-angle weights.

    Replaces the 2D-FFT wavenumber proxy, which is NOT spherical harmonic
    degree: on an equirectangular grid the longitude cells are not equal area,
    the map is periodic in longitude but not in latitude, and the index
    hypot(ky,kx) has no reason to coincide with l (referee Comment 8).
    """
    from scipy.special import lpmv, gammaln
    lat = (np.arange(nlat) + 0.5) / nlat * np.pi - np.pi / 2.0
    lon = (np.arange(nlon) + 0.5) / nlon * 2.0 * np.pi
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    dlat = np.pi / nlat
    dlon = 2.0 * np.pi / nlon
    w = np.cos(LA) * dlat * dlon                     # solid angle per cell
    basis = {}
    for l in range(lmax + 1):
        for m in range(l + 1):
            lnrm = 0.5 * (gammaln(l - m + 1) - gammaln(l + m + 1)) \
                   + 0.5 * np.log((2 * l + 1) / (4.0 * np.pi))
            norm = np.exp(lnrm)
            P = lpmv(m, l, np.sin(LA))
            if m == 0:
                Y = norm * P
            else:
                Y = norm * np.sqrt(2.0) * P * np.cos(m * LO)
            basis[(l, m, "c")] = Y
            if m > 0:
                basis[(l, m, "s")] = norm * np.sqrt(2.0) * P * np.sin(m * LO)
    return basis, w


def sphalm_transform(map_2d, basis, w):
    return {k: float(np.sum(map_2d * Y * w)) for k, Y in basis.items()}


def scale_dependent_correlation(map_est, map_truth, nlat=36, nlon=72, lmax=20,
                                basis=None, w=None):
    """r(l) from real spherical-harmonic band powers (area-weighted)."""
    if basis is None:
        basis, w = real_sphalm_basis(nlat, nlon, lmax)
    me = np.asarray(map_est).reshape(nlat, nlon)
    mt = np.asarray(map_truth).reshape(nlat, nlon)
    ae = sphalm_transform(me, basis, w)
    at = sphalm_transform(mt, basis, w)
    degrees = np.arange(1, lmax + 1)
    r_l = np.zeros(len(degrees))
    for i, l in enumerate(degrees):
        num = den_e = den_t = 0.0
        for m in range(l + 1):
            for kind in (("c", "s") if m else ("c",)):
                e = ae[(l, m, kind)]
                t = at[(l, m, kind)]
                num += e * t
                den_e += e * e
                den_t += t * t
        r_l[i] = num / np.sqrt(den_e * den_t) if (
            den_e > 1e-24 and den_t > 1e-24) else np.nan
    return degrees, r_l


def harmonic_quadrature_error(nlat, nlon, lmax):
    """Diagonal quadrature error of the discrete Y_lm basis.

    On a 36 x 72 grid the solid-angle quadrature is only marginally adequate
    at high degree, so any statement about a measured limiting resolution must
    be bounded by this error.  Returns max |<Y_lm,Y_lm> - 1| over l <= lmax.
    """
    basis, w = real_sphalm_basis(nlat, nlon, lmax)
    errs = {}
    for l in range(lmax + 1):
        e = 0.0
        for m in range(l + 1):
            for kind in (("c", "s") if m else ("c",)):
                e = max(e, abs(float(np.sum(basis[(l, m, kind)]
                                            * basis[(l, m, kind)] * w)) - 1.0))
        errs[l] = e
    return errs


def harmonic_l_to_scale_km(l, r_earth=6371.0):
    """Two conventions the paper must choose between explicitly."""
    return dict(half_wavelength_km=np.pi * r_earth / max(l, 1),
                full_wavelength_km=2.0 * np.pi * r_earth / max(l, 1))


def detection_dprime(map_est, map_truth, lat_max_deg=60.0):
    """Compute detection separation d' between true land and ocean pixels."""
    nlat, nlon = map_truth.shape
    lat = (np.arange(nlat) + 0.5) / nlat * 180.0 - 90.0
    sel = np.abs(lat) <= lat_max_deg
    me = map_est.reshape(nlat, nlon)[sel]
    mt = map_truth[sel]
    land_mask = mt > 0.15
    ocean_mask = ~land_mask
    if not np.any(land_mask) or not np.any(ocean_mask):
        return 0.0
    mu_l = me[land_mask].mean()
    mu_o = me[ocean_mask].mean()
    var_l = me[land_mask].var()
    var_o = me[ocean_mask].var()
    pooled_std = np.sqrt(0.5 * (var_l + var_o) + 1e-12)
    return float((mu_l - mu_o) / pooled_std)


def label_permutation_dprime(map_est, truth_labels, n_perm=1000, seed=0,
                             lat_max_deg=60.0):
    """Label-permutation null for the land--ocean statistic.

    NOTE what this does and does not test: it asks whether the reconstructed
    map's own two-group separation is unusual when the injected class labels
    are randomly reassigned.  It is a test of the LABELLING, not of detection
    against a physical null, and it is not the right null for a claim that the
    instrument detected continents.  For that, use `cloud_only_null_dprime`.
    """
    rng = np.random.default_rng(seed)
    nlat, nlon = truth_labels.shape
    lat = (np.arange(nlat) + 0.5) / nlat * 180.0 - 90.0
    sel = np.abs(lat) <= lat_max_deg
    me = np.asarray(map_est).reshape(nlat, nlon)[sel].ravel()
    lab = truth_labels[sel].ravel().astype(bool)
    obs = _dprime_from(me, lab)
    null = np.empty(n_perm)
    n_land = int(lab.sum())
    for k in range(n_perm):
        idx = rng.permutation(lab.size)[:n_land]
        l2 = np.zeros(lab.size, dtype=bool)
        l2[idx] = True
        null[k] = _dprime_from(me, l2)
    return dict(observed=obs, null=null,
                p_rank=(1.0 + float(np.sum(null >= obs))) / (n_perm + 1.0))


def _dprime_from(vals, lab):
    if lab.all() or not lab.any():
        return 0.0
    a, b = vals[lab], vals[~lab]
    pooled = np.sqrt(0.5 * (a.var() + b.var()) + 1e-12)
    return float((a.mean() - b.mean()) / pooled)


def phase_scrambled_null(map_2d, seed=42):
    """DEPRECATED surrogate: Fourier phase scrambling on an equirectangular
    grid.  It ignores the cos(lat) cell areas, does not respect the sphere, and
    contains neither photon noise nor the reconstruction operator, so it is not
    a null for any detection statistic reported in the paper.  Retained only so
    the v2 numbers remain reproducible."""
    rng = np.random.default_rng(seed)
    F = np.fft.rfft2(map_2d)
    mag = np.abs(F)
    random_phases = rng.uniform(0, 2 * np.pi, size=F.shape)
    random_phases[0, 0] = 0.0
    F_null = mag * np.exp(1j * random_phases)
    surrogate = np.fft.irfft2(F_null, s=map_2d.shape)
    surrogate = (surrogate - surrogate.mean()) / (surrogate.std() + 1e-12) * map_2d.std() + map_2d.mean()
    return surrogate


def analyze_deflation(camp, sgl, nlat=36, nlon=72):
    """Demonstrate linear algebra properties of slot deflation:
    rank reduction, condition number change, and information retention."""
    camp_1p = Campaign(n=camp.n, nsc=camp.nsc, ts=camp.ts, mp=1, seed=camp.seed)
    F1 = build_F(camp_1p, sgl, nlat, nlon)
    ns = nlat * nlon
    nb = camp_1p.nbins_tot
    nsc = camp_1p.nsc
    
    A_undef = F1.T @ F1
    cond_undef = float(np.linalg.cond(A_undef))
    
    Fbar = np.zeros((nb, ns), dtype=np.float32)
    for b in range(nb):
        Fbar[b] = F1[b * nsc:(b + 1) * nsc].mean(axis=0)
    F_defl = F1 - np.repeat(Fbar, nsc, axis=0)
    A_defl = F_defl.T @ F_defl
    cond_defl = float(np.linalg.cond(A_defl))
    
    tr_undef = float(np.trace(A_undef))
    tr_defl = float(np.trace(A_defl))
    info_retained = tr_defl / tr_undef
    
    return dict(cond_undef=cond_undef, cond_defl=cond_defl,
                info_retained=info_retained, nsc=nsc,
                theoretical_retention=1.0 - 1.0 / nsc)


def inject_systematics(y, camp, drift_amp=1e-4, streamer_amp=1e-4, seed=77,
                        streamer_tau_days=30.0, spatial_scale_cells=8.0,
                        units="planet"):
    """Inject the two systematics Section 5.5 names, with the convention the
    referee asked to see stated explicitly (R22).

    UNITS.  ``y`` is the normalized planet photocentre signal, so a fractional
    residual eps of the BRIGHT coronal background enters as

        delta_y = eps * Q_cor / Q_exo = 7.7403e4 * eps   (planet units)

    -- not as eps itself.  ``units="coronal"`` therefore multiplies the given
    amplitudes by QCOR/QEXO; ``units="planet"`` takes them literally.  The v2
    injection used raw ~1e-4 amplitudes on y, i.e. it injected a fractional
    error of the PLANET signal, which is ~7.7e4 times too small to represent a
    coronal residual.

    TEMPLATES.
      * instrumental gain drift: a smooth, fully coherent multiplicative ramp
        across the campaign, 1 + eps * (2u-1 + (2u-1)^2/2), u = t/t_end.  Coherent
        with the signal, so revisits do NOT decorrelate it.
      * coronal streamer residual: a slowly rotating low-spatial-frequency
        pattern, amplitude eps, scale `spatial_scale_cells` image-plane pixels,
        evolving with an exponential correlation time `streamer_tau_days` --
        drawn as a smooth random field, not white noise.
    """
    rng = np.random.default_rng(seed)
    scale = (QCOR / QEXO) if units == "coronal" else 1.0
    u = camp.sample_t / camp.bins_t[-1]
    gain_drift = 1.0 + scale * drift_amp * (2.0 * u - 1.0 + 0.5 * (2.0 * u - 1.0) ** 2)
    n = camp.n
    px = (camp.sample_pix % n).astype(float)
    py = (camp.sample_pix // n).astype(float)
    tt = camp.sample_t
    tau = streamer_tau_days * 86400.0
    lam_xy = max(n / float(spatial_scale_cells), 1.0)   # modes ~8 cells across
    k = np.arange(1, 4)
    cx = np.pi * k[:, None] * px[None, :] / lam_xy
    cy = np.pi * k[:, None] * py[None, :] / lam_xy
    pat = np.zeros(camp.nsamp)
    for a in range(3):
        for b in range(3):
            for fx in (np.sin(cx[a]), np.cos(cx[a])):
                ph = rng.uniform(0.0, 2.0 * np.pi)
                per = tau * rng.uniform(0.5, 2.0)
                pat += fx * np.sin(cy[b]) * np.cos(2.0 * np.pi * tt / per + ph)
    pat /= max(float(np.abs(pat).max()), 1e-30)
    return y * gain_drift + scale * streamer_amp * pat


def background_reference_snr(ts, tb=None):
    """Cost of an independent background reference of duration t_b (R22):
    extra variance Qcor/(Qexo^2 tb); the reference SNR at tb = ts."""
    tb = ts if tb is None else tb
    var = QCOR / (QEXO ** 2 * tb)
    sig = noise_sigma(1.0, ts)
    return dict(tb=tb, extra_variance=float(var),
                extra_sigma=float(np.sqrt(var)),
                ref_snr=float(1.0 / np.sqrt(QCOR * tb)) * QEXO * tb,
                ratio_to_photon_sigma=float(np.sqrt(var) / sig))


def effective_cadence_overhead(ts, mp, wallclock_days=90.0, slew_s=30.0, settle_s=10.0, sync_s=5.0):
    """Calculate effective duty cycle and achievable pass count under realistic overheads."""
    t_overhead = slew_s + settle_s + sync_s
    duty_cycle = ts / (ts + t_overhead)
    effective_photons = mp * ts * duty_cycle
    return dict(ts=ts, mp=mp, duty_cycle=duty_cycle, effective_photons=effective_photons)


def check_numerical_precision(F, y, camp, sigma, sigma_cl, tau_days, lam, LtL,
                              block=256):
    """Auditable precision diagnostics with ONE stated norm convention.

    The v2 version reported max|ds|/max|s| next to RMS(ds)/std(s) -- different
    denominators, which is why its RMS exceeded its maximum -- and it compared
    SOLUTION vectors while the manuscript described it as a normal-matrix
    accumulation test.

    What is actually varied here: F is stored as float32, so comparing a
    float32-F accumulation against a float64-F accumulation of the SAME stored
    array tests nothing (both see identical inputs).  The meaningful test is
    whether the WHITENING and the ACCUMULATION order lose precision, so:

      * reference: whiten in float64, accumulate in float64;
      * float32 pipeline: whiten in float64 but round the whitened rows to
        float32 before accumulating (what a memory-limited implementation
        would do);
      * blocked vs single-pass accumulation in float64;
      * normal-equation solve vs a QR solve of the same whitened design.

    Every relative error uses one stated denominator.
    """
    ns = F.shape[1]
    tau = tau_days * 86400.0

    def whitened(dtype, round32):
        """Full whitened design.  Kept only for a REDUCED problem: at n = 64 the
        dense float64 design is 65536 x 2592 x 8 = 1.4 GB per copy, so the
        precision audit must run on a smaller campaign (cmd_precision passes
        n=32 for exactly this reason)."""
        rows = []
        ys = []
        for p in range(camp.n * camp.n):
            si = camp.pix_samples[p]
            Cd = _pixel_cov(camp.sample_t[si], sigma[si], sigma_cl, tau, False)
            Lc = cholesky(Cd, lower=True)
            Fr = solve_triangular(Lc, np.asarray(F[si], dtype=np.float64),
                                  lower=True)
            yr = solve_triangular(Lc, np.asarray(y[si], dtype=np.float64),
                                  lower=True)
            if round32:
                Fr = Fr.astype(np.float32)
            rows.append(np.asarray(Fr, dtype=dtype))
            ys.append(yr.astype(dtype))
        return np.vstack(rows), np.concatenate(ys)

    Fw64, yw64 = whitened(np.float64, False)
    Fw32, yw32 = whitened(np.float32, True)
    A64 = Fw64.T @ Fw64
    b64 = Fw64.T @ yw64
    # (a) float32 design accumulated in float32 (sgemm): the realistic
    #     memory-limited pipeline; (b) the SAME float32-rounded rows promoted to
    #     float64 before accumulating, which isolates the rounding of the
    #     whitened design from the accumulation arithmetic itself.
    A32 = np.asarray(Fw32.T @ Fw32, dtype=np.float64)
    b32 = np.asarray(Fw32.T @ yw32, dtype=np.float64)
    Fw32_64 = np.asarray(Fw32, np.float64)
    A32_round_only = Fw32_64.T @ Fw32_64
    b32_round_only = Fw32_64.T @ np.asarray(yw32, np.float64)
    del Fw32, Fw32_64, yw32
    # blocked accumulation of the reference, same dtype: tests summation order.
    # Rows here are PIXEL-grouped in the order solve_gls builds them.
    per = camp.mp
    Ab = np.zeros((ns, ns)); bb = np.zeros(ns)
    for p0 in range(0, camp.n * camp.n, block):
        sl = slice(p0 * per, min(p0 + block, camp.n * camp.n) * per)
        Ab += Fw64[sl].T @ Fw64[sl]
        bb += Fw64[sl].T @ yw64[sl]
    nA = float(np.linalg.norm(A64, ord="fro"))
    nb_ = float(np.linalg.norm(b64))
    lam_eff = lam * np.trace(A64) / np.trace(LtL)
    Al = A64 + lam_eff * LtL
    s_np = np.linalg.solve(Al, b64)
    # regularised least squares in the DESIGN form: LtL is PSD-singular (the
    # Laplacian annihilates the constant mode), so its square root comes from
    # an eigendecomposition with the tiny negatives clipped.
    ev, V = np.linalg.eigh(LtL)
    Lsqrt = (V * np.sqrt(np.clip(ev, 0.0, None))) @ V.T
    Aug = np.vstack([Fw64, np.sqrt(lam_eff) * Lsqrt])
    bgu = np.concatenate([yw64, np.zeros(ns)])
    s_qr = np.linalg.lstsq(Aug, bgu, rcond=None)[0]
    del Aug
    resid = float(np.linalg.norm(b64 - Al @ s_np) / nb_)
    return dict(
        denom_A_fro=nA, denom_b_norm=nb_,
        rel_err_A_fro=float(np.linalg.norm(A32 - A64, ord="fro") / nA),
        max_rel_err_A=float(np.abs(A32 - A64).max() / np.abs(A64).max()),
        rel_err_A_round_only=float(np.linalg.norm(A32_round_only - A64, ord="fro") / nA),
        rel_err_b=float(np.linalg.norm(b32 - b64) / nb_),
        rel_err_b_round_only=float(np.linalg.norm(b32_round_only - b64) / nb_),
        rel_err_A_blockorder=float(np.linalg.norm(Ab - A64, ord="fro") / nA),
        rel_err_b_blockorder=float(np.linalg.norm(bb - b64) / nb_),
        cond_A_unregularized=float(np.linalg.cond(A64)),
        cond_A_lambda=float(np.linalg.cond(Al)),
        lam_eff=float(lam_eff),
        normal_eq_residual_rel=resid,
        map_diff_normal_vs_qr=float(np.linalg.norm(s_np - s_qr) /
                                    np.linalg.norm(s_np)),
        max_abs_map=float(np.abs(s_np).max()),
        rank_A_unregularized=int(np.linalg.matrix_rank(A64)),
        ns=int(ns),
    )


# end of module# end of module
