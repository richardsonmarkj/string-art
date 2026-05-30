#!/usr/bin/env python3
"""Batch generate SVG, SCAD, and STL files for a set of letters."""

import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SCRIPT_DIR)

LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")

FONT = "Arial"
SPACING = 10
HOLE_DIAMETER = 3
THICKNESS = 5
CORNER_STRATEGY = 1
OUTPUT_DIR = "output"


def find_openscad():
    for candidate in [
        "openscad",
        "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
    ]:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return None


def run(cmd, desc):
    print(f"  {desc}...", end=" ", flush=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FAILED")
        print(result.stderr)
        sys.exit(1)
    print("OK")


def main():
    parser = argparse.ArgumentParser(
        description="Batch generate string art templates for multiple letters."
    )
    parser.add_argument(
        "--letters", nargs="+", default=None, help="Letters to process (default: A-Z)"
    )
    parser.add_argument(
        "--font", default=FONT, help=f"System font name (default: {FONT})"
    )
    parser.add_argument(
        "--spacing",
        type=float,
        default=SPACING,
        help=f"Nail spacing in mm (default: {SPACING})",
    )
    parser.add_argument(
        "--hole-diameter",
        type=float,
        default=HOLE_DIAMETER,
        help=f"Hole diameter in mm (default: {HOLE_DIAMETER})",
    )
    parser.add_argument(
        "--thickness",
        type=float,
        default=THICKNESS,
        help=f"Model thickness in mm (default: {THICKNESS})",
    )
    parser.add_argument(
        "--corner-strategy",
        type=int,
        choices=[1, 2],
        default=CORNER_STRATEGY,
        help=f"Corner strategy (default: {CORNER_STRATEGY})",
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--mesh",
        action="store_true",
        help="Generate mesh SCAD (svg_to_mesh_openscad) instead of slab template",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Generate 2D plan SVG (svg_to_nail_plan_svg) instead of slab template",
    )
    parser.add_argument(
        "--wall-thickness",
        type=float,
        default=1.0,
        help="Wall thickness for mesh mode in mm (default: 1.0)",
    )
    parser.add_argument("--skip-stl", action="store_true", help="Skip STL rendering")
    args = parser.parse_args()

    letters = args.letters if args.letters else LETTERS
    out_dir = os.path.join(REPO_DIR, args.output_dir)
    os.makedirs(out_dir, exist_ok=True)

    openscad = None if args.skip_stl else find_openscad()
    if not args.skip_stl:
        if openscad:
            print(f"  OpenSCAD: {openscad}")
        else:
            print("  OpenSCAD not found — STL rendering will be skipped")

    font_to_svg = os.path.join(REPO_DIR, "src", "font_to_svg.py")

    if args.plan:
        gen_script = os.path.join(REPO_DIR, "src", "svg_to_nail_plan_svg.py")
        label = "PLAN"
        prefix = "plan_"
        ext = ".svg"
    elif args.mesh:
        gen_script = os.path.join(REPO_DIR, "src", "svg_to_mesh_openscad.py")
        label = "MESH"
        prefix = "mesh_"
        ext = ".scad"
    else:
        gen_script = os.path.join(REPO_DIR, "src", "svg_to_openscad.py")
        label = "SCAD"
        prefix = "template_"
        ext = ".scad"

    for letter in letters:
        print(f"\n[{letter}]")
        svg_path = os.path.join(out_dir, f"letter_{letter}.svg")
        out_path = os.path.join(out_dir, f"{prefix}{letter}{ext}")
        stl_path = os.path.join(out_dir, f"{prefix}{letter}.stl")

        run(
            [
                sys.executable,
                font_to_svg,
                "--letter",
                letter,
                "--font",
                args.font,
                "--output",
                svg_path,
            ],
            "SVG",
        )

        if args.plan:
            cmd = [
                sys.executable,
                gen_script,
                "--input",
                svg_path,
                "--spacing",
                str(args.spacing),
                "--hole-diameter",
                str(args.hole_diameter),
                "--corner-strategy",
                str(args.corner_strategy),
                "--output",
                out_path,
            ]
        elif args.mesh:
            cmd = [
                sys.executable,
                gen_script,
                "--input",
                svg_path,
                "--spacing",
                str(args.spacing),
                "--hole-diameter",
                str(args.hole_diameter),
                "--wall-thickness",
                str(args.wall_thickness),
                "--thickness",
                str(args.thickness),
                "--corner-strategy",
                str(args.corner_strategy),
                "--output",
                out_path,
            ]
        else:
            cmd = [
                sys.executable,
                gen_script,
                "--input",
                svg_path,
                "--spacing",
                str(args.spacing),
                "--hole-diameter",
                str(args.hole_diameter),
                "--thickness",
                str(args.thickness),
                "--corner-strategy",
                str(args.corner_strategy),
                "--output",
                out_path,
            ]
        run(cmd, label)

        if openscad and not args.plan and ext == ".scad":
            run([openscad, "-o", stl_path, out_path], "STL")

    print(f"\nDone. Files in {out_dir}")


if __name__ == "__main__":
    main()
