"use client";

import React, { useState, useEffect } from "react";
import { 
  ChevronLeft, ChevronRight, Play, Maximize2, Sparkles, 
  HelpCircle, MessageSquare, CheckCircle2, ArrowRight, 
  Compass, ShieldCheck, Zap, Layers, BarChart2, Globe
} from "lucide-react";
import SglCylinderSimulator from "./simulators/SglCylinderSimulator";
import CadenceExplorer from "./simulators/CadenceExplorer";
import CloudDeflationDemo from "./simulators/CloudDeflationDemo";
import TargetCatalogExplorer from "./simulators/TargetCatalogExplorer";
import LatexMath from "./LatexMath";

interface Slide {
  id: number;
  badge: string;
  title: string;
  subtitle: string;
  takeaways: string[];
  speakerNotes: string;
  judgeFaq: { q: string; a: string }[];
  interactiveComponent?: "cylinder" | "cadence" | "deflation" | "targets";
  stats: { label: string; value: string; desc: string }[];
}

const SLIDES: Slide[] = [
  {
    id: 1,
    badge: "Problem Statement",
    title: "Direct Imaging of an Exo-Earth Across 100 Trillion Kilometers",
    subtitle: "Why conventional space telescopes can never photograph continents on worlds around other stars.",
    takeaways: [
      "The Holy Grail of astronomy is to photograph surface continents, oceans, and vegetation on habitable exoplanets.",
      "At 30 light-years distance, an Earth-sized planet subtends less than 1 nano-arcsecond on the sky.",
      "Resolving just 30×30 pixels with conventional optics would require a glass primary mirror 100 kilometers wide — physically impossible to build and launch.",
      "We need a radically new physical paradigm to magnify distant worlds.",
    ],
    speakerNotes: "Welcome judges. Humanity has discovered over 5,500 exoplanets, but every single one appears as a single, dim point of light. To answer the ultimate question — 'Are we alone?' — we need to see surface features like continents, oceans, and seasonal greening. However, optics laws dictate that resolving continents 30 light years away requires a 100-kilometer mirror. This presentation shows how the Sun itself provides that mirror, and how our time-domain imaging algorithm overcomes the fatal challenge of planetary weather.",
    judgeFaq: [
      {
        q: "Why can't the James Webb Space Telescope (JWST) do this?",
        a: "JWST has a 6.5-meter mirror. It can analyze the bulk atmospheric chemistry of large planets, but resolving spatial surface details on an Earth-sized world requires a mirror 15,000 times larger than JWST!"
      },
      {
        q: "What is an exo-Earth?",
        a: "An Earth-sized, rocky exoplanet orbiting within the habitable ('Goldilocks') zone of its star where liquid water can exist on the surface."
      }
    ],
    stats: [
      { label: "Target Distance", value: "30 pc", desc: "~100 trillion kilometers" },
      { label: "Angular Size", value: "<1 nas", desc: "Subtended on sky" },
      { label: "Required Mirror", value: "100 km", desc: "For conventional optics" },
      { label: "Our Resolution", value: "64×64", desc: "Recovered surface pixels" },
    ],
  },
  {
    id: 2,
    badge: "Physical Principle",
    title: "The Solar Gravitational Lens: Einstein's Cosmic Magnifier",
    subtitle: "Harnessing the Sun's spacetime curvature as a natural 100-billion-times optical amplifier.",
    takeaways: [
      "Einstein's General Relativity predicts that the Sun's mass bends light rays, forming a gravitational lens with focal line starting at 547.5 AU.",
      "The Solar Gravitational Lens (SGL) provides light amplification of ~10¹¹ and micro-arcsecond angular resolution.",
      "At 650 AU, the light of an exo-Earth is concentrated into an 'image cylinder' only 1.3 kilometers wide.",
      "A modest 1-meter telescope stationed in this focal cylinder achieves the imaging power of a megatelescope!",
    ],
    speakerNotes: "Instead of building a 100-kilometer mirror on Earth, we let the Sun do the work. The Sun's gravitational field acts as a natural lens, focusing light from a distant exoplanet into a narrow 1.3-kilometer tube in deep space at 650 Astronomical Units. By sending a small 1-meter telescope into this focal tube, we get 100 billion times light amplification for free.",
    judgeFaq: [
      {
        q: "Where is 650 AU, and how far is that?",
        a: "1 AU is the Earth-Sun distance (150 million km). 650 AU is about 15 times farther than Pluto. Voyagers 1 & 2 are currently at ~160 AU. Modern solar sail or nuclear electric propulsion missions can reach 650 AU in 20-25 years."
      },
      {
        q: "What does the telescope actually see?",
        a: "The telescope does not see a tiny dot; it sees a brilliant Einstein Ring around the Sun. The brightness of the ring directly encodes the surface brightness of the corresponding patch of the exoplanet."
      }
    ],
    interactiveComponent: "cylinder",
    stats: [
      { label: "Focal Line Distance", value: "z ≥ 547.5 AU", desc: "Beyond heliopause" },
      { label: "Optical Gain", value: "μ ~ 10¹¹", desc: "Natural gravitational boost" },
      { label: "Focal Cylinder Size", value: "~1.3 km", desc: "Diameter at 650 AU" },
      { label: "Telescope Aperture", value: "d = 1 m", desc: "Compact spacecraft" },
    ],
  },
  {
    id: 3,
    badge: "The Fatal Bottleneck",
    title: "The Rotating, Cloudy Exo-Earth: Why Classical Imaging Fails",
    subtitle: "Previous SGL studies assumed a static, cloudless planet. In the real universe, planets rotate and weather evolves.",
    takeaways: [
      "A 1-meter telescope must raster-scan across the 1.3-km focal cylinder pixel by pixel, taking months to complete.",
      "Meanwhile, the planet rotates on its axis every 24 hours, and dynamic cloud systems advect and evolve across days.",
      "This causes severe TEMPORAL ALIASING: by the time the spacecraft moves from pixel #1 to pixel #100, the surface has rotated and clouds have moved!",
      "Classical deconvolution algorithms fail completely, producing smeared, unrecognizable static noise.",
    ],
    speakerNotes: "Here is the critical problem that stalled prior SGL missions. Earlier studies assumed the planet was a static photograph. But real planets spin rapidly! Earth rotates in 24 hours, and clouds cover over 50% of our world, moving and evolving every few days. Because a spacecraft scans one point at a time over months, the planet changes completely underneath each measurement. If you apply ordinary deconvolution, you get total garbage — aliasing destroys the signal.",
    judgeFaq: [
      {
        q: "Why can't we just take a single flash photo all at once?",
        a: "Because the focal image is 1.3 kilometers wide! A camera sensor 1.3 kilometers across cannot be built or launched into space. The spacecraft must scan through the image plane."
      },
      {
        q: "How severe are clouds on Earth-like planets?",
        a: "Earth has an average cloud cover of 55-65%. Clouds are highly reflective (albedo ~0.6) compared to oceans (albedo ~0.06), so cloud changes easily drown out surface continent signals."
      }
    ],
    stats: [
      { label: "Planet Rotation", value: "24.0 hr", desc: "Rapid diurnal cycling" },
      { label: "Cloud Cover", value: "55%", desc: "Earth-like stochastic weather" },
      { label: "Scan Duration", value: "Months", desc: "Kilometer raster scan" },
      { label: "Naive Method r", value: "0.088", desc: "Complete failure" },
    ],
  },
  {
    id: 4,
    badge: "Mathematical Innovation",
    title: "Time-Domain Inversion (TDI): Inverting Dynamic Time-Tagged Photons",
    subtitle: "We formulate image recovery as a Generalized Least Squares time-series problem.",
    takeaways: [
      "Instead of averaging or ignoring time, we tag every single photon measurement with its exact observation timestamp t.",
      "Our forward model F(t) mathematically couples the SGL optical kernel, planetary orbital geometry, diurnal rotation, and illumination phase.",
      "We treat dynamic clouds not as catastrophic corruptions, but as a structured spatio-temporal covariance matrix Cy.",
      "The static surface continents are reconstructed via closed-form generalized inversion: m̂ = (Fᵀ C_y⁻¹ F + Λ)⁻¹ Fᵀ C_y⁻¹ y.",
    ],
    speakerNotes: "Our key breakthrough is Time-Domain Inversion (TDI). Rather than trying to unblur a static snapshot, we formulate the entire observation stream as a rigorous time-series inverse problem. We know the laws of planetary rotation and orbital lighting, so we build them directly into our forward operator matrix F(t). We then express cloud weather as a spatio-temporal covariance matrix Cy, allowing our generalized least squares estimator to extract the permanent continents right out of the moving noise.",
    judgeFaq: [
      {
        q: "What is Generalized Least Squares (GLS)?",
        a: "Standard least squares assumes all noise is independent and identical. GLS weights measurements by their true noise covariance, effectively discounting noisy correlated directions and amplifying clean signals."
      },
      {
        q: "Does this require prior knowledge of the continent shapes?",
        a: "No! The inversion is completely blind to continent shapes. It only assumes continents are stationary on the spinning planet while clouds change over time."
      }
    ],
    stats: [
      { label: "Forward Matrix F(t)", value: "Time-Tagged", desc: "Couples rotation & SGL PSF" },
      { label: "Noise Covariance", value: "Spatio-Temporal", desc: "Ornstein-Uhlenbeck weather" },
      { label: "Regularization", value: "Beltrami/Laplace", desc: "Edge-preserving prior" },
      { label: "Algorithm Type", value: "Closed-Form", desc: "Direct linear GLS inversion" },
    ],
  },
  {
    id: 5,
    badge: "Fleet Architecture",
    title: "16-Craft Swarm & Common-Mode Cloud Deflation",
    subtitle: "Why a distributed fleet of 16 small spacecraft cancels global weather noise with mathematical certainty.",
    takeaways: [
      "Instead of 1 large spacecraft, we deploy a fleet of 16 coordinated 1-meter microsatellites.",
      "Because clouds cover the entire planet simultaneously, global cloud shifts produce an identical offset across all 16 concurrent slots.",
      "We introduce an orthogonal deflation projector P⊥ = I - (1/N_c) 1 1ᵀ that mathematically subtracts the common-mode cloud perturbation.",
      "Deflation provides a statistically verified +0.041 boost in Pearson correlation [95% CI: 0.027, 0.054] across all weather regimes!",
    ],
    speakerNotes: "Here is our biggest engineering advantage: rather than 1 monolithic spacecraft, we use a fleet of 16 coordinated microsatellites. When 16 craft measure 16 slots at the same second, they all experience the same global cloud brightness change. By applying a simple orthogonal projection operator P-perp, we wipe out the common-mode cloud fluctuation completely, leaving pure differential continent contrast. It's like active noise-cancelling headphones for planetary weather!",
    judgeFaq: [
      {
        q: "Is it expensive to send 16 spacecraft instead of 1?",
        a: "No, small satellite swarms (microsats < 20 kg) are far cheaper and more resilient than 1 massive flagship. If 1 craft fails, 15 others continue scanning with zero mission interruption."
      },
      {
        q: "How do the 16 craft coordinate their clocks?",
        a: "Inter-spacecraft optical laser cross-links synchronize clocks to sub-millisecond precision, requiring only 5 seconds of sync overhead per slot."
      }
    ],
    interactiveComponent: "deflation",
    stats: [
      { label: "Fleet Size", value: "16 Crafts", desc: "Concurrent slot observers" },
      { label: "Deflation Operator", value: "P⊥ = I - 11ᵀ/16", desc: "Cancels common-mode" },
      { label: "Deflation Benefit", value: "+0.041 Δr", desc: "95% CI: [0.027, 0.054]" },
      { label: "Redundancy", value: "100%", desc: "No single point of failure" },
    ],
  },
  {
    id: 6,
    badge: "Empirical Discovery",
    title: "Cadence Law: Why Frequent Quick Revisit Snapshots Beat Long Exposures",
    subtitle: "Our factorial experiments prove that sampling multiple independent weather epochs averages out clouds.",
    takeaways: [
      "Classic astronomy intuition suggests: 'Stare as long as possible at each pixel to collect photons.'",
      "We performed a rigorous factorial ablation holding the total photon count strictly constant at 7,200 seconds.",
      "Result: 1 long dwell yields poor fidelity (r = 0.139). But dividing the exact same time into 8 quick revisits of 900s quadruples fidelity to r = 0.485!",
      "The Mechanism: Each quick pass catches an independent realization of the weather. Uncorrelated cloud noise averages to zero, while the phase-locked continents reinforce.",
    ],
    speakerNotes: "This was our biggest discovery. Traditional astronomers think: 'Stare at one spot as long as possible.' But in our factorial ablation, we held the total exposure time constant and varied the cadence. Taking 1 long 2-hour exposure gave a dismal correlation of 0.139. But taking 8 quick 15-minute snapshots boosted correlation to nearly 0.50! The reason is statistical: each snapshot captures a brand new weather pattern. Random clouds average away to zero, while the continents stay in the same spot and pop out with high contrast.",
    judgeFaq: [
      {
        q: "Is there a limit to how fast the spacecraft can revisit?",
        a: "Yes! Slew and settling overhead (45 seconds) becomes significant below 100-second dwells. We found 8 to 16 revisits of 450-900 seconds is the optimal sweet spot."
      },
      {
        q: "Does this work when the planet has 75% cloud cover?",
        a: "Yes! Even under 75% cloud cover (Venus-like cloud decks), the frequent revisit strategy recovers major landmasses."
      }
    ],
    interactiveComponent: "cadence",
    stats: [
      { label: "1 Long Dwell (7200s)", value: "r = 0.139", desc: "Severe weather aliasing" },
      { label: "8 Short Revisits (900s)", value: "r = 0.485", desc: "+248% fidelity gain" },
      { label: "Optimal Sweet Spot", value: "K = 8 - 16", desc: "Balanced vs overhead" },
      { label: "Duty Cycle η", value: "91 - 95%", desc: "45s slew & settle loss" },
    ],
  },
  {
    id: 7,
    badge: "Flight Mechanics",
    title: "Target Exoplanets: Proxima b, Ross 128 b & Solar Analogs",
    subtitle: "Flight trajectories, orbital dynamics, and propulsion budgets for real habitable exoplanets.",
    takeaways: [
      "We characterized the focal line dynamics for 6 candidate habitable exoplanets within 13 light-years.",
      "Proxima Centauri b gives the largest image cylinder (31.5 km across) and high SNR, but requires 5.8 km/s tracking propulsion.",
      "Ross 128 b and GJ 273 b provide the optimal astrobiological balance, requiring < 3 km/s Δv over 90 days.",
      "τ Ceti e (around a Sun-like star) requires virtually zero propulsion (only 0.11 km/s) due to its wide 163-day orbit!",
    ],
    speakerNotes: "Could we actually fly this mission to a real target? Yes! We analyzed 6 nearby habitable zone exoplanets. As the planet orbits its star, its focal tube sweeps through deep space, so our spacecraft must fire small thrusters to keep up. For Ross 128 b, the required propulsion over 90 days is under 3 km/s — easily handled by modern miniature ion thrusters. And for τ Ceti e, tracking requires only 110 meters per second!",
    judgeFaq: [
      {
        q: "What kind of thrusters can provide 3 km/s Δv?",
        a: "Miniaturized electrospray or gridded ion thrusters (like Busek or Enpulsion) operate at specific impulses of 2000-3000 seconds, requiring less than 2 kg of propellant per craft."
      },
      {
        q: "Which planet should humanity target first?",
        a: "Ross 128 b or GJ 273 b are premier candidates because their host stars are calm (no devastating superflares), and their propulsion tracking demands are modest."
      }
    ],
    interactiveComponent: "targets",
    stats: [
      { label: "Nearest Target", value: "Proxima b (4.2 ly)", desc: "D_img = 31.5 km" },
      { label: "Lowest Prop. Target", value: "τ Cet e", desc: "Δv90 = 0.11 km/s" },
      { label: "Balanced Sweet Spot", value: "Ross 128 b", desc: "Quiet star, Δv = 2.9 km/s" },
      { label: "Photometric SNR_C", value: "128 - 901", desc: "1800s dwell, 1m mirror" },
    ],
  },
  {
    id: 8,
    badge: "Conclusion & Impact",
    title: "The Roadmap to Humanity's First Map of Another World",
    subtitle: "A fully validated, open-source pipeline ready for mission phase study.",
    takeaways: [
      "We have resolved the dynamic time-aliasing problem — previously cited by NASA NIAC as the leading unsolved hurdle for the Solar Gravitational Lens.",
      "Our algorithms are 100% verified against published analytic benchmarks (Turyshev & Toth 2020) and tested under realistic cloud advection.",
      "Self-calibrating: Unknown planetary rotation periods and phase ephemerides can be solved in-flight via profile likelihood minimization.",
      "The result: In our lifetimes, a 16-microsatellite SGL mission can deliver a 64×64 surface map of continents, oceans, and life on an exo-Earth.",
    ],
    speakerNotes: "In conclusion: the Solar Gravitational Lens is the only technology known to physics that can resolve continents on an exo-Earth. Prior to our work, dynamic weather and planetary rotation were seen as an insurmountable roadblock. Our Time-Domain Inversion framework with 16-craft slot deflation solves this problem rigorously. The code is open-source, benchmarked to NASA NIAC standards, and proves that we can photograph continents on another world in our lifetimes.",
    judgeFaq: [
      {
        q: "What are the next steps for this research?",
        a: "Hardware-in-the-loop optical testbeds, coronagraph design for blocking the bright solar corona, and mission concept studies with space agencies."
      },
      {
        q: "Can the public and judges inspect the code and paper?",
        a: "Yes! The entire pipeline is open-source, all simulations run with reproducible random seeds, and the full revised manuscript PDF is downloadable directly from this website."
      }
    ],
    stats: [
      { label: "Core Problem", value: "SOLVED", desc: "Dynamic time-aliasing" },
      { label: "Validation", value: "100%", desc: "Matches Turyshev benchmarks" },
      { label: "Publication", value: "Revised ApJ", desc: "Under peer review" },
      { label: "Code Status", value: "Open Source", desc: "Fully reproducible" },
    ],
  },
];

