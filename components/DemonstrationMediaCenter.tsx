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
    description: "Demonstrates the forward physical model of an Earth-like planet with 23.4° axial tilt rotating with a 24.0-hour diurnal period. Dynamic weather systems advect eastward at +21 m/s across the continental landmasses. The right panel tracks the integrated disk-averaged diurnal light curve F(t), revealing photometric variability driven by cloud masking of dark oceans and bright continents.",
    formula: "F(t) = \\int_{\\text{disk}} A(\\mathbf{r}, t) \\, (\\mathbf{n} \\cdot \\mathbf{s}) \\, d\\Omega",
    stats: [
      { label: "Diurnal Period", value: "P = 24.0 h", desc: "Planet spin rate" },
      { label: "Cloud Cover", value: "f_c = 55%", desc: "Earth-analog fiducial" },
      { label: "Zonal Wind", value: "+21 m/s", desc: "Eastward jet advection" },
      { label: "Axial Obliquity", value: "23.4°", desc: "Seasonal tilt" }
    ],
    keyPoints: [
      "Simulates dynamic cloud evolution with synoptic wave speeds faster than planetary rotation.",
      "Demonstrates why single-epoch static snapshots fail: clouds mask continents non-uniformly over time.",
      "Integrates diurnal light curve with Lambertian host star scattering."
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
    description: "Visualizes the field of view through an internal coronagraph aboard an SGL telescope stationed at 650 AU. The Sun's brilliant disk is occulted by the central coronagraph mask, unveiling the luminous, razor-thin Einstein ring. As the exoplanet rotates, continents and clouds modulate the azimuthal intensity profile I(θ) according to the SGL gravitational kernel.",
    formula: "K(\\rho) = \\frac{d}{4 \\cdot r\\rho}, \\quad \\mu \\sim 10^{11}",
    stats: [
      { label: "Optical Gain", value: "μ ~ 10¹¹", desc: "Natural gravitational boost" },
      { label: "Kernel Scale", value: "K(ρ) ∝ 1/ρ", desc: "Hyperbolic PSF" },
      { label: "Telescope Dist", value: "z = 650 AU", desc: "Focal line station" },
      { label: "Photon SNR", value: "SNR_C = 43.16", desc: "Cloud-free benchmark" }
    ],
    keyPoints: [
      "Gravity bends planetary light around the entire solar perimeter into a 360° ring.",
      "Azimuthal angles on the Einstein ring map directly to position angles on the exoplanet.",
      "The razor-sharp 1/ρ radial decay provides micro-arcsecond spatial resolution."
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
    description: "Demonstrates the concurrent spatial scanning strategy within the 1.34-kilometer focal tube. A constellation of 16 nano-spacecraft flies in synchronized formation, each sweeping an assigned transverse strip at 15 m/s with active laser cross-links. The right telemetry monitors cylinder coverage, accumulating full 64×64 pixel maps in 90 days.",
    formula: "\\Delta t_{\\rm frame} = \\frac{D_{\\rm img}}{N_{\\rm craft} \\cdot v_{\\rm slew}} \\approx 5.6\\text{ hours}",
    stats: [
      { label: "Fleet Constellation", value: "16 Crafts", desc: "Coordinated nano-probes" },
      { label: "Cylinder Diameter", value: "1.34 km", desc: "Exo-Earth image size" },
      { label: "Slew Velocity", value: "15.2 m/s", desc: "Transverse scan speed" },
      { label: "Cadence Law", value: "K^0.26", desc: "Resolution scaling" }
    ],
    keyPoints: [
      "Divides the 1.34 km image plane into 16 parallel tracks, slashing campaign duration by 93%.",
      "Inter-satellite laser telemetry maintains sub-millimeter relative astrometric positioning.",
      "Prevents temporal aliasing by completing each full spatial scan in under 6 hours."
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
    description: "Follows the four-stage TDI mathematical inversion: Stage 1 reveals the raw SGL observation degraded by horizontal diurnal spin stripes and 21:1 cloud noise; Stage 2 applies the projection operator P_perp to cancel common-mode cloud albedo; Stage 3 applies Tikhonov regularization in the spectral domain; Stage 4 demonstrates resolution enhancement as cadence increases to K=64.",
    formula: "\\hat{\\mathbf{m}} = (\\mathbf{F}^T \\mathbf{C}_y^{-1} \\mathbf{F} + \\mathbf{\\Lambda})^{-1} \\mathbf{F}^T \\mathbf{C}_y^{-1} \\mathbf{y}",
    stats: [
      { label: "Initial Fidelity", value: "r = 0.13", desc: "Raw phase-binned" },
      { label: "Deflation Gain", value: "Δr = +0.041", desc: "P_perp operator benefit" },
      { label: "Fiducial Recon", value: "r = 0.334", desc: "At fc = 0.55, K = 8" },
      { label: "High Cadence", value: "r = 0.544", desc: "Cadence Law at K = 64" }
    ],
    keyPoints: [
      "Directly validates how the projection operator eliminates cloud-induced horizontal barcodes.",
      "Recovers continental boundaries with 95% confidence interval [0.027, 0.054].",
      "Demonstrates convergence from noise floor to continental-scale geography."
    ],
    simulatorTab: "sandbox"
  },
  {
    id: "img-sgl-architecture",
    type: "image",
    title: "Solar Gravitational Lens Optical Architecture",
    subtitle: "Comprehensive 3D diagram of the Sun as a gravitational lens, the 547.5+ AU focal line, and the 1.34 km focal tube.",
    category: "Mission Architecture",
    src: "/images/sgl_focal_cylinder_diagram.jpg",
    thumbnail: "/images/sgl_focal_cylinder_diagram.jpg",
    badge: "Mission Diagram",
    description: "Detailed scientific illustration showing an exo-Earth on the left emitting rays toward the Sun. Spacetime curvature focuses these rays along a focal line starting at 547.5 AU and extending beyond 650 AU, creating an image cylinder 1.34 km wide. A 16-spacecraft fleet equipped with solar sails and optical coronagraphs performs raster scanning across the cylinder.",
    formula: "z_0 = \\frac{R_\\odot^2}{2 r_g} \\approx 547.5\\text{ AU}, \\quad r_g = \\frac{2GM_\\odot}{c^2}",
    stats: [
      { label: "Focal Onset", value: "547.5 AU", desc: "Minimum focal distance" },
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
    description: "Photorealistic visualization of a habitable exo-Earth exhibiting realistic atmospheric circulation. Zonal jet streams drive dynamic cloud bands eastward, masking continental landmasses and deep ocean basins. Inset shows the Bond albedo time-series curve and rotation axis tilt (23.4°).",
    formula: "\\frac{\\partial c}{\\partial t} + v_{\\rm zonal} \\frac{\\partial c}{\\partial \\phi} = \\mathcal{S}(\\mathbf{r}, t)",
    stats: [
      { label: "Target Planet", value: "Kepler-186f", desc: "Habitable-zone analog" },
      { label: "Axial Tilt", value: "23.4°", desc: "Rotation axis obliquity" },
      { label: "Bond Albedo", value: "0.28 - 0.35", desc: "Dynamic variability" },
      { label: "Zonal Drift", value: "+21 m/s", desc: "Atmospheric circulation" }
    ],
    keyPoints: [
      "Visualizes the physical origin of the cloud-to-photon noise ratio (21:1).",
      "Depicts day/night terminator with realistic Rayleigh atmospheric scattering.",
      "Demonstrates why time-domain modeling is essential for moving atmospheres."
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
    description: "Astrophysical instrument simulation from 650 AU in deep space. An internal coronagraph occulter disk blocks the direct blinding sunlight, exposing the delicate solar corona and the luminous blue Einstein ring of the exoplanet. Includes polar coordinate degree markings (0°–360°) and the SGL point spread function kernel formula.",
    formula: "K(\\rho) = \\frac{d}{4 \\cdot r\\rho}",
    stats: [
      { label: "Occulter Attenuation", value: "10⁻¹⁰", desc: "Starlight suppression" },
      { label: "Ring Radius", value: "θ_E ≈ 1.7 arcsec", desc: "Angular Einstein radius" },
      { label: "Azimuthal Bins", value: "360°", desc: "Full perimeter mapping" },
      { label: "Distance", value: "650 AU", desc: "Spacecraft station" }
    ],
    keyPoints: [
      "Starlight is suppressed by 10 orders of magnitude using an internal occulter.",
      "The razor-thin ring concentrates photons from across the entire planetary disk.",
      "Radial distance rho marks the distance from the optical optical focal axis."
    ],
    simulatorTab: "einstein"
  },
  {
    id: "img-tdi-pipeline",
    type: "image",
    title: "TDI Deconvolution Pipeline Architecture",
    subtitle: "End-to-end flowchart from observation phase and cloud deflation to reconstructed planetary surface map.",
    category: "Deconvolution Algorithm",
    src: "/images/tdi_reconstruction_pipeline.jpg",
    thumbnail: "/images/tdi_reconstruction_pipeline.jpg",
    badge: "Algorithm Pipeline",
    description: "Comprehensive infographic detailing the TDI deconvolution pipeline. On the left: observation phase with cloud interference creating a striped barcode measurement vector y. Center: the mathematical inversion engine applying generalized least squares with projection operator P_perp. Right: the reconstructed surface map with recovered continents and peer-reviewed metrics.",
    formula: "(\\mathbf{F}^T \\mathbf{C}_y^{-1} \\mathbf{F} + \\mathbf{\\Lambda})^{-1} \\mathbf{F}^T \\mathbf{C}_y^{-1} \\mathbf{y}, \\quad \\mathbf{P}_\\perp = \\mathbf{I} - \\frac{1}{N_c}\\mathbf{1}\\mathbf{1}^T",
    stats: [
      { label: "Correlation", value: "r = 0.334", desc: "Fiducial recovery" },
      { label: "Deflation Gain", value: "+0.041 Δr", desc: "Cloud removal boost" },
      { label: "Structure SSIM", value: "0.109", desc: "Structural similarity" },
      { label: "Benchmark SNR", value: "43.16", desc: "Cloud-free SNR" }
    ],
    keyPoints: [
      "Defines the exact mathematical steps executed by the TDI algorithm.",
      "Illustrates how common-mode cloud noise is projected out along the scan axis.",
      "Highlights the verified peer-reviewed performance benchmarks."
    ],
    simulatorTab: "deflation"
  },
  {
    id: "img-target-catalog",
    type: "image",
    title: "Prime Habitable Zone Exoplanet Targets for the SGL",
    subtitle: "Comparative telemetry cards and habitability indices for Proxima b, TRAPPIST-1e, Kepler-186f, and key systems.",
    category: "Exoplanet Targets",
    src: "/images/sgl_target_exoplanets.jpg",
    thumbnail: "/images/sgl_target_exoplanets.jpg",
    badge: "Target Catalog",
    description: "Infographic comparing six primary habitable zone exoplanet targets accessible by the SGL mission: Proxima Centauri b (1.3 pc), TRAPPIST-1e (12.1 pc), Kepler-186f (178 pc), LHS 1140 b (15 pc), Ross 128 b (3.4 pc), and Wolf 1061 c (4.3 pc). Displays distance, planetary radius, equilibrium temperature, and required spacecraft slew velocity Delta-v.",
    formula: "\\Delta v_{90} = \\frac{D_{\\rm img}}{\\Delta t_{90}} \\approx 0.17\\text{--}3.2\\text{ km/s}",
    stats: [
      { label: "Closest Target", value: "1.3 pc", desc: "Proxima Centauri b" },
      { label: "Trappist Target", value: "12.1 pc", desc: "TRAPPIST-1e" },
      { label: "Habitable Targets", value: "6 Systems", desc: "Cataloged in paper" },
      { label: "Slew Feasibility", value: "Δv < 3 km/s", desc: "Solar sail reachable" }
    ],
    keyPoints: [
      "Evaluates target distance vs required transverse delta-v for focal tube tracking.",
      "Proxima Centauri b offers the highest photon flux due to its 1.3 pc proximity.",
      "TRAPPIST-1e offers an Earth-sized rocky world orbiting an ultra-cool dwarf star."
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
      ctx.fillText("PEER-REVIEWED ASTROPHYSICAL RESEARCH • SONTANKE ET AL. (2026)", 20, h - 20);

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
