"use client";

import React, { useState } from "react";
import { Code, Copy, Check, FileText, Terminal, ExternalLink } from "lucide-react";
import codeSnippets from "../data/codeSnippets.json";

interface CodeViewerProps {
  initialFile?: string;
}

export default function CodeViewer({ initialFile = "sglsim.py" }: CodeViewerProps) {
  const [selectedFile, setSelectedFile] = useState<string>(initialFile);
  const [copied, setCopied] = useState(false);

  const files = Object.keys(codeSnippets);
  const currentCode = (codeSnippets as Record<string, string>)[selectedFile] || "";

  const handleCopy = () => {
    navigator.clipboard.writeText(currentCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fileDescriptions: Record<string, string> = {
    "sglsim.py": "Monolithic core engine: SGL optical kernel (d/4ρ), forward time-dependent matrix F(t), advecting cloud spatio-temporal OU generator, slot deflation operator P⊥, and regularized GLS solver.",
    "run_experiments.py": "Scientific experimentation pipeline: executes benchmark validation, cadence trade study, 4-way component ablation with paired bootstrap CIs, and spin ephemeris sweeps.",
    "targets.py": "Astrophysical target catalog: computes image cylinder dimensions, photon arrival rates, optical depths, and 90-day focal tracking Δv budgets for 6 exo-Earths.",
    "make_figures.py": "Publication figure renderer: loads results and formats publication-ready EPS/PDF/PNG figures with font sizing and styling conforming to AAS/ApJ guidelines.",
    "cad_solve_one.py": "Standalone MPI/subprocess worker for high-throughput parallel execution of individual cadence parameter configurations.",
  };

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-primary flex items-center gap-1">
            <Code size={14} />
            <span>Open Source Pipeline</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            Source Code & Algorithmic Implementation
          </h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="btn btn-sm btn-outline flex items-center gap-1 text-xs"
          >
            {copied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
            <span>{copied ? "Copied to Clipboard!" : "Copy Source"}</span>
          </button>
        </div>
      </div>

      <div className="card-body">
        {/* File Tabs */}
        <div className="flex flex-wrap gap-1.5 border-b border-slate-200 pb-2 mb-3">
          {files.map((file) => (
            <button
              key={file}
              onClick={() => setSelectedFile(file)}
              className={`px-3 py-1.5 rounded-md text-xs font-mono font-medium transition-all ${
                selectedFile === file
                  ? "bg-slate-900 text-white shadow-sm"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {file}
            </button>
          ))}
        </div>

        {/* Description */}
        <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded border border-slate-200 mb-3 flex items-center gap-2">
          <Terminal size={14} className="text-slate-400 shrink-0" />
          <span>{fileDescriptions[selectedFile] || "Python source module."}</span>
        </div>

        {/* Code display with line numbers */}
        <div className="relative bg-slate-950 text-slate-100 rounded-lg p-4 font-mono text-xs overflow-x-auto max-h-[520px] shadow-inner">
          <pre className="leading-relaxed">
            <code>
              {currentCode.split("\n").map((line, idx) => (
                <div key={idx} className="table-row hover:bg-slate-900/60">
                  <span className="table-cell pr-4 text-slate-600 select-none text-right w-10">
                    {idx + 1}
                  </span>
                  <span className="table-cell">{line}</span>
                </div>
              ))}
            </code>
          </pre>
        </div>

        {/* Run instructions */}
        <div className="mt-3 pt-2 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500 flex-wrap gap-2">
          <span>Run locally with reproducible uv environment:</span>
          <code className="bg-slate-100 text-slate-800 px-2 py-1 rounded font-mono text-[11px]">
            uv run --with numpy,scipy,matplotlib,scikit-image python src/run_experiments.py
          </code>
        </div>
      </div>
    </div>
  );
}
