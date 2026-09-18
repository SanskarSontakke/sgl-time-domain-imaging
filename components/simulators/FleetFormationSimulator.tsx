"use client";

import React, { useState, useRef, useEffect } from "react";
import { Play, Pause, Compass, Rocket, Radio, ShieldCheck, Zap, Sliders, CheckCircle2 } from "lucide-react";
import LatexMath from "../LatexMath";

type FormationMode = "grid" | "hex" | "lissajous";

export default function FleetFormationSimulator() {
  const [formation, setFormation] = useState<FormationMode>("grid");
  const [driftSpeed, setDriftSpeed] = useState<number>(51.0); // m/s (Ross 128 b nominal)
  const [thrusterType, setThrusterType] = useState<"electrospray" | "ion" | "coldgas">("ion");
  const [isPlaying, setIsPlaying] = useState<boolean>(true);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Propulsion physics
  // Tsiolkovsky rocket equation: m_prop = m_dry * (exp(dv / (g0 * Isp)) - 1)
  const ispMap = {
    electrospray: 2000, // seconds
    ion: 3000,         // seconds
    coldgas: 70,       // seconds
  };
  const isp = ispMap[thrusterType];
  const g0 = 9.80665;
  const dvKms = (driftSpeed * 0.057).toFixed(2); // Approximate 90-day dv based on drift velocity
  const dryMassKg = 18.0; // 18 kg microsat
  const dvMs = parseFloat(dvKms) * 1000;
  const propMassKg = (dryMassKg * (Math.exp(dvMs / (g0 * isp)) - 1)).toFixed(2);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let time = 0;

    const render = () => {
      if (isPlaying) {
        time += 0.02;
      }

      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;
      const radius = Math.min(w, h) * 0.40;

      // Deep space background
      ctx.fillStyle = "#090d16";
      ctx.fillRect(0, 0, w, h);

      // Stars in background
      ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
      for (let i = 0; i < 30; i++) {
        const sx = ((i * 73 + 12) % w);
        const sy = ((i * 127 + 45) % h);
        ctx.fillRect(sx, sy, 1.2, 1.2);
      }

      // 1.3 km Image Cylinder Boundary
      ctx.strokeStyle = "rgba(56, 189, 248, 0.25)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      // Cylinder fill glow
      const cylGrad = ctx.createRadialGradient(cx, cy, radius * 0.7, cx, cy, radius);
      cylGrad.addColorStop(0, "rgba(2, 132, 199, 0.02)");
      cylGrad.addColorStop(1, "rgba(2, 132, 199, 0.08)");
      ctx.fillStyle = cylGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fill();

      // Center exoplanet focal line axis
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - 10, cy);
      ctx.lineTo(cx + 10, cy);
      ctx.moveTo(cx, cy - 10);
      ctx.lineTo(cx, cy + 10);
      ctx.stroke();

      // 16 Spacecraft Positions
      const nCrafts = 16;
      const craftCoords: { x: number; y: number }[] = [];

      for (let i = 0; i < nCrafts; i++) {
        let x = cx;
        let y = cy;

        if (formation === "grid") {
          // 4x4 Grid with slight patrol drift
          const row = Math.floor(i / 4);
          const col = i % 4;
          const spacing = (radius * 1.5) / 3;
          x = cx + (col - 1.5) * spacing + Math.sin(time + i) * 6;
          y = cy + (row - 1.5) * spacing + Math.cos(time + i) * 6;
        } else if (formation === "hex") {
          // Hexagonal rings
          if (i === 0) {
            x = cx;
            y = cy;
          } else if (i <= 6) {
            const angle = (i / 6) * Math.PI * 2 + time * 0.2;
            x = cx + Math.cos(angle) * (radius * 0.45);
            y = cy + Math.sin(angle) * (radius * 0.45);
          } else {
            const angle = ((i - 6) / 9) * Math.PI * 2 - time * 0.15;
            x = cx + Math.cos(angle) * (radius * 0.82);
            y = cy + Math.sin(angle) * (radius * 0.82);
          }
        } else if (formation === "lissajous") {
          // Orthogonal sinusoidal Lissajous orbits
          const phase = (i / nCrafts) * Math.PI * 2;
          x = cx + Math.sin(time * 0.6 + phase) * (radius * 0.85);
          y = cy + Math.cos(time * 0.9 + phase * 2) * (radius * 0.85);
        }

        craftCoords.push({ x, y });
      }

      // Inter-satellite Laser Cross-Links
      ctx.strokeStyle = "rgba(16, 185, 129, 0.35)";
      ctx.lineWidth = 1;
      for (let i = 0; i < nCrafts; i++) {
        const next = (i + 1) % nCrafts;
        ctx.beginPath();
        ctx.moveTo(craftCoords[i].x, craftCoords[i].y);
        ctx.lineTo(craftCoords[next].x, craftCoords[next].y);
        ctx.stroke();

        // Cross connection to center
        if (i % 2 === 0) {
          ctx.beginPath();
          ctx.moveTo(craftCoords[i].x, craftCoords[i].y);
          ctx.lineTo(craftCoords[(i + 4) % nCrafts].x, craftCoords[(i + 4) % nCrafts].y);
          ctx.stroke();
        }
      }

      // Draw Individual Spacecraft
      craftCoords.forEach((c, idx) => {
        // Thruster plume (if moving)
        ctx.fillStyle = "rgba(56, 189, 248, 0.6)";
        ctx.beginPath();
        ctx.arc(c.x - Math.sin(time * 2 + idx) * 4, c.y + 7, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Spacecraft body (1m aperture)
        ctx.fillStyle = "#38bdf8";
        ctx.beginPath();
        ctx.arc(c.x, c.y, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.2;
        ctx.stroke();

        // Craft label
        ctx.fillStyle = "#94a3b8";
        ctx.font = "8px monospace";
        ctx.fillText(`SC${idx + 1}`, c.x + 6, c.y + 3);
      });

      // Formation Header annotation
      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 10px monospace";
      ctx.fillText("16-CRAFT COOPERATIVE SWARM FORMATION", 16, 22);
      ctx.fillStyle = "#64748b";
      ctx.font = "9px sans-serif";
      ctx.fillText("Laser sync latency < 5 μs | P⊥ Deflation active", 16, 36);

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [formation, driftSpeed, isPlaying]);

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-primary flex items-center gap-1">
            <Radio size={14} />
            <span>Swarm Dynamics Simulator</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            16-Spacecraft Deep Space Formation & Propulsion Flight
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="btn btn-sm btn-outline flex items-center gap-1 text-xs"
          >
            {isPlaying ? <Pause size={13} /> : <Play size={13} />}
            <span>{isPlaying ? "Pause Flight" : "Resume"}</span>
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
              Formation scanning within the 1.3 km focal cylinder at 650 AU
            </div>
          </div>

          {/* Controls & Mission Budgets */}
          <div className="lg:col-span-5 space-y-4 text-xs">
            {/* Formation Selector */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <label className="font-semibold text-slate-700 block">Swarm Geometry Configuration</label>
              <div className="grid grid-cols-3 gap-1.5 pt-1">
                {[
                  { id: "grid", label: "4×4 Raster Grid" },
                  { id: "hex", label: "Hexagonal Rings" },
                  { id: "lissajous", label: "Lissajous Sweep" },
                ].map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFormation(f.id as FormationMode)}
                    className={`py-1.5 px-2 rounded-lg text-[11px] font-bold border transition-all ${
                      formation === f.id
                        ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Target Image Plane Drift Speed */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="font-semibold text-slate-700">Exoplanet Focal Drift Velocity:</span>
                <span className="font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">{driftSpeed.toFixed(1)} m/s</span>
              </div>
              <input
                type="range"
                min="20"
                max="120"
                step="5"
                value={driftSpeed}
                onChange={(e) => setDriftSpeed(parseFloat(e.target.value))}
                className="w-full range-slider"
              />
              <div className="grid grid-cols-3 gap-1.5 text-[10px] text-slate-500 pt-1 text-center">
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">31 m/s</span>
                  <span className="text-[9px] text-slate-400">τ Ceti e</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">51 m/s</span>
                  <span className="text-[9px] text-slate-400">Ross 128 b</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">114 m/s</span>
                  <span className="text-[9px] text-slate-400">Prox Cen b</span>
                </div>
              </div>
            </div>

            {/* Thruster Engine Technology */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <label className="font-semibold text-slate-700 block">Propulsion Technology</label>
              <div className="grid grid-cols-3 gap-1.5 pt-1">
                {[
                  { id: "ion", label: "Gridded Ion (Isp 3000s)" },
                  { id: "electrospray", label: "Electrospray (2000s)" },
                  { id: "coldgas", label: "Cold Gas (70s)" },
                ].map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setThrusterType(t.id as any)}
                    className={`py-1.5 px-1 rounded-lg text-[10px] font-bold border text-center transition-all ${
                      thrusterType === t.id
                        ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                        : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Mission Propulsion Readouts */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">Required 90-Day Δv</div>
                <div className="text-base font-extrabold font-mono text-amber-600 mt-0.5">
                  {dvKms} km/s
                </div>
                <div className="text-[9px] text-slate-400">Trajectory station-keeping</div>
              </div>

              <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">Propellant Mass / Craft</div>
                <div className={`text-base font-extrabold font-mono mt-0.5 ${parseFloat(propMassKg) < 5 ? "text-emerald-700" : "text-rose-600"}`}>
                  {propMassKg} kg
                </div>
                <div className="text-[9px] text-slate-400">
                  {parseFloat(propMassKg) < 5 ? "Highly feasible (<5 kg)" : "Heavy propellant load"}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
