"use client";

import React, { useState } from "react";
import Image from "next/image";
import { Image as ImageIcon, Download, ZoomIn, CheckCircle2, ChevronRight } from "lucide-react";

interface FigureItem {
  id: string;
  num: number;
  title: string;
  filename: string;
  pdfFilename: string;
  caption: string;
  takeaway: string;
  keyMetric: string;
}

const FIGURES: FigureItem[] = [
  {
    id: "fig1",
    num: 1,
    title: "SGL Forward Model & Stochastic Cloud Physics",
    filename: "/figures/fig_model.png",
    pdfFilename: "/figures/fig_model.pdf",
    caption: "Model overview. (a) Discrete aperture-averaged SGL kernel used in this work (points) against the analytic d/(4ρ) tail (line). (b) Synthetic truth surface albedo map (fine grid, seeded, with oceans, continents, and polar caps). (c) A single instantaneous scene during the campaign at mean cloud cover fc ≈ 0.55: rotated, partially illuminated, and modulated by the advecting cloud field. (d) The same scene after convolution with the SGL kernel: the measurement raster sampled across the image cylinder.",
    takeaway: "Sets out the forward model actually inverted: a discrete aperture-averaged kernel, a rotating illuminated scene, and a stochastic OU cloud field, with the convolved raster in (d) as the observable.",
    keyMetric: "Kernel: K(ρ) ∝ d/(4ρ) Aperture-Averaged",
  },
  {
    id: "fig2",
    num: 2,
    title: "Operator Validation Against Analytic Estimates",
    filename: "/figures/fig_validation.png",
    pdfFilename: "/figures/fig_validation.pdf",
    caption: "Validation of the discrete operator: measured deconvolution noise penalty vs. the analytic estimate of Toth & Turyshev (2021). The ~45% difference at n = 128 reflects discrete pixel-averaging of the central singularity and finite-domain boundary attenuation.",
    takeaway: "The discrete operator reproduces the analytic deconvolution-noise scaling, but not to machine precision: the deviation at the largest grid is ~45% and is stated, attributed, and bounded in the caption.",
    keyMetric: "Noise Penalty vs. Analytic; 45% Gap at n=128",
  },
  {
    id: "fig3",
    num: 3,
    title: "Exoplanet Surface Recovery Gallery",
    filename: "/figures/fig_gallery.png",
    pdfFilename: "/figures/fig_gallery.pdf",
    caption: "Reconstruction gallery for the fiducial 87.33-day campaign (n = 64, M_p = 16, t_s = 1800 s, 16-node exposure quadrature). Top row: truth albedo; TDI reconstruction of the rotating cloud-free planet (r = 0.979, SSIM = 0.848); phase-blind coadd (B1) at realized cover 0.56, essentially featureless (r = 0.042). Bottom row, all at realized cover ≈ 0.56: 16-bin phase-binned coadd (B2), white-noise GLS (B3), and TDI.",
    takeaway: "At ~56% realized cloud cover the TDI map recovers the gross hemispheric dichotomy (r = 0.342), while the phase-blind coadd does not — but fine surface features are erased by weather, not recovered.",
    keyMetric: "r = 0.342 at 56% Realized Cover",
  },
  {
    id: "fig4",
    num: 4,
    title: "Reconstruction Fidelity vs. Cloud Cover",
    filename: "/figures/fig_ssim_fc.png",
    pdfFilename: "/figures/fig_ssim_fc.pdf",
    caption: "(a) SSIM and (b) Pearson correlation r as functions of realized cloud cover, across 10 paired seeds; error bars are ±1 SE. Curves: TDI with exact slot profiling (blue), clouds-as-white-noise GLS, 16-bin phase-binned coadd, and the phase-blind coadd.",
    takeaway: "TDI with slot profiling is the best estimator above ~40% cover, but the 16-bin phase-binned coadd matches or beats it at low cover — the gain is weather-driven, not uniform across all conditions.",
    keyMetric: "Pearson r = 0.342 ± 0.008 at 55% Clouds",
  },
  {
    id: "fig5",
    num: 5,
    title: "Factorial Cadence Mechanism Ablation",
    filename: "/figures/fig_cadence.png",
    pdfFilename: "/figures/fig_cadence.pdf",
    caption: "(a) Fidelity r vs. registered revisits per pixel M_p and dwell time t_s at fixed photon budget, for both resource arms (A: 8 h per raster position; B: 90-day wall clock). (b) Effective number of independent looks N_eff against the M_p line for τ_cloud = 1, 2, 4 d, with the arm-A duty cycle η for 45 s/dwell overhead on the second axis.",
    takeaway: "Frequent revisits beat a single long dwell, but the gain saturates: the OU model caps the effective independent looks well below M_p, and in the fixed-wall-clock arm the same doublings buy far less.",
    keyMetric: "r: 0.049 → 0.571 from M_p = 4 → 64 (arm A)",
  },
  {
    id: "fig6",
    num: 6,
    title: "Robustness Suite: Spin Ephemeris & Scale Resolution",
    filename: "/figures/fig_robust.png",
    pdfFilename: "/figures/fig_robust.pdf",
    caption: "(a) Correlation vs. spin-pole tilt and assumed initial-phase error (10 paired seeds). (b) Whitened χ² re-referenced to its own value at zero phase against assumed phase offset for every trial period: the objective is exactly flat (≤10⁻¹¹), while r (right axis) peaks at the truth. (c) Scale-dependent correlation r(ℓ) for the cloud-free and cloudy campaigns (10 seeds, ±1 SE) with the ℓ ≤ 20 grid ceiling marked.",
    takeaway: "r peaks at the true spin state while the likelihood is exactly flat in phase, so the ephemeris must come from an external precursor; resolution is capped by the grid (ℓ ≈ 18–20), and clouds cut the usable band at ℓ ≈ 9.",
    keyMetric: "r Peaks at Truth; Ephemeris from Precursor",
  },
  {
    id: "fig7",
    num: 7,
    title: "Regularization and Cloud-Amplitude Sensitivity",
    filename: "/figures/fig_lamsigma.png",
    pdfFilename: "/figures/fig_lamsigma.pdf",
    caption: "Regularization and assumed-cloud-amplitude sensitivity (10 seeds). (a) Paired Δr against the frozen λ = 3×10⁻³: cloud-free quality peaks near λ = 0.3 and then declines, while cloudy quality keeps rising to the largest weight tested (+0.178 at λ = 10). Bars are ±1 SE. (b) The whitened objective χ²/χ²(3×10⁻³) cannot make that choice: flat to ~0.1% over five decades in the cloudy case. (c) The assumed cloud amplitude: mean paired change in r is ≤ 2.6×10⁻⁴ from 0.25× to 16× the calibrated σ_cl, while χ² spans a factor 8×10⁴.",
    takeaway: "Image quality can improve where the likelihood is blind: neither χ² nor the assumed cloud amplitude selects the regularization weight, so λ is chosen on image quality and disclosed as a tuned prior, not fitted from the data.",
    keyMetric: "r Insensitive to σ_cl (≤2.6×10⁻⁴); χ² Blind",
  },
  {
    id: "fig8",
    num: 8,
    title: "Candidate Exo-Earth Targets & Focal-Line Placement",
    filename: "/figures/fig_targets.png",
    pdfFilename: "/figures/fig_targets.pdf",
    caption: "Celestial placement (equatorial Mollweide) of the five confirmed targets (blue circles), the refuted τ Cet e signal (green square), and their SGL focal directions (orange stars, purple triangle). The gray line marks the ecliptic plane; Ross 128 and Teegarden c focal lines lie in the ecliptic (β_ecl ≈ 0°).",
    takeaway: "Focal-line ecliptic latitude, not distance, sets the departure cost: two of the five confirmed targets are essentially in-plane, while the along-track 90-day tracking requirement for the confirmed set spans 1.34–5.81 km/s. The τ Cet row is illustrative dynamics only — its planet signal has been refuted.",
    keyMetric: "5 Confirmed Targets; Δv 1.34–5.81 km/s",
  },
];

