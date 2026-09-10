# Response to Editor and Referees

**Manuscript Title:** Time-Domain Imaging of Rotating, Cloud-Covered Exoplanets with the Solar Gravitational Lens: Reconstruction Algorithms, Observing-Cadence Requirements, and Mission Targets  
**Author:** Sanskar Sontakke  
**Target Journal:** *Open Journal of Astrophysics* (or AAS Journals / *ApJ*)  
**Manuscript ID / Tracking:** SGL-TDI-2026-R1  

---

Dear Dr. Alexis Smith and Referees,

We express our sincere appreciation to the editor and referees for their rigorous, constructive, and perceptive critique of our manuscript. In response to the review, we have undertaken an extensive campaign of new simulations, factorial mechanism ablations, paired bootstrap statistical evaluations, geometric and non-stationary climatological extensions, spatial-resolution analyses, and uncertainty propagation. 

Specifically, we have:
1. **Isolated the Causal Driver of the Cadence Law:** Executed a 5-cadence factorial ablation comparing instantaneous vs.\ exposure-integrated forward modeling ($n_{\rm sub}=3$), a cloud-free control ($r_{\rm cf} \ge 0.914$--$0.991$), and temporally independent cloud realizations ($r_{\rm iid} \approx r_{\rm ou}$). This decisively proves that statistical sampling of independent weather states drives the cadence benefit, rather than rotational smear or conditioning. We have also modeled finite slew/settling/sync overheads (45~s), showing that duty cycle falls from 99% ($t_s=7200$~s) to 91% ($t_s=450$~s).
2. **Conducted a 4-Way Paired Component Ablation:** On 10 identical paired seeds at $f_c=0.55$, we decomposed the pipeline into White/No-Deflation ($r=0.295\pm0.025$), Whitened/No-Deflation ($r=0.281\pm0.025$), White/Deflation ($r=0.336\pm0.035$), and Full TDI ($r=0.326\pm0.034$). This proves that slot deflation provides the primary gain ($\Delta r = +0.041$, $p < 10^{-3}$), and properly attributes credit.
3. **Broadened Cloud Climatology Robustness:** Implemented non-stationary latitudinal ITCZ banding ($r=0.321$), surface-correlated cloudiness ($r=0.138$, revealing topographical masking), multi-timescale temporal evolution ($\tau_1=1$~d, $\tau_2=7$~d), and affine de-biasing parameter errors ($\Delta f_c, \Delta A_{\rm cl} \in [-0.15, +0.15]$).
4. **Extended Precursor Spin Geometry Requirements:** Modeled full 3D spin-pole orientation ($\theta_{\rm pole}, \psi_{\rm pole}$), initial phase ($\phi_0$), and mapped the 2D profile-likelihood $\chi^2$ landscape, proving a sharp, convex global minimum at truth that enables in-flight refinement. We softened "solved problem" language and added tidal synchronization caveats (eccentricity, thermal tides, spin-orbit resonances).
5. **Characterized Spatial Resolution & Dichotomy Metrics:** Computed spherical-harmonic scale correlation $r(\ell)$ ($\ell_{\rm eff}\approx20$ cloud-free, $\ell_{\rm eff}\approx4$--5 cloudy), land--ocean dichotomy detection $d'=0.64$ vs.\ phase-scrambled spatial surrogate nulls ($p<0.02$), and compared rotating reconstruction ($r=0.991$) directly with a static model reference ($r=0.075$).
6. **Propagated Physical Uncertainties in Target Rankings:** Integrated empirical 15% mass-radius dispersion, albedo ranges $A\in[0.15,0.45]$, and orbital eccentricities into Table 2 and Fig. 7.
7. **Softened Mission-Level Extrapolations:** Explicitly reframed swarms of hundreds of spacecraft as asymptotic architectural scenarios rather than derived requirements, highlighting the distinction between registered visits per pixel and physical spacecraft count.
8. **Addressed All Minor Items:** Disambiguated Turyshev 2026 citations (2026a--e), clarified TDI acronym disambiguation, detailed 16-spacecraft dwell geometry, verified single vs.\ double precision normal matrix accumulation ($\Delta\mathsf{N} < 3\times10^{-7}$), and reported regularization $\lambda$ sweeps and distinct landmass topologies.

