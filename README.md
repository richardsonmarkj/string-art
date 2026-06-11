# String Art Template Generator

Generate 3D-printable or paper-printed string art nail templates. The toolchain takes a letter, generates an SVG outline, then produces an OpenSCAD mesh model with precisely placed nail positions — ready for STL export and 3D printing.

## Features

- **Font to SVG** — Extract any letter from any installed system font (TTF/OTF) or custom font file
- **Mesh model** — Lightweight mesh of hollow cylinders at nail positions, connected by bars to nearest neighbors
- **2D plan view** — Generate top-down blueprints showing nail+bar layout
- **Auto-strategy per subpath** — Subpaths with real curves keep all segment junctions; subpaths with only straight or near-straight segments use corner-only detection
- **Subpath-aware** — Outer contours and inner holes (counters) each get independent nail distributions
- **Batch processing** — Generate models for all 26 letters (A–Z) in a single command
- **OpenSCAD import** — SVG is imported natively by OpenSCAD, preserving full bezier precision; nail positions align perfectly with the letter geometry

## Pipeline Overview

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────┐     ┌──────────┐
│  Font file   │ ──▶ │ font_to_svg  │ ──▶ │ svg_to_mesh_      │ ──▶ │ OpenSCAD │ ──▶ STL
│  (TTF/OTF)   │     │  (.py)       │     │ openscad.py       │     │  CLI     │
└─────────────┘     └──────────────┘     └────────────────────┘     └──────────┘
                           │                       │
                           ▼                       ▼
                      letter_A.svg          mesh_A.scad
```

## Installation

### Requirements

- Python 3.12+
- [OpenSCAD](https://openscad.org) — optional, only for STL rendering

### Setup

```bash
git clone https://github.com/yourusername/string-art.git
cd string-art
make install
```

This installs: `svgwrite`, `svgpathtools`, `fonttools`, `numpy`, `pytest`.

## Usage

### Quick start

```bash
make mesh-example
```

Generates a letter J mesh model (SCAD + optional STL).
Use `make plan-example` for a 2D nail plan blueprint.

### Step by step

#### 1. Generate an SVG outline of a letter

```bash
# Filled shape (default) — for 3D model generation
python3 src/font_to_svg.py --letter A --font Arial --output letter_A.svg

# Outline mode — for visualization
python3 src/font_to_svg.py --letter A --font Arial --outline --output letter_A_outline.svg

# Use a custom font file
python3 src/font_to_svg.py --letter B --font-file /path/to/font.ttf --output letter_B.svg
```

#### 2. Generate a 3D model (OpenSCAD)

**Mesh model (hollow cylinders connected by bars):**
```bash
python3 src/svg_to_mesh_openscad.py \
    --input letter_A.svg \
    --hole-diameter 5 \
    --wall-thickness 1 \
    --thickness 5 \
    --max-spacing 40 \
    --output mesh_A.scad
```

**2D nail plan SVG (blueprint view):**
```bash
python3 src/svg_to_nail_plan_svg.py \
    --input letter_A.svg \
    --hole-diameter 3 \
    --max-spacing 40 \
    --output plan_A.svg
```

#### 3. Render to STL

```bash
openscad -o mesh_A.stl mesh_A.scad
```

The Makefile auto-detects OpenSCAD on macOS (`/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD`) and PATH.

### Shell wrappers

```bash
./scripts/generate_svg.sh --letter A --font Arial --output letter_A.svg
./scripts/generate_scad_stl.sh --input letter_A.svg --hole-diameter 5 --thickness 5 --stl
./scripts/generate_plan_svg.sh --input letter_A.svg --hole-diameter 3 --output plan_A.svg
```

## Nail Placement

Each closed subpath (contour) gets nails at its segment junctions. Subpaths with real curves (arc/chord ratio > 1.01, e.g. letter B's lobes) keep all segment junctions; subpaths with only straight or near-straight segments use corner-only detection (angle > 30°).

Use `--max-spacing` to control nail density. When set (default 40mm), must-have corner/junction nails are always included, and any gap between consecutive nails exceeding the threshold is subdivided with evenly-spaced intermediate nails. Pass 0 to disable gap-filling and use junction-only placement.

For small subpaths (whiskers, small ovals), a minimum of 3 nails is enforced to ensure the shape is represented.

## Batch Processing

Generate models for any set of letters in one command:

```bash
# Mesh models for A-Z (default)
python3 scripts/batch_generate.py

# 2D plan SVGs for specific letters
python3 scripts/batch_generate.py --plan --letters A B C --plan-hole-diameter 4

# Mesh models with custom parameters
python3 scripts/batch_generate.py --mesh --letters A B C --stl-hole-diameter 5 --wall-thickness 1

# Skip STL rendering
python3 scripts/batch_generate.py --skip-stl
```

Makefile shortcuts:
```bash
make mesh-batch  # mesh models for A-Z
make plan-batch  # plan SVGs for A-Z
make all-batch   # both mesh + plan for A-Z
```

Output goes to `output/` by default (gitignored).

## Project Structure

```
src/
  font_to_svg.py            # Letter → SVG outline
  svg_to_mesh_openscad.py   # SVG → OpenSCAD mesh model
  svg_to_nail_plan_svg.py   # SVG → 2D nail plan blueprint
  string_art_utils.py       # Font lookup, glyph extraction, nail geometry, paths
scripts/
  generate_svg.sh           # Shell wrapper: font → SVG
  generate_scad_stl.sh      # Shell wrapper: SVG → mesh SCAD (+ optional STL)
  generate_plan_svg.sh      # Shell wrapper: SVG → nail plan SVG
  batch_generate.py         # Batch processing for multiple letters
tests/
  test_font_to_svg.py
  test_svg_to_openscad.py
  test_data/                # Test fixture SVGs
Makefile                    # install, test, lint, example, batch targets
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `svgwrite` | SVG output generation |
| `svgpathtools` | SVG path parsing and geometry |
| `fonttools` | Font-to-glyph extraction (TTF/OTF) |
| `numpy` | Numerical operations |
| `pytest` | Test framework |
| OpenSCAD | (optional) STL rendering |

## Testing

```bash
make test       # pytest
make lint       # Python syntax checks
```

## How It Works

Nail positions are computed in the SVG's native coordinate space using `svgpathtools`. Each closed subpath (contour) gets nails at its segment junctions — corner-only for straight subpaths, all junctions for curved subpaths. The `--max-spacing` option subdivides gaps larger than the threshold with evenly-spaced intermediate nails. The SCAD file imports the SVG directly — OpenSCAD's `import()` handles the SVG coordinate system natively, so no Y-flip or coordinate transformation is needed. The mesh model places hollow cylinders at each nail position connected by bars to their nearest neighbors.

## License

MIT