#!/usr/bin/env python3
"""Convert an SVG outline to an OpenSCAD mesh of interconnected hollow cylinders.

Instead of a solid slab with nail holes, this generates a wireframe-like mesh:
hollow cylinders at each nail position, connected by bars to their two nearest
neighbors (by Euclidean distance).

Shared nail-position computation is imported from string_art_utils.
"""

import argparse
import math
import os
import sys

from string_art_utils import (
    _build_arc_table,
    _point_from_arc,
    _signed_area,
    _split_subpaths,
    compute_nail_positions,
    get_corner_vertices,
    offset_nails_inward,
    parse_svg_paths,
    relative_svg_path,
    svg_canvas_height,
)


def _subpath_info(idx, starts):
    for s in range(len(starts) - 1):
        if starts[s] <= idx < starts[s + 1]:
            return s, idx - starts[s]
    return len(starts) - 1, idx - starts[-1]


def _circ_dist(a, b, length):
    d = abs(a - b)
    return min(d, length - d)


def _subpath_range(idx, starts):
    for s in range(len(starts) - 1):
        if starts[s] <= idx < starts[s + 1]:
            return s, starts[s], starts[s + 1]
    return len(starts) - 1, starts[-1], None


def _is_same_subpath(i, j, starts):
    si, _, _ = _subpath_range(i, starts)
    sj, _, _ = _subpath_range(j, starts)
    return si == sj


def _path_neighbors(i, starts):
    """Return (prev, next) indices along the same subpath, wrapping around."""
    si, lo, hi = _subpath_range(i, starts)
    if hi is None or hi - lo < 2:
        return None, None
    pos = i - lo
    length = hi - lo
    prev = lo + (pos - 1) % length
    nxt = lo + (pos + 1) % length
    return prev, nxt


def find_mesh_edges(points, subpath_starts, min_bridges=3, min_nail_gap=4):
    """Build a connected graph along path contours, bridged across components.

    Primary edges follow path order: each nail connects to its predecessor and
    successor along the same subpath (wrapping around for closed contours).
    This ensures the mesh traces the letter shape.

    Disconnected components (different contours / subpaths) are then bridged
    by adding *min_bridges* closest cross-component edges, ensuring the mesh
    is a single connected part.

    Returns a deduplicated list of ((x1,y1), (x2,y2)) edges.
    """
    n = len(points)
    if n <= 1:
        return []

    edges = set()

    # Step 1 — path-order edges: each nail connects to its neighbors along the contour
    if subpath_starts is not None:
        for i in range(n):
            prev, nxt = _path_neighbors(i, subpath_starts)
            if prev is not None:
                edges.add(tuple(sorted((i, prev))))
            if nxt is not None:
                edges.add(tuple(sorted((i, nxt))))

    # Build adjacency
    adj = {i: set() for i in range(n)}
    for i, j in edges:
        adj[i].add(j)
        adj[j].add(i)

    # Find connected components
    visited = set()
    components = []
    for i in range(n):
        if i not in visited:
            stack = [i]
            comp = set()
            while stack:
                v = stack.pop()
                if v not in visited:
                    visited.add(v)
                    comp.add(v)
                    stack.extend(adj[v] - visited)
            components.append(comp)

    # Step 2 — bridge disconnected components with closest cross-component edges.
    # Each bridge uses a distinct nail on the incoming component and respects
    # min_nail_gap spacing along the same subpath.
    while len(components) > 1:
        pairs = []
        for i in components[0]:
            xi, yi = points[i]
            for j in components[1]:
                d = math.hypot(xi - points[j][0], yi - points[j][1])
                pairs.append((d, i, j))
        pairs.sort(key=lambda x: x[0])

        added = 0
        used_nails = set()
        used_positions = {}

        for _, i, j in pairs:
            if added >= min_bridges:
                break
            if j in used_nails:
                continue

            if subpath_starts is not None:
                sp_idx, sp_pos = _subpath_info(j, subpath_starts)
                sp_len = subpath_starts[sp_idx + 1] - subpath_starts[sp_idx]
                too_close = False
                existing = used_positions.get(sp_idx, [])
                for pos in existing:
                    if _circ_dist(sp_pos, pos, sp_len) <= min_nail_gap:
                        too_close = True
                        break
                if too_close:
                    continue

            edge = tuple(sorted((i, j)))
            if edge not in edges:
                edges.add(edge)
                adj[i].add(j)
                adj[j].add(i)
                used_nails.add(j)
                if subpath_starts is not None:
                    used_positions.setdefault(sp_idx, []).append(sp_pos)
                added += 1

        components[0] |= components[1]
        components.pop(1)

    return [
        ((points[i][0], points[i][1]), (points[j][0], points[j][1])) for i, j in edges
    ]


