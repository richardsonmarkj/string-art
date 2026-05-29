#!/usr/bin/env python3
"""Convert an SVG outline to an OpenSCAD mesh of interconnected hollow cylinders.

Instead of a solid slab with nail holes, this generates a wireframe-like mesh:
hollow cylinders at each nail position, connected by bars to their two nearest
neighbors (by Euclidean distance).

Shared nail-position computation is imported from svg_to_openscad.py.
"""

import argparse
import math
import os
import sys

from svg_to_openscad import (
    _split_subpaths,
    compute_nail_positions,
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


def find_mesh_edges(points, k=2, min_bridges=3, min_nail_gap=4, subpath_starts=None):
    """Build a connected graph by connecting each point to its k nearest neighbors.

    After k-nearest assignment, disconnected components are bridged by adding
    *min_bridges* closest cross-component edges between each component pair,
    ensuring the mesh is a single connected part with adequate structural joints.

    When *subpath_starts* is provided, bridges on the incoming component are
    placed at least *min_nail_gap* positions apart along the same subpath
    (accounting for wrap-around on closed contours).
    Returns a deduplicated list of ((x1,y1), (x2,y2)) edges.
    """
    n = len(points)
    if n <= 1:
        return []

    edges = set()
    for i in range(n):
        xi, yi = points[i]
        dists = []
        for j in range(n):
            if j == i:
                continue
            xj, yj = points[j]
            dists.append((math.hypot(xi - xj, yi - yj), j))
        dists.sort(key=lambda x: x[0])
        for _, j in dists[:k]:
            edges.add(tuple(sorted((i, j))))

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

    # Bridge components by adding min_bridges closest cross-component edges.
    # Each bridge uses a distinct nail on the incoming component (components[1])
    # and respects min_nail_gap spacing along the same subpath.
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
        used_positions = {}  # subpath_idx -> list of positions along subpath

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
    nail_positions_1,
    nail_positions_2,
    edges_1,
    edges_2,
    hole_diameter,
    thickness,
    wall_thickness,
    default_strategy,
    scad_path,
    canvas_height,
):
    svg_rel = relative_svg_path(svg_path, scad_path)

    def flip(y):
        return canvas_height - y if canvas_height else y

    tube_calls_1 = [
        f"    nail_tube({x:.4f}, {flip(y):.4f});" for x, y in nail_positions_1
    ]
    tube_calls_2 = [
        f"    nail_tube({x:.4f}, {flip(y):.4f});" for x, y in nail_positions_2
    ]

    def bar_call(x1, y1, x2, y2):
        ny1, ny2 = flip(y1), flip(y2)
        return f"    connecting_bar([{x1:.4f},{ny1:.4f}], [{x2:.4f},{ny2:.4f}]);"

    bar_calls_1 = [bar_call(x1, y1, x2, y2) for (x1, y1), (x2, y2) in edges_1]
    bar_calls_2 = [bar_call(x1, y1, x2, y2) for (x1, y1), (x2, y2) in edges_2]

    lines = [
        f"// Generated by svg_to_mesh_openscad.py",
        f"// SVG source: {os.path.basename(svg_path)}",
        f"",
        f"thickness = {thickness}; // cylinder height in mm",
        f"hole_d = {hole_diameter}; // inner diameter of hollow cylinders in mm",
        f"wall = {wall_thickness}; // wall thickness of hollow cylinders in mm",
        f"corner_strategy = {default_strategy}; // 1=corners-first, 2=all-vertices",
        f"",
        f"module nail_tube(x, y) {{",
        f"    translate([x, y, 0])",
        f"    difference() {{",
        f"        cylinder(h = thickness, d = hole_d + 2*wall, $fn=16);",
        f"        translate([0, 0, -1])",
        f"            cylinder(h = thickness + 2, d = hole_d, $fn=16);",
        f"    }}",
        f"}}",
        f"",
        f"module connecting_bar(p1, p2) {{",
        f"    oc = hole_d + 2*wall;   // outer cylinder diameter",
        f"    h = thickness;",
        f"    dx = p2[0] - p1[0];",
        f"    dy = p2[1] - p1[1];",
        f"    len = sqrt(dx*dx + dy*dy);",
        f"    if (len > oc + 0.01) {{",
        f"        angle = atan2(dy, dx);",
        f"        // overlap=wall so bar fuses into cylinder wall",
        f"        overlap = wall;",
        f"        translate(p1)",
        f"        rotate([0, 0, angle])",
        f"        translate([oc/2 - overlap, -oc/2, -1])",
        f"            cube([len - oc + 2*overlap, oc, h + 2]);",
        f"    }}",
        f"}}",
        f"",
        f"module nail_tubes_strategy1() {{",
    ]
    lines += tube_calls_1
    lines += [
        f"}}",
        f"",
        f"module connecting_bars_strategy1() {{",
    ]
    lines += bar_calls_1
    lines += [
        f"}}",
        f"",
        f"module nail_tubes_strategy2() {{",
    ]
    lines += tube_calls_2
    lines += [
        f"}}",
        f"",
        f"module connecting_bars_strategy2() {{",
    ]
    lines += bar_calls_2
    lines += [
        f"}}",
        f"",
        f"module mesh_strategy1() {{",
        f"    union() {{",
        f"        nail_tubes_strategy1();",
        f"        connecting_bars_strategy1();",
        f"    }}",
        f"}}",
        f"",
        f"module mesh_strategy2() {{",
        f"    union() {{",
        f"        nail_tubes_strategy2();",
        f"        connecting_bars_strategy2();",
        f"    }}",
        f"}}",
        f"",
        f"module mesh() {{",
        f"    if (corner_strategy == 1) mesh_strategy1();",
        f"    else mesh_strategy2();",
        f"}}",
        f"",
        f"mesh();",
    ]

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Convert an SVG outline to an OpenSCAD mesh of interconnected hollow cylinders."
    )
    parser.add_argument("--input", required=True, help="Input SVG file")
    parser.add_argument(
        "--spacing", type=float, required=True, help="Nail spacing in mm"
    )
    parser.add_argument(
        "--hole-diameter",
        type=float,
        required=True,
        help="Inner diameter of hollow cylinders in mm",
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
    starts_1 = [0]
    starts_2 = [0]
    for pd in path_data:
        subpaths, _ = _split_subpaths(pd["path"])
        for sp in subpaths:
            for strategy in (1, 2):
                nails_with_t = compute_nail_positions(sp, args.spacing, strategy)
                if nails_with_t:
                    positions = offset_nails_inward(
                        nails_with_t, sp, args.hole_diameter, all_subpaths=subpaths
                    )
                    if strategy == 1:
                        nails_1.extend(positions)
                        starts_1.append(len(nails_1))
                    else:
                        nails_2.extend(positions)
                        starts_2.append(len(nails_2))

    if not nails_1 and not nails_2:
        print("Error: No nail positions computed", file=sys.stderr)
        sys.exit(1)

    edges_1 = find_mesh_edges(nails_1, k=2, subpath_starts=starts_1) if nails_1 else []
    edges_2 = find_mesh_edges(nails_2, k=2, subpath_starts=starts_2) if nails_2 else []

    canvas_height = svg_canvas_height(args.input)

    scad_code = generate_scad_mesh(
        args.input,
        nails_1,
        nails_2,
        edges_1,
        edges_2,
        args.hole_diameter,
        args.thickness,
        args.wall_thickness,
        args.corner_strategy,
        args.output,
        canvas_height=canvas_height,
    )

    with open(args.output, "w") as f:
        f.write(scad_code)

    print(f"OpenSCAD mesh saved to {args.output}")
    print(f"  Nail tubes (strategy 1): {len(nails_1)}")
    print(f"  Mesh edges (strategy 1): {len(edges_1)}")
    print(f"  Nail tubes (strategy 2): {len(nails_2)}")
    print(f"  Mesh edges (strategy 2): {len(edges_2)}")
    print(f"  Cylinder height:         {args.thickness} mm")
    print(f"  Nail spacing:            {args.spacing} mm")
    print(f"  Hole diameter:           {args.hole_diameter} mm")
    print(f"  Wall thickness:          {args.wall_thickness} mm")
    print(
        f"  Default strategy:        {'corners-first' if args.corner_strategy == 1 else 'all-vertices'}"
    )


if __name__ == "__main__":
    main()
