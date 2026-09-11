"use client";

import React, { useState } from "react";
import { Compass, Rocket, Globe, Zap, CheckCircle2, ChevronRight } from "lucide-react";
import LatexMath from "../LatexMath";

interface Target {
  id: string;
  name: string;
  star: string;
  dist_pc: number;
  dist_ly: number;
  period_days: number;
  mass_earth: number;
  radius_earth: number;
  d_img_m: number;
  d_img_err: number;
  snr_c: number;
  snr_min: number;
  snr_max: number;
  v_img_ms: number;
  dv90_kms: number;
  dv90_err: number;
  focal_ra_deg: number;
  focal_dec_deg: number;
  ecliptic_lat: number;
  highlight: string;
  verdict: string;
}

const TARGETS: Target[] = [
  {
    id: "proxima_b",
    name: "Proxima Centauri b",
    star: "M5.5V Red Dwarf",
    dist_pc: 1.30,
    dist_ly: 4.24,
    period_days: 11.2,
    mass_earth: 1.17,
    radius_earth: 1.07,
    d_img_m: 31454,
    d_img_err: 4718,
    snr_c: 659.2,
    snr_min: 280,
    snr_max: 1237,
    v_img_ms: 114.4,
    dv90_kms: 5.78,
    dv90_err: 1.27,
    focal_ra_deg: 37.5,
    focal_dec_deg: 62.7,
    ecliptic_lat: 44.8,
    highlight: "Nearest known exoplanet to Earth. Largest focal image cylinder (31.5 km).",
    verdict: "Highest photon rate, but requires high Δv propulsion (5.8 km/s over 90 days) due to 11-day orbit.",
  },
  {
    id: "ross_128_b",
    name: "Ross 128 b",
    star: "M4.0V Inactive Red Dwarf",
    dist_pc: 3.37,
    dist_ly: 11.0,
    period_days: 9.9,
    mass_earth: 1.40,
    radius_earth: 1.11,
    d_img_m: 12940,
    d_img_err: 1941,
    snr_c: 575.8,
    snr_min: 245,
    snr_max: 1080,
    v_img_ms: 51.0,
    dv90_kms: 2.92,
    dv90_err: 0.70,
    focal_ra_deg: 357.0,
    focal_dec_deg: -0.8,
    ecliptic_lat: 0.5,
    highlight: "Extremely quiet, non-flaring host star in the habitable zone.",
    verdict: "Ideal astrobiological candidate with moderate propulsion requirement (2.9 km/s).",
  },
  {
    id: "gj_273_b",
    name: "GJ 273 b (Luyten b)",
    star: "M3.5V Red Dwarf",
    dist_pc: 3.80,
    dist_ly: 12.4,
    period_days: 18.6,
    mass_earth: 2.89,
    radius_earth: 1.34,
    d_img_m: 14223,
    d_img_err: 2133,
    snr_c: 486.1,
    snr_min: 207,
    snr_max: 912,
    v_img_ms: 44.1,
    dv90_kms: 1.34,
    dv90_err: 0.27,
    focal_ra_deg: 291.9,
    focal_dec_deg: -5.2,
    ecliptic_lat: 16.5,
    highlight: "Low tracking velocity budget (1.34 km/s) and strong habitable zone thermal balance.",
    verdict: "Top mission engineering sweet spot: balanced SNR and low thruster delta-v requirement.",
  },
  {
    id: "gj_1061_d",
    name: "GJ 1061 d",
    star: "M5.5V Red Dwarf",
    dist_pc: 3.67,
    dist_ly: 12.0,
    period_days: 13.0,
    mass_earth: 1.64,
    radius_earth: 1.16,
    d_img_m: 12566,
    d_img_err: 1885,
    snr_c: 279.6,
    snr_min: 119,
    snr_max: 524,
    v_img_ms: 38.7,
    dv90_kms: 1.68,
    dv90_err: 0.20,
    focal_ra_deg: 234.0,
    focal_dec_deg: 44.5,
    ecliptic_lat: 60.8,
    highlight: "High ecliptic latitude (+60.8°) avoids solar dust plane interference.",
    verdict: "Excellent clean background sightline; modest propulsion budget (1.68 km/s).",
  },
  {
    id: "teegarden_c",
    name: "Teegarden c",
    star: "M7.0V Ultra-cool Dwarf",
    dist_pc: 3.83,
    dist_ly: 12.5,
    period_days: 11.4,
    mass_earth: 1.11,
    radius_earth: 1.05,
    d_img_m: 10792,
    d_img_err: 1619,
    snr_c: 128.8,
    snr_min: 55,
    snr_max: 242,
    v_img_ms: 34.7,
    dv90_kms: 1.72,
    dv90_err: 0.14,
    focal_ra_deg: 223.2,
    focal_dec_deg: -16.9,
    ecliptic_lat: -0.3,
    highlight: "True Earth-mass analog orbiting an ultra-cool dwarf star.",
    verdict: "Compact image plane (10.8 km) requiring careful optical alignment.",
  },
  {
    id: "tau_cet_e",
    name: "τ Ceti e (Solar Analog)",
    star: "G8.5V Yellow Dwarf (Sun-like)",
    dist_pc: 3.65,
    dist_ly: 11.9,
    period_days: 162.9,
    mass_earth: 3.93,
    radius_earth: 1.52,
    d_img_m: 16349,
    d_img_err: 2452,
    snr_c: 901.4,
    snr_min: 383,
    snr_max: 1691,
    v_img_ms: 31.4,
    dv90_kms: 0.11,
    dv90_err: 0.04,
    focal_ra_deg: 205.9,
    focal_dec_deg: 15.9,
    ecliptic_lat: 24.8,
    highlight: "Sun-like host star! Long 163-day orbit means practically zero tracking effort.",
    verdict: "Virtually zero propulsion needed (0.11 km/s over 90 days); highest SNR.",
  },
];

