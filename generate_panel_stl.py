#!/usr/bin/env python3
"""
Generate a 3D-printable STL of the control surface panel.
Matches panel-control-surface.svg layout (resized for Bambu A1).

Usage:
    python3 generate_panel_stl.py

Output:
    panel-control-surface.stl (in the same directory)
"""

import numpy as np
from shapely.geometry import Polygon, MultiPolygon, box
from shapely.ops import unary_union
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
import trimesh
import os

# ============================================
# DIMENSIONS (all in mm)
# ============================================

PANEL_W = 250.0       # fits Bambu A1 (256mm bed)
PANEL_H = 145.0       # was 170 — trimmed ~1" (25mm)
PANEL_T = 4.0         # thinner — 4mm for M3 through-hardware
CORNER_R = 5.0

# Panel mounting holes (M4 = 4.2mm clearance)
M4_D = 4.2
MOUNT_INSET = 8.0

# P160 potentiometer
POT_HOLE_D = 7.5
POT_Y = 90.0
POT_X_START = 50.0    # centered: (250 - 3*50) / 2
POT_SPACING = 50.0    # 26mm knob-to-knob clearance
POT_COUNT = 4

# Anti-rotation tab slot — VERY TIGHT for zero-play 3D-print fit
# P160 tab is nominally 3.0 x 1.5mm; near-nominal for interference fit
SLOT_W = 3.05         # was 3.2 — near-nominal, relies on print shrink for grip
SLOT_H = 1.6          # was 1.8 — just 0.1mm over nominal, very snug
SLOT_R = 0.10         # was 0.15 — nearly square corners lock the tab
SLOT_OFFSET_Y = 7.8   # mm above shaft center

# M3 through-holes for back-mounted boards (3.2mm clearance)
M3_D = 3.2

# ── Arduino NG (rotated 90° CW — USB faces top edge) ───
# Board: ~68.6 x 53.3mm (2.7" x 2.1")
# Rotated so USB connector edge points toward Y=0 (panel top).
# Rotation maps board (bx, by) → panel-relative (by, bx),
# so the rotated footprint is 53.3mm wide × 68.6mm tall.
# Centered horizontally in the top zone, above the pots.
# Rotated footprint: 53.3mm wide × 68.6mm tall → bottom edge at Y=73.6
# Pot hardware starts at Y≈82 → 8.4mm clearance
ARDUINO_ORIGIN_X = 98.0    # centered: (250 - 53.3) / 2 ≈ 98
ARDUINO_ORIGIN_Y = 5.0     # tight to top edge for max pot clearance
ARDUINO_HOLES = [           # relative to board origin, AFTER rotation
    ( 2.54, 14.0),          # near USB/reset corner (top-left)
    (50.8,  15.24),         # opposite USB corner (top-right)
    ( 7.62, 66.04),         # near power jack (bottom-left)
    (35.56, 66.04),         # near analog pins (bottom-right)
]

# ── Adafruit 1/4-size Perma-Proto (product 1608) ────────
# Board: 43 x 50.8mm (1.7" x 2.0")
# 2 mounting holes, 35.56mm (1.4") apart along the LONG axis,
#   centered on board width (x = 21.5mm from left edge)
# Placed in top zone, right of Arduino (Arduino occupies x=98-152)
# Board spans x=175-218, y=8-59 — clears Arduino and top mount holes
PROTO_ORIGIN_X = 175.0     # board lower-left X on panel
PROTO_ORIGIN_Y = 8.0       # top zone, same side as Arduino
PROTO_BOARD_W = 43.0       # 1.7"
PROTO_BOARD_H = 50.8       # 2.0"
PROTO_HOLES = [             # relative to board origin — 2 holes along long axis
    (43.0 / 2,  (50.8 - 35.56) / 2),          # upper hole (y≈7.6, → panel y≈117.6)
    (43.0 / 2,  (50.8 + 35.56) / 2),          # lower hole (y≈43.2, → panel y≈153.2)
]
# Result: holes at panel (196.5, 15.6) and (196.5, 51.2)
#   both holes in top zone, well clear of pots at y=90
#   board bottom edge at y=58.8 — 31mm above pot zone

