#!/usr/bin/env python3
"""Tool 2: Convert an SVG outline to OpenSCAD 3D model with nail placement holes.

Parses any SVG file, computes nail positions along all paths, and generates
self-contained OpenSCAD code that imports the SVG and places cylindrical holes
at each nail position.

The SVG is imported (not embedded) so that OpenSCAD handles bezier curves with
full precision. Nail coordinates are computed in the SVG's native coordinate
space, guaranteeing alignment with the imported geometry.
"""

import argparse
import math
import os
import sys

import svgpathtools


CORNER_ANGLE_THRESHOLD = 30


def parse_svg_paths(svg_path):
    paths, attributes = svgpathtools.svg2paths(svg_path)
    path_data = []
    for i, path in enumerate(paths):
        attrs = attributes[i] if i < len(attributes) else {}
        path_data.append(
            {
                "path": path,
                "fill": attrs.get("fill", ""),
                "fill_rule": attrs.get("fill-rule", attrs.get("fillRule", "nonzero")),
                "id": attrs.get("id", f"path_{i}"),
            }
        )
    return path_data


def is_corner(prev_seg, next_seg, threshold=CORNER_ANGLE_THRESHOLD):
    try:
        d1 = prev_seg.derivative(1)
        if abs(d1) < 1e-10:
            return True
        t1 = d1 / abs(d1)

        d2 = next_seg.derivative(0)
        if abs(d2) < 1e-10:
            return True
        t2 = d2 / abs(d2)

        dot = t1.real * t2.real + t1.imag * t2.imag
        cos_a = max(-1.0, min(1.0, dot))
        angle = math.degrees(math.acos(cos_a))
        return angle > threshold
    except (ZeroDivisionError, ValueError):
        return True


def get_corner_vertices(path):
    n = len(path)
    total = path.length()
    cum = 0.0
    vertices = []
    for i, seg in enumerate(path):
        t = cum / total
        if i == 0:
            vertices.append((t, True))
        cum += seg.length()
        next_seg = path[(i + 1) % n]
        vertices.append((min(cum / total, 1.0), is_corner(seg, next_seg)))
    return vertices


def _build_arc_table(path, samples_per_mm=4):
    """Build a lookup table mapping arc length → (x, y) at high resolution.

    This avoids svgpathtools' broken t-parameterization for curved segments.
    Returns list of (arc_length, x, y) sorted by arc_length.
    """
    total = path.length()
    table = [(0.0, path.point(0).real, path.point(0).imag)]
    cum = 0.0
    for seg in path:
        seg_len = seg.length()
        n = max(2, int(seg_len * samples_per_mm))
        for i in range(1, n + 1):
            local_t = i / n
            pt = seg.point(local_t)
            arc = cum + seg.length(0, local_t)
            table.append((arc, pt.real, pt.imag))
        cum += seg_len
    # Ensure exact closure
    table[-1] = (total, path.point(1).real, path.point(1).imag)
    return table


def _point_from_arc(arc_table, target_arc):
    """Interpolate (x, y) at a given arc length from the arc table."""
    if target_arc <= arc_table[0][0]:
        return arc_table[0][1], arc_table[0][2]
    if target_arc >= arc_table[-1][0]:
        return arc_table[-1][1], arc_table[-1][2]
    lo, hi = 0, len(arc_table) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if arc_table[mid][0] <= target_arc:
            lo = mid
        else:
            hi = mid
    a0, x0, y0 = arc_table[lo]
    a1, x1, y1 = arc_table[hi]
    if a1 - a0 < 1e-10:
        return x0, y0
    f = (target_arc - a0) / (a1 - a0)
    return x0 + f * (x1 - x0), y0 + f * (y1 - y0)


