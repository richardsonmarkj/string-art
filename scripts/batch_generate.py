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
SVG_HOLE_DIAMETER = 3
STL_HOLE_DIAMETER = 5
THICKNESS = 5
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
    for line in result.stdout.strip().splitlines():
        print(f"    {line}")


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
        "--font-file",
        default=None,
        help="Path to TTF/OTF font file (overrides --font)",
    )
    parser.add_argument(
        "--stl-hole-diameter",
        type=float,
        default=STL_HOLE_DIAMETER,
        help=f"Hole diameter in mm for STL (default: {STL_HOLE_DIAMETER})",
    )
    parser.add_argument(
        "--plan-hole-diameter",
        type=float,
        default=SVG_HOLE_DIAMETER,
        help=f"Hole diameter in mm for Plan SVG (default: {SVG_HOLE_DIAMETER})",
    )
    parser.add_argument(
        "--thickness",
        type=float,
        default=THICKNESS,
        help=f"Model thickness in mm (default: {THICKNESS})",
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--mesh",
        action="store_true",
        help="Generate mesh SCAD (svg_to_mesh_openscad)",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Generate 2D plan SVG (svg_to_nail_plan_svg)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate both mesh SCAD/STL and plan SVG in one pass",
    )
    parser.add_argument(
        "--wall-thickness",
        type=float,
        default=1.0,
        help="Wall thickness for mesh mode in mm (default: 1.0)",
    )
    parser.add_argument("--skip-stl", action="store_true", help="Skip STL rendering")
    parser.add_argument(
        "--no-outline",
        action="store_true",
        help="Omit the original faint outline in plan SVG",
    )
    parser.add_argument(
        "--no-edges",
        action="store_true",
        help="Only show nail circles, skip connecting bar lines in plan SVG",
    )
    parser.add_argument(
        "--max-spacing",
        type=float,
        default=40,
        help="Maximum arc-length gap between consecutive nails in mm "
        "(default: 40). Pass 0 to disable.",
    )
    args = parser.parse_args()

    if args.all:
        if args.mesh or args.plan:
            parser.error("--all is exclusive with --mesh and --plan")
    elif not args.mesh and not args.plan:
        parser.error("Specify --mesh, --plan, or --all")

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

    def _build_svg_cmd(letter, svg_path):
        cmd = [
            sys.executable,
            font_to_svg,
            "--letter",
            letter,
            "--output",
            svg_path,
        ]
        if args.font_file:
            cmd += ["--font-file", args.font_file]
        else:
            cmd += ["--font", args.font]
        return cmd

    def _build_mesh_cmd(svg_path, scad_path):
        cmd = [
            sys.executable,
            os.path.join(REPO_DIR, "src", "svg_to_mesh_openscad.py"),
            "--input",
            svg_path,
            "--hole-diameter",
            str(args.stl_hole_diameter),
            "--wall-thickness",
            str(args.wall_thickness),
            "--thickness",
            str(args.thickness),
            "--output",
            scad_path,
        ]
        cmd += ["--max-spacing", str(args.max_spacing)]
        return cmd

    def _build_plan_cmd(svg_path, plan_path):
        cmd = [
            sys.executable,
            os.path.join(REPO_DIR, "src", "svg_to_nail_plan_svg.py"),
            "--input",
            svg_path,
            "--hole-diameter",
            str(args.plan_hole_diameter),
            "--output",
            plan_path,
        ]
        cmd += ["--max-spacing", str(args.max_spacing)]
        if args.no_outline:
            cmd += ["--no-outline"]
        if args.no_edges:
            cmd += ["--no-edges"]
        return cmd

    for letter in letters:
        print(f"\n[{letter}]")
        svg_path = os.path.join(out_dir, f"letter_{letter}.svg")
        run(_build_svg_cmd(letter, svg_path), "SVG")

        if args.mesh or args.all:
            scad_path = os.path.join(out_dir, f"mesh_{letter}.scad")
            run(_build_mesh_cmd(svg_path, scad_path), "MESH")
            if openscad:
                stl_path = os.path.join(out_dir, f"mesh_{letter}.stl")
                run([openscad, "-o", stl_path, scad_path], "STL")

        if args.plan or args.all:
            plan_path = os.path.join(out_dir, f"plan_{letter}.svg")
            run(_build_plan_cmd(svg_path, plan_path), "PLAN")

    print(f"\nDone. Files in {out_dir}")


if __name__ == "__main__":
    main()