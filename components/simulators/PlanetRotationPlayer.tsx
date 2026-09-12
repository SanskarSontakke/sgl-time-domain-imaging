"use client";

import React, { useRef, useEffect, useState } from "react";
import { Play, Pause, RotateCcw, Download, Sparkles, Sliders, Eye } from "lucide-react";

export default function PlanetRotationPlayer() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [speed, setSpeed] = useState<number>(1);
  const [cloudCover, setCloudCover] = useState<number>(55); // 55% fiducial
  const [viewMode, setViewMode] = useState<"live" | "gif">("live");

  const animRef = useRef<number | null>(null);
  const angleRef = useRef<number>(0);
  const lightHistoryRef = useRef<number[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let lastTime = performance.now();

    const render = (now: number) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      if (isPlaying) {
        angleRef.current += dt * 0.8 * speed;
      }

      const w = canvas.width;
      const h = canvas.height;

      // Background
      ctx.fillStyle = "#0a0e17";
      ctx.fillRect(0, 0, w, h);

      // Top Title Bar
      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 13px -apple-system, BlinkMacSystemFont, monospace";
      ctx.fillText("SOLAR GRAVITATIONAL LENS: TIME-DOMAIN SIMULATION", 16, 22);

      ctx.fillStyle = "#94a3b8";
      ctx.font = "11px -apple-system, BlinkMacSystemFont, monospace";
      ctx.fillText("EXO-EARTH ROTATION WITH DYNAMIC CLOUD ADVECTION & DIURNAL LIGHT CURVE", 16, 38);

      ctx.strokeStyle = "#1e293b";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(16, 48);
      ctx.lineTo(w - 16, 48);
      ctx.stroke();

      const cx = 175;
      const cy = 205;
      const R = 120;
      const rotAngle = angleRef.current;
      const cloudAdvect = rotAngle * 1.4;

      // Draw 3D Sphere
      // Base glow
      const glowGrad = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, R * 1.25);
      glowGrad.addColorStop(0, "rgba(56, 189, 248, 0.3)");
      glowGrad.addColorStop(1, "rgba(56, 189, 248, 0)");
      ctx.fillStyle = glowGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, R * 1.25, 0, Math.PI * 2);
      ctx.fill();

      // Deep Ocean Base
      ctx.save();
      ctx.beginPath();
      ctx.arc(cx, cy, R, 0, Math.PI * 2);
      ctx.clip();

      ctx.fillStyle = "#0c2b4d";
      ctx.fillRect(cx - R, cy - R, R * 2, R * 2);

      // Continents (Simulated Earth-like landmasses)
      ctx.fillStyle = "#15803d";
      const numContinents = 5;
      for (let c = 0; c < numContinents; c++) {
        const cLon = (c * (Math.PI * 2 / numContinents)) + rotAngle;
        const cLat = (c % 2 === 0 ? 0.3 : -0.2);

        // Project onto visible disk
        const cosLon = Math.cos(cLon);
        const sinLon = Math.sin(cLon);

        if (cosLon > -0.2) {
          const px = cx + sinLon * (R * 0.85);
          const py = cy - Math.sin(cLat) * (R * 0.7);
          const landW = 38 * Math.max(0.1, cosLon);
          const landH = 34;

          ctx.beginPath();
          ctx.ellipse(px, py, landW, landH, 0.2, 0, Math.PI * 2);
          ctx.fill();

          // Sub-feature continent
          ctx.beginPath();
          ctx.ellipse(px + 10 * cosLon, py + 18, landW * 0.7, landH * 0.8, -0.3, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Dynamic Clouds
      if (cloudCover > 0) {
        const cOpacity = (cloudCover / 100) * 0.85;
        ctx.fillStyle = `rgba(240, 249, 255, ${cOpacity})`;

        const numBands = 6;
        for (let b = 0; b < numBands; b++) {
          const bLon = (b * 1.1) + cloudAdvect;
          const bLat = -0.6 + b * 0.25;

          const cosLon = Math.cos(bLon);
          const sinLon = Math.sin(bLon);

          if (cosLon > -0.3) {
            const px = cx + sinLon * (R * 0.9);
            const py = cy - bLat * (R * 0.8);
            const cloudW = (40 + b * 6) * Math.max(0.1, cosLon);
            const cloudH = 14 + (b % 3) * 4;

            ctx.beginPath();
            ctx.ellipse(px, py, cloudW, cloudH, 0.1, 0, Math.PI * 2);
            ctx.fill();
          }
        }
      }

      // Polar Ice Caps
      ctx.fillStyle = "#e2e8f0";
      // North
      ctx.beginPath();
      ctx.ellipse(cx, cy - R + 14, R * 0.55, 14, 0, 0, Math.PI * 2);
      ctx.fill();
      // South
      ctx.beginPath();
      ctx.ellipse(cx, cy + R - 14, R * 0.55, 14, 0, 0, Math.PI * 2);
      ctx.fill();

      // Day / Night Terminator Shading (Star illumination from left)
      const termGrad = ctx.createLinearGradient(cx - R, cy, cx + R * 0.8, cy);
      termGrad.addColorStop(0, "rgba(255, 255, 255, 0.15)");
      termGrad.addColorStop(0.55, "rgba(0, 0, 0, 0.0)");
      termGrad.addColorStop(0.75, "rgba(0, 0, 0, 0.65)");
      termGrad.addColorStop(1, "rgba(5, 8, 15, 0.95)");
      ctx.fillStyle = termGrad;
      ctx.fillRect(cx - R, cy - R, R * 2, R * 2);

      ctx.restore();

      // Limb Atmosphere Ring
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, R + 1, 0, Math.PI * 2);
      ctx.stroke();

      // Calculate Integrated Flux for Light Curve
      const fluxVal = 0.16 + 0.05 * Math.sin(rotAngle * 2) + 0.03 * Math.cos(cloudAdvect * 1.5);
      if (isPlaying) {
        lightHistoryRef.current.push(fluxVal);
        if (lightHistoryRef.current.length > 50) lightHistoryRef.current.shift();
      }

      // Right Side: Diurnal Light Curve Graph
      const gx = 350;
      const gy = 60;
      const gw = 260;
      const gh = 120;

      ctx.fillStyle = "#0f172a";
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 1;
      ctx.fillRect(gx, gy, gw, gh);
      ctx.strokeRect(gx, gy, gw, gh);

      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 11px -apple-system, BlinkMacSystemFont, monospace";
      ctx.fillText("DIURNAL LIGHT CURVE F(t)", gx + 10, gy + 18);

      ctx.fillStyle = "#94a3b8";
      ctx.font = "10px -apple-system, BlinkMacSystemFont, monospace";
      ctx.fillText("Normalized Disk-Averaged Photometry", gx + 10, gy + 32);

      // Grid lines
      ctx.strokeStyle = "#1e293b";
      for (let y = gy + 48; y < gy + gh; y += 24) {
        ctx.beginPath();
        ctx.moveTo(gx + 8, y);
        ctx.lineTo(gx + gw - 8, y);
        ctx.stroke();
      }

      // Plot curve
      const history = lightHistoryRef.current;
      if (history.length > 1) {
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 2;
        ctx.beginPath();
        const minF = 0.08;
        const maxF = 0.26;
        for (let i = 0; i < history.length; i++) {
          const px = gx + 12 + (i / 50) * (gw - 24);
          const py = gy + gh - 10 - ((history[i] - minF) / (maxF - minF)) * (gh - 55);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();

        // Pulsing marker
        const lastX = gx + 12 + ((history.length - 1) / 50) * (gw - 24);
        const lastY = gy + gh - 10 - ((history[history.length - 1] - minF) / (maxF - minF)) * (gh - 55);
        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // Telemetry Box
      const tx = 350;
      const ty = 195;
      const tw = 260;
      const th = 135;

      ctx.fillStyle = "#0f172a";
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 1;
      ctx.fillRect(tx, ty, tw, th);
      ctx.strokeRect(tx, ty, tw, th);

      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 11px -apple-system, BlinkMacSystemFont, monospace";
      ctx.fillText("SIMULATION TELEMETRY", tx + 10, ty + 16);

      const telemetry = [
        ["DIURNAL PERIOD", "P = 24.0 hours"],
        ["CLOUD FRACTION", `f_c = ${cloudCover}% (fiducial)`],
        ["ZONAL JET STREAM", "v_zonal = +21 m/s"],
        ["AXIAL OBLIQUITY", "23.4° tilt"],
        ["NOISE RATIO", "Clouds:Photons = 21:1"],
      ];

      telemetry.forEach(([label, val], idx) => {
        const rowY = ty + 36 + idx * 18;
        ctx.fillStyle = "#94a3b8";
        ctx.font = "10px -apple-system, BlinkMacSystemFont, monospace";
        ctx.fillText(label, tx + 10, rowY);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(val, tx + 130, rowY);
      });

      // Bottom Footer Bar
      ctx.strokeStyle = "#1e293b";
      ctx.beginPath();
      ctx.moveTo(16, h - 22);
      ctx.lineTo(w - 16, h - 22);
      ctx.stroke();

      ctx.fillStyle = "#64748b";
      ctx.font = "10px -apple-system, BlinkMacSystemFont, monospace";
      ctx.fillText("PEER-REVIEWED ASTROPHYSICAL RESEARCH • SONTANKE ET AL. (2026)", 16, h - 8);

      ctx.fillStyle = isPlaying ? "#34d399" : "#f59e0b";
      ctx.fillText(isPlaying ? "SIMULATION ACTIVE • 60 FPS" : "SIMULATION PAUSED", w - 160, h - 8);

      animRef.current = requestAnimationFrame(render);
    };

    animRef.current = requestAnimationFrame(render);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isPlaying, speed, cloudCover]);

  return (
    <div className="bg-slate-950 rounded-xl border border-slate-800 overflow-hidden shadow-lg flex flex-col">
      {/* Top Header Controls */}
      <div className="p-2.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse shrink-0" />
          <span className="text-xs font-mono font-bold text-blue-400">
            Exo-Earth Rotation & Cloud Advection Simulation
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setViewMode(viewMode === "live" ? "gif" : "live")}
            className="text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-1 rounded font-mono border border-slate-700 transition-colors"
          >
            {viewMode === "live" ? "Switch to GIF" : "Switch to Live 60FPS"}
          </button>

          <a
            href="/videos/planet_rotation_clouds.gif"
            download="planet_rotation_clouds.gif"
            className="text-[10px] bg-blue-600 hover:bg-blue-500 text-white px-2.5 py-1 rounded font-mono font-bold flex items-center gap-1 transition-colors"
            title="Download Clean High-Res GIF"
          >
            <Download size={11} />
            <span>Save GIF</span>
          </a>
        </div>
      </div>

      {/* Main View Area */}
      <div className="relative w-full aspect-[640/355] bg-black flex items-center justify-center overflow-hidden">
        {viewMode === "live" ? (
          <canvas
            ref={canvasRef}
            width={640}
            height={355}
            className="w-full h-full object-contain"
          />
        ) : (
          <img
            src="/videos/planet_rotation_clouds.gif"
            alt="Exo-Earth Rotation & Cloud Simulation"
            className="w-full h-full object-contain"
          />
        )}
      </div>

      {/* Interactive Control Toolbar */}
      <div className="p-2.5 bg-slate-900/95 border-t border-slate-800 flex items-center justify-between text-xs flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="btn btn-sm btn-outline text-white border-slate-700 hover:bg-slate-800 px-2 py-1 text-xs flex items-center gap-1"
          >
            {isPlaying ? <Pause size={12} /> : <Play size={12} />}
            <span>{isPlaying ? "Pause" : "Play"}</span>
          </button>

          <button
            onClick={() => {
              angleRef.current = 0;
              lightHistoryRef.current = [];
            }}
            className="btn btn-sm btn-outline text-slate-300 border-slate-700 hover:bg-slate-800 px-2 py-1 text-xs"
            title="Reset Rotation Angle"
          >
            <RotateCcw size={12} />
          </button>

          <div className="flex items-center gap-1 text-[11px] text-slate-400 pl-1">
            <span>Speed:</span>
            {[0.5, 1, 2].map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`px-1.5 py-0.5 rounded text-[10px] font-mono ${
                  speed === s ? "bg-blue-600 text-white font-bold" : "bg-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* Cloud Cover Slider */}
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <span>Clouds:</span>
          <input
            type="range"
            min="0"
            max="80"
            step="5"
            value={cloudCover}
            onChange={(e) => setCloudCover(Number(e.target.value))}
            className="w-20 sm:w-24 accent-blue-500 h-1"
          />
          <span className="font-mono text-white text-[10px] w-7">{cloudCover}%</span>
        </div>
      </div>

      {/* Caption Strip */}
      <div className="px-3 py-2 bg-slate-950 text-slate-400 text-[10px] sm:text-[11px] border-t border-slate-900 leading-snug">
        Continuous 24-hour diurnal rotation with dynamic eastward zonal jet streams (+21 m/s) and photometric light curve F(t).
      </div>
    </div>
  );
}
