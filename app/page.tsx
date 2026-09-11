"use client";

import React, { useState } from "react";
import Header from "../components/Header";
import JudgePresentation from "../components/JudgePresentation";
import TechnicalDocumentation from "../components/TechnicalDocumentation";
import { Sparkles, Presentation, BookOpen, Download, Compass, ShieldCheck, Zap, Globe, Cpu } from "lucide-react";

export default function HomePage() {
  const [activeMode, setActiveMode] = useState<"presentation" | "documentation">("presentation");

  return (
    <div className="flex flex-col min-h-screen">
      {/* Top Header */}
      <Header activeMode={activeMode} setActiveMode={setActiveMode} />

      {/* Hero Banner with Executive Highlights */}
      <section className="bg-gradient-to-b from-blue-50/70 via-slate-50 to-slate-50 border-b border-slate-200 py-8 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="badge badge-primary text-xs font-mono font-bold">
                  NASA NIAC & ApJ Phase Research
                </span>
                <span className="text-xs text-slate-500 font-medium">
                  Peer-Reviewed Astrophysical Research
                </span>
              </div>
              <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black text-slate-900 tracking-tight">
                Time-Domain Imaging of a Rotating, Cloudy Exo-Earth with the SGL
              </h1>
              <p className="text-sm sm:text-base text-slate-600 max-w-3xl">
                A definitive end-to-end framework solving the dynamic time-aliasing problem for the Solar Gravitational Lens, reconstructing planetary surface continents through moving cloud cover.
              </p>
            </div>

            {/* Mode Switcher Action Card */}
            <div className="bg-white p-2.5 rounded-xl border border-slate-200 shadow-sm flex items-center gap-2">
              <span className="text-xs font-bold text-slate-500 pl-2">View Mode:</span>
              <button
                onClick={() => setActiveMode("presentation")}
                className={`btn btn-sm ${
                  activeMode === "presentation" ? "btn-primary" : "btn-outline"
                } text-xs flex items-center gap-1.5`}
              >
                <Presentation size={14} />
                <span>Judge Board (PPT)</span>
              </button>
              <button
                onClick={() => setActiveMode("documentation")}
                className={`btn btn-sm ${
                  activeMode === "documentation" ? "btn-primary" : "btn-outline"
                } text-xs flex items-center gap-1.5`}
              >
                <BookOpen size={14} />
                <span>Technical Docs</span>
              </button>
            </div>
          </div>

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 pt-3 border-t border-slate-200/80">
            <div className="bg-white p-3 rounded-lg border border-slate-200/80 shadow-xs">
              <div className="text-[10px] uppercase font-bold text-slate-400">Gravitational Gain</div>
              <div className="text-base font-extrabold font-mono text-blue-600 mt-0.5">μ ~ 10¹¹</div>
              <div className="text-[10px] text-slate-500">Natural Sun lens</div>
            </div>

            <div className="bg-white p-3 rounded-lg border border-slate-200/80 shadow-xs">
              <div className="text-[10px] uppercase font-bold text-slate-400">Mission Distance</div>
              <div className="text-base font-extrabold font-mono text-slate-800 mt-0.5">650 AU</div>
              <div className="text-[10px] text-slate-500">1.3 km focal cylinder</div>
            </div>

            <div className="bg-white p-3 rounded-lg border border-slate-200/80 shadow-xs">
              <div className="text-[10px] uppercase font-bold text-slate-400">Fleet Architecture</div>
              <div className="text-base font-extrabold font-mono text-slate-800 mt-0.5">16 Crafts</div>
              <div className="text-[10px] text-slate-500">Concurrent slots</div>
            </div>

            <div className="bg-white p-3 rounded-lg border border-slate-200/80 shadow-xs">
              <div className="text-[10px] uppercase font-bold text-slate-400">Slot Deflation Benefit</div>
              <div className="text-base font-extrabold font-mono text-emerald-600 mt-0.5">+0.041 Δr</div>
              <div className="text-[10px] text-slate-500">95% CI: [0.027, 0.054]</div>
            </div>

            <div className="bg-white p-3 rounded-lg border border-slate-200/80 shadow-xs">
              <div className="text-[10px] uppercase font-bold text-slate-400">Surface Fidelity</div>
              <div className="text-base font-extrabold font-mono text-blue-700 mt-0.5">r = 0.326</div>
              <div className="text-[10px] text-slate-500">At 55% cloud cover</div>
            </div>

            <div className="bg-white p-3 rounded-lg border border-slate-200/80 shadow-xs">
              <div className="text-[10px] uppercase font-bold text-slate-400">Habitable Targets</div>
              <div className="text-base font-extrabold font-mono text-slate-800 mt-0.5">6 Systems</div>
              <div className="text-[10px] text-slate-500">Δv90 &lt; 3 km/s</div>
            </div>
          </div>
        </div>
      </section>

      {/* Main Mode View */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
        {activeMode === "presentation" ? (
          <div className="space-y-6">
            <div className="flex items-center justify-between flex-wrap gap-2 pb-2 border-b border-slate-200">
              <div className="flex items-center gap-2">
                <Presentation size={18} className="text-blue-600" />
                <h2 className="text-lg font-bold text-slate-800">
                  Judge Presentation Board (PPT Deck Mode)
                </h2>
              </div>
              <span className="text-xs text-slate-500">
                Use arrow keys (← / →) or on-screen controls to step through slides.
              </span>
            </div>
            <JudgePresentation />
          </div>
        ) : (
          <TechnicalDocumentation />
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-slate-200 py-8 px-4 sm:px-6 lg:px-8 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="space-y-1 text-center md:text-left">
            <div className="font-bold text-slate-700">
              Solar Gravitational Lens (SGL) Time-Domain Imaging Research
            </div>
            <p>
              Original research by Sanskar Sontakke and Collaborators. Prepared for The Astrophysical Journal (ApJ).
            </p>
          </div>

          <div className="flex items-center gap-4 flex-wrap justify-center">
            <a
              href="/docs/sgl_time_domain_imaging.pdf"
              download
              className="text-blue-600 hover:text-blue-800 font-semibold"
            >
              Paper PDF
            </a>
            <span className="text-slate-300">•</span>
            <a
              href="/docs/response_to_editor.pdf"
              download
              className="text-blue-600 hover:text-blue-800 font-semibold"
            >
              Response to Editor
            </a>
            <span className="text-slate-300">•</span>
            <a
              href="/docs/cover_letter.pdf"
              download
              className="text-blue-600 hover:text-blue-800 font-semibold"
            >
              Cover Letter
            </a>
            <span className="text-slate-300">•</span>
            <span className="text-slate-400">MIT License</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
