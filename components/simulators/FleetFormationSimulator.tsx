"use client";

import React, { useState, useRef, useEffect } from "react";
import { Play, Pause, Radio, AlertTriangle } from "lucide-react";
import LatexMath from "../LatexMath";
// Δv and image-plane velocities come from the archived table (src/targets.py),
// so this simulator cannot drift away from the manuscript's numbers.
import TARGET_ARCHIVE from "../../results/targets.json";

type FormationMode = "grid" | "hex" | "lissajous";

interface Row {
  name: string;
  Dimg_km: number;
  v_img_ms: number;
  dv90_face_on_kms: number;
  dv90_edge_on_kms: number;
  note: string;
}

const ROWS: Row[] = TARGET_ARCHIVE.targets as unknown as Row[];

// Fiducial geometry (Section 3.3 of the manuscript): N_sc = 16 craft sample 16
// raster positions at once on ADJACENT boustrophedon tracks, with transverse
// separations of ~80--300 m. The craft therefore occupy a small cluster inside
// the 1.338 km image cylinder -- they are not spread across it, and the
// formation is never a "1.3 km formation".
const CYL_DIAM_KM = 1.338;
const SPAN_M_MAX = 300;

// Illustrative only: a bare Tsiolkovsky budget at an assumed 18 kg dry mass.
// The manuscript computes the Δv *requirement* and explicitly does not size a
// propulsion system, so everything derived below Δv is labelled as outside the
// paper's scope.
const DRY_MASS_KG = 18.0;
const ISP_MAP = { ion: 3000, electrospray: 2000, coldgas: 70 } as const;
const G0 = 9.80665;

