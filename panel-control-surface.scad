// ============================================
// CONTROL SURFACE PANEL — 3D Printable Version
// 280mm x 170mm x 4.76mm (3/16")
// Matches: panel-control-surface.svg
// ============================================
// Export: Render (F6) then Export as STL (F7)
// Print: 0.2mm layer height, 3 walls, 20% infill
// Material: PLA or PETG recommended
// ============================================

/* [Panel Dimensions] */
panel_w = 280;        // mm — panel width
panel_h = 170;        // mm — panel height
panel_t = 4.76;       // mm — thickness (3/16" acrylic)
corner_r = 5;         // mm — corner radius

/* [Mounting Holes — M4] */
m4_hole_d = 4.2;      // mm — M4 clearance hole
mount_inset = 10;     // mm — distance from edge to hole center

/* [Potentiometer — P160 TT Electronics] */
pot_hole_d = 7.5;     // mm — shaft hole diameter
pot_y = 90;           // mm — vertical center of pots
pot_x_start = 42.5;   // mm — first pot X
pot_spacing = 65;     // mm — spacing between pots
pot_count = 4;

// Anti-rotation tab slot
slot_w = 3.5;         // mm
slot_h = 2.0;         // mm
slot_r = 0.3;         // mm — corner radius
slot_offset_y = 7.8;  // mm — distance above shaft center
                      //      (slot top edge is at shaft_y - 7.8 - 1.0)

/* [Cable Routing Slot] */
cable_slot_x = 125;   // mm — left edge
cable_slot_y = 164;   // mm — top edge
cable_slot_w = 30;    // mm
cable_slot_h = 6;     // mm
cable_slot_r = 2;     // mm — corner radius

/* [Engraving] */
engrave_depth = 0.6;  // mm — depth of engraved features
engrave_deep = 0.8;   // mm — deep etch features (labels, arcs)

/* [Resolution] */
$fn = 64;


// ============================================
// MODULES
// ============================================

// Rounded rectangle (2D)
module rounded_rect(w, h, r) {
    offset(r) offset(-r) square([w, h]);
}

// Rounded rectangle with position (2D)
module rounded_rect_at(x, y, w, h, r) {
    translate([x, y]) rounded_rect(w, h, r);
}

// Through-hole cylinder
module through_hole(x, y, d) {
    translate([x, y, -1])
        cylinder(d=d, h=panel_t+2);
}

// Anti-rotation slot (through-cut)
module anti_rot_slot(cx, cy) {
    // cx, cy = pot center; slot is centered on pot X, offset above
    sx = cx - slot_w/2;
    sy = cy - slot_offset_y - slot_h/2;
    translate([0, 0, -1])
        linear_extrude(panel_t + 2)
            rounded_rect_at(sx, sy, slot_w, slot_h, slot_r);
}

// Cable routing slot (through-cut)
module cable_slot() {
    translate([0, 0, -1])
        linear_extrude(panel_t + 2)
            rounded_rect_at(cable_slot_x, cable_slot_y, cable_slot_w, cable_slot_h, cable_slot_r);
}

// Engraved line (rectangular groove on top surface)
module engrave_line(x1, y1, x2, y2, width=0.3, depth=engrave_depth) {
    len = sqrt((x2-x1)*(x2-x1) + (y2-y1)*(y2-y1));
    angle = atan2(y2-y1, x2-x1);
    translate([x1, y1, panel_t - depth])
        rotate([0, 0, angle])
            translate([0, -width/2, 0])
                cube([len, width, depth + 0.01]);
}

// Engraved arc (knob indicator arc)
module engrave_arc(cx, cy, r, start_angle, end_angle, width=0.3, depth=engrave_deep) {
    steps = 60;
    step_angle = (end_angle - start_angle) / steps;
    translate([0, 0, panel_t - depth])
        for (i = [0:steps-1]) {
            a1 = start_angle + i * step_angle;
            a2 = start_angle + (i+1) * step_angle;
            x1 = cx + r * cos(a1);
            y1 = cy + r * sin(a1);
            x2 = cx + r * cos(a2);
            y2 = cy + r * sin(a2);
            hull() {
                translate([x1, y1, 0]) cylinder(d=width, h=depth+0.01);
                translate([x2, y2, 0]) cylinder(d=width, h=depth+0.01);
            }
        }
}

// Engraved dot
module engrave_dot(x, y, d=1.0, depth=engrave_deep) {
    translate([x, y, panel_t - depth])
        cylinder(d=d, h=depth+0.01);
}

// Engraved tick mark
module engrave_tick(cx, cy, depth_val=engrave_deep) {
    // Center tick at 6 o'clock (below pot)
    engrave_line(cx, cy+15, cx, cy+17.5, width=0.3, depth=depth_val);
}

// Header/footer rules
module engrave_rule(x, y, w, depth_val=engrave_depth) {
    translate([x, y-0.125, panel_t - depth_val])
        cube([w, 0.25, depth_val+0.01]);
}

// Simple text label placeholder — engraved rectangle
// (OpenSCAD text() can be used if you have fonts installed)
module engrave_text_block(x, y, w, h, depth_val=engrave_deep) {
    translate([x, y, panel_t - depth_val])
        cube([w, h, depth_val+0.01]);
}

// Registration/corner mark
module corner_mark(x1, y1, x2, y2, x3, y3, width=0.2) {
    engrave_line(x1, y1, x2, y2, width, engrave_deep);
    engrave_line(x2, y2, x3, y3, width, engrave_deep);
}