def compute_nail_positions(path, spacing, strategy):
    total = path.length()
    if total < 0.01:
        return []

    arc_table = _build_arc_table(path)

    # Get must-have arc positions (corners/vertices)
    if strategy == 1:
        vertices = get_corner_vertices(path)
    else:
        cum = 0.0
        vertices = []
        for seg in path:
            vertices.append((cum / total, True))
            cum += seg.length()
        vertices.append((1.0, True))

    must_have_ts = sorted({t for t, is_c in vertices if is_c})
    if 1.0 not in must_have_ts:
        must_have_ts.append(1.0)

    # Convert must-have t values to actual arc lengths
    must_have_arcs = []
    for t in must_have_ts:
        x, y = _point_from_arc(arc_table, t * total)
        must_have_arcs.append((t * total, x, y, t))

    raw = []
    for i, (arc_a, x_a, y_a, t_a) in enumerate(must_have_arcs):
        raw.append((x_a, y_a, t_a))
        if i < len(must_have_arcs) - 1:
            arc_b = must_have_arcs[i + 1][0]
            if abs(arc_b - arc_a) < 1e-10:
                continue
            arc_len = arc_b - arc_a
            num = max(0, int(arc_len / spacing + 0.5) - 1)
            for j in range(1, num + 1):
                target_arc = arc_a + arc_len * j / (num + 1)
                x, y = _point_from_arc(arc_table, target_arc)
                raw.append((x, y, 0.0))

    cleaned = []
    for x, y, t in raw:
        if cleaned:
            lx, ly, _ = cleaned[-1]
            if math.hypot(x - lx, y - ly) < 0.5:
                continue
        cleaned.append((x, y, t))

    if len(cleaned) > 1:
        fx, fy, _ = cleaned[0]
        lx, ly, _ = cleaned[-1]
        if math.hypot(lx - fx, ly - fy) < 0.5:
            cleaned.pop()

    return cleaned  # list of (x, y, t)


def _split_subpaths(path):
    """Split a compound Path into individual closed subpaths."""
    subpaths = []
    current = []
    for i, seg in enumerate(path):
        current.append(seg)
        if i < len(path) - 1:
            if abs(seg.end - path[i + 1].start) > 1e-6:
                subpaths.append(svgpathtools.Path(*current))
                current = []
    if current:
        subpaths.append(svgpathtools.Path(*current))
    return subpaths, [len(sp) for sp in subpaths]


def _signed_area(subpath):
    area = 0.0
    samples_per_seg = 16
    for seg in subpath:
        seg_len = seg.length() if hasattr(seg, "length") else 1.0
        n = max(samples_per_seg, int(seg_len / 2))
        for i in range(n):
            t1 = i / n
            t2 = (i + 1) / n
            p1 = seg.point(t1)
            p2 = seg.point(t2)
            area += p1.real * p2.imag - p2.real * p1.imag
    return area


def offset_nails_inward(nails_with_t, path=None, hole_diameter=None, all_subpaths=None):
    """Place nail holes on the edge of the outline (no offset)."""
    return [(x, y) for x, y, t in nails_with_t]


def relative_svg_path(svg_path, scad_path):
    svg_abs = os.path.abspath(svg_path)
    scad_dir = os.path.dirname(os.path.abspath(scad_path))
    try:
        return os.path.relpath(svg_abs, scad_dir)
    except ValueError:
        return svg_abs


def svg_canvas_height(svg_path):
    """Extract the canvas height from an SVG file's viewBox."""
    import xml.etree.ElementTree as ET

    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        viewbox = root.get("viewBox")
        if viewbox:
            parts = viewbox.strip().split()
            if len(parts) == 4:
                return float(parts[3])
    except Exception:
        pass
    return None


