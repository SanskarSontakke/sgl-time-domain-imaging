"""Solve one cadence config with ONE method (for large-mp configs)."""
import sys, numpy as np
import sglsim as S
import run_experiments as R

icfg, iseed, method = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
ts, mp = R.CADENCE[icfg]
seed = R.CAD_SEEDS[iseed]
camp = R.campaign(ts=ts, mp=mp)
sgl = S.SGLOperator(64)
truthF, truth_c = R.truth()
d = np.load(R.TMP / ("cad_%d_%d.npz" % (icfg, iseed)))
F = R.get_F(camp, sgl, build_ok=False)
LtL = R.get_LtL()
sigma_cl = R.get_sigcl(R.CAD_FC, camp, sgl, truthF)
if method == "b2":
    m = S.debias_cloud(S.reconstruct_phasebin({"y": d["y"]}, camp, sgl,
                                              R.NLAT, R.NLON, Kw=R.KW_B2),
                       R.CAD_FC)
else:
    white = method == "white"
    m = S.debias_cloud(
        S.solve_gls(F, d["y"], camp, d["sigma"], sigma_cl, R.TAU_DAYS,
                    R.LAM_GLS, LtL, white=white, deflate=not white), R.CAD_FC)
ev = S.eval_map(m, truth_c)
print("cfg=%d mp=%d seed=%d %s: ssim=%.3f r=%.3f" %
      (icfg, mp, seed, method, ev["ssim"], ev["pearson"]), flush=True)
np.savez(R.PARTS / ("cadm_c%d_s%d_%s.npz" % (icfg, iseed, method)),
         mp=mp, ts=ts, wall=camp.wallclock_days, **ev)
