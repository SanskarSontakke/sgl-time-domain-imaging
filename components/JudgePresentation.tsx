"use client";

import React, { useState, useEffect } from "react";
import { 
  ChevronLeft, ChevronRight, Play, Maximize2, Minimize2, Sparkles, 
  HelpCircle, MessageSquare, CheckCircle2, ArrowRight, 
  Compass, ShieldCheck, Zap, Layers, BarChart2, Globe,
  Download, Video, Image as ImageIcon
} from "lucide-react";
import SglCylinderSimulator from "./simulators/SglCylinderSimulator";
import CadenceExplorer from "./simulators/CadenceExplorer";
import CloudDeflationDemo from "./simulators/CloudDeflationDemo";
import TargetCatalogExplorer from "./simulators/TargetCatalogExplorer";
import ImageReconstructionSandbox from "./simulators/ImageReconstructionSandbox";
import EinsteinRingSimulator from "./simulators/EinsteinRingSimulator";
import FleetFormationSimulator from "./simulators/FleetFormationSimulator";
import PlanetRotationPlayer from "./simulators/PlanetRotationPlayer";
import MediaZoomViewer from "./MediaZoomViewer";
import LatexMath from "./LatexMath";

interface Slide {
  id: number;
  badge: string;
  title: string;
  subtitle: string;
  takeaways: (string | React.ReactNode)[];
  speakerNotes: string;
  judgeFaq: { q: string; a: string }[];
  interactiveComponent?: "cylinder" | "cadence" | "deflation" | "targets" | "sandbox" | "einstein" | "fleet" | "planet-video";
  mediaSrc?: string;
  mediaTitle?: string;
  mediaDesc?: string;
  mediaBadge?: string;
  stats: { label: string; value: string | React.ReactNode; desc: string }[];
}

