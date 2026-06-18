#!/usr/bin/env python3
"""
Generate 3D-printable STL files for the pedestal mount.
Angled two-piece design for gallery presentation of the
SIGINT::OPTICS control panel (250x170mm).

Usage:
    python3 generate_pedestal_mount.py

Output:
    pedestal-mount-left.stl   (print 1x)
    pedestal-mount-right.stl  (print 1x)

Dependencies:
    pip install numpy shapely trimesh
    pip install manifold3d   (optional, faster booleans)
"""

import numpy as np
from shapely.geometry import Polygon
import trimesh
import os
import sys


# ============================================
# PANEL REFERENCE DIMENSIONS
# (must match generate_panel_stl.py)
# ============================================

PANEL_W     = 250.0     # mm — panel width (Bambu A1 fit)
PANEL_H     = 170.0     # mm — panel height
PANEL_T     = 4.0       # mm — panel thickness
MOUNT_INSET = 8.0       # mm — panel mounting hole inset from edges

# Panel M4 mounting holes (from generate_panel_stl.py):
#   (8,8), (242,8), (8,162), (242,162), (125,8), (125,162)


# ============================================
# MOUNT DESIGN PARAMETERS
# ============================================

TILT = 22.0              # degrees — presentation angle from horizontal

# Structure
BASE_T   = 6.0           # mm — base plate thickness
WALL     = 4.0           # mm — back wall thickness
LIP_T    = 8.0           # mm — front lip depth (Y direction)
LIP_H    = 14.0          # mm — front lip height above panel surface
BACK_EXT = 6.0           # mm — back wall extension above panel surface

# Panel attachment — M4 heat-set inserts
INSERT_D     = 5.2       # mm — pilot hole diameter
INSERT_DEPTH = 6.0       # mm — insert depth into mount body

# Pedestal screws — 1/4-20 flat-head or M6
PED_D       = 6.5        # mm — clearance hole diameter
PED_CBORE_D = 12.0       # mm — counterbore diameter
PED_CBORE_T = 3.5        # mm — counterbore depth

# Cable management
CABLE_W = 35.0           # mm — cable slot width in back wall
CABLE_H = 10.0           # mm — cable slot height

# Resolution
CIRCLE_SEG = 48


# ============================================
# COMPUTED DIMENSIONS
# ============================================

TILT_RAD   = np.radians(TILT)
HALF_W     = PANEL_W / 2.0                        # 125mm per half
DEPTH_PROJ = PANEL_H * np.cos(TILT_RAD)           # ~157.6mm
RISE       = PANEL_H * np.sin(TILT_RAD)           # ~63.7mm
MOUNT_D    = LIP_T + DEPTH_PROJ + WALL            # ~169.6mm total depth
MOUNT_H    = BASE_T + RISE + BACK_EXT             # ~75.7mm max height


# ============================================
# HOLE POSITIONS
# ============================================

# Left half covers panel X = 0..125
# Corner holes at panel (8,8) and (8,162) fall inside
LEFT_PANEL_HOLES = [
    (MOUNT_INSET, MOUNT_INSET),                # panel (8, 8)
    (MOUNT_INSET, PANEL_H - MOUNT_INSET),      # panel (8, 162)
]

# Pedestal screw positions on left half (mount X, Y)
LEFT_PED_HOLES = [
    (25.0,          25.0),              # front-left
    (25.0,          MOUNT_D - 20.0),    # back-left
    (HALF_W - 20,   MOUNT_D / 2.0),    # center-right (near seam)
]


# ============================================
# GEOMETRY
# ============================================

def create_mount_profile():
    """
    Side cross-section of the mount as a 2D polygon.
    Coordinates: X = depth (front to back), Y = height.

    Profile shape (front on left):

        p7___p6
        |    |
        |    p5___________p4
        |   /              |
        |  /  panel angle  | p3
        | /                |
        |/                 p2
        p0_________________p1
    """
    return Polygon([
        (0,                   0),                          # p0: front-bottom
        (MOUNT_D,             0),                          # p1: back-bottom
        (MOUNT_D,             MOUNT_H),                    # p2: back-top outer
        (LIP_T + DEPTH_PROJ,  BASE_T + RISE + BACK_EXT),  # p3: back-top inner
        (LIP_T + DEPTH_PROJ,  BASE_T + RISE),             # p4: panel surface back
        (LIP_T,               BASE_T),                     # p5: panel surface front
        (LIP_T,               BASE_T + LIP_H),            # p6: lip inner top
        (0,                   BASE_T + LIP_H),            # p7: lip outer top
    ])


