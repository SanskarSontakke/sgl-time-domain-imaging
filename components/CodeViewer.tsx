"use client";

import React, { useState } from "react";
import { Code, Copy, Check, Terminal } from "lucide-react";
import codeSnippets from "../data/codeSnippets.json";
import LatexMath from "./LatexMath";

interface CodeViewerProps {
  initialFile?: string;
}

export default function CodeViewer({ initialFile = "sglsim.py" }: CodeViewerProps) {
  const [selectedFile, setSelectedFile] = useState<string>(initialFile);
  const [copied, setCopied] = useState<boolean>(false);

  const files = Object.keys(codeSnippets);
  const currentCode = (codeSnippets as Record<string, string>)[selectedFile] || "";

  const handleCopy = () => {
    navigator.clipboard.writeText(currentCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fileDescriptions: Record<string, React.ReactNode> = {
    "sglsim.py": (
      <span>
        Core library: SGL optical kernel (<LatexMath math="d / (4\rho)" />), time-dependent forward matrix <LatexMath math="\mathbf{F}(t)" /> with Gauss–Legendre exposure integration, advecting OU cloud generator and extended climatology variants, explicit campaign time ledger, slot-mean profiling, and the regularized GLS/TDI solver.
      </span>
    ),
    "expcommon.py": "Single source of conventions: seeds, quadrature order, cloud fractions, the two cadence arms, cached operators, and the paired statistics (t-test, exact sign test, bootstrap CI) every table quotes.",
    "run_experiments.py": "Checkpointed experiment driver: one subcommand per study, seeds looped inside a single process so the forward operator is built once, then `merge` assembles results/*.npz and writes audit.json with the seed count behind every headline number.",
    "targets.py": (
      <span>
        Target table + map: image cylinder dimensions, photon rates, focal-line antipodes, ecliptic latitudes and 90-day tracking <LatexMath math="\Delta v" /> for five confirmed temperate planets plus one refuted signal kept as an illustrative row.
      </span>
    ),
    "make_figures.py": "Figure renderer: every panel in the manuscript is drawn from results/*.npz, so a figure cannot disagree with a table.",
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
          <span>Regenerate one study and the archive from the repository root:</span>
          <code className="bg-slate-100 text-slate-800 px-2 py-1 rounded font-mono text-[11px]">
            python3 src/run_experiments.py clouds 3 &amp;&amp; python3 src/run_experiments.py merge
          </code>
        </div>
      </div>
    </div>
  );
}
