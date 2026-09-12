"use client";

import React from "react";
import { Sparkles, BookOpen, Presentation, Download, Globe } from "lucide-react";

interface HeaderProps {
  activeMode: "presentation" | "documentation";
  setActiveMode: (mode: "presentation" | "documentation") => void;
}

export default function Header({ activeMode, setActiveMode }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-2 sm:gap-4">
        {/* Project Branding */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center text-white font-black text-sm sm:text-base shadow-sm">
            ☀️
          </div>
          <div>
            <div className="flex items-center gap-1.5 sm:gap-2">
              <span className="font-extrabold text-slate-900 text-sm sm:text-base tracking-tight truncate max-w-[130px] sm:max-w-none">
                SGL Time-Domain
              </span>
              <span className="badge badge-primary text-[9px] sm:text-[10px] uppercase font-bold py-0.2 px-1 hidden md:inline">
                ApJ Revised
              </span>
            </div>
            <p className="text-[10px] text-slate-500 hidden lg:block">
              Exo-Earth Surface Recovery with the Solar Gravitational Lens
            </p>
          </div>
        </div>

        {/* Primary View Mode Switcher (Fully responsive) */}
        <div className="flex items-center bg-slate-100 p-0.5 sm:p-1 rounded-xl border border-slate-200 shrink-0">
          <button
            onClick={() => setActiveMode("presentation")}
            className={`flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeMode === "presentation"
                ? "bg-white text-blue-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <Presentation size={13} className={activeMode === "presentation" ? "text-blue-600" : "text-slate-400"} />
            <span className="sm:hidden">Judge Deck</span>
            <span className="hidden sm:inline">Judge Presentation (PPT)</span>
          </button>

          <button
            onClick={() => setActiveMode("documentation")}
            className={`flex items-center gap-1 sm:gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeMode === "documentation"
                ? "bg-white text-blue-700 shadow-sm"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            <BookOpen size={13} className={activeMode === "documentation" ? "text-blue-600" : "text-slate-400"} />
            <span className="sm:hidden">Tech Docs</span>
            <span className="hidden sm:inline">Technical Docs</span>
          </button>
        </div>

        {/* Download Actions */}
        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          <a
            href="/docs/sgl_time_domain_imaging.pdf"
            download
            className="btn btn-sm btn-primary text-xs flex items-center gap-1 sm:gap-1.5 shadow-sm px-2 sm:px-3 py-1.5"
            title="Download Full Paper PDF"
          >
            <Download size={13} />
            <span className="hidden sm:inline">Paper PDF</span>
          </a>
        </div>
      </div>
    </header>
  );
}