# ── Weight-relief cutouts ───────────────────────────────
# Big windows in dead zones to cut print time
# 5mm corner radius for strength at window corners
RELIEF_R = 5.0
RELIEF_WINDOWS = [
    # (x, y, w, h) — positioned to avoid all holes with margin
    # Arduino occupies x≈98-152, y=5-74; Proto occupies x=175-218, y=8-59
    # Top-left: left of Arduino (small)
    (25,  22,   40,  30),
    # Arduino viewing window: between the 4 Arduino mount holes (keep full size)
    (110, 26,   20,  38),
    # Lower-left: below pots (small)
    (25,  103,  40,  20),
    # Lower-center: below pots (small)
    (108, 103,  35,  20),
    # Lower-right: freed up by Proto moving to top (small)
    (160, 103,  40,  20),
]

# ── Embossed title text ────────────────────────────────
TEXT_STRING = "SIGINT::OPTICS"
TEXT_FONT_SIZE = 8.0      # mm cap height
TEXT_EMBOSS_H = 0.8       # mm raised above panel surface
# Centered between middle (x=125) and right (x=242) mount holes,
# on their shared centerline (y=137)
TEXT_CENTER_X = (125.0 + 242.0) / 2   # 183.5
TEXT_CENTER_Y = PANEL_H - MOUNT_INSET  # 137.0

# Circle resolution
CIRCLE_SEGMENTS = 64


# ============================================
# GEOMETRY HELPERS
# ============================================

def rounded_rect(x, y, w, h, r, segments=16):
    """Create a rounded rectangle polygon."""
    if r <= 0:
        return box(x, y, x + w, y + h)
    r = min(r, w / 2, h / 2)
    points = []
    for corner, (cx, cy, start) in enumerate([
        (x + r,     y + r,     np.pi),
        (x + w - r, y + r,     3*np.pi/2),
        (x + w - r, y + h - r, 0),
        (x + r,     y + h - r, np.pi/2),
    ]):
        for i in range(segments + 1):
            angle = start + (np.pi / 2) * (i / segments)
            points.append((cx + r * np.cos(angle), cy + r * np.sin(angle)))
    return Polygon(points)


def circle(cx, cy, d, segments=CIRCLE_SEGMENTS):
    """Create a circle polygon."""
    r = d / 2
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    return Polygon([(cx + r * np.cos(a), cy + r * np.sin(a)) for a in angles])


def text_to_polygons(text, x, y, size, font_family='monospace'):
    """Convert a text string to positioned Shapely polygons.

    Uses matplotlib's TextPath for vector outlines, then classifies
    contours as outer boundaries vs. holes (e.g. inside 'O', 'P').
    Returns a single (Multi)Polygon translated to (x, y).
    """
    fp = FontProperties(family=font_family, weight='bold')
    tp = TextPath((0, 0), text, size=size, prop=fp)
    raw = tp.to_polygons()

    # Build valid shapely polygons from each contour
    contours = []
    for pts in raw:
        if len(pts) >= 3:
            p = Polygon(pts)
            if not p.is_valid:
                p = p.buffer(0)
            if not p.is_empty:
                contours.append(p)

    # Sort largest-first; large contours are letter outlines,
    # smaller ones nested inside are holes (counter-punches)
    contours.sort(key=lambda p: p.area, reverse=True)
    outers, holes = [], []
    for c in contours:
        is_hole = any(o.contains(c) for o in outers)
        (holes if is_hole else outers).append(c)

    result = unary_union(outers)
    if holes:
        result = result.difference(unary_union(holes))

    from shapely.affinity import translate, scale
    # Rotate 180° — panel Y=0 is the physical top, so text needs full rotation
    result = scale(result, xfact=-1, yfact=-1, origin=(0, 0))
    # After 180° rotation the text bbox is in negative space; shift it so
    # its lower-left corner lands at (x, y)
    bx = result.bounds  # (minx, miny, maxx, maxy)
    return translate(result, xoff=x - bx[0], yoff=y - bx[1])