export default function TargetCatalogExplorer() {
  const [selectedId, setSelectedId] = useState<string>("ross_128_b");
  const target = TARGETS.find((t) => t.id === selectedId) || TARGETS[0];

  return (
    <div className="card">
      <div className="card-header flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <div className="badge badge-primary flex items-center gap-1">
            <Compass size={14} />
            <span>Exoplanet Target Database</span>
          </div>
          <h3 className="text-lg font-bold text-slate-800">
            Exo-Earth Target Catalog & Focal-Line Tracking Dynamics
          </h3>
        </div>
        <span className="text-xs text-slate-500 font-mono">
          6 Candidates Evaluated at z = 650 AU
        </span>
      </div>

      <div className="card-body">
        {/* Target Buttons */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 mb-4">
          {TARGETS.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedId(t.id)}
              className={`p-2.5 rounded-lg text-left border transition-all ${
                selectedId === t.id
                  ? "border-blue-600 bg-blue-50/70 shadow-sm"
                  : "border-slate-200 hover:border-slate-300 bg-white"
              }`}
            >
              <div className="text-xs font-bold text-slate-800 truncate">{t.name}</div>
              <div className="text-[11px] text-slate-500">{t.dist_ly.toFixed(1)} ly</div>
              <div className="text-[10px] font-mono text-blue-600 mt-1">
                {(t.d_img_m / 1000).toFixed(1)} km img
              </div>
            </button>
          ))}
        </div>

        {/* Selected Target Deep Dive */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* Main Info Card */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
            <div className="flex justify-between items-start">
              <div>
                <h4 className="text-base font-bold text-slate-900">{target.name}</h4>
                <div className="text-xs text-slate-500">{target.star}</div>
              </div>
              <span className="badge badge-accent text-xs">
                {target.dist_pc.toFixed(2)} pc ({target.dist_ly.toFixed(1)} ly)
              </span>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              {target.highlight}
            </p>

            <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded-lg text-xs space-y-1">
              <span className="font-bold text-emerald-900 flex items-center gap-1">
                <CheckCircle2 size={13} className="text-emerald-600" />
                Mission Assessment:
              </span>
              <p className="text-emerald-800 leading-snug">{target.verdict}</p>
            </div>

            {/* Orbit & Focal Line Coordinates */}
            <div className="pt-2 border-t border-slate-200 text-xs space-y-1.5 font-mono">
              <div className="flex justify-between text-slate-600">
                <span>Orbital Period:</span>
                <span className="font-bold text-slate-800">{target.period_days.toFixed(1)} days</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Planet Mass / Radius:</span>
                <span className="font-bold text-slate-800">{target.mass_earth} M⊕ / {target.radius_earth} R⊕</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Focal Line RA / Dec:</span>
                <span className="font-bold text-slate-800">{target.focal_ra_deg.toFixed(1)}° / {target.focal_dec_deg > 0 ? "+" : ""}{target.focal_dec_deg.toFixed(1)}°</span>
              </div>
              <div className="flex justify-between text-slate-600">
                <span>Ecliptic Latitude:</span>
                <span className="font-bold text-slate-800">{target.ecliptic_lat > 0 ? "+" : ""}{target.ecliptic_lat.toFixed(1)}°</span>
              </div>
            </div>
          </div>

          {/* SGL Focal Image & Optical Parameters */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
              SGL Focal Image Characteristics (at 650 AU)
            </h4>

            <div className="bg-white p-3 rounded-lg border border-slate-200 space-y-1">
              <div className="text-xs text-slate-500">Projected Image Plane Diameter</div>
              <div className="text-2xl font-bold font-mono text-slate-900">
                {(target.d_img_m / 1000).toFixed(2)} ± {(target.d_img_err / 1000).toFixed(2)} <span className="text-sm font-normal">km</span>
              </div>
              <div className="text-[11px] text-slate-400">
                Formed by Einstein deflection <LatexMath math="D_{\rm img} = 2 R_p (z / d_L)" />
              </div>
            </div>

            <div className="bg-white p-3 rounded-lg border border-slate-200 space-y-1">
              <div className="text-xs text-slate-500">Per-Sample SNR (1800 s Dwell, 1m Telescope)</div>
              <div className="text-2xl font-bold font-mono text-blue-600">
                <LatexMath math="\mathrm{SNR_C} =" /> {target.snr_c.toFixed(1)}
              </div>
              <div className="text-[11px] text-slate-400">
                Uncertainty range: [{target.snr_min} - {target.snr_max}] due to star variability
              </div>
            </div>

            <div className="bg-white p-3 rounded-lg border border-slate-200 space-y-1">
              <div className="text-xs text-slate-500">Focal Image Linear Velocity</div>
              <div className="text-xl font-bold font-mono text-slate-800">
                {target.v_img_ms.toFixed(1)} <span className="text-xs font-normal">m/s</span>
              </div>
              <div className="text-[11px] text-slate-400">
                Speed at which the exoplanet image sweeps through deep space
              </div>
            </div>
          </div>

          {/* Propulsion and Flight Budget */}
          <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
              90-Day Focal Track Tracking Requirement
            </h4>

            <div className="bg-white p-3.5 rounded-lg border border-slate-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Required Trajectory Δv (90 days)</span>
                <Rocket size={16} className="text-amber-600" />
              </div>
              <div className="text-2xl font-bold font-mono text-amber-600">
                {target.dv90_kms.toFixed(2)} ± {target.dv90_err.toFixed(2)} <span className="text-sm font-normal">km/s</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-snug">
                As the exoplanet orbits its star, its focal cylinder drifts across space. The spacecraft fleet must fire thrusters to stay centered in the beam.
              </p>
            </div>

            {/* Scale Comparison Bar */}
            <div className="bg-white p-3 rounded-lg border border-slate-200 space-y-2">
              <div className="text-xs font-semibold text-slate-700">Relative Tracking Difficulty:</div>
              <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    target.dv90_kms > 4 ? "bg-rose-500" :
                    target.dv90_kms > 2 ? "bg-amber-500" : "bg-emerald-500"
                  }`}
                  style={{ width: `${Math.min(100, (target.dv90_kms / 6.0) * 100)}%` }}
                />
              </div>
              <div className="flex justify-between text-[10px] font-mono text-slate-400">
                <span>τ Cet e: 0.11 km/s (Easiest)</span>
                <span>Prox b: 5.78 km/s (High)</span>
              </div>
            </div>

            <div className="p-2.5 bg-blue-50/60 rounded border border-blue-100 text-[11px] text-blue-900 leading-snug">
              <strong>Mission Strategy:</strong> Ion propulsion or solar sailing can easily provide up to ~3 km/s Δv, making Ross 128 b, GJ 273 b, and τ Cet e prime first-generation targets!
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