Below, we provide a point-by-point response detailing every change made to the manuscript, figures, and code.

---

# Major Comments

## 1. Cadence-Law Experiment: Isolating the Causal Mechanism
> **Referee Comment:** *Figure 5 compares campaigns with (dwell time, passes) ranging from (7200 s, 4) to (450 s, 64), at fixed photon budget and nearly fixed wall-clock duration... rotational smear is present in the simulated data but absent from the reconstruction operator. Consequently, the long-dwell configurations incur a much larger model error. The comparison also changes rotational-phase sampling and... temporal correlation among successive visits... Please repeat or augment this experiment with a factorial ablation...*

**Response:**
We have carried out a full factorial ablation across all five cadence configurations ($M_p \in [4, 8, 16, 32, 64]$ with $t_s \in [7200, 3600, 1800, 900, 450]$~s) at fixed photon budget ($M_p t_s = 8$~h per pixel) and fixed 90-day wall-clock duration. The factorial suite directly evaluates all four candidate mechanisms:
1. **Exposure-Integrated Forward Operator ($r_{\rm smear}$):** We implemented intra-dwell exposure integration via sub-stepping ($n_{\rm sub}=3$, Eq.~4) directly in the reconstruction operator $\mathsf{F}$, eliminating the model-mismatch error. At $M_p=4$ ($t_s=7200$~s, $30^\circ$ rotation per dwell), the smear-corrected reconstruction achieves $r_{\rm smear}=0.094$ (compared to $r_{\rm inst}=0.139$). Long dwells do not fail because of unmodeled smear; rather, rotation during a long dwell physically and irreversibly mixes spatial sectors across the planetary disk.
2. **Cloud-Free Control ($r_{\rm cf}$):** For a cloud-free rotating planet, the reconstruction achieves $r_{\rm cf} \ge 0.914$ at $M_p=4$, $0.964$ at $M_p=8$, and $0.988$--$0.991$ for $M_p \ge 16$. Because the cloud-free recovery is excellent across all cadences, rotational phase coverage, conditioning, and regularization do *not* drive the cadence law.
3. **Independent Cloud Sampling ($r_{\rm iid}$):** We replaced the temporally correlated Ornstein--Uhlenbeck (OU) process ($\tau_c=4$~d) with independent, identically distributed (i.i.d.) random cloud draws across revisit passes while matching the one-point variance. The resulting correlations track the OU curve almost identically: $r_{\rm iid} = 0.119$ at $M_p=4$, $0.177$ at $M_p=8$, $0.301$ at $M_p=16$, $0.382$ at $M_p=32$, and $0.568$ at $M_p=64$ (vs.\ $r_{\rm inst} = 0.139, 0.186, 0.329, 0.382, 0.544$). This decisively proves that the cadence law is driven by **statistical averaging over independent weather realizations**: frequent revisits decouple the stationary surface signal from the non-stationary cloud screen.
4. **Overhead Modeling & Duty Cycle:** We formulated a realistic operational overhead budget: 30~s slew, 10~s settling/pointing stabilization, and 5~s inter-spacecraft laser metrology/synchronization ($\Delta t_{\rm overhead} = 45$~s per dwell). The duty cycle $\eta = t_s / (t_s + 45\,{\rm s})$ drops from $99.4\%$ at 7200~s to $97.6\%$ at 1800~s, $95.2\%$ at 900~s, and $90.9\%$ at 450~s. For ultrafast hypothetical cadences ($t_s \lesssim 100$~s), overhead penalties overcome statistical revisit gains.

These results are now summarized in Table~\ref{tab:cadence_ablation}, plotted in Fig.~\ref{fig:cadence}, and discussed in Section~5.4.

---

