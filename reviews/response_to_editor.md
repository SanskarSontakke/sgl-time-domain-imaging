# Response to the Editor and Referee

**Manuscript:** Time-Domain Imaging of Rotating, Cloud-Covered Exoplanets with the Solar
Gravitational Lens: Reconstruction Algorithms, Observing-Cadence Requirements, and Mission
Targets
**Author:** Sanskar Sontakke (Independent Researcher)
**Journal:** *The Open Journal of Astrophysics*
**Decision:** Revise and resubmit (editor: Dr. Alexis Smith)

---

Dear Dr. Smith,

Thank you and the referee for a review of unusual specificity. Every one of the twenty
comments was actionable, and acting on them changed the paper's content materially rather than
cosmetically. We summarise the four structural changes before the point-by-point response.

**1. The v2 experiment was re-run, not re-described.** The referee correctly identified that
several quantitative claims in v2 could not have been produced by the shipped pipeline. We found
this to be true more widely than the review alleged. In v2 the cadence table contained
$r_{\rm smear}$, $r_{\rm cf}$ and $r_{\rm iid}$ columns that no code path emitted; the
"93.75% of spatial information retained" was a rank calculation about the wrong matrix; the
"14–23×" noise ratio and the "~2 GB" telemetry figure were arithmetic on quantities the model
does not use; the structured-coronal experiment asserted a result it never measured. In this
revision, **every number in the manuscript is read from an archive under `results/` by a
generation script**, and `results/audit.json` states for each headline value how many seeds
actually produced it. No number is typed into the text or into a figure.

**2. Correcting the forward model lowered almost every headline number.** The v2 exposure
operator averaged three *equal-spaced, equal-weight* sub-exposures, which is not a convergent
quadrature of the smear kernel: at the fiducial dwell it passes azimuthal harmonic $m=36$ at
unit gain where the exact response annihilates it. Replacing it with 16-node Gauss–Legendre
quadrature, and replacing the approximate slot deflation with exact per-dwell nuisance
profiling, moves the cloud-free result from $r=0.990$ to $r=0.9786\pm0.0002$, the fiducial
cloudy result from $r=0.334$ to $r=0.3422\pm0.0082$, and the effective resolution from
"$\ell_{\rm eff}\approx4$–5" to a measured scale-dependent $r(\ell)$ whose cloud-free curve
stays above 0.99 to the $\ell=20$ grid ceiling. We report the differences, not a smooth
transition.

**3. Some v2 claims are withdrawn rather than updated.** Where re-running contradicted the
original conclusion we kept the conclusion out. The largest is in-flight ephemeris refinement:
the whitened $\chi^2$ is invariant in initial phase to $5\times10^{-9}$ absolute because the
longitude basis is complete, so a $\chi^2$ landscape cannot refine the phase at all. The spin
state is still observable, but through image quality, and we now say so. Also withdrawn: the
"order-of-magnitude cloud climatology is enough" framing (partly retained, partly sharpened),
and the extrapolation that a few hundred visits will reach $r\gtrsim0.8$. Two further v2
assertions — robustness to surface morphology and to regularizer choice — were not restated
but re-measured and bounded instead (§5.11–5.13, items (e) and (f) below).

**4. The paper's positive content survived.** The central result is stronger than we had
argued. A rotating, orbit-illuminated, cloud-covered planet is imaged by a time-dependent linear
operator, and the cadence law now has a *mechanism* rather than a trend: cloud-free controls and
independent-weather controls at every cadence show that the gain comes from acquiring
statistically independent samples of the atmosphere, and not from the assumed covariance
structure, not from conditioning, and not from reduced smear. The paper's honest scope is that
under characterized geometry and a photon-limited budget, weather — not the corona — sets the
error budget, *within the adopted calibration assumptions*, and Sections 5.12–5.13 now put
numbers on what those assumptions have to deliver — and on the two assumptions that turn out not
to matter at all (the assumed cloud amplitude, and the choice of regularizer the objective cannot
make).

**Formatting.** All changed text is enclosed in a `\rev{}` macro and sets boldface.
`\revflagfalse` produces a clean version; the change bars and boldface are then removed and the
line numbering and page count are unchanged. Equation numbers are not preserved between versions
(v2 had 5, v3 has 17), so we list the correspondence explicitly below and refer to sections and
labels rather than to old equation numbers.

---

# Major comments

## 1. Cadence-law experiment must isolate the causal mechanism

> *Please repeat or augment this experiment with a factorial ablation that includes at least: an
> exposure-integrated forward operator ...; a cloud-free control at every cadence ...; a
> comparison between temporally independent cloud realizations and OU-correlated clouds with the
> same one-point variance; where practical, matched rotational phases ...; a quantitative
> accounting of slew, settling, readout, inter-spacecraft synchronization, and calibration
> overheads as dwell times become short.*

**Done, and the referee's suspicion was right in a way we did not expect.** All five controls are
now measured on identical campaign objects, seeds and estimators.

*(a) Exposure-integrated operator.* We implemented sub-exposure integration in the
reconstruction operator and, in the process, discovered that the v2 rule is not a quadrature at
all (Section 4.3, Table 1). The v2 data and operator both used three equal-weight samples at
$-t_s/3,0,+t_s/3$; this rule has an aliasing passband and at $t_s=7200$ s reconstructs a
differently-smeared planet than the one simulated. The revision uses 16-node Gauss–Legendre in
**both** the data and the operator, and reports the response error of each rule against the
analytic $\mathrm{sinc}$: the equal-3 rule errs by up to $8.8\times10^{-1}$ at $m=20$, the 16-node
rule by $1.0\times10^{-15}$. The comparison is now model-consistent at every cadence, so the
trend cannot be a smear-mismatch artifact.

*(b) Cloud-free control at every cadence* and *(c) independent vs OU weather with matched
one-point variance.* These were the two most informative new runs (Section 5.6). Arm A,
$M_p=4\to64$:

| | $M_p=4$ | 8 | 16 | 32 | 64 |
|---|---|---|---|---|---|
| correlated OU (main sweep) | 0.049 | 0.173 | 0.346 | 0.497 | 0.571 |
| cloud-free control | 0.773 | 0.934 | 0.979 | 0.984 | 0.987 |
| per-pass independent weather | 0.051 | 0.165 | 0.342 | 0.494 | 0.583 |