def polygon_to_mesh(polygon, height):
    """Extrude a 2D Shapely polygon into a 3D trimesh."""
    if isinstance(polygon, MultiPolygon):
        meshes = [polygon_to_mesh(p, height) for p in polygon.geoms]
        return trimesh.util.concatenate(meshes)
    return trimesh.creation.extrude_polygon(polygon, height)


# ============================================
# MAIN
# ============================================

def main():
    print("=" * 56)
    print("CONTROL SURFACE PANEL — STL Generator")
    print("=" * 56)
    print(f"  Panel:     {PANEL_W} x {PANEL_H} x {PANEL_T} mm")
    print(f"  Bed fit:   {'YES' if PANEL_W <= 256 and PANEL_H <= 256 else 'NO'} (Bambu A1: 256x256)")
    print()

    # --- Panel outline ---
    panel = rounded_rect(0, 0, PANEL_W, PANEL_H, CORNER_R)

    # --- Collect all through-holes ---
    holes = []

    # ── Panel mounting (M4) ──
    print("  M4 panel mounting holes:")
    m4_positions = [
        (MOUNT_INSET, MOUNT_INSET),                     # BL corner
        (PANEL_W - MOUNT_INSET, MOUNT_INSET),           # BR corner
        (MOUNT_INSET, PANEL_H - MOUNT_INSET),           # TL corner
        (PANEL_W - MOUNT_INSET, PANEL_H - MOUNT_INSET), # TR corner
        (PANEL_W / 2, MOUNT_INSET),                     # bottom mid
        (PANEL_W / 2, PANEL_H - MOUNT_INSET),           # top mid
    ]
    for cx, cy in m4_positions:
        holes.append(circle(cx, cy, M4_D))
        print(f"    ({cx:.0f}, {cy:.0f})  d={M4_D}")

    # ── Pot shaft holes ──
    print(f"\n  P160 pot shaft holes (d={POT_HOLE_D}):")
    for i in range(POT_COUNT):
        px = POT_X_START + i * POT_SPACING
        holes.append(circle(px, POT_Y, POT_HOLE_D))
        print(f"    Pot {i+1}: ({px:.1f}, {POT_Y})")

    # ── Anti-rotation slots (tightened) ──
    print(f"\n  Anti-rot slots ({SLOT_W} x {SLOT_H} mm — tightened):")
    for i in range(POT_COUNT):
        px = POT_X_START + i * POT_SPACING
        sx = px - SLOT_W / 2
        sy = POT_Y - SLOT_OFFSET_Y - SLOT_H / 2
        slot = rounded_rect(sx, sy, SLOT_W, SLOT_H, SLOT_R, segments=8)
        holes.append(slot)
        print(f"    Pot {i+1}: slot at ({sx:.2f}, {sy:.2f})")

    # ── Arduino NG mounting (M3) ──
    print(f"\n  Arduino NG mounting holes (M3, d={M3_D}):")
    print(f"    Board origin on panel: ({ARDUINO_ORIGIN_X}, {ARDUINO_ORIGIN_Y})")
    for j, (rx, ry) in enumerate(ARDUINO_HOLES):
        ax = ARDUINO_ORIGIN_X + rx
        ay = ARDUINO_ORIGIN_Y + ry
        holes.append(circle(ax, ay, M3_D))
        print(f"    Hole {j+1}: ({ax:.1f}, {ay:.1f})  [board-relative: ({rx}, {ry})]")

    # ── Adafruit 1/4 Proto mounting (M3) — 2 holes, diagonal ──
    print(f"\n  Adafruit 1/4 Proto mounting holes (M3, d={M3_D}):")
    print(f"    Board origin on panel: ({PROTO_ORIGIN_X}, {PROTO_ORIGIN_Y})")
    for j, (rx, ry) in enumerate(PROTO_HOLES):
        px_pos = PROTO_ORIGIN_X + rx
        py_pos = PROTO_ORIGIN_Y + ry
        holes.append(circle(px_pos, py_pos, M3_D))
        print(f"    Hole {j+1}: ({px_pos:.1f}, {py_pos:.1f})  [board-relative: ({rx}, {ry})]")

    # ── Weight-relief cutout windows ──
    print(f"\n  Relief windows (print speed optimization):")
    relief_cuts = []
    for i, (rx, ry, rw, rh) in enumerate(RELIEF_WINDOWS):
        window = rounded_rect(rx, ry, rw, rh, RELIEF_R)
        relief_cuts.append(window)
        print(f"    Window {i+1}: ({rx}, {ry}) {rw}x{rh} mm  = {rw*rh:.0f} mm^2 removed")
    total_relief = sum(w.area for w in relief_cuts)
    print(f"    Total material removed: {total_relief:.0f} mm^2 ({total_relief/panel.area*100:.0f}%)")

    # --- Boolean subtract all holes + relief windows ---
    all_cuts = unary_union(holes + relief_cuts)
    panel_2d = panel.difference(all_cuts)

    total_holes = len(holes)
    print(f"\n  Total holes: {total_holes}")
    print(f"  Panel area: {panel_2d.area:.1f} mm^2")

    # --- Extrude to 3D ---
    print("\n  Extruding to 3D...")
    mesh = polygon_to_mesh(panel_2d, PANEL_T)

    # --- Embossed title text ---
    print(f"\n  Embossed text: \"{TEXT_STRING}\"")
    # First pass at origin to measure, then re-center on target point
    text_raw = text_to_polygons(TEXT_STRING, 0, 0, TEXT_FONT_SIZE)
    tb = text_raw.bounds  # (minx, miny, maxx, maxy)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    text_x = TEXT_CENTER_X - tw / 2
    text_y = TEXT_CENTER_Y - th / 2
    text_poly = text_to_polygons(TEXT_STRING, text_x, text_y,
                                 TEXT_FONT_SIZE)
    if not text_poly.is_empty:
        text_mesh = polygon_to_mesh(text_poly, TEXT_EMBOSS_H)
        # Shift up to sit on top of the panel surface
        text_mesh.apply_translation([0, 0, PANEL_T])
        mesh = trimesh.util.concatenate([mesh, text_mesh])
        bx = text_poly.bounds  # (minx, miny, maxx, maxy)
        print(f"    Position: ({bx[0]:.1f}, {bx[1]:.1f}) to ({bx[2]:.1f}, {bx[3]:.1f})")
        print(f"    Emboss height: {TEXT_EMBOSS_H} mm above panel")
    else:
        print("    WARNING: text polygon is empty — skipping")

    print(f"  Mesh: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")
    print(f"  Bounds: X=[{mesh.bounds[0][0]:.1f}, {mesh.bounds[1][0]:.1f}]"
          f"  Y=[{mesh.bounds[0][1]:.1f}, {mesh.bounds[1][1]:.1f}]"
          f"  Z=[{mesh.bounds[0][2]:.1f}, {mesh.bounds[1][2]:.1f}]")
    print(f"  Watertight: {mesh.is_watertight}")

    if not mesh.is_watertight:
        print("  Fixing mesh...")
        mesh.fill_holes()
        mesh.fix_normals()
        print(f"  Watertight after fix: {mesh.is_watertight}")

    # --- Export ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    stl_path = os.path.join(script_dir, "panel-control-surface.stl")
    mesh.export(stl_path, file_type="stl")

    file_size = os.path.getsize(stl_path)
    print(f"\n  Exported: {stl_path}")
    print(f"  File size: {file_size / 1024:.1f} KB")

    print(f"\n{'=' * 56}")
    print("PRINT SETTINGS")
    print(f"{'=' * 56}")
    print("  Layer height: 0.2mm")
    print("  Walls: 2-3")
    print("  Infill: 15% (doesn't need to be solid)")
    print("  Material: PLA or PETG")
    print("  Supports: none (flat panel)")
    print(f"{'=' * 56}")


if __name__ == "__main__":
    main()
