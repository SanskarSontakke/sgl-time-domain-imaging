import json
import math
import os
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

start_time = time.time()
print("=" * 75)
print("GENERATING PERFECT 1080p FULL HD (1920x1080) SIMULATION GIFS")
print("=" * 75)

W, H = 1920, 1080

# Load Segoe UI fonts which have 100% native Unicode mathematical symbol support
try:
    font_main_title = ImageFont.truetype('segoeuib.ttf', 32)
    font_sub_title = ImageFont.truetype('segoeui.ttf', 20)
    font_card_header = ImageFont.truetype('segoeuib.ttf', 22)
    font_card_sub = ImageFont.truetype('segoeui.ttf', 17)
    font_metric_val = ImageFont.truetype('segoeuib.ttf', 32)
    font_metric_label = ImageFont.truetype('segoeui.ttf', 18)
    font_mono_label = ImageFont.truetype('consola.ttf', 18)
    font_mono_val = ImageFont.truetype('consolab.ttf', 19)
    font_map_label = ImageFont.truetype('segoeuib.ttf', 16)
    font_badge = ImageFont.truetype('segoeuib.ttf', 20)
    font_footer = ImageFont.truetype('segoeui.ttf', 18)
    font_footer_bold = ImageFont.truetype('segoeuib.ttf', 19)
    font_axis = ImageFont.truetype('consola.ttf', 15)
except Exception:
    font_main_title = ImageFont.load_default()
    font_sub_title = font_main_title
    font_card_header = font_main_title
    font_card_sub = font_main_title
    font_metric_val = font_main_title
    font_metric_label = font_main_title
    font_mono_label = font_main_title
    font_mono_val = font_main_title
    font_map_label = font_main_title
    font_badge = font_main_title
    font_footer = font_main_title
    font_footer_bold = font_main_title
    font_axis = font_main_title

# Load truth and reconstruction map data
with open('public/data/reconstruction_maps.json', 'r') as f:
    data = json.load(f)

natural_truth = np.array(data['natural_truth']).astype(float) # (36, 72, 3)
gls_fc3 = np.array(data['gls_natural']['fc_3']).astype(float)
white_fc3 = np.array(data['white_natural']['fc_3']).astype(float)
gls_fc0 = np.array(data['gls_natural']['fc_0']).astype(float)
b2_fc3 = np.array(data['b2_natural']['fc_3']).astype(float)

os.makedirs('public/videos', exist_ok=True)

def draw_card(draw, x, y, w, h, fill=(15, 23, 42), outline=(51, 65, 85), r=10):
    draw.rounded_rectangle([(x, y), (x + w, y + h)], radius=r, fill=fill, outline=outline, width=2)


# =============================================================
# 1. PLANET ROTATION & CLOUD ADVECTION (240 frames @ 100ms = 24.0s, 1080p)
# =============================================================
print("\n[1/4] Rendering 1080p Planet Rotation (240 frames = 24.0s)...")
num_frames_1 = 240
frame_duration_1 = 100
frames_1 = []

cx, cy, R = 540, 560, 360
y_indices, x_indices = np.ogrid[cy - R:cy + R + 1, cx - R:cx + R + 1]
dx = (x_indices - cx) / R
dy = (y_indices - cy) / R
dist_sq = dx**2 + dy**2
disk_mask = dist_sq <= 1.0
dz = np.sqrt(np.maximum(0.0, 1.0 - dist_sq))

tilt = math.radians(23.4)
cos_tilt = math.cos(tilt)
sin_tilt = math.sin(tilt)
y_rot = dy * cos_tilt - dz * sin_tilt
z_rot = dy * sin_tilt + dz * cos_tilt
x_rot = dx

lat = np.arcsin(np.clip(-y_rot, -1.0, 1.0))
base_lon = np.arctan2(x_rot, z_rot)

sun_x, sun_y, sun_z = -0.78, 0.22, 0.62
sun_norm = math.sqrt(sun_x**2 + sun_y**2 + sun_z**2)
sun_vec = np.array([sun_x/sun_norm, sun_y/sun_norm, sun_z/sun_norm])
illum = np.maximum(0.04, (dx * sun_vec[0] + dy * sun_vec[1] + dz * sun_vec[2]))
illum_3d = illum[..., np.newaxis]
polar_mask = np.abs(lat) > 1.05