def generate_scad_mesh(
    svg_path,
    nail_positions,
    edges,
    hole_diameter,
    thickness,
    wall_thickness,
    scad_path,
    canvas_height,
):
    svg_rel = relative_svg_path(svg_path, scad_path)

    def flip(y):
        return canvas_height - y if canvas_height else y

    def _ocall(x, y):
        ny = flip(y)
        return f"    outer_cylinder({x:.4f}, {ny:.4f});"

    def _hcall(x, y):
        ny = flip(y)
        return f"    inner_hole({x:.4f}, {ny:.4f});"

    tube_calls = [_ocall(x, y) for x, y in nail_positions]
    hole_calls = [_hcall(x, y) for x, y in nail_positions]

    def bar_call(x1, y1, x2, y2):
        ny1, ny2 = flip(y1), flip(y2)
        return f"    connecting_bar([{x1:.4f},{ny1:.4f}], [{x2:.4f},{ny2:.4f}]);"

    bar_calls = [bar_call(x1, y1, x2, y2) for (x1, y1), (x2, y2) in edges]

    lines = [
        f"// Generated by svg_to_mesh_openscad.py",
        f"// SVG source: {os.path.basename(svg_path)}",
        f"",
        f"thickness = {thickness}; // cylinder height in mm",
        f"hole_d = {hole_diameter}; // inner diameter of hollow cylinders in mm",
        f"wall = {wall_thickness}; // wall thickness of hollow cylinders in mm",
        f"",
        f"module outer_cylinder(x, y) {{",
        f"    translate([x, y, 0])",
        f"        cylinder(h = thickness, d = hole_d + 2*wall, $fn=16);",
        f"}}",
        f"",
        f"module inner_hole(x, y) {{",
        f"    translate([x, y, -1])",
        f"        cylinder(h = thickness + 2, d = hole_d, $fn=16);",
        f"}}",
        f"",
        f"module connecting_bar(p1, p2) {{",
        f"    oc = hole_d + 2*wall;",
        f"    hull() {{",
        f"        translate(p1) cylinder(h = thickness, d = oc, $fn=16);",
        f"        translate(p2) cylinder(h = thickness, d = oc, $fn=16);",
        f"    }}",
        f"}}",
        f"",
        f"module outer_cylinders() {{",
    ]
    lines += tube_calls
    lines += [
        f"}}",
        f"",
        f"module connecting_bars() {{",
    ]
    lines += bar_calls
    lines += [
        f"}}",
        f"",
        f"module inner_holes() {{",
    ]
    lines += hole_calls
    lines += [
        f"}}",
        f"",
        f"difference() {{",
        f"    union() {{",
        f"        outer_cylinders();",
        f"        connecting_bars();",
        f"    }}",
        f"    inner_holes();",
        f"}}",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert an SVG outline to an OpenSCAD mesh of interconnected hollow cylinders."
    )
    parser.add_argument("--input", required=True, help="Input SVG file")
    parser.add_argument(
        "--hole-diameter",
        type=float,
        default=5.0,
        help="Inner diameter of hollow cylinders in mm (default: 5.0)",
    )
    parser.add_argument(
        "--wall-thickness",
        type=float,
        default=1.0,
        help="Wall thickness of hollow cylinders in mm (default: 1.0)",
    )
    parser.add_argument(
        "--thickness",
        type=float,
        default=5.0,
        help="Cylinder height in mm (default: 5)",
    )
    parser.add_argument(
        "--output",
        help="Output OpenSCAD file path (default: input filename with .scad)",
    )
    parser.add_argument(
        "--max-spacing",
        type=float,
        default=40,
        help="Arc-length spacing between consecutive nails in mm "
        "(default: 40). Nails at path corners/junctions are always included; "
        "additional nails fill gaps proportionally to achieve this spacing. "
        "Pass 0 to disable and use junction-only placement.",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.input):
        parser.error(f"Input SVG file not found: {args.input}")
    if args.hole_diameter <= 0:
        parser.error("--hole-diameter must be positive")

    if not args.output:
        args.output = os.path.splitext(os.path.basename(args.input))[0] + ".scad"
    if not args.output.endswith(".scad"):
        args.output += ".scad"

    try:
        path_data = parse_svg_paths(args.input)
    except Exception as e:
        print(f"Error parsing SVG: {e}", file=sys.stderr)
        sys.exit(1)

    if not path_data:
        print("Error: No paths found in SVG", file=sys.stderr)
        sys.exit(1)

    nails = []
    starts = [0]
    inner_corners = []

    for pd in path_data:
        subpaths, _ = _split_subpaths(pd["path"])
        for sp in subpaths:
            before = len(nails)
            nails_with_t = compute_nail_positions(
                sp,
                hole_diameter=args.hole_diameter,
                max_spacing=args.max_spacing,
            )
            if nails_with_t:
                positions = offset_nails_inward(
                    nails_with_t, sp, args.hole_diameter, all_subpaths=subpaths
                )
                nails.extend(positions)
                starts.append(len(nails))

            is_inner = _signed_area(sp) < 0
            if is_inner and sp.length() > 0.01:
                total = sp.length()
                table = _build_arc_table(sp)
                vertices = get_corner_vertices(sp)
                corner_ts = {t for t, is_c in vertices if is_c and abs(t) > 1e-10}
                if not corner_ts:
                    continue
                corner_xy = [_point_from_arc(table, t * total) for t in corner_ts]

                def _find_corner_nails(nails_data, start, end, corners_out):
                    sub_nails = nails_data[start:end]
                    for cx, cy in corner_xy:
                        best = min(
                            range(len(sub_nails)),
                            key=lambda k: math.hypot(
                                cx - sub_nails[k][0], cy - sub_nails[k][1]
                            ),
                        )
                        gi = start + best
                        if gi not in corners_out:
                            corners_out.append(gi)

                _find_corner_nails(nails, before, len(nails), inner_corners)

    if not nails:
        print("Error: No nail positions computed", file=sys.stderr)
        sys.exit(1)

    edges = find_mesh_edges(nails, subpath_starts=starts)

    def _add_corner_bridges(nails_data, edges_data, corners, starts_data):
        if not corners:
            return
        edge_set = set(edges_data)
        for ci in corners:
            xc, yc = nails_data[ci]
            start = end = None
            for s in range(len(starts_data) - 1):
                if starts_data[s] <= ci < starts_data[s + 1]:
                    start, end = starts_data[s], starts_data[s + 1]
                    break
            if start is None:
                continue
            best = None
            best_d = math.inf
            for j, (xj, yj) in enumerate(nails_data):
                if start <= j < end:
                    continue
                d = math.hypot(xc - xj, yc - yj)
                if d < best_d:
                    best_d = d
                    best = j
            if best is not None:
                edge_set.add((nails_data[ci], nails_data[best]))
        edges_data[:] = sorted(edge_set, key=lambda e: (e[0][0], e[0][1]))

    _add_corner_bridges(nails, edges, inner_corners, starts)

    canvas_height = svg_canvas_height(args.input)

    scad_code = generate_scad_mesh(
        args.input,
        nails,
        edges,
        args.hole_diameter,
        args.thickness,
        args.wall_thickness,
        args.output,
        canvas_height=canvas_height,
    )

    with open(args.output, "w") as f:
        f.write(scad_code)

    print(f"OpenSCAD mesh saved to {args.output}")
    print(f"  Nail tubes:       {len(nails)}")
    print(f"  Mesh edges:       {len(edges)}")
    print(f"  Cylinder height:  {args.thickness} mm")
    print(f"  Hole diameter:    {args.hole_diameter} mm")
    print(f"  Wall thickness:   {args.wall_thickness} mm")


if __name__ == "__main__":
    main()