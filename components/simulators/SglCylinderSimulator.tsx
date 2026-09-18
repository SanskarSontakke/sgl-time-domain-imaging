"use client";

import React, { useRef, useEffect, useState } from "react";
import { Play, Pause, RotateCcw, Eye, ShieldCheck, Zap, Info } from "lucide-react";

export default function SglCylinderSimulator() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(true);
  const [mode, setMode] = useState<"fleet" | "single">("fleet");
  const [rotSpeed, setRotSpeed] = useState(1.0);
  const [cloudSpeed, setCloudSpeed] = useState(1.5);
  const [activeSlot, setActiveSlot] = useState(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let time = 0;

    // Fixed continental coordinates for a realistic mini-planet map
    const continents = [
      { x: 0.25, y: 0.45, r: 0.18, shape: [[0, -0.15], [0.12, -0.05], [0.08, 0.15], [-0.1, 0.12], [-0.14, -0.08]] },
      { x: 0.65, y: 0.35, r: 0.22, shape: [[0, -0.18], [0.15, -0.1], [0.18, 0.12], [-0.05, 0.2], [-0.16, 0.05]] },
      { x: 0.75, y: 0.65, r: 0.12, shape: [[0, -0.08], [0.1, -0.02], [0.06, 0.1], [-0.08, 0.06]] },
    ];

    const render = () => {
      if (isPlaying) {
        time += 0.015;
      }

      const w = canvas.width;
      const h = canvas.height;

      // Background clean slate
      ctx.fillStyle = "#f8fafc";
      ctx.fillRect(0, 0, w, h);

      // Section 1: The Distant Rotating Exo-Earth (Left third)
      const cx1 = w * 0.22;
      const cy1 = h * 0.5;
      const r1 = Math.min(w, h) * 0.28;

      ctx.save();
      ctx.beginPath();
      ctx.arc(cx1, cy1, r1, 0, Math.PI * 2);
      ctx.clip();

      // Deep ocean blue
      const oceanGrad = ctx.createRadialGradient(cx1 - r1 * 0.3, cy1 - r1 * 0.3, 10, cx1, cy1, r1);
      oceanGrad.addColorStop(0, "#1d4ed8");
      oceanGrad.addColorStop(0.7, "#1e40af");
      oceanGrad.addColorStop(1, "#0f172a");
      ctx.fillStyle = oceanGrad;
      ctx.fillRect(cx1 - r1, cy1 - r1, r1 * 2, r1 * 2);

      // Rotating continents
      const planetPhase = (time * rotSpeed * 0.2) % 1;
      continents.forEach((cont) => {
        for (let copy = -1; copy <= 1; copy++) {
          const px = cx1 + ((cont.x + planetPhase + copy) % 1 - 0.5) * r1 * 2;
          const py = cy1 + (cont.y - 0.5) * r1 * 1.8;

          // Spherical projection factor
          const dx = px - cx1;
          const dy = py - cy1;
          if (dx * dx + dy * dy < r1 * r1) {
            ctx.fillStyle = "#15803d"; // Vegetation green
            ctx.beginPath();
            ctx.moveTo(px + cont.shape[0][0] * r1, py + cont.shape[0][1] * r1);
            for (let i = 1; i < cont.shape.length; i++) {
              ctx.lineTo(px + cont.shape[i][0] * r1, py + cont.shape[i][1] * r1);
            }
            ctx.closePath();
            ctx.fill();
          }
        }
      });

      // Advecting clouds (white semi-transparent swirling bands)
      const cloudPhase = (time * (rotSpeed * 0.2 + cloudSpeed * 0.05)) % 1;
      ctx.fillStyle = "rgba(255, 255, 255, 0.65)";
      for (let i = 0; i < 6; i++) {
        const cpy = cy1 + ((i / 6) - 0.5) * r1 * 1.6;
        const cpx = cx1 + (((i * 0.3 + cloudPhase) % 1) - 0.5) * r1 * 2;
        ctx.beginPath();
        ctx.ellipse(cpx, cpy, r1 * 0.35, r1 * 0.08, 0.1, 0, Math.PI * 2);
        ctx.fill();
      }

      // Day/Night terminator shading
      const shadowGrad = ctx.createLinearGradient(cx1 - r1, cy1, cx1 + r1, cy1);
      shadowGrad.addColorStop(0, "rgba(0, 0, 0, 0)");
      shadowGrad.addColorStop(0.65, "rgba(0, 0, 0, 0.05)");
      shadowGrad.addColorStop(1, "rgba(2, 6, 23, 0.75)");
      ctx.fillStyle = shadowGrad;
      ctx.fillRect(cx1 - r1, cy1 - r1, r1 * 2, r1 * 2);

      ctx.restore();

      // Atmospheric limb glow
      ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.arc(cx1, cy1, r1, 0, Math.PI * 2);
      ctx.stroke();

      // Title & Annotation for Left side
      ctx.fillStyle = "#0f172a";
      ctx.font = "bold 13px sans-serif";
      ctx.fillText("Exo-Earth at 30 pc", cx1 - 60, cy1 - r1 - 14);
      ctx.font = "11px sans-serif";
      ctx.fillStyle = "#64748b";
      ctx.fillText("Rotating surface + evolving clouds", cx1 - 90, cy1 + r1 + 18);

      // Section 2: Light Rays passing Sun (Middle connector)
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = "#cbd5e1";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx1 + r1, cy1 - r1 * 0.4);
      ctx.bezierCurveTo(w * 0.45, cy1 - 20, w * 0.48, cy1 - 10, w * 0.65, cy1 - 90);
      ctx.moveTo(cx1 + r1, cy1 + r1 * 0.4);
      ctx.bezierCurveTo(w * 0.45, cy1 + 20, w * 0.48, cy1 + 10, w * 0.65, cy1 + 90);
      ctx.stroke();
      ctx.restore();

      // Solar Gravity Lens label in middle
      ctx.fillStyle = "#d97706";
      ctx.font = "bold 11px sans-serif";
      ctx.fillText("☀️ Solar Gravity Lens", w * 0.42, cy1 - 8);
      ctx.fillStyle = "#64748b";
      ctx.font = "10px sans-serif";
      ctx.fillText("z ≥ 547.5 AU", w * 0.44, cy1 + 10);

      // Section 3: SGL 1.3-km Image Cylinder in the Focal Plane (Right side)
      const cx2 = w * 0.76;
      const cy2 = h * 0.5;
      const r2 = Math.min(w, h) * 0.32;

      // Outer cylinder bounding circle
      ctx.save();
      ctx.fillStyle = "#ffffff";
      ctx.strokeStyle = "#e2e8f0";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx2, cy2, r2, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();

      // Grid of 64x64 or 16x16 scanning slots
      const nSlots = 8;
      const slotSize = (r2 * 1.6) / nSlots;
      const startX = cx2 - (r2 * 0.8);
      const startY = cy2 - (r2 * 0.8);

      ctx.strokeStyle = "#f1f5f9";
      ctx.lineWidth = 1;
      for (let i = 0; i <= nSlots; i++) {
        ctx.beginPath();
        ctx.moveTo(startX + i * slotSize, startY);
        ctx.lineTo(startX + i * slotSize, startY + nSlots * slotSize);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(startX, startY + i * slotSize);
        ctx.lineTo(startX + nSlots * slotSize, startY + i * slotSize);
        ctx.stroke();
      }

      // Einstein ring glow inside cylinder
      const ringGrad = ctx.createRadialGradient(cx2, cy2, r2 * 0.6, cx2, cy2, r2);
      ringGrad.addColorStop(0, "rgba(2, 132, 199, 0.05)");
      ringGrad.addColorStop(0.7, "rgba(2, 132, 199, 0.2)");
      ringGrad.addColorStop(1, "rgba(2, 132, 199, 0.0)");
      ctx.fillStyle = ringGrad;
      ctx.beginPath();
      ctx.arc(cx2, cy2, r2, 0, Math.PI * 2);
      ctx.fill();

      // Spacecraft positioning
      if (mode === "single") {
        // Single spacecraft raster scan
        const totalSteps = nSlots * nSlots;
        const currentStep = Math.floor((time * 8) % totalSteps);
        const row = Math.floor(currentStep / nSlots);
        const col = row % 2 === 0 ? (currentStep % nSlots) : (nSlots - 1 - (currentStep % nSlots));
        const scX = startX + (col + 0.5) * slotSize;
        const scY = startY + (row + 0.5) * slotSize;

        // Trace of recent path
        ctx.fillStyle = "rgba(220, 38, 38, 0.15)";
        for (let s = 0; s < currentStep; s++) {
          const r_s = Math.floor(s / nSlots);
          const c_s = r_s % 2 === 0 ? (s % nSlots) : (nSlots - 1 - (s % nSlots));
          ctx.fillRect(startX + c_s * slotSize, startY + r_s * slotSize, slotSize, slotSize);
        }

        // Active craft dot
        ctx.fillStyle = "#dc2626";
        ctx.beginPath();
        ctx.arc(scX, scY, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = "#dc2626";
        ctx.font = "bold 10px monospace";
        ctx.fillText("1 CRAFT (SLOW SCAN)", cx2 - 60, cy2 + r2 + 20);
        ctx.fillStyle = "#64748b";
        ctx.font = "10px sans-serif";
        ctx.fillText("Temporal aliasing: Clouds change mid-scan!", cx2 - 100, cy2 + r2 + 34);
      } else {
        // 16-Craft Fleet Concurrent Slots
        const nCrafts = 16;
        const pulse = Math.sin(time * 3) * 0.15 + 0.85;

        // Highlight concurrent slots
        for (let i = 0; i < nCrafts; i++) {
          const col = (i * 2 + Math.floor(time * 2)) % nSlots;
          const row = (Math.floor(i / 2) + Math.floor(time * 0.5)) % nSlots;
          const scX = startX + (col + 0.5) * slotSize;
          const scY = startY + (row + 0.5) * slotSize;

          ctx.fillStyle = "rgba(2, 132, 199, 0.18)";
          ctx.fillRect(startX + col * slotSize, startY + row * slotSize, slotSize, slotSize);

          // Craft aperture dot
          ctx.fillStyle = "#0284c7";
          ctx.beginPath();
          ctx.arc(scX, scY, 5 * pulse, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }

        ctx.fillStyle = "#0284c7";
        ctx.font = "bold 10px monospace";
        ctx.fillText("16-CRAFT FLEET CONCURRENT SLOTS", cx2 - 95, cy2 + r2 + 20);
        ctx.fillStyle = "#059669";
        ctx.font = "10px sans-serif";
        ctx.fillText("Common-mode cloud variations cancelled via P⊥!", cx2 - 115, cy2 + r2 + 34);
      }

      ctx.restore();

      // Focal Plane Header
      ctx.fillStyle = "#0f172a";
      ctx.font = "bold 13px sans-serif";
      ctx.fillText("1.3 km Image Cylinder at 650 AU", cx2 - 90, cy2 - r2 - 14);

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [isPlaying, mode, rotSpeed, cloudSpeed]);

  return (
    <div className="card simulator-card">
      <div className="card-header flex justify-between items-center flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-primary flex items-center gap-1">
            <Zap size={14} />
            <span>Interactive Simulator</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            SGL Image Cylinder & Spacecraft Scan Dynamics
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setMode(mode === "fleet" ? "single" : "fleet")}
            className={`btn btn-sm ${mode === "fleet" ? "btn-primary" : "btn-outline"}`}
          >
            {mode === "fleet" ? "16-Craft Fleet Active" : "Single Craft Active"}
          </button>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="btn btn-sm btn-outline flex items-center gap-1"
          >
            {isPlaying ? <Pause size={14} /> : <Play size={14} />}
            <span>{isPlaying ? "Pause" : "Play"}</span>
          </button>
        </div>
      </div>

      <div className="card-body">
        <div className="canvas-container relative rounded-lg border border-slate-200 overflow-hidden bg-slate-50">
          <canvas
            ref={canvasRef}
            width={840}
            height={360}
            className="w-full h-auto block"
          />
        </div>

        {/* Controls and Physical Legend */}
        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 border-t border-slate-100 text-sm">
          <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center text-xs mb-1">
                <span className="font-semibold text-slate-700">Planet Rotation Speed:</span>
                <span className="font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">{rotSpeed.toFixed(1)}×</span>
              </div>
              <input
                type="range"
                min="0.2"
                max="3.0"
                step="0.1"
                value={rotSpeed}
                onChange={(e) => setRotSpeed(parseFloat(e.target.value))}
                className="w-full range-slider"
              />
            </div>
            <span className="text-[10px] text-slate-500 font-mono">Earth-like: ~24 hr diurnal period</span>
          </div>

          <div className="bg-slate-50 p-3 rounded-xl border border-slate-200 space-y-1.5 flex flex-col justify-between">
            <div>
              <div className="flex justify-between items-center text-xs mb-1">
                <span className="font-semibold text-slate-700">Cloud Advection / Evolution:</span>
                <span className="font-mono font-bold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">{cloudSpeed.toFixed(1)}×</span>
              </div>
              <input
                type="range"
                min="0.2"
                max="4.0"
                step="0.2"
                value={cloudSpeed}
                onChange={(e) => setCloudSpeed(parseFloat(e.target.value))}
                className="w-full range-slider"
              />
            </div>
            <span className="text-[10px] text-slate-500 font-mono">Timescale τ ≈ 3.5 days advection</span>
          </div>

          <div className="bg-slate-50 p-2.5 rounded border border-slate-200 text-xs">
            <div className="font-semibold text-slate-700 flex items-center gap-1 mb-1">
              <Info size={13} className="text-sky-600" />
              <span>Key Observation Principle</span>
            </div>
            <p className="text-slate-600 leading-snug">
              The focal image of an exo-Earth is compressed into a ~1.3 km cylinder at 650 AU.
              A single spacecraft takes months to raster scan it, during which clouds scramble the surface.
              Our 16-craft fleet with slot deflation cancels cloud fluctuations in real time.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