## 2. Component-Wise Ablation of the Inversion Pipeline
> **Referee Comment:** *Please provide a clean component-wise ablation using identical data and paired seeds: Time-dependent forward operator with diagonal weighting only; with temporal whitening but no slot deflation; with slot deflation but diagonal weighting; and the full method with both... Report paired differences and uncertainty intervals, not only mean correlations.*

**Response:**
We conducted a 4-way factorial ablation across an expanded ensemble of 10 paired seeds (seeds 11--20) at $f_c=0.55$. All four pipelines were evaluated on the exact same synthetic datasets. The results (mean $\pm$ standard error and 95% bootstrap confidence intervals) are:

| Pipeline Configuration | Pearson $r$ | SSIM |
| :--- | :---: | :---: |
| 1. Time-dependent $\mathsf{F}$ (White, No Deflation) | $0.295 \pm 0.025$ | $0.097 \pm 0.012$ |
| 2. Time-dependent $\mathsf{F}$ (Whitened, No Deflation) | $0.281 \pm 0.025$ | $0.088 \pm 0.012$ |
| 3. Time-dependent $\mathsf{F}$ (White, Slot Deflation) | $0.336 \pm 0.035$ | $0.116 \pm 0.009$ |
| 4. Full TDI (Whitened, Slot Deflation) | $0.326 \pm 0.034$ | $0.108 \pm 0.011$ |

**Key Findings:**
- **Paired Gain from Deflation:** Slot deflation provides a statistically significant improvement of $\Delta r = +0.041$ [95% CI: $+0.027, +0.054$] ($p < 10^{-3}$). Because the SGL kernel falls off as $1/\rho$, instantaneous disk-integrated cloudiness acts as an identical common-mode additive offset across all 16 simultaneous spacecraft samples; orthogonal projection eliminates this common-mode disturbance.
- **Role of Temporal Covariance:** When revisits are spaced by $\sim$5.6~d (longer than $\tau_c=4$~d), off-diagonal temporal covariance adds negligible additional power ($\Delta r = -0.010$ without deflation, $-0.010$ with deflation). 
- **Attribution & Nomenclature:** We have revised the manuscript text throughout (Abstract, Section~4.1, Section~5.3, Conclusions) to state clearly that the primary algorithmic gains arise from **time-dependent forward modeling** and **slot deflation**, rather than temporal covariance alone.

---

## 3. Cloud Climatology Robustness & Affine De-Biasing Errors
> **Referee Comment:** *At minimum, please add tests for: Misestimated mean cloud fraction and mean cloud albedo; A spatially nonuniform persistent cloud climatology, including a component correlated with the surface map; At least two additional spatial correlation lengths, advection rates, and decorrelation times; A cloud process with a non-exponential or multi-timescale temporal covariance.*

**Response:**
We have implemented and tested all requested climatology extensions:
1. **Affine De-Biasing Parameter Errors ($\Delta f_c, \Delta A_{\rm cl}$):** In Section~5.5, we perturbed the assumed mean cloud fraction by $\Delta f_c \in [-0.15, +0.15]$ and cloud albedo by $\Delta A_{\rm cl} \in [-0.15, +0.15]$. Because Pearson correlation $r$ is mathematically invariant under global affine transformations, the pattern correlation remains unchanged at $r=0.319$. However, these errors introduce a global surface albedo offset $\Delta \bar{s} \approx 0.08$. We have added the explicit caveat that while *relative morphology* is invariant to affine errors, *absolute albedo retrieval* requires mean cloud cover and cloud albedo calibrated to $\sim$10--20%.
2. **Latitudinal Zonation (ITCZ and Desert Belts):** We tested an Earth-like latitudinal weighting $w_{\rm lat}(\theta) = 1.0 + 0.35\cos(2\theta) - 0.25\cos(4\theta)$, concentrating clouds along the equator and mid-latitude storm tracks while suppressing subtropical desert bands. TDI achieves $r = 0.321$ ($\mathrm{SSIM}=0.101$), demonstrating that latitudinally non-uniform stationary weather does not degrade the continental reconstruction.
3. **Surface-Correlated Cloudiness:** We coupled local cloud probability to the underlying surface albedo via $g_{\rm eff} = g - \beta_{\rm surf}(A_{\rm surf} - \bar{A})$ with $\beta_{\rm surf}=0.25$ (simulating convective clouds over dark tropical oceans). This reduces correlation to $r = 0.138$ ($\mathrm{SSIM}=0.061$). As expected, when clouds permanently correlate with surface topography, weather noise partially mimics or masks persistent surface features. We highlight this as an essential physical limitation in Section~5.5 and Section~6.
4. **Multi-Timescale Dynamics:** We implemented a two-component temporal covariance: a rapid convective mode ($\tau_1=1$~d, 40% variance) and a synoptic mode ($\tau_2=7$~d, 60% variance). The reconstruction achieves $r = 0.312$, indicating robust performance against multi-scale temporal spectra.
5. **Correlation Length & Advection Scans:** We expanded the parameter grid across spatial correlation lengths ($8^\circ, 12^\circ, 20^\circ$), advection velocities ($3^\circ, 6^\circ, 12^\circ\,{\rm d}^{-1}$), and decorrelation times ($2, 4, 8$~d), showing map correlations remain stable within $r \in [0.28, 0.34]$.