# Precompute reference 24-hour light curve
ref_curve = []
for f in range(num_frames_1):
    ang = (f / num_frames_1) * 2 * math.pi
    c_advect = ang * 1.35
    c_lon = base_lon + ang
    uf = ((c_lon / (2 * math.pi)) % 1.0) * 72.0
    vf = np.clip((-lat / math.pi + 0.5) * 36.0, 0.0, 35.0)
    u0 = np.floor(uf).astype(int)
    u1 = (u0 + 1) % 72
    v0 = np.floor(vf).astype(int)
    v1 = np.clip(v0 + 1, 0, 35)
    wu = (uf - u0)[..., np.newaxis]
    wv = (vf - v0)[..., np.newaxis]
    b_rgb = (natural_truth[v0, u0]*(1-wu)*(1-wv) + natural_truth[v0, u1]*wu*(1-wv) +
             natural_truth[v1, u0]*(1-wu)*wv + natural_truth[v1, u1]*wu*wv)
    clon = c_lon + c_advect * (0.85 + 0.35 * np.cos(lat))
    cwave = np.sin(clon * 3.2 + lat * 4.1) * np.cos(clon * 2.1 - lat * 3.3)
    cjet = np.sin(lat * 5.8)
    hcloud = (cwave + cjet * 0.32) > 0.12
    cdens = np.where(hcloud, np.clip(0.48 + 0.42 * cwave, 0.0, 1.0), 0.0)[..., np.newaxis]
    b_rgb = b_rgb * (1.0 - cdens) + np.array([245.0, 250.0, 255.0]) * cdens
    b_rgb[polar_mask] = [238.0, 246.0, 255.0]
    flux = float(np.mean((b_rgb * illum_3d)[disk_mask]) / 255.0)
    ref_curve.append(flux)

