# AGENTS.md — Instructions for AI Assistants

String art nail template toolchain. See README.md for user-facing docs.

## Project Structure

```
src/
  font_to_svg.py            # letter → SVG outline
  svg_to_mesh_openscad.py   # SVG → OpenSCAD mesh (hollow cyls + bars)
  svg_to_nail_plan_svg.py   # SVG → 2D blueprint SVG
  string_art_utils.py       # Font lookup, glyph extraction, paths, nail geometry
scripts/
  generate_svg.sh           # Shell wrapper for font_to_svg.py
  generate_scad_stl.sh      # Shell wrapper for svg_to_mesh_openscad.py (+ STL)
  batch_generate.py         # Batch processing for multiple letters
tests/
  test_font_to_svg.py
  test_svg_to_openscad.py  # Nail geometry, subpaths, corner detection
  test_data/                # Test fixture SVGs
Makefile                    # install, test, lint, example, batch targets
AGENTS.md                   # This file — instructions for AI assistants
README.md                   # User-facing documentation
```

## Design Decisions — AI-relevant

- **Mesh and Plan tools accept any SVG**, not just output from Tool 1. Nail positions
  are computed in the SVG's native coordinate space via `svgpathtools`, and
  OpenSCAD's `import()` preserves this same space — alignment is guaranteed.
- **No Y-flip**: SVG coordinate space (Y-down) is preserved directly in SCAD.
  OpenSCAD's `import()` handles SVG natively. Nail hole coordinates use raw SVG y.
- **Nail placement is per-subpath** — each closed contour gets independent nail
  distribution based on its own perimeter length and the spacing parameter.
- **Nails are placed directly on the path** — no inward offset is applied (see below).
- **Default output is filled**: `fill="black" fill-rule="evenodd"`. Pass `--outline`
  for `fill="none" stroke="black"`.

## Nail Offset Algorithm (disabled)

`offset_nails_inward()` in `src/string_art_utils.py` is a no-op — nails are placed
directly on the path. The function is kept as a placeholder for future implementation.

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

## Testing

```bash
make test        # pytest (36 tests)
make lint        # Python syntax check
make example     # A → SVG → SCAD → STL
```

Test coverage: font lookup, glyph extraction, canvas-space coords, SVG parsing,
corner detection, nail positions (strategy 1 & 2), spacing, subpath splitting,
signed area (winding), offset containment, integration tests (square, letter O),
outline mode.