const SLIDES: Slide[] = [
  {
    id: 1,
    badge: "Problem Statement",
    title: "Direct Imaging of an Exo-Earth Across 900 Trillion Kilometers",
    subtitle: "Why conventional space telescopes can never resolve continents on worlds around other stars.",
    interactiveComponent: "planet-video",
    mediaSrc: "/videos/planet_rotation_clouds.gif",
    mediaTitle: "Exo-Earth Rotation & Cloud Advection Simulation",
    mediaDesc: "Illustrative render. The simulated planet has zero obliquity and no jet: clouds advect at 6°/day (≈7.7 m/s) with a 4-day decorrelation time.",
    mediaBadge: "Simulation Video",
    takeaways: [
      "The goal of this paper is albedo mapping: recovering persistent surface contrast (continents vs. oceans) on a habitable-zone world, not photographing terrain or vegetation.",
      "At 30 pc — the paper's nominal proxy — an Earth-sized planet subtends only ~2.8 microarcseconds across, so a 64×64 map needs ~0.04 μas per resolution element.",
      "The paper's own scaling: a 10×10 surface map at 10 pc needs ~0.85 μas elements, i.e. a ~10² km filled aperture, and conventional concepts still integrate for 10⁴–10⁵ yr once realistic backgrounds are included (Turyshev 2026a).",
      "We need a radically different optical element to magnify distant worlds: the Sun itself.",
    ],
    speakerNotes: "Imagine trying to read the date on a coin a quadrillion kilometers away. That is the challenge of imaging an Earth-like exoplanet. An Earth twin at 30 pc is 2.8 microarcseconds across, so every filled-aperture and interferometric concept sees a single unresolved pixel — and the deconvolution and integration-time costs scale with aperture diameter, not with patience. To map the surface of an alien world we must turn to a prediction of General Relativity: the Solar Gravitational Lens.",
    judgeFaq: [
      {
        q: "Why can't the James Webb Space Telescope (JWST) resolve continents?",
        a: "JWST's 6.5-m diffraction limit is ~77 microarcseconds at 2 μm (~23 μas at 0.6 μm), while an Earth twin at 30 pc is ~2.8 μas across. The resolution element is 8–27 times larger than the entire planet, so it is one unresolved pixel no matter how long JWST stares."
      },
      {
        q: "What is an 'exo-Earth'?",
        a: "An Earth-sized, rocky exoplanet orbiting within the habitable ('Goldilocks') zone of its star where liquid water can exist on the surface. The simulations here use a generic Earth-radius proxy at 30 pc, not a named planet's climate."
      }
    ],
    stats: [
      { label: "Target Distance", value: "30 pc", desc: "~9×10¹⁴ km (nominal proxy)" },
      { label: "Angular Size", value: "~2.8 μas", desc: "Earth diameter at 30 pc" },
      { label: "Conventional Aperture", value: "~10² km", desc: "For a 10×10 map at 10 pc" },
      { label: "This Paper Delivers", value: "36×72 grid", desc: "ℓ ≲ 9 usable under clouds" },
    ],
  },
  {
    id: 2,
    badge: "Physical Principle",
    title: "The Solar Gravitational Lens: Einstein's Cosmic Magnifier",
    subtitle: "Harnessing the Sun's spacetime curvature as a natural 100-billion-times optical amplifier.",
    takeaways: [
      <span>Einstein's General Relativity predicts that the Sun's mass bends light rays, forming a gravitational lens whose strong-interference region starts at <LatexMath math="z_0 \simeq b^2/2r_g \simeq 547.8\text{ AU}" /> for rays grazing the solar limb.</span>,
      <span>The Solar Gravitational Lens (SGL) provides on-axis amplification of <LatexMath math="\mu_0 = 4\pi^2 r_g/\lambda \simeq 1.2\times10^{11}" /> at <LatexMath math="\lambda = 1\,\mu\text{m}" /> and angular resolution of order <LatexMath math="10^{-10}" /> arcsec.</span>,
      <span>At 650 AU, the light of an Earth-radius planet at 30 pc is compressed into an image cylinder only <LatexMath math="D_{\rm img} \approx 1.34\text{ km}" /> wide.</span>,
      <span>A 1-meter telescope in that cylinder acts as a single-pixel detector that must physically traverse the image plane: it replaces the ~10² km conventional aperture, but it buys photons and magnification, not surface detail, which the inversion has to reconstruct.</span>,
    ],
    speakerNotes: "Instead of building a 100-kilometer-class mirror, we let the Sun do the work. The Sun's gravitational field focuses light from a distant exoplanet into a narrow 1.34-kilometer image cylinder near 650 AU. A meter-class telescope inside that cylinder collects the planetary Einstein ring with ~10¹¹ amplification for free. The catch: it is a single pixel, so the map has to be assembled by scanning and by inverting the scan — which is what this paper is about.",
    judgeFaq: [
      {
        q: "Where is 650 AU, and how far is that?",
        a: "1 AU is the Earth-Sun distance (150 million km). 650 AU is about 15 times farther than Pluto, while the Voyagers are near 140–170 AU. Reaching it in 20 years needs v∞ ≈ 154 km/s (32.5 AU/yr); the paper's only concept in that range is a deep-perihelion solar sail (105–155 km/s at areal densities of 2.3–4.9 g/m²), not chemical propulsion (3–4 AU/yr)."
      },
      {
        q: "What does the telescope actually see?",
        a: "The telescope does not see a tiny dot; it sees a brilliant Einstein Ring around the Sun. The brightness of the ring directly encodes the surface brightness of the corresponding patch of the exoplanet."
      }
    ],
    interactiveComponent: "cylinder",
    mediaSrc: "/images/sgl_focal_cylinder_diagram.jpg",
    mediaTitle: "3D SGL Optical Architecture & Focal Tube",
    mediaDesc: "Light from an exo-Earth proxy focused by the Sun's gravity into a 1.34 km image cylinder at 650 AU, sampled by a 16-craft raster.",
    mediaBadge: "3D Mission Diagram",
    stats: [
      { label: "Focal Onset", value: "z₀ ≈ 547.8 AU", desc: "b = R☉, r_g ≈ 2.95 km" },
      { label: "Optical Gain", value: "μ₀ ≈ 1.2×10¹¹", desc: "On-axis, at λ = 1 μm" },
      { label: "Focal Cylinder Size", value: "~1.3 km", desc: "Earth radius at 30 pc, 650 AU" },
      { label: "Telescope Aperture", value: "d = 1 m", desc: "Single-pixel scanner" },
    ],
  },
  {
    id: 3,
    badge: "Optical Physics",
    title: "Telescope Pupil Camera & Coronagraph Optics",
    subtitle: "How off-axis motion creates gravitational arcs and how coronagraph masks isolate exoplanet photons.",
    takeaways: [
      <span>When the telescope is on-axis (<LatexMath math="\rho = 0" />), exoplanet light forms a continuous, circular Einstein Ring around the Sun.</span>,
      <span>As the spacecraft steps off-axis, the ring splits into opposing gravitational arcs with intensity <LatexMath math="K(\rho) \approx \frac{d}{4\rho}" />.</span>,
      <span>Even after the occulter, the residual solar corona outshines the planet by <LatexMath math="Q_{\rm cor}/Q_{\rm exo} = 6.20\times10^{9}/8.01\times10^{4} \simeq 7.74\times10^{4}" /> photons/s, giving <LatexMath math="\mathrm{SNR_C} = 43.16" /> per 1800~s dwell.</span>,
      <span>We checked the discrete aperture-averaged operator against the published deconvolution-noise scaling <LatexMath math="0.891\,D/(d\sqrt{N})" />: agreement is at the <em>percent-to-tens-of-percent</em> level (0.324 vs 0.291 at n = 64; the ~45% gap at n = 128 is stated and attributed in the paper), i.e. partial validation, not machine precision.</span>,
    ],
    speakerNotes: "Here is what the telescope camera actually sees at 650 AU. Light from the exoplanet wraps around the solar limb into an Einstein ring, and a coronagraph occulter blocks the blinding solar disk. Even after that the corona still delivers ~7.7×10⁴ times the planet's photon rate, which is why the noise model is built around coronal shot noise and why the per-dwell SNR is 43 rather than 4300. Our own check of the forward operator reproduces the published deconvolution penalty to within tens of percent — we call that partial validation, and the paper says so.",
    judgeFaq: [
      {
        q: "What is a coronagraph?",
        a: "An optical device that blocks direct sunlight like an artificial solar eclipse, allowing faint light from the exoplanet right next to the Sun to be photographed. It suppresses the bright solar disk; it does not remove the corona, which remains ~7.7×10⁴ times brighter than the planet in photon rate."
      },
      {
        q: "How big is the Einstein ring on the sky?",
        a: "Its radius is D_img/2 ≈ 669 m at 650 AU, i.e. ~1.4 microarcseconds, while the solar disk there is ~2.95 arcsec across. The Sun's angular radius (≈1.48×10⁶ μas) is about a million times the ring radius — that contrast, plus the corona that survives the occulter, is the real difficulty of the observation."
      }
    ],
    interactiveComponent: "einstein",
    mediaSrc: "/videos/einstein_ring_convolution.gif",
    mediaTitle: "SGL Einstein Ring Optical Convolution Video",
    mediaDesc: "Azimuthal folding of planetary surface features into a luminous Einstein ring convolved with the 1/ρ kernel.",
    mediaBadge: "Optical Ray-Trace Video",
    stats: [
      { label: "Kernel Formula", value: <LatexMath math="d / (4\rho)" />, desc: "Aperture-averaged kernel" },
      { label: "Coronagraph Mask", value: "Active", desc: "Occulter; corona still 7.7×10⁴× planet" },
      { label: "Sample SNR_C", value: "43.16", desc: "per 1800 s dwell, d = 1 m" },
      { label: "Wavelength", value: "λ = 1 μm", desc: "single-band model" },
    ],
  },
  {
    id: 4,
    badge: "Mathematical Breakthrough",
    title: "Time-Domain Inversion (TDI): Reconstructing Moving Weather",
    subtitle: "We formulate image recovery as a Generalized Least Squares time-series problem.",
    takeaways: [
      <span>Instead of averaging or ignoring time, we time-tag every photocurrent sample and index it by its exact observation timestamp <LatexMath math="t" />.</span>,
      <span>The forward model <LatexMath math="\mathsf{F}(t)" /> couples the aperture-averaged SGL kernel <LatexMath math="d/4\rho" />, the 16-node Gauss–Legendre exposure smear, rotation, and orbital illumination.</span>,
      <span>Dynamic clouds enter as a structured covariance, block-diagonal over image-plane pixels: <LatexMath math="(\mathsf{C}_p)_{ij} = \sigma_{\rm cl}^2 e^{-|t_i - t_j|/\tau_c} + \delta_{ij}\sigma_i^2" /> with <LatexMath math="\tau_c = 4" /> d.</span>,
      <div className="flex flex-col gap-1 w-full">
        <span>The albedo map is then a single closed-form regularized GLS solve — no iteration, no truth information:</span>
        <div className="py-1.5 px-3 bg-blue-50/70 rounded-lg border border-blue-200/80 overflow-x-auto my-1 shadow-2xs">
          <LatexMath math="\hat{\mathbf{s}} = \arg\min_{\mathbf{s}} \left\| \mathsf{C}^{-1/2}(\mathbf{y} - \mathsf{F}\mathbf{s}) \right\|^2 + \lambda_{\rm eff}\|\mathsf{L}\mathbf{s}\|^2" block />
        </div>
        <span className="text-[11px] text-slate-500">with <LatexMath math="\mathsf{L}" /> the spherical-grid Laplacian and <LatexMath math="\lambda = 3\times10^{-3}" />, a hardcoded constant of the released pipeline that the paper sweeps over six decades rather than claims to be optimal.</span>
      </div>,
    ],
    speakerNotes: "Our contribution is Time-Domain Inversion (TDI). Rather than trying to unblur a static snapshot, we write the whole observation stream as one regularized generalized least-squares problem. Rotation, exposure smear, and orbital illumination go into the forward operator F; the cloud field goes into the covariance C as an Ornstein–Uhlenbeck correlation between revisits of the same raster position. One linear solve gives the albedo map. Note what this is not: it is not a photo of continents — it recovers the persistent surface albedo structure, and we score it against a seeded truth we generated.",
    judgeFaq: [
      {
        q: "What is Generalized Least Squares (GLS)?",
        a: "Standard least squares assumes all noise is independent and identical. GLS weights measurements by their true noise covariance, discounting correlated directions instead of pretending they are clean. Using white-noise GLS on cloudy data is exactly the mistake the paper measures: it drops r from 0.342 to 0.289 at 55% cover."
      },
      {
        q: "Does this require prior knowledge of the continent shapes?",
        a: "No. The inversion is blind to continent shapes; it assumes only that the surface albedo is stationary on the spinning planet while the cloud field decorrelates over ~4 days, plus a smoothness penalty on the spherical grid. The truth maps are seeded synthetic fields, and the reported r is a correlation against that known truth."
      }
    ],
    interactiveComponent: "sandbox",
    mediaSrc: "/videos/tdi_deconvolution_timelapse.gif",
    mediaTitle: "TDI Reconstruction Timelapse Simulation Video",
    mediaDesc: "Illustrative sequence: raw striped raster → exact slot-offset profiling → regularized GLS solve → fidelity vs revisit count. Each frame is one linear solve, not an iterative deconvolution.",
    mediaBadge: "Reconstruction Timelapse",
    stats: [
      { label: "Forward Matrix F(t)", value: "Time-Tagged", desc: "Rotation, smear & SGL kernel" },
      { label: "Noise Covariance", value: "Block-OU", desc: "τ_c = 4 d per pixel" },
      { label: "Regularization", value: "Laplacian", desc: "λ_eff from λ = 3×10⁻³" },
      { label: "Algorithm Type", value: "Closed-Form", desc: "One linear GLS solve" },
    ],
  },
  {
    id: 5,
    badge: "Fleet Architecture",
    title: "16-Craft Raster & Exact Profiling of the Slot Offsets",
    subtitle: "Concurrent sampling turns a disk-integrated weather flicker into a nuisance parameter that can be profiled out.",
    takeaways: [
      <span>The reference campaign is <LatexMath math="N_{\rm sc} = 16" /> spacecraft on a <LatexMath math="64\times64" /> raster with <LatexMath math="20.9" /> m pitch: each dwell samples 16 pixels at once, on adjacent boustrophedon tracks, with transverse separations of ~80–300 m — <em>not</em> a 1.3 km formation.</span>,
      <span>An instantaneous disk-integrated cloud fluctuation perturbs all 16 simultaneous samples coherently, because <LatexMath math="K(\rho) \propto 1/\rho" /> mixes the whole planet into every sample. We therefore model it as per-slot nuisance offsets <LatexMath math="\boldsymbol\alpha" />: <LatexMath math="\mathbf{y} = \mathsf{F}\mathbf{s} + \mathsf{B}\boldsymbol\alpha + \boldsymbol\varepsilon" />.</span>,
      <div className="flex flex-col gap-1 w-full">
        <span>They are removed by exact profile likelihood, not by subtracting a per-slot mean. Since <LatexMath math="\mathsf{C}" /> is block-diagonal over pixels while <LatexMath math="\mathsf{B}" /> couples slots within a pixel, <LatexMath math="\mathsf{H} = \mathsf{B}^{\sf T}\mathsf{C}^{-1}\mathsf{B}" /> is 256 blocks of size <LatexMath math="M_p \times M_p" />, and with the anchor <LatexMath math="\sum_b \alpha_b = 0" /> the profile is a rank-one correction:</span>
        <div className="py-1.5 px-3 bg-blue-50/70 rounded-lg border border-blue-200/80 overflow-x-auto my-1 shadow-2xs">
          <LatexMath math="\mathsf{A} = \mathsf{A}_{\rm free} + \mathbf{q}\mathbf{q}^{\sf T}/S, \qquad \mathbf{b} = \mathbf{b}_{\rm free} + \mathbf{q}\,m/S" block />
        </div>
      </div>,
      <span>Measured gain of profiling against a fit that ignores the offsets: <LatexMath math="\Delta r = +0.054 \pm 0.006" /> (paired, 10/10 seeds) — at the fiducial 55% cover. The four-step ablation isolates it as the <em>profiling</em> term: the OU covariance alone adds nothing on top.</span>,
    ],
    speakerNotes: "The engineering story here is not 'more telescopes = more resolution'. Sixteen craft let sixteen raster positions be sampled simultaneously, and the physics that matters is that a whole-planet cloud brightening shows up in all of them together. An early version of this work treated that as an orthogonal projection that simply subtracted the per-slot mean and kept 93.75% of the information. That was wrong in both mechanism and arithmetic. What the revised paper does is exact profile likelihood over the 256 slot offsets with a sum-to-zero anchor. The audit is blunt: profiling removes no rank at all — the null space is set by the grid and the raster. What it changes is the response along the mean-albedo direction, and the anchor is what preserves it: the unanchored profile attenuates the disk-integrated albedo by a factor of 49.",
    judgeFaq: [
      {
        q: "Why anchor the offsets with Σα = 0?",
        a: "Because without it the disk-integrated albedo is thrown away. The information audit measures the constant-mode gain as 913.7 un-profiled, 18.79 for the free profile (2.06% retained), and 774.1 for the anchored profile (84.72% retained). Anchoring is what 'full TDI' means in this paper."
      },
      {
        q: "How do the 16 craft coordinate?",
        a: "The campaign ledger charges 45 s per dwell — 30 s translation slew, 10 s pointing settling and 5 s inter-spacecraft metrology — and nothing else. The simulation does not model clock jitter or formation keeping, so no claim is made about sub-millisecond timing; that is mission-systems work outside this paper."
      }
    ],
    interactiveComponent: "deflation",
    mediaSrc: "/images/tdi_reconstruction_pipeline.jpg",
    mediaTitle: "TDI Mathematical Pipeline & Operator Architecture",
    mediaDesc: "End-to-end flowchart: time-tagged raster → slot-offset profiling (anchored) → regularized GLS solve → scored surface map.",
    mediaBadge: "Algorithm Pipeline Flowchart",
    stats: [
      { label: "Fleet Size", value: "16 Crafts", desc: "16 pixels per dwell, 80–300 m apart" },
      { label: "Nuisance Treatment", value: <LatexMath math="\mathsf{A} = \mathsf{A}_{\rm free} + \mathbf{q}\mathbf{q}^{\sf T}/S" />, desc: "Anchored profile, 256 blocks" },
      { label: "Slot-Profiling Benefit", value: "+0.054 Δr", desc: "±0.006, 10/10 seeds, f_c ≈ 0.56" },
      { label: "Rank Removed", value: "0", desc: "Nullity 288 before and after" },
    ],
  },
  {
    id: 6,
    badge: "Empirical Discovery",
    title: "Cadence Law: Why Frequent Quick Revisits Beat Long Dwells",
    subtitle: "Two factorial arms that hold either the photons per raster position or the wall clock fixed, and agree to within the error bars.",
    takeaways: [
      "Classic intuition says: stare as long as possible at each pixel to collect photons.",
      "We ran two mutually exclusive ledgers. Arm A holds the integration per raster position constant at M_p·t_s = 28,800 s (8 h) and lets the wall clock grow; arm B holds the wall clock at 89.87 d and lets t_s fall. Total photons per position, not stare time, is what arm A fixes.",
      "Arm A: M_p = 4 (7200 s dwells) gives r = 0.049 ± 0.005; M_p = 32 (900 s) gives 0.497 ± 0.014; M_p = 64 (450 s) gives 0.571 ± 0.010. Every step is unanimous across the six paired seeds, and arm B reproduces the same curve (0.049 → 0.576) under the other ledger.",
      "The mechanism is weather sampling, not conditioning: each quick pass catches a fresh realization of the cloud field, so uncorrelated cloud noise averages down while the stationary surface reinforces. The step gains shrink (+0.124, +0.173, +0.151, +0.075) and N_eff saturates near 12 at M_p = 64.",
    ],
    speakerNotes: "This is the paper's central empirical result. We held the photons per raster position strictly constant and varied the cadence. Four two-hour dwells gave r = 0.049. Spending the same photons on 32 quick 900-second snapshots gave 0.497, and 64 dwells of 450 s gave 0.571. Two things keep us honest about it. First, the arms are separate ledgers — arm A buys its extra revisits with wall-clock time and lands at 93.73 days, outside a 90-day window; arm B stays at 89.87 days by shortening dwells, and reaches the same answer, which is why we believe the trend rather than the bookkeeping. Second, the curve saturates: the increments fall, and the effective number of independent looks is only ~12 at M_p = 64 because the cloud field has a 4-day memory. If the real decorrelation time is longer, M_p > 32 buys almost nothing.",
    judgeFaq: [
      {
        q: "Is there a limit to how fast the spacecraft can revisit?",
        a: "Yes, and it is measured rather than assumed. The 45 s/dwell overhead drives the duty cycle from 0.994 at M_p = 4 to 0.909 at M_p = 64, and arm A's wall clock reaches 93.73 d — beyond the nominal campaign window. On top of that, with τ_cloud = 4 d the effective look count saturates near 12, so extra revisits buy diminishing returns. The tested range stops at 450 s; nothing below it was simulated."
      },
      {
        q: "Does this work when the planet has 75% cloud cover?",
        a: "It degrades, and we report the degradation. In the ten-seed cloud study the profiled estimator gives r = 0.342 at 55% realized cover and r = 0.249 at 71%, with SSIM falling from 0.106 to 0.061 and land–ocean d′ from 0.73 to 0.53. That is a coarse continental-scale detection, not a map of landmasses — the ℓ ≳ 9 band is gone by then."
      }
    ],
    interactiveComponent: "cadence",
    stats: [
      { label: "M_p=4 (7200s)", value: "r = 0.049", desc: "4 dwells × 2 h, 85.73 d wall" },
      { label: "M_p=32 (900s)", value: "r = 0.497", desc: "32 revisits, η = 0.952" },
      { label: "M_p=64 (450s)", value: "r = 0.571", desc: "93.73 d wall (> 90 d)" },
      { label: "Duty Cycle η", value: "90.9%", desc: "45 s overhead at M_p = 64" },
    ],
  },
  {
    id: 7,
    badge: "Flight Mechanics",
    title: "Target Exoplanets: Proxima b, Ross 128 b & Nominal Proxies",
    subtitle: "Focal-line dynamics, image-cylinder sizes and tracking Δv budgets for nearby temperate planets.",
    takeaways: [
      "We evaluated six rows: five confirmed temperate planets around M dwarfs within ~13 light-years, plus τ Ceti e. τ Cet e's planet interpretation has been refuted (Figueira et al. 2025, A&A 700 A174), so it is kept only as an illustrative dynamics row, not as a target.",
      "Proxima Centauri b has the largest image cylinder (D_img = 31.8 km at 650 AU) and a nominal SNR_C = 665.8, but its 11.2-day orbit costs 5.81 km/s of tracking Δv over 90 days.",
      "Ross 128 b (quiet host, β_ecl ≈ 0.5°, D_img = 13.1 km) needs 2.94 km/s; GJ 273 b needs only 1.34 km/s, but its M·sin i = 2.89 M⊕ lies above the Chen & Kipping Terran/Neptunian transition, so the rocky radius used for it is an extrapolation rather than a measurement.",
      "The Δv spread is a factor of 53 across the six rows (0.11–5.81 km/s; 1.34–5.81 km/s among the confirmed five), computed as the time integral of the projected Keplerian transverse acceleration, not the circular estimate.",
    ],
    speakerNotes: "Could we actually fly this? The paper maps the requirements rather than the hardware. As a planet orbits its star, its focal cylinder sweeps across space, so the fleet has to steer to keep up. We integrate |a_perp| over the 90-day window: that is the honest number, and it varies by a factor of 53 across the rows, which is why the v2 presentation of ~10% uncertainties was replaced. I want to be careful about τ Ceti e: it appears here because the v2 target list used it, and the RV signal has since been attributed to stellar activity and classified as a false positive. We keep the row for its dynamics — its 163-day orbit makes the tracking cost trivially small at 0.11 km/s — and we label it as illustrative.",
    judgeFaq: [
      {
        q: "What kind of thrusters can provide 3 km/s Δv?",
        a: "This paper does not size a propulsion system; it produces the Δv requirement. The mission-design discussion covers cruise (deep-perihelion sail, 105–155 km/s) and power (APPLE planar RTG tiles), and explicitly leaves formation keeping and thruster trade studies outside its scope."
      },
      {
        q: "Which planet should be targeted first?",
        a: "The paper explicitly declines to do site selection; it maps requirements. Reading those numbers together: Ross 128 b combines an in-ecliptic focal line (β_ecl ≈ 0.5°, so no plane change) with a quiet host, SNR_C = 581 and 2.94 km/s of tracking. GJ 273 b is cheapest to track at 1.34 km/s, but its M·sin i sits above the Chen & Kipping mass regime transition so its rocky radius is extrapolated. Teegarden c is also in-plane at 1.72 km/s but has the lowest photon rate, SNR_C = 130."
      }
    ],
    interactiveComponent: "targets",
    mediaSrc: "/images/sgl_target_exoplanets.jpg",
    mediaTitle: "Temperate Exoplanet Target Infographic",
    mediaDesc: "Comparative telemetry cards for the five confirmed rows (Proxima Cen b, Ross 128 b, GJ 1061 d, Teegarden c, GJ 273 b) plus the refuted τ Cet e illustrative row. Values from results/targets.json.",
    mediaBadge: "Target Infographic",
    stats: [
      { label: "Nearest Target", value: "Proxima b (4.2 ly)", desc: "D_img = 31.8 km" },
      { label: "Illustrative Row", value: "τ Cet e", desc: "Δv90 = 0.11 km/s; planet refuted" },
      { label: "Lowest-Cost Confirmed", value: "Ross 128 b", desc: "β_ecl ≈ 0.5°, Δv = 2.94 km/s" },
      { label: "Photometric SNR_C", value: "130 – 909", desc: "nominal, 1800 s, 1 m" },
    ],
  },
  {
    id: 8,
    badge: "Mission Roadmap",
    title: "What the Mission Needs, and What This Paper Does Not Establish",
    subtitle: "Characterized ephemerides are a hard requirement; formation keeping and propulsion are outside this study's scope.",
    takeaways: [
      "The fleet is not a 1.3 km formation: 16 craft sample 16 raster positions at once on adjacent tracks, with transverse separations of ~80–300 m inside the 1.34 km image cylinder.",
      "Spin state is not solvable in flight from these data. The whitened χ² is flat in assumed initial phase (relative variation ≤ 10⁻¹¹) and monotone in assumed period, so the rotation period and phase must come from precursor photometry — the paper's own requirement is characterization to ~10⁻⁴.",
      "What this paper delivers is a bounded, reproducible result: at 55% realized cloud cover, r = 0.342 ± 0.008 with SSIM = 0.106 on a 36×72 unknown vector, and a usable harmonic band of ℓ ≲ 9 (~2200 km resolution elements for an Earth-radius planet).",
      "Propellant budgets, thruster selection, coronagraph engineering and formation keeping are not computed here; the mission section covers cruise (sail), power (APPLE tiles) and data volume, and flags the rest as open.",
    ],
    speakerNotes: "To close honestly: the Solar Gravitational Lens is, as far as the published literature shows, the only concept that reaches the photon budget and angular scale needed for multipixel exo-Earth surface mapping. Before this work, rotation and weather were treated as a corruption to be averaged away; we made them part of the model and measured what that buys. What I want to leave you with is the boundary of the claim. We did not solve the spin-state problem — we proved the photometric residuals cannot solve it, so an external ephemeris is mandatory. We did not size a propulsion system or a coronagraph. What we did is build an open pipeline in which every number on these slides traces to an archived, seeded experiment, and report where it stops: continental-scale albedo structure at ℓ ≲ 9, not a photograph of a world.",
    judgeFaq: [
      {
        q: "What are the next steps for this research?",
        a: "The paper names them: a real regularizer-selection criterion (L-curve, discrepancy principle, GCV, or a validated prior over surface models) instead of the hardcoded λ = 3×10⁻³; a wavelength-integrated rather than bolometric signal model; and a full spin-resolved dynamic retrieval, which it explicitly defers. Optical testbeds and coronagraph design belong to the mission-study community, not to this manuscript."
      },
      {
        q: "Can the public and judges inspect the code and paper?",
        a: "Yes. The pipeline is open-source, every figure is regenerated from archived npz results by scripts in src/, seeds are fixed and published, and the revised manuscript PDF is downloadable from this site. Numbers shown in this presentation are read from the same archive rather than retyped."
      }
    ],
    interactiveComponent: "fleet",
    mediaSrc: "/videos/fleet_raster_scan.gif",
    mediaTitle: "16-Spacecraft Raster Scan Simulation Video",
    mediaDesc: "Illustrative concurrent raster scanning of the 1.34 km image cylinder. The archived fiducial campaign is 256 slots × 1845 s per pass over 16 passes: 85.33 d exposure plus 2.00 d in-window overhead = 87.33 d wall clock.",
    mediaBadge: "Fleet Formation Video",
    stats: [
      { label: "Deliverable", value: "r = 0.342", desc: "± 0.008, 55% cover, 10 seeds" },
      { label: "Usable Band", value: "ℓ ≲ 9", desc: "≈ 2200 km elements" },
      { label: "Status", value: "Revise & Resubmit", desc: "TOJA, under review" },
      { label: "Code Status", value: "Open Source", desc: "Seeds fixed, figures reproducible" },
    ],
  },
];

