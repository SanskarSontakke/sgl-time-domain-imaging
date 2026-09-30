"use client";

import React, { useState } from "react";
import { 
  BookOpen, FileText, CheckCircle2, Download, ExternalLink, 
  Layers, Code, Cpu, Calculator, HelpCircle, ArrowUpRight, Copy, Check, ShieldCheck, ChevronDown, Sparkles, Eye, Radio, Zap, Sliders, Compass
} from "lucide-react";
import LatexMath from "./LatexMath";
import FigureGallery from "./FigureGallery";
import CodeViewer from "./CodeViewer";
import CadenceExplorer from "./simulators/CadenceExplorer";
import CloudDeflationDemo from "./simulators/CloudDeflationDemo";
import TargetCatalogExplorer from "./simulators/TargetCatalogExplorer";
import SpinLikelihoodMap from "./simulators/SpinLikelihoodMap";
import SglCylinderSimulator from "./simulators/SglCylinderSimulator";
import ImageReconstructionSandbox from "./simulators/ImageReconstructionSandbox";
import EinsteinRingSimulator from "./simulators/EinsteinRingSimulator";
import FleetFormationSimulator from "./simulators/FleetFormationSimulator";
import DemonstrationMediaCenter from "./DemonstrationMediaCenter";

export default function TechnicalDocumentation() {
  const [activeSection, setActiveSection] = useState<string>("overview");
  const [mobileTocOpen, setMobileTocOpen] = useState<boolean>(false);
  const [bibtexCopied, setBibtexCopied] = useState<boolean>(false);
  const [activeSimTab, setActiveSimTab] = useState<"sandbox" | "einstein" | "fleet" | "cylinder" | "cadence" | "deflation" | "spin">("sandbox");

  const bibtex = `@article{sgl_tdi_2026,
  title = {Time-Domain Imaging of a Rotating, Cloudy Exo-Earth with the Solar Gravitational Lens},
  author = {Sontakke, Sanskar and Collaborators},
  journal = {The Astrophysical Journal (ApJ)},
  year = {2026},
  note = {Revised Manuscript Under Review}
}`;

  const copyBibtex = () => {
    navigator.clipboard.writeText(bibtex);
    setBibtexCopied(true);
    setTimeout(() => setBibtexCopied(false), 2000);
  };

  const navItems = [
    { id: "overview", label: "1. Executive Overview & Abstract" },
    { id: "optics", label: "2. SGL Optical Physics & Benchmarks" },
    { id: "forward_model", label: "3. Time-Domain Forward Model" },
    { id: "inversion", label: "4. GLS Inversion & Slot Profiling" },
    { id: "cadence", label: "5. Factorial Cadence Ablations" },
    { id: "robustness", label: "6. Spin Ephemeris & Robustness" },
    { id: "targets", label: "7. Exoplanet Target Catalog" },
    { id: "media", label: "8. Simulation Videos & Media Showcase" },
    { id: "interactive", label: "9. Interactive Simulation Suite" },
    { id: "figures", label: "10. Publication Figures Gallery" },
    { id: "code", label: "11. Source Code & Reproducibility" },
    { id: "publications", label: "12. Manuscripts & References" },
  ];

  return (
    <div className="w-full space-y-6">
      {/* Mobile Table of Contents Accordion (Visible on Mobile/Tablet) */}
      <div className="lg:hidden bg-white p-3 sm:p-4 rounded-xl border border-slate-200 shadow-xs">
        <button
          onClick={() => setMobileTocOpen(!mobileTocOpen)}
          className="w-full flex items-center justify-between font-bold text-xs sm:text-sm text-slate-800"
        >
          <span className="flex items-center gap-1.5 text-blue-700">
            <BookOpen size={16} className="text-blue-600" />
            <span>Table of Contents: {navItems.find((n) => n.id === activeSection)?.label.split(". ")[1] || "Select Chapter"}</span>
          </span>
          <ChevronDown size={16} className={`text-slate-500 transform transition-transform ${mobileTocOpen ? "rotate-180" : ""}`} />
        </button>

        {mobileTocOpen && (
          <div className="pt-2 mt-2 border-t border-slate-100 space-y-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setActiveSection(item.id);
                  setMobileTocOpen(false);
                  document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth" });
                }}
                className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs transition-all ${
                  activeSection === item.id
                    ? "bg-blue-50 text-blue-700 font-bold"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8 items-start">
        {/* Sticky Table of Contents Sidebar (Desktop only) */}
        <div className="hidden lg:block lg:col-span-3 sticky top-20 bg-white rounded-xl border border-slate-200 p-4 shadow-xs space-y-3">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <BookOpen size={16} className="text-blue-600" />
            <h3 className="font-bold text-slate-800 text-sm">Table of Contents</h3>
          </div>
          <nav className="space-y-1 text-xs">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setActiveSection(item.id);
                  document.getElementById(item.id)?.scrollIntoView({ behavior: "smooth" });
                }}
                className={`w-full text-left px-2.5 py-1.5 rounded-lg transition-all ${
                  activeSection === item.id
                    ? "bg-blue-50 text-blue-700 font-bold border-l-2 border-blue-600"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>

          {/* Paper Quick Actions */}
          <div className="pt-3 border-t border-slate-100 space-y-2">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Official Documents
            </div>
            <a
              href="/docs/sgl_time_domain_imaging.pdf"
              download
              className="w-full btn btn-sm btn-primary text-xs flex items-center justify-between"
            >
              <span>Download Paper PDF</span>
              <Download size={13} />
            </a>
            <a
              href="/docs/response_to_editor.pdf"
              download
              className="w-full btn btn-sm btn-outline text-xs flex items-center justify-between"
            >
              <span>Response to Editor</span>
              <Download size={13} />
            </a>
          </div>
        </div>

        {/* Main Documentation Body */}
        <div className="lg:col-span-9 space-y-8 sm:space-y-12">
          {/* Section 1: Overview & Abstract */}
          <section id="overview" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 1</span>
              <h2 className="text-xl sm:text-2xl md:text-3xl font-bold text-slate-900">
                Executive Overview & Scientific Contribution
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Time-Domain Imaging of a Rotating, Cloudy Exo-Earth with the Solar Gravitational Lens
              </p>
            </div>

            {/* Abstract Box */}
            <div className="p-3.5 sm:p-5 bg-slate-50 border border-slate-200 rounded-xl space-y-2.5">
              <h3 className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-slate-500">
                Official Paper Abstract
              </h3>
              <p className="text-xs sm:text-sm text-slate-700 leading-relaxed italic">
                "The solar gravitational lens (SGL) can, in principle, deliver multipixel images of terrestrial exoplanets from heliocentric distances z ≃ 650–900 AU. In practice the planet rotates and its cloud cover evolves while a spacecraft raster-scans the kilometer-scale image cylinder one “pixel” at a time, so the measurements are temporally aliased; recent studies identify this dynamic inversion problem as a leading unsolved challenge for the concept. We present an open, end-to-end simulation framework that reproduces the published SGL photometric benchmarks (the aperture-averaged d/4ρ kernel; per-sample SNR_C = 43.16 for 1800 s dwells on an exo-Earth at 30 pc from 650 AU; the 0.891 D/(d√N) deconvolution penalty) and then treats rotation, orbital illumination, and stochastic, advecting clouds explicitly. We formulate image recovery as a regularized generalized least-squares inversion of the time-tagged sample stream (time-domain inversion, TDI, distinguished here from detector-level time-delay integration), in which rotation and illumination are modeled directly by the forward operator and cloud variability enters statistically. For a rotating, cloud-free planet observed under known spin geometry, TDI recovers the surface albedo map with Pearson r = 0.9786 ± 0.0002 (SSIM = 0.848 ± 0.001) over 10 paired seeds; clouds, not coronal photon noise, dominate the error budget, collapsing fidelity to r = 0.249 ± 0.010 at 71% realized cover. Replacing 4 long dwells with 64 short revisits improves r from 0.049 to 0.571 at fixed photons, and exact anchored profiling of the per-dwell-slot cloud nuisance lifts r by +0.054 ± 0.006 over a fit that ignores it. The spin-ephemeris requirement is measured rather than asserted, and the whitened χ² is exactly invariant to assumed initial phase — so the spin state is observable through image quality but not recoverable from photometric residuals."
              </p>
            </div>

            {/* Plain English Summary for Judges */}
            <div className="p-3.5 sm:p-5 bg-amber-50/70 border border-amber-200 rounded-xl space-y-2">
              <h3 className="text-[11px] sm:text-xs font-bold uppercase tracking-wider text-amber-900 flex items-center gap-1.5">
                <HelpCircle size={14} className="text-amber-600" />
                <span>Plain English Summary for Non-Astrophysics Judges</span>
              </h3>
              <p className="text-xs sm:text-sm text-amber-800 leading-relaxed">
                If you try to photograph a moving car in heavy rain using a single camera sensor, exposing it one pixel at a time over two weeks, you get an unrecognizable smear. That is what happens when a telescope maps an exoplanet through the Solar Gravitational Lens: the planet spins every 24 hours, clouds roll across it on day-long timescales, and a spacecraft can only sample one image-plane position at a time. Our framework, <strong>Time-Domain Inversion (TDI)</strong>, keeps every measurement's timestamp instead of averaging them, models rotation and illumination inside the forward operator, and treats weather as a correlated noise term rather than a corruption. It works — but at continental scale: at realistic cloud cover the recovered map has correlation r ≈ 0.34 with the truth and usable detail down to roughly 2200 km resolution elements, not coastlines you could trace.
              </p>
            </div>

            {/* Summary Comparison Table (Mobile-friendly horizontal scroll) */}
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-xs min-w-[500px]">
                <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                  <tr>
                    <th className="p-2.5 sm:p-3">Imaging Methodology</th>
                    <th className="p-2.5 sm:p-3">Assumed Planet State</th>
                    <th className="p-2.5 sm:p-3">Cloud Handling</th>
                    <th className="p-2.5 sm:p-3">Fidelity (Pearson r)</th>
                    <th className="p-2.5 sm:p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  <tr className="hover:bg-slate-50">
                    <td className="p-2.5 sm:p-3 font-semibold text-slate-800">Classical Static Deconvolution</td>
                    <td className="p-2.5 sm:p-3 text-slate-600">Static, non-rotating</td>
                    <td className="p-2.5 sm:p-3 text-rose-600">Ignored / zero clouds</td>
                    <td className="p-2.5 sm:p-3 font-mono text-slate-400">N/A (Fails on real data)</td>
                    <td className="p-2.5 sm:p-3"><span className="badge badge-error text-[9px]">Unphysical</span></td>
                  </tr>
                  <tr className="hover:bg-slate-50">
                    <td className="p-2.5 sm:p-3 font-semibold text-slate-800">Phase-Binned Coaddition</td>
                    <td className="p-2.5 sm:p-3 text-slate-600">Rotates (16 phase bins)</td>
                    <td className="p-2.5 sm:p-3 text-amber-600">Averaged within each bin</td>
                    <td className="p-2.5 sm:p-3 font-mono text-slate-600">r = 0.318 ± 0.016</td>
                    <td className="p-2.5 sm:p-3"><span className="badge badge-accent text-[9px]">Best SSIM at this cover</span></td>
                  </tr>
                  <tr className="hover:bg-slate-50 bg-blue-50/50">
                    <td className="p-2.5 sm:p-3 font-semibold text-blue-900">Our Time-Domain Inversion (TDI)</td>
                    <td className="p-2.5 sm:p-3 text-blue-900">Rotation + orbital illumination (zero obliquity)</td>
                    <td className="p-2.5 sm:p-3 text-emerald-700 font-medium">OU covariance + anchored slot profiling</td>
                    <td className="p-2.5 sm:p-3 font-mono font-bold text-emerald-700">r = 0.342 ± 0.008</td>
                    <td className="p-2.5 sm:p-3"><span className="badge badge-success text-[9px]">Best r above ~40% cover</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          {/* Section 2: SGL Optical Physics & Benchmarks */}
          <section id="optics" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 2</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                SGL Optical Physics & Benchmark Validations
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Einstein ring formation, the aperture-averaged kernel, and how closely our discrete operator matches the published estimates.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-6 items-start">
              <div className="space-y-3 text-xs sm:text-sm text-slate-700 leading-relaxed">
                <p>
                  Under General Relativity, the gravitational potential of the Sun bends passing starlight by an angle:
                </p>
                <div className="p-2.5 sm:p-3 bg-slate-50 border border-slate-200 rounded-lg font-mono text-xs overflow-x-auto">
                  <LatexMath math="\alpha(b) = \frac{4 G M_\odot}{c^2 b} = \frac{2 r_g}{b}" block />
                </div>
                <p>
                  Rays passing at the solar radius <LatexMath math="b = R_\odot" /> intersect the optical axis at the focal line beginning at:
                </p>
                <div className="p-2.5 sm:p-3 bg-slate-50 border border-slate-200 rounded-lg font-mono text-xs overflow-x-auto">
                  <LatexMath math="z_0 = \frac{b^2}{2 r_g} \simeq 547.8 \text{ AU} \quad (b \simeq R_\odot,\; r_g \simeq 2.95 \text{ km})" block />
                </div>
                <p>
                  At a mission distance of <LatexMath math="z = 650\text{ AU}" />, an Earth-sized exoplanet (<LatexMath math="R_p = 6,371\text{ km}" />) at distance <LatexMath math="d_L = 30\text{ pc}" /> projects a focal image cylinder of diameter:
                </p>
                <div className="p-2.5 sm:p-3 bg-slate-50 border border-slate-200 rounded-lg font-mono text-xs overflow-x-auto">
                  <LatexMath math="D_{\rm img} = 2 R_p \frac{z}{d_L} \approx 1,343 \text{ meters}" block />
                </div>
              </div>

              {/* Benchmark Validation Verification Card */}
              <div className="bg-slate-50 p-3.5 sm:p-4 rounded-xl border border-slate-200 space-y-2.5 sm:space-y-3">
                <div className="flex items-center gap-2">
                  <CheckCircle2 size={16} className="text-emerald-600" />
                  <h4 className="font-bold text-slate-800 text-xs uppercase tracking-wider">
                    What Matches, and What Only Approximates
                  </h4>
                </div>
                <p className="text-xs text-slate-600 leading-relaxed">
                  The paper adopts the published SGL photometric quantities and checks its discrete operator against them. Agreement is close in two cases and approximate in the third:
                </p>
                <div className="space-y-2 text-xs">
                  <div className="bg-white p-2.5 rounded border border-slate-200 flex justify-between items-center">
                    <span className="text-slate-600">Aperture-averaged kernel tail (adopted):</span>
                    <span className="font-mono font-bold text-slate-900">
                      <LatexMath math="K(\rho) \simeq d / (4\rho)" />
                    </span>
                  </div>
                  <div className="bg-white p-2.5 rounded border border-slate-200 flex justify-between items-center">
                    <span className="text-slate-600">Fiducial rates of Turyshev &amp; Toth (2022a), adopted as the normalization — not recomputed here:</span>
                    <span className="font-mono font-bold text-emerald-600">
                      <LatexMath math="\mathrm{SNR_C} = 43.16" /> / 1800 s
                    </span>
                  </div>
                  <div className="bg-white p-2.5 rounded border border-slate-200 flex justify-between items-center">
                    <span className="font-mono font-bold text-slate-900">
                      <LatexMath math="0.891 \frac{D}{d \sqrt{N}}" />
                    </span>
                    <span className="text-slate-600 text-left">
                      Measured vs. analytic: 0.324 / 0.291 at n = 64; 0.106 / 0.073 at n = 128
                    </span>
                  </div>
                </div>
                <p className="text-[11px] text-slate-500 leading-snug">
                  That third row is the paper's only operator validation, and it is a partial one:
                  the discrete operator follows the analytic scaling but deviates by ~11% at n = 64
                  and ~45% at n = 128, which Section 2.3 attributes to pixel-binning of the central
                  1/ρ singularity and finite-domain boundary effects.
                </p>
              </div>
            </div>

            {/* Embedded Einstein Ring Simulator */}
            <div className="pt-3">
              <EinsteinRingSimulator />
            </div>
          </section>

          {/* Section 3: Time-Domain Forward Model */}
          <section id="forward_model" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 3</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                Time-Domain Forward Model & Stochastic Weather
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Coupling diurnal rotation, orbital phase lighting, and advecting Ornstein-Uhlenbeck cloud processes into a unified operator.
              </p>
            </div>

            <div className="space-y-3 sm:space-y-4 text-xs sm:text-sm text-slate-700 leading-relaxed">
              <p>
                At any timestamp <LatexMath math="t" />, a spacecraft located at image-plane coordinate <LatexMath math="\mathbf{x}_k(t)" /> integrates photons over dwell duration <LatexMath math="t_s" />. The observed flux <LatexMath math="y_k(t)" /> is given by the linear forward model:
              </p>
              <div className="p-3 sm:p-4 bg-slate-50 border border-slate-200 rounded-lg font-mono text-xs overflow-x-auto text-center">
                <LatexMath math="\mathbf{y} = \mathbf{F}\mathbf{m} + \mathbf{n}_{\rm cloud} + \mathbf{n}_{\rm photon}" block />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4 pt-1 sm:pt-2">
                <div className="bg-white p-3 rounded-lg border border-slate-200 space-y-1">
                  <div className="font-bold text-slate-800 text-xs">Diurnal Planetary Spin</div>
                  <p className="text-xs text-slate-500 leading-snug">
                    Coordinates rotate via Rodrigues formula around spin pole <LatexMath math="\hat{\mathbf{\omega}}" /> with period <LatexMath math="P_{\rm rot} = 24.0\text{ hr}" />.
                  </p>
                </div>

                <div className="bg-white p-3 rounded-lg border border-slate-200 space-y-1">
                  <div className="font-bold text-slate-800 text-xs">Orbital Illumination</div>
                  <p className="text-xs text-slate-500 leading-snug">
                    Lambertian phase angle <LatexMath math="\Phi(t) = \max(0, \cos\theta_{\rm inc})" /> casts dynamic day/night shadows across pixels.
                  </p>
                </div>

                <div className="bg-white p-3 rounded-lg border border-slate-200 space-y-1">
                  <div className="font-bold text-slate-800 text-xs">Advecting Weather</div>
                  <p className="text-xs text-slate-500 leading-snug">
                    Spatio-temporal Ornstein-Uhlenbeck process with correlation length <LatexMath math="\ell_c = 12^\circ" />, advection <LatexMath math="6^\circ\text{/day}" /> and decorrelation time <LatexMath math="\tau_c = 4\text{ d}" />; all three are swept in the robustness suite.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Section 4: Inversion & Slot Deflation */}
          <section id="inversion" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 4</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                Regularized GLS Inversion &amp; Slot-Offset Profiling
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Closed-form generalized least-squares estimator with exact profiling of the per-dwell-slot nuisance offsets.
              </p>
            </div>

            <div className="space-y-3 sm:space-y-4 text-xs sm:text-sm text-slate-700 leading-relaxed">
              <p>
                We invert the full observation stream directly for the stationary surface albedo map <LatexMath math="\hat{\mathbf{s}}" /> as one regularized Generalized Least Squares solve:
              </p>
              <div className="p-3 sm:p-4 bg-slate-50 border border-slate-200 rounded-lg font-mono text-xs overflow-x-auto text-center">
                <LatexMath math="\hat{\mathbf{s}} = \arg\min_{\mathbf{s}} \left\| \mathsf{C}^{-1/2}(\mathbf{y} - \mathsf{F}\mathbf{s}) \right\|^2 + \lambda_{\rm eff}\|\mathsf{L}\mathbf{s}\|^2" block />
              </div>

              <p>
                <LatexMath math="\mathsf{C}" /> is block-diagonal over image-plane pixels, with the <LatexMath math="M_p" /> revisits of a pixel coupled by the OU cloud covariance, <LatexMath math="(\mathsf{C}_p)_{ij} = \sigma_{\rm cl}^2 e^{-|t_i - t_j|/\tau_c} + \delta_{ij}\sigma_i^2" />; <LatexMath math="\mathsf{L}" /> is the spherical-grid Laplacian and <LatexMath math="\lambda = 3\times10^{-3}" /> is a fixed pipeline constant (not a fitted or claimed-optimal value).
              </p>

              <div className="p-3 sm:p-4 bg-emerald-50 border border-emerald-200 rounded-xl space-y-2">
                <div className="font-bold text-emerald-900 flex items-center gap-1.5 text-xs uppercase tracking-wider">
                  <ShieldCheck size={16} className="text-emerald-600" />
                  <span>Exact Profiling of the Simultaneous-Sample Offsets</span>
                </div>
                <p className="text-xs text-emerald-800 leading-relaxed">
                  Because <LatexMath math="K(\rho) \propto 1/\rho" />, a disk-integrated cloud fluctuation perturbs all <LatexMath math="N_{\rm sc} = 16" /> simultaneous samples coherently, so we model it as per-slot nuisance offsets: <LatexMath math="\mathbf{y} = \mathsf{F}\mathbf{s} + \mathsf{B}\boldsymbol\alpha + \boldsymbol\varepsilon" />. Profiling them out is <em>not</em> a per-slot mean subtraction: <LatexMath math="\mathsf{H} = \mathsf{B}^{\sf T}\mathsf{C}^{-1}\mathsf{B}" /> is block-diagonal with 256 blocks of size <LatexMath math="M_p \times M_p" />, and under the anchor <LatexMath math="\sum_b \alpha_b = 0" /> the profile reduces to a rank-one correction:
                </p>
                <div className="p-2 bg-white rounded border border-emerald-200 font-mono text-xs text-center overflow-x-auto">
                  <LatexMath math="\mathsf{A} = \mathsf{A}_{\rm free} + \mathbf{q}\mathbf{q}^{\sf T}/S, \qquad \mathbf{b} = \mathbf{b}_{\rm free} + \mathbf{q}\,m/S" block />
                </div>
                <p className="text-xs text-emerald-800 leading-relaxed">
                  Against a fit that ignores the offsets this is a paired gain of <LatexMath math="\Delta r = +0.054 \pm 0.006" /> (10/10 seeds, at 55% cover). The information audit adds two caveats worth stating: profiling removes no rank at all (nullity 288 before and after), and without the anchor the disk-integrated albedo is attenuated by a factor of 49.
                </p>
              </div>

              {/* Embedded Image Reconstruction Sandbox */}
              <div className="pt-3">
                <ImageReconstructionSandbox />
              </div>
            </div>
          </section>

          {/* Section 5: Cadence Ablation */}
          <section id="cadence" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 5</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                Factorial Cadence Mechanism Ablation
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Proving causality: frequent revisits beat long single dwells by averaging independent weather draws.
              </p>
            </div>

            <div className="space-y-4">
              <p className="text-xs sm:text-sm text-slate-700 leading-relaxed">
                We evaluated five cadence configurations (resource arm A) holding the photon budget per raster position strictly constant at 8 hours (<LatexMath math="M_p\,t_s = 28{,}800\ \rm s" />) while the wall clock grows from 85.7 to 93.7 days, at nominal <LatexMath math="f_c = 0.55" /> on 6 paired seeds:
              </p>

              {/* Cadence Table */}
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="w-full text-left text-xs min-w-[540px]">
                  <thead className="bg-slate-100 text-slate-700 font-semibold border-b border-slate-200">
                    <tr>
                      <th className="p-2.5 sm:p-3">Configuration</th>
                      <th className="p-2.5 sm:p-3">Dwell Time (<LatexMath math="t_s" />)</th>
                      <th className="p-2.5 sm:p-3">Revisits (<LatexMath math="M_p" />)</th>
                      <th className="p-2.5 sm:p-3">Duty Cycle (<LatexMath math="\eta" />)</th>
                      <th className="p-2.5 sm:p-3">Fidelity (<LatexMath math="r" />)</th>
                      <th className="p-2.5 sm:p-3">White-Noise GLS (<LatexMath math="r" />)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    <tr className="hover:bg-slate-50">
                      <td className="p-2.5 sm:p-3 font-semibold text-slate-800">Longest dwell</td>
                      <td className="p-2.5 sm:p-3 font-mono">7,200 s</td>
                      <td className="p-2.5 sm:p-3 font-mono">4 revisits</td>
                      <td className="p-2.5 sm:p-3 font-mono">99.4%</td>
                      <td className="p-2.5 sm:p-3 font-mono text-rose-600">0.049 ± 0.005</td>
                      <td className="p-2.5 sm:p-3 font-mono">0.024 ± 0.003</td>
                    </tr>
                    <tr className="hover:bg-slate-50">
                      <td className="p-2.5 sm:p-3 font-semibold text-slate-800">Halved dwell</td>
                      <td className="p-2.5 sm:p-3 font-mono">3,600 s</td>
                      <td className="p-2.5 sm:p-3 font-mono">8 revisits</td>
                      <td className="p-2.5 sm:p-3 font-mono">98.8%</td>
                      <td className="p-2.5 sm:p-3 font-mono text-slate-700">0.173 ± 0.013</td>
                      <td className="p-2.5 sm:p-3 font-mono">0.144 ± 0.011</td>
                    </tr>
                    <tr className="hover:bg-slate-50 bg-blue-50/40">
                      <td className="p-2.5 sm:p-3 font-semibold text-blue-900">Nominal (TDI baseline)</td>
                      <td className="p-2.5 sm:p-3 font-mono">1,800 s</td>
                      <td className="p-2.5 sm:p-3 font-mono">16 revisits</td>
                      <td className="p-2.5 sm:p-3 font-mono">97.6%</td>
                      <td className="p-2.5 sm:p-3 font-mono text-blue-800 font-bold">0.346 ± 0.010</td>
                      <td className="p-2.5 sm:p-3 font-mono">0.291 ± 0.009</td>
                    </tr>
                    <tr className="hover:bg-slate-50">
                      <td className="p-2.5 sm:p-3 font-semibold text-slate-800">Fast revisit</td>
                      <td className="p-2.5 sm:p-3 font-mono">900 s</td>
                      <td className="p-2.5 sm:p-3 font-mono">32 revisits</td>
                      <td className="p-2.5 sm:p-3 font-mono">95.2%</td>
                      <td className="p-2.5 sm:p-3 font-mono text-emerald-700 font-bold">0.497 ± 0.014</td>
                      <td className="p-2.5 sm:p-3 font-mono">0.475 ± 0.012</td>
                    </tr>
                    <tr className="hover:bg-slate-50 bg-emerald-50/50">
                      <td className="p-2.5 sm:p-3 font-semibold text-emerald-900">Fastest tested (90-d budget exceeded)</td>
                      <td className="p-2.5 sm:p-3 font-mono">450 s</td>
                      <td className="p-2.5 sm:p-3 font-mono">64 revisits</td>
                      <td className="p-2.5 sm:p-3 font-mono">90.9%</td>
                      <td className="p-2.5 sm:p-3 font-mono text-emerald-700 font-bold">0.571 ± 0.010</td>
                      <td className="p-2.5 sm:p-3 font-mono">0.573 ± 0.013</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          {/* Section 6: Robustness Suite */}
          <section id="robustness" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 6</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                Spin Ephemeris & Robustness Suite
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Sensitivity to unknown spin pole orientation and initial phase offset.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-1">
                <div className="font-bold text-slate-800 text-xs">Spin Pole Tilt Tolerance</div>
                <p className="text-xs text-slate-600 leading-snug">
                  Tilt errors <LatexMath math="\Delta\theta_{\rm pole} \le 5^\circ" /> reduce recovery from <LatexMath math="r = 0.342" /> to <LatexMath math="0.286 \pm 0.014" /> (17% loss). Tilt 20° gives <LatexMath math="0.170 \pm 0.018" />. Precursor astrometry must constrain pole tilt to <LatexMath math="\le 5^\circ" />.
                </p>
              </div>

              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-1">
                <div className="font-bold text-slate-800 text-xs">Phase Ephemeris Window</div>
                <p className="text-xs text-slate-600 leading-snug">
                  Phase errors <LatexMath math="\Delta\phi_0 \le 5^\circ" /> give <LatexMath math="r = 0.295 \pm 0.008" />. At 15°: <LatexMath math="0.187 \pm 0.009" />. At 30°: <LatexMath math="0.072 \pm 0.010" />. At 60°: <LatexMath math="-0.027 \pm 0.014" /> (map destroyed).
                </p>
              </div>

              <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 space-y-1">
                <div className="font-bold text-slate-800 text-xs">Spin State Observability</div>
                <p className="text-xs text-slate-600 leading-snug">
                  The whitened <LatexMath math="\chi^2" /> is numerically invariant to assumed initial phase (&lt;1e-11 relative) and monotone in assumed period across the tested grid. The spin state is observable through reconstruction quality (<LatexMath math="r" /> peaks at truth for 4/4 seeds) but NOT recoverable by minimizing photometric residuals; the ephemeris must come from external precursor astrometry.
                </p>
              </div>
            </div>
          </section>

          {/* Section 7: Exoplanet Target Catalog */}
          <section id="targets" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 7</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                Candidate Exo-Earth Targets &amp; Focal-Line Tracking Budgets
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Astrophysical characterization, focal-line coordinates, and along-window tracking <LatexMath math="\Delta v" /> for five confirmed systems plus one refuted signal kept as an illustrative row. Propulsion hardware is out of the paper's scope.
              </p>
            </div>
            <TargetCatalogExplorer />
            <div className="pt-4">
              <FleetFormationSimulator />
            </div>
          </section>

          {/* Section 8: Simulation Videos & Demonstration Media Showcase */}
          <section id="media" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <DemonstrationMediaCenter
              onSelectSimulator={(tab) => {
                if (tab === "targets") {
                  document.getElementById("targets")?.scrollIntoView({ behavior: "smooth" });
                } else {
                  setActiveSimTab(tab);
                  document.getElementById("interactive")?.scrollIntoView({ behavior: "smooth" });
                }
              }}
            />
          </section>

          {/* Section 9: Interactive Simulators Suite (Tabs layout) */}
          <section id="interactive" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <span className="badge badge-primary text-xs mb-1">Section 9</span>
                <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                  Interactive Physics & Inversion Suite
                </h2>
                <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                  7 real-time interactive laboratory widgets modeling all aspects of SGL time-domain imaging.
                </p>
              </div>
            </div>

            {/* Simulators Interactive Selector Tabs */}
            <div className="flex flex-wrap gap-1.5 border-b border-slate-200 pb-2.5">
              {[
                { id: "sandbox", label: "Image Reconstruction Sandbox", icon: Sparkles },
                { id: "einstein", label: "Einstein Ring Pupil Camera", icon: Eye },
                { id: "fleet", label: "Swarm Fleet Dynamics", icon: Radio },
                { id: "cylinder", label: "SGL Cylinder & Rotation", icon: Zap },
                { id: "cadence", label: "Cadence Law Explorer", icon: Sliders },
                { id: "deflation", label: "Slot-Offset Profiling Demo", icon: ShieldCheck },
                { id: "spin", label: "Spin Likelihood χ² Map", icon: Compass },
              ].map((tab) => {
                const IconComponent = tab.icon;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveSimTab(tab.id as any)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                      activeSimTab === tab.id
                        ? "bg-blue-600 text-white shadow-xs"
                        : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                    }`}
                  >
                    <IconComponent size={13} />
                    <span>{tab.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Active Simulator Display */}
            <div className="pt-2">
              {activeSimTab === "sandbox" && <ImageReconstructionSandbox />}
              {activeSimTab === "einstein" && <EinsteinRingSimulator />}
              {activeSimTab === "fleet" && <FleetFormationSimulator />}
              {activeSimTab === "cylinder" && <SglCylinderSimulator />}
              {activeSimTab === "cadence" && <CadenceExplorer />}
              {activeSimTab === "deflation" && <CloudDeflationDemo />}
              {activeSimTab === "spin" && <SpinLikelihoodMap />}
            </div>
          </section>

          {/* Section 10: Figures Gallery */}
          <section id="figures" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 10</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                Publication Figures Gallery
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Browse all 7 publication figures with captions, high-resolution zoom, and PDF vector downloads.
              </p>
            </div>
            <FigureGallery />
          </section>

          {/* Section 11: Code & Reproducibility */}
          <section id="code" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 11</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                Source Code Architecture & Reproducibility
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Inspect the Python codebase directly in your browser or run all experiments locally.
              </p>
            </div>
            <CodeViewer />
          </section>

          {/* Section 12: Manuscripts & References */}
          <section id="publications" className="card p-4 sm:p-6 md:p-8 space-y-4 sm:space-y-6">
            <div className="border-b border-slate-100 pb-3 sm:pb-4">
              <span className="badge badge-primary text-xs mb-1.5">Section 12</span>
              <h2 className="text-xl sm:text-2xl font-bold text-slate-900">
                Manuscripts, Documents & Citations
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-0.5">
                Download the complete compiled submission papers, review responses, and bibtex citation.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4">
              <div className="bg-slate-50 p-3.5 sm:p-4 rounded-xl border border-slate-200 flex flex-col justify-between space-y-2.5">
                <div>
                  <div className="text-xs font-bold text-slate-800">Main Revised Manuscript PDF</div>
                  <div className="text-[11px] text-slate-500">45 pages, ApJ format, zero overfull errors</div>
                </div>
                <a
                  href="/docs/sgl_time_domain_imaging.pdf"
                  download
                  className="btn btn-sm btn-primary text-xs flex items-center justify-between"
                >
                  <span>Download Paper (PDF)</span>
                  <Download size={13} />
                </a>
              </div>

              <div className="bg-slate-50 p-3.5 sm:p-4 rounded-xl border border-slate-200 flex flex-col justify-between space-y-2.5">
                <div>
                  <div className="text-xs font-bold text-slate-800">Response to Editor & Reviewers</div>
                  <div className="text-[11px] text-slate-500">Itemized point-by-point rebuttal & ablation notes</div>
                </div>
                <a
                  href="/docs/response_to_editor.pdf"
                  download
                  className="btn btn-sm btn-outline text-xs flex items-center justify-between"
                >
                  <span>Download Response (PDF)</span>
                  <Download size={13} />
                </a>
              </div>

              <div className="bg-slate-50 p-3.5 sm:p-4 rounded-xl border border-slate-200 flex flex-col justify-between space-y-2.5">
                <div>
                  <div className="text-xs font-bold text-slate-800">Official Cover Letter</div>
                  <div className="text-[11px] text-slate-500">Formal letter of resubmission to ApJ</div>
                </div>
                <a
                  href="/docs/cover_letter.pdf"
                  download
                  className="btn btn-sm btn-outline text-xs flex items-center justify-between"
                >
                  <span>Download Cover Letter (PDF)</span>
                  <Download size={13} />
                </a>
              </div>
            </div>

            {/* BibTeX Citation Box */}
            <div className="bg-slate-900 text-slate-100 p-3.5 sm:p-4 rounded-xl font-mono text-xs space-y-2">
              <div className="flex justify-between items-center text-slate-400 pb-2 border-b border-slate-800">
                <span>BibTeX Citation</span>
                <button
                  onClick={copyBibtex}
                  className="btn btn-sm btn-outline text-white border-slate-700 hover:bg-slate-800 text-[11px] flex items-center gap-1"
                >
                  {bibtexCopied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                  <span>{bibtexCopied ? "Copied!" : "Copy BibTeX"}</span>
                </button>
              </div>
              <pre className="overflow-x-auto text-slate-300 leading-relaxed text-[11px] sm:text-xs">
                <code>{bibtex}</code>
              </pre>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
