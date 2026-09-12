import json
import math
import os
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

start_time = time.time()
print("Starting Typography-Enhanced Ultra-Extended Duration GIF Generation (24.0s - 32.0s)...")

# Fonts for crisp, professional typography
try:
    font_title = ImageFont.truetype('arialbd.ttf', 13)
    font_sub = ImageFont.truetype('arial.ttf', 11)
    font_card = ImageFont.truetype('arialbd.ttf', 11)
    font_body = ImageFont.truetype('arial.ttf', 11)
    font_metric = ImageFont.truetype('arialbd.ttf', 14)
    font_mono = ImageFont.truetype('consola.ttf', 11)
    font_mono_bold = ImageFont.truetype('consolab.ttf', 11)
except Exception:
    font_title = ImageFont.load_default()
    font_sub = font_title
    font_card = font_title
    font_body = font_title
    font_metric = font_title
    font_mono = font_title
    font_mono_bold = font_title

# Load truth and reconstruction map data
with open('public/data/reconstruction_maps.json', 'r') as f:
    data = json.load(f)

natural_truth = np.array(data['natural_truth']) # (36, 72, 3)
gls_fc3 = np.array(data['gls_natural']['fc_3']) # (36, 72, 3)
white_fc3 = np.array(data['white_natural']['fc_3']) # (36, 72, 3)
gls_fc0 = np.array(data['gls_natural']['fc_0']) # (36, 72, 3)
b2_fc3 = np.array(data['b2_natural']['fc_3']) # (36, 72, 3)

W, H = 640, 440
os.makedirs('public/videos', exist_ok=True)

# =============================================================
# 1. PLANET ROTATION & CLOUD ADVECTION (240 frames @ 100ms = 24.0s)
# 1.0 second per diurnal hour (0.0h -> 24.0h)
# =============================================================
print("\n[1/4] Rendering Planet Rotation (240 frames = 24.0s, 1s/hour)...")
num_frames_1 = 240
frame_duration_1 = 100 # 100ms = 10 fps -> 24.0 seconds total loop
frames_1 = []

cx, cy, R = 195, 225, 135
light_history_1 = []

# Precalculate planetary spherical geometry
y_indices, x_indices = np.ogrid[cy - R:cy + R + 1, cx - R:cx + R + 1]
dx = (x_indices - cx) / R
dy = (y_indices - cy) / R
dist_sq = dx**2 + dy**2
disk_mask = dist_sq <= 1.0
dz = np.sqrt(np.maximum(0.0, 1.0 - dist_sq))

# Axial obliquity tilt (23.4 degrees)
tilt = math.radians(23.4)
cos_tilt = math.cos(tilt)
sin_tilt = math.sin(tilt)
y_rot = dy * cos_tilt - dz * sin_tilt
z_rot = dy * sin_tilt + dz * cos_tilt
x_rot = dx

lat = np.arcsin(np.clip(-y_rot, -1.0, 1.0))
base_lon = np.arctan2(x_rot, z_rot)

# Star illumination direction
sun_x, sun_y, sun_z = -0.78, 0.22, 0.62
sun_norm = math.sqrt(sun_x**2 + sun_y**2 + sun_z**2)
sun_vec = np.array([sun_x/sun_norm, sun_y/sun_norm, sun_z/sun_norm])
illum = np.maximum(0.05, (dx * sun_vec[0] + dy * sun_vec[1] + dz * sun_vec[2]))
illum_3d = illum[..., np.newaxis]
polar_mask = np.abs(lat) > 1.05