Two conclusions, pulling in opposite directions, and we report both. The cloud-free control
*does* rise with $M_p$ — by 0.214 over $4\to64$ — so a conditioning contribution is real and v2's
flat assertion that the trend is "not conditioning" was overstated. But it is front-loaded
(0.16 of that 0.214 comes in the first doubling, where a raster position receives only four
dwells) and saturates: from $M_p=16$ to 64 the cloud-free curve gains 0.008 while the cloudy
curve gains 0.225. Meanwhile the independent-weather control is **within the paired standard
errors of OU at every cadence** in both arms (paired differences
$+0.002,-0.008,-0.004,-0.003,+0.012$; all $p_t\ge0.14$; the exact sign-flip floor with six pairs
is 0.031, so nothing is remotely close). The cadence law therefore requires independent
*weather states*, not OU structure: the covariance model determines how many of the $M_p$ looks
count as independent, not why more looks help.

*(d) Separating phases from distinct cloud states.* The $N_{\rm eff}$ table (Table 8) does this
directly: at $\tau_{\rm cloud}=4$ d, $M_p=64$ buys 12.1 effective looks, not 64 — a 5.3-fold
saturation invisible in $M_p$. We now require the cadence specification to be quoted jointly
with the assumed $\tau_{\rm cloud}$, because as a revisit count alone it is not a mission
requirement. Control (c) above is the complementary test: it holds the phase count fixed and
destroys only the temporal correlation.

*(e) Overheads.* Section 3.4 defines two mutually exclusive resource ledgers, because the
referee is right that v2 tried to hold photons and wall clock fixed at once. Arm A holds
$M_pt_s=8$ h per raster position (wall clock grows to 93.73 d at $M_p=64$, i.e. it *violates* the
90-day goal); arm B holds 89.87 d (photons fall from 8.39 to 7.64 h). A 45 s/dwell overhead
(slew, settling, readout, sync, calibration — itemised in Section 3.4) gives duty cycles
0.994→0.909. The two arms agree within the paired standard error at every $M_p$, which is the
result that makes the law usable: what is being paid for is independent looks, and the exchange
rate between dose and revisit count is favourable over the whole range studied. The v2 sentence
about ultrafast cadences ($t_s\lesssim100$ s) being offset by overheads is deleted — no
configuration below 429.6 s exists in the archive, so it was not a measurement.

## 2. Separate the gain from time-aware modeling, deflation, and covariance weighting

> *Please provide a clean component-wise ablation using identical data and paired seeds ...
> Report paired differences and uncertainty intervals, not only mean correlations.*

Done — six configurations, 10 paired seeds, identical data (Table 6, Section 5.4). The referee's
diagnosis was correct and the correction is larger than expected:

| | configuration | $r$ | SSIM | rel. dev. vs D |
|---|---|---|---|---|
| A | time-dependent $\mathsf F$, diagonal weighting, no deflation | 0.2886 ± 0.0097 | 0.0853 | 77.8% |
| B | + OU temporal whitening, no deflation | 0.2863 ± 0.0090 | 0.0825 | 79.0% |
| C | v2 approximate deflation, whitened | 0.3422 ± 0.0082 | 0.1058 | 9.29% |
| D | exact anchored slot profiling, whitened | 0.3454 ± 0.0082 | 0.1095 | 0 (ref) |
| E | D with free (unanchored) profile | 0.3453 | 0.1093 | 0.98% |
| F | full pipeline (D + affine debias) | 0.3422 ± 0.0082 | 0.1060 | 9.22% |

The decomposition the referee asked for is F−B = **+0.0559** (paired SE 0.0049, 10/10 seeds,
$t=11.3$, exact sign-flip $p=0.00195$, bootstrap CI [+0.047, +0.065]): that is the contribution of
handling the slots at all, and it is the only large effect. Within slot handling, exact profiling
over the v2 approximation is +0.0032 ± 0.0019, $p_t=0.13$ — *not* significant. Temporal whitening
contributes nothing without slot handling (B−A = −0.002). So the credit goes to the
time-dependent operator plus per-slot nuisance handling, and the specific covariance model earns
almost none. We have rewritten the Abstract, Sections 4.2, 5.4 and 7 to say this, and the term
"covariance-aware" no longer appears as an explanation of the gain.

We note one honest oddity: C and F are numerically identical to four decimals. This is not a
copying error; the v2 deflation and the corrected profiling differ by only 0.0032 on this
campaign, and the affine debias step then removes a comparable amount, so the two pipelines cross.
Section 5.4 states this rather than selecting the more flattering column.

## 3. Cloud climatology assumptions require broader robustness tests

> *At minimum, please add tests for: misestimated mean cloud fraction and mean cloud albedo; a
> spatially nonuniform persistent cloud climatology, including a component correlated with the
> surface map; at least two additional spatial correlation lengths, advection rates, and
> decorrelation times; a cloud process with a non-exponential or multi-timescale temporal
> covariance.*

Three of the four were already done in v3 before this round; the fourth (correlation length,
advection rate, decorrelation time) is new and is reported below. All 10 paired seeds.

