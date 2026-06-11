#!/usr/bin/env python3
"""Generate a 2D SVG blueprint of nail+bar layout (top-down plan view).

Each contour (outer path, inner counters) is drawn independently as a closed loop of
circles connected by thick lines — no cross-contour bridges.  The visual
matches what the mesh model looks like from above.
"""

import argparse
import os
import sys
import xml.etree.ElementTree as ET

import svgwrite

from string_art_utils import (
    _signed_area,
    _split_subpaths,
    compute_nail_positions,
    offset_nails_inward,
    parse_svg_paths,
)


def svg_viewbox(svg_path):
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        vb = root.get("viewBox")
        if vb:
            parts = vb.strip().split()
            if len(parts) == 4:
                return float(parts[2]), float(parts[3])
    except Exception:
        pass
    return 170.0, 170.0


def main():
    parser = argparse.ArgumentParser(
        description="Generate a 2D SVG plan of nail+bar layout."
    )
    parser.add_argument("--input", required=True, help="Input SVG outline file")
    parser.add_argument(
        "--hole-diameter",
        default=3.0,
        type=float,
        help="Visual diameter of circles and bars in mm (default: 3.0)",
    )
    parser.add_argument(
        "--output", help="Output SVG plan file (default: input filename with .svg)"
    )
    parser.add_argument(
        "--no-outline", action="store_true", help="Omit the original faint outline"
    )
    parser.add_argument(
        "--no-edges", action="store_true", help="Only circles, skip connecting lines"
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

    if not args.output:
        args.output = (
            "plan_" + os.path.splitext(os.path.basename(args.input))[0] + ".svg"
        )
    if not args.output.endswith(".svg"):
        args.output += ".svg"

    try:
        path_data = parse_svg_paths(args.input)
    except Exception as e:
        print(f"Error parsing SVG: {e}", file=sys.stderr)
        sys.exit(1)

    if not path_data:
        print("Error: No paths found in SVG", file=sys.stderr)
        sys.exit(1)

    # Collect nail positions per subpath (no cross-subpath merging)
    subpath_nails = []
    subpath_info = []
    for pd in path_data:
        subpaths, _ = _split_subpaths(pd["path"])
        for sp in subpaths:
            nails_with_t = compute_nail_positions(
                sp,
                hole_diameter=args.hole_diameter,
                max_spacing=args.max_spacing,
            )
            if nails_with_t:
                positions = offset_nails_inward(
                    nails_with_t, sp, args.hole_diameter, all_subpaths=subpaths
                )
                direction = "inner" if _signed_area(sp) < 0 else "outer"
                subpath_nails.append(positions)
                subpath_info.append((direction, len(sp), len(positions)))

    if not subpath_nails:
        print("Error: No nail positions computed", file=sys.stderr)
        sys.exit(1)

    w, h = svg_viewbox(args.input)

    dwg = svgwrite.Drawing(
        args.output,
        size=(f"{w}mm", f"{h}mm"),
        viewBox=f"0 0 {w} {h}",
    )

    if not args.no_outline:
        for pd in path_data:
            dwg.add(
                dwg.path(
                    d=pd["path"].d(),
                    fill="none",
                    stroke="#ccc",
                    stroke_width=0.3,
                )
            )

    r = args.hole_diameter / 2

    for positions in subpath_nails:
        pts = [(x, y) for x, y in positions]

        if not args.no_edges and len(pts) >= 2:
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                dwg.add(
                    dwg.line(
                        start=(x1, y1),
                        end=(x2, y2),
                        stroke="black",
                        stroke_width=args.hole_diameter,
                        stroke_linecap="round",
                    )
                )

        for x, y in pts:
            dwg.add(
                dwg.circle(
                    center=(x, y), r=r, fill="white", stroke="black", stroke_width=0.5
                )
            )

    dwg.save()

    total_nails = sum(len(p) for p in subpath_nails)

    print(f"Plan SVG saved to {args.output}")
    print(f"  Canvas:            {w:.0f}x{h:.0f}mm")
    print(f"  Nail circles:      {total_nails}")
    print(f"  Visual diameter:   {args.hole_diameter} mm")
    for i, (direction, segs, count) in enumerate(subpath_info):
        print(f"  Subpath {i} ({direction}, {segs} segs): {count} nails")


if __name__ == "__main__":
    main()
