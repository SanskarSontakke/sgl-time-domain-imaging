"use client";

import React, { useState, useRef, useEffect } from "react";
import { 
  Play, Pause, Download, Maximize2, Sparkles, Video, Image as ImageIcon, 
  Layers, Compass, Zap, ShieldCheck, CheckCircle2, Sliders, ExternalLink, RefreshCw, Eye
} from "lucide-react";
import LatexMath from "./LatexMath";

interface MediaItem {
  id: string;
  type: "video" | "image";
  title: string;
  subtitle: string;
  category: string;
  src: string;
  thumbnail: string;
  badge: string;
  description: string;
  formula?: string;
  stats: { label: string; value: string; desc: string }[];
  keyPoints: string[];
  simulatorTab?: "sandbox" | "einstein" | "fleet" | "cylinder" | "cadence" | "deflation" | "spin" | "targets";
}

const MEDIA_ITEMS: MediaItem[] = [
  {
    id: "vid-planet-rotation",
    type: "video",
    title: "Planetary Rotation & Dynamic Cloud Advection",
    subtitle: "Continuous simulation of a rotating exo-Earth with eastward zonal jet streams and diurnal photometric light curve.",
    category: "Atmospheric Simulation",
    src: "/videos/planet_rotation_clouds.gif",
    thumbnail: "/images/exoearth_cloud_dynamics.jpg",
    badge: "Time-Series Simulation",
    description: "Visualization of the forward physical model this paper inverts: an Earth-analog with a 24.0-hour diurnal period, illuminated by a Lambertian terminator whose sub-stellar longitude drifts 86.1 deg over the 87.33-day fiducial campaign (P_orb = 1 yr). Clouds are an advecting Ornstein-Uhlenbeck field with zonal drift 6 deg/day (~7.7 m/s at the equator) and decorrelation time 4 d. The disk-integrated brightness that each dwell actually records is shown alongside.",
    formula: "F(t) = \\int_{\\text{disk}} A(\\mathbf{r}, t) \\, (\\mathbf{n} \\cdot \\mathbf{s}) \\, d\\Omega",
    stats: [
      { label: "Diurnal Period", value: "P = 24.0 h", desc: "Planet spin rate" },
      { label: "Cloud Cover", value: "f_c = 55%", desc: "Earth-analog fiducial" },
      { label: "Zonal Advection", value: "6°/day", desc: "≈7.7 m/s at equator" },
      { label: "Decorrelation", value: "τ_c = 4 d", desc: "OU cloud memory" }
    ],
    keyPoints: [
      "The sub-stellar latitude is held fixed at the equator: obliquity is deliberately not modeled, and the seasonal intertropical migration that a tilted planet would show is outside the tested regime.",
      "Demonstrates why single-epoch static snapshots fail: clouds mask continents non-uniformly over time.",
      "Disk-integrated cloud fluctuations are coherent across all 16 simultaneous samples, which is exactly the nuisance the slot profiling removes."
    ],
    simulatorTab: "sandbox"
  },
  {
    id: "vid-einstein-ring",
    type: "video",
    title: "SGL Einstein Ring Optical Convolution",
    subtitle: "Azimuthal folding of planetary surface features into a luminous Einstein ring convolved with the 1/ρ point spread function.",
    category: "Optical Physics",
    src: "/videos/einstein_ring_convolution.gif",
    thumbnail: "/images/einstein_ring_view.jpg",
    badge: "SGL Optical Ray-Trace",
    description: "Visualizes the field of view through an internal coronagraph aboard an SGL telescope stationed at 650 AU. The Sun's brilliant disk is occulted by the central coronagraph mask, unveiling the luminous, razor-thin Einstein ring. As the exoplanet rotates, continents and clouds modulate the azimuthal intensity profile I(θ) according to the SGL gravitational kernel — the paper inverts the aperture-averaged form, K(0) = 1 with a d/(4ρ) tail, not the singular point PSF.",
    formula: "K(0)=1, \\quad K(\\rho>0) \\simeq \\frac{d}{4\\rho}, \\quad \\mu_0 \\simeq 1.2\\times10^{11}",
    stats: [
      { label: "Optical Gain", value: "μ₀ ≈ 1.2×10¹¹", desc: "on-axis, λ = 1 μm" },
      { label: "Kernel Scale", value: "K(ρ) ∝ 1/ρ", desc: "aperture-averaged" },
      { label: "Telescope Dist", value: "z = 650 AU", desc: "Focal line station" },
      { label: "Photon SNR", value: "SNR_C = 43.16", desc: "per 1800 s dwell" }
    ],
    keyPoints: [
      "Gravity bends planetary light around the entire solar perimeter into a 360° ring.",
      "Azimuthal angles on the Einstein ring map directly to position angles on the exoplanet.",
      "The 10⁻¹⁰ arcsec figure is the wave-optical kernel scale quoted from the literature. The resolution this paper can actually claim is set by image-plane sampling — one 20.9 m element ≈ 4×10⁻⁸ arcsec — and clouds cut the recovered band at ℓ ≈ 9."
    ],
    simulatorTab: "einstein"
  },
  {
    id: "vid-fleet-raster",
    type: "video",
    title: "Multi-Spacecraft Fleet Formation Scanning",
    subtitle: "16 nano-spacecraft sweeping concurrent tracks across the 1.34 km focal cylinder image plane.",
    category: "Mission Architecture",
    src: "/videos/fleet_raster_scan.gif",
    thumbnail: "/images/sgl_focal_cylinder_diagram.jpg",
    badge: "Fleet Constellation",
    description: "Demonstrates the sampling geometry the paper actually inverts: a 64×64 raster with 20.9 m image-plane pitch inside the 1.34 km focal tube, grouped into 256 dwell slots of 16 simultaneous pixels each, visited M_p = 16 times at t_s = 1800 s. A full pass takes 256 × (1800 + 45) s ≈ 5.5 days, so the fiducial campaign spans 87.33 days of wall clock — 85.33 d of exposure plus 2.00 d of in-window slew, settle and metrology overhead.",
    formula: "\\Delta t_{\\rm pass} = N_{\\rm slot}\\,(t_s + T_{\\rm oh}) = 256 \\times 1845\\,{\\rm s} \\approx 5.5\\text{ days}",
    stats: [
      { label: "Fleet Constellation", value: "16 craft", desc: "One per simultaneous slot pixel" },
      { label: "Cylinder Diameter", value: "1.34 km", desc: "Exo-Earth image size" },
      { label: "Raster Pitch", value: "20.9 m", desc: "≈199 km on the planet" },
      { label: "Cadence Law", value: "saturating in M_p", desc: "N_eff < M_p for OU weather" }
    ],
    keyPoints: [
      "The 16 simultaneous samples of a slot share one common-mode cloud fluctuation; that degeneracy is a rank-1 nuisance per slot, not an extra measurement of the surface.",
      "Wall clock is 87.33 d at M_p = 16, not 90.0 d; the 45 s/dwell overhead ledger is explicit and auditable (30 s slew + 10 s settle + 5 s metrology).",
      "More revisits do not keep paying: at τ_cloud = 4 d the 64 passes deliver only ≈12 effective independent looks."
    ],
    simulatorTab: "fleet"
  },
  {
    id: "vid-tdi-timelapse",
    type: "video",
    title: "TDI Iterative Deconvolution Timelapse",
    subtitle: "Progressive transformation of raw striped barcode measurements into resolved planetary continents.",
    category: "Deconvolution Algorithm",
    src: "/videos/tdi_deconvolution_timelapse.gif",
    thumbnail: "/images/tdi_reconstruction_pipeline.jpg",
    badge: "Algorithmic Convergence",
    description: "Follows the four-stage inversion as the paper defines it: Stage 1 is the raw SGL raster, where a dwell is 7.5° of rotational smear and the cloud term is ~19× the photon noise in σ at the fiducial cover (variance ratio ≈362). Stage 2 removes the per-slot nuisance level by exact profile likelihood over the 256 slot offsets, not by an approximate common-mode subtraction. Stage 3 solves the regularized GLS normal equations with the OU covariance and Tikhonov weight λ = 3×10⁻³. Stage 4 shows fidelity growth as the revisit count rises to M_p = 64, where r saturates rather than continuing to climb.",
    formula: "\\hat{\\mathbf{m}} = (\\mathbf{F}^T \\mathbf{C}_y^{-1} \\mathbf{F} + \\mathbf{\\Lambda})^{-1} \\mathbf{F}^T \\mathbf{C}_y^{-1} \\mathbf{y}",
    stats: [
      { label: "Long-Dwell Baseline", value: "r = 0.049", desc: "M_p = 4, 7200 s dwells (arm A)" },
      { label: "Slot-Profiling Gain", value: "Δr = +0.054", desc: "F−A paired, ±0.006, 10/10 seeds" },
      { label: "Fiducial Recon", value: "r = 0.342", desc: "Realized cover 0.56, M_p = 16" },
      { label: "High Cadence", value: "r = 0.571", desc: "Arm A at M_p = 64 (93.7 d wall)" }
    ],
    keyPoints: [
      "The reconstruction is a regularized GLS solve, not an iterative deconvolution; the figure shows a single linear inverse per dataset.",
      "Slot profiling gains +0.054 in r over a fit that ignores the offsets, but the OU covariance itself adds nothing measurable on top (F−D = −0.003, 6/10 in sign).",
      "Even the best case is continental-scale only: r = 0.342 with SSIM = 0.106 at nominal weather."
    ],
    simulatorTab: "sandbox"
  },
  {
    id: "img-sgl-architecture",
    type: "image",
    title: "Solar Gravitational Lens Optical Architecture",
    subtitle: "Comprehensive 3D diagram of the Sun as a gravitational lens, the 547.8 AU focal-line onset, and the 1.34 km focal tube.",
    category: "Mission Architecture",
    src: "/images/sgl_focal_cylinder_diagram.jpg",
    thumbnail: "/images/sgl_focal_cylinder_diagram.jpg",
    badge: "Mission Diagram",
    description: "Detailed scientific illustration showing an exo-Earth on the left emitting rays toward the Sun. Spacetime curvature focuses these rays along a focal line starting at 547.8 AU and extending beyond 650 AU, creating an image cylinder 1.34 km wide. A 16-spacecraft fleet equipped with solar sails and optical coronagraphs performs raster scanning across the cylinder.",
    formula: "z_0 = \\frac{b^2}{2 r_g} \\approx 547.8\\text{ AU}\\ (b \\simeq R_\\odot), \\qquad r_g = \\frac{2GM_\\odot}{c^2} \\simeq 2.95\\text{ km}",
    stats: [
      { label: "Focal Onset", value: "547.8 AU", desc: "Minimum focal distance" },
      { label: "Operating Station", value: "650 AU", desc: "Operational distance" },
      { label: "Image Cylinder", value: "1.34 km", desc: "Exo-Earth focal diameter" },
      { label: "Light Gain", value: "~10¹¹", desc: "Natural magnification" }
    ],
    keyPoints: [
      "Spacetime acts as a gigantic telescope lens without human-made glass.",
      "The focal line continues indefinitely into deep interstellar space.",
      "Spacecraft formation raster-scans the 1.34 km cylinder to construct the full 2D picture."
    ],
    simulatorTab: "cylinder"
  },
  {
    id: "img-exoearth-dynamics",
    type: "image",
    title: "Exo-Earth Atmospheric Dynamics & Cloud Bands",
    subtitle: "Photorealistic scientific 3D render of Kepler-186f with dynamic cloud bands, diurnal terminator, and light curve telemetry.",
    category: "Atmospheric Simulation",
    src: "/images/exoearth_cloud_dynamics.jpg",
    thumbnail: "/images/exoearth_cloud_dynamics.jpg",
    badge: "Exoplanet Render",
    description: "Illustrative render, not a figure from the paper. The surface the simulation actually uses is a seeded synthetic albedo map on a 144×72 grid: ocean 0.06, continents 0.32 ± 0.10, polar caps up to 0.60, 30% land fraction. Its disk-mean value is normalized to 1, which is why no absolute Bond albedo is reported or needed.",
    formula: "\\frac{\\partial c}{\\partial t} + v_{\\rm adv} \\frac{\\partial c}{\\partial \\phi} = -\\frac{c}{\\tau_c} + \\eta(\\mathbf{r}, t)",
    stats: [
      { label: "Scene Type", value: "synthetic GRF", desc: "seeded albedo map, not Kepler-186f" },
      { label: "Sub-stellar Latitude", value: "0°", desc: "obliquity not modeled" },
      { label: "Surface Albedo", value: "0.06–0.60", desc: "ocean → polar cap" },
      { label: "Zonal Advection", value: "6°/day", desc: "OU cloud drift (fiducial)" }
    ],
    keyPoints: [
      "The paper models a generic Earth-analog at 30 pc; it does not claim a specific planet's climate, so this render is decoration, not a result.",
      "The OU field is parameterized by correlation length 12°, advection 6°/day and decorrelation 4 d — all three are swept in Table 8 of the manuscript.",
      "Time-domain modeling matters because the cloud term is ~19× the photon noise in σ at nominal cover."
    ],
    simulatorTab: "sandbox"
  },
  {
    id: "img-einstein-ring-view",
    type: "image",
    title: "Telescope Coronagraph View of the Einstein Ring",
    subtitle: "High-resolution view through the telescope coronagraph at 650 AU with the Sun blocked by the occulter mask.",
    category: "Optical Physics",
    src: "/images/einstein_ring_view.jpg",
    thumbnail: "/images/einstein_ring_view.jpg",
    badge: "Coronagraph Telemetry",
    description: "Instrument concept for the observation, drawn from the paper's forward model rather than an image of real data. At 650 AU the Sun subtends ~1.5 arcsec; the planet's Einstein ring is focused into the annulus sampled by the 1-m aperture, and the corona that survives coronagraphic rejection sets the noise floor (Q_cor = 6.20×10⁹ photons/s against Q_exo = 8.01×10⁴ for the reference planet). The image-plane grid is the 64×64 raster, 20.9 m pitch.",
    formula: "\\sigma_k=\\frac{\\sqrt{(Q_{\\rm cor}+Q_{\\rm exo}\\bar{s}_k)\\,t_s}}{Q_{\\rm exo}}",
    stats: [
      { label: "Coronal Background", value: "6.2×10⁹ s⁻¹", desc: "after rejection, 1 m @ 650 AU" },
      { label: "Ring Radius (image plane)", value: "669 m", desc: "= D_img/2 at z = 650 AU" },
      { label: "Sampling", value: "64×64 @ 20.9 m", desc: "the inverted measurement raster" },
      { label: "Distance", value: "650 AU", desc: "Spacecraft station" }
    ],
    keyPoints: [
      "Starlight suppression is a mission requirement, not a result of this paper: the noise model simply takes the quoted post-coronagraphy corona rate as input.",
      "The per-sample photon SNR at the fiducial 1800 s dwell is SNR_C = 43.16, reproduced in Figure 2.",
      "Radial distance ρ marks distance from the optical focal axis; K(ρ) = d/(4ρ) for ρ > 0."
    ],
    simulatorTab: "einstein"
  },
  {
    id: "img-tdi-pipeline",
    type: "image",
    title: "TDI Deconvolution Pipeline Architecture",
    subtitle: "End-to-end flowchart from the time-tagged sample stream and slot-offset profiling to the reconstructed planetary surface map.",
    category: "Deconvolution Algorithm",
    src: "/images/tdi_reconstruction_pipeline.jpg",
    thumbnail: "/images/tdi_reconstruction_pipeline.jpg",
    badge: "Algorithm Pipeline",
    description: "Infographic of the inversion flow. Left: the measurement vector y, in which every dwell mixes light from the whole planet through the 1/ρ kernel and carries one shared cloud offset per dwell slot. Center: exact nuisance profiling — the slot offsets α enter through B and are removed by inverting the 256 block-diagonal H_j = B_jᵀC⁻¹B_j of the OU covariance, then re-anchored with Σ_b α_b = 0, giving A = A_free + qqᵀ/S. Right: the regularized GLS solution and its metrics.",
    formula: "\\mathsf{A}=\\mathsf{A}_{\\rm free}+\\mathbf{q}\\mathbf{q}^{\\sf T}/S,\\qquad \\mathbf{q}=\\textstyle\\sum_j \\mathsf{G}_j^{\\sf T}\\mathsf{H}_j^{-1}\\mathbf{1}",
    stats: [
      { label: "Correlation", value: "r = 0.342", desc: "±0.008, realized cover 0.56" },
      { label: "Slot-Profiling Gain", value: "+0.054 Δr", desc: "F−A paired, 10/10 seeds" },
      { label: "Structure SSIM", value: "0.106", desc: "±0.005 at the same cover" },
      { label: "Benchmark SNR", value: "43.16", desc: "per 1800 s dwell" }
    ],
    keyPoints: [
      "Profiling is a rank-one anchored correction, not a plain mean subtraction: v2's approximate deflation is audited and replaced (Section 4.2).",
      "The disk-integrated albedo mode is exactly what profiling preserves; without the anchor it is projected out entirely.",
      "Metrics shown are the archived 10-seed means with ddof=1 standard errors, quoted from results/audit.json."
    ],
    simulatorTab: "deflation"
  },
  {
    id: "img-target-catalog",
    type: "image",
    title: "Prime Habitable Zone Exoplanet Targets for the SGL",
    subtitle: "Comparative cards for the five confirmed nearby systems in Table 2, plus one refuted signal kept only as a dynamics illustration.",
    category: "Exoplanet Targets",
    src: "/images/sgl_target_exoplanets.jpg",
    thumbnail: "/images/sgl_target_exoplanets.jpg",
    badge: "Target Catalog",
    description: "Illustrative artwork — the planets it depicts are not the paper's target list. Table 2 and Figure 8 of the manuscript evaluate five confirmed small planets near or interior to the habitable zone: Proxima Cen b (1.30 pc), Ross 128 b (3.38 pc), GJ 1061 d (3.67 pc), Teegarden c (3.83 pc) and GJ 273 b / Luyten's star (3.80 pc). The sixth row, τ Cet e, is retained only to illustrate low-acceleration tracking; its radial-velocity signal was refuted at 10 cm/s precision by Figueira et al. (2025).",
    formula: "\\Delta v(T)=\\oint \\left|\\mathbf{a}_\\perp(t)\\right|\\,dt,\\qquad \\mathbf{a}_\\perp=-\\frac{GM_\\star}{r^2}\\left(\\cos E-e,\\ \\sin E\\sqrt{1-e^2}\\cos i\\right)",
    stats: [
      { label: "Closest Target", value: "1.30 pc", desc: "Proxima Centauri b" },
      { label: "Confirmed Systems", value: "5", desc: "+1 refuted illustration row" },
      { label: "90-day Tracking Δv", value: "1.34–5.81 km/s", desc: "confirmed rows, face-on" },
      { label: "Worst Case", value: "Proxima b", desc: "5.81 km/s: shortest period, 11.2 d" }
    ],
    keyPoints: [
      "Tracking cost is set by the projected transverse acceleration integrated over the window, so it scales with orbital period, not with distance — hence a factor 53 spread across these rows.",
      "Focal-line ecliptic latitude (0.3°–60.8° here) drives the departure and plane-change cost, which this paper does not attempt to optimize.",
      "τ Cet e is flagged as refuted everywhere it appears; no target claim rests on it."
    ],
    simulatorTab: "targets"
  }
];

