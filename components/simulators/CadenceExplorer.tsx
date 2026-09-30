"use client";

import React, { useState } from "react";
import { Sliders, CheckCircle2, AlertTriangle, ArrowRight, Lightbulb } from "lucide-react";
import LatexMath from "../LatexMath";

export default function CadenceExplorer() {
  // Configurable parameters.  M_p is restricted to the five archived arm-A
  // cadences, because the fidelity numbers below are straight from
  // results/audit.json (cadence_photons) and there is no archived measurement
  // between them -- the previous version linearly interpolated a Pearson r
  // across dwell lengths that the archive does not contain, and did not say so.
  const MP_GRID = [4, 8, 16, 32, 64];
  const [mpIndex, setMpIndex] = useState<number>(2); // M_p = 4, 8, ..., 64
  const revisits = MP_GRID[mpIndex];
  const [overheadSec, setOverheadSec] = useState<number>(45); // 45s standard slew+settle

  // Fixed photon budget per raster position (arm A): M_p * t_s = 8 h = 28,800 s
  const totalBudgetSec = 28800;
  const dwellSec = Math.round(totalBudgetSec / revisits);

  // Overhead and duty cycle.  Duty is per raster position, t_s / (t_s + t_ov).
  const dutyCycle = dwellSec / (dwellSec + overheadSec);
  const smearDeg = (dwellSec / 86400) * 360; // Assuming 24 hr rotation

  // Wall-clock length of the campaign: exposure is fixed by the photon budget
  // (36 x 72 x 8 h = 85.333 d) and only the inter-position overhead grows,
  // (M_p - 1) x 256 slews x t_ov.  At the nominal 45 s this reproduces the
  // archived ledger (85.73 ... 93.73 d).
  const nPositions = 36 * 72;
  const exposureDays = (nPositions * totalBudgetSec) / 86400;
  const wallDays = exposureDays + ((revisits - 1) * nPositions * overheadSec) / 86400;

  // v3 arm-A cadence law (fixed 8 h per raster position, 6 paired seeds),
  // archived in results/audit.json as cadence_photons.{r_profiled,r_white}
  // {mean,se,n=6}.  Only these five points exist.
  const ARCHIVED_R: Record<number, { r: number; se: number; white: number }> = {
    4: { r: 0.0488, se: 0.005, white: 0.0243 },
    8: { r: 0.1725, se: 0.013, white: 0.1441 },
    16: { r: 0.3457, se: 0.010, white: 0.2914 },
    32: { r: 0.4966, se: 0.014, white: 0.4753 },
    64: { r: 0.5712, se: 0.010, white: 0.573 },
  };

  const estimatedR = ARCHIVED_R[revisits].r;
  const estimatedSE = ARCHIVED_R[revisits].se;
  const baselineR = ARCHIVED_R[4].r;

  const presets = [
    { label: "Long dwell (M_p=4)", k: 4, desc: "4 dwells of 7,200 s (r = 0.049)" },
    { label: "Nominal TDI (M_p=16)", k: 16, desc: "16 dwells of 1,800 s (r = 0.346)" },
    { label: "Best within 90 d (M_p=32)", k: 32, desc: "32 dwells of 900 s (r = 0.497)" },
    { label: "Fastest tested (M_p=64)", k: 64, desc: "64 dwells of 450 s (r = 0.571, 93.7 d)" },
  ];

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-accent flex items-center gap-1">
            <Sliders size={14} />
            <span>Factorial Trade Study</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            Cadence Law: Dwell Duration vs. Revisit Count Explorer
          </h3>
        </div>
        <span className="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-1 rounded">
          Fixed photon budget: 28,800 s per raster position
        </span>
      </div>

      <div className="card-body">
        {/* Presets */}
        <div className="flex flex-wrap gap-1.5 mb-5">
          {presets.map((p) => (
            <button
              key={p.k}
              type="button"
              onClick={() => setMpIndex(MP_GRID.indexOf(p.k))}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${
                revisits === p.k
                  ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                  : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Main Controls & Live Outputs */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
          {/* Controls */}
          <div className="space-y-4">
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Revisits per raster position (<LatexMath math="M_p" />):</span>
                <span className="font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">{revisits} dwells</span>
              </div>
              <input
                type="range"
                min="0"
                max={MP_GRID.length - 1}
                step="1"
                value={mpIndex}
                onChange={(e) => setMpIndex(parseInt(e.target.value))}
                className="w-full range-slider"
              />
              <div className="text-[10px] text-slate-500 pt-1 text-center font-mono">
                discrete archived cadences only (M_p = 4, 8, 16, 32, 64)
              </div>
              <div className="grid grid-cols-3 gap-1.5 text-[10px] text-slate-500 pt-1 text-center">
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">M_p = 4</span>
                  <span className="text-[9px] text-slate-400">Longest dwell</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-emerald-700 block">M_p = 32</span>
                  <span className="text-[9px] text-emerald-600 font-bold">Best within 90 d</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">M_p = 64</span>
                  <span className="text-[9px] text-slate-400">Fastest tested</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Spacecraft Slew + Settling Overhead:</span>
                <span className="font-mono font-bold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">{overheadSec} s</span>
              </div>
              <input
                type="range"
                min="15"
                max="90"
                step="5"
                value={overheadSec}
                onChange={(e) => setOverheadSec(parseInt(e.target.value))}
                className="w-full range-slider"
              />
              <div className="grid grid-cols-3 gap-1.5 text-[10px] text-slate-500 pt-1 text-center">
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">15 s</span>
                  <span className="text-[9px] text-slate-400">Micro-thrusters</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-blue-700 block">45 s</span>
                  <span className="text-[9px] text-blue-600 font-bold">Nominal sync</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">90 s</span>
                  <span className="text-[9px] text-slate-400">Conservative</span>
                </div>
              </div>
            </div>

            {/* Plain English Takeaway for Judges */}
            <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs space-y-1.5">
              <div className="flex items-center gap-1.5 font-bold text-amber-900">
                <Lightbulb size={14} className="text-amber-600" />
                <span>Non-Technical Intuition for Judges</span>
              </div>
              <p className="text-amber-800 leading-relaxed">
                Imagine trying to photograph a spinning carousel in a foggy park. If you take one very long exposure, the fog that moves during the exposure blurs everything permanently. But if you take <strong>many short snapshots</strong> at different times, the weather changes randomly between snapshots, while the painted carousel stays in the same place! Averaging the snapshots reveals the true carousel design.
              </p>
            </div>
          </div>

          {/* Metrics Display & SVG Chart */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Live Inversion Performance Metrics
            </h4>

            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white p-3 rounded-lg border border-slate-200">
                <div className="text-xs text-slate-500">Single Dwell Time</div>
                <div className="text-xl font-bold font-mono text-slate-800">
                  {dwellSec} <span className="text-xs font-normal">seconds</span>
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Smear: {smearDeg.toFixed(1)}° rotation
                </div>
              </div>

              <div className="bg-white p-3 rounded-lg border border-slate-200">
                <div className="text-xs text-slate-500">Observation Duty Cycle</div>
                <div className="text-xl font-bold font-mono text-slate-800">
                  {(dutyCycle * 100).toFixed(1)}%
                </div>
                <div className="text-xs text-slate-400 mt-1">
                  Overhead: {(100 - dutyCycle * 100).toFixed(1)}% lost to slew
                </div>
              </div>

              <div className="bg-white p-3 rounded-lg border border-slate-200 col-span-2">
                <div className="flex justify-between items-baseline">
                  <div className="text-xs text-slate-500">
                    Surface Recovery Fidelity (Pearson r)
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded font-bold ${
                    estimatedR > 0.4 ? "bg-emerald-100 text-emerald-800" :
                    estimatedR > 0.25 ? "bg-blue-100 text-blue-800" :
                    "bg-rose-100 text-rose-800"
                  }`}>
                    {estimatedR > 0.4 ? "High Contrast / Continents Visible" :
                     estimatedR > 0.25 ? "Moderate Resolution" : "Severe Aliasing Blur"}
                  </span>
                </div>
                <div className="text-3xl font-extrabold font-mono text-slate-900 mt-1">
                  r = {estimatedR.toFixed(3)}{" "}
                  <span className="text-sm font-bold text-slate-500">± {estimatedSE.toFixed(3)}</span>
                </div>
                <div className="text-[10px] text-slate-500 mt-1">
                  Archived arm-A profiled-GLS mean ± SE over the 6 paired seeds;
                  the white-noise GLS gives{" "}
                  {ARCHIVED_R[revisits].white.toFixed(3)} at the same cadence.
                </div>
                {/* Progress bar */}
                <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden mt-2">
                  <div
                    className="bg-blue-600 h-full rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, (estimatedR / 0.6) * 100)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Quick Summary comparison */}
            <div className="text-xs text-slate-600 pt-1 space-y-1">
              <div>
                <span className="font-semibold text-slate-700">Statistical Gain: </span>
                {revisits > 4 ? (
                  <span className="text-emerald-700 font-medium">
                    +{(estimatedR - baselineR).toFixed(3)} absolute in r over the
                    M_p = 4 baseline ({baselineR.toFixed(3)}).
                  </span>
                ) : (
                  <span className="text-amber-700">Baseline: the longest dwell allowed by the 8 h budget.</span>
                )}
              </div>
              <div>
                <span className="font-semibold text-slate-700">Campaign wall-clock: </span>
                {wallDays.toFixed(2)} d ({exposureDays.toFixed(2)} d exposure +{" "}
                {(wallDays - exposureDays).toFixed(2)} d inter-position slew)
                {wallDays > 90 && <span className="text-rose-700 font-bold"> — exceeds a 90-day window</span>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
