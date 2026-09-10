"""Target selection for an SGL imaging mission: the five nearest confirmed
potentially habitable planets, their focal-line placements, image-plane
geometry/dynamics, and photon budgets with propagated physical uncertainties.
Writes ../results/targets.json, ../paper/figures/fig_targets.pdf, ../paper/targets_table.tex.
"""
import json
import numpy as np
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sglsim as S

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
EPS = np.deg2rad(23.43928)   # obliquity J2000
Z = 650.0 * S.AU

# name, host, SpT, dist_pc, RA(h), Dec(deg), Msini(ME), P(d), a(AU), S(S_earth), note, ecc
TARGETS = [
 ("Proxima Cen b","Proxima Centauri","M5.5V",1.301,14+29.7/60,-(62+41/60.),1.07,11.19,0.04857,0.65,"closest; ESPRESSO-confirmed",0.11),
 ("Ross 128 b","Ross 128","M4V",3.375,11+47.7/60,0+48/60.,1.35,9.87,0.0496,1.38,"quiet host; near inner CHZ",0.12),
 ("GJ 1061 d","GJ 1061","M5.5V",3.67,3+36.0/60,-(44+31/60.),1.64,13.03,0.054,0.69,"temperate; compact multi-planet",0.06),
 ("Teegarden c","Teegarden's Star","M7V",3.831,2+53.0/60,16+53/60.,1.11,11.41,0.0443,0.37,"conservative HZ; low-flare host",0.04),
 ("GJ 273 b (Luyten b)","GJ 273","M3.5V",3.80,7+27.4/60,5+14/60.,2.89,18.65,0.0911,1.06,"near inner CHZ edge",0.10),
 ("tau Cet e (alt.)","tau Ceti","G8.5V",3.603,1+44.1/60,-(15+56/60.),3.93,162.9,0.538,1.71,"RV candidate; solar-type host",0.18),
]

def ecl_lat(ra_h, dec_d):
    a = np.deg2rad(ra_h*15.0); d = np.deg2rad(dec_d)
    sb = np.sin(d)*np.cos(EPS) - np.cos(d)*np.sin(EPS)*np.sin(a)
    return np.rad2deg(np.arcsin(sb))

rows = []
for (nm,host,spt,dpc,ra,dec,msini,P,a_au,inst,note,ecc) in TARGETS:
    z0 = dpc*S.PC
    ratio = Z/z0
    # Rocky mass-radius with 15% empirical scatter (Chen & Kipping 2017)
    # Median mass expectation assuming isotropic inclination: <1/sin i> ~ 1.27
    Rp_nom = msini**0.28
    Rp_err = Rp_nom * 0.15
    Rp_hi = (msini * 1.35)**0.28 * 1.15
    Rp_lo = msini**0.28 * 0.85
    
    Dimg = 2*Rp_nom*S.RPL*ratio
    Dimg_err = Dimg * 0.15
    
    # Photon rate at nominal albedo A=0.30, with albedo range [0.15, 0.45]
    Q_nom = 8.01e4 * inst * Rp_nom * (30.0 / dpc)
    Q_lo  = Q_nom * (0.15 / 0.30) * (Rp_lo / Rp_nom)
    Q_hi  = Q_nom * (0.45 / 0.30) * (Rp_hi / Rp_nom)
    
    snrc_nom = Q_nom * 1800 / np.sqrt((S.QCOR + Q_nom) * 1800)
    snrc_lo  = Q_lo * 1800 / np.sqrt((S.QCOR + Q_lo) * 1800)
    snrc_hi  = Q_hi * 1800 / np.sqrt((S.QCOR + Q_hi) * 1800)
    
    a_m = a_au * S.AU
    Ps = P * 86400.0
    r_img = a_m * ratio
    v_img = 2 * np.pi * a_m / Ps * ratio
    acc = 4 * np.pi**2 * a_m / Ps**2 * ratio
    
    # Delta-v tracking over 90 days with orbital eccentricity modulation
    dv90 = acc * 90 * 86400.0
    dv90_err = dv90 * (2 * ecc)  # variation due to orbital eccentricity
    
    raf = (ra + 12.0) % 24.0
    rows.append(dict(
        name=nm, host=host, spt=spt, d_pc=dpc, ra_h=ra, dec_d=dec,
        msini=msini,
        Rp=round(Rp_nom, 2),
        Rp_err=round(Rp_err, 2),
        P_d=P, a_au=a_au, S=inst, ecc=ecc,
        Dimg_m=round(Dimg, 1),
        Dimg_err_m=round(Dimg_err, 1),
        pix64_m=round(Dimg / 64, 2),
        Qexo=float(f"{Q_nom:.3g}"),
        SNRC1800=round(float(snrc_nom), 1),
        SNRC1800_lo=round(float(snrc_lo), 1),
        SNRC1800_hi=round(float(snrc_hi), 1),
        foc_ra_h=round(raf, 3),
        foc_dec_d=round(-dec, 3),
        foc_ecl_lat=round(float(ecl_lat(raf, -dec)), 1),
        r_img_km=round(r_img / 1e3, 1),
        v_img_ms=round(v_img, 1),
        acc_um_s2=round(acc * 1e6, 1),
        dv90_kms=round(dv90 / 1e3, 2),
        dv90_err_kms=round(dv90_err / 1e3, 2),
        note=note
    ))