// ============================================
// MAIN PANEL
// ============================================

// Note: SVG Y=0 is top, OpenSCAD Y=0 is bottom.
// We keep the same coordinate system as the SVG
// (Y increases downward in SVG, upward in OpenSCAD).
// The model uses SVG coordinates directly —
// flip in your slicer if needed, or uncomment the
// mirror line below.

difference() {
    // --- PANEL BODY ---
    linear_extrude(panel_t)
        rounded_rect(panel_w, panel_h, corner_r);

    // === THROUGH-CUT FEATURES ===

    // Corner mounting holes (M4 clearance)
    through_hole(mount_inset, mount_inset, m4_hole_d);
    through_hole(panel_w - mount_inset, mount_inset, m4_hole_d);
    through_hole(mount_inset, panel_h - mount_inset, m4_hole_d);
    through_hole(panel_w - mount_inset, panel_h - mount_inset, m4_hole_d);

    // Mid-edge mounting holes (M4)
    through_hole(panel_w/2, mount_inset, m4_hole_d);
    through_hole(panel_w/2, panel_h - mount_inset, m4_hole_d);

    // Potentiometer shaft holes
    for (i = [0:pot_count-1]) {
        px = pot_x_start + i * pot_spacing;
        through_hole(px, pot_y, pot_hole_d);
    }

    // Anti-rotation tab slots
    for (i = [0:pot_count-1]) {
        px = pot_x_start + i * pot_spacing;
        anti_rot_slot(px, pot_y);
    }

    // Cable routing slot
    cable_slot();

    // === ENGRAVED FEATURES (top surface) ===

    // Header rule line
    engrave_rule(12, 12, 256, engrave_depth);
    // Sub-header thin rule
    engrave_rule(12, 25, 256, engrave_depth * 0.5);
    // Footer rule line
    engrave_rule(12, 155, 256, engrave_depth);

    // Header text "SIGINT::OPTICS" — represented as engraved block
    engrave_text_block(14, 14, 42, 3.5, engrave_deep);

    // Knob arcs and labels (260-degree arcs, r=16)
    // Arc spans from ~230 deg to ~310 deg gap (dead zone at top)
    // In SVG the arc endpoints are at (-12.26, -10.28) and (12.26, -10.28)
    // relative to pot center. That's ~220 degrees sweep.
    // start_angle = 140 deg (from 3 o'clock), end_angle = 400 deg (=40 deg)
    for (i = [0:pot_count-1]) {
        px = pot_x_start + i * pot_spacing;

        // 260-degree arc, dead zone at top (~50 degrees each side of 90)
        // SVG arc: starts at (-12.26, -10.28) ends at (12.26, -10.28) relative to center
        // Converting: atan2(-10.28, -12.26) = ~220 deg, atan2(-10.28, 12.26) = ~320 deg
        // The arc goes the LONG way around (through bottom), so:
        // From 140 deg CCW to 40 deg (= 400 deg) = 260 degrees
        engrave_arc(px, pot_y, 16, 140, 400, width=0.3, depth=engrave_deep);

        // Endpoint dots
        engrave_dot(px - 12.26, pot_y - 10.28, d=1.0, depth=engrave_deep);
        engrave_dot(px + 12.26, pot_y - 10.28, d=1.0, depth=engrave_deep);

        // Center tick at 6 o'clock
        engrave_tick(px, pot_y, engrave_deep);
    }

    // Knob labels (I, II, III, IV) — small engraved blocks
    label_y = pot_y + 37;  // ~40 units below pot center, adjusted for block size
    engrave_text_block(pot_x_start - 2, label_y, 4, 3, engrave_deep);             // I
    engrave_text_block(pot_x_start + pot_spacing - 4, label_y, 8, 3, engrave_deep); // II
    engrave_text_block(pot_x_start + 2*pot_spacing - 5, label_y, 10, 3, engrave_deep); // III
    engrave_text_block(pot_x_start + 3*pot_spacing - 4, label_y, 8, 3, engrave_deep); // IV

    // Scale ruler (50mm reference line, near footer)
    engrave_line(14, 148, 64, 148, width=0.2, depth=engrave_depth);
    engrave_line(14, 146.5, 14, 149.5, width=0.2, depth=engrave_depth);
    engrave_line(64, 146.5, 64, 149.5, width=0.2, depth=engrave_depth);

    // Corner registration marks
    corner_mark(2, 8, 2, 2, 8, 2);
    corner_mark(272, 2, 278, 2, 278, 8);
    corner_mark(2, 162, 2, 168, 8, 168);
    corner_mark(278, 162, 278, 168, 272, 168);
}


// ============================================
// OPTIONAL: Text labels using OpenSCAD text()
// Uncomment if your OpenSCAD has font support
// ============================================

/*
// Header text
translate([14, panel_h - 20, panel_t - engrave_deep])
    linear_extrude(engrave_deep + 0.01)
        text("SIGINT::OPTICS", size=3.5, font="Courier New:style=Bold", spacing=1.1);

// Knob labels
labels = ["I", "II", "III", "IV"];
for (i = [0:3]) {
    px = pot_x_start + i * pot_spacing;
    translate([px, panel_h - pot_y - 40, panel_t - engrave_deep])
        linear_extrude(engrave_deep + 0.01)
            text(labels[i], size=3.2, font="Courier New", halign="center", spacing=1.2);
}
*/