export default function DemonstrationMediaCenter({
  onSelectSimulator
}: {
  onSelectSimulator?: (tab: "sandbox" | "einstein" | "fleet" | "cylinder" | "cadence" | "deflation" | "spin" | "targets") => void;
}) {
  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [selectedItem, setSelectedItem] = useState<MediaItem>(MEDIA_ITEMS[0]);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [recordProgress, setRecordProgress] = useState<number>(0);
  const recorderCanvasRef = useRef<HTMLCanvasElement | null>(null);

  const categories = [
    { id: "all", label: `All Demonstration Media (${MEDIA_ITEMS.length})` },
    { id: "video", label: `Simulation Videos (${MEDIA_ITEMS.filter(m => m.type === "video").length})` },
    { id: "image", label: `Mission Architecture (${MEDIA_ITEMS.filter(m => m.type === "image").length})` },
  ];

  const filteredItems = MEDIA_ITEMS.filter(item => {
    if (activeCategory === "all") return true;
    return item.type === activeCategory;
  });

  // Built-in live canvas demonstration recorder (WebM export)
  const startLiveRecording = () => {
    if (isRecording) return;
    setIsRecording(true);
    setRecordProgress(0);

    const canvas = recorderCanvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let stream: MediaStream;
    let recorder: MediaRecorder;
    const chunks: BlobPart[] = [];

    try {
      stream = canvas.captureStream(30);
      recorder = new MediaRecorder(stream, { mimeType: "video/webm" });
    } catch (e) {
      console.warn("MediaRecorder fallback", e);
      // Fallback if mimeType not supported
      try {
        stream = (canvas as any).captureStream(30);
        recorder = new MediaRecorder(stream);
      } catch (err) {
        alert("Video recording is not supported in this browser environment.");
        setIsRecording(false);
        return;
      }
    }

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };

    recorder.onstop = () => {
      const blob = new Blob(chunks, { type: "video/webm" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `sgl_simulation_${selectedItem.id}.webm`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setIsRecording(false);
      setRecordProgress(0);
    };

    recorder.start();

    // 4-second animation recording
    const startTime = performance.now();
    const duration = 4000;

    const renderLoop = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      setRecordProgress(Math.floor(progress * 100));

      // Draw custom animated simulation frame
      const w = canvas.width;
      const h = canvas.height;
      ctx.fillStyle = "#0a0e17";
      ctx.fillRect(0, 0, w, h);

      const t = (elapsed / 1000) * 2 * Math.PI;

      // Draw planetary sphere & rings
      const cx = w / 2;
      const cy = h / 2 - 20;
      const r = 70;

      // Glow
      const grad = ctx.createRadialGradient(cx, cy, r * 0.8, cx, cy, r * 1.3);
      grad.addColorStop(0, "rgba(56, 189, 248, 0.4)");
      grad.addColorStop(1, "rgba(56, 189, 248, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, r * 1.3, 0, Math.PI * 2);
      ctx.fill();

      // Planet disk
      ctx.fillStyle = "#0c4a6e";
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();

      // Continents & clouds
      ctx.fillStyle = "#15803d";
      for (let i = -2; i <= 2; i++) {
        const angle = t + (i * Math.PI) / 2.5;
        const px = cx + Math.cos(angle) * (r * 0.75);
        const py = cy + i * 18;
        if (Math.sin(angle) > -0.2) {
          ctx.beginPath();
          ctx.ellipse(px, py, 24, 14, 0.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Clouds
      ctx.fillStyle = "rgba(240, 249, 255, 0.75)";
      for (let i = -2; i <= 2; i++) {
        const angle = t * 1.3 + (i * Math.PI) / 2;
        const px = cx + Math.cos(angle) * (r * 0.82);
        const py = cy + i * 20 - 5;
        if (Math.sin(angle) > -0.1) {
          ctx.beginPath();
          ctx.ellipse(px, py, 30, 10, -0.1, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      // Telemetry overlay
      ctx.fillStyle = "#38bdf8";
      ctx.font = "bold 13px monospace";
      ctx.fillText(`SGL TIME-DOMAIN IMAGING: ${selectedItem.title.toUpperCase()}`, 20, 30);
      ctx.fillStyle = "#94a3b8";
      ctx.font = "11px monospace";
      ctx.fillText(`TIME: ${(elapsed / 1000).toFixed(2)}s | PROGRESS: ${Math.floor(progress * 100)}% | STATUS: ACTIVE`, 20, 48);

      // Bottom bar
      ctx.fillStyle = "#e2e8f0";
      ctx.font = "11px monospace";
      ctx.fillText("PEER-REVIEWED ASTROPHYSICAL RESEARCH • SONTAKKE (2026) — SINGLE-AUTHOR STUDY", 20, h - 20);

      if (progress < 1) {
        requestAnimationFrame(renderLoop);
      } else {
        recorder.stop();
      }
    };

    requestAnimationFrame(renderLoop);
  };

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <div className="bg-gradient-to-r from-blue-900 via-indigo-900 to-slate-900 text-white rounded-2xl p-5 sm:p-7 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="bg-blue-500/30 text-blue-200 text-[10px] sm:text-xs font-mono font-bold px-2 py-0.5 rounded border border-blue-400/30 flex items-center gap-1">
                <Video size={12} />
                Multi-Media Demonstration Suite
              </span>
              <span className="text-slate-300 text-xs">
                9 High-Definition Assets Ready for Presenters & Judges
              </span>
            </div>
            <h2 className="text-xl sm:text-2xl md:text-3xl font-extrabold tracking-tight">
              Simulation Demonstration Gallery & Video Showcase
            </h2>
            <p className="text-xs sm:text-sm text-slate-300 max-w-2xl leading-relaxed">
              Explore dynamic animated simulation videos, high-resolution 3D optical ray-tracing diagrams, and mathematical deconvolution walkthroughs created to demonstrate the Solar Gravitational Lens project.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              onClick={() => {
                const a = document.createElement("a");
                a.href = selectedItem.src;
                a.download = selectedItem.src.split("/").pop() || "sgl_demo_asset";
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
              }}
              className="btn btn-sm bg-white text-slate-900 hover:bg-blue-50 font-bold text-xs flex items-center gap-1.5 shadow-sm"
            >
              <Download size={14} />
              <span>Download Active Asset</span>
            </button>
          </div>
        </div>

        {/* Filter Categories Bar */}
        <div className="flex items-center gap-2 pt-5 mt-5 border-t border-white/10 flex-wrap">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeCategory === cat.id
                  ? "bg-blue-500 text-white shadow-xs"
                  : "bg-white/10 text-slate-200 hover:bg-white/20"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Featured Active Player & Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 bg-white rounded-2xl border border-slate-200 p-4 sm:p-6 shadow-xs items-start">
        {/* Main Media Preview Canvas */}
        <div className="lg:col-span-7 space-y-3">
          <div className="relative rounded-xl overflow-hidden bg-slate-950 border border-slate-800 aspect-video flex items-center justify-center group shadow-inner">
            <img
              src={selectedItem.src}
              alt={selectedItem.title}
              className="w-full h-full object-contain"
            />

            {/* Badge Pill */}
            <div className="absolute top-3 left-3 bg-slate-900/80 backdrop-blur-md text-white text-[10px] sm:text-xs font-mono font-bold px-2.5 py-1 rounded-md border border-white/10 flex items-center gap-1.5">
              {selectedItem.type === "video" ? <Video size={12} className="text-blue-400" /> : <ImageIcon size={12} className="text-emerald-400" />}
              <span>{selectedItem.badge}</span>
            </div>

            {/* Controls Overlay */}
            <div className="absolute bottom-3 right-3 flex items-center gap-2">
              <button
                onClick={() => setModalOpen(true)}
                className="bg-slate-900/80 hover:bg-slate-900 text-white p-2 rounded-lg border border-white/10 backdrop-blur-md transition-colors"
                title="View Fullscreen"
              >
                <Maximize2 size={14} />
              </button>
              <a
                href={selectedItem.src}
                download
                className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-sm transition-colors"
              >
                <Download size={13} />
                <span>Save</span>
              </a>
            </div>
          </div>

          {/* Quick Recorder Bar for Presenters */}
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
            <div className="flex items-center gap-2 text-slate-700 font-medium">
              <Sparkles size={14} className="text-amber-500" />
              <span>Need a standalone video clip for your presentation slides?</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={startLiveRecording}
                disabled={isRecording}
                className={`btn btn-sm ${
                  isRecording ? "bg-amber-500 text-white" : "btn-primary"
                } text-xs flex items-center gap-1.5 shrink-0 font-bold`}
              >
                <Video size={13} />
                <span>{isRecording ? `Recording (${recordProgress}%)...` : "Export 4s WebM Video"}</span>
              </button>
            </div>
          </div>

          {/* Hidden Canvas for Live Video Recording */}
          <canvas
            ref={recorderCanvasRef}
            width={480}
            height={270}
            className="hidden"
          />
        </div>

        {/* Detailed Explanation & Technical Parameters */}
        <div className="lg:col-span-5 space-y-4">
          <div className="space-y-1.5 border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <span className="badge badge-primary text-[10px] font-bold uppercase">
                {selectedItem.category}
              </span>
              <span className="text-slate-400 text-xs font-mono">
                {selectedItem.type === "video" ? "Animated Simulation Clip" : "High-Resolution Graphic"}
              </span>
            </div>
            <h3 className="text-lg sm:text-xl font-bold text-slate-900 leading-snug">
              {selectedItem.title}
            </h3>
            <p className="text-xs text-slate-500 font-medium">
              {selectedItem.subtitle}
            </p>
          </div>

          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
            {selectedItem.description}
          </p>

          {/* LaTeX Formula Callout */}
          {selectedItem.formula && (
            <div className="bg-blue-50/70 border border-blue-200 rounded-xl p-3 space-y-1">
              <div className="text-[10px] font-bold uppercase text-blue-600 tracking-wider">
                Governing Optical / Algorithmic Equation:
              </div>
              <div className="text-xs sm:text-sm font-semibold text-slate-800 overflow-x-auto py-1">
                <LatexMath math={selectedItem.formula} block />
              </div>
            </div>
          )}

          {/* Key Simulation Parameters Grid */}
          <div className="grid grid-cols-2 gap-2">
            {selectedItem.stats.map((s, idx) => (
              <div key={idx} className="bg-slate-50 p-2.5 rounded-lg border border-slate-200/80">
                <div className="text-[10px] text-slate-400 font-medium truncate">{s.label}</div>
                <div className="text-sm font-bold font-mono text-slate-900 mt-0.5">{s.value}</div>
                <div className="text-[10px] text-slate-500 mt-0.5 truncate">{s.desc}</div>
              </div>
            ))}
          </div>

          {/* Bullet Highlights */}
          <div className="space-y-1.5 pt-1">
            <div className="text-[10px] font-bold uppercase text-slate-400 tracking-wider">
              Demonstration Highlights:
            </div>
            <ul className="space-y-1 text-xs text-slate-600">
              {selectedItem.keyPoints.map((pt, i) => (
                <li key={i} className="flex items-start gap-1.5">
                  <CheckCircle2 size={13} className="text-blue-500 shrink-0 mt-0.5" />
                  <span>{pt}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Link to Interactive Simulator */}
          {selectedItem.simulatorTab && onSelectSimulator && (
            <button
              onClick={() => onSelectSimulator(selectedItem.simulatorTab!)}
              className="w-full btn btn-sm btn-outline text-blue-700 hover:bg-blue-50 border-blue-300 text-xs font-bold flex items-center justify-center gap-1.5 py-2"
            >
              <Sliders size={13} />
              <span>Launch Matching Interactive Simulator ({selectedItem.simulatorTab.toUpperCase()})</span>
              <ExternalLink size={12} />
            </button>
          )}
        </div>
      </div>

      {/* Grid of All Demonstration Media Cards */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="font-bold text-slate-900 text-base flex items-center gap-2">
            <Layers size={18} className="text-blue-600" />
            <span>Demonstration Media Asset Catalog</span>
          </h3>
          <span className="text-xs text-slate-500">
            Click any card to load into the high-resolution inspector above.
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredItems.map((item) => {
            const isSelected = selectedItem.id === item.id;
            return (
              <div
                key={item.id}
                onClick={() => setSelectedItem(item)}
                className={`bg-white rounded-xl border p-3 cursor-pointer transition-all hover:shadow-md space-y-2.5 ${
                  isSelected
                    ? "border-blue-500 ring-2 ring-blue-200 shadow-sm"
                    : "border-slate-200 hover:border-slate-300"
                }`}
              >
                <div className="relative rounded-lg overflow-hidden bg-slate-950 aspect-video flex items-center justify-center border border-slate-800">
                  <img
                    src={item.src}
                    alt={item.title}
                    className="w-full h-full object-cover"
                  />
                  <div className="absolute top-2 left-2 bg-slate-900/80 backdrop-blur-md text-white text-[9px] font-mono font-bold px-2 py-0.5 rounded border border-white/10 flex items-center gap-1">
                    {item.type === "video" ? <Video size={10} className="text-blue-400" /> : <ImageIcon size={10} className="text-emerald-400" />}
                    <span>{item.type.toUpperCase()}</span>
                  </div>
                </div>

                <div className="space-y-1">
                  <div className="text-[10px] uppercase font-bold text-blue-600 tracking-wider">
                    {item.category}
                  </div>
                  <h4 className="font-bold text-slate-900 text-xs sm:text-sm line-clamp-1">
                    {item.title}
                  </h4>
                  <p className="text-[11px] text-slate-500 line-clamp-2 leading-relaxed">
                    {item.subtitle}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-[11px]">
                  <span className="text-slate-400 font-mono text-[10px]">{item.stats[0].value}</span>
                  <span className="text-blue-600 font-bold flex items-center gap-1">
                    <span>Inspect</span>
                    <Eye size={12} />
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Fullscreen Lightbox Modal */}
      {modalOpen && (
        <div 
          className="fixed inset-0 z-50 bg-black/90 backdrop-blur-md flex flex-col items-center justify-center p-4"
          onClick={() => setModalOpen(false)}
        >
          <div 
            className="relative max-w-5xl w-full bg-slate-950 rounded-2xl overflow-hidden border border-slate-800 p-2 space-y-3"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between text-white px-2 pt-2">
              <div className="space-y-0.5">
                <span className="text-xs text-blue-400 font-mono font-bold uppercase">{selectedItem.category}</span>
                <h3 className="font-bold text-base sm:text-lg text-white">{selectedItem.title}</h3>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="btn btn-sm btn-outline text-white border-white/20 hover:bg-white/10 text-xs"
              >
                Close (ESC)
              </button>
            </div>

            <div className="relative aspect-video w-full rounded-xl overflow-hidden bg-black flex items-center justify-center">
              <img
                src={selectedItem.src}
                alt={selectedItem.title}
                className="max-h-full max-w-full object-contain"
              />
            </div>

            <div className="flex items-center justify-between text-xs text-slate-400 px-2 pb-2">
              <span>{selectedItem.subtitle}</span>
              <a
                href={selectedItem.src}
                download
                className="btn btn-sm btn-primary text-xs flex items-center gap-1"
              >
                <Download size={13} />
                <span>Download Asset</span>
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