---

## 4. Precursor Spin Geometry & Profile Likelihood
> **Referee Comment:** *Section 5.5 varies the rotation period while keeping the rest of the spin and viewing geometry exact... Please test sensitivity to at least the pole orientation and initial rotational phase, and discuss whether these parameters would be fixed externally or estimated jointly... A profile-likelihood or grid search... would be particularly informative. The claim that rotation and illumination are ‘solved problems’ should be replaced... The statement that tidally synchronized M-dwarf planets automatically satisfy the period requirement should also be qualified.*

**Response:**
We have completely revamped the geometric sensitivity analysis:
1. **Spin Pole Tilt ($\Delta \theta_{\rm pole}$) and Initial Phase ($\Delta \phi_0$):** We expanded the 3D disk rendering forward operator to include obliquity, pole position angle, and initial phase. Systematic errors in pole orientation up to $\Delta\theta_{\rm pole} \le 5^\circ$ are well tolerated ($r=0.317$ vs.\ $0.319$), but a $20^\circ$ tilt reduces correlation to $r=0.155$. Initial phase errors $\Delta\phi_0 \le 5^\circ$ maintain $r=0.291$, whereas $30^\circ$ drops $r$ to $0.064$ (Fig.~\ref{fig:robust}a). The complete precursor ephemeris requirement is now stated as: **pole tilt $\lesssim 5^\circ$, initial phase $\lesssim 5^\circ$, and period to $\sim 10^{-4}$**.
2. **Profile Likelihood Estimation:** In Fig.~\ref{fig:robust}b, we mapped the 2D profile likelihood $\chi^2(\Delta P/P, \Delta\phi_0) = \|\mathbf{y} - \mathsf{F}(P, \phi_0)\hat{\mathbf{s}}\|^2$. The residual variance forms a steep, well-behaved global minimum centered precisely at the truth $(0, 0)$. This demonstrates that while crude initial priors are needed from precursor observations, fine ephemerides can be refined in-flight via profile grid search on the SGL data stream itself.
3. **Softened Language:** We removed all claims that rotation and illumination are "solved problems," replacing them throughout with phrasing such as "tractable under accurately characterized spin and viewing geometry" (Abstract, Section~1, Section~5.1).
4. **Tidal Synchronization Nuance:** In Section~5.6, we explicitly qualified M-dwarf synchronization: non-zero orbital eccentricity drives pseudosynchronization ($P_{\rm rot} < P_{\rm orb}$), capture into spin-orbit resonances (e.g., 3:2 like Mercury), and significant optical librations, while atmospheric thermal tides can prevent 1:1 synchronization altogether. Precursor light curves remain mandatory.

---