def extrude_and_orient(profile, width):
    """
    Extrude the side profile into a 3D body and reorient.

    extrude_polygon gives: X=depth, Y=height, Z=width
    We want:               X=width, Y=depth,  Z=height
    """
    mesh = trimesh.creation.extrude_polygon(profile, width)

    # Cyclic permutation: (X,Y,Z) -> (Z,X,Y)
    perm = np.eye(4)
    perm[:3, :3] = np.array([
        [0, 0, 1],   # new X = old Z (width)
        [1, 0, 0],   # new Y = old X (depth)
        [0, 1, 0],   # new Z = old Y (height)
    ])
    mesh.apply_transform(perm)
    return mesh


def surface_point(px, py):
    """Convert panel coordinates to mount surface coordinates."""
    return (
        px,
        LIP_T + py * np.cos(TILT_RAD),
        BASE_T + py * np.sin(TILT_RAD),
    )


def make_insert_hole(px, py):
    """Cylinder for a heat-set insert hole, perpendicular to the angled surface."""
    mx, my, mz = surface_point(px, py)
    total_h = INSERT_DEPTH + PANEL_T + 15

    cyl = trimesh.creation.cylinder(
        radius=INSERT_D / 2, height=total_h, sections=CIRCLE_SEG
    )

    # Shift so surface level is at Z=0, hole goes INSERT_DEPTH below
    cyl.apply_translation([0, 0, total_h / 2 - INSERT_DEPTH])

    # Rotate to align with surface normal: (0, -sin(tilt), cos(tilt))
    # rotate(-tilt) around X maps Z-axis to that direction
    rot = trimesh.transformations.rotation_matrix(-TILT_RAD, [1, 0, 0])
    cyl.apply_transform(rot)

    # Translate to surface position
    cyl.apply_translation([mx, my, mz])
    return cyl


def make_ped_hole(x, y):
    """Vertical pedestal screw hole through the base plate.
    Single clearance hole — countersink/counterbore after printing if needed."""
    cyl = trimesh.creation.cylinder(
        radius=PED_D / 2, height=BASE_T + 4, sections=CIRCLE_SEG
    )
    cyl.apply_translation([x, y, BASE_T / 2])
    return cyl


def make_cable_slot(x_center):
    """Cable pass-through slot in the back wall."""
    slot = trimesh.creation.box([CABLE_W, WALL + 2, CABLE_H])
    slot.apply_translation([
        x_center,
        MOUNT_D - WALL / 2,
        BASE_T + RISE * 0.5,
    ])
    return slot


# ============================================
# BOOLEAN ENGINE
# ============================================

def find_boolean_engine():
    """Detect the best available boolean engine."""
    engines = []
    try:
        import manifold3d  # noqa: F401
        engines.append('manifold')
    except ImportError:
        pass
    engines.append('blender')

    a = trimesh.creation.box([10, 10, 10])
    b = trimesh.creation.box([5, 5, 15])
    b.apply_translation([2.5, 2.5, 0])

    for eng in engines:
        try:
            r = trimesh.boolean.difference([a, b], engine=eng)
            if r is not None and hasattr(r, 'faces') and len(r.faces) > 0:
                return eng
        except Exception:
            continue
    return None


def subtract(body, cut, engine):
    """Boolean subtract cut from body."""
    try:
        result = trimesh.boolean.difference([body, cut], engine=engine)
        if result is not None and len(result.faces) > 0:
            return result
    except Exception:
        pass
    return None


# ============================================
# MAIN
# ============================================

