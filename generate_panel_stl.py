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
import trimesh
import os

# ============================================
# DIMENSIONS (all in mm)
# ============================================

PANEL_W = 250.0       # fits Bambu A1 (256mm bed)
PANEL_H = 170.0
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

# Anti-rotation tab slot — TIGHTENED for snug 3D-print fit
# P160 tab is nominally 3.0 x 1.5mm; oversized slightly for print tolerance
SLOT_W = 3.2          # was 3.5 — tighter on tab width
SLOT_H = 1.8          # was 2.0 — tighter on tab depth
SLOT_R = 0.15         # was 0.3 — sharper corners grip better
SLOT_OFFSET_Y = 7.8   # mm above shaft center

# M3 through-holes for back-mounted boards (3.2mm clearance)
M3_D = 3.2

# ── Arduino NG ──────────────────────────────────────────
# Board: ~68.6 x 53.3mm (2.7" x 2.1")
# Classic pre-R3 mounting holes (from board lower-left origin):
#   (14.0, 2.54), (15.24, 50.8), (66.04, 7.62), (66.04, 35.56)
# Placed in lower-left zone of panel, below pots
ARDUINO_ORIGIN_X = 28.0    # board lower-left X on panel
ARDUINO_ORIGIN_Y = 107.0   # board lower-left Y on panel
ARDUINO_HOLES = [           # relative to board origin
    (14.0,  2.54),          # near USB/reset corner
    (15.24, 50.8),          # opposite USB corner
    (66.04,  7.62),         # near power jack
    (66.04, 35.56),         # near analog pins
]

# ── Adafruit 1/4-size Perma-Proto (product 1608) ────────
# Board: 43 x 50.8mm (1.7" x 2.0")
# 2 mounting holes, 35.56mm (1.4") apart along the LONG axis,
#   centered on board width (x = 21.5mm from left edge)
# Available zone: y=120 (30mm clear of pot bodies) to y=160 (before edge mounts)
#   → 50mm window for a 50.8mm board — tight but fits
# Board origin placed so top hole clears pot wiring,
#   bottom hole stays well inside panel
PROTO_ORIGIN_X = 155.0     # board lower-left X on panel
PROTO_ORIGIN_Y = 110.0     # board lower-left Y on panel
PROTO_BOARD_W = 43.0       # 1.7"
PROTO_BOARD_H = 50.8       # 2.0"
PROTO_HOLES = [             # relative to board origin — 2 holes along long axis
    (43.0 / 2,  (50.8 - 35.56) / 2),          # upper hole (y≈7.6, → panel y≈117.6)
    (43.0 / 2,  (50.8 + 35.56) / 2),          # lower hole (y≈43.2, → panel y≈153.2)
]
# Result: holes at panel (176.5, 117.6) and (176.5, 153.2)
#   upper hole: 27.6mm from pots — clears P160 body + wiring
#   lower hole: 16.8mm from panel edge — fully inside
#   board top edge at y=160.8 — just under edge mount at y=162

# ── Weight-relief cutouts ───────────────────────────────
# Big windows in dead zones to cut print time
# 5mm corner radius for strength at window corners
RELIEF_R = 5.0
RELIEF_WINDOWS = [
    # (x, y, w, h) — positioned to avoid all holes with margin
    # Upper left:  between top-edge mounts and pot zone
    (20,  20,   95,  52),
    # Upper right: mirror of upper left (gap for mid-mount at x=125)
    (135, 20,   97,  52),
    # Lower center: gap between Arduino and Proto board zones
    (102, 110,  45,  45),
    # Lower far-right: right of Proto board zone
    (202, 110,  30,  45),
    # Arduino viewing window: see the board from the front!
    (50,  122,  30,  25),
]

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