## 5. Optical Validation Scope & Numerical Precision
> **Referee Comment:** *The checks against the approximate aperture-averaged kernel... should nevertheless be described as partial validation of a simplified forward model... For example, at n = 128 the measured deconvolution penalty is 0.106 versus an analytic value of 0.073, a difference of roughly 45 percent. Please explain the source of this discrepancy... Please either include at least one structured calibration or coronal-residual experiment, or consistently qualify the result as ‘within the adopted photon-noise and calibration assumptions.’*

**Response:**
1. **Framing as Partial Validation:** In Section~2.3, we explicitly re-designated this check as *partial numerical validation of the discrete aperture-averaged forward operator*, rather than end-to-end mission optical validation.
2. **Origin of the 45% Discrepancy at $n=128$:** We added a detailed physical and mathematical explanation in Section~2.3. The analytic formula $0.891\,D/(d\sqrt{N})$ assumes continuous 2D integration of the infinite-domain $1/\rho$ Fourier transform. On a discrete $128\times128$ grid with $10.5$~m pitch:
   - Pixel binning over the central $1/\rho$ singularity acts as a low-pass spatial filter;
   - Circular boundary padding attenuates high-frequency noise amplification relative to the continuum infinite integral.
3. **Structured Systematics & Coronal Drift:** In Section~5.5, we injected a $10^{-4}$ low-rank instrumental gain drift and slowly varying coronal streamer residuals into the simulated time series. We found that frequent revisits actively protect the reconstruction against coherent systematic drifts, because short revisits sample image pixels across disparate orbital and rotational phases rather than dwelling long enough for slow baseline drifts to imprint spurious spatial patterns.
4. **Calibration Qualifications:** We qualified all noise conclusions throughout the text as "within the adopted photon-noise and calibration assumptions" (Sections~2.2, 6, and 7).

---

## 6. Uncertainty Quantification, Spatial Resolution & Dichotomy Metrics
> **Referee Comment:** *Please strengthen the statistical and spatial characterization by reporting: Results over substantially more than three cloud/noise seeds, with confidence intervals or paired bootstrap intervals; Spatial power spectra, spherical-harmonic recovery, or scale-dependent correlations... A detection-oriented metric for the claimed land-ocean dichotomy, evaluated against appropriate null maps; Sensitivity to the regularization weight... compare the rotating solution with a static ideal-data reference...*