def main():
    print("=" * 60)
    print("PEDESTAL MOUNT — STL Generator")
    print("For: SIGINT::OPTICS Control Panel (250 x 170 mm)")
    print("=" * 60)

    print(f"\n  Design")
    print(f"  {'—'*40}")
    print(f"  Type:           Two-piece angled wedge")
    print(f"  Tilt angle:     {TILT} deg from horizontal")
    print(f"  Half width:     {HALF_W:.0f} mm (each piece)")
    print(f"  Depth:          {MOUNT_D:.1f} mm")
    print(f"  Height (back):  {MOUNT_H:.1f} mm")
    ok = "YES" if max(HALF_W, MOUNT_D) <= 256 else "NO"
    print(f"  Bambu A1 fit:   {ok}")

    # --- Boolean engine ---
    print(f"\n  Boolean engine...")
    engine = find_boolean_engine()
    if engine:
        print(f"    Using: {engine}")
    else:
        print(f"    WARNING: none found — STL will have no holes")
        print(f"    Install manifold3d:  pip install manifold3d")

    # --- Mount body ---
    print(f"\n  Creating mount body...")
    profile = create_mount_profile()
    body = extrude_and_orient(profile, HALF_W)

    if not body.is_watertight:
        body.fill_holes()
        body.fix_normals()

    print(f"    Vertices: {len(body.vertices)}")
    print(f"    Faces:    {len(body.faces)}")
    print(f"    Bounds:   X=[{body.bounds[0][0]:.1f}, {body.bounds[1][0]:.1f}]"
          f"  Y=[{body.bounds[0][1]:.1f}, {body.bounds[1][1]:.1f}]"
          f"  Z=[{body.bounds[0][2]:.1f}, {body.bounds[1][2]:.1f}]")
    print(f"    Watertight: {body.is_watertight}")

    # --- Cut features ---
    result = body
    cut_ok = 0
    cut_total = 0

    if engine:
        print(f"\n  Cutting features...")

        # Panel insert holes
        for px, py in LEFT_PANEL_HOLES:
            cut_total += 1
            cyl = make_insert_hole(px, py)
            new = subtract(result, cyl, engine)
            if new is not None:
                result = new
                cut_ok += 1
                print(f"    OK  Insert at panel ({px:.0f}, {py:.0f})")
            else:
                print(f"    SKIP Insert at panel ({px:.0f}, {py:.0f})")

        # Pedestal screw holes
        for x, y in LEFT_PED_HOLES:
            cut_total += 1
            cyl = make_ped_hole(x, y)
            new = subtract(result, cyl, engine)
            if new is not None:
                result = new
                cut_ok += 1
                print(f"    OK  Pedestal screw at ({x:.0f}, {y:.0f})")
            else:
                print(f"    SKIP Pedestal screw at ({x:.0f}, {y:.0f})")

        # Cable slot
        cut_total += 1
        slot = make_cable_slot(HALF_W * 0.45)
        new = subtract(result, slot, engine)
        if new is not None:
            result = new
            cut_ok += 1
            print(f"    OK  Cable slot")
        else:
            print(f"    SKIP Cable slot")

        print(f"    Cut {cut_ok}/{cut_total} features")

    # --- Fix mesh ---
    if not result.is_watertight:
        result.fill_holes()
        result.fix_normals()

    # --- Export left half ---
    script_dir = os.path.dirname(os.path.abspath(__file__))

    left_path = os.path.join(script_dir, "pedestal-mount-left.stl")
    result.export(left_path, file_type="stl")
    left_size = os.path.getsize(left_path)

    print(f"\n  Left half")
    print(f"    File:       {os.path.basename(left_path)}")
    print(f"    Size:       {left_size / 1024:.1f} KB")
    print(f"    Vertices:   {len(result.vertices)}")
    print(f"    Faces:      {len(result.faces)}")
    print(f"    Watertight: {result.is_watertight}")

    # --- Mirror for right half ---
    print(f"\n  Creating right half (mirror)...")
    right = result.copy()
    right.vertices[:, 0] = HALF_W - right.vertices[:, 0]  # mirror X
    right.faces = right.faces[:, ::-1]                      # fix winding

    right_path = os.path.join(script_dir, "pedestal-mount-right.stl")
    right.export(right_path, file_type="stl")
    right_size = os.path.getsize(right_path)

    print(f"    File:       {os.path.basename(right_path)}")
    print(f"    Size:       {right_size / 1024:.1f} KB")
    print(f"    Watertight: {right.is_watertight}")

    # --- Summary ---
    print(f"\n{'=' * 60}")
    print("PRINT SETTINGS")
    print(f"{'=' * 60}")
    print("  Printer:       Bambu A1 (256x256mm bed)")
    print("  Layer height:  0.2mm")
    print("  Walls:         3-4 perimeters")
    print("  Infill:        20-25% gyroid")
    print("  Material:      PLA or PETG")
    print("  Supports:      none required")

    print(f"\n{'=' * 60}")
    print("HARDWARE (total for both halves)")
    print(f"{'=' * 60}")
    print("  4x M4 x 8mm socket-head cap screws (panel to mount)")
    print("  4x M4 x 5.7mm heat-set threaded inserts")
    print("  6x 1/4-20 or M6 flat-head screws (mount to pedestal)")

    print(f"\n{'=' * 60}")
    print("ASSEMBLY")
    print(f"{'=' * 60}")
    print("  1. Install heat-set inserts into the 4 angled pilot holes")
    print("     (soldering iron at 220C for PLA, 250C for PETG)")
    print("  2. Place both halves on pedestal, flat mating faces together")
    print("  3. Secure to pedestal with flat-head screws through base")
    print("  4. Seat the control panel on the angled surface")
    print("  5. Fasten panel with M4 cap screws into inserts")

    if not engine:
        print(f"\n{'=' * 60}")
        print("DRILL GUIDE (no boolean engine was available)")
        print(f"{'=' * 60}")
        print(f"  Panel insert holes: d={INSERT_D}mm x {INSERT_DEPTH}mm deep")
        print(f"    Drill perpendicular to the angled surface")
        for px, py in LEFT_PANEL_HOLES:
            mx, my, mz = surface_point(px, py)
            print(f"    at mount ({mx:.0f}, {my:.1f}, {mz:.1f}) mm")
        print(f"  Pedestal screws: d={PED_D}mm through base, d={PED_CBORE_D}mm counterbore")
        for x, y in LEFT_PED_HOLES:
            print(f"    at mount ({x:.0f}, {y:.0f}) mm")
        print("  (Mirror all positions for the right half)")

    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