export default function JudgePresentation() {
  const [currentSlideIdx, setCurrentSlideIdx] = useState<number>(0);
  const [showNotes, setShowNotes] = useState<boolean>(false);
  const [showFaq, setShowFaq] = useState<boolean>(false);
  const [mediaToggle, setMediaToggle] = useState<Record<number, "sim" | "media">>({});
  const [isSimFullscreen, setIsSimFullscreen] = useState<boolean>(false);

  // Touch swipe support for mobile
  const [touchStart, setTouchStart] = useState<number | null>(null);
  const [touchEnd, setTouchEnd] = useState<number | null>(null);

  const slide = SLIDES[currentSlideIdx];

  // Reset simulator fullscreen on slide change
  useEffect(() => {
    setIsSimFullscreen(false);
  }, [currentSlideIdx]);

  // Keyboard navigation (Left/Right arrows and Escape for fullscreen)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isSimFullscreen) {
        setIsSimFullscreen(false);
      } else if (e.key === "ArrowRight" || e.key === "PageDown") {
        setCurrentSlideIdx((prev) => Math.min(SLIDES.length - 1, prev + 1));
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        setCurrentSlideIdx((prev) => Math.max(0, prev - 1));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSimFullscreen]);

  const goToPrev = () => setCurrentSlideIdx((prev) => Math.max(0, prev - 1));
  const goToNext = () => setCurrentSlideIdx((prev) => Math.min(SLIDES.length - 1, prev + 1));

  // Touch handlers
  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchEnd(null);
    setTouchStart(e.targetTouches[0].clientX);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    setTouchEnd(e.targetTouches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    const distance = touchStart - touchEnd;
    const minSwipeDistance = 45;
    if (distance > minSwipeDistance) {
      goToNext();
    } else if (distance < -minSwipeDistance) {
      goToPrev();
    }
  };

  return (
    <div 
      className="presentation-container w-full space-y-4"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >
      {/* Top Deck Control Toolbar */}
      <div className="flex items-center justify-between bg-white px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl border border-slate-200 shadow-xs flex-wrap gap-2">
        <div className="flex items-center gap-1.5 sm:gap-2">
          <span className="badge badge-primary font-mono text-[10px] sm:text-xs">
            Slide {slide.id} / {SLIDES.length}
          </span>
          <span className="font-semibold text-slate-800 text-xs sm:text-sm hidden md:inline truncate max-w-[280px]">
            {slide.title}
          </span>
        </div>

        {/* Action Toggles & Navigation */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          <button
            onClick={() => setShowNotes(!showNotes)}
            className={`btn btn-sm ${showNotes ? "btn-primary" : "btn-outline"} text-[11px] sm:text-xs flex items-center gap-1 px-2 sm:px-2.5 py-1`}
            title="Toggle Speaker Notes"
          >
            <MessageSquare size={12} />
            <span className="hidden sm:inline">{showNotes ? "Hide Notes" : "Speaker Notes"}</span>
            <span className="sm:hidden">Notes</span>
          </button>

          <button
            onClick={() => setShowFaq(!showFaq)}
            className={`btn btn-sm ${showFaq ? "btn-accent" : "btn-outline"} text-[11px] sm:text-xs flex items-center gap-1 px-2 sm:px-2.5 py-1`}
            title="Toggle Judge FAQ"
          >
            <HelpCircle size={12} />
            <span className="hidden sm:inline">{showFaq ? "Hide Q&A" : "Judge Q&A"}</span>
            <span className="sm:hidden">Q&A</span>
          </button>

          <div className="h-4 w-px bg-slate-200 mx-0.5" />

          <button
            onClick={goToPrev}
            disabled={currentSlideIdx === 0}
            className="btn btn-sm btn-outline disabled:opacity-30 flex items-center gap-0.5 text-xs px-2 py-1"
            title="Previous Slide"
          >
            <ChevronLeft size={14} />
            <span className="hidden sm:inline">Prev</span>
          </button>

          <button
            onClick={goToNext}
            disabled={currentSlideIdx === SLIDES.length - 1}
            className="btn btn-sm btn-primary disabled:opacity-30 flex items-center gap-0.5 text-xs px-2.5 py-1"
            title="Next Slide"
          >
            <span className="hidden sm:inline">Next</span>
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Main Presentation Board (Slide Canvas) */}
      <div className="bg-white rounded-2xl border border-slate-200 p-4 sm:p-6 md:p-8 shadow-xs space-y-4 sm:space-y-6 min-h-[460px] md:min-h-[560px] flex flex-col justify-between">
        {/* Slide Header */}
        <div className="space-y-1.5 border-b border-slate-100 pb-3 sm:pb-4">
          <div className="flex items-center gap-2">
            <span className="badge badge-accent uppercase tracking-wider font-bold text-[9px] sm:text-[10px]">
              {slide.badge}
            </span>
            <span className="text-[10px] sm:text-xs text-slate-400 font-mono hidden sm:inline">
              Presentation Board • SGL Time-Domain Inversion
            </span>
          </div>
          <h2 className="text-xl sm:text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight leading-snug">
            {slide.title}
          </h2>
          <p className="text-xs sm:text-sm md:text-base text-slate-600 font-medium">
            {slide.subtitle}
          </p>
        </div>

        {/* Slide Content Area */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 sm:gap-6 my-auto items-start">
          {/* Key Bullet Takeaways */}
          <div className={slide.interactiveComponent ? "lg:col-span-4 xl:col-span-4 space-y-2 sm:space-y-3" : "lg:col-span-8 space-y-2 sm:space-y-3"}>
            <h4 className="text-[10px] sm:text-xs font-bold uppercase tracking-wider text-slate-500 mb-1">
              Key Board Takeaways:
            </h4>
            <div className="space-y-2">
              {slide.takeaways.map((point, idx) => (
                <div key={idx} className="flex items-start gap-2 p-2 sm:p-2.5 bg-slate-50 rounded-lg border border-slate-150 text-xs sm:text-sm text-slate-700 leading-relaxed">
                  <CheckCircle2 size={15} className="text-blue-600 shrink-0 mt-0.5" />
                  <span>{point}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Interactive Simulation / Right Card */}
          <div className={slide.interactiveComponent ? "lg:col-span-8 xl:col-span-8" : "lg:col-span-4"}>
            {/* View Switcher Bar if slide has both simulator and media */}
            {slide.mediaSrc && slide.interactiveComponent !== "planet-video" && (
              <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-100 flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Display Mode:</span>
                  <div className="inline-flex bg-slate-100 p-0.5 rounded-lg border border-slate-200">
                    <button
                      onClick={() => setMediaToggle(prev => ({ ...prev, [slide.id]: "sim" }))}
                      className={`px-2.5 py-1 text-xs font-bold rounded-md flex items-center gap-1.5 transition-all ${
                        (mediaToggle[slide.id] || "sim") === "sim"
                          ? "bg-white text-blue-700 shadow-xs"
                          : "text-slate-500 hover:text-slate-800"
                      }`}
                    >
                      <Zap size={12} className={(mediaToggle[slide.id] || "sim") === "sim" ? "text-amber-500" : "text-slate-400"} />
                      <span>Interactive Sim</span>
                    </button>
                    <button
                      onClick={() => setMediaToggle(prev => ({ ...prev, [slide.id]: "media" }))}
                      className={`px-2.5 py-1 text-xs font-bold rounded-md flex items-center gap-1.5 transition-all ${
                        mediaToggle[slide.id] === "media"
                          ? "bg-blue-600 text-white shadow-xs"
                          : "text-slate-500 hover:text-slate-800"
                      }`}
                    >
                      <Video size={12} className={mediaToggle[slide.id] === "media" ? "text-sky-200" : "text-slate-400"} />
                      <span>{slide.mediaBadge || "1080p Master Video"}</span>
                    </button>
                  </div>
                </div>

                {/* Fullscreen Sim button for interactive mode */}
                {(mediaToggle[slide.id] || "sim") === "sim" && (
                  <button
                    type="button"
                    onClick={() => setIsSimFullscreen(true)}
                    className="text-xs text-slate-600 hover:text-slate-900 font-semibold flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors shadow-2xs"
                    title="View Simulation in Fullscreen"
                  >
                    <Maximize2 size={12} className="text-blue-600" />
                    <span>Fullscreen Sim</span>
                  </button>
                )}
              </div>
            )}

            {/* Fullscreen Sim button for slides without media toggle */}
            {!slide.mediaSrc && slide.interactiveComponent && slide.interactiveComponent !== "planet-video" && (
              <div className="flex items-center justify-end pb-2 mb-2 border-b border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsSimFullscreen(true)}
                  className="text-xs text-slate-600 hover:text-slate-900 font-semibold flex items-center gap-1 px-2.5 py-1 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors shadow-2xs"
                  title="View Simulation in Fullscreen"
                >
                  <Maximize2 size={12} className="text-blue-600" />
                  <span>Fullscreen Sim</span>
                </button>
              </div>
            )}

            {/* Display Planet Rotation Live Player for Slide 1 */}
            {slide.interactiveComponent === "planet-video" && (
              <PlanetRotationPlayer />
            )}

            {/* Display Media Mode for other slides with 1080p Zoom Viewer */}
            {slide.interactiveComponent !== "planet-video" && slide.mediaSrc && mediaToggle[slide.id] === "media" && (
              <MediaZoomViewer
                src={slide.mediaSrc}
                title={slide.mediaTitle || slide.title}
                badge={slide.mediaBadge || "1080p Full HD"}
                desc={slide.mediaDesc}
                downloadName={slide.mediaSrc.split("/").pop()}
              />
            )}

            {/* Display Interactive Simulator Mode (Supports Fullscreen) */}
            {slide.interactiveComponent !== "planet-video" && (!slide.mediaSrc || mediaToggle[slide.id] !== "media") && (
              <div className={isSimFullscreen ? "fixed inset-0 z-[99999] w-screen h-screen bg-slate-900/98 backdrop-blur-2xl p-4 sm:p-6 overflow-y-auto flex flex-col animate-fadeIn" : "w-full"}>
                {isSimFullscreen && (
                  <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-700 shrink-0 max-w-7xl mx-auto w-full">
                    <div className="flex items-center gap-2">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                      <h3 className="text-sm sm:text-base font-bold text-white font-mono">
                        {slide.title} • Interactive Simulation Lab
                      </h3>
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsSimFullscreen(false)}
                      className="btn btn-sm bg-slate-800 hover:bg-red-900 text-white border border-slate-700 px-3 py-1.5 flex items-center gap-1.5 rounded-lg shadow-xs transition-colors"
                      title="Exit Fullscreen (Esc)"
                    >
                      <Minimize2 size={13} />
                      <span>Exit Fullscreen (Esc)</span>
                    </button>
                  </div>
                )}
                <div className={isSimFullscreen ? "w-full max-w-7xl mx-auto my-auto" : "w-full"}>
                  {slide.interactiveComponent === "cylinder" && <SglCylinderSimulator />}
                  {slide.interactiveComponent === "einstein" && <EinsteinRingSimulator />}
                  {slide.interactiveComponent === "sandbox" && <ImageReconstructionSandbox />}
                  {slide.interactiveComponent === "cadence" && <CadenceExplorer />}
                  {slide.interactiveComponent === "deflation" && <CloudDeflationDemo />}
                  {slide.interactiveComponent === "targets" && <TargetCatalogExplorer />}
                  {slide.interactiveComponent === "fleet" && <FleetFormationSimulator />}
                </div>
              </div>
            )}

            {!slide.interactiveComponent && (
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                <h4 className="text-[10px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                  Mission Executive Metrics
                </h4>
                <div className="grid grid-cols-2 gap-2.5">
                  {slide.stats.map((s, idx) => (
                    <div key={idx} className="bg-white p-2.5 sm:p-3 rounded-lg border border-slate-200">
                      <div className="text-[10px] text-slate-400 font-medium truncate">{s.label}</div>
                      <div className="text-base sm:text-lg font-bold font-mono text-slate-900 mt-0.5">{s.value}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5 truncate">{s.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Slide Footer Stat Strip */}
        <div className="pt-3 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
          {slide.stats.map((st, i) => (
            <div key={i} className="text-xs border-l-2 border-blue-500 pl-2 sm:pl-2.5 py-0.5">
              <div className="text-slate-400 text-[9px] sm:text-[10px] uppercase font-bold truncate">{st.label}</div>
              <div className="font-mono font-bold text-slate-800 text-xs sm:text-sm truncate">{st.value}</div>
              <div className="text-slate-500 text-[9px] sm:text-[10px] truncate">{st.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Speaker Notes Drawer (Toggled) */}
      {showNotes && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-3.5 sm:p-4 shadow-xs text-xs space-y-1.5 animate-fadeIn">
          <div className="flex items-center gap-1.5 font-bold text-amber-900">
            <MessageSquare size={13} className="text-amber-600" />
            <span>Spoken Script / Speaker Notes for Presenter:</span>
          </div>
          <p className="text-amber-800 text-xs sm:text-sm leading-relaxed italic">
            "{slide.speakerNotes}"
          </p>
        </div>
      )}

      {/* Judge Q&A Cheat Sheet (Toggled) */}
      {showFaq && (
        <div className="bg-blue-50/80 border border-blue-200 rounded-xl p-3.5 sm:p-4 shadow-xs text-xs space-y-2.5 animate-fadeIn">
          <div className="flex items-center gap-1.5 font-bold text-blue-900">
            <HelpCircle size={13} className="text-blue-600" />
            <span>Anticipated Judge Questions & Technical Answers:</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            {slide.judgeFaq.map((faq, idx) => (
              <div key={idx} className="bg-white p-2.5 sm:p-3 rounded-lg border border-blue-150 space-y-1">
                <div className="font-bold text-slate-800 text-xs flex items-start gap-1">
                  <span className="text-blue-600">Q:</span>
                  <span>{faq.q}</span>
                </div>
                <div className="text-slate-600 text-[11px] sm:text-xs leading-relaxed pl-3 border-l border-slate-200">
                  {faq.a}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slide Thumbnails & Direct Navigation Bar */}
      <div className="flex items-center justify-center gap-1 sm:gap-1.5 pt-1 sm:pt-2">
        {SLIDES.map((s, idx) => (
          <button
            key={s.id}
            onClick={() => setCurrentSlideIdx(idx)}
            className={`h-2 rounded-full transition-all ${
              currentSlideIdx === idx
                ? "w-6 sm:w-8 bg-blue-600"
                : "w-2 bg-slate-300 hover:bg-slate-400"
            }`}
            title={`Go to slide ${s.id}: ${s.title}`}
          />
        ))}
      </div>
    </div>
  );
}
