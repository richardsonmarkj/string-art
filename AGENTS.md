# AGENTS.md — Instructions for AI Assistants

This is a string art nail template toolchain project. It converts letters to SVG
outlines, then to OpenSCAD 3D models with nail placement holes for 3D printing.

## Project Structure

```
src/
  font_to_svg.py        # Tool 1: letter → SVG outline
  svg_to_openscad.py    # Tool 2: SVG → OpenSCAD 3D template
  string_art_utils.py   # Shared utilities (font lookup, glyphs, transforms)
scripts/
  generate_svg.sh       # Shell wrapper for Tool 1
  generate_scad_stl.sh  # Shell wrapper for Tool 2 (optionally renders STL)
tests/
  test_font_to_svg.py   # Tests for Tool 1
  test_svg_to_openscad.py  # Tests for Tool 2
  test_data/            # Test fixture SVGs
Makefile                # Convenience targets: install, test, clean, example (renders STL)
AGENTS.md               # This file — instructions for AI assistants
```

## Key Design Decisions

- **Tool 2 accepts any SVG**, not just output from Tool 1. Nail positions are computed
  in the SVG's native coordinate space via `svgpathtools`, and OpenSCAD's `import()`
  preserves this same space — so alignment is guaranteed.
- **Both corner strategies** are implemented (1=corners-first, 2=all-vertices).
- **fonttools** is used for font-to-glyph extraction (supports TTF and OTF).
- **svgwrite** generates clean SVG output.
- **svgpathtools** parses SVG paths for nail position computation.
- Import approach: SCAD uses `import("file.svg")` for the letter shape, preserving
  full bezier precision; nail holes are placed at matching coordinates.
- **No Y-flip**: SVG coordinate space (Y-down) is preserved directly in SCAD —
  OpenSCAD's `import()` handles SVG natively. Nail hole coordinates use raw SVG y.
- **Nail placement is per-subpath** — each closed contour (outer, inner hole/counter)
  gets its own independent nail distribution based on its own perimeter length and
  the spacing parameter. This produces complete circles on each contour.
- **Nails are placed directly on the path** — no inward offset is applied.
- **Default output is filled** — Tool 1 renders SVG with `fill="black" fill-rule="evenodd"`
  by default. Pass `--outline` to get `fill="none" stroke="black"` for visualization.

## Nail Offset Algorithm (disabled)

`offset_nails_inward()` in `src/svg_to_openscad.py` is a no-op — nails are placed
directly on the path (no inward offset). The function is kept as a placeholder for
future implementation.

## Testing

```bash
make test        # runs pytest (36 tests)
make lint        # Python syntax check
make example     # generates a quick A → SVG → SCAD → STL example
```

## Current State (36 passing tests)

All tests pass. Key test coverage:
- Font lookup, glyph extraction, canvas-space coordinates (Tool 1)
- SVG parsing, corner detection, nail positions (strategy 1 & 2), spacing
- Subpath splitting, signed area (winding detection), offset containment
- Integration tests: end-to-end square, letter O with strategy 2
- Outline mode for SVG generation

## Known Issues / Gotchas

- **`Path.unit_tangent(t)` in svgpathtools uses a polyline approximation** that
  disagrees with `path.point(t)` which uses segment-based parameterization.
  The tangent computation in `offset_nails_inward` was replaced with a direction
  search (8 uniform directions) that avoids tangent computation entirely.
  (This function is no longer used but the issue remains.)
- **svgpathtools t-parameters are arc-length-based, not segment-index-based**:
  `path.point(t)`, `path.length(t_a, t_b)`, etc. all use t as fraction of total
  arc length. `get_corner_vertices()` and strategy 2 vertex computation both
  originally used `i / n` (segment-index-based), which gave wrong positions
  whenever segment lengths were unequal. Fixed by computing cumulative arc
  length: `cum / total` for junction t values, with clamping via
  `min(cum/total, 1.0)`.
- **Missing closing segment bug (fixed)**: `get_corner_vertices()` did not check
  the corner between the last segment and the first (wrap-around), so t=1.0 was
  never included in `must_have`. And `compute_nail_positions` didn't ensure t=1.0
  was present for the closing fill segment. This meant the last segment of each
  subpath (from the last corner/pin to the start) got no intermediate nails,
  producing incomplete contours (e.g., letter A was missing ~60mm of the right
  leg). Fixed by: (1) wrapping `get_corner_vertices` index with `(i + 1) % n`,
  (2) always including t=1.0 in `must_have` in `compute_nail_positions`, and
  (3) deduping the wrap-around duplicate point via first/last distance check in
  the cleaning step. Letter A nail count went from 59 to 66 with the previously
  missing right-leg section now properly populated.

## Full Pipeline

```bash
# Step 1: Generate SVG (filled, for template generation)
python3 src/font_to_svg.py --letter A --font Arial --output letter_A.svg

# Step 1b: Generate SVG (outline, for visualization)
python3 src/font_to_svg.py --letter A --font Arial --outline --output letter_A_outline.svg

# Step 2: Generate SCAD
python3 src/svg_to_openscad.py \
    --input letter_A.svg \
    --spacing 10 \
    --hole-diameter 8 \
    --thickness 5 \
    --corner-strategy 1 \
    --output template.scad

# Step 3: Render STL
openscad -o template.stl template.scad
```

## Dependencies

- Python 3.12+
- svgwrite, svgpathtools, fonttools, numpy, pytest
- OpenSCAD (for STL rendering, not required for SVG/SCAD generation)
