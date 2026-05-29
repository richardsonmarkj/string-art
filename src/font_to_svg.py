#!/usr/bin/env python3
"""Tool 1: Generate an SVG outline of a single letter in a specified font."""

import argparse
import os
import sys

from string_art_utils import system_font_path, glyph_to_svg_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate an SVG outline of a single letter in a specified font."
    )
    parser.add_argument("--letter", required=True, help="Single character to render")

    font_group = parser.add_mutually_exclusive_group(required=True)
    font_group.add_argument("--font", help="System font name (e.g., Arial)")
    font_group.add_argument(
        "--font-file", dest="font_file", help="Path to TTF/OTF font file"
    )

    parser.add_argument(
        "--outline",
        action="store_true",
        help="Render as outline/stroke (default is filled shape)",
    )
    parser.add_argument(
        "--stroke-width",
        type=float,
        default=1.0,
        help="Stroke width in mm (default: 1)",
    )
    parser.add_argument(
        "--width", type=float, default=170.0, help="Canvas width in mm (default: 170)"
    )
    parser.add_argument(
        "--height", type=float, default=170.0, help="Canvas height in mm (default: 170)"
    )
    parser.add_argument("--output", required=True, help="Output SVG file path")

    args = parser.parse_args()

    if not args.letter or len(args.letter) > 1:
        parser.error("--letter must be a single character")

    if args.font_file:
        font_path = args.font_file
        if not os.path.isfile(font_path):
            parser.error(f"Font file not found: {font_path}")
    else:
        try:
            font_path = system_font_path(args.font)
        except FileNotFoundError as e:
            parser.error(str(e))

    import svgwrite

    try:
        path_d, scale = glyph_to_svg_path(
            args.letter,
            font_path,
            canvas_w=args.width,
            canvas_h=args.height,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    dwg = svgwrite.Drawing(
        args.output,
        size=(f"{args.width}mm", f"{args.height}mm"),
        viewBox=f"0 0 {args.width} {args.height}",
    )
    if args.outline:
        dwg.add(
            dwg.path(
                d=path_d, fill="none", stroke="black", stroke_width=args.stroke_width
            )
        )
    else:
        dwg.add(dwg.path(d=path_d, fill="black", fill_rule="evenodd"))
    dwg.save()

    print(f"SVG saved to {args.output}")
    print(f"  Canvas: {args.width}x{args.height}mm")
    print(f"  Scale factor: {scale:.4f}")
    print(f"  Font file: {font_path}")
    if args.outline:
        print(f"  Style: outline (stroke-width={args.stroke_width}mm)")
    else:
        print(f"  Style: filled")


if __name__ == "__main__":
    main()
