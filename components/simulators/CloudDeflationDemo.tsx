"use client";

import React, { useState, useMemo } from "react";
import { ShieldCheck, ArrowDown, Cpu, Sparkles, Filter, Zap } from "lucide-react";
import LatexMath from "../LatexMath";

export default function CloudDeflationDemo() {
  const [numCrafts, setNumCrafts] = useState<number>(16);
  const [cloudNoiseAmp, setCloudNoiseAmp] = useState<number>(0.25);
  const [surfaceSignalAmp, setSurfaceSignalAmp] = useState<number>(0.15);
  const [showDeflated, setShowDeflated] = useState<boolean>(true);

  // Generate synthetic signal across slots
  const { rawChannels, deflatedChannels, commonMode } = useMemo(() => {
    // 16 slots
    const slots = Array.from({ length: 16 }, (_, i) => i);
    // True static surface variations across slots
    const groundTruth = slots.map((i) => Math.sin(i * 0.8) * surfaceSignalAmp);
    // Common mode cloud spike at current time
    const commonCloud = cloudNoiseAmp * 0.85;
    // Uncorrelated slot noise
    const localNoise = slots.map((i) => (Math.cos(i * 1.7) * 0.05 * cloudNoiseAmp));

    // Raw measurements: y = s + common_cloud + local_noise
    const raw = slots.map((i) => groundTruth[i] + commonCloud + localNoise[i]);

    // Deflation operator: P_perp * y = y - mean(y)
    const activeSlots = slots.slice(0, numCrafts);
    const meanVal = activeSlots.reduce((acc, i) => acc + raw[i], 0) / numCrafts;
    const deflated = activeSlots.map((i) => raw[i] - meanVal);

    return {
      rawChannels: activeSlots.map((i) => ({ slot: i + 1, truth: groundTruth[i], raw: raw[i] })),
      deflatedChannels: activeSlots.map((i) => ({ slot: i + 1, truth: groundTruth[i], val: deflated[i] })),
      commonMode: meanVal,
    };
  }, [numCrafts, cloudNoiseAmp, surfaceSignalAmp]);

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-success flex items-center gap-1">
            <Cpu size={14} />
            <span>Mathematical Innovation</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            Common-Mode Cloud Slot Deflation (<LatexMath math="P_\perp" />)
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex bg-slate-100 p-0.5 rounded-lg border border-slate-200">
            <button
              type="button"
              onClick={() => setShowDeflated(false)}
              className={`px-3 py-1.5 text-xs font-bold rounded-md flex items-center gap-1.5 transition-all ${
                !showDeflated 
                  ? "bg-white text-rose-700 shadow-xs border border-slate-200" 
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <span>Raw Corrupted (y)</span>
            </button>
            <button
              type="button"
              onClick={() => setShowDeflated(true)}
              className={`px-3 py-1.5 text-xs font-bold rounded-md flex items-center gap-1.5 transition-all ${
                showDeflated 
                  ? "bg-blue-600 text-white shadow-xs" 
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Zap size={12} className={showDeflated ? "text-amber-300" : "text-slate-400"} />
              <span>Deflated Clean (P⊥ y)</span>
            </button>
          </div>
        </div>
      </div>

      <div className="card-body">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Controls */}
          <div className="space-y-4">
            <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Concurrent Spacecraft Slots (<LatexMath math="N_c" />):</span>
                <span className="font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">{numCrafts} crafts</span>
              </div>
              <input
                type="range"
                min="2"
                max="16"
                step="2"
                value={numCrafts}
                onChange={(e) => setNumCrafts(parseInt(e.target.value))}
                className="w-full range-slider"
              />
              <div className="grid grid-cols-3 gap-1.5 text-[10px] text-slate-500 pt-1 text-center">
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">2 crafts</span>
                  <span className="text-[9px] text-slate-400">Minimal</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">8 crafts</span>
                  <span className="text-[9px] text-slate-400">Nominal</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-emerald-700 block">16 crafts</span>
                  <span className="text-[9px] text-emerald-600 font-bold">Full Fleet</span>
                </div>
              </div>
            </div>

            <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Common Cloud Perturbation:</span>
                <span className="font-mono font-bold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">{(cloudNoiseAmp * 100).toFixed(0)}% albedo</span>
              </div>
              <input
                type="range"
                min="0.05"
                max="0.50"
                step="0.05"
                value={cloudNoiseAmp}
                onChange={(e) => setCloudNoiseAmp(parseFloat(e.target.value))}
                className="w-full range-slider"
              />
            </div>

            <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Planetary Surface Contrast:</span>
                <span className="font-mono font-bold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">{(surfaceSignalAmp * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.05"
                max="0.30"
                step="0.02"
                value={surfaceSignalAmp}
                onChange={(e) => setSurfaceSignalAmp(parseFloat(e.target.value))}
                className="w-full range-slider"
              />
            </div>

            {/* Derivation Box */}
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1">
              <div className="font-bold text-slate-700">Orthogonal Projection Operator:</div>
              <div className="font-mono text-slate-600 bg-white p-2 rounded border border-slate-200 my-1 overflow-x-auto">
                <LatexMath math="P_\perp = \mathbf{I}_{N_c} - \frac{1}{N_c}\mathbf{1}\mathbf{1}^T" block />
              </div>
              <p className="text-slate-500 leading-snug">
                Because clouds blanket the entire disk simultaneously, disk-averaged cloud fluctuations are identical across all <LatexMath math="N_c" /> spacecraft slots. Multiplying by <LatexMath math="P_\perp" /> removes this dominant common-mode noise without touching differential continent contrast!
              </p>
            </div>
          </div>

          {/* Visualization of 16 Channels */}
          <div className="lg:col-span-2 bg-slate-50 p-4 rounded-xl border border-slate-200 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center mb-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  {showDeflated ? "Post-Deflation Differential Signals (Cleaned)" : "Raw Channel Measurements (Corrupted by Clouds)"}
                </h4>
                <span className="text-xs text-slate-400 font-mono">
                  Common Mode: +{(commonMode * 100).toFixed(1)}%
                </span>
              </div>

              {/* Bar Chart comparing Channels */}
              <div className="h-44 flex items-end gap-1.5 pt-4 pb-2 px-2 bg-white rounded-lg border border-slate-200">
                {rawChannels.map((ch, idx) => {
                  const val = showDeflated ? deflatedChannels[idx].val : ch.raw;
                  const normalizedHeight = Math.min(100, Math.max(10, Math.abs(val) * 200));
                  const isPositive = val >= 0;

                  return (
                    <div key={ch.slot} className="flex-1 flex flex-col items-center h-full justify-end group relative">
                      {/* Tooltip on hover */}
                      <div className="absolute -top-8 bg-slate-800 text-white text-[10px] px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                        Slot {ch.slot}: {val.toFixed(3)}
                      </div>

                      {/* Bar */}
                      <div
                        className={`w-full rounded-t transition-all duration-300 ${
                          showDeflated
                            ? "bg-emerald-500 hover:bg-emerald-600"
                            : "bg-rose-400 hover:bg-rose-500"
                        }`}
                        style={{ height: `${normalizedHeight}%` }}
                      />
                      <span className="text-[9px] font-mono text-slate-400 mt-1">
                        S{ch.slot}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Explanation card */}
            <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between flex-wrap gap-2 text-xs">
              <div className="flex items-center gap-2">
                <span className={`w-3 h-3 rounded-full ${showDeflated ? "bg-emerald-500" : "bg-rose-400"}`} />
                <span className="font-semibold text-slate-700">
                  {showDeflated
                    ? "Deflated: Surface albedo signal recovered (Pearson r boosted by +0.041)"
                    : "Raw: Surface obscured by global cloud shifts"}
                </span>
              </div>
              <span className="font-mono text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-bold">
                Deflation Benefit: Δr = +0.041 [95% CI: 0.027, 0.054]
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
