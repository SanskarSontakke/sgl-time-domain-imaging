import json
import math
import numpy as np
from PIL import Image, ImageDraw

# Load truth and reconstruction map data
with open('public/data/reconstruction_maps.json', 'r') as f:
    data = json.load(f)

natural_truth = np.array(data['natural_truth']) # (36, 72, 3)
gls_fc3 = np.array(data['gls_natural']['fc_3']) # (36, 72, 3)
white_fc3 = np.array(data['white_natural']['fc_3']) # (36, 72, 3)
gls_fc0 = np.array(data['gls_natural']['fc_0']) # (36, 72, 3)
b2_fc3 = np.array(data['b2_natural']['fc_3']) # (36, 72, 3)

W, H = 640, 440

# =============================================================
# 1. PLANET ROTATION & CLOUD ADVECTION (120 frames @ 100ms = 12.0s)
# =============================================================
print("Rendering Animation 1: Extended Planet Rotation (120 frames = 12.0s)...")
num_frames_1 = 120
frame_duration_1 = 100 # 100ms per frame = 10 fps -> 12.0 seconds total loop
frames_1 = []

cx, cy, R = 195, 225, 135
light_history_1 = []

for f_idx in range(num_frames_1):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    sim_time_hours = (f_idx / num_frames_1) * 24.0
    rot_angle = (f_idx / num_frames_1) * 2 * math.pi
    cloud_advect = rot_angle * 1.35

    # Top Header
    draw.text((20, 14), "SOLAR GRAVITATIONAL LENS: TIME-DOMAIN SIMULATION", fill=(56, 189, 248))
    draw.text((20, 30), f"EXO-EARTH ROTATION • DIURNAL TIME: {sim_time_hours:04.1f}h / 24.0h • DYNAMIC CLOUDS", fill=(148, 163, 184))
    draw.line([(20, 48), (W - 20, 48)], fill=(30, 41, 59), width=1)

    # Coordinates grid
    y_indices, x_indices = np.ogrid[cy - R:cy + R + 1, cx - R:cx + R + 1]
    dx = (x_indices - cx) / R
    dy = (y_indices - cy) / R
    dist_sq = dx**2 + dy**2
    mask = dist_sq <= 1.0

    dz = np.sqrt(np.maximum(0.0, 1.0 - dist_sq))

    # Planetary obliquity tilt (23.4 degrees)
    tilt = math.radians(23.4)
    y_rot = dy * math.cos(tilt) - dz * math.sin(tilt)
    z_rot = dy * math.sin(tilt) + dz * math.cos(tilt)
    x_rot = dx

    lat = np.arcsin(np.clip(-y_rot, -1.0, 1.0))
    lon = np.arctan2(x_rot, z_rot) + rot_angle

    u = ((lon / (2 * math.pi)) % 1.0) * 72.0
    v = ((-lat / math.pi + 0.5) % 1.0) * 36.0
    map_x = np.clip(u.astype(int), 0, 71)
    map_y = np.clip(v.astype(int), 0, 35)

    base_rgb = natural_truth[map_y, map_x].astype(float)

    # Dynamic cloud evolution
    cloud_lon = lon + cloud_advect * (0.85 + 0.35 * np.cos(lat))
    cloud_wave = np.sin(cloud_lon * 3.2 + lat * 4.1) * np.cos(cloud_lon * 2.1 - lat * 3.3)
    cloud_jet = np.sin(lat * 5.8)
    has_cloud = (cloud_wave + cloud_jet * 0.32) > 0.12
    cloud_dens = np.where(has_cloud, np.clip(0.48 + 0.42 * cloud_wave, 0.0, 1.0), 0.0)

    # Illumination from host star
    sun_x, sun_y, sun_z = -0.78, 0.22, 0.62
    sun_norm = math.sqrt(sun_x**2 + sun_y**2 + sun_z**2)
    illum = np.maximum(0.04, (dx * (sun_x/sun_norm) + dy * (sun_y/sun_norm) + dz * (sun_z/sun_norm)))

    # Blend clouds & ice
    cloud_rgb = np.array([245.0, 250.0, 255.0])
    c_dens_3d = cloud_dens[..., np.newaxis]
    blended_rgb = base_rgb * (1.0 - c_dens_3d) + cloud_rgb * c_dens_3d

    polar_mask = np.abs(lat) > 1.05
    blended_rgb[polar_mask] = [238.0, 246.0, 255.0]

    illum_3d = illum[..., np.newaxis]
    final_rgb = np.clip(blended_rgb * illum_3d, 0, 255).astype(np.uint8)

    rendered_img = Image.fromarray(final_rgb)
    img.paste(rendered_img, (cx - R, cy - R), mask=Image.fromarray((mask * 255).astype(np.uint8)))
    draw.ellipse([(cx - R - 2, cy - R - 2), (cx + R + 2, cy + R + 2)], outline=(56, 189, 248), width=2)

    visible_flux = float(np.mean(final_rgb[mask]) / 255.0)
    light_history_1.append(visible_flux)

    # Right Side: Photometric Light Curve Graph
    gx, gy, gw, gh = 385, 75, 235, 140
    draw.rectangle([(gx, gy), (gx + gw, gy + gh)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((gx + 12, gy + 8), "DIURNAL LIGHT CURVE F(t)", fill=(255, 255, 255))
    draw.text((gx + 12, gy + 22), "Normalized Disk-Averaged Photometry", fill=(148, 163, 184))

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

    # Current geographic feature in central meridian view
    meridian_lon_deg = int((sim_time_hours / 24.0) * 360) % 360
    if 30 <= meridian_lon_deg < 120:
        viewed_feature = "Americas & Caribbean Basins"
    elif 120 <= meridian_lon_deg < 240:
        viewed_feature = "Pacific Ocean & Island Arcs"
    elif 240 <= meridian_lon_deg < 320:
        viewed_feature = "Eurasia / Africa Continents"
    else:
        viewed_feature = "Atlantic Ocean Meridian"

    # Telemetry Box
    tx, ty, tw, th = 385, 230, 235, 155
    draw.rectangle([(tx, ty), (tx + tw, ty + th)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((tx + 12, ty + 8), "SIMULATION TELEMETRY", fill=(56, 189, 248))

    telemetry = [
        ("DIURNAL TIME", f"{sim_time_hours:04.1f}h / 24.0h"),
        ("MERIDIAN REGION", viewed_feature),
        ("CLOUD FRACTION", "f_c = 55% (fiducial)"),
        ("ZONAL ADVECTION", "v_jet = +21 m/s"),
        ("AXIAL OBLIQUITY", "23.4° tilt"),
        ("STATUS", "DIURNAL CYCLE ACTIVE")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 26 + i * 20
        draw.text((tx + 12, row_y), label, fill=(148, 163, 184))
        draw.text((tx + 125, row_y), val, fill=(255, 255, 255) if i < 5 else (52, 211, 153))

    draw.line([(20, H - 35), (W - 20, H - 35)], fill=(30, 41, 59), width=1)
    draw.text((20, H - 24), "PEER-REVIEWED ASTROPHYSICAL RESEARCH • SONTANKE ET AL. (2026)", fill=(100, 116, 139))
    draw.text((W - 220, H - 24), f"DURATION: 12.0s • 120 FRAMES", fill=(56, 189, 248))

    frames_1.append(img)

frames_1[0].save(
    'public/videos/planet_rotation_clouds.gif',
    save_all=True,
    append_images=frames_1[1:],
    duration=frame_duration_1,
    loop=0,
    optimize=True
)
print("Saved public/videos/planet_rotation_clouds.gif (12.0s duration)")


# =============================================================
# 2. EINSTEIN RING OPTICAL CONVOLUTION (120 frames @ 100ms = 12.0s)
# =============================================================
print("Rendering Animation 2: Extended Einstein Ring (120 frames = 12.0s)...")
num_frames_2 = 120
frame_duration_2 = 100
frames_2 = []

cx, cy = 195, 225
R_coronagraph = 52
R_ring = 118

for f_idx in range(num_frames_2):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    sim_t_sec = f_idx * 0.1
    t = (f_idx / num_frames_2) * 4 * math.pi # 2 full optical cycles

    # Dynamic off-axis drift rho(t): wanders from on-axis 0m out to 2.8m and back
    rho_t = 1.4 * (1.0 + math.sin(t * 0.5))

    draw.text((20, 14), "SGL CORONAGRAPH TELESCOPE: 650 AU", fill=(56, 189, 248))
    draw.text((20, 30), f"OPTICAL CONVOLUTION • OFF-AXIS DISTANCE: rho = {rho_t:.2f} m • K(rho) = d/(4 rho)", fill=(148, 163, 184))
    draw.line([(20, 48), (W - 20, 48)], fill=(30, 41, 59), width=1)

    # Solar Corona Glow
    for r_step in range(R_coronagraph, R_coronagraph + 48):
        draw.ellipse([(cx - r_step, cy - r_step), (cx + r_step, cy + r_step)], outline=(217, 119, 6))

    # Luminous Einstein Ring with off-axis gravitational arc split
    for angle_deg in range(360):
        theta = math.radians(angle_deg)
        # As rho increases, the ring splits into opposing crescent arcs along the shear axis
        arc_factor = math.exp(-((math.sin(theta - t*0.2)**2) * (rho_t * 1.8)))
        mod = (0.35 + 0.35 * math.sin(theta * 2 + t) + 0.3 * arc_factor)

        ring_col = (int(56 * mod + 160 * (1 - mod)), int(189 * mod + 40), 248)

        px = cx + int(R_ring * math.cos(theta))
        py = cy + int(R_ring * math.sin(theta))
        if mod > 0.2:
            draw.ellipse([(px - 2, py - 2), (px + 2, py + 2)], fill=ring_col)

    # Polar Grid Marks
    for r in [60, 90, 120, 150]:
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(30, 41, 59), width=1)
    draw.line([(cx - 160, cy), (cx + 160, cy)], fill=(30, 41, 59), width=1)
    draw.line([(cx, cy - 160), (cx, cy + 160)], fill=(30, 41, 59), width=1)

    # Dark Central Occulter Mask
    draw.ellipse([(cx - R_coronagraph, cy - R_coronagraph), (cx + R_coronagraph, cy + R_coronagraph)], fill=(15, 23, 42), outline=(239, 68, 68), width=2)
    draw.text((cx - 40, cy - 6), "OCCULTER MASK", fill=(239, 68, 68))

    # Right Side: Azimuthal Profile I(theta)
    gx, gy, gw, gh = 385, 75, 235, 140
    draw.rectangle([(gx, gy), (gx + gw, gy + gh)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((gx + 12, gy + 8), "AZIMUTHAL INTENSITY PROFILE I(θ)", fill=(255, 255, 255))
    draw.text((gx + 12, gy + 22), f"Off-Axis Offset: rho = {rho_t:.2f} m", fill=(251, 191, 36))

    for y_step in range(gy + 45, gy + gh, 30):
        draw.line([(gx + 5, y_step), (gx + gw - 5, y_step)], fill=(30, 41, 59), width=1)

    profile_pts = []
    for deg in range(0, 360, 4):
        theta = math.radians(deg)
        arc_factor = math.exp(-((math.sin(theta - t*0.2)**2) * (rho_t * 1.8)))
        mod = (0.35 + 0.35 * math.sin(theta * 2 + t) + 0.3 * arc_factor)
        px = gx + int((deg / 360) * (gw - 24)) + 12
        py = gy + gh - int(mod * (gh - 55)) - 10
        profile_pts.append((px, py))

    if len(profile_pts) > 1:
        draw.line(profile_pts, fill=(56, 189, 248), width=2)

    # Telemetry Box
    tx, ty, tw, th = 385, 230, 235, 155
    draw.rectangle([(tx, ty), (tx + tw, ty + th)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((tx + 12, ty + 8), "CORONAGRAPH TELEMETRY", fill=(56, 189, 248))

    telemetry = [
        ("DISTANCE", "z = 650 AU"),
        ("SGL GAIN", "mu ~ 10^11"),
        ("OCCULTER SUPPRESSION", "10^-10 starlight"),
        ("CURRENT OFFSET", f"rho = {rho_t:.2f} m"),
        ("SAMPLE SNR", "SNR_C = 43.16"),
        ("STATUS", "RING CONVOLUTION ACTIVE")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 26 + i * 20
        draw.text((tx + 12, row_y), label, fill=(148, 163, 184))
        draw.text((tx + 125, row_y), val, fill=(255, 255, 255) if i < 5 else (52, 211, 153))

    draw.line([(20, H - 35), (W - 20, H - 35)], fill=(30, 41, 59), width=1)
    draw.text((20, H - 24), "SOLAR GRAVITATIONAL LENS CORONAGRAPH • SONTANKE ET AL. (2026)", fill=(100, 116, 139))
    draw.text((W - 220, H - 24), f"DURATION: 12.0s • 120 FRAMES", fill=(56, 189, 248))

    frames_2.append(img)

frames_2[0].save(
    'public/videos/einstein_ring_convolution.gif',
    save_all=True,
    append_images=frames_2[1:],
    duration=frame_duration_2,
    loop=0,
    optimize=True
)
print("Saved public/videos/einstein_ring_convolution.gif (12.0s duration)")


# =============================================================
# 3. FLEET FORMATION RASTER SCANNING (140 frames @ 90ms = 12.6s)
# =============================================================
print("Rendering Animation 3: Extended Fleet Formation (140 frames = 12.6s)...")
num_frames_3 = 140
frame_duration_3 = 90
frames_3 = []
num_crafts = 16

for f_idx in range(num_frames_3):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    progress = f_idx / num_frames_3
    pct = int(progress * 100)

    draw.text((20, 14), "SGL MULTI-SPACECRAFT FLEET FORMATION", fill=(56, 189, 248))
    draw.text((20, 30), f"16 NANO-SPACECRAFT SWEEPING THE 1.34 KM FOCAL CYLINDER • SAMPLING: {pct}%", fill=(148, 163, 184))
    draw.line([(20, 48), (W - 20, 48)], fill=(30, 41, 59), width=1)

    # Focal Cylinder Profile (Left)
    cx, cy, rx, ry = 195, 225, 145, 125
    draw.ellipse([(cx - rx, cy - ry), (cx + rx, cy + ry)], outline=(51, 65, 85), width=2)
    draw.text((cx - 50, cy - ry - 16), "1.34 KM FOCAL TUBE", fill=(148, 163, 184))

    # Spacecraft positions
    craft_pts = []
    for i in range(num_crafts):
        track_y = cy - ry + 18 + int((i / (num_crafts - 1)) * (2 * ry - 36))
        y_norm = (track_y - cy) / ry
        x_span = rx * math.sqrt(max(0.0, 1.0 - y_norm**2))

        # Track line
        draw.line([(cx - x_span, track_y), (cx + x_span, track_y)], fill=(30, 41, 59), width=1)

        # Multi-sweep phase
        phase = (progress * 2.5 + i * 0.07) % 1.0
        direction = 1 if (i % 2 == 0) else -1
        scan_x = (cx - x_span + phase * 2 * x_span) if direction == 1 else (cx + x_span - phase * 2 * x_span)
        craft_pts.append((scan_x, track_y))

        # Green sampled swath trail
        start_x = (cx - x_span) if direction == 1 else scan_x
        end_x = scan_x if direction == 1 else (cx + x_span)
        draw.line([(start_x, track_y), (end_x, track_y)], fill=(16, 185, 129), width=2)

    # Inter-satellite laser telemetry links
    for i in range(len(craft_pts) - 1):
        p1 = craft_pts[i]
        p2 = craft_pts[i + 1]
        draw.line([p1, p2], fill=(56, 189, 248), width=1)

    # Spacecraft dots
    for p in craft_pts:
        draw.ellipse([(p[0] - 4, p[1] - 4), (p[0] + 4, p[1] + 4)], fill=(255, 255, 255), outline=(251, 191, 36))

    # Right Side: Coverage Gauge
    gx, gy, gw, gh = 385, 75, 235, 140
    draw.rectangle([(gx, gy), (gx + gw, gy + gh)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((gx + 12, gy + 8), "IMAGE PLANE SAMPLING", fill=(255, 255, 255))
    draw.text((gx + 12, gy + 24), f"Cylinder Coverage: {pct}% Complete", fill=(52, 211, 153))

    # Progress bar
    draw.rectangle([(gx + 12, gy + 50), (gx + gw - 12, gy + 75)], fill=(30, 41, 59), outline=(51, 65, 85))
    bar_fill = int((progress) * (gw - 24))
    draw.rectangle([(gx + 12, gy + 50), (gx + 12 + bar_fill, gy + 75)], fill=(16, 185, 129))

    pixels_collected = int(progress * 4096)
    draw.text((gx + 12, gy + 90), f"Sampled Pixels: {pixels_collected} / 4096", fill=(148, 163, 184))
    draw.text((gx + 12, gy + 110), f"Full Frame Time: 5.6 Hours", fill=(251, 191, 36))

    # Telemetry Box
    tx, ty, tw, th = 385, 230, 235, 155
    draw.rectangle([(tx, ty), (tx + tw, ty + th)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((tx + 12, ty + 8), "SWARM DYNAMICS TELEMETRY", fill=(56, 189, 248))

    telemetry = [
        ("FLEET SIZE", "16 nano-spacecraft"),
        ("SLEW SPEED", "15.2 m/s transverse"),
        ("CYLINDER DIAMETER", "1.34 km"),
        ("FORMATION SPACING", "83.7 m track-to-track"),
        ("LASER LINK", "Sub-mm astrometry"),
        ("STATUS", "SYNCHRONIZED RASTER")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 26 + i * 20
        draw.text((tx + 12, row_y), label, fill=(148, 163, 184))
        draw.text((tx + 125, row_y), val, fill=(255, 255, 255) if i < 5 else (52, 211, 153))

    draw.line([(20, H - 35), (W - 20, H - 35)], fill=(30, 41, 59), width=1)
    draw.text((20, H - 24), "CONCURRENT SWARM RASTER SCANNING • SONTANKE ET AL. (2026)", fill=(100, 116, 139))
    draw.text((W - 220, H - 24), f"DURATION: 12.6s • 140 FRAMES", fill=(56, 189, 248))

    frames_3.append(img)

frames_3[0].save(
    'public/videos/fleet_raster_scan.gif',
    save_all=True,
    append_images=frames_3[1:],
    duration=frame_duration_3,
    loop=0,
    optimize=True
)
print("Saved public/videos/fleet_raster_scan.gif (12.6s duration)")


# =============================================================
# 4. TDI ITERATIVE DECONVOLUTION TIMELAPSE (160 frames @ 100ms = 16.0s)
# =============================================================
print("Rendering Animation 4: Extended TDI Timelapse (160 frames = 16.0s)...")
num_frames_4 = 160
frame_duration_4 = 100
frames_4 = []

stages = [
    {
        "name": "STAGE 1: RAW RASTER WITH CLOUD BARCODE", 
        "r": 0.13, "ssim": 0.04, "data": white_fc3, 
        "desc": "Diurnal spin east-west aliasing dominates raw stream (fc = 55%)"
    },
    {
        "name": "STAGE 2: COMMON-MODE CLOUD DEFLATION P_perp", 
        "r": 0.22, "ssim": 0.08, "data": b2_fc3, 
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

    # 4 stages spread evenly across 160 frames (40 frames = 4.0s per stage!)
    s_progress = (f_idx / num_frames_4) * len(stages)
    s_idx = min(len(stages) - 1, int(s_progress))
    next_s_idx = (s_idx + 1) % len(stages)
    
    # Sigmoidal smooth transition between stages
    raw_alpha = s_progress - int(s_progress)
    alpha = 0.5 - 0.5 * math.cos(raw_alpha * math.pi)

    s1 = stages[s_idx]
    s2 = stages[next_s_idx]

    elapsed_time = f_idx * 0.1

    draw.text((20, 14), "TDI DECONVOLUTION PIPELINE: CONVERGENCE TIMELAPSE", fill=(56, 189, 248))
    draw.text((20, 30), f"RECONSTRUCTION ITERATION: {elapsed_time:04.1f}s / 16.0s • (F^T C_y^-1 F + Lambda)^-1", fill=(148, 163, 184))
    draw.line([(20, 48), (W - 20, 48)], fill=(30, 41, 59), width=1)

    # Interpolate RGB map
    interpolated = (s1['data'] * (1.0 - alpha) + s2['data'] * alpha).astype(np.uint8)

    # Render upscaled 320x160 map on left
    map_pil = Image.fromarray(interpolated).resize((320, 160), Image.Resampling.NEAREST)
    img.paste(map_pil, (30, 120))
    draw.rectangle([(29, 119), (351, 281)], outline=(51, 65, 85), width=2)

    # Stage Badge
    draw.rectangle([(30, 75), (350, 105)], fill=(15, 23, 42), outline=(56, 189, 248))
    draw.text((38, 83), s1['name'], fill=(56, 189, 248))

    draw.text((30, 290), s1['desc'], fill=(148, 163, 184))

    # Right Side: Performance Gauges
    gx, gy, gw, gh = 385, 75, 235, 180
    draw.rectangle([(gx, gy), (gx + gw, gy + gh)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((gx + 12, gy + 10), "RECONSTRUCTION FIDELITY", fill=(255, 255, 255))

    cur_r = s1['r'] * (1.0 - alpha) + s2['r'] * alpha
    cur_ssim = s1['ssim'] * (1.0 - alpha) + s2['ssim'] * alpha

    draw.text((gx + 12, gy + 35), "PEARSON CORRELATION (r)", fill=(148, 163, 184))
    draw.text((gx + 12, gy + 52), f"r = {cur_r:.3f}", fill=(56, 189, 248))

    draw.rectangle([(gx + 12, gy + 75), (gx + gw - 12, gy + 88)], fill=(30, 41, 59))
    r_w = int((cur_r / 0.6) * (gw - 24))
    draw.rectangle([(gx + 12, gy + 75), (gx + 12 + max(0, r_w), gy + 88)], fill=(56, 189, 248))

    draw.text((gx + 12, gy + 105), "STRUCTURAL SIMILARITY (SSIM)", fill=(148, 163, 184))
    draw.text((gx + 12, gy + 122), f"SSIM = {cur_ssim:.3f}", fill=(52, 211, 153))

    draw.rectangle([(gx + 12, gy + 145), (gx + gw - 12, gy + 158)], fill=(30, 41, 59))
    ssim_w = int((cur_ssim / 0.4) * (gw - 24))
    draw.rectangle([(gx + 12, gy + 145), (gx + 12 + max(0, ssim_w), gy + 158)], fill=(52, 211, 153))

    # Bottom Telemetry Box
    tx, ty, tw, th = 385, 270, 235, 115
    draw.rectangle([(tx, ty), (tx + tw, ty + th)], fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((tx + 12, ty + 8), "ALGORITHMIC METRICS", fill=(251, 191, 36))

    telemetry = [
        ("CLOUD DEFLATION GAIN", "Δr = +0.041 (verified)"),
        ("PHOTON SNR", "SNR_C = 43.16"),
        ("SIGNIFICANCE", "d' = 0.64 (p < 0.02)"),
        ("CONTINENTS RECOVERED", "YES (Dichotomy)")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 26 + i * 20
        draw.text((tx + 12, row_y), label, fill=(148, 163, 184))
        draw.text((tx + 135, row_y), val, fill=(255, 255, 255) if i < 3 else (52, 211, 153))

    draw.line([(20, H - 35), (W - 20, H - 35)], fill=(30, 41, 59), width=1)
    draw.text((20, H - 24), "TIME-DOMAIN INVERSION (TDI) PIPELINE • SONTANKE ET AL. (2026)", fill=(100, 116, 139))
    draw.text((W - 220, H - 24), f"DURATION: 16.0s • 160 FRAMES", fill=(56, 189, 248))

    frames_4.append(img)

frames_4[0].save(
    'public/videos/tdi_deconvolution_timelapse.gif',
    save_all=True,
    append_images=frames_4[1:],
    duration=frame_duration_4,
    loop=0,
    optimize=True
)
print("Saved public/videos/tdi_deconvolution_timelapse.gif (16.0s duration)")

print("ALL EXTENDED-DURATION HIGH-FPS GIFS GENERATED SUCCESSFULLY!")
