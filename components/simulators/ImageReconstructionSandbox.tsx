"use client";

import React, { useState, useRef, useEffect } from "react";
import { Play, RotateCcw, Sliders, Cpu, Sparkles, CheckCircle2, ShieldCheck, Zap, Layers, Info } from "lucide-react";
import { RECONSTRUCTION_DATA } from "../../data/reconstructionMaps";
import LatexMath from "../LatexMath";

type ColormapMode = "natural" | "cividis";
type InversionMethod = "gls" | "white" | "b2";

export default function ImageReconstructionSandbox() {
  const [fcIndex, setFcIndex] = useState<number>(1); // Default to 25% for high clarity
  const [method, setMethod] = useState<InversionMethod>("gls");
  const [colormap, setColormap] = useState<ColormapMode>("natural");
  const [numCrafts, setNumCrafts] = useState<number>(16);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [progress, setProgress] = useState<number>(100);

  const canvasTruthRef = useRef<HTMLCanvasElement | null>(null);
  const canvasObsRef = useRef<HTMLCanvasElement | null>(null);
  const canvasReconRef = useRef<HTMLCanvasElement | null>(null);

  const fcValues = [0.0, 0.25, 0.40, 0.55, 0.70];
  const activeFc = fcValues[fcIndex];
  const fcKey = `fc_${fcIndex}` as keyof typeof RECONSTRUCTION_DATA.clouds;

  // Real Pearson r and SSIM directly from publication simulation results
  const methodRowIdx = method === "gls" ? 0 : method === "white" ? 1 : 2;
  const baseR = RECONSTRUCTION_DATA.pearson[methodRowIdx][fcIndex];
  const baseSSIM = RECONSTRUCTION_DATA.ssim[methodRowIdx][fcIndex];

  // Dynamically account for fleet size physics (Table 2 in publication):
  // Single craft cannot perform simultaneous common-mode subtraction (deflation lost)
  // Dense fleet improves sampling cadence
  const fleetDeltaR = method === "gls" 
    ? (numCrafts < 4 ? -0.041 : numCrafts >= 24 ? 0.020 : 0.000)
    : 0;
  const currentR = Math.max(0.01, Math.min(0.999, baseR + fleetDeltaR));
  const currentSSIM = Math.max(0.01, Math.min(0.999, baseSSIM + (fleetDeltaR * 0.4)));

  const runSimulation = () => {
    setIsSimulating(true);
    setProgress(0);

    let step = 0;
    const interval = setInterval(() => {
      step += 20;
      setProgress(Math.min(100, step));

      if (step >= 100) {
        clearInterval(interval);
        setIsSimulating(false);
      }
    }, 90);
  };

  // Helper to render an RGB matrix onto a canvas with smooth scaling
  const drawRgbToCanvas = (
    canvas: HTMLCanvasElement, 
    rgbMatrix: any, 
    cloudMatrix?: any
  ) => {
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rows = 36;
    const cols = 72;

    const offscreen = document.createElement("canvas");
    offscreen.width = cols;
    offscreen.height = rows;
    const offCtx = offscreen.getContext("2d");
    if (!offCtx) return;

    const imgData = offCtx.createImageData(cols, rows);

    for (let y = 0; y < rows; y++) {
      for (let x = 0; x < cols; x++) {
        const idx = (y * cols + x) * 4;
        const rgb = rgbMatrix[y][x];

        let r = rgb[0];
        let g = rgb[1];
        let b = rgb[2];

        // Cloud blend for Panel (b)
        if (cloudMatrix && activeFc > 0) {
          const opac = cloudMatrix[y] ? cloudMatrix[y][x] : 0;
          if (opac > 0.20) {
            const alpha = Math.min(0.88, (opac - 0.20) * 0.55 + 0.30);
            r = Math.round(r * (1 - alpha) + 245 * alpha);
            g = Math.round(g * (1 - alpha) + 248 * alpha);
            b = Math.round(b * (1 - alpha) + 255 * alpha);
          }
        }

        imgData.data[idx] = r;
        imgData.data[idx + 1] = g;
        imgData.data[idx + 2] = b;
        imgData.data[idx + 3] = 255;
      }
    }

    offCtx.putImageData(imgData, 0, 0);

    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(offscreen, 0, 0, canvas.width, canvas.height);
  };

  // Redraw whenever parameters change
  useEffect(() => {
    const isCividis = colormap === "cividis";
    const truthMatrix = isCividis ? RECONSTRUCTION_DATA.cividis_truth : RECONSTRUCTION_DATA.natural_truth;
    const cloudMatrix = RECONSTRUCTION_DATA.clouds[fcKey];

    // Method matrix selector
    let reconMatrix: any = truthMatrix;
    if (method === "gls") {
      reconMatrix = isCividis 
        ? RECONSTRUCTION_DATA.gls_cividis[fcKey] 
        : RECONSTRUCTION_DATA.gls_natural[fcKey];
    } else if (method === "white") {
      reconMatrix = isCividis 
        ? RECONSTRUCTION_DATA.white_cividis[fcKey] 
        : RECONSTRUCTION_DATA.white_natural[fcKey];
    } else {
      reconMatrix = isCividis 
        ? RECONSTRUCTION_DATA.b2_cividis[fcKey] 
        : RECONSTRUCTION_DATA.b2_natural[fcKey];
    }

    // 1. Draw Ground Truth
    if (canvasTruthRef.current) {
      drawRgbToCanvas(canvasTruthRef.current, truthMatrix);
    }

    // 2. Draw Observations with OU Clouds
    if (canvasObsRef.current) {
      drawRgbToCanvas(canvasObsRef.current, truthMatrix, cloudMatrix);
    }

    // 3. Draw Reconstructed Output
    if (canvasReconRef.current) {
      drawRgbToCanvas(canvasReconRef.current, reconMatrix);
    }
  }, [fcIndex, method, colormap, numCrafts]);

  return (
    <div className="card">
      {/* Header with clean responsive spacing and segmented colormap switch */}
      <div className="card-header flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="badge badge-primary text-[10px] font-bold flex items-center gap-1">
              <Sparkles size={13} />
              <span>Interactive Laboratory</span>
            </span>
            <span className="text-xs text-slate-500 font-medium">
              Peer-Reviewed Simulation Suite
            </span>
          </div>
          <h3 className="text-base sm:text-lg font-bold text-slate-900">
            End-to-End Image Reconstruction Sandbox
          </h3>
        </div>

        <div className="flex items-center gap-2.5 self-start sm:self-auto shrink-0 flex-wrap">
          {/* Segmented Colormap Toggle */}
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-0.5 text-xs shadow-inner">
            <button
              type="button"
              onClick={() => setColormap("natural")}
              className={`px-2.5 py-1 rounded-md transition-all ${
                colormap === "natural" 
                  ? "bg-white text-blue-700 shadow-xs font-bold" 
                  : "text-slate-600 hover:text-slate-900 font-medium"
              }`}
            >
              Natural Earth
            </button>
            <button
              type="button"
              onClick={() => setColormap("cividis")}
              className={`px-2.5 py-1 rounded-md transition-all ${
                colormap === "cividis" 
                  ? "bg-white text-blue-700 shadow-xs font-bold" 
                  : "text-slate-600 hover:text-slate-900 font-medium"
              }`}
            >
              ApJ Cividis
            </button>
          </div>

          <button
            onClick={runSimulation}
            disabled={isSimulating}
            className="btn btn-sm btn-primary text-xs flex items-center gap-1.5 px-3 py-1.5 shadow-sm"
          >
            {isSimulating ? (
              <>
                <RotateCcw size={13} className="animate-spin" />
                <span>Inverting ({progress}%)...</span>
              </>
            ) : (
              <>
                <Play size={13} />
                <span>Run Inversion</span>
              </>
            )}
          </button>
        </div>
      </div>

      <div className="card-body space-y-6">
        {/* 3-Panel Physics Display */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* Panel 1: Ground Truth */}
          <div className="bg-slate-50 p-3 sm:p-3.5 rounded-xl border border-slate-200 flex flex-col justify-between">
            <div className="w-full flex flex-col gap-0.5 mb-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 font-bold text-xs text-slate-800">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
                  <span>(a) Ground Truth</span>
                </div>
                <span className="text-[10px] text-slate-600 font-mono font-semibold bg-slate-200/80 px-2 py-0.5 rounded-md">
                  36×72 Map
                </span>
              </div>
              <div className="text-[10px] text-slate-400 pl-3.5">Exo-Earth Surface Albedo</div>
            </div>

            <div className="w-full aspect-[2/1] rounded-lg overflow-hidden border border-slate-300 shadow-inner bg-slate-950">
              <canvas ref={canvasTruthRef} width={288} height={144} className="w-full h-full block" />
            </div>

            <div className="text-[11px] text-slate-500 mt-2.5 text-center leading-tight">
              True continental geography (Americas, Eurasia, Africa)
            </div>
          </div>

          {/* Panel 2: Cloud-Corrupted Stream */}
          <div className="bg-slate-50 p-3 sm:p-3.5 rounded-xl border border-slate-200 flex flex-col justify-between">
            <div className="w-full flex flex-col gap-0.5 mb-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 font-bold text-xs text-slate-800">
                  <span className="w-2 h-2 rounded-full bg-amber-500 shrink-0" />
                  <span>(b) Corrupted Stream</span>
                </div>
                <span className="text-[10px] text-amber-800 font-mono font-bold bg-amber-100 border border-amber-300/80 px-2 py-0.5 rounded-md">
                  {(activeFc * 100).toFixed(0)}% Clouds
                </span>
              </div>
              <div className="text-[10px] text-slate-400 pl-3.5">OU Stochastic Weather Field</div>
            </div>

            <div className="w-full aspect-[2/1] rounded-lg overflow-hidden border border-slate-300 shadow-inner bg-slate-950">
              <canvas ref={canvasObsRef} width={288} height={144} className="w-full h-full block" />
            </div>

            <div className="text-[11px] text-slate-500 mt-2.5 text-center leading-tight">
              Spatio-temporal Ornstein-Uhlenbeck cloud advection
            </div>
          </div>

          {/* Panel 3: Inversion Output */}
          <div className="bg-slate-50 p-3 sm:p-3.5 rounded-xl border border-slate-200 flex flex-col justify-between">
            <div className="w-full flex flex-col gap-0.5 mb-2.5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 font-bold text-xs text-slate-800">
                  <span className="w-2 h-2 rounded-full bg-blue-600 shrink-0" />
                  <span>(c) Reconstructed Map</span>
                </div>
                <span className="text-[10px] text-blue-800 font-mono font-bold bg-blue-100 border border-blue-300/80 px-2 py-0.5 rounded-md">
                  {method === "gls" ? (numCrafts >= 4 ? "TDI Deflated" : "TDI (No Defl)") : method === "white" ? "White Noise" : "Coaddition"}
                </span>
              </div>
              <div className="text-[10px] text-slate-400 pl-3.5">GLS Inverse Solution m̂</div>
            </div>

            <div className="w-full aspect-[2/1] rounded-lg overflow-hidden border border-slate-300 shadow-inner bg-slate-950 relative">
              <canvas ref={canvasReconRef} width={288} height={144} className="w-full h-full block" />
              {isSimulating && (
                <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-[2px] flex flex-col items-center justify-center text-white z-10 animate-fadeIn p-3 text-center">
                  <RotateCcw className="animate-spin text-blue-400 mb-2" size={24} />
                  <span className="text-xs font-mono font-bold tracking-wider uppercase text-blue-300">
                    Inverting Time-Series ({progress}%)
                  </span>
                  <div className="mt-2 px-3 py-1 bg-slate-900/90 rounded-md border border-slate-700 text-xs shadow-md">
                    <LatexMath math="\hat{\mathbf{m}} = \left( \mathbf{F}^T \mathbf{C}_y^{-1} \mathbf{F} + \mathbf{\Lambda} \right)^{-1} \mathbf{F}^T \mathbf{C}_y^{-1} \mathbf{y}" />
                  </div>
                </div>
              )}
            </div>

            <div className="text-[11px] text-emerald-700 font-bold mt-2.5 text-center font-mono">
              r = {currentR.toFixed(3)} | SSIM = {currentSSIM.toFixed(3)}
            </div>
          </div>
        </div>

        {/* Interactive Controls Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs">
          {/* Cloud Cover Slider */}
          <div className="space-y-1.5">
            <div className="flex justify-between items-baseline">
              <label className="font-semibold text-slate-700">Cloud Fraction (fc):</label>
              <span className="font-mono font-bold text-blue-600">{(activeFc * 100).toFixed(0)}% cover</span>
            </div>
            <input
              type="range"
              min="0"
              max="4"
              step="1"
              value={fcIndex}
              onChange={(e) => setFcIndex(parseInt(e.target.value))}
              className="w-full range-slider"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>0% (Clear)</span>
              <span>25%</span>
              <span>40%</span>
              <span className="font-bold text-slate-700">55% (Earth)</span>
              <span>70%</span>
            </div>
          </div>

          {/* Inversion Algorithm Selector */}
          <div className="space-y-1.5">
            <label className="font-semibold text-slate-700 block">Inversion Algorithm</label>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as InversionMethod)}
              className="w-full p-2 rounded-lg border border-slate-200 bg-white text-slate-800 font-semibold text-xs leading-normal cursor-pointer"
            >
              <option value="gls">TDI (Deflated GLS) [Our Method]</option>
              <option value="white">Naive White-Noise GLS</option>
              <option value="b2">Phase-Binned Coaddition</option>
            </select>
            <div className="text-[10px] text-slate-500">
              {method === "gls" ? (
                numCrafts >= 4 ? (
                  <span className="flex items-center gap-1 flex-wrap">
                    Full <LatexMath math="\mathbf{P}_\perp" /> common-mode deflation + covariance <LatexMath math="\mathbf{C}_y" />
                  </span>
                ) : (
                  <span>Single craft: Deflation inactive (<LatexMath math="\mathbf{P}_\perp" /> requires &ge; 4 crafts)</span>
                )
              ) : method === "white" ? (
                <span className="flex items-center gap-1 flex-wrap">
                  Disregards cloud correlations (<LatexMath math="\mathbf{C}_y \to \sigma^2 \mathbf{I}" />)
                </span>
              ) : (
                <span>Averages observations, suffering rotational smearing</span>
              )}
            </div>
          </div>

          {/* Spacecraft Fleet Size */}
          <div className="space-y-1.5 sm:col-span-2 lg:col-span-1">
            <div className="flex justify-between items-baseline">
              <label className="font-semibold text-slate-700">Spacecraft Fleet:</label>
              <span className="font-mono font-bold text-emerald-700">{numCrafts} Spacecraft</span>
            </div>
            <input
              type="range"
              min="1"
              max="32"
              step="1"
              value={numCrafts}
              onChange={(e) => setNumCrafts(parseInt(e.target.value))}
              className="w-full range-slider"
            />
            <div className="flex justify-between text-[10px] text-slate-400">
              <span>1 (Single)</span>
              <span className="font-bold text-slate-700">16 (Nominal)</span>
              <span>32 (Dense)</span>
            </div>
          </div>
        </div>

        {/* Live Metrics Readout Bar */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 sm:gap-3">
          <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs">
            <div className="text-[10px] uppercase font-bold text-slate-400 truncate">Pearson Fidelity (r)</div>
            <div className={`text-xl font-extrabold font-mono mt-0.5 ${currentR > 0.3 ? "text-emerald-700" : "text-amber-700"}`}>
              {currentR.toFixed(3)}
            </div>
            <div className="text-[10px] text-slate-500">Benchmark: 0.326 at fc=0.55</div>
          </div>

          <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs">
            <div className="text-[10px] uppercase font-bold text-slate-400 truncate">Structural SSIM</div>
            <div className="text-xl font-extrabold font-mono text-slate-800 mt-0.5">{currentSSIM.toFixed(3)}</div>
            <div className="text-[10px] text-slate-500">Coastline shape index</div>
          </div>

          <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs">
            <div className="text-[10px] uppercase font-bold text-slate-400 truncate">Deflation Benefit</div>
            <div className="text-xl font-extrabold font-mono text-emerald-600 mt-0.5">
              {method === "gls" && numCrafts >= 4 ? "+0.041 Δr" : "0.000"}
            </div>
            <div className="text-[10px] text-slate-500">
              {method === "gls" && numCrafts >= 4 ? "95% CI: [0.027, 0.054]" : "Inactive (requires swarm)"}
            </div>
          </div>

          <div className="bg-white p-3 rounded-lg border border-slate-200 shadow-2xs">
            <div className="text-[10px] uppercase font-bold text-slate-400 truncate">Harmonic Degree</div>
            <div className="text-xl font-extrabold font-mono text-blue-600 mt-0.5">
              ℓ ≈ {activeFc === 0 ? "20" : activeFc <= 0.25 ? "12" : activeFc <= 0.4 ? "8" : "5"}
            </div>
            <div className="text-[10px] text-slate-500">Resolved feature scale</div>
          </div>
        </div>
      </div>
    </div>
  );
}