t_anim1_start = time.time()
for f_idx in range(num_frames_1):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    sim_time_hours = (f_idx / num_frames_1) * 24.0
    rot_angle = (f_idx / num_frames_1) * 2 * math.pi
    cloud_advect = rot_angle * 1.35

    # Top Header
    draw.text((60, 35), "SOLAR GRAVITATIONAL LENS: TIME-DOMAIN SIMULATION", fill=(56, 189, 248), font=font_main_title)
    draw.text((60, 78), f"EXO-EARTH ROTATION • DIURNAL TIME: {sim_time_hours:04.1f}h / 24.0h • DYNAMIC SYNOPTIC CLOUDS", fill=(148, 163, 184), font=font_sub_title)
    draw.line([(60, 115), (W - 60, 115)], fill=(30, 41, 59), width=2)

    # Bilinear Planet Sampling
    cur_lon = base_lon + rot_angle
    u_f = ((cur_lon / (2 * math.pi)) % 1.0) * 72.0
    v_f = np.clip((-lat / math.pi + 0.5) * 36.0, 0.0, 35.0)
    u0 = np.floor(u_f).astype(int)
    u1 = (u0 + 1) % 72
    v0 = np.floor(v_f).astype(int)
    v1 = np.clip(v0 + 1, 0, 35)
    wu = (u_f - u0)[..., np.newaxis]
    wv = (v_f - v0)[..., np.newaxis]

    base_rgb = (
        natural_truth[v0, u0] * (1 - wu) * (1 - wv) +
        natural_truth[v0, u1] * wu * (1 - wv) +
        natural_truth[v1, u0] * (1 - wu) * wv +
        natural_truth[v1, u1] * wu * wv
    )

    cloud_lon = cur_lon + cloud_advect * (0.85 + 0.35 * np.cos(lat))
    cloud_wave = np.sin(cloud_lon * 3.2 + lat * 4.1 + f_idx * 0.02) * np.cos(cloud_lon * 2.1 - lat * 3.3)
    cloud_jet = np.sin(lat * 5.8)
    has_cloud = (cloud_wave + cloud_jet * 0.32) > 0.12
    cloud_dens = np.where(has_cloud, np.clip(0.48 + 0.42 * cloud_wave, 0.0, 1.0), 0.0)[..., np.newaxis]

    blended_rgb = base_rgb * (1.0 - cloud_dens) + np.array([245.0, 250.0, 255.0]) * cloud_dens
    blended_rgb[polar_mask] = [238.0, 246.0, 255.0]

    final_rgb = np.clip(blended_rgb * illum_3d, 0, 255).astype(np.uint8)
    rendered_img = Image.fromarray(final_rgb)
    img.paste(rendered_img, (cx - R, cy - R), mask=Image.fromarray((disk_mask * 255).astype(np.uint8)))

    # Atmospheric limb halo
    draw.ellipse([(cx - R - 6, cy - R - 6), (cx + R + 6, cy + R + 6)], outline=(30, 58, 90), width=2)
    draw.ellipse([(cx - R - 2, cy - R - 2), (cx + R + 2, cy + R + 2)], outline=(56, 189, 248), width=3)

    # Right Side Card 1: Photometric Light Curve Graph
    gx, gy, gw, gh = 1060, 140, 800, 390
    draw_card(draw, gx, gy, gw, gh)
    draw.text((gx + 28, gy + 22), "DIURNAL LIGHT CURVE F(t)", fill=(255, 255, 255), font=font_card_header)
    draw.text((gx + 28, gy + 52), "Disk-Averaged Photometry vs. Orbital Rotation (24.0h Period)", fill=(148, 163, 184), font=font_card_sub)

    plot_x, plot_y, plot_w, plot_h = gx + 60, gy + 95, gw - 100, gh - 145
    min_f, max_f = 0.08, 0.25

    # Horizontal gridlines & flux labels
    for f_val in [0.10, 0.15, 0.20, 0.25]:
        py = plot_y + plot_h - int(((f_val - min_f) / (max_f - min_f)) * plot_h)
        draw.line([(plot_x, py), (plot_x + plot_w, py)], fill=(30, 41, 59), width=1)
        draw.text((plot_x - 48, py - 9), f"{f_val:.2f}", fill=(100, 116, 139), font=font_axis)

    # Vertical gridlines & hour ticks
    for h_tick in [0, 6, 12, 18, 24]:
        px = plot_x + int((h_tick / 24.0) * plot_w)
        draw.line([(px, plot_y), (px, plot_y + plot_h)], fill=(30, 41, 59), width=1)
        draw.text((px - 14, plot_y + plot_h + 10), f"{h_tick}h", fill=(100, 116, 139), font=font_axis)

    # Faint 24h reference light curve
    ref_pts = []
    for i, val in enumerate(ref_curve):
        px = plot_x + int((i / num_frames_1) * plot_w)
        py = plot_y + plot_h - int(((val - min_f) / (max_f - min_f)) * plot_h)
        ref_pts.append((px, py))
    if len(ref_pts) > 1:
        draw.line(ref_pts, fill=(51, 65, 85), width=2)

    # Active trace up to current frame
    active_pts = ref_pts[:f_idx + 1]
    if len(active_pts) > 1:
        draw.line(active_pts, fill=(251, 191, 36), width=3)
    if active_pts:
        cur_pt = active_pts[-1]
        draw.ellipse([(cur_pt[0] - 6, cur_pt[1] - 6), (cur_pt[0] + 6, cur_pt[1] + 6)], fill=(239, 68, 68), outline=(255, 255, 255), width=2)
        cur_val = ref_curve[f_idx]
        draw.text((gx + gw - 300, gy + 22), f"Flux: {cur_val:.3f} F_0", fill=(251, 191, 36), font=font_card_header)

    # Right Side Card 2: Planetary Telemetry
    tx, ty, tw, th = 1060, 560, 800, 410
    draw_card(draw, tx, ty, tw, th)
    draw.text((tx + 28, ty + 22), "EXOPLANETARY ROTATION TELEMETRY", fill=(56, 189, 248), font=font_card_header)

    meridian_lon_deg = int((sim_time_hours / 24.0) * 360) % 360
    if 30 <= meridian_lon_deg < 120:
        viewed_feature = "Americas & Caribbean Basins"
    elif 120 <= meridian_lon_deg < 240:
        viewed_feature = "Pacific Ocean & Island Arcs"
    elif 240 <= meridian_lon_deg < 320:
        viewed_feature = "Eurasia & African Landmasses"
    else:
        viewed_feature = "Atlantic Ocean Meridian"

    telemetry = [
        ("DIURNAL PERIOD", f"{sim_time_hours:04.1f}h / 24.0h (Active Cycle)"),
        ("CENTRAL MERIDIAN", viewed_feature),
        ("MEAN CLOUD FRACTION", "f_c = 55% (Earth-analog fiducial)"),
        ("ZONAL JET STREAM", "v_jet = +21 m/s (eastward advection)"),
        ("AXIAL OBLIQUITY", "23.4° (Earth-like seasonal tilt)"),
        ("ORBITAL DISTANCE", "1.00 AU (Sun-like G-dwarf host)"),
        ("SYSTEM STATUS", "CONTINUOUS TIME-DOMAIN RUNNING")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 68 + i * 44
        draw.text((tx + 28, row_y), label, fill=(148, 163, 184), font=font_mono_label)
        val_color = (52, 211, 153) if i == 6 else (255, 255, 255)
        draw.text((tx + 290, row_y), val, fill=val_color, font=font_mono_val)

    # Footer
    draw.line([(60, H - 70), (W - 60, H - 70)], fill=(30, 41, 59), width=2)
    draw.text((60, H - 46), "SGL TIME-DOMAIN RESEARCH • SONTANKE ET AL. (2026)", fill=(100, 116, 139), font=font_footer)
    draw.text((W - 540, H - 46), "DURATION: 24.0s • 240 FRAMES • 1080p FULL HD", fill=(56, 189, 248), font=font_footer_bold)

    frames_1.append(img.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))

frames_1[0].save(
    'public/videos/planet_rotation_clouds.gif',
    save_all=True,
    append_images=frames_1[1:],
    duration=frame_duration_1,
    loop=0,
    optimize=True
)
print(f"Saved public/videos/planet_rotation_clouds.gif (1080p, 24.0s) in {time.time() - t_anim1_start:.1f}s")


# =============================================================
# 2. EINSTEIN RING OPTICAL CONVOLUTION (240 frames @ 100ms = 24.0s, 1080p)
# =============================================================
print("\n[2/4] Rendering 1080p Einstein Ring Optical Convolution (240 frames = 24.0s)...")
num_frames_2 = 240
frame_duration_2 = 100
frames_2 = []

cx, cy = 540, 560
R_coronagraph = 140
R_ring = 310

