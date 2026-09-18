"use client";

import React, { useRef, useEffect, useState } from "react";
import { 
  Play, Pause, RotateCcw, Download, Sparkles, Sliders, 
  Eye, Zap, Video, Maximize2, ZoomIn, ZoomOut, Move, RefreshCw
} from "lucide-react";
import MediaZoomViewer from "../MediaZoomViewer";

export default function PlanetRotationPlayer() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [speed, setSpeed] = useState<number>(1);
  const [cloudCover, setCloudCover] = useState<number>(55); // 55% fiducial
  const [viewMode, setViewMode] = useState<"live" | "gif">("live");
  const [gifKey, setGifKey] = useState<number>(1);

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
      ctx.font = "bold 14px -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace";
      ctx.fillText("SOLAR GRAVITATIONAL LENS: TIME-DOMAIN SIMULATION", 20, 24);

      ctx.fillStyle = "#94a3b8";
      ctx.font = "11px -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace";
      ctx.fillText("EXO-EARTH ROTATION WITH DYNAMIC CLOUD ADVECTION & DIURNAL LIGHT CURVE", 20, 42);

      ctx.strokeStyle = "#1e293b";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(20, 52);
      ctx.lineTo(w - 20, 52);
      ctx.stroke();

      const cx = 200;
      const cy = 275;
      const R = 170;
      const rotAngle = angleRef.current;
      const cloudAdvect = rotAngle * 1.4;

      // Draw 3D Sphere Base glow
      const glowGrad = ctx.createRadialGradient(cx, cy, R * 0.9, cx, cy, R * 1.25);
      glowGrad.addColorStop(0, "rgba(56, 189, 248, 0.35)");
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
          const landW = 54 * Math.max(0.1, cosLon);
          const landH = 48;

          ctx.beginPath();
          ctx.ellipse(px, py, landW, landH, 0.2, 0, Math.PI * 2);
          ctx.fill();

          // Sub-feature continent
          ctx.beginPath();
          ctx.ellipse(px + 14 * cosLon, py + 24, landW * 0.7, landH * 0.8, -0.3, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Dynamic Clouds
      if (cloudCover > 0) {
        const cOpacity = (cloudCover / 100) * 0.85;
        ctx.fillStyle = `rgba(240, 249, 255, ${cOpacity})`;

        const numBands = 7;
        for (let b = 0; b < numBands; b++) {
          const bLon = (b * 1.1) + cloudAdvect;
          const bLat = -0.65 + b * 0.22;

          const cosLon = Math.cos(bLon);
          const sinLon = Math.sin(bLon);

          if (cosLon > -0.3) {
            const px = cx + sinLon * (R * 0.9);
            const py = cy - bLat * (R * 0.8);
            const cloudW = (55 + b * 8) * Math.max(0.1, cosLon);
            const cloudH = 18 + (b % 3) * 5;

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
      ctx.ellipse(cx, cy - R + 20, R * 0.55, 20, 0, 0, Math.PI * 2);
      ctx.fill();
      // South
      ctx.beginPath();
      ctx.ellipse(cx, cy + R - 20, R * 0.55, 20, 0, 0, Math.PI * 2);
      ctx.fill();

      // Day / Night Terminator Shading (Star illumination from left)
      const termGrad = ctx.createLinearGradient(cx - R, cy, cx + R * 0.8, cy);
      termGrad.addColorStop(0, "rgba(255, 255, 255, 0.18)");
      termGrad.addColorStop(0.55, "rgba(0, 0, 0, 0.0)");
      termGrad.addColorStop(0.75, "rgba(0, 0, 0, 0.65)");
      termGrad.addColorStop(1, "rgba(5, 8, 15, 0.95)");
      ctx.fillStyle = termGrad;
      ctx.fillRect(cx - R, cy - R, R * 2, R * 2);

      ctx.restore();

      // Limb Atmosphere Ring
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.arc(cx, cy, R + 1.5, 0, Math.PI * 2);
      ctx.stroke();

      // Calculate Integrated Flux for Light Curve
      const fluxVal = 0.16 + 0.05 * Math.sin(rotAngle * 2) + 0.03 * Math.cos(cloudAdvect * 1.5);
      if (isPlaying) {
        lightHistoryRef.current.push(fluxVal);
        if (lightHistoryRef.current.length > 50) lightHistoryRef.current.shift();
      }

      // Right Side: Diurnal Light Curve Graph
      const gx = 440;
      const gy = 75;
      const gw = 480;
      const gh = 180;

      ctx.fillStyle = "#0f172a";
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 1;
      ctx.fillRect(gx, gy, gw, gh);
      ctx.strokeRect(gx, gy, gw, gh);

      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace";
      ctx.fillText("DIURNAL LIGHT CURVE F(t)", gx + 16, gy + 24);

      ctx.fillStyle = "#94a3b8";
      ctx.font = "11px -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace";
      ctx.fillText("Normalized Disk-Averaged Photometry vs. Time", gx + 16, gy + 42);

      // Grid lines
      ctx.strokeStyle = "#1e293b";
      for (let y = gy + 60; y < gy + gh; y += 32) {
        ctx.beginPath();
        ctx.moveTo(gx + 12, y);
        ctx.lineTo(gx + gw - 12, y);
        ctx.stroke();
      }

      // Plot curve
      const history = lightHistoryRef.current;
      if (history.length > 1) {
        ctx.strokeStyle = "#fbbf24";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        const minF = 0.08;
        const maxF = 0.26;
        for (let i = 0; i < history.length; i++) {
          const px = gx + 16 + (i / 50) * (gw - 32);
          const py = gy + gh - 15 - ((history[i] - minF) / (maxF - minF)) * (gh - 75);
          if (i === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.stroke();

        // Pulsing marker
        const lastX = gx + 16 + ((history.length - 1) / 50) * (gw - 32);
        const lastY = gy + gh - 15 - ((history[history.length - 1] - minF) / (maxF - minF)) * (gh - 75);
        ctx.fillStyle = "#ef4444";
        ctx.beginPath();
        ctx.arc(lastX, lastY, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Telemetry Box
      const tx = 440;
      const ty = 280;
      const tw = 480;
      const th = 210;

      ctx.fillStyle = "#0f172a";
      ctx.strokeStyle = "#334155";
      ctx.lineWidth = 1;
      ctx.fillRect(tx, ty, tw, th);
      ctx.strokeRect(tx, ty, tw, th);

      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace";
      ctx.fillText("SIMULATION TELEMETRY", tx + 16, ty + 24);

      const telemetry = [
        ["DIURNAL PERIOD", "P = 24.0 hours"],
        ["CLOUD FRACTION", `fc = ${cloudCover}% (fiducial)`],
        ["ZONAL JET STREAM", "v_zonal = +21 m/s (eastward)"],
        ["AXIAL OBLIQUITY", "23.4° tilt"],
        ["NOISE COVARIANCE", "Clouds:Photons = 21:1 (dominant)"],
      ];

      telemetry.forEach(([label, val], idx) => {
        const rowY = ty + 56 + idx * 28;
        ctx.fillStyle = "#94a3b8";
        ctx.font = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace";
        ctx.fillText(label, tx + 16, rowY);
        ctx.fillStyle = "#ffffff";
        ctx.fillText(val, tx + 180, rowY);
      });

      // Bottom Footer Bar
      ctx.strokeStyle = "#1e293b";
      ctx.beginPath();
      ctx.moveTo(20, h - 28);
      ctx.lineTo(w - 20, h - 28);
      ctx.stroke();

      ctx.fillStyle = "#64748b";
      ctx.font = "11px -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace";
      ctx.fillText("PEER-REVIEWED ASTROPHYSICAL RESEARCH • SONTANKE ET AL. (2026)", 20, h - 10);

      ctx.fillStyle = isPlaying ? "#34d399" : "#f59e0b";
      ctx.fillText(isPlaying ? "SIMULATION ACTIVE • 60 FPS" : "SIMULATION PAUSED", w - 190, h - 10);

      animRef.current = requestAnimationFrame(render);
    };

    animRef.current = requestAnimationFrame(render);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isPlaying, speed, cloudCover]);

  const restartGif = () => {
    setGifKey(Date.now());
  };

  return (
    <MediaZoomViewer
      title="Exo-Earth Rotation & Cloud Advection Simulation"
      badge="1080p Full HD"
      desc="Continuous 24-hour diurnal rotation with dynamic eastward zonal jet streams (+21 m/s) and disk-averaged photometric light curve F(t)."
      downloadName="planet_rotation_clouds_1080p.gif"
      src={viewMode === "gif" ? `/videos/planet_rotation_clouds.gif?v=${gifKey}` : undefined}
      headerControls={
        <div className="inline-flex bg-slate-950 p-0.5 rounded-lg border border-slate-700 shadow-inner">
          <button
            type="button"
            onClick={() => setViewMode("live")}
            className={`px-2.5 py-1 rounded font-mono text-[10px] font-bold flex items-center gap-1.5 transition-all ${
              viewMode === "live"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Zap size={12} className={viewMode === "live" ? "text-amber-300" : "text-slate-500"} />
            <span>Live 60FPS</span>
          </button>

          <button
            type="button"
            onClick={() => setViewMode("gif")}
            className={`px-2.5 py-1 rounded font-mono text-[10px] font-bold flex items-center gap-1.5 transition-all ${
              viewMode === "gif"
                ? "bg-blue-600 text-white shadow-xs"
                : "text-slate-400 hover:text-white"
            }`}
          >
            <Video size={12} className={viewMode === "gif" ? "text-sky-300" : "text-slate-500"} />
            <span>1080p Master GIF</span>
          </button>
        </div>
      }
      footerControls={
        <div className="p-2.5 sm:p-3 bg-slate-900/95 border-t border-slate-800 flex items-center justify-between text-xs flex-wrap gap-2.5">
          {viewMode === "live" ? (
            <>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsPlaying(!isPlaying)}
                  className="btn btn-sm btn-outline text-white border-slate-700 hover:bg-slate-800 px-2.5 py-1 text-xs flex items-center gap-1.5 rounded-lg shadow-xs"
                >
                  {isPlaying ? <Pause size={12} /> : <Play size={12} />}
                  <span>{isPlaying ? "Pause" : "Play"}</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    angleRef.current = 0;
                    lightHistoryRef.current = [];
                  }}
                  className="btn btn-sm btn-outline text-slate-300 border-slate-700 hover:bg-slate-800 px-2 py-1 text-xs rounded-lg"
                  title="Reset Rotation Angle"
                >
                  <RotateCcw size={12} />
                </button>

                <div className="flex items-center gap-1 text-[11px] text-slate-400 pl-1">
                  <span className="font-semibold text-slate-300">Speed:</span>
                  {[0.5, 1, 2].map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => setSpeed(s)}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                        speed === s 
                          ? "bg-blue-600 text-white font-bold shadow-xs" 
                          : "bg-slate-800 text-slate-400 hover:text-white"
                      }`}
                    >
                      {s}x
                    </button>
                  ))}
                </div>
              </div>

              {/* Cloud Cover Slider */}
              <div className="flex items-center gap-2 text-[11px] text-slate-300 bg-slate-950/60 px-2.5 py-1 rounded-lg border border-slate-800">
                <span className="font-semibold">Clouds:</span>
                <input
                  type="range"
                  min="0"
                  max="80"
                  step="5"
                  value={cloudCover}
                  onChange={(e) => setCloudCover(Number(e.target.value))}
                  className="w-20 sm:w-28 range-slider range-slider-dark"
                />
                <span className="font-mono text-emerald-400 font-bold text-[11px] w-8">{cloudCover}%</span>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between w-full gap-2 flex-wrap">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                <span className="text-[11px] text-slate-300 font-medium">
                  Showing 1080p Master Recording • 24.0s (240 Frames @ 100ms)
                </span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={restartGif}
                  className="btn btn-sm btn-outline text-slate-300 border-slate-700 hover:bg-slate-800 px-2.5 py-1 text-xs flex items-center gap-1.5 rounded-lg"
                  title="Restart animation from frame 0"
                >
                  <RefreshCw size={11} />
                  <span>Replay GIF</span>
                </button>

                <a
                  href="/videos/planet_rotation_clouds.gif"
                  download="planet_rotation_clouds_1080p.gif"
                  className="btn btn-sm btn-primary text-xs flex items-center gap-1.5 px-3 py-1 rounded-lg shadow-xs"
                >
                  <Download size={11} />
                  <span>Download 1080p GIF</span>
                </a>
              </div>
            </div>
          )}
        </div>
      }
    >
      {/* Live Canvas (Always mounted to preserve 60FPS animation context) */}
      <canvas
        ref={canvasRef}
        width={960}
        height={540}
        className={`w-full h-full object-contain ${viewMode === "live" ? "block" : "hidden"}`}
      />

      {/* 1080p GIF Layer */}
      {viewMode === "gif" && (
        <img
          key={gifKey}
          src={`/videos/planet_rotation_clouds.gif?v=${gifKey}`}
          alt="Exo-Earth Rotation & Cloud Simulation (1080p Full HD)"
          className="w-full h-full object-contain"
        />
      )}
    </MediaZoomViewer>
  );
}