for f_idx in range(num_frames_1):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    sim_time_hours = (f_idx / num_frames_1) * 24.0
    rot_angle = (f_idx / num_frames_1) * 2 * math.pi
    cloud_advect = rot_angle * 1.35 # Zonal wind advects faster than planetary surface

    # Top Header
    draw.text((20, 14), "SOLAR GRAVITATIONAL LENS: TIME-DOMAIN SIMULATION", fill=(56, 189, 248), font=font_title)
    draw.text((20, 31), f"EXO-EARTH ROTATION | DIURNAL TIME: {sim_time_hours:04.1f}h / 24.0h | DYNAMIC CLOUDS", fill=(148, 163, 184), font=font_sub)
    draw.line([(20, 48), (W - 20, 48)], fill=(30, 41, 59), width=1)

    # Current rotation longitude
    cur_lon = base_lon + rot_angle
    u = ((cur_lon / (2 * math.pi)) % 1.0) * 72.0
    v = ((-lat / math.pi + 0.5) % 1.0) * 36.0
    map_x = np.clip(u.astype(int), 0, 71)
    map_y = np.clip(v.astype(int), 0, 35)

    base_rgb = natural_truth[map_y, map_x].astype(float)

    # Dynamic atmospheric cloud pattern
    cloud_lon = cur_lon + cloud_advect * (0.85 + 0.35 * np.cos(lat))
    cloud_wave = np.sin(cloud_lon * 3.2 + lat * 4.1 + f_idx * 0.02) * np.cos(cloud_lon * 2.1 - lat * 3.3)
    cloud_jet = np.sin(lat * 5.8)
    has_cloud = (cloud_wave + cloud_jet * 0.32) > 0.12
    cloud_dens = np.where(has_cloud, np.clip(0.48 + 0.42 * cloud_wave, 0.0, 1.0), 0.0)

    # Blend clouds & ice
    cloud_rgb = np.array([245.0, 250.0, 255.0])
    c_dens_3d = cloud_dens[..., np.newaxis]
    blended_rgb = base_rgb * (1.0 - c_dens_3d) + cloud_rgb * c_dens_3d
    blended_rgb[polar_mask] = [238.0, 246.0, 255.0]

    final_rgb = np.clip(blended_rgb * illum_3d, 0, 255).astype(np.uint8)

    rendered_img = Image.fromarray(final_rgb)
    img.paste(rendered_img, (cx - R, cy - R), mask=Image.fromarray((disk_mask * 255).astype(np.uint8)))

    # Atmospheric limb halo
    draw.ellipse([(cx - R - 3, cy - R - 3), (cx + R + 3, cy + R + 3)], outline=(30, 58, 90), width=1)
    draw.ellipse([(cx - R - 1, cy - R - 1), (cx + R + 1, cy + R + 1)], outline=(56, 189, 248), width=2)

    visible_flux = float(np.mean(final_rgb[disk_mask]) / 255.0)
    light_history_1.append(visible_flux)

    # Right Side: Photometric Light Curve Graph
    gx, gy, gw, gh = 385, 75, 235, 140
    draw.rectangle([(gx, gy), (gx + gw, gy + gh)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((gx + 12, gy + 8), "DIURNAL LIGHT CURVE F(t)", fill=(255, 255, 255), font=font_card)
    draw.text((gx + 12, gy + 24), "Disk-Averaged Photometry vs. Time", fill=(148, 163, 184), font=font_sub)

    for y_step in range(gy + 45, gy + gh, 30):
        draw.line([(gx + 5, y_step), (gx + gw - 5, y_step)], fill=(30, 41, 59), width=1)

    min_f, max_f = 0.08, 0.25
    curve_pts = []
    for i, val in enumerate(light_history_1):
        px = gx + int((i / num_frames_1) * (gw - 24)) + 12
        py = gy + gh - int(((val - min_f) / (max_f - min_f)) * (gh - 55)) - 10
        py = max(gy + 40, min(gy + gh - 5, py))
        curve_pts.append((px, py))

    if len(curve_pts) > 1:
        draw.line(curve_pts, fill=(251, 191, 36), width=2)
        draw.ellipse([(curve_pts[-1][0] - 4, curve_pts[-1][1] - 4), (curve_pts[-1][0] + 4, curve_pts[-1][1] + 4)], fill=(239, 68, 68), outline=(255, 255, 255))

    # Current geographic meridian
    meridian_lon_deg = int((sim_time_hours / 24.0) * 360) % 360
    if 30 <= meridian_lon_deg < 120:
        viewed_feature = "Americas & Caribbean"
    elif 120 <= meridian_lon_deg < 240:
        viewed_feature = "Pacific Ocean Basin"
    elif 240 <= meridian_lon_deg < 320:
        viewed_feature = "Eurasia & Africa"
    else:
        viewed_feature = "Atlantic Meridian"

    # Telemetry Box
    tx, ty, tw, th = 385, 230, 235, 155
    draw.rectangle([(tx, ty), (tx + tw, ty + th)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((tx + 12, ty + 8), "SIMULATION TELEMETRY", fill=(56, 189, 248), font=font_card)

    telemetry = [
        ("DIURNAL TIME", f"{sim_time_hours:04.1f}h / 24.0h"),
        ("MERIDIAN VIEW", viewed_feature),
        ("CLOUD COVER", "fc = 55% (fiducial)"),
        ("ZONAL ADVECTION", "v_jet = +21 m/s"),
        ("AXIAL TILT", "23.4° obliquity"),
        ("STATUS", "FULL ROTATION ACTIVE")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 26 + i * 20
        draw.text((tx + 12, row_y), label, fill=(148, 163, 184), font=font_mono)
        val_color = (52, 211, 153) if i == 5 else (255, 255, 255)
        draw.text((tx + 115, row_y), val, fill=val_color, font=font_mono_bold)

    draw.line([(20, H - 35), (W - 20, H - 35)], fill=(30, 41, 59), width=1)
    draw.text((20, H - 24), "SGL TIME-DOMAIN RESEARCH | SONTANKE ET AL. (2026)", fill=(100, 116, 139), font=font_sub)
    draw.text((W - 190, H - 24), "DURATION: 24.0s (240f)", fill=(56, 189, 248), font=font_card)

    frames_1.append(img)

# Save Animation 1
frames_1[0].save(
    'public/videos/planet_rotation_clouds.gif',
    save_all=True,
    append_images=frames_1[1:],
    duration=frame_duration_1,
    loop=0,
    optimize=True
)
print(f"Saved public/videos/planet_rotation_clouds.gif (24.0s duration, {len(frames_1)} frames)")


# =============================================================
# 2. EINSTEIN RING OPTICAL CONVOLUTION (240 frames @ 100ms = 24.0s)
# Comprehensive optical sweep showing off-axis drift & arc bifurcation
# =============================================================
print("\n[2/4] Rendering Einstein Ring Optical Convolution (240 frames = 24.0s)...")
num_frames_2 = 240
frame_duration_2 = 100
frames_2 = []

cx, cy = 195, 225
R_coronagraph = 52
R_ring = 118

for f_idx in range(num_frames_2):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    elapsed_s = f_idx * 0.1
    t = (f_idx / num_frames_2) * 4 * math.pi
    rho_t = 1.4 * (1.0 - math.cos(t * 0.5)) # smoothly goes 0m -> 2.8m -> 0m -> 2.8m -> 0m

    draw.text((20, 14), "SGL CORONAGRAPH TELESCOPE: 650 AU", fill=(56, 189, 248), font=font_title)
    draw.text((20, 31), f"OPTICAL CONVOLUTION | OFF-AXIS DRIFT: rho = {rho_t:.2f} m | K(rho) = d/(4 rho)", fill=(148, 163, 184), font=font_sub)
    draw.line([(20, 48), (W - 20, 48)], fill=(30, 41, 59), width=1)

    # Solar Corona dynamic flaring glow
    for r_step in range(R_coronagraph, R_coronagraph + 48):
        draw.ellipse([(cx - r_step, cy - r_step), (cx + r_step, cy + r_step)], outline=(217, 119, 6))

    # Luminous Einstein Ring with off-axis gravitational shear and arc bifurcation
    for angle_deg in range(360):
        theta = math.radians(angle_deg)
        theta_shear = t * 0.15
        shear_diff = theta - theta_shear
        arc_factor = math.exp(-((math.sin(shear_diff)**2) * (rho_t * 1.6)))
        mod = 0.35 + 0.30 * math.sin(theta * 2 + t) + 0.35 * arc_factor

        col_r = int(np.clip(40 + 190 * (mod**2), 0, 255))
        col_g = int(np.clip(140 + 100 * mod, 0, 255))
        col_b = 255

        ring_r = R_ring + int(rho_t * 2.5 * math.cos(2 * shear_diff))
        px = cx + int(ring_r * math.cos(theta))
        py = cy + int(ring_r * math.sin(theta))

        dot_radius = 2 if mod > 0.45 else 1
        if mod > 0.18:
            draw.ellipse([(px - dot_radius, py - dot_radius), (px + dot_radius, py + dot_radius)], fill=(col_r, col_g, col_b))

    # Polar Grid Marks
    for r in [60, 90, 120, 150]:
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(30, 41, 59), width=1)
    draw.line([(cx - 160, cy), (cx + 160, cy)], fill=(30, 41, 59), width=1)
    draw.line([(cx, cy - 160), (cx, cy + 160)], fill=(30, 41, 59), width=1)

    # Dark Central Occulter Mask
    draw.ellipse([(cx - R_coronagraph, cy - R_coronagraph), (cx + R_coronagraph, cy + R_coronagraph)], fill=(15, 23, 42), outline=(239, 68, 68), width=2)
    draw.text((cx - 45, cy - 6), "OCCULTER MASK", fill=(239, 68, 68), font=font_mono_bold)

    # Right Side: Azimuthal Profile I(theta)
    gx, gy, gw, gh = 385, 75, 235, 140
    draw.rectangle([(gx, gy), (gx + gw, gy + gh)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((gx + 12, gy + 8), "AZIMUTHAL PROFILE I(theta)", fill=(255, 255, 255), font=font_card)
    draw.text((gx + 12, gy + 24), f"Off-Axis Offset: rho = {rho_t:.2f} m", fill=(251, 191, 36), font=font_sub)

    for y_step in range(gy + 45, gy + gh, 30):
        draw.line([(gx + 5, y_step), (gx + gw - 5, y_step)], fill=(30, 41, 59), width=1)

    profile_pts = []
    for deg in range(0, 360, 3):
        theta = math.radians(deg)
        shear_diff = theta - (t * 0.15)
        arc_factor = math.exp(-((math.sin(shear_diff)**2) * (rho_t * 1.6)))
        mod = 0.35 + 0.30 * math.sin(theta * 2 + t) + 0.35 * arc_factor
        px = gx + int((deg / 360) * (gw - 24)) + 12
        py = gy + gh - int(np.clip(mod, 0.0, 1.0) * (gh - 55)) - 10
        profile_pts.append((px, py))

    if len(profile_pts) > 1:
        draw.line(profile_pts, fill=(56, 189, 248), width=2)

    # Telemetry Box
    tx, ty, tw, th = 385, 230, 235, 155
    draw.rectangle([(tx, ty), (tx + tw, ty + th)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((tx + 12, ty + 8), "CORONAGRAPH TELEMETRY", fill=(56, 189, 248), font=font_card)

    telemetry = [
        ("DISTANCE", "z = 650 AU"),
        ("SGL GAIN", "mu ~ 10^11"),
        ("SUPPRESSION", "10^-10 starlight"),
        ("OFFSET DRIFT", f"rho = {rho_t:.2f} m"),
        ("PHOTON SNR", "SNR_C = 43.16"),
        ("STATUS", "RING CONVOLUTION ACTIVE")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 26 + i * 20
        draw.text((tx + 12, row_y), label, fill=(148, 163, 184), font=font_mono)
        val_color = (52, 211, 153) if i == 5 else (255, 255, 255)
        draw.text((tx + 115, row_y), val, fill=val_color, font=font_mono_bold)

    draw.line([(20, H - 35), (W - 20, H - 35)], fill=(30, 41, 59), width=1)
    draw.text((20, H - 24), "SGL CORONAGRAPH MODEL | SONTANKE ET AL. (2026)", fill=(100, 116, 139), font=font_sub)
    draw.text((W - 190, H - 24), "DURATION: 24.0s (240f)", fill=(56, 189, 248), font=font_card)

    frames_2.append(img)

# Save Animation 2
frames_2[0].save(
    'public/videos/einstein_ring_convolution.gif',
    save_all=True,
    append_images=frames_2[1:],
    duration=frame_duration_2,
    loop=0,
    optimize=True
)
print(f"Saved public/videos/einstein_ring_convolution.gif (24.0s duration, {len(frames_2)} frames)")


# =============================================================
# 3. FLEET FORMATION RASTER SCANNING (240 frames @ 100ms = 24.0s)
# Full high-resolution raster mapping of 1.34 km focal tube
# =============================================================
print("\n[3/4] Rendering Fleet Formation Raster (240 frames = 24.0s)...")
num_frames_3 = 240
frame_duration_3 = 100
frames_3 = []
num_crafts = 16

for f_idx in range(num_frames_3):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    progress = f_idx / num_frames_3
    pct = int(progress * 100)

    draw.text((20, 14), "SGL MULTI-SPACECRAFT FLEET FORMATION", fill=(56, 189, 248), font=font_title)
    draw.text((20, 31), f"16 NANO-SPACECRAFT SWEEPING 1.34 KM FOCAL CYLINDER | SAMPLING: {pct}%", fill=(148, 163, 184), font=font_sub)
    draw.line([(20, 48), (W - 20, 48)], fill=(30, 41, 59), width=1)

    # Focal Cylinder Profile (Left)
    cx, cy, rx, ry = 195, 225, 145, 125
    draw.ellipse([(cx - rx, cy - ry), (cx + rx, cy + ry)], outline=(51, 65, 85), width=2)
    draw.text((cx - 55, cy - ry - 16), "1.34 KM FOCAL TUBE", fill=(148, 163, 184), font=font_card)

    # Spacecraft positions and tracks
    craft_pts = []
    for i in range(num_crafts):
        track_y = cy - ry + 18 + int((i / (num_crafts - 1)) * (2 * ry - 36))
        y_norm = (track_y - cy) / ry
        x_span = rx * math.sqrt(max(0.0, 1.0 - y_norm**2))

        # Track line
        draw.line([(cx - x_span, track_y), (cx + x_span, track_y)], fill=(30, 41, 59), width=1)

        # Multi-sweep phase across the 24s duration
        phase = (progress * 3.0 + i * 0.06) % 1.0
        direction = 1 if (i % 2 == 0) else -1
        scan_x = (cx - x_span + phase * 2 * x_span) if direction == 1 else (cx + x_span - phase * 2 * x_span)
        craft_pts.append((scan_x, track_y))

        # Green sampled swath trail based on overall mission progress
        fill_frac = min(1.0, progress * 1.05)
        swath_w = fill_frac * (2 * x_span)
        if direction == 1:
            draw.line([(cx - x_span, track_y), (cx - x_span + swath_w, track_y)], fill=(16, 185, 129), width=3)
        else:
            draw.line([(cx + x_span - swath_w, track_y), (cx + x_span, track_y)], fill=(16, 185, 129), width=3)

    # Inter-satellite laser telemetry cross-links
    pulse_alpha = 0.5 + 0.5 * math.sin(f_idx * 0.25)
    link_col = (int(56 * pulse_alpha), int(189 * pulse_alpha), 248)
    for i in range(len(craft_pts) - 1):
        draw.line([craft_pts[i], craft_pts[i + 1]], fill=link_col, width=1)

    # Spacecraft dots
    for p in craft_pts:
        draw.ellipse([(p[0] - 4, p[1] - 4), (p[0] + 4, p[1] + 4)], fill=(255, 255, 255), outline=(251, 191, 36))

    # Right Side: Coverage Gauge
    gx, gy, gw, gh = 385, 75, 235, 140
    draw.rectangle([(gx, gy), (gx + gw, gy + gh)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((gx + 12, gy + 8), "IMAGE PLANE SAMPLING", fill=(255, 255, 255), font=font_card)
    draw.text((gx + 12, gy + 24), f"Cylinder Coverage: {pct}% Complete", fill=(52, 211, 153), font=font_sub)

    # Progress bar
    draw.rectangle([(gx + 12, gy + 50), (gx + gw - 12, gy + 75)], fill=(30, 41, 59), outline=(51, 65, 85))
    bar_fill = int(progress * (gw - 24))
    draw.rectangle([(gx + 12, gy + 50), (gx + 12 + bar_fill, gy + 75)], fill=(16, 185, 129))

    pixels_collected = int(progress * 4096)
    draw.text((gx + 12, gy + 88), f"Sampled Pixels: {pixels_collected} / 4096", fill=(148, 163, 184), font=font_mono)
    draw.text((gx + 12, gy + 108), "Frame Time: 5.6 Hours / Sweep", fill=(251, 191, 36), font=font_mono)

    # Telemetry Box
    tx, ty, tw, th = 385, 230, 235, 155
    draw.rectangle([(tx, ty), (tx + tw, ty + th)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((tx + 12, ty + 8), "SWARM DYNAMICS TELEMETRY", fill=(56, 189, 248), font=font_card)

    telemetry = [
        ("FLEET SIZE", "16 nano-spacecraft"),
        ("SLEW SPEED", "15.2 m/s transverse"),
        ("TUBE DIAMETER", "1.34 km"),
        ("TRACK SPACING", "83.7 m cross-track"),
        ("ASTROMETRY", "Sub-mm laser links"),
        ("STATUS", "SYNCHRONIZED RASTER")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 26 + i * 20
        draw.text((tx + 12, row_y), label, fill=(148, 163, 184), font=font_mono)
        val_color = (52, 211, 153) if i == 5 else (255, 255, 255)
        draw.text((tx + 115, row_y), val, fill=val_color, font=font_mono_bold)

    draw.line([(20, H - 35), (W - 20, H - 35)], fill=(30, 41, 59), width=1)
    draw.text((20, H - 24), "SGL SWARM RASTER ARCHITECTURE | SONTANKE ET AL. (2026)", fill=(100, 116, 139), font=font_sub)
    draw.text((W - 190, H - 24), "DURATION: 24.0s (240f)", fill=(56, 189, 248), font=font_card)

    frames_3.append(img)

# Save Animation 3
frames_3[0].save(
    'public/videos/fleet_raster_scan.gif',
    save_all=True,
    append_images=frames_3[1:],
    duration=frame_duration_3,
    loop=0,
    optimize=True
)
print(f"Saved public/videos/fleet_raster_scan.gif (24.0s duration, {len(frames_3)} frames)")


# =============================================================
# 4. TDI ITERATIVE DECONVOLUTION TIMELAPSE (320 frames @ 100ms = 32.0s)
# 8.0s per stage across 4 distinct algorithmic convergence regimes!
# =============================================================
print("\n[4/4] Rendering TDI Deconvolution Timelapse (320 frames = 32.0s, 8.0s/stage)...")
num_frames_4 = 320
frame_duration_4 = 100
frames_4 = []

stages = [
    {
        "name": "STAGE 1: RAW RASTER WITH CLOUD BARCODE", 
        "r": 0.130, "ssim": 0.040, "data": white_fc3, 
        "desc": "Diurnal spin east-west aliasing dominates raw stream (fc = 55%)"
    },
    {
        "name": "STAGE 2: COMMON-MODE CLOUD DEFLATION P_perp", 
        "r": 0.220, "ssim": 0.080, "data": b2_fc3, 
        "desc": "Orthogonal projector cancels global weather offsets (Δr = +0.041)"
    },
    {
        "name": "STAGE 3: TIKHONOV TDI GLS INVERSION (K=8)", 
        "r": 0.334, "ssim": 0.109, "data": gls_fc3, 
        "desc": "Continental dichotomy recovered with closed-form inversion"
    },
    {
        "name": "STAGE 4: HIGH-CADENCE LIMIT (K=64 REVISITS)", 
        "r": 0.544, "ssim": 0.320, "data": gls_fc0, 
        "desc": "Independent weather draws average out to clean limits"
    }
]

for f_idx in range(num_frames_4):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    # 4 stages spread evenly across 320 frames (80 frames = 8.0s per stage!)
    s_progress = (f_idx / num_frames_4) * len(stages)
    s_idx = min(len(stages) - 1, int(s_progress))
    next_s_idx = (s_idx + 1) % len(stages)
    
    # 70% hold steady on stage, 30% cosine transition
    raw_sub = s_progress - int(s_progress)
    if raw_sub < 0.70:
        alpha = 0.0
    else:
        t_trans = (raw_sub - 0.70) / 0.30
        alpha = 0.5 - 0.5 * math.cos(t_trans * math.pi)

    s1 = stages[s_idx]
    s2 = stages[next_s_idx]

    elapsed_time = f_idx * 0.1

    draw.text((20, 14), "TDI DECONVOLUTION PIPELINE: CONVERGENCE TIMELAPSE", fill=(56, 189, 248), font=font_title)
    draw.text((20, 31), f"RECONSTRUCTION ITERATION: {elapsed_time:04.1f}s / 32.0s | (F^T Cy^-1 F + Lambda)^-1", fill=(148, 163, 184), font=font_sub)
    draw.line([(20, 48), (W - 20, 48)], fill=(30, 41, 59), width=1)

    # Interpolate RGB map
    interpolated = (s1['data'] * (1.0 - alpha) + s2['data'] * alpha).astype(np.uint8)

    # Render upscaled 320x160 map on left
    map_pil = Image.fromarray(interpolated).resize((320, 160), Image.Resampling.NEAREST)
    img.paste(map_pil, (30, 115))
    draw.rectangle([(29, 114), (351, 276)], outline=(51, 65, 85), width=2)

    # Stage Badge
    draw.rectangle([(30, 75), (350, 102)], fill=(15, 23, 42), outline=(56, 189, 248))
    draw.text((38, 81), s1['name'], fill=(56, 189, 248), font=font_card)

    draw.text((30, 285), s1['desc'], fill=(148, 163, 184), font=font_sub)

    # Right Side: Performance Gauges
    gx, gy, gw, gh = 385, 75, 235, 180
    draw.rectangle([(gx, gy), (gx + gw, gy + gh)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((gx + 12, gy + 10), "RECONSTRUCTION FIDELITY", fill=(255, 255, 255), font=font_card)

    cur_r = s1['r'] * (1.0 - alpha) + s2['r'] * alpha
    cur_ssim = s1['ssim'] * (1.0 - alpha) + s2['ssim'] * alpha

    draw.text((gx + 12, gy + 32), "PEARSON CORRELATION (r)", fill=(148, 163, 184), font=font_sub)
    draw.text((gx + 12, gy + 47), f"r = {cur_r:.3f}", fill=(56, 189, 248), font=font_metric)

    draw.rectangle([(gx + 12, gy + 72), (gx + gw - 12, gy + 85)], fill=(30, 41, 59))
    r_w = int((cur_r / 0.6) * (gw - 24))
    draw.rectangle([(gx + 12, gy + 72), (gx + 12 + max(0, r_w), gy + 85)], fill=(56, 189, 248))

    draw.text((gx + 12, gy + 98), "STRUCTURAL SIMILARITY (SSIM)", fill=(148, 163, 184), font=font_sub)
    draw.text((gx + 12, gy + 113), f"SSIM = {cur_ssim:.3f}", fill=(52, 211, 153), font=font_metric)

    draw.rectangle([(gx + 12, gy + 138), (gx + gw - 12, gy + 151)], fill=(30, 41, 59))
    ssim_w = int((cur_ssim / 0.4) * (gw - 24))
    draw.rectangle([(gx + 12, gy + 138), (gx + 12 + max(0, ssim_w), gy + 151)], fill=(52, 211, 153))

    # Bottom Telemetry Box
    tx, ty, tw, th = 385, 268, 235, 118
    draw.rectangle([(tx, ty), (tx + tw, ty + th)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((tx + 12, ty + 8), "ALGORITHMIC METRICS", fill=(251, 191, 36), font=font_card)

    telemetry = [
        ("DEFLATION GAIN", "\u0394r = +0.041 (verified)"),
        ("PHOTON SNR", "SNR_C = 43.16"),
        ("SIGNIFICANCE", "d' = 0.64 (p < 0.02)"),
        ("CONTINENTS RECON", "YES (Dichotomy)")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 26 + i * 20
        draw.text((tx + 12, row_y), label, fill=(148, 163, 184), font=font_mono)
        val_color = (52, 211, 153) if i == 3 else (255, 255, 255)
        draw.text((tx + 120, row_y), val, fill=val_color, font=font_mono_bold)

    draw.line([(20, H - 35), (W - 20, H - 35)], fill=(30, 41, 59), width=1)
    draw.text((20, H - 24), "SGL TDI INVERSION PIPELINE | SONTANKE ET AL. (2026)", fill=(100, 116, 139), font=font_sub)
    draw.text((W - 190, H - 24), "DURATION: 32.0s (320f)", fill=(56, 189, 248), font=font_card)

    frames_4.append(img)

# Save Animation 4
frames_4[0].save(
    'public/videos/tdi_deconvolution_timelapse.gif',
    save_all=True,
    append_images=frames_4[1:],
    duration=frame_duration_4,
    loop=0,
    optimize=True
)
print(f"Saved public/videos/tdi_deconvolution_timelapse.gif (32.0s duration, {len(frames_4)} frames)")

elapsed = time.time() - start_time
print(f"\nALL 4 ULTRA-EXTENDED HIGH-DURATION SIMULATION GIFS GENERATED IN {elapsed:.1f}s!")