def generate_scad(
    svg_path,
    nail_positions_1,
    nail_positions_2,
    hole_diameter,
    thickness,
    default_strategy,
    scad_path,
    canvas_height,
):
    svg_rel = relative_svg_path(svg_path, scad_path)

    def write_nail_module(name, positions):
        lines = [f"module {name}() {{"]
        for x, y in positions:
            ny = canvas_height - y if canvas_height else y
            lines.append(f"    translate([{x:.4f}, {ny:.4f}, -1])")
            lines.append(f"        cylinder(h = thickness + 2, d = hole_d, $fn=16);")
        lines.append("}")
        return lines

    lines = [
        f"// Generated by svg_to_openscad.py",
        f"// SVG source: {os.path.basename(svg_path)}",
        f"",
        f"thickness = {thickness}; // model thickness in mm (manifest constant)",
        f"hole_d = {hole_diameter}; // nail hole diameter in mm",
        f"corner_strategy = {default_strategy}; // 1=corners-first, 2=all-vertices",
        f"",
        f"module letter_outline() {{",
        f"    linear_extrude(height = thickness)",
        f'        import("{svg_rel}");',
        f"}}",
        f"",
    ]
    lines += write_nail_module("nail_holes_strategy1", nail_positions_1)
    lines += [""]
    lines += write_nail_module("nail_holes_strategy2", nail_positions_2)
    lines += [
        f"",
        f"module nail_holes() {{",
        f"    if (corner_strategy == 1) nail_holes_strategy1();",
        f"    else nail_holes_strategy2();",
        f"}}",
        f"",
        f"difference() {{",
        f"    letter_outline();",
        f"    nail_holes();",
        f"}}",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert an SVG outline to OpenSCAD 3D model with nail placement holes."
    )
    parser.add_argument("--input", required=True, help="Input SVG file")
    parser.add_argument(
        "--spacing", type=float, required=True, help="Nail spacing in mm"
    )
    parser.add_argument(
        "--hole-diameter", type=float, required=True, help="Nail hole diameter in mm"
    )
    parser.add_argument(
        "--thickness",
        type=float,
        default=5.0,
        help="Model thickness in mm (default: 5)",
    )
    parser.add_argument(
        "--corner-strategy",
        type=int,
        choices=[1, 2],
        default=1,
        help="Corner strategy: 1=corners-first, 2=all-vertices (default: 1)",
    )
    parser.add_argument("--output", required=True, help="Output OpenSCAD file path")

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        parser.error(f"Input SVG file not found: {args.input}")
    if args.spacing <= 0:
        parser.error("--spacing must be positive")
    if args.hole_diameter <= 0:
        parser.error("--hole-diameter must be positive")

    try:
        path_data = parse_svg_paths(args.input)
    except Exception as e:
        print(f"Error parsing SVG: {e}", file=sys.stderr)
        sys.exit(1)

    if not path_data:
        print("Error: No paths found in SVG", file=sys.stderr)
        sys.exit(1)

    nails_1 = []
    nails_2 = []
    for pd in path_data:
        subpaths, _ = _split_subpaths(pd["path"])
        for sp in subpaths:
            for strategy, store in [(1, nails_1), (2, nails_2)]:
                nails_with_t = compute_nail_positions(sp, args.spacing, strategy)
                if nails_with_t:
                    offset = offset_nails_inward(
                        nails_with_t, sp, args.hole_diameter, all_subpaths=subpaths
                    )
                    store.extend(offset)

    if not nails_1 and not nails_2:
        print("Error: No nail positions computed", file=sys.stderr)
        sys.exit(1)

    canvas_height = svg_canvas_height(args.input)

    scad_code = generate_scad(
        args.input,
        nails_1,
        nails_2,
        args.hole_diameter,
        args.thickness,
        args.corner_strategy,
        args.output,
        canvas_height=canvas_height,
    )

    with open(args.output, "w") as f:
        f.write(scad_code)

    print(f"OpenSCAD saved to {args.output}")
    print(f"  Nail holes (strategy 1): {len(nails_1)}")
    print(f"  Nail holes (strategy 2): {len(nails_2)}")
    print(f"  Thickness:               {args.thickness} mm")
    print(f"  Nail spacing:            {args.spacing} mm")
    print(f"  Hole diameter:           {args.hole_diameter} mm")
    print(
        f"  Default strategy:        {'corners-first' if args.corner_strategy == 1 else 'all-vertices'}"
    )


if __name__ == "__main__":
    main()
