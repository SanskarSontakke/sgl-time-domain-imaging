const fs = require('fs');
const path = require('path');
const SimpleGifEncoder = require('./test_gif');

// Load truth and reconstruction map data
const rawData = JSON.parse(fs.readFileSync('public/data/reconstruction_maps.json', 'utf8'));
const naturalTruth = rawData.natural_truth; // 64x64 [r,g,b]
const fiducialNatural = rawData.gls_natural.fc_3; // 64x64 [r,g,b] at fc=0.55
const whiteNoiseNatural = rawData.white_natural.fc_3; // 64x64 [r,g,b]
const cloudFreeNatural = rawData.gls_natural.fc_0; // 64x64 [r,g,b] at fc=0

// Color Palettes
// Build a 256-color palette tailored for scientific aerospace visualizations
function createMasterPalette() {
  const pal = [];
  // 0: Deep space black
  pal.push([10, 14, 23]);
  // 1-15: Grayscale / UI borders / text
  for (let i = 1; i <= 15; i++) {
    const v = Math.round(i * 17);
    pal.push([v, v, v]);
  }
  // 16-63: Ocean blues (dark to bright cyan)
  for (let i = 0; i < 48; i++) {
    const t = i / 47;
    pal.push([
      Math.round(8 + 15 * t),
      Math.round(25 + 65 * t),
      Math.round(60 + 150 * t)
    ]);
  }
  // 64-111: Land greens & earth browns
  for (let i = 0; i < 48; i++) {
    const t = i / 47;
    pal.push([
      Math.round(30 + 130 * t),
      Math.round(85 + 90 * t),
      Math.round(40 + 40 * t)
    ]);
  }
  // 112-143: Cloud whites & ice
  for (let i = 0; i < 32; i++) {
    const t = i / 31;
    pal.push([
      Math.round(180 + 75 * t),
      Math.round(195 + 60 * t),
      Math.round(210 + 45 * t)
    ]);
  }
  // 144-175: Golden yellow / Solar corona / Highlights
  for (let i = 0; i < 32; i++) {
    const t = i / 31;
    pal.push([
      Math.round(180 + 75 * t),
      Math.round(140 + 90 * t),
      Math.round(20 + 40 * t)
    ]);
  }
  // 176-207: Cyan / Laser links / Metrics
  for (let i = 0; i < 32; i++) {
    const t = i / 31;
    pal.push([
      Math.round(20 + 40 * t),
      Math.round(150 + 80 * t),
      Math.round(200 + 55 * t)
    ]);
  }
  // 208-239: Red / Alert / Occulter rim
  for (let i = 0; i < 32; i++) {
    const t = i / 31;
    pal.push([
      Math.round(160 + 95 * t),
      Math.round(40 + 60 * t),
      Math.round(40 + 60 * t)
    ]);
  }
  // 240-255: UI Accents (white, dark slate, etc.)
  while (pal.length < 256) {
    const idx = pal.length;
    pal.push([idx, idx, idx]);
  }
  return pal;
}

const masterPalette = createMasterPalette();

// Helper to find closest color index in palette
function getColor(r, g, b) {
  let bestDist = Infinity;
  let bestIdx = 0;
  for (let i = 0; i < 256; i++) {
    const p = masterPalette[i];
    const dr = r - p[0];
    const dg = g - p[1];
    const db = b - p[2];
    const dist = dr * dr * 2 + dg * dg * 4 + db * db * 3;
    if (dist < bestDist) {
      bestDist = dist;
      bestIdx = i;
    }
  }
  return bestIdx;
}

// Precompute color map lookups
const COLOR_BLACK = 0;
const COLOR_WHITE = 15;
const COLOR_GRID = 3;
const COLOR_TEXT = 13;
const COLOR_CYAN = 195;
const COLOR_GOLD = 165;
const COLOR_RED = 225;
const COLOR_GREEN = 90;