export default function FigureGallery() {
  const [selectedFig, setSelectedFig] = useState<FigureItem>(FIGURES[2]); // Default to Gallery (Fig 3)

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-primary flex items-center gap-1">
            <ImageIcon size={14} />
            <span>Publication Figures</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            High-Resolution Scientific Figures Gallery
          </h3>
        </div>
        <a
          href={selectedFig.pdfFilename}
          download
          className="btn btn-sm btn-outline flex items-center gap-1 text-xs"
        >
          <Download size={13} />
          <span>Download Figure {selectedFig.num} Vector PDF</span>
        </a>
      </div>

      <div className="card-body">
        {/* Figure Selector Pills */}
        <div className="flex flex-wrap gap-2 mb-4 border-b border-slate-200 pb-3">
          {FIGURES.map((fig) => (
            <button
              key={fig.id}
              onClick={() => setSelectedFig(fig)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedFig.id === fig.id
                  ? "bg-blue-600 text-white shadow-sm"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200"
              }`}
            >
              Fig {fig.num}: {fig.title.split(":")[0]}
            </button>
          ))}
        </div>

        {/* Active Figure Card */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Image Display */}
          <div className="lg:col-span-8 bg-slate-50 p-3 rounded-xl border border-slate-200 flex flex-col items-center justify-center">
            <div className="relative w-full rounded-lg overflow-hidden bg-white border border-slate-200 shadow-sm">
              <img
                src={selectedFig.filename}
                alt={selectedFig.title}
                className="w-full h-auto object-contain max-h-[500px]"
              />
            </div>
          </div>

          {/* Details & Takeaway */}
          <div className="lg:col-span-4 space-y-4">
            <div>
              <span className="text-xs font-mono font-bold text-blue-600 uppercase tracking-wider">
                Figure {selectedFig.num} of {FIGURES.length}
              </span>
              <h4 className="text-base font-bold text-slate-900 mt-1">
                {selectedFig.title}
              </h4>
            </div>

            <div className="p-3 bg-blue-50/70 border border-blue-200 rounded-lg text-xs space-y-1.5">
              <div className="font-bold text-blue-900 flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-blue-600" />
                <span>Executive Finding for Judges:</span>
              </div>
              <p className="text-blue-800 leading-relaxed">
                {selectedFig.takeaway}
              </p>
            </div>

            <div className="bg-slate-50 p-3 rounded-lg border border-slate-200 text-xs">
              <div className="text-slate-400 font-bold uppercase tracking-wider text-[10px] mb-1">
                Formal Paper Caption:
              </div>
              <p className="text-slate-600 leading-relaxed">
                {selectedFig.caption}
              </p>
            </div>

            <div className="bg-white p-3 rounded-lg border border-slate-200 flex justify-between items-center text-xs">
              <span className="text-slate-500 font-medium">Key Quantitative Metric:</span>
              <span className="font-mono font-bold text-slate-800 bg-slate-100 px-2 py-1 rounded">
                {selectedFig.keyMetric}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