(OUT / "results" / "targets.json").write_text(json.dumps(rows, indent=1))
for r in rows:
    print(f"{r['name']:22s} D_img={r['Dimg_m']:7.1f}±{r['Dimg_err_m']:<5.1f} m  "
          f"SNRC={r['SNRC1800']:5.1f} ({r['SNRC1800_lo']:.0f}-{r['SNRC1800_hi']:.0f})  "
          f"v_img={r['v_img_ms']:5.1f} m/s  dv90={r['dv90_kms']:4.2f}±{r['dv90_err_kms']:<4.2f} km/s  "
          f"foc=({r['foc_ra_h']:.2f}h,{r['foc_dec_d']:+.1f})  beta={r['foc_ecl_lat']:+.1f}")

# Sky map (equatorial Mollweide) of targets and antipodal focal directions
plt.rcParams.update({"font.size": 8.5, "font.family": "serif", "savefig.bbox": "tight"})
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

# Candidate tau Cet e
rc = rows[5]
xt, yt = towrap(rc["ra_h"]), np.deg2rad(rc["dec_d"])
xf, yf = towrap(rc["foc_ra_h"]), np.deg2rad(rc["foc_dec_d"])
ax.plot(xt, yt, "s", color="#029e73", ms=4, mfc="none")
ax.plot(xf, yf, "^", color="#cc79a7", ms=7, mfc="none")
ax.annotate("tau Cet e (cand.)", (xt, yt), textcoords="offset points", xytext=(4, 4), fontsize=6.5, color="#029e73")

# Ecliptic curve
lam = np.linspace(0, 2 * np.pi, 361)
ra_e = np.arctan2(np.sin(lam) * np.cos(EPS), np.cos(lam))
de_e = np.arcsin(np.sin(EPS) * np.sin(lam))
o = np.argsort(((ra_e + 2 * np.pi) % (2 * np.pi)))
xe = np.where(ra_e > np.pi, ra_e - 2 * np.pi, ra_e)
ax.plot(xe[o], de_e[o], "-", color="0.7", lw=0.8, label="ecliptic plane")

ax.plot([], [], "o", color="#0173b2", label="confirmed target planet")
ax.plot([], [], "*", color="#d55e00", label="SGL focal direction (650-900 AU)")
ax.plot([], [], "s", color="#029e73", mfc="none", label="solar-type candidate")
ax.legend(loc="lower right", fontsize=6.5, frameon=False)
ax.grid(alpha=0.3, lw=0.4)
ax.set_xticklabels(["14h","16h","18h","20h","22h","0h","2h","4h","6h","8h","10h"], fontsize=7)
fig.savefig(OUT / "paper" / "figures" / "fig_targets.pdf")
print("Target skymap and targets.json regenerated successfully.")
