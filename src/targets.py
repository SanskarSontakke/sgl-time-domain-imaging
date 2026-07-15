"""Target selection for an SGL imaging mission: the five nearest confirmed
potentially habitable planets, their focal-line placements, image-plane
geometry/dynamics, and photon budgets. Writes ../results/targets.json,
../paper/figures/fig_targets.pdf, ../paper/targets_table.tex."""
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

# name, host, SpT, dist_pc, RA(h), Dec(deg), Msini(ME), P(d), a(AU), S(S_earth), note
TARGETS = [
 ("Proxima Cen b","Proxima Centauri","M5.5V",1.301,14+29.7/60,-(62+41/60.),1.07,11.19,0.04857,0.65,"closest; ESPRESSO-confirmed"),
 ("Ross 128 b","Ross 128","M4V",3.375,11+47.7/60,0+48/60.,1.35,9.87,0.0496,1.38,"quiet host; near inner CHZ"),
 ("GJ 1061 d","GJ 1061","M5.5V",3.67,3+36.0/60,-(44+31/60.),1.64,13.03,0.054,0.69,"temperate; compact multi-planet"),
 ("Teegarden c","Teegarden's Star","M7V",3.831,2+53.0/60,16+53/60.,1.11,11.41,0.0443,0.37,"conservative HZ; low-flare host"),
 ("GJ 273 b (Luyten b)","GJ 273","M3.5V",3.80,7+27.4/60,5+14/60.,2.89,18.65,0.0911,1.06,"near inner CHZ edge"),
 ("tau Cet e (alt.)","tau Ceti","G8.5V",3.603,1+44.1/60,-(15+56/60.),3.93,162.9,0.538,1.71,"RV candidate; solar-type host"),
]

def ecl_lat(ra_h, dec_d):
    a = np.deg2rad(ra_h*15.0); d = np.deg2rad(dec_d)
    sb = np.sin(d)*np.cos(EPS) - np.cos(d)*np.sin(EPS)*np.sin(a)
    return np.rad2deg(np.arcsin(sb))

rows = []
for (nm,host,spt,dpc,ra,dec,msini,P,a_au,inst,note) in TARGETS:
    z0 = dpc*S.PC
    ratio = Z/z0
    Rp = msini**0.28                       # Chen & Kipping-like rocky M-R
    Dimg = 2*Rp*S.RPL*ratio
    Q = 8.01e4*inst*Rp*(30.0/dpc)
    snrc = Q*1800/np.sqrt((S.QCOR+Q)*1800)
    a_m = a_au*S.AU
    Ps = P*86400.0
    r_img = a_m*ratio
    v_img = 2*np.pi*a_m/Ps*ratio
    acc = 4*np.pi**2*a_m/Ps**2*ratio
    dv90 = acc*90*86400.0
    raf = (ra+12.0) % 24.0
    rows.append(dict(name=nm,host=host,spt=spt,d_pc=dpc,ra_h=ra,dec_d=dec,
        msini=msini,Rp=round(Rp,2),P_d=P,a_au=a_au,S=inst,
        Dimg_m=round(Dimg,1),pix64_m=round(Dimg/64,2),
        Qexo=float(f"{Q:.3g}"),SNRC1800=round(float(snrc),1),
        foc_ra_h=round(raf,3),foc_dec_d=round(-dec,3),
        foc_ecl_lat=round(float(ecl_lat(raf,-dec)),1),
        r_img_km=round(r_img/1e3,1),v_img_ms=round(v_img,1),
        acc_um_s2=round(acc*1e6,1),dv90_kms=round(dv90/1e3,2),note=note))

(OUT/"results"/"targets.json").write_text(json.dumps(rows,indent=1))
for r in rows:
    print(f"{r['name']:22s} D_img={r['Dimg_m']:7.1f} m  Q={r['Qexo']:.2e}  "
          f"SNRC={r['SNRC1800']:6.1f}  v_img={r['v_img_ms']:6.1f} m/s  "
          f"dv90={r['dv90_kms']:6.2f} km/s  foc=({r['foc_ra_h']:.2f}h,"
          f"{r['foc_dec_d']:+.1f})  beta_ecl={r['foc_ecl_lat']:+.1f}")

# sky map (equatorial Mollweide) of targets and antipodal focal directions
plt.rcParams.update({"font.size":8.5,"font.family":"serif","savefig.bbox":"tight"})
fig = plt.figure(figsize=(7.0,3.6))
ax = fig.add_subplot(111, projection="mollweide")
def towrap(ra_h):
    x = np.deg2rad(ra_h*15.0)
    return np.where(x>np.pi, x-2*np.pi, x)
for r in rows[:5]:
    xt, yt = towrap(r["ra_h"]), np.deg2rad(r["dec_d"])
    xf, yf = towrap(r["foc_ra_h"]), np.deg2rad(r["foc_dec_d"])
    ax.plot(xt, yt, "o", color="#0173b2", ms=5)
    ax.plot(xf, yf, "*", color="#d55e00", ms=10)
    lab = r["name"].split(" (")[0]
    ax.annotate(lab, (xt,yt), textcoords="offset points", xytext=(4,4), fontsize=7)
    ax.annotate(lab+" focus", (xf,yf), textcoords="offset points", xytext=(4,-9),
                fontsize=7, color="#a04000")
# ecliptic curve
lam = np.linspace(0,2*np.pi,361)
ra_e = np.arctan2(np.sin(lam)*np.cos(EPS), np.cos(lam))
de_e = np.arcsin(np.sin(EPS)*np.sin(lam))
o = np.argsort(((ra_e+2*np.pi)%(2*np.pi)))
xe = np.where(ra_e>np.pi, ra_e-2*np.pi, ra_e)
ax.plot(xe[o], de_e[o], ".", color="0.75", ms=0.8)
ax.plot([],[],"o",color="#0173b2",label="target planet")
ax.plot([],[],"*",color="#d55e00",label="SGL focal direction (650-900 AU)")
ax.legend(loc="lower right", fontsize=7, frameon=False)
ax.grid(alpha=0.3, lw=0.4)
ax.set_xticklabels(["14h","16h","18h","20h","22h","0h","2h","4h","6h","8h","10h"], fontsize=7)
fig.savefig(OUT/"paper"/"figures"/"fig_targets.pdf")
print("skymap saved")