// Simple bitmap font 5x7 for labels
const FONT = {
  'A': [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
  'B': [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
  'C': [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
  'D': [0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E],
  'E': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
  'F': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
  'G': [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F],
  'H': [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
  'I': [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
  'K': [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
  'L': [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
  'M': [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
  'N': [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
  'O': [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
  'P': [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
  'R': [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
  'S': [0x0E, 0x11, 0x10, 0x0E, 0x01, 0x11, 0x0E],
  'T': [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
  'U': [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
  'V': [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
  'W': [0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11],
  'X': [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
  'Y': [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
  'Z': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
  '0': [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
  '1': [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
  '2': [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F],
  '3': [0x1F, 0x01, 0x02, 0x06, 0x01, 0x11, 0x0E],
  '4': [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
  '5': [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
  '6': [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E],
  '7': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
  '8': [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
  '9': [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C],
  ':': [0x00, 0x04, 0x04, 0x00, 0x04, 0x04, 0x00],
  '.': [0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x04],
  '=': [0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00, 0x00],
  '+': [0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00],
  '-': [0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00],
  '%': [0x19, 0x19, 0x02, 0x04, 0x08, 0x13, 0x13],
  ' ': [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
};

function drawText(buf, w, h, text, startX, startY, color) {
  let cx = startX;
  for (let ch of text.toUpperCase()) {
    const glyph = FONT[ch] || FONT[' '];
    for (let row = 0; row < 7; row++) {
      const bitmask = glyph[row];
      for (let col = 0; col < 5; col++) {
        if (bitmask & (0x10 >> col)) {
          const px = cx + col;
          const py = startY + row;
          if (px >= 0 && px < w && py >= 0 && py < h) {
            buf[py * w + px] = color;
          }
        }
      }
    }
    cx += 6;
  }
}

// -------------------------------------------------------------
// ANIMATION 1: Rotating Exo-Earth with Dynamic Cloud Advection
// -------------------------------------------------------------
console.log('Generating Animation 1: Planet Rotation with Cloud Advection...');
{
  const W = 320, H = 220;
  const numFrames = 36;
  const enc = new SimpleGifEncoder(W, H, 8); // 80ms per frame
  enc.setPalette(masterPalette);

  const cx = 95, cy = 110, R = 68;
  const lightHistory = [];

  for (let frameIdx = 0; frameIdx < numFrames; frameIdx++) {
    const buf = new Uint8Array(W * H);
    buf.fill(COLOR_BLACK);

    // Header & Section line
    drawText(buf, W, H, 'SGL SIMULATION: PLANETARY ROTATION', 10, 10, COLOR_CYAN);
    for (let x = 10; x < W - 10; x++) buf[22 * W + x] = COLOR_GRID;

    const rotAngle = (frameIdx / numFrames) * 2 * Math.PI;
    const cloudAdvect = rotAngle * 1.35; // clouds drift faster eastward

    let integratedFlux = 0;
    let visiblePixels = 0;

    // Render 3D orthographic sphere
    for (let py = cy - R; py <= cy + R; py++) {
      for (let px = cx - R; px <= cx + R; px++) {
        const dx = (px - cx) / R;
        const dy = (py - cy) / R;
        const distSq = dx * dx + dy * dy;
        if (distSq <= 1.0) {
          const dz = Math.sqrt(1.0 - distSq); // normal towards viewer

          // 3D coordinates on sphere
          // Planetary tilt 23.4 degrees
          const tilt = 23.4 * Math.PI / 180;
          const yRot = dy * Math.cos(tilt) - dz * Math.sin(tilt);
          const zRot = dy * Math.sin(tilt) + dz * Math.cos(tilt);
          const xRot = dx;

          const lat = Math.asin(Math.max(-1, Math.min(1, -yRot)));
          const lon = Math.atan2(xRot, zRot) + rotAngle;

          // Normalized map coords (36 rows x 72 cols)
          let u = (((lon / (2 * Math.PI)) % 1 + 1) % 1) * 72;
          let v = (((-lat / Math.PI + 0.5)) % 1 + 1) % 1 * 36;
          const mapX = Math.min(71, Math.max(0, Math.floor(u)));
          const mapY = Math.min(35, Math.max(0, Math.floor(v)));

          const rgb = naturalTruth[mapY][mapX];
          const baseAlbedo = (rgb[0] * 0.299 + rgb[1] * 0.587 + rgb[2] * 0.114) / 255;

          // Dynamic cloud advection layer
          const cloudLon = lon + cloudAdvect * (0.8 + 0.4 * Math.cos(lat));
          const cloudWave = Math.sin(cloudLon * 3 + lat * 4) * Math.cos(cloudLon * 2 - lat * 3);
          const cloudJet = Math.sin(lat * 6);
          const hasCloud = (cloudWave + cloudJet * 0.3) > 0.15;
          const cloudDensity = hasCloud ? 0.45 + 0.35 * Math.max(0, cloudWave) : 0;

          // Illumination: star at left (-0.8, 0.2, 0.5)
          const sunX = -0.7, sunY = 0.2, sunZ = 0.68;
          const sunDist = Math.sqrt(sunX*sunX + sunY*sunY + sunZ*sunZ);
          const illumination = Math.max(0.04, (dx * (sunX/sunDist) + dy * (sunY/sunDist) + dz * (sunZ/sunDist)));

          const totalAlbedo = hasCloud ? Math.max(baseAlbedo, cloudDensity) : baseAlbedo;
          const observedLight = totalAlbedo * illumination;
          integratedFlux += observedLight;
          visiblePixels++;

          // Blend surface RGB with cloud and illumination
          let cr = rgb[0], cg = rgb[1], cb = rgb[2];
          if (Math.abs(lat) > 1.05) {
            cr = 230; cg = 240; cb = 255; // Polar ice
          } else if (hasCloud) {
            cr = cr * (1 - cloudDensity) + 245 * cloudDensity;
            cg = cg * (1 - cloudDensity) + 250 * cloudDensity;
            cb = cb * (1 - cloudDensity) + 255 * cloudDensity;
          }

          cr = Math.min(255, Math.floor(cr * illumination));
          cg = Math.min(255, Math.floor(cg * illumination));
          cb = Math.min(255, Math.floor(cb * illumination));

          buf[py * W + px] = getColor(cr, cg, cb);
        }
      }
    }

    // Atmospheric limb glow
    for (let angle = 0; angle < Math.PI * 2; angle += 0.05) {
      const rx = Math.round(cx + (R + 1) * Math.cos(angle));
      const ry = Math.round(cy + (R + 1) * Math.sin(angle));
      if (rx >= 0 && rx < W && ry >= 0 && ry < H && Math.cos(angle) < 0.2) {
        buf[ry * W + rx] = COLOR_CYAN;
      }
    }

    const normFlux = integratedFlux / (visiblePixels || 1);
    lightHistory.push(normFlux);
    if (lightHistory.length > 36) lightHistory.shift();

    // Right Side: Live Photometric Light Curve F(t)
    drawText(buf, W, H, 'DIURNAL LIGHT CURVE F(T)', 185, 32, COLOR_WHITE);
    drawText(buf, W, H, 'P = 24.0 H  FC = 55%', 185, 44, COLOR_CYAN);

    // Light curve graph box
    const gx = 185, gy = 56, gw = 120, gh = 65;
    for (let x = gx; x < gx + gw; x++) {
      buf[gy * W + x] = COLOR_GRID;
      buf[(gy + gh) * W + x] = COLOR_GRID;
      buf[(gy + Math.floor(gh/2)) * W + x] = 1; // dashed mid-line
    }
    for (let y = gy; y <= gy + gh; y++) {
      buf[y * W + gx] = COLOR_GRID;
      buf[y * W + (gx + gw - 1)] = COLOR_GRID;
    }

    // Draw historical curve
    const minF = 0.05, maxF = 0.18;
    for (let i = 0; i < lightHistory.length - 1; i++) {
      const px1 = gx + Math.floor((i / 36) * gw);
      const py1 = gy + gh - Math.floor(((lightHistory[i] - minF) / (maxF - minF)) * (gh - 4)) - 2;
      const px2 = gx + Math.floor(((i + 1) / 36) * gw);
      const py2 = gy + gh - Math.floor(((lightHistory[i+1] - minF) / (maxF - minF)) * (gh - 4)) - 2;

      // Draw segment
      const clampedY = Math.max(gy + 1, Math.min(gy + gh - 1, py1));
      if (px1 >= gx && px1 < gx + gw) buf[clampedY * W + px1] = COLOR_GOLD;
    }

    // Telemetry Cards on Bottom Right
    drawText(buf, W, H, 'SPIN PERIOD : 24.0 H', 185, 134, COLOR_TEXT);
    drawText(buf, W, H, 'ZONAL WIND  : +21 M/S', 185, 148, COLOR_TEXT);
    drawText(buf, W, H, 'AXIAL TILT  : 23.4 DEG', 185, 162, COLOR_TEXT);
    drawText(buf, W, H, 'STATUS      : ADVECTION ON', 185, 176, COLOR_GREEN);

    // Bottom banner
    drawText(buf, W, H, 'CONTINENTAL ROTATION & CLOUD TIME-SERIES', 10, 202, COLOR_TEXT);

    enc.addFrame(buf);
  }

  const gifData = enc.encode();
  fs.writeFileSync('public/videos/planet_rotation_clouds.gif', gifData);
  console.log('Saved public/videos/planet_rotation_clouds.gif (' + gifData.length + ' bytes)');
}

// -------------------------------------------------------------
// ANIMATION 2: SGL Einstein Ring Formation & Azimuthal Convolution
// -------------------------------------------------------------
console.log('Generating Animation 2: SGL Einstein Ring Optical Convolution...');
{
  const W = 320, H = 220;
  const numFrames = 36;
  const enc = new SimpleGifEncoder(W, H, 8);
  enc.setPalette(masterPalette);

  const cx = 95, cy = 110, R_coronagraph = 28, R_ring = 58;

  for (let frameIdx = 0; frameIdx < numFrames; frameIdx++) {
    const buf = new Uint8Array(W * H);
    buf.fill(COLOR_BLACK);

    drawText(buf, W, H, 'SGL CORONAGRAPH: EINSTEIN RING', 10, 10, COLOR_CYAN);
    for (let x = 10; x < W - 10; x++) buf[22 * W + x] = COLOR_GRID;

    const t = (frameIdx / numFrames) * 2 * Math.PI;

    // Draw coronagraph occulting mask (dark center)
    for (let y = cy - R_ring - 12; y <= cy + R_ring + 12; y++) {
      for (let x = cx - R_ring - 12; x <= cx + R_ring + 12; x++) {
        const d = Math.sqrt((x - cx) ** 2 + (y - cy) ** 2);

        // Solar corona glow outside occulter
        if (d >= R_coronagraph && d < R_coronagraph + 18) {
          const coronaT = 1 - (d - R_coronagraph) / 18;
          const cVal = Math.floor(coronaT * 12);
          buf[y * W + x] = Math.max(buf[y * W + x], 208 + cVal);
        }

        // Razor-thin Einstein Ring around R_ring
        const dr = Math.abs(d - R_ring);
        if (dr <= 3.2) {
          const theta = Math.atan2(y - cy, x - cx);
          // Modulated intensity based on planet continents + cloud rotation
          const mod1 = Math.sin(theta * 2 + t);
          const mod2 = Math.cos(theta * 3 - t * 0.7);
          const ringBright = 0.55 + 0.35 * mod1 + 0.15 * mod2;
          const intensity = Math.max(0, 1 - dr / 3.2) * ringBright;

          const col = 176 + Math.min(31, Math.floor(intensity * 31));
          buf[y * W + x] = col;
        }

        // Dark occulter mask
        if (d < R_coronagraph) {
          buf[y * W + x] = (d > R_coronagraph - 2) ? COLOR_RED : 0;
        }
      }
    }

    // Polar crosshairs
    for (let r = 10; r <= R_ring + 18; r += 4) {
      buf[cy * W + (cx + r)] = COLOR_GRID;
      buf[cy * W + (cx - r)] = COLOR_GRID;
      buf[(cy + r) * W + cx] = COLOR_GRID;
      buf[(cy - r) * W + cx] = COLOR_GRID;
    }

    // Right Side: Azimuthal Profile I(theta)
    drawText(buf, W, H, 'AZIMUTHAL PROFILE I(THETA)', 185, 32, COLOR_WHITE);
    drawText(buf, W, H, 'K(RHO) = D / (4 * RHO)', 185, 44, COLOR_GOLD);

    // Profile Box
    const gx = 185, gy = 56, gw = 120, gh = 65;
    for (let x = gx; x < gx + gw; x++) {
      buf[gy * W + x] = COLOR_GRID;
      buf[(gy + gh) * W + x] = COLOR_GRID;
    }
    for (let y = gy; y <= gy + gh; y++) {
      buf[y * W + gx] = COLOR_GRID;
      buf[y * W + (gx + gw - 1)] = COLOR_GRID;
    }

    // Draw I(theta) curve
    for (let i = 0; i < gw - 2; i++) {
      const theta = (i / gw) * 2 * Math.PI;
      const mod1 = Math.sin(theta * 2 + t);
      const mod2 = Math.cos(theta * 3 - t * 0.7);
      const val = 0.55 + 0.35 * mod1 + 0.15 * mod2;
      const py = gy + gh - Math.floor(val * (gh - 6)) - 3;
      if (py >= gy + 1 && py < gy + gh) {
        buf[py * W + (gx + 1 + i)] = COLOR_CYAN;
      }
    }

    // Telemetry info
    drawText(buf, W, H, 'TELESCOPE   : 650 AU SGL', 185, 134, COLOR_TEXT);
    drawText(buf, W, H, 'GAIN MU     : ~10^11', 185, 148, COLOR_TEXT);
    drawText(buf, W, H, 'OCCULTER    : CORONAGRAPH', 185, 162, COLOR_TEXT);
    drawText(buf, W, H, 'PHOTON SNR  : 43.16', 185, 176, COLOR_GOLD);

    drawText(buf, W, H, 'REAL-TIME 1/RHO GRAVITATIONAL FOLDING', 10, 202, COLOR_TEXT);

    enc.addFrame(buf);
  }

  const gifData = enc.encode();
  fs.writeFileSync('public/videos/einstein_ring_convolution.gif', gifData);
  console.log('Saved public/videos/einstein_ring_convolution.gif (' + gifData.length + ' bytes)');
}

// -------------------------------------------------------------
// ANIMATION 3: Multi-Spacecraft Fleet Formation Rastering
// -------------------------------------------------------------
console.log('Generating Animation 3: Fleet Formation Scanning...');
{
  const W = 320, H = 220;
  const numFrames = 40;
  const enc = new SimpleGifEncoder(W, H, 8);
  enc.setPalette(masterPalette);

  const numCrafts = 8; // 8 craft tracks visualized

  for (let frameIdx = 0; frameIdx < numFrames; frameIdx++) {
    const buf = new Uint8Array(W * H);
    buf.fill(COLOR_BLACK);

    drawText(buf, W, H, 'SGL FLEET FORMATION: 1.34 KM RASTER', 10, 10, COLOR_CYAN);
    for (let x = 10; x < W - 10; x++) buf[22 * W + x] = COLOR_GRID;

    const progress = (frameIdx / numFrames);

    // Draw SGL Focal Tube Cylinder cross-section on left
    const cx = 95, cy = 110, rx = 72, ry = 62;
    for (let angle = 0; angle < Math.PI * 2; angle += 0.03) {
      const px = Math.round(cx + rx * Math.cos(angle));
      const py = Math.round(cy + ry * Math.sin(angle));
      if (px >= 0 && px < W && py >= 0 && py < H) buf[py * W + px] = COLOR_GRID;
    }

    // Spacecraft positions and raster tracks
    const craftPositions = [];
    for (let i = 0; i < numCrafts; i++) {
      const trackY = cy - ry + 12 + Math.floor((i / (numCrafts - 1)) * (2 * ry - 24));
      // Track line inside cylinder
      const yNorm = (trackY - cy) / ry;
      const xSpan = rx * Math.sqrt(Math.max(0, 1 - yNorm * yNorm));

      // Draw faint track guide
      for (let x = Math.round(cx - xSpan); x <= Math.round(cx + xSpan); x += 3) {
        if (x >= 0 && x < W) buf[trackY * W + x] = 2;
      }

      // Spacecraft sweep position
      const phase = (progress + i * 0.12) % 1.0;
      const dir = (i % 2 === 0) ? 1 : -1;
      const scanX = (dir === 1)
        ? (cx - xSpan + phase * 2 * xSpan)
        : (cx + xSpan - phase * 2 * xSpan);

      craftPositions.push({ x: Math.round(scanX), y: trackY });

      // Draw scanned footprint path behind craft
      const startX = (dir === 1) ? Math.round(cx - xSpan) : Math.round(scanX);
      const endX = (dir === 1) ? Math.round(scanX) : Math.round(cx + xSpan);
      for (let x = startX; x <= endX; x++) {
        if (x >= 0 && x < W) {
          buf[trackY * W + x] = 16 + Math.floor(Math.random() * 8); // sampled pixel trail
        }
      }
    }

    // Draw inter-satellite laser links between adjacent spacecraft
    for (let i = 0; i < craftPositions.length - 1; i++) {
      const p1 = craftPositions[i];
      const p2 = craftPositions[i + 1];
      // Draw line
      const steps = 15;
      for (let s = 0; s <= steps; s++) {
        const lx = Math.round(p1.x + (p2.x - p1.x) * (s / steps));
        const ly = Math.round(p1.y + (p2.y - p1.y) * (s / steps));
        if (lx >= 0 && lx < W && ly >= 0 && ly < H && s % 2 === 0) {
          buf[ly * W + lx] = COLOR_CYAN;
        }
      }
    }

    // Draw spacecraft icons
    for (let p of craftPositions) {
      if (p.x >= 2 && p.x < W - 2 && p.y >= 2 && p.y < H - 2) {
        buf[p.y * W + p.x] = COLOR_WHITE;
        buf[p.y * W + (p.x - 1)] = COLOR_GOLD;
        buf[p.y * W + (p.x + 1)] = COLOR_GOLD;
        buf[(p.y - 1) * W + p.x] = COLOR_GOLD;
        buf[(p.y + 1) * W + p.x] = COLOR_GOLD;
      }
    }

    // Right Side: Progress & Coverage Stats
    drawText(buf, W, H, 'IMAGE PLANE COVERAGE', 185, 32, COLOR_WHITE);
    const pct = Math.floor(progress * 100);
    drawText(buf, W, H, `CYLINDER : ${pct}% SAMPLED`, 185, 44, COLOR_CYAN);

    // Coverage Progress Bar
    const bx = 185, by = 58, bw = 120, bh = 14;
    for (let x = bx; x < bx + bw; x++) {
      buf[by * W + x] = COLOR_GRID;
      buf[(by + bh) * W + x] = COLOR_GRID;
    }
    for (let y = by; y <= by + bh; y++) {
      buf[y * W + bx] = COLOR_GRID;
      buf[y * W + (bx + bw - 1)] = COLOR_GRID;
    }
    const fillW = Math.floor((progress) * (bw - 4));
    for (let y = by + 2; y < by + bh - 1; y++) {
      for (let x = bx + 2; x < bx + 2 + fillW; x++) {
        buf[y * W + x] = COLOR_GREEN;
      }
    }

    // Telemetry Cards
    drawText(buf, W, H, 'FLEET SIZE  : 16 CRAFTS', 185, 84, COLOR_TEXT);
    drawText(buf, W, H, 'SLEW VEL    : 15.2 M/S', 185, 98, COLOR_TEXT);
    drawText(buf, W, H, 'CYLINDER D  : 1.34 KM', 185, 112, COLOR_TEXT);
    drawText(buf, W, H, 'MISSION DUR : 90 DAYS', 185, 126, COLOR_TEXT);
    drawText(buf, W, H, 'CADENCE LAW : K^0.26', 185, 140, COLOR_GOLD);
    drawText(buf, W, H, 'INTER-LINK  : LASER LOCK', 185, 154, COLOR_CYAN);
    drawText(buf, W, H, 'STATUS      : NOMINAL', 185, 168, COLOR_GREEN);

    drawText(buf, W, H, 'CONCURRENT MULTI-SPACECRAFT SPATIAL SCANNING', 10, 202, COLOR_TEXT);

    enc.addFrame(buf);
  }

  const gifData = enc.encode();
  fs.writeFileSync('public/videos/fleet_raster_scan.gif', gifData);
  console.log('Saved public/videos/fleet_raster_scan.gif (' + gifData.length + ' bytes)');
}

// -------------------------------------------------------------
// ANIMATION 4: TDI Deconvolution Timelapse Convergence
// -------------------------------------------------------------
console.log('Generating Animation 4: TDI Deconvolution Timelapse...');
{
  const W = 320, H = 220;
  const numFrames = 36;
  const enc = new SimpleGifEncoder(W, H, 10); // 100ms per frame
  enc.setPalette(masterPalette);

  // We blend between 4 key scientific states:
  // State 0: Raw noisy observation with horizontal cloud stripes (whiteNoise)
  // State 1: Common-mode cloud deflation P_perp applied
  // State 2: Regularized TDI reconstruction at K=8 (fiducial)
  // State 3: High-cadence limit K=64 (approaching cloudFree)
  const mapStages = [
    { name: 'RAW SGL OBS (FC=0.55)', r: '0.13', data: whiteNoiseNatural, stage: 'STAGE 1: RAW RASTER WITH CLOUD NOISE' },
    { name: 'P_PERP CLOUD DEFLATION', r: '0.22', data: rawData.b2_natural.fc_3, stage: 'STAGE 2: COMMON-MODE CLOUD DEFLATION' },
    { name: 'TDI GLS RECON (K=8)', r: '0.33', data: fiducialNatural, stage: 'STAGE 3: SPECTRAL REGULARIZATION' },
    { name: 'HIGH CADENCE (K=64)', r: '0.54', data: cloudFreeNatural, stage: 'STAGE 4: CADENCE SCALING RESOLUTION' }
  ];

  for (let frameIdx = 0; frameIdx < numFrames; frameIdx++) {
    const buf = new Uint8Array(W * H);
    buf.fill(COLOR_BLACK);

    drawText(buf, W, H, 'TDI ALGORITHM: DECONVOLUTION TIMELAPSE', 10, 10, COLOR_CYAN);
    for (let x = 10; x < W - 10; x++) buf[22 * W + x] = COLOR_GRID;

    // Determine interpolation stage
    const stageProgress = (frameIdx / numFrames) * mapStages.length;
    const currentStageIdx = Math.min(mapStages.length - 1, Math.floor(stageProgress));
    const nextStageIdx = (currentStageIdx + 1) % mapStages.length;
    const alpha = stageProgress - Math.floor(stageProgress);

    const s1 = mapStages[currentStageIdx];
    const s2 = mapStages[nextStageIdx];

    // Render equirectangular map on left (132x66, 2:1 ratio)
    const mx = 16, my = 50, mW = 132, mH = 66;
    for (let py = 0; py < mH; py++) {
      const srcY = Math.min(35, Math.floor((py / mH) * 36));

      for (let px = 0; px < mW; px++) {
        const srcX = Math.min(71, Math.floor((px / mW) * 72));

        const rgb1 = s1.data[srcY][srcX];
        const rgb2 = s2.data[srcY][srcX];
        const cr = Math.round(rgb1[0] * (1 - alpha) + rgb2[0] * alpha);
        const cg = Math.round(rgb1[1] * (1 - alpha) + rgb2[1] * alpha);
        const cb = Math.round(rgb1[2] * (1 - alpha) + rgb2[2] * alpha);

        buf[(my + py) * W + (mx + px)] = getColor(cr, cg, cb);
      }
    }

    // Border around map
    for (let x = mx - 1; x <= mx + mW; x++) {
      buf[(my - 1) * W + x] = COLOR_GRID;
      buf[(my + mH) * W + x] = COLOR_GRID;
    }
    for (let y = my - 1; y <= my + mH; y++) {
      buf[y * W + (mx - 1)] = COLOR_GRID;
      buf[y * W + (mx + mW)] = COLOR_GRID;
    }

    // Right Side: Algorithmic Status & Metrics
    drawText(buf, W, H, 'INVERSION STATUS', 160, 36, COLOR_WHITE);
    drawText(buf, W, H, s1.name, 160, 48, COLOR_GOLD);

    // Current Correlation r value
    const curR = (parseFloat(s1.r) * (1 - alpha) + parseFloat(s2.r) * alpha).toFixed(2);
    drawText(buf, W, H, `SURFACE CORR  : R = ${curR}`, 160, 68, COLOR_CYAN);
    drawText(buf, W, H, 'DEFLATION DR  : +0.041', 160, 82, COLOR_GREEN);
    drawText(buf, W, H, 'PHOTON SNR    : 43.16', 160, 96, COLOR_TEXT);
    drawText(buf, W, H, 'CLOUD COVER   : FC = 55%', 160, 110, COLOR_TEXT);
    drawText(buf, W, H, 'REGULARIZER   : TK-TDI', 160, 124, COLOR_TEXT);
    drawText(buf, W, H, 'HARMONICS     : L_EFF = 4-5', 160, 138, COLOR_TEXT);
    drawText(buf, W, H, 'DICHOTOMY     : RECOVERED', 160, 152, COLOR_GREEN);

    // Progress line at bottom of map
    drawText(buf, W, H, s1.stage, 10, 176, COLOR_GOLD);
    drawText(buf, W, H, 'PROGRESSIVE RESTORATION OF CONTINENTAL SHAPES', 10, 202, COLOR_TEXT);

    enc.addFrame(buf);
  }

  const gifData = enc.encode();
  fs.writeFileSync('public/videos/tdi_deconvolution_timelapse.gif', gifData);
  console.log('Saved public/videos/tdi_deconvolution_timelapse.gif (' + gifData.length + ' bytes)');
}

console.log('All 4 simulation animations successfully generated!');
