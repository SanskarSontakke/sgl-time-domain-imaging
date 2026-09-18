"use client";

import React from "react";
import { Download } from "lucide-react";

interface HeaderProps {
  activeMode?: "presentation" | "documentation";
  setActiveMode?: (mode: "presentation" | "documentation") => void;
}

export default function Header({ activeMode, setActiveMode }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200">
      <div className="w-full px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Project Branding */}
        <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
          <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-blue-600 to-sky-500 flex items-center justify-center text-white font-black text-sm sm:text-base shadow-sm">
            ☀️
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-extrabold text-slate-900 text-sm sm:text-base tracking-tight">
                SGL Time-Domain Imaging
              </span>
            </div>
            <p className="text-[10px] sm:text-[11px] text-slate-500 hidden sm:block">
              Exo-Earth Surface Recovery with the Solar Gravitational Lens
            </p>
          </div>
        </div>

        {/* Download Actions & Paper Link */}
        <div className="flex items-center gap-2 shrink-0">
          <a
            href="/docs/sgl_time_domain_imaging.pdf"
            download
            className="btn btn-sm btn-primary text-xs flex items-center gap-1.5 shadow-sm px-3 py-1.5"
            title="Download Full Paper PDF"
          >
            <Download size={13} />
            <span>Paper PDF</span>
          </a>
        </div>
      </div>
    </header>
  );
}