*(a) Misestimated mean cloud fraction and albedo* (Section 5.10, Figure 6). A $5\times5$ grid on
$\Delta f_c,\Delta A_{\rm cl}\in[-0.15,+0.15]$. $r$ is *mathematically invariant* to the affine
correction error — identical to $4\times10^{-7}$ in all 25 cells — and the referee is right that
this makes the v2 framing incomplete, so we now report the quantity that does move: absolute
albedo, spanning **+0.206 to −0.550** over the grid (the map's dynamic range is ~1.1), and the
land–ocean contrast ratio, 0.80–1.61. The requirement is correspondingly restated: order-of-
magnitude climatology suffices for *pattern* recovery and is not sufficient for *albedo*
recovery. These are different claims and v2 blurred them.

*(b) Structured, surface-correlated climatology* (Section 5.10). ITCZ-style latitudinal banding
costs nothing measurable ($r=0.3240\pm0.0126$ vs 0.3422). Surface-correlated cloud formation
(coupling 0.25 to the underlying albedo) is catastrophic: $r=0.1444\pm0.0124$,
SSIM $0.0602\pm0.0038$. This is the result the referee was driving at, and it is now stated as a
hard limit rather than a robustness check: a weather pattern that is stationary in the *surface*
frame is indistinguishable from the surface, and no cadence fixes it, because revisiting does not
change it. Any persistent surface–cloud correlation is absorbed into the albedo map.

*(c) Multi-timescale temporal covariance* (Section 5.10): $(\tau_1,\tau_2,w)=(1\,{\rm d},10\,{\rm d},0.7)$
gives $r=0.3174\pm0.0088$, and the same with pure per-pass independence gives $0.3151\pm0.0093$.
Neither exponential nor non-exponential covariance is load-bearing.

*(d) New: correlation length, advection rate, decorrelation time* (Section 5.12, Table 11). Six variants of
the *true* weather field — $\ell_{\rm corr}=8°$ and $20°$ (fiducial 12°), $u=3$ and $12$ deg/day
(fiducial 6), $\tau=2$ and 8 d (fiducial 4) — each scored twice: once with the estimator keeping
the fiducial OU climatology ("misspecified"), once with $\sigma_{\rm cl}$ and $\tau$ recalibrated
to the variant ("recalibrated"), so the gap isolates the cost of climatological error per se.

The full six-variant table is Section 5.12 / Table 11. Four of the six variants change the
*spatial or temporal structure* of the weather, and $r$ moves over all four within a narrow band
(0.313–0.327 against the fiducial 0.3422) with paired differences of recalibrated − misspecified
at the $10^{-6}$–$10^{-7}$ level. Only the decorrelation-time variants move anything: $\tau=2$ d
gives $+0.0017\pm0.0008$ and $\tau=8$ d gives $-0.0072\pm0.0016$ (exact sign-flip $p=0.021$), so a
weather field that decorrelates *slower* than assumed is the one structural mis-specification with
a measurable cost.

The striking outcome is that "recalibrated" and "misspecified" are **numerically identical** for
the structural variants, and that we can show why rather than report it as luck. The
reconstruction is nearly insensitive to the *assumed* cloud amplitude: scaling $\sigma_{\rm cl}$
between $0.25\times$ and $16\times$ changes the mean paired $r$ by $\le2.6\times10^{-4}$ (no
individual seed by more than $5.2\times10^{-4}$), and even deleting the cloud term entirely costs
only $3.2\times10^{-3}\pm1.9\times10^{-3}$ (Section 5.12, archive `sigma_sensitivity`) — while the
whitened $\chi^2$ over the same span moves by a factor $8\times10^{4}$. We then checked that this
is a property of the operator rather than of our anchoring, by running the same sweep on the free
(un-anchored) profiler and on v2's approximate deflation: per-seed spreads of
$2.74\times10^{-4}$ (anchored), $2.72\times10^{-4}$ (free) and $2.56\times10^{-4}$ (v2
deflation) (archives
`sigma_sensitivity_free`, `sigma_sensitivity_v2`), all against a seed-to-seed scatter of 0.026. Two
consequences are drawn in the paper: the pre-flight calibration requirement is on weather
*correlation structure*, and $\sigma_{\rm cl}$ itself can be fit in flight from the residuals
because $\chi^2$ does respond to it steeply even though the map does not — but equally, $\chi^2$
cannot be used to *validate* an assumed cloud model without an independent amplitude estimate,
which v2's methodology implicitly assumed it could do.

A GCM experiment remains outside this revision and Section 7 now says so explicitly rather than
listing it as future work.

## 4. The rotation requirement extends beyond the period

> *Please test sensitivity to at least the pole orientation and initial rotational phase, and
> discuss whether these parameters would be fixed externally or estimated jointly from the SGL
> data. A profile-likelihood or grid search over period, phase, and pole orientation would be
> particularly informative. The claim that rotation and illumination are 'solved problems' should
> be replaced... The statement that tidally synchronized M-dwarf planets automatically satisfy the
> period requirement should also be qualified.*

All four parts are addressed, and the profile-likelihood grid produced the single largest
withdrawal in the revision.

*(a) Geometry sensitivity* (Section 5.8, Table 9, Figure 6a), 10 paired seeds. Pole tilt:
$0.3422\to0.2856$ at $5°$ (17% relative loss) $\to0.1699$ at $20°$ (50%). Assumed initial phase:
$0.2949$ at $5°$, $0.1874$ at $15°$, $0.0719$ at $30°$, $-0.0269$ at $60°$. v2's "virtually intact
at 5°" is replaced; the phase direction is much steeper than the tilt direction and a $60°$ error
destroys the reconstruction, so we no longer describe either as tolerant. Section 5.8 states the
requirement as a joint budget rather than three thresholds.

*(b) Profile likelihood over (period error × phase error)* (Section 5.9, Figure 6b), a $5\times5$
grid on 4 seeds. **The objective contains no information about the phase.** Whitened $\chi^2$
varies across the whole $\pm10°$ phase range by less than $10^{-11}$ in relative terms — not
"nearly flat" but numerically identical — for a structural reason we can state: the surface basis
is complete in longitude, so an assumed phase shift is a relabelling of $\phi$ and the minimiser
follows it exactly. In the period direction the grid is monotone, not convex: $\bar\chi^2$ falls
from 42,746.8 at $\Delta P/P=-2\times10^{-4}$ to 42,493.0 at $+2\times10^{-4}$ on every seed, so
the minimum sits on the grid boundary, no curvature estimate exists, and per-seed parabolic
vertices scatter over $(-3\times10^{-3},+5\times10^{-4})$. The anchored and free profiles differ
by a constant 19.5 in $\chi^2$ and agree on every argmin, so this is not an artifact of the
anchor. **v2's "sharp, convex global minimum enabling in-flight refinement" was wrong, and is
deleted.** What survives is a weaker but usable statement: $r$ peaks at the truth on 4/4 seeds,
so the spin state is observable through *image quality* and can be validated by reconstructing
and checking the map, which is a different (and more expensive) procedure than a likelihood
search. The Discussion now says the geometry must come from external precursor observations.

*(c) "Solved problems" language* — removed everywhere, replaced with "tractable under accurately
known spin and illumination geometry, which must be supplied externally".

*(d) Tidal synchronization* — Section 6.1 now qualifies the M-dwarf period argument: a precise
orbital period does not imply synchronous rotation, and pseudosynchronization at non-zero
eccentricity, 3:2-type resonant capture, libration amplitude, and atmospheric/oceanic thermal
tides can each put $P_{\rm rot}$ outside the tolerance in Table 9. Light-curve period
characterisation remains a mission prerequisite, not a formality.

## 5. Optical validation is useful but presently limited

> *...should nevertheless be described as partial validation of a simplified forward model rather
> than end-to-end validation... at n = 128 the measured deconvolution penalty is 0.106 versus an
> analytic value of 0.073, a difference of roughly 45 percent. Please explain the source of this
> discrepancy, show numerical-convergence tests, and avoid describing the agreement as exact...
> Please either include at least one structured calibration or coronal-residual experiment, or
> consistently qualify the result as 'within the adopted photon-noise and calibration
> assumptions.'*

*(a) Framing.* Section 2.3 is titled "Deconvolution-penalty validation and numerical limits" and
describes itself as partial validation of the discrete aperture-averaged operator. The word
"exact" is gone.

*(b) The 45% discrepancy, now explained and bounded.* The analytic $\bar\sigma = 0.891\,D/(d\sqrt
N)$ is a continuum result for an infinite-domain $1/\rho$ transform; the implementation computes
a cell-averaged kernel on a finite periodic grid. We now report both kernels and their ratio at
$n=16,32,64,128$ (the point-core/cell-mean ratio falls as $23.7, 47.5, 94.9$ with refinement —
i.e. the discretisation is converging toward the singular continuum kernel, and the disagreement
is a property of the *reference*, not of the solver), the off-diagonal relative error (3.66%,
stable across four resolutions), and the uniform-disk closure residual (1.094 point / 1.135
cell-mean at $n=64$). We also state which core we use and why (point-sampling reproduces the
published SNR benchmark; cell-mean does not) and record the resulting SSIM difference
(0.851 vs 0.486) as a kernel-model ablation rather than hiding it. Section 2.3 now says the
agreement with the analytic value is at the tens-of-percent level *by construction*, and that
this bounds what the check can certify.

*(c) The structured coronal experiment, measured.* This is new and it changed a conclusion
(Section 5.15, Table 12). We inject a coherent linear gain ramp across the image plane, a slowly
evolving 8-cell coronal streamer field with 15–60 day random-walk modes, and both together, at
amplitudes $\epsilon$ expressed as a fraction **of the coronal background** — which is the unit
in which a coronagraph engineer quotes them, and is $7.74\times10^{4}$ smaller in planet
reference units. v2's assertion that frequent revisits protect against coherent drifts was not
measured, and the truth is the opposite in one respect and more benign in another. The results,
10 paired seeds against a base $r=0.3422\pm0.0082$:

| $\epsilon$ (of corona) | drift $r$ | streamer $r$ | both $r$ |
|---|---|---|---|
| $10^{-6}$ | 0.3400 | 0.3408 | 0.3385 |
| $10^{-5}$ | 0.2700 | 0.2640 | 0.2319 |
| $10^{-4}$ | 0.0842 | 0.0355 | 0.0568 |

At $\epsilon=10^{-6}$ the loss is 0.4–1.1% of $r$ and is statistically detectable but
practically irrelevant (paired $\Delta r=-0.0023\pm0.0006$, $t=-3.6$; $-0.0015\pm0.0002$,
$t=-6.3$; $-0.0037\pm0.0006$, $t=-5.9$). At $10^{-5}$ it is 21–23%; at $10^{-4}$ the map is gone
(SSIM $7\times10^{-4}$ to $1.3\times10^{-3}$, albedo bias up to +1.29). The joint case is
**sub-additive** — 73% of the sum of the individual losses at $10^{-5}$, 50% at $10^{-4}$ — which
we report as an observed property of these templates rather than a mechanism we can justify.
The calibration scale is now explicit: a single dwell's own photon fluctuation is
$\epsilon=2.99\times10^{-7}$ in these units, so the knee of the curve sits at 3–4$\sigma$ of
ordinary photon noise, and the requirement is a *sub-$10^{-6}$-of-background* calibration of the
low-order spatio-temporal modes. Revisit cadence does not rescue any of this: a coherent
systematic is repeated, not averaged, and v2 claimed the opposite. A dedicated background
reference costs a full photon $\sigma$ ($\sigma=0.02317$ at $t_b=\tau_{\rm int}$, equal to the
dwell photon noise to $7\times10^{-6}$ relative) and removes only the mean, leaving the structure
that the table prices untouched.

*(d) Qualification.* All noise-budget conclusions are now stated as conditional on the adopted
photon-noise and calibration assumptions, including in the Abstract and Conclusions.

## 6. Image quality, uncertainty, and effective spatial resolution

> *Please strengthen the statistical and spatial characterization by reporting: results over
> substantially more than three cloud/noise seeds, with confidence intervals or paired bootstrap
> intervals; spatial power spectra, spherical-harmonic recovery, or scale-dependent correlations
> to identify the effective resolvable scales; uncertainty or resolution maps, including the
> dependence on latitude and illumination coverage; a detection-oriented metric for the claimed
> land-ocean dichotomy, evaluated against appropriate null maps; sensitivity to the
> regularization weight and to substantially different surface-map morphologies. ... Please also
> compare the rotating solution with a static ideal-data reference under the same photon budget,
> and report the information or resolution loss attributable specifically to rotation.*

*(a) Seeds and intervals.* Ten paired seeds (11–20) throughout, six for the cadence sweep where
five campaign configurations × 10 seeds exceeded the budget. Every table entry carries a
standard error; every headline comparison carries a paired difference with bootstrap CI, a
paired $t$ $p$-value and the **exact** sign-flip $p$-value, and the paper states the floors: with
10 pairs the smallest attainable two-sided sign-flip $p$ is $1.95\times10^{-3}$, with 6 pairs
0.031, and with a 40-member null $1/41=0.024$. v2's several "$p<10^{-3}$" and "$p<0.02$"
assertions are replaced with the measured values.

During the final audit we corrected the sign-test convention itself. `src/expcommon.py` computed
the two-sided sign-flip $p$ as $2\binom{n}{k}/2^n$ (twice the point probability of the observed
split), which is anti-conservative relative to the standard central definition — twice the smaller
binomial tail, $\min\{1,\,2\sum_{i\le k}\binom{n}{i}/2^n\}$. The fixed convention is now in the
code and the archive has been regenerated with it. Nothing that was called significant changes
status, but three numbers move and one sentence was tightened: the supercontinent penalty is
$p_{\rm sign}=0.109$ rather than $0.088$ (still 8/10 seeds, still the same conclusion), the
$\tau=8$ d weather cost is $0.021$ rather than $0.020$, and the two ten-seed comparisons that were
reported at $0.410$ (the D$-$C component control, and the archipelago-vs-fiducial morphology
control) are now $0.754$. We also state explicitly in Section 4 that the floor binds the *sign
test* only: paired $t$-tests, which use magnitudes as well as signs, do reach $p_t\ll10^{-3}$ for
the largest effects, and those are labelled $p_t$ everywhere.

*(b) Scale-dependent recovery.* Section 5.3 computes $r(\ell)$ by real spherical-harmonic
projection on the actual reconstruction grid (v2's 2D-FFT $r(\ell)$ is not a spherical harmonic
decomposition on an equirectangular grid; we checked and the orthonormality error at $\ell=20$ is
0.018, which is why the ceiling is now stated as $\ell\le20$ rather than presented as a
measurement). Cloud-free $r(\ell)\ge0.99$ at every degree up to the ceiling. Under fiducial
clouds the curve is non-monotone and noisy ($0.88$ at $\ell=2$, $0.33$ at $\ell=9$, $0.18$ at
$\ell=17$), which we report as the honest shape rather than fitting a cutoff; quoting
"$\ell_{\rm eff}\approx7$–9 (2200–2900 km)" as a summary of where it crosses 0.5 is our
compromise, and the crossing is *not* a resolution in the usual sense. The v2
"$\ell_{\rm eff}=4$–5" is superseded.

*(c) Detection metric and nulls.* Land–ocean $d'=0.662$–$0.909$ over the 10 seeds (mean 0.732),
against two nulls of different kind: a 40-member cloud-only physical null (uniform-albedo scenes
through the identical pipeline; mean $d'=0.0013$, SD 0.0900, 95th percentile 0.114) and a 2000-
permutation label null on the maps themselves. Both nulls are significant ($p=0.024$ at the
40-member floor, $p=5.0\times10^{-4}$ for permutations). We emphasize in the text that the
permutation null tests map structure and the physical null tests whether the pipeline manufactures
a dichotomy from weather alone; v2's single "100 phase-scrambled surrogates, $p<0.02$" was the
weaker of the two designs and its $p$-value could not have been below $1/101$.

*(d) Latitude and illumination coverage.* Section 5.3 and Table 5. The referee asked for
uncertainty or resolution maps "including the dependence on latitude and illumination coverage";
we now score the archived fiducial reconstructions in six $30°$ latitude bands and pair each band
with the illumination it actually receives — the campaign-mean Lambert factor over its disk pixels
and the campaign-mean column energy $\Vert F_{:,i}\Vert^2$ of the operator, which is the quantity
that decides whether a band is sampled at all. Band quality is monotone in delivered information
across the well-sampled globe (column energy 21.4 → $r=0.35$–0.39 cloudy and 0.981–0.986
cloud-free; energy 6.6 → 0.30–0.34 and 0.966–0.974). The two polar bands score *higher* in $r$
(0.45, 0.55) and we say plainly why that is not a recovery claim: half of each polar band is
never sampled by the $n=64$ circular raster, the ice cap makes those bands the highest-contrast
and lowest-frequency truth structure in the map, and the amplitude diagnostic gives them away —
the polar reconstruction/truth SD ratio is 1.7–2.0 against 2.8–3.9 at mid-latitudes. Restricting
the polar correlation to sampled cells moves it to 0.52 and 0.65, and the band-to-band mean
offsets are $\le 0.019$, so there is no latitudinal albedo bias, only a correlation artefact.
We quote these as coverage diagnostics and explicitly not as polar imaging.

*(e) Regularization sensitivity — the referee was right to ask, and the answer was more
inconvenient than we expected.* Section 5.13, Figure 7 and archives `lambda_sweep`,
`lambda_resolution`. $\lambda$ was frozen at $3\times10^{-3}$ in v2 on a held-out seed and never
swept. Swept over **six** decades, $10^{-5}\to10$, on 10 seeds, including the turnover the
earlier five-decade grid missed:

- cloud-free: $r$ rises $0.9752\to0.9916$ (paired $+0.0130$, 10/10 seeds), **peaks at
  $\lambda=0.3$, then turns over** to $0.9639$ by $\lambda=10$; SSIM follows the same curve
  ($0.839\to0.945\to0.891$).
- cloudy ($f_c=0.55$): $r$ rises **monotonically across the whole tested range**, $0.3378\to0.5200$
  — a paired $+0.178\pm0.007$ at $\lambda=10$, more than three times the entire algorithmic gain
  of the pipeline — while $\chi^2$ varies by less than $0.1\%$ from $10^{-5}$ to $0.3$ (within
  $\pm54$ absolute against an expected sampling width of $\sqrt{2N}=362$). There is no
  discrepancy-principle minimum in the cloudy objective at all.

Because a monotone $r(\lambda)$ under a smoothing prior invites exactly the wrong reading — that
more regularization is better imaging — we scored what the gain is made of: the same inversions at
$\lambda=3\times10^{-3}, 0.1, 1, 10$ re-analysed in harmonic bands. Cloudy, $\overline{r(\ell)}$
over $\ell\le4$ stays at 0.72–0.74 and over $\ell\ge13$ at 0.26–0.29 while $d'$ rises
$0.749\to1.219$ and contrast falls $1.071\to0.929$ — genuine large-scale recovery, not blur, since
clouds have already removed the $\ell\gtrsim9$ information that $\lambda$ cannot put back.
Cloud-free the control behaves as a resolution claim should: the $\ell\ge13$ band degrades
$0.992\to0.850$ and $r$ turns over exactly there.

This is a result we **report rather than adopt**, and the paper says so: the headline numbers keep
$\lambda=3\times10^{-3}$ because our selector is correlation against a known truth map, which is
precisely what is unavailable in flight. What we no longer claim is that the choice is unimportant.
The missing truth-blind criterion (discrepancy principle, GCV, a validated prior over surface
models) is now stated as a limitation — Section 7(viii) — rather than papered over by a frozen
constant.

*(f) Morphology sensitivity.* Now restored, and the v2 claim turns out to be half right. Section
5.11 and Table 10 (archive `morphology_*`). Three truth fields from the same seed at the same
quantile land fraction — 30% of the fine grid, mean albedo 0.235–0.237, SD within 2% of each
other — differing only in arrangement: the fiducial *earthlike* field, a *supercontinent* field
with its power pushed to the largest scales, and an *archipelago* field with its power pushed to
the smallest. Each gets its own weather realization on the same cloud seeds and its own calibrated
$\sigma_{\rm cl}$, because the cloud-induced variance depends on the albedo pattern it modulates.
10 paired seeds, scored against the earthlike reconstruction on the same seeds:

| field | $\sigma_{\rm cl}$ | $r$, $f_c=0$ | $r$, $f_c=0.55$ | paired $\Delta r$ vs earthlike |
|---|---|---|---|---|
| earthlike | 0.4406 | 0.9786 | 0.3422 | — |
| supercontinent | 0.4870 | 0.9844 | **0.3026** | **−0.0396 ± 0.0090** ($p_t=0.0017$, 8/10 negative) |
| archipelago | 0.4426 | 0.9738 | 0.3393 | −0.0030 ± 0.0056 (unresolved, 4/10) |

Fragmentation is free; concentration is not. Island chains cost less than one standard error,
which is what one expects when the cloudy campaign has already lost every scale above
$\ell\approx9$. A single large continent costs $\sim12\%$ of the fiducial $r$, and the mechanism
is the surface–cloud coupling the referee's comment 3b identifies rather than an information loss:
the supercontinent's $\sigma_{\rm cl}$ is 10.5% *larger* than the fiducial's, and its contrast
collapses from 1.071 to 0.983. The control that separates the two explanations is the cloud-free
column, where all three morphologies score $\ge0.974$ and the supercontinent is the *best* of them
(+$0.0058$, 10/10 seeds) — so the penalty exists only in the presence of weather. We replaced the
v2 blanket "robust to morphology" with this bounded statement rather than dropping the claim.

*(g) Static ideal-data reference.* Added, measured, and counter-intuitive (Section 5.1, archive
`static_reference`). The same 64×64 raster, the same 1800 s dwell, the same 16 revisits and
therefore the same 8 h per raster position, but the planet frozen and cloud-free, so every pass
sees an identical pose — the best case any observation of this planet at this dose could produce.
Scored on the same 10 seeds with the same estimator it gives $r=0.4074\pm0.0254$ (SD 0.0804,
per-seed range 0.284–0.523), SSIM 0.3604, NRMSE 0.4299 — i.e. **worse than the rotating
cloud-free planet by $+0.5728\pm0.0254$** ($p_t=3.1\times10^{-9}$, 10/10 seeds), with the rotating
cloudy campaign between them at $-0.6379\pm0.0083$ relative to rotating cloud-free
($p_t=5.2\times10^{-14}$, 10/10). The reason is conditioning, not information: with the planet
frozen the 16 pose-passes of each raster position are literally identical rows of $\mathsf F$, the
time-domain design loses the rank rotation supplies, and the regularizer does all the work. So the
"loss attributable specifically to rotation" the referee asked us to report is *negative* —
rotation is not the bottleneck even against the idealized static limit, and the entire 0.638 gap
the paper is about is weather. This replaces v2's "$r=0.991$ vs $r=0.075$", which compared a
rotating planet to a *phase-blind coadd* and thereby attributed to rotation a loss produced by
throwing away the time information.

## 7. Mission and swarm conclusions should not rely on untested extrapolation

> *Please either simulate the several-hundred-visit regime with realistic overhead and at least
> one systematic-error model, or relabel this result as a speculative scenario... A fitted
> scaling law should include uncertainty and should not be extrapolated outside the tested range
> without justification. The distinction between 'registered visits per pixel' and 'number of
> spacecraft' should also remain explicit.*

Relabelled, and the supporting quantitative structure is new. We did not simulate hundreds of
visits, and the paper does not pretend otherwise: Section 6 is titled "From Algorithm to
Mission", the $r\gtrsim0.8$ extrapolation is marked as a scenario, and the scaling law is quoted
with its tested range ($M_p\le64$) on the axis.

Three things replace the extrapolation where a prediction was being made. (i) The $N_{\rm eff}$
ledger shows *why* the extrapolation is unsafe: the trend is not $r$ vs $M_p$ but $r$ vs
independent looks, and at $\tau_{\rm cloud}=4$ d that saturates at 12.1 for $M_p=64$ — so the
hundreds-of-visits regime is where the assumed $\tau$ dominates the answer, which is exactly the
untested parameter. (ii) The new systematics result (major 5c) is the second brake: a coherent
coronal residual is *repeated* by revisits rather than averaged, so beyond some revisit count the
floor is calibration, not photons. Both are stated as reasons the curve must flatten, with the
$\epsilon\sim10^{-6}$ tolerance as the quantitative version. (iii) Registered visits per pixel
and spacecraft count are separated wherever they appear: 64 registered visits per position is a
$256$-slot campaign schedule for a 16-spacecraft formation, and the achievable $M_p$ depends on
campaign duration, per-pass dwell, slot geometry and availability — not on swarm size alone.

## 8. Target-ranking table uncertainties and transport separation

> *The target-ranking table is a useful synthesis, but its uncertainties should be propagated
> more visibly. The planets do not transit, radii are inferred from minimum masses, atmospheric
> and cloud properties are unknown, and target-specific stellar contamination and illumination
> may dominate the nominal photon ranking. The transportation, power, and communications
> discussion should be clearly separated into adopted literature values versus new results
> derived here.*

Section 6.1 is now titled "Target selection: a nominal-proxy table, not an uncertainty budget",
which is the honest description of what we could compute. We did **not** fabricate error bars:
the radii are $M\sin i$-derived through a mass–radius relation, the albedos and cloud
climatalogies are assumed, and for four of the five targets the planet's rotation state is
entirely unknown — which, given Table 9, is the dominant risk to the observation and not
subsumed by a radius uncertainty. The table therefore propagates *assumptions*, not
measurements, and the caption lists which column is which. Stellar contamination and
illumination are flagged as potentially dominating the nominal photon ranking, which is the
referee's point and is now in the text rather than in a footnote.

Transport, power and communications are separated in Section 6.2 into adopted literature values
(each cited) and quantities derived here (the $\Delta v$ and image-plane tracking budget from our
own kinematics, and the data-volume figures). The derived tracking numbers are reproduced from
code (`results/kinematics.json`: 20.9 m pitch, 45 s available, 0.93 m/s lower bound, 1.86 m/s for
a symmetric bang-bang profile at 0.041 m/s²) and no longer presented as literature.

---

# Minor comments

1. **Turyshev 2026a–e disambiguation.** Done. The five 2026 entries are suffixed a–e in the
   bibliography and cited consistently; each in-text citation now identifies which paper it
   supports (kernel, benchmark, UHR imaging, propulsion, coronal background).
2. **Metric averaging convention.** Stated in Section 4.6: all scalar metrics are computed per
   seed and then averaged, never on a mean map. The mean map is used only for Figure 3
   presentation, where it is labelled as a seed-mean of the *displayed* reconstruction and the
   quoted numbers are the per-seed means.
3. **Sensitivity to $\lambda=3\times10^{-3}$.** Done over six decades, cloud-free and cloudy,
   with the turnover located and a harmonic-band control on what the large-$\lambda$ gain is made
   of (major 6e, Section 5.13, Figure 7). The outcome contradicts v2's implicit claim of
   insensitivity — cloudy $r$ rises monotonically to $+0.178$ at $\lambda=10$ while the objective
   stays flat — and the paper says so, and states the missing truth-blind selection criterion as a
   limitation rather than adopting the better-looking weight.
4. **Spatial arrangement of the 16 simultaneous samples.** Section 3.3: the $64\times64$ image
   plane is scanned in boustrophedon order at $\Delta_{\rm img}=20.9$ m pitch, divided into 256
   dwell slots, and each dwell's 16 pixels are sampled simultaneously by spacecraft distributed
   across *adjacent raster tracks* with transverse separations of $\sim$80–300 m — i.e. a compact
   but not contiguous group of samples, deliberately not a kilometre-scale formation. That is
   exactly why the common-mode interpretation holds (one disk-integrated cloud state per slot,
   shared by the 16 samples) and why the removed subspace is 288-dimensional and not 1
   (comment 5). The v2 text implied a 1.3 km formation; the 1.338 km figure is the *diameter of
   the image cylinder*, not the craft separation.
5. **Rank/condition before and after deflation; which modes are lost.** Section 4.4 (`results/
   deflation_diag.json`). v2's "only a global mode is removed" and "6.25% rank loss / 93.75%
   information retained" are both replaced. The slot-mean operator removes 4,096 directions in
   *sample* space — one per dwell slot — and its null space on the 2,592-unknown surface grid has
   dimension **288**, with the constant surface mode surviving at gain 913.7 and overlapping the
   removed subspace by 0.236. The unregularised and deflated normal matrices have the same rank
   (2,304 of 2,592), so deflation as implemented removes no *additional* surface modes at
   fiducial sampling; what it removes is the slot offsets, which is a different statement from the
   one v2 made. Condition numbers before and after regularisation are in Table 3
   ($\kappa(\mathsf A)=\infty$ unregularised, $5.3\times10^{5}$ at $\lambda_{\rm eff}=0.0089$), and
   the "information retained" phrasing is gone.
6. **Mean-cloud versus global-albedo separation; bias if the correction is wrong.** Handled as
   major 3a rather than as a minor fix: $r$ is provably invariant, and the bias, which is not, is
   now quantified over the full $5\times5$ mis-specification grid ($+0.206$ to $-0.550$ in
   absolute albedo).
7. **"Surface albedo" not "topography".** Corrected throughout; the state vector is an albedo map
   and every comparison to prior topography-recovery work now says so.
8. **Telemetry qualified as photometric only.** Section 6: 2.10 MB per campaign (65,536 samples ×
   32 bytes: time tag, value, uncertainty, bookkeeping) and 10.4 kB per 36×72 float32 map. The v2
   "~2 GB for megapixel maps" is withdrawn as an order-of-magnitude error and the remaining
   sentence notes that navigation, metrology, calibration, health and relay telemetry are
   additional and may dominate.
9. **TDI acronym.** Noted in the Abstract and Section 1: *time-domain inversion* here, distinct
   from detector time-delay integration.
10. **Table 2 uncertainties / confirmed vs assumed.** Handled as major 8: the table is relabelled
    as a nominal-proxy ranking, each column marked as measured, derived, or assumed, and no
    propagated uncertainty is claimed where none could be computed.
11. **Why ~90° of illumination change is representative.** Section 3.1 now explains that the
    campaign's illumination drift is set by the *target's* orbital period, and that for the
    short-period M-dwarf systems of Table 13 a 90-day campaign completes several whole orbits, so
    the fiducial one-year-style planet with a partial illumination arc is the conservative case,
    not the typical one.
12. **Numerical precision.** Section 4.5 and Table 3 (`results/precision.json`): float32 vs
    float64 normal-matrix accumulation differs by $3.1\times10^{-7}$ in relative Frobenius norm
    ($8.1\times10^{-7}$ worst element), the right-hand side by $4.1\times10^{-7}$, and the
    resulting maps by $1.7\times10^{-13}$; block-summation order changes nothing
    ($5\times10^{-16}$); the ill-conditioned unregularised matrix is flagged with $\kappa=\infty$
    and its regularised $\kappa=5.3\times10^{5}$ reported, and a QR vs normal-equation cross-check
    is given. The regime note states that these are at $n=32$ and why the fiducial $n=64$ case
    cannot be doubled in this sandbox; the chunk-order check at $n=64$ is reported separately
    ($3.4\times10^{-13}$).

---

## Change log for the editor

**Structure.** v2: 5 sections, 5 equations, 2 tables, 7 figures. v3: 8 sections, 17 numbered
equations, 13 tables, 8 figures, 24 pages. New in v3: §3.4 resource ledgers, §4.2 exact nuisance
profiling, §4.3 exposure quadrature, §4.4 information audit, §4.5 precision, §5.3 resolution
(now including the latitude/illumination table added this round), §5.4 ablation, §5.5–5.6 cadence
law and controls, §5.8–5.9 geometry and profile likelihood, and the four new robustness
subsections of this round — §5.11 morphology, §5.12 weather parameters, §5.13 regularization,
§5.14 nulls — plus §5.15 systematics and §7 limitations (now items (i)–(ix)).

**Label → v3 number** (for locating changes): §5.1 `sec:rotation`, §5.2 `sec:clouds`,
§5.3 `sec:res`, §5.4 `sec:ablation`, §5.5 `sec:cadence`, §5.6 `sec:cadctl`, §5.7 `sec:robust`,
§5.8 `sec:geom`, §5.9 `sec:proflike`, §5.10 `sec:climrobust`, §5.11 `sec:morph`, §5.12
`sec:wxsens`, §5.13 `sec:lamsens`, §5.14 `sec:nulls`, §5.15 `sec:sys`; §6.1 `sec:targets`,
§6.2 `sec:sail`. Tables: 1 quadrature, 2 information audit, 3 precision, 4 clouds, 5 latitude and
illumination bands, 6 ablation, 7 cadence, 8 $N_{\rm eff}$, 9 geometry, 10 morphology, 11 weather
parameters, 12 systematics, 13 targets. Figures: 1 model, 2 validation, 3 gallery, 4
SSIM-vs-cover, 5 cadence, 6 robustness, 7 regularization and $\sigma_{\rm cl}$ sensitivity,
8 targets. v2 equations (1)–(5) map to v3 (1)–(5) unchanged; v3 (6)–(17) are new
(cloud covariance, nuisance model, profiling system $\mathsf H$, the two profile equations,
anchor and the anchored-deflation definitions, aliasing, Chen & Kipping mass–radius relation,
de-inclination, SNR rule, $\Delta v$ rule).

**New archives this round** (all read by `src/run_experiments.py merge` into
`results/audit.json`, and every one of them is what the corresponding text quotes):
`lambda_sweep_f0`/`_f0.55` (12 weights, 10 seeds, turnover located),
`lambda_resolution` (harmonic-band control on the large-$\lambda$ gain),
`sigma_sensitivity` plus `sigma_sensitivity_free` and `sigma_sensitivity_v2` (assumed cloud
amplitude, three estimators), `weather_misspecified`/`_recalibrated`/`_sensitivity` (six true
weather fields), `morphology_supercontinent_f0.55` / `_f0` and `morphology_archipelago_f0.55` /
`_f0` (10 seeds each, paired against earthlike on the same seeds), `latband` (six latitude bands
scored from the archived fiducial maps, with the illumination and column-energy diagnostics),
and `static_reference` (frozen planet at identical dose, paired against rotating cloud-free and
cloudy). New commands: `robust_morph`, `latband`, `lam_res`, `sigma_sens_est`.

**Claims withdrawn, with the reason** (all also stated at the point in the text):
in-flight ephemeris refinement via profile likelihood ($\chi^2$ is phase-invariant to $10^{-11}$);
"p < 10⁻³" and "p < 0.02" (replaced by exact sign-flip values with their floors);
"14–23×" noise inflation (measured 12.8–21.0× in σ, 163–440× in variance);
"~2 GB" telemetry (2.10 MB campaign / 10.4 kB map);
"virtually zero information loss" from rotation (residual $1-r\simeq0.021$, attributable to
aperture and regularisation; the static ideal-data reference is now measured and scores *lower*,
0.407, than the rotating planet — see major 6g);
"93.75% of information retained" by deflation (replaced by the nullity-288 audit);
deflation as the primary algorithmic gain ($\Delta r=+0.041$: replaced by profiling +0.056 with
$p=1.95\times10^{-3}$, and by the finding that profiling vs the v2 approximation is $p=0.13$);
ultrafast-cadence overhead penalty (no data below 429.6 s);
"$r$ insensitive to $\lambda$ and $\lambda=3\times10^{-3}$ optimal" (six-decade sweep: cloudy $r$
monotone to $+0.178$ at $\lambda=10$, cloud-free turnover at 0.3, and no minimum in the objective);
"robust to surface morphology" (re-measured and now bounded: granularity free, coherence costs
0.040);
the v2 morphology and regularisation scans themselves (superseded quadrature and approximate
deflation — both re-run for this round);
overhead-offsets-gains and revisit-protects-against-drift (both opposite to measurement);
"propagated uncertainties" in the target table (nominal proxies).

**Reproducibility.** `src/run_experiments.py <command>` regenerates every archive; commands are
checkpointed per seed, so a partial run leaves a consistent tree. `results/audit.json` records
seed counts for every number, and `paper/main.tex`, `src/make_figures.py` and the tables read
only from these archives — the figure script contains no literals. Simulations, operators and
$\sigma_{\rm cl}$ calibrations are cached by content-keyed filename, so "the same photons" is a
statement enforced by the code rather than by a comment.

---

We are grateful to the referee for a review that was, in effect, an independent audit of this
work. Several corrections lowered our headline numbers and one removed a claim we had built a
mission-design argument on; the manuscript is better for it and we would not have found all of
these ourselves.

Sincerely,
**Sanskar Sontakke**
Independent Researcher · sanskarsontakke@gmail.com