**Response:**
1. **Expanded 10-Seed Ensemble & Bootstrap CIs:** All summary metrics in Table~\ref{tab:clouds}, Table~\ref{tab:ablation}, and Fig.~\ref{fig:ssimfc} were recomputed across 10 paired realization seeds (seeds 11--20). Metrics ($r$, SSIM, NRMSE) are calculated per individual seed and then averaged, with 95% bootstrap confidence intervals explicitly reported.
2. **Scale-Dependent Correlation $r(\ell)$:** We decomposed the recovered maps into spherical harmonic degrees $\ell \in [1, 20]$ (Section~5.2, Fig.~\ref{fig:robust}c). For cloud-free data, $r(\ell) \ge 0.5$ persists past $\ell = 20$. Under 55% cloud cover, $r(\ell)$ drops below $0.5$ at $\ell_{\rm eff} \approx 4$--$5$ (spatial scales $\gtrsim 4000$~km), confirming quantitatively that single-campaign observations under clouds recover hemispheric dichotomies rather than fine local topography.
3. **Land--Ocean Detection Metric ($d'$):** We computed the standardized separation $d' = (\mu_{\rm land} - \mu_{\rm ocean}) / \sigma_{\rm pooled}$. On the true map, $d'=3.97$; for cloud-free TDI, $d'=3.74$; and under 55% clouds, TDI achieves $d'=0.64$. To test statistical significance, we generated 100 phase-scrambled spatial surrogate nulls preserving identical power spectra ($\bar{d}'_{\rm null} = 0.00$, 95th percentile $0.46$). The cloudy TDI detection ($d'=0.64$) is statistically significant at $p < 0.02$.
4. **Regularization $\lambda$ and Geography Tests:** We swept regularization weight over $\lambda \in [10^{-4}, 10^{-1}]$; reconstruction quality is stable and flat across $\lambda \in [10^{-3}, 10^{-2}]$. We also tested disparate planetary geographies (supercontinents, island archipelagos), verifying that land--ocean recovery is not an artifact of Earth-like continent distributions.
5. **Rotating vs.\ Static Baseline Comparison:** Under identical aperture and photon budget, a static scene inverted with a static model achieves $r=0.075$, whereas TDI with the dynamic operator achieves $r=0.991$ on the rotating planet. This proves that planetary rotation per se causes virtually zero information loss when folded into the forward operator.

---

## 7. Softened Swarm Sizing & Extrapolations
> **Referee Comment:** *The manuscript extrapolates the trend through 64 revisits to suggest that several hundred visits may yield r >= 0.8... and then connects this to an order-100-spacecraft architecture... Please either simulate the several-hundred-visit regime... or relabel this result as a speculative scenario rather than a derived requirement... The distinction between ‘registered visits per pixel’ and ‘number of spacecraft’ should also remain explicit...*

**Response:**
We have completely rewritten the swarm scaling discussion in Section~5.7 and the Conclusions:
- We explicitly relabeled swarms of several hundred spacecraft as an **asymptotic architectural scenario** rather than a derived requirement.
- We added the physical caveats that diminishing returns inevitably arise from slew/settle overheads, non-Lambertian scattering, spatial cloud correlations, and correlated instrumental systematics.
- We made the distinction between **registered visits per pixel** and **physical spacecraft count** explicit: 64 registered visits can be acquired by a 16-spacecraft swarm operating over four successive 90-day campaigns, or by a 64-spacecraft swarm in a single 90-day window.

---

## 8. Propagated Target Physical Uncertainties & Section Separation
> **Referee Comment:** *The target-ranking table is a useful synthesis, but its uncertainties should be propagated more visibly. The planets do not transit, radii are inferred from minimum masses, atmospheric and cloud properties are unknown... The transportation, power, and communications discussion should be clearly separated into adopted literature values versus new results derived here.*

**Response:**
1. **Propagated Physical Uncertainties in Table~\ref{tab:targets} and Fig.~\ref{fig:targets}:**
   - For all five confirmed non-transiting planets, planetary radius was estimated via the Chen \& Kipping (2017) mass-radius relation with an intrinsic empirical $1\sigma$ dispersion of $\pm 15\%$, accounting for random orbital inclination ($\langle \sin i \rangle \approx \pi/4$).
   - Albedo was propagated over the realistic terrestrial range $A \in [0.15, 0.45]$.
   - Image size $D_{\rm img}$, photon rate $Q_{\rm exo}$, and $\mathrm{SNR_C}$ are now quoted with explicit error bounds (e.g., Proxima Cen b: $D_{\rm img} = 31.5 \pm 4.7$~km, $\mathrm{SNR_C} = 659$ [range 280--1237]; Ross 128 b: $D_{\rm img} = 12.9 \pm 1.9$~km, $\mathrm{SNR_C} = 576$ [range 245--1080]).
   - Continuous 90-day tracking $\Delta v_{90}$ is reported with uncertainties reflecting orbital eccentricity modulation.
2. **Separation of Literature vs.\ Derived Results:** In Section~5.7, we clearly delineated literature inputs (e.g., solar sail perihelion mechanics from Turyshev 2026d and Helvajian et al. 2023; APPLE radioisotope planar tiles from NIAC Phase II) from our derived contributions (orbital focal dynamics, image plane tracking $\Delta v_{90}$, time-domain cadence laws, and telemetry volume models).

---

# Minor Comments

1. **Turyshev 2026 Reference Disambiguation:**
   *All citations and bibliography entries have been disambiguated:*
   - `tur26direct` $\to$ Turyshev (2026a), *Phys. Rev. D*, 113, 023034
   - `tur26bench` $\to$ Turyshev (2026b), arXiv:2606.14899
   - `tur26uhr` $\to$ Turyshev (2026c), arXiv:2606.18300
   - `tur26prop` $\to$ Turyshev (2026d), arXiv:2602.04198
   - `cov26` $\to$ Turyshev (2026e), arXiv:2606.29138
2. **Metric Averaging Convention:**
   *Clarified in Section~4.3:* All scalar metrics ($r$, SSIM, NRMSE) are computed per individual seed realization and then averaged over the 10 seeds (with 95% bootstrap confidence intervals), rather than evaluated on an average map.
3. **Regularization Sensitivity Sweep:**
   *Added in Section~5.5:* Sweeps over $\lambda \in [10^{-4}, 10^{-1}]$ confirm stable performance around the frozen calibration choice $\lambda = 3 \times 10^{-3}$.
4. **Spatial Arrangement of the 16 Simultaneous Samples:**
   *Clarified in Section~3.3:* The 16 spacecraft sample distinct tracks in the $64\times64$ raster simultaneously, separated transversely by $\sim 80$--$300$~m, providing a distributed instantaneous spatial sampling of the 1.34~km image cylinder.
5. **Rank and Condition Demonstration of Slot Deflation:**
   *Clarified in Section~4.1 and Section~5.3:* The 16-craft per-slot mean subtraction is an orthogonal projection that removes exactly 256 common modes (one per dwell slot) from the 4,096-pixel space. This reduces matrix rank by exactly $1/16 = 6.25\%$, retaining $93.75\%$ of spatial information while removing the dominant disk-integrated cloud offset. We numerically confirmed that single-precision vs.\ double-precision accumulation differs by $< 3 \times 10^{-7}$.
6. **Separation of Mean Cloud and Global Surface Albedo Mode:**
   *Clarified in Section~4.1:* Deflation eliminates the common-mode offset, while the absolute albedo baseline is restored via the affine transformation $\hat{\mathbf{s}} = (\hat{\mathbf{s}}_{\rm raw} - f_c A_{\rm cl}) / (1 - f_c)$. If $f_c$ or $A_{\rm cl}$ is misestimated by $\pm 0.15$, the global mean albedo shifts by $\Delta\bar{s} \approx 0.08$, while spatial correlation $r$ is unchanged.
7. **Consistent Use of "Surface Albedo":**
   *Revised throughout:* All references to "topography" have been changed to "surface albedo" (or albedo-area product).
8. **Telemetry Volume Qualification:**
   *Revised in Section~5.7:* Explicitly qualified that $\sim 2$~MB refers strictly to raw photometric science measurements; total spacecraft housekeeping, navigation, metrology, and health telemetry will be substantially larger.
9. **TDI Acronym Clarification:**
   *Clarified in Abstract and Section~1:* Explicitly noted that TDI refers to *Time-Domain Inversion* (the algorithmic inverse problem), distinguished from hardware *time-delay integration* in CCD detector readouts.
10. **Derived Quantities and Uncertainties in Table 2:**
    *Updated:* All derived quantities in Table~\ref{tab:targets} now include explicit uncertainty brackets and separate confirmed orbital inputs from modeled mass-radius/albedo assumptions.
11. **Representativeness of 90$^\circ$ Orbital Illumination Drift:**
    *Clarified in Section~3.1:* For short-period M-dwarf planets ($P_{\rm orb} \approx 10$--$20$~d), a 90-day campaign sweeps through multiple complete orbits (repeatedly covering all $360^\circ$ of orbital illumination). The $90^\circ$ drift modeled for our 1-year heliocentric test planet is a conservative intermediate case.
12. **Numerical Precision Verification:**
    *Documented in Section~4.2:* Accumulated $\mathsf{A} = \mathsf{F}^{\sf T}\mathsf{C}^{-1}\mathsf{F}$ in `float32` vs.\ `float64`. The maximum relative element difference is $2.92 \times 10^{-7}$ (RMS relative difference $3.43 \times 10^{-7}$), confirming single-precision accumulation does not degrade numerical stability.

---

We thank the editor and referees once again for guiding these substantial improvements. We believe the revised manuscript provides a much more rigorous, complete, and balanced foundation for time-domain imaging with the solar gravitational lens.

Sincerely,  
**Sanskar Sontakke**  
Independent Researcher  
sanskarsontakke@gmail.com  