export default function FleetFormationSimulator() {
  const [formation, setFormation] = useState<FormationMode>("grid");
  const [targetName, setTargetName] = useState<string>("Ross 128 b");
  const [thrusterType, setThrusterType] = useState<keyof typeof ISP_MAP>("ion");
  const [isPlaying, setIsPlaying] = useState<boolean>(true);

  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const row = ROWS.find((t) => t.name === targetName) || ROWS[0];
  const isp = ISP_MAP[thrusterType];
  const dvMs = row.dv90_face_on_kms * 1000;
  const propMassKg = (DRY_MASS_KG * (Math.exp(dvMs / (G0 * isp)) - 1)).toFixed(2);

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
      // Fleet footprint drawn to scale: SPAN_M_MAX of the 1338 m cylinder.
      const span = radius * (SPAN_M_MAX / 1000 / CYL_DIAM_KM) * 2;

      // Deep space background
      ctx.fillStyle = "#090d16";
      ctx.fillRect(0, 0, w, h);

      // Stars in background
      ctx.fillStyle = "rgba(255, 255, 255, 0.4)";
      for (let i = 0; i < 30; i++) {
        const sx = (i * 73 + 12) % w;
        const sy = (i * 127 + 45) % h;
        ctx.fillRect(sx, sy, 1.2, 1.2);
      }

      // Image cylinder boundary (D_img for an Earth-radius planet at 650 AU)
      ctx.strokeStyle = "rgba(56, 189, 248, 0.25)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.setLineDash([]);

      const cylGrad = ctx.createRadialGradient(cx, cy, radius * 0.7, cx, cy, radius);
      cylGrad.addColorStop(0, "rgba(2, 132, 199, 0.02)");
      cylGrad.addColorStop(1, "rgba(2, 132, 199, 0.08)");
      ctx.fillStyle = cylGrad;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.fill();

      // Focal-line axis
      ctx.strokeStyle = "#ef4444";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - 10, cy);
      ctx.lineTo(cx + 10, cy);
      ctx.moveTo(cx, cy - 10);
      ctx.lineTo(cx, cy + 10);
      ctx.stroke();

      // 16 spacecraft, clustered inside the cylinder at the true scale
      const nCrafts = 16;
      const craftCoords: { x: number; y: number }[] = [];

      for (let i = 0; i < nCrafts; i++) {
        let x = cx;
        let y = cy;

        if (formation === "grid") {
          const rowIdx = Math.floor(i / 4);
          const col = i % 4;
          const spacing = span / 3;
          x = cx + (col - 1.5) * spacing + Math.sin(time + i) * 2;
          y = cy + (rowIdx - 1.5) * spacing + Math.cos(time + i) * 2;
        } else if (formation === "hex") {
          if (i === 0) {
            x = cx;
            y = cy;
          } else if (i <= 6) {
            const angle = (i / 6) * Math.PI * 2 + time * 0.2;
            x = cx + Math.cos(angle) * (span * 0.45);
            y = cy + Math.sin(angle) * (span * 0.45);
          } else {
            const angle = ((i - 6) / 9) * Math.PI * 2 - time * 0.15;
            x = cx + Math.cos(angle) * (span * 0.82);
            y = cy + Math.sin(angle) * (span * 0.82);
          }
        } else {
          const phase = (i / nCrafts) * Math.PI * 2;
          x = cx + Math.sin(time * 0.6 + phase) * (span * 0.85);
          y = cy + Math.cos(time * 0.9 + phase * 2) * (span * 0.85);
        }

        craftCoords.push({ x, y });
      }

      // Inter-craft metrology links (5 s budget per dwell, Section 3.3)
      ctx.strokeStyle = "rgba(16, 185, 129, 0.35)";
      ctx.lineWidth = 1;
      for (let i = 0; i < nCrafts; i++) {
        const next = (i + 1) % nCrafts;
        ctx.beginPath();
        ctx.moveTo(craftCoords[i].x, craftCoords[i].y);
        ctx.lineTo(craftCoords[next].x, craftCoords[next].y);
        ctx.stroke();
        if (i % 2 === 0) {
          ctx.beginPath();
          ctx.moveTo(craftCoords[i].x, craftCoords[i].y);
          ctx.lineTo(craftCoords[(i + 4) % nCrafts].x, craftCoords[(i + 4) % nCrafts].y);
          ctx.stroke();
        }
      }

      craftCoords.forEach((c, idx) => {
        ctx.fillStyle = "rgba(56, 189, 248, 0.6)";
        ctx.beginPath();
        ctx.arc(c.x - Math.sin(time * 2 + idx) * 3, c.y + 6, 2, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = "#38bdf8";
        ctx.beginPath();
        ctx.arc(c.x, c.y, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.2;
        ctx.stroke();

        ctx.fillStyle = "#94a3b8";
        ctx.font = "8px monospace";
        ctx.fillText(`SC${idx + 1}`, c.x + 5, c.y + 3);
      });

      // Scale bracket for the fleet footprint
      ctx.strokeStyle = "#fbbf24";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(cx - span / 2, cy + radius * 0.62);
      ctx.lineTo(cx + span / 2, cy + radius * 0.62);
      ctx.stroke();
      ctx.fillStyle = "#fbbf24";
      ctx.font = "9px monospace";
      ctx.textAlign = "center";
      ctx.fillText("~300 m fleet footprint", cx, cy + radius * 0.62 - 6);
      ctx.fillStyle = "#64748b";
      ctx.fillText(
        `image cylinder ${CYL_DIAM_KM.toFixed(2)} km (Earth radius, 650 AU)`,
        cx,
        cy + radius + 16,
      );
      ctx.textAlign = "left";

      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 10px monospace";
      ctx.fillText(`16 SLOTS SAMPLED PER DWELL — ${row.name}`, 16, 22);
      ctx.fillStyle = "#64748b";
      ctx.font = "9px sans-serif";
      ctx.fillText("Per-dwell overhead 45 s: 30 s slew + 10 s settle + 5 s metrology", 16, 36);

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [formation, isPlaying, row]);

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-primary flex items-center gap-1">
            <Radio size={14} />
            <span>Raster Sampling Simulator</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            16-Craft Concurrent Raster &amp; Tracking Budget
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="btn btn-sm btn-outline flex items-center gap-1 text-xs"
          >
            {isPlaying ? <Pause size={13} /> : <Play size={13} />}
            <span>{isPlaying ? "Pause" : "Resume"}</span>
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
              Sixteen craft sample 16 raster positions concurrently inside the {CYL_DIAM_KM} km
              image cylinder at 650 AU. The formation footprint (~300 m across) is to scale; the
              craft themselves are not.
            </div>
          </div>

          {/* Controls & Budgets */}
          <div className="lg:col-span-5 space-y-4 text-xs">
            {/* Target selector */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <label className="font-semibold text-slate-700 block">
                Target (values from results/targets.json)
              </label>
              <select
                value={targetName}
                onChange={(e) => setTargetName(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-xs font-semibold text-slate-800"
              >
                {ROWS.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.name}
                  </option>
                ))}
              </select>
              <div className="grid grid-cols-3 gap-1.5 pt-1 text-center">
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">
                    {row.v_img_ms.toFixed(1)} m/s
                  </span>
                  <span className="text-[9px] text-slate-400">image-plane speed</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">
                    {row.dv90_face_on_kms.toFixed(2)} km/s
                  </span>
                  <span className="text-[9px] text-slate-400">Δv 90 d, face-on</span>
                </div>
                <div className="bg-white/90 py-1 px-1 rounded border border-slate-200">
                  <span className="font-bold text-slate-700 block">
                    {row.dv90_edge_on_kms.toFixed(2)} km/s
                  </span>
                  <span className="text-[9px] text-slate-400">edge-on (2/π)</span>
                </div>
              </div>
              {/refuted/i.test(row.note) && (
                <p className="text-[10px] text-rose-700 leading-snug">{row.note}</p>
              )}
            </div>

            {/* Formation Selector */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <label className="font-semibold text-slate-700 block">
                Formation Pattern (schematic)
              </label>
              <div className="grid grid-cols-3 gap-1.5 pt-1">
                {([
                  { id: "grid", label: "4×4 Track Block" },
                  { id: "hex", label: "Hexagonal Rings" },
                  { id: "lissajous", label: "Lissajous Sweep" },
                ] as { id: FormationMode; label: string }[]).map((f) => (
                  <button
                    key={f.id}
                    type="button"
                    onClick={() => setFormation(f.id)}
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
              <p className="text-[10px] text-slate-500 leading-snug">
                The archived campaign uses boustrophedon tracks with 16 craft on adjacent rows; the
                other patterns are visual alternatives, not simulated configurations.
              </p>
            </div>

            {/* Thruster Engine Technology */}
            <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-200 space-y-1.5">
              <label className="font-semibold text-slate-700 block">
                Illustrative Propulsion Assumption
              </label>
              <div className="grid grid-cols-3 gap-1.5 pt-1">
                {([
                  { id: "ion", label: "Gridded Ion (Isp 3000 s)" },
                  { id: "electrospray", label: "Electrospray (2000 s)" },
                  { id: "coldgas", label: "Cold Gas (70 s)" },
                ] as { id: keyof typeof ISP_MAP; label: string }[]).map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setThrusterType(t.id)}
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

            {/* Readouts */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">
                  Tracking Δv (archived)
                </div>
                <div className="text-base font-extrabold font-mono text-amber-600 mt-0.5">
                  {row.dv90_face_on_kms.toFixed(2)} km/s
                </div>
                <div className="text-[9px] text-slate-400">
                  <LatexMath math="\oint |a_\perp(t)|\,dt" /> over 90 d
                </div>
              </div>

              <div className="bg-white p-2.5 rounded-lg border border-slate-200">
                <div className="text-[10px] text-slate-400 font-bold uppercase">
                  Propellant / Craft (illustrative)
                </div>
                <div className="text-base font-extrabold font-mono mt-0.5 text-slate-800">
                  {propMassKg} kg
                </div>
                <div className="text-[9px] text-slate-400">
                  Tsiolkovsky at {DRY_MASS_KG} kg dry, Isp {isp} s
                </div>
              </div>
            </div>

            <div className="flex items-start gap-2 p-2.5 bg-amber-50 border border-amber-200 rounded-lg text-[10px] text-amber-900 leading-snug">
              <AlertTriangle size={12} className="mt-0.5 shrink-0 text-amber-600" />
              <span>
                Only the Δv figure is a paper result. The propellant number is a generic rocket
                equation applied here for intuition; the manuscript deliberately does not size a
                propulsion system, and its mission section covers cruise (deep-perihelion sail) and
                power (APPLE tiles) only.
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
