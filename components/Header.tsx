"use client";

import React from "react";
import { Sparkles, BookOpen, Presentation, Download, Github, Globe } from "lucide-react";

interface HeaderProps {
  activeMode: "presentation" | "documentation";
  setActiveMode: (mode: "presentation" | "documentation") => void;
}

export default function Header({ activeMode, setActiveMode }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Project Branding */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center text-white font-black text-base shadow-sm">
            ☀️
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-slate-900 text-base tracking-tight">
                SGL Time-Domain Imaging
              </span>
              <span className="badge badge-primary text-[10px] uppercase font-bold py-0.5 px-1.5 hidden sm:inline">
                ApJ Revised
              </span>
            </div>
            <p className="text-[11px] text-slate-500 hidden md:block">
              Exo-Earth Surface Recovery with the Solar Gravitational Lens
            </p>
          </div>
        </div>

        {/* Primary View Mode Switcher */}
        <div className="flex items-center bg-slate-100 p-1 rounded-xl border border-slate-200">
          <button
            onClick={() => setActiveMode("presentation")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeMode === "presentation"
                ? "bg-white text-blue-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Presentation size={14} className={activeMode === "presentation" ? "text-blue-600" : "text-slate-400"} />
            <span>Judge Presentation Board (PPT)</span>
          </button>

          <button
            onClick={() => setActiveMode("documentation")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeMode === "documentation"
                ? "bg-white text-blue-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <BookOpen size={14} className={activeMode === "documentation" ? "text-blue-600" : "text-slate-400"} />
            <span>Technical Documentation</span>
          </button>
        </div>

        {/* Download Actions */}
        <div className="flex items-center gap-2">
          <a
            href="/docs/sgl_time_domain_imaging.pdf"
            download
            className="btn btn-sm btn-primary text-xs flex items-center gap-1.5 shadow-sm"
          >
            <Download size={13} />
            <span className="hidden sm:inline">Paper PDF</span>
          </a>
        </div>
      </div>
    </header>
  );
}