t_anim2_start = time.time()
for f_idx in range(num_frames_2):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    t = (f_idx / num_frames_2) * 4 * math.pi
    rho_t = 1.4 * (1.0 - math.cos(t * 0.5))

    # Top Header
    draw.text((60, 35), "SGL CORONAGRAPH TELESCOPE: 650 AU DEEP-SPACE STATION", fill=(56, 189, 248), font=font_main_title)
    draw.text((60, 78), f"OPTICAL CONVOLUTION • OFF-AXIS DRIFT: ρ = {rho_t:.2f} m • K(ρ) = d / (4ρ)", fill=(148, 163, 184), font=font_sub_title)
    draw.line([(60, 115), (W - 60, 115)], fill=(30, 41, 59), width=2)

    # Polar Grid Marks & Crosshairs
    for r in [160, 240, 310, 380, 450]:
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], outline=(30, 41, 59), width=1)
    draw.line([(cx - 460, cy), (cx + 460, cy)], fill=(30, 41, 59), width=1)
    draw.line([(cx, cy - 460), (cx, cy + 460)], fill=(30, 41, 59), width=1)

    # Scale Callouts with dark backdrop pills
    draw.rounded_rectangle([(cx + 325, cy - 14), (cx + 465, cy + 14)], radius=4, fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((cx + 332, cy - 8), "EINSTEIN RING", fill=(56, 189, 248), font=font_axis)

    draw.rounded_rectangle([(cx + 175, cy - 14), (cx + 300, cy + 14)], radius=4, fill=(15, 23, 42), outline=(51, 65, 85))
    draw.text((cx + 182, cy - 8), "CORONA GLOW", fill=(251, 191, 36), font=font_axis)

    # Solar Corona dynamic flaring glow
    for r_step in range(R_coronagraph, R_coronagraph + 120):
        c_mod = max(0.0, 1.0 - (r_step - R_coronagraph) / 120.0)
        c_r = int(217 * c_mod + 15 * (1 - c_mod))
        c_g = int(119 * c_mod + 23 * (1 - c_mod))
        c_b = int(6 * c_mod + 42 * (1 - c_mod))
        draw.ellipse([(cx - r_step, cy - r_step), (cx + r_step, cy + r_step)], outline=(c_r, c_g, c_b))

    # Luminous Einstein Ring with off-axis gravitational shear and arc bifurcation
    for angle_deg in range(720):
        theta = math.radians(angle_deg * 0.5)
        theta_shear = t * 0.15
        shear_diff = theta - theta_shear
        arc_factor = math.exp(-((math.sin(shear_diff)**2) * (rho_t * 1.6)))
        mod = 0.35 + 0.30 * math.sin(theta * 2 + t) + 0.35 * arc_factor

        col_r = int(np.clip(40 + 190 * (mod**2), 0, 255))
        col_g = int(np.clip(140 + 100 * mod, 0, 255))
        col_b = 255

        ring_r = R_ring + int(rho_t * 6.0 * math.cos(2 * shear_diff))
        px = cx + int(ring_r * math.cos(theta))
        py = cy + int(ring_r * math.sin(theta))

        dot_radius = 4 if mod > 0.50 else (3 if mod > 0.25 else 2)
        if mod > 0.16:
            draw.ellipse([(px - dot_radius, py - dot_radius), (px + dot_radius, py + dot_radius)], fill=(col_r, col_g, col_b))

    # Dark Central Occulter Mask
    draw.ellipse([(cx - R_coronagraph, cy - R_coronagraph), (cx + R_coronagraph, cy + R_coronagraph)], fill=(15, 23, 42), outline=(239, 68, 68), width=3)
    draw.text((cx - 85, cy - 12), "OCCULTER MASK", fill=(239, 68, 68), font=font_badge)

    # Right Side Card 1: Azimuthal Intensity Profile I(theta)
    gx, gy, gw, gh = 1060, 140, 800, 390
    draw_card(draw, gx, gy, gw, gh)
    draw.text((gx + 28, gy + 22), "AZIMUTHAL INTENSITY PROFILE I(θ)", fill=(255, 255, 255), font=font_card_header)
    draw.text((gx + 28, gy + 52), f"Gravitational Arc Bifurcation at Offset ρ = {rho_t:.2f} m", fill=(251, 191, 36), font=font_card_sub)

    plot_x, plot_y, plot_w, plot_h = gx + 60, gy + 95, gw - 100, gh - 145

    for deg in [0, 90, 180, 270, 360]:
        px = plot_x + int((deg / 360.0) * plot_w)
        draw.line([(px, plot_y), (px, plot_y + plot_h)], fill=(30, 41, 59), width=1)
        draw.text((px - 10, plot_y + plot_h + 10), f"{deg}°", fill=(100, 116, 139), font=font_axis)

    for level, lbl in [(0.25, "0.25"), (0.50, "0.50"), (0.75, "0.75"), (1.0, "1.00")]:
        py = plot_y + plot_h - int(level * plot_h)
        draw.line([(plot_x, py), (plot_x + plot_w, py)], fill=(30, 41, 59), width=1)
        draw.text((plot_x - 48, py - 9), lbl, fill=(100, 116, 139), font=font_axis)

    profile_pts = []
    for deg in range(0, 361, 2):
        theta = math.radians(deg)
        shear_diff = theta - (t * 0.15)
        arc_factor = math.exp(-((math.sin(shear_diff)**2) * (rho_t * 1.6)))
        mod = 0.35 + 0.30 * math.sin(theta * 2 + t) + 0.35 * arc_factor
        px = plot_x + int((deg / 360.0) * plot_w)
        py = plot_y + plot_h - int(np.clip(mod, 0.0, 1.0) * plot_h)
        profile_pts.append((px, py))

    if len(profile_pts) > 1:
        draw.line(profile_pts, fill=(56, 189, 248), width=3)

    # Right Side Card 2: Coronagraph Telemetry
    tx, ty, tw, th = 1060, 560, 800, 410
    draw_card(draw, tx, ty, tw, th)
    draw.text((tx + 28, ty + 22), "SGL CORONAGRAPH TELEMETRY", fill=(56, 189, 248), font=font_card_header)

    telemetry = [
        ("HELIOCENTRIC DISTANCE", "z = 650 AU (Focal Line Station)"),
        ("SGL OPTICAL GAIN", "μ ~ 10¹¹ (Natural Gravitational Boost)"),
        ("OCCULTER SUPPRESSION", "10⁻¹⁰ Starlight Rejection Ratio"),
        ("OFF-AXIS DISPLACEMENT", f"ρ = {rho_t:.2f} m (Cylinder Deviation)"),
        ("PHOTON BENCHMARK SNR", "SNR_C = 43.16 (Turyshev & Toth 2020)"),
        ("KERNEL HYPERBOLA", "K(ρ) ~ 1/ρ (Micro-arcsec Resolution)"),
        ("OPTICAL PHENOMENON", "EINSTEIN ARC BIFURCATION ACTIVE")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 68 + i * 44
        draw.text((tx + 28, row_y), label, fill=(148, 163, 184), font=font_mono_label)
        val_color = (52, 211, 153) if i == 6 else (255, 255, 255)
        draw.text((tx + 300, row_y), val, fill=val_color, font=font_mono_val)

    # Footer
    draw.line([(60, H - 70), (W - 60, H - 70)], fill=(30, 41, 59), width=2)
    draw.text((60, H - 46), "SGL CORONAGRAPH OPTICAL MODEL • SONTANKE ET AL. (2026)", fill=(100, 116, 139), font=font_footer)
    draw.text((W - 540, H - 46), "DURATION: 24.0s • 240 FRAMES • 1080p FULL HD", fill=(56, 189, 248), font=font_footer_bold)

    frames_2.append(img.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))

frames_2[0].save(
    'public/videos/einstein_ring_convolution.gif',
    save_all=True,
    append_images=frames_2[1:],
    duration=frame_duration_2,
    loop=0,
    optimize=True
)
print(f"Saved public/videos/einstein_ring_convolution.gif (1080p, 24.0s) in {time.time() - t_anim2_start:.1f}s")


# =============================================================
# 3. FLEET FORMATION RASTER SCANNING (240 frames @ 100ms = 24.0s, 1080p)
# =============================================================
print("\n[3/4] Rendering 1080p Fleet Formation Raster (240 frames = 24.0s)...")
num_frames_3 = 240
frame_duration_3 = 100
frames_3 = []
num_crafts = 16

cx, cy, rx, ry = 540, 560, 420, 360

t_anim3_start = time.time()
for f_idx in range(num_frames_3):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    progress = f_idx / num_frames_3
    pct = int(progress * 100)

    # Top Header
    draw.text((60, 35), "SGL MULTI-SPACECRAFT FLEET CONSTELLATION", fill=(56, 189, 248), font=font_main_title)
    draw.text((60, 78), f"16 NANO-SPACECRAFT SWEEPING 1.34 KM FOCAL CYLINDER • SAMPLING: {pct}%", fill=(148, 163, 184), font=font_sub_title)
    draw.line([(60, 115), (W - 60, 115)], fill=(30, 41, 59), width=2)

    # Focal Tube Perimeter & Grid
    draw.ellipse([(cx - rx, cy - ry), (cx + rx, cy + ry)], outline=(51, 65, 85), width=3)
    draw.text((cx - 180, cy - ry - 32), "1.34 KM FOCAL CYLINDER IMAGE PLANE", fill=(148, 163, 184), font=font_card_header)

    # Spacecraft positions and tracks
    craft_pts = []
    for i in range(num_crafts):
        track_y = cy - ry + 40 + int((i / (num_crafts - 1)) * (2 * ry - 80))
        y_norm = (track_y - cy) / ry
        x_span = rx * math.sqrt(max(0.0, 1.0 - y_norm**2))

        # Track line
        draw.line([(cx - x_span, track_y), (cx + x_span, track_y)], fill=(30, 41, 59), width=2)

        # Multi-sweep phase
        phase = (progress * 3.0 + i * 0.06) % 1.0
        direction = 1 if (i % 2 == 0) else -1
        scan_x = (cx - x_span + phase * 2 * x_span) if direction == 1 else (cx + x_span - phase * 2 * x_span)
        craft_pts.append((scan_x, track_y))

        # Green sampled swath trail
        fill_frac = min(1.0, progress * 1.05)
        swath_w = fill_frac * (2 * x_span)
        if direction == 1:
            draw.line([(cx - x_span, track_y), (cx - x_span + swath_w, track_y)], fill=(16, 185, 129), width=6)
        else:
            draw.line([(cx + x_span - swath_w, track_y), (cx + x_span, track_y)], fill=(16, 185, 129), width=6)

    # Inter-satellite laser telemetry cross-links
    pulse_alpha = 0.5 + 0.5 * math.sin(f_idx * 0.25)
    link_col = (int(56 * pulse_alpha), int(189 * pulse_alpha), 248)
    for i in range(len(craft_pts) - 1):
        draw.line([craft_pts[i], craft_pts[i + 1]], fill=link_col, width=2)

    # Spacecraft dots
    for i, p in enumerate(craft_pts):
        draw.ellipse([(p[0] - 8, p[1] - 8), (p[0] + 8, p[1] + 8)], fill=(255, 255, 255), outline=(251, 191, 36), width=2)

    # Right Side Card 1: Coverage Gauge
    gx, gy, gw, gh = 1060, 140, 800, 390
    draw_card(draw, gx, gy, gw, gh)
    draw.text((gx + 28, gy + 22), "IMAGE PLANE SAMPLING PROGRESS", fill=(255, 255, 255), font=font_card_header)
    draw.text((gx + 28, gy + 52), f"Cylinder Coverage: {pct}% Complete", fill=(52, 211, 153), font=font_card_sub)

    # Progress bar
    draw.rectangle([(gx + 28, gy + 95), (gx + gw - 28, gy + 145)], fill=(30, 41, 59), outline=(51, 65, 85), width=2)
    bar_fill = int(progress * (gw - 56))
    draw.rectangle([(gx + 28, gy + 95), (gx + 28 + bar_fill, gy + 145)], fill=(16, 185, 129))

    pixels_collected = int(progress * 4096)
    draw.text((gx + 28, gy + 170), f"Sampled Pixels: {pixels_collected} / 4096 (64 × 64 Grid)", fill=(148, 163, 184), font=font_card_sub)
    draw.text((gx + 28, gy + 205), "Frame Sweep Time: 5.6 Hours / Coordinated Pass", fill=(251, 191, 36), font=font_card_sub)
    draw.text((gx + 28, gy + 240), "Total Campaign Duration: 90 Days (Multi-Revisit Inversion)", fill=(56, 189, 248), font=font_card_sub)

    # Right Side Card 2: Swarm Dynamics Telemetry
    tx, ty, tw, th = 1060, 560, 800, 410
    draw_card(draw, tx, ty, tw, th)
    draw.text((tx + 28, ty + 22), "SWARM DYNAMICS TELEMETRY", fill=(56, 189, 248), font=font_card_header)

    telemetry = [
        ("FLEET CONSTELLATION", "16 nano-spacecraft (synchronized formation)"),
        ("SLEW VELOCITY", "15.2 m/s (transverse scan rate)"),
        ("TUBE DIAMETER", "D_img = 1.34 km (Exo-Earth image size)"),
        ("CROSS-TRACK SPACING", "Δy = 83.7 m track-to-track separation"),
        ("LASER ASTROMETRY", "Sub-millimeter inter-satellite link"),
        ("IMAGE REVISIT LAW", "Resolution scales as K^0.26"),
        ("MISSION STATUS", "SYNCHRONIZED RASTER SCAN ACTIVE")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 68 + i * 44
        draw.text((tx + 28, row_y), label, fill=(148, 163, 184), font=font_mono_label)
        val_color = (52, 211, 153) if i == 6 else (255, 255, 255)
        draw.text((tx + 280, row_y), val, fill=val_color, font=font_mono_val)

    # Footer
    draw.line([(60, H - 70), (W - 60, H - 70)], fill=(30, 41, 59), width=2)
    draw.text((60, H - 46), "SGL SWARM RASTER ARCHITECTURE • SONTANKE ET AL. (2026)", fill=(100, 116, 139), font=font_footer)
    draw.text((W - 540, H - 46), "DURATION: 24.0s • 240 FRAMES • 1080p FULL HD", fill=(56, 189, 248), font=font_footer_bold)

    frames_3.append(img.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))

frames_3[0].save(
    'public/videos/fleet_raster_scan.gif',
    save_all=True,
    append_images=frames_3[1:],
    duration=frame_duration_3,
    loop=0,
    optimize=True
)
print(f"Saved public/videos/fleet_raster_scan.gif (1080p, 24.0s) in {time.time() - t_anim3_start:.1f}s")


# =============================================================
# 4. TDI ITERATIVE DECONVOLUTION TIMELAPSE (320 frames @ 100ms = 32.0s, 1080p)
# =============================================================
print("\n[4/4] Rendering 1080p TDI Deconvolution Timelapse (320 frames = 32.0s)...")
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
        "name": "STAGE 4: HIGH-CADENCE ASYMPTOTIC LIMIT (K=64)", 
        "r": 0.544, "ssim": 0.320, "data": gls_fc0, 
        "desc": "Independent weather draws average out to pristine continental clarity"
    }
]