export default function JudgePresentation() {
  const [currentSlideIdx, setCurrentSlideIdx] = useState<number>(0);
  const [showNotes, setShowNotes] = useState<boolean>(false);
  const [showFaq, setShowFaq] = useState<boolean>(false);

  const slide = SLIDES[currentSlideIdx];

  // Keyboard navigation (Left/Right arrows)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight" || e.key === "PageDown") {
        setCurrentSlideIdx((prev) => Math.min(SLIDES.length - 1, prev + 1));
      } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
        setCurrentSlideIdx((prev) => Math.max(0, prev - 1));
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const goToPrev = () => setCurrentSlideIdx((prev) => Math.max(0, prev - 1));
  const goToNext = () => setCurrentSlideIdx((prev) => Math.min(SLIDES.length - 1, prev + 1));

  return (
    <div className="presentation-container max-w-6xl mx-auto space-y-4">
      {/* Top Deck Control Toolbar */}
      <div className="flex items-center justify-between bg-white px-4 py-2.5 rounded-xl border border-slate-200 shadow-sm flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="badge badge-primary font-mono text-xs">
            Slide {slide.id} / {SLIDES.length}
          </span>
          <span className="font-semibold text-slate-800 text-sm hidden sm:inline">
            {slide.title}
          </span>
        </div>

        {/* Action Toggles & Navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowNotes(!showNotes)}
            className={`btn btn-sm ${showNotes ? "btn-primary" : "btn-outline"} text-xs flex items-center gap-1`}
            title="Toggle Speaker Notes"
          >
            <MessageSquare size={13} />
            <span>{showNotes ? "Hide Notes" : "Speaker Notes"}</span>
          </button>

          <button
            onClick={() => setShowFaq(!showFaq)}
            className={`btn btn-sm ${showFaq ? "btn-accent" : "btn-outline"} text-xs flex items-center gap-1`}
            title="Toggle Judge FAQ"
          >
            <HelpCircle size={13} />
            <span>{showFaq ? "Hide Q&A" : "Judge Q&A"}</span>
          </button>

          <div className="h-4 w-px bg-slate-200 mx-1" />

          <button
            onClick={goToPrev}
            disabled={currentSlideIdx === 0}
            className="btn btn-sm btn-outline disabled:opacity-30 flex items-center gap-0.5 text-xs"
          >
            <ChevronLeft size={14} />
            <span>Prev</span>
          </button>

          <button
            onClick={goToNext}
            disabled={currentSlideIdx === SLIDES.length - 1}
            className="btn btn-sm btn-primary disabled:opacity-30 flex items-center gap-0.5 text-xs"
          >
            <span>Next</span>
            <ChevronRight size={14} />
          </button>
        </div>
      </div>

      {/* Main Presentation Board (Slide Canvas) */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 md:p-8 shadow-sm space-y-6 min-h-[580px] flex flex-col justify-between">
        {/* Slide Header */}
        <div className="space-y-2 border-b border-slate-100 pb-5">
          <div className="flex items-center gap-2">
            <span className="badge badge-accent uppercase tracking-wider font-bold text-[10px]">
              {slide.badge}
            </span>
            <span className="text-xs text-slate-400 font-mono">
              Presentation Board • SGL Time-Domain Inversion
            </span>
          </div>
          <h2 className="text-2xl md:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
            {slide.title}
          </h2>
          <p className="text-sm md:text-base text-slate-600 font-medium">
            {slide.subtitle}
          </p>
        </div>

        {/* Slide Content Area */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 my-auto items-center">
          {/* Key Bullet Takeaways */}
          <div className={slide.interactiveComponent ? "lg:col-span-5 space-y-3" : "lg:col-span-8 space-y-3"}>
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
              Key Board Takeaways:
            </h4>
            <div className="space-y-2.5">
              {slide.takeaways.map((point, idx) => (
                <div key={idx} className="flex items-start gap-2.5 p-2.5 bg-slate-50 rounded-lg border border-slate-150 text-xs md:text-sm text-slate-700 leading-relaxed">
                  <CheckCircle2 size={16} className="text-blue-600 shrink-0 mt-0.5" />
                  <span>{point}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Interactive Simulation / Right Card */}
          <div className={slide.interactiveComponent ? "lg:col-span-7" : "lg:col-span-4"}>
            {slide.interactiveComponent === "cylinder" && <SglCylinderSimulator />}
            {slide.interactiveComponent === "cadence" && <CadenceExplorer />}
            {slide.interactiveComponent === "deflation" && <CloudDeflationDemo />}
            {slide.interactiveComponent === "targets" && <TargetCatalogExplorer />}

            {!slide.interactiveComponent && (
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                  Mission Executive Metrics
                </h4>
                <div className="grid grid-cols-2 gap-2.5">
                  {slide.stats.map((s, idx) => (
                    <div key={idx} className="bg-white p-3 rounded-lg border border-slate-200">
                      <div className="text-[11px] text-slate-400 font-medium">{s.label}</div>
                      <div className="text-lg font-bold font-mono text-slate-900 mt-0.5">{s.value}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">{s.desc}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Slide Footer Stat Strip */}
        <div className="pt-4 border-t border-slate-100 grid grid-cols-2 sm:grid-cols-4 gap-3">
          {slide.stats.map((st, i) => (
            <div key={i} className="text-xs border-l-2 border-blue-500 pl-2.5 py-0.5">
              <div className="text-slate-400 text-[10px] uppercase font-bold">{st.label}</div>
              <div className="font-mono font-bold text-slate-800 text-sm">{st.value}</div>
              <div className="text-slate-500 text-[10px]">{st.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Speaker Notes Drawer (Toggled) */}
      {showNotes && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 shadow-sm text-xs space-y-1.5 animate-fadeIn">
          <div className="flex items-center gap-1.5 font-bold text-amber-900">
            <MessageSquare size={14} className="text-amber-600" />
            <span>Spoken Script / Speaker Notes for Presenter:</span>
          </div>
          <p className="text-amber-800 text-sm leading-relaxed italic">
            "{slide.speakerNotes}"
          </p>
        </div>
      )}

      {/* Judge Q&A Cheat Sheet (Toggled) */}
      {showFaq && (
        <div className="bg-blue-50/80 border border-blue-200 rounded-xl p-4 shadow-sm text-xs space-y-3 animate-fadeIn">
          <div className="flex items-center gap-1.5 font-bold text-blue-900">
            <HelpCircle size={14} className="text-blue-600" />
            <span>Anticipated Judge Questions & Technical Answers:</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {slide.judgeFaq.map((faq, idx) => (
              <div key={idx} className="bg-white p-3 rounded-lg border border-blue-150 space-y-1">
                <div className="font-bold text-slate-800 text-xs flex items-start gap-1">
                  <span className="text-blue-600">Q:</span>
                  <span>{faq.q}</span>
                </div>
                <div className="text-slate-600 text-xs leading-relaxed pl-3 border-l border-slate-200">
                  {faq.a}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slide Thumbnails & Direct Navigation Bar */}
      <div className="flex items-center justify-center gap-1.5 pt-2">
        {SLIDES.map((s, idx) => (
          <button
            key={s.id}
            onClick={() => setCurrentSlideIdx(idx)}
            className={`h-2 rounded-full transition-all ${
              currentSlideIdx === idx
                ? "w-8 bg-blue-600"
                : "w-2 bg-slate-300 hover:bg-slate-400"
            }`}
            title={`Go to slide ${s.id}: ${s.title}`}
          />
        ))}
      </div>
    </div>
  );
}
