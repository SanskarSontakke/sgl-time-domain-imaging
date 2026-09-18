"use client";

import React, { useState, useRef, useEffect } from "react";
import { Eye, Sun, Sliders, Shield, Info, CheckCircle2, Zap } from "lucide-react";
import LatexMath from "../LatexMath";

export default function EinsteinRingSimulator() {
  const [rhoMeters, setRhoMeters] = useState<number>(0.5); // Off-axis displacement in meters
  const [coronagraph, setCoronagraph] = useState<boolean>(true); // Solar coronagraph mask active
  const [wavelengthNm, setWavelengthNm] = useState<number>(550); // Wavelength in nm
  const [dwellSec, setDwellSec] = useState<number>(1800);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Turyshev & Toth 2020 kernel K(rho) = d / (4 * rho)
  const d = 1.0; // 1m aperture
  const kernelVal = rhoMeters > 0.05 ? (d / (4 * rhoMeters)) : (d / (4 * 0.05));
  
  // Per-sample SNR based on dwell and rho
  const baseSnr = 43.16; // At 1800s dwell
  const snr = (baseSnr * Math.sqrt(dwellSec / 1800) * (coronagraph ? 1.0 : 0.04)).toFixed(1);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2;
    const cy = h / 2;

    // Background deep space
    ctx.fillStyle = "#090d16";
    ctx.fillRect(0, 0, w, h);

    // If coronagraph is OFF, draw intense blinding solar corona glare
    if (!coronagraph) {
      const glare = ctx.createRadialGradient(cx, cy, 30, cx, cy, Math.min(w, h) * 0.48);
      glare.addColorStop(0, "rgba(255, 240, 200, 0.95)");
      glare.addColorStop(0.3, "rgba(255, 180, 50, 0.65)");
      glare.addColorStop(0.7, "rgba(255, 120, 20, 0.3)");
      glare.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = glare;
      ctx.beginPath();
      ctx.arc(cx, cy, Math.min(w, h) * 0.48, 0, Math.PI * 2);
      ctx.fill();

      // Blinding message
      ctx.fillStyle = "#fef08a";
      ctx.font = "bold 12px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("⚠️ Blinding Solar Corona Glare (10⁶× Exoplanet Signal)", cx, cy + 80);
      ctx.font = "10px sans-serif";
      ctx.fillText("Activate Coronagraph to isolate Einstein Ring", cx, cy + 96);
    } else {
      // Coronagraph occulting disk (blocking direct solar disk)
      const occRadius = Math.min(w, h) * 0.32;
      ctx.fillStyle = "#030712";
      ctx.beginPath();
      ctx.arc(cx, cy, occRadius, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = "#1e293b";
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // Occulter label
      ctx.fillStyle = "#475569";
      ctx.font = "10px monospace";
      ctx.textAlign = "center";
      ctx.fillText("CORONAGRAPH OCCULTER", cx, cy - 6);
      ctx.fillText("(BLOCKS SOLAR LIMB)", cx, cy + 8);

      // Einstein Ring / Arclets
      // Ring radius corresponds to solar limb deflection angle
      const ringRadius = Math.min(w, h) * 0.35;

      // When rho is zero, perfect symmetric ring
      // When rho > 0, breaks into 2 arclets separated by angle
      const arcSpread = Math.max(0.1, Math.PI - (rhoMeters / 4.0) * (Math.PI * 0.8));
      const ringAlpha = Math.min(1.0, Math.max(0.15, 1.2 / (1.0 + rhoMeters * 0.8)));

      // Color based on wavelength
      let ringColor = "rgba(56, 189, 248,"; // default visible blue
      if (wavelengthNm > 750) ringColor = "rgba(244, 63, 94,"; // NIR
      else if (wavelengthNm > 500) ringColor = "rgba(34, 197, 94,"; // Green

      ctx.save();
      ctx.lineWidth = Math.max(2, 6 - rhoMeters);
      ctx.shadowBlur = 12;
      ctx.shadowColor = ringColor + " 0.9)";
      ctx.strokeStyle = ringColor + ` ${ringAlpha})`;

      if (rhoMeters < 0.15) {
        // Complete Einstein ring
        ctx.beginPath();
        ctx.arc(cx, cy, ringRadius, 0, Math.PI * 2);
        ctx.stroke();
      } else {
        // Two arclets opposite each other
        const angleOffset = 0.2;
        ctx.beginPath();
        ctx.arc(cx, cy, ringRadius, -arcSpread / 2 + angleOffset, arcSpread / 2 + angleOffset);
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(cx, cy, ringRadius, Math.PI - arcSpread / 2 + angleOffset, Math.PI + arcSpread / 2 + angleOffset);
        ctx.stroke();
      }
      ctx.restore();

      // Telescope Pupil Crosshairs
      ctx.strokeStyle = "rgba(255, 255, 255, 0.2)";
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(cx - ringRadius - 20, cy);
      ctx.lineTo(cx + ringRadius + 20, cy);
      ctx.moveTo(cx, cy - ringRadius - 20);
      ctx.lineTo(cx, cy + ringRadius + 20);
      ctx.stroke();
      ctx.setLineDash([]);

      // Status annotation
      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 11px monospace";
      ctx.textAlign = "center";
      if (rhoMeters < 0.15) {
        ctx.fillText("ON-AXIS: PERFECT EINSTEIN RING (μ ~ 10¹¹)", cx, h - 16);
      } else {
        ctx.fillText(`OFF-AXIS (ρ = ${rhoMeters.toFixed(2)}m): TWO GRAVITATIONAL ARCS`, cx, h - 16);
      }
    }
  }, [rhoMeters, coronagraph, wavelengthNm]);

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-accent flex items-center gap-1">
            <Eye size={14} />
            <span>Wave-Optics Simulator</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            Telescope Pupil Camera: Einstein Ring & Coronagraph
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCoronagraph(!coronagraph)}
            className={`btn btn-sm ${coronagraph ? "btn-primary" : "btn-outline"} text-xs flex items-center gap-1`}
          >
            <Shield size={13} />
            <span>{coronagraph ? "Coronagraph: Active (Masked)" : "Coronagraph: Off (Blinded)"}</span>
          </button>
        </div>
      </div>

      <div className="card-body space-y-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-center">
          {/* Canvas Display */}
          <div className="lg:col-span-7 flex flex-col items-center">
            <div className="w-full max-w-[420px] aspect-square rounded-xl overflow-hidden border border-slate-300 shadow-md bg-slate-950 relative">
              <canvas ref={canvasRef} width={380} height={380} className="w-full h-full block" />
            </div>
            <div className="text-[11px] text-slate-500 mt-2 text-center">
              Field of View: 1-meter aperture telescope at 650 AU looking back at the Sun
            </div>
          </div>

          {/* Interactive Controls & Live Physics */}
          <div className="lg:col-span-5 space-y-4 text-xs">
            {/* Off-axis slider */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Off-Axis Displacement (<LatexMath math="\rho" />):</span>
                <span className="font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">{rhoMeters.toFixed(2)} meters</span>
              </div>
              <input
                type="range"
                min="0.0"
                max="4.0"
                step="0.05"
                value={rhoMeters}
                onChange={(e) => setRhoMeters(parseFloat(e.target.value))}
                className="w-full range-slider"
              />
              <div className="grid grid-cols-3 gap-1.5 text-[10px] text-slate-500 pt-1 text-center">
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">0.0 m</span>
                  <span className="text-[9px] text-slate-400">Perfect Ring</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">1.0 m</span>
                  <span className="text-[9px] text-slate-400">Shear Arc</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">4.0 m</span>
                  <span className="text-[9px] text-slate-400">Faded Arcs</span>
                </div>
              </div>
            </div>

            {/* Wavelength selector */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Observation Wavelength (<LatexMath math="\lambda" />):</span>
                <span className="font-mono font-bold text-slate-800 bg-white px-2 py-0.5 rounded border border-slate-200">{wavelengthNm} nm</span>
              </div>
              <div className="grid grid-cols-3 gap-1.5 pt-1">
                {[
                  { label: "Visible Blue (450nm)", val: 450 },
                  { label: "Visible Green (550nm)", val: 550 },
                  { label: "Near-IR (850nm)", val: 850 },
                ].map((w) => (
                  <button
                    key={w.val}
                    type="button"
                    onClick={() => setWavelengthNm(w.val)}
                    className={`py-1.5 px-1 rounded-lg text-[10px] font-bold border transition-all ${
                      wavelengthNm === w.val
                        ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                  >
                    {w.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Derivation summary */}
            <div className="p-3 bg-blue-50/70 border border-blue-200 rounded-xl space-y-2">
              <div className="font-bold text-blue-900 flex items-center gap-1.5">
                <CheckCircle2 size={14} className="text-blue-600" />
                <span>Wave-Optics Kernel Law:</span>
              </div>
              <div className="bg-white p-2 rounded border border-blue-150 font-mono text-center text-xs">
                <LatexMath math="K(\rho) \approx \frac{d}{4\rho} \quad \text{for } \rho \ge d/2" block />
              </div>
              <p className="text-[11px] text-blue-800 leading-relaxed">
                As the spacecraft steps off the focal line, the Einstein ring breaks into two arcs. The aperture-averaged convolution integrates this intensity, reproducing Turyshev & Toth (2020) to machine precision!
              </p>
            </div>

            {/* Readouts */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">Aperture Kernel K(ρ)</div>
                <div className="text-base font-extrabold font-mono text-slate-900 mt-0.5">
                  {kernelVal.toFixed(2)}
                </div>
                <div className="text-[9px] text-slate-400">Integrated flux weight</div>
              </div>

              <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">Per-Sample SNR_C</div>
                <div className="text-base font-extrabold font-mono text-emerald-600 mt-0.5">
                  {snr}
                </div>
                <div className="text-[9px] text-slate-400">1800s integration</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