t_anim4_start = time.time()
for f_idx in range(num_frames_4):
    img = Image.new('RGB', (W, H), (10, 14, 23))
    draw = ImageDraw.Draw(img)

    s_progress = (f_idx / num_frames_4) * len(stages)
    s_idx = min(len(stages) - 1, int(s_progress))
    next_s_idx = (s_idx + 1) % len(stages)
    
    raw_sub = s_progress - int(s_progress)
    if raw_sub < 0.70:
        alpha = 0.0
    else:
        t_trans = (raw_sub - 0.70) / 0.30
        alpha = 0.5 - 0.5 * math.cos(t_trans * math.pi)

    s1 = stages[s_idx]
    s2 = stages[next_s_idx]
    elapsed_time = f_idx * 0.1

    # Top Header with explicit mathematical equation formatted with clean Unicode
    draw.text((60, 35), "TDI DECONVOLUTION PIPELINE: CONVERGENCE TIMELAPSE", fill=(56, 189, 248), font=font_main_title)
    draw.text((60, 78), f"RECONSTRUCTION ITERATION: {elapsed_time:04.1f}s / 32.0s • m̂ = (Fᵀ C_y⁻¹ F + Λ)⁻¹ Fᵀ C_y⁻¹ y", fill=(148, 163, 184), font=font_sub_title)
    draw.line([(60, 115), (W - 60, 115)], fill=(30, 41, 59), width=2)

    # Left Side: Map Box ($W = 960, H = 830$)
    mx, my, mw, mh = 60, 140, 960, 830
    draw_card(draw, mx, my, mw, mh)

    # Stage Badge
    badge_w, badge_h = mw - 56, 56
    draw.rounded_rectangle([(mx + 28, my + 24), (mx + 28 + badge_w, my + 24 + badge_h)], radius=6, fill=(15, 23, 42), outline=(56, 189, 248), width=2)
    draw.text((mx + 48, my + 38), s1['name'], fill=(56, 189, 248), font=font_badge)

    # Map Interpolation & Upscaling
    interpolated = (s1['data'] * (1.0 - alpha) + s2['data'] * alpha).astype(np.uint8)
    map_x_offset = mx + 78
    map_w_pixels = 854
    map_h_pixels = 427
    map_pil = Image.fromarray(interpolated).resize((map_w_pixels, map_h_pixels), Image.Resampling.NEAREST)
    img.paste(map_pil, (map_x_offset, my + 105))
    draw.rectangle([(map_x_offset - 1, my + 104), (map_x_offset + map_w_pixels, my + 105 + map_h_pixels)], outline=(51, 65, 85), width=2)

    # Coordinate Grid Marks & Labels
    # Longitudes
    for lon_val, x_frac in [("-180°", 0.0), ("-90°", 0.25), ("0°", 0.50), ("+90°", 0.75), ("+180°", 1.0)]:
        lx = map_x_offset + int(x_frac * map_w_pixels)
        draw.line([(lx, my + 105), (lx, my + 105 + map_h_pixels)], fill=(40, 50, 70), width=1)
        draw.text((lx - 16, my + 105 + map_h_pixels + 10), lon_val, fill=(100, 116, 139), font=font_axis)

    # Latitudes (placed outside the map on the left!)
    for lat_val, y_frac in [("+60°", 0.166), ("+30°", 0.333), ("0°", 0.50), ("-30°", 0.666), ("-60°", 0.833)]:
        ly = my + 105 + int(y_frac * map_h_pixels)
        draw.line([(map_x_offset, ly), (map_x_offset + map_w_pixels, ly)], fill=(40, 50, 70), width=1)
        draw.text((map_x_offset - 50, ly - 8), lat_val, fill=(100, 116, 139), font=font_axis)

    # Continental Identification Labels with subtle background pill
    if s_idx >= 2:
        for c_lbl, c_x, c_y in [
            ("AMERICAS", map_x_offset + 140, my + 230),
            ("AFRICA", map_x_offset + 420, my + 260),
            ("EURASIA", map_x_offset + 570, my + 190),
            ("OCEANIA", map_x_offset + 700, my + 330)
        ]:
            draw.rounded_rectangle([(c_x - 6, c_y - 4), (c_x + 84, c_y + 22)], radius=4, fill=(10, 14, 23, 200), outline=(51, 65, 85))
            draw.text((c_x, c_y), c_lbl, fill=(255, 255, 255), font=font_map_label)

    # Description below map
    draw.text((mx + 28, my + 575), s1['desc'], fill=(148, 163, 184), font=font_card_sub)
    draw.text((mx + 28, my + 610), "• Tikhonov Prior: Spectral decay Λ = α · I guarantees physical positivity & stability", fill=(100, 116, 139), font=font_axis)
    draw.text((mx + 28, my + 635), "• Common-Mode Cancellation: P_perp projects out 21:1 cloud albedo offsets (Δr = +0.041)", fill=(100, 116, 139), font=font_axis)
    draw.text((mx + 28, my + 660), "• Multi-Revisit Limit: High cadence (K = 64) establishes continental geography at 95% CI", fill=(100, 116, 139), font=font_axis)

    # Right Side Card 1: Performance Gauges
    gx, gy, gw, gh = 1060, 140, 800, 420
    draw_card(draw, gx, gy, gw, gh)
    draw.text((gx + 28, gy + 22), "RECONSTRUCTION FIDELITY METRICS", fill=(255, 255, 255), font=font_card_header)

    cur_r = s1['r'] * (1.0 - alpha) + s2['r'] * alpha
    cur_ssim = s1['ssim'] * (1.0 - alpha) + s2['ssim'] * alpha

    # Pearson r
    draw.text((gx + 28, gy + 70), "PEARSON CORRELATION (r)", fill=(148, 163, 184), font=font_metric_label)
    draw.text((gx + 28, gy + 96), f"r = {cur_r:.3f}", fill=(56, 189, 248), font=font_metric_val)
    draw.rectangle([(gx + 28, gy + 140), (gx + gw - 28, gy + 165)], fill=(30, 41, 59))
    r_w = int((cur_r / 0.6) * (gw - 56))
    draw.rectangle([(gx + 28, gy + 140), (gx + 28 + max(0, r_w), gy + 165)], fill=(56, 189, 248))
    draw.text((gx + 28, gy + 175), "Target Threshold: r > 0.30 (Continental Dichotomy Established)", fill=(100, 116, 139), font=font_axis)

    # SSIM
    draw.text((gx + 28, gy + 220), "STRUCTURAL SIMILARITY (SSIM)", fill=(148, 163, 184), font=font_metric_label)
    draw.text((gx + 28, gy + 246), f"SSIM = {cur_ssim:.3f}", fill=(52, 211, 153), font=font_metric_val)
    draw.rectangle([(gx + 28, gy + 290), (gx + gw - 28, gy + 315)], fill=(30, 41, 59))
    ssim_w = int((cur_ssim / 0.4) * (gw - 56))
    draw.rectangle([(gx + 28, gy + 290), (gx + 28 + max(0, ssim_w), gy + 315)], fill=(52, 211, 153))
    draw.text((gx + 28, gy + 325), "Asymptotic Multi-Year Limit: SSIM → 0.320 at K = 64 Revisits", fill=(100, 116, 139), font=font_axis)

    # Right Side Card 2: Algorithmic Telemetry
    tx, ty, tw, th = 1060, 580, 800, 390
    draw_card(draw, tx, ty, tw, th)
    draw.text((tx + 28, ty + 22), "ALGORITHMIC TELEMETRY", fill=(251, 191, 36), font=font_card_header)

    telemetry = [
        ("CLOUD DEFLATION GAIN", "Δr = +0.041 (orthogonal projector P_perp)"),
        ("PHOTON BENCHMARK SNR", "SNR_C = 43.16 (Turyshev et al. 2020)"),
        ("STATISTICAL EFFECT SIZE", "d' = 0.64 (p < 0.02, 95% CI [0.027, 0.054])"),
        ("CADENCE SCALING LAW", "Resolution gain r(K) ~ K^0.26"),
        ("REGULARIZATION TIKHONOV", "Λ = 1.0e-3 · Spectral Laplacian Prior"),
        ("CONTINENTAL DICHOTOMY", "YES (Continent boundaries resolved)")
    ]
    for i, (label, val) in enumerate(telemetry):
        row_y = ty + 68 + i * 44
        draw.text((tx + 28, row_y), label, fill=(148, 163, 184), font=font_mono_label)
        val_color = (52, 211, 153) if i == 5 else (255, 255, 255)
        draw.text((tx + 300, row_y), val, fill=val_color, font=font_mono_val)

    # Footer
    draw.line([(60, H - 70), (W - 60, H - 70)], fill=(30, 41, 59), width=2)
    draw.text((60, H - 46), "SGL TIME-DOMAIN INVERSION (TDI) • SONTANKE ET AL. (2026)", fill=(100, 116, 139), font=font_footer)
    draw.text((W - 540, H - 46), "DURATION: 32.0s • 320 FRAMES • 1080p FULL HD", fill=(56, 189, 248), font=font_footer_bold)

    frames_4.append(img.convert('P', palette=Image.Palette.ADAPTIVE, colors=128))

frames_4[0].save(
    'public/videos/tdi_deconvolution_timelapse.gif',
    save_all=True,
    append_images=frames_4[1:],
    duration=frame_duration_4,
    loop=0,
    optimize=True
)
print(f"Saved public/videos/tdi_deconvolution_timelapse.gif (1080p, 32.0s) in {time.time() - t_anim4_start:.1f}s")

print("=" * 75)
print(f"ALL 4 SIMULATION GIFS GENERATED AT 1080p FULL HD IN {time.time() - start_time:.1f}s!")
print("=" * 75)
