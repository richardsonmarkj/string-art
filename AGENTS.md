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
  generate_plan_svg.sh      # Shell wrapper for svg_to_nail_plan_svg.py
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

- **`--max-spacing` uses proportional gap fill**: When `--max-spacing` is set
  (default 40mm), must-have nails are first computed using the auto-strategy (segment
  junctions for curves, corners for straight). Then any gap between consecutive
  must-haves that exceeds the threshold is subdivided evenly with `ceil(gap/spacing)`
  intervals. This ensures star tips, letter corners, etc. always get nails while
  preventing any gap from exceeding the target spacing. Without `--max-spacing`, the
  auto-junction strategy is used alone.
- **Minimum 3 nails per subpath**: If the computed result has fewer than 3 nails
  (e.g. tiny ovals, single-segment whiskers), 3 equidistant arc-length nails are
  placed instead.
- **Clustering threshold scales with path length**: `min(8, total * 0.15)` prevents
  over-merging on small subpaths while keeping 8mm for typical ~500mm letter perimeters.
- **Auto-detection per subpath**: Each subpath independently decides whether to
  use all segment junctions or only corners, based on whether it contains genuine
  curves (arc/chord ratio > 1.01). Letter A's inner triangle (font subdivisions
  masquerading as curves) gets only corner nails; letter B's lobes (real curves)
  keep all their segment junctions to preserve shape.
- **Mesh and Plan tools accept any SVG**, not just output from Tool 1. Nail positions
  are computed in the SVG's native coordinate space via `svgpathtools`, and
  OpenSCAD's `import()` preserves this same space — alignment is guaranteed.
- **No Y-flip**: SVG coordinate space (Y-down) is preserved directly in SCAD.
  OpenSCAD's `import()` handles SVG natively. Nail hole coordinates use raw SVG y.
- **Nail placement is per-subpath** — each closed contour gets independent nail
  distribution based on path segment junctions, with `--max-spacing` fill
  and minimum-3-nail enforcement for small subpaths.
- **Nails are placed directly on the path** — no inward offset is applied (see below).
- **Default output is filled**: `fill="black" fill-rule="evenodd"`. Pass `--outline`
  for `fill="none" stroke="black"`.
- **SVG ancestor `<g>` transforms are applied**: `svgpathtools.svg2paths()` does NOT
  apply ancestor `<g>` transforms (e.g. `transform="matrix(...)"` on a `<g>` element).
  `parse_svg_paths()` walks the XML ancestor chain via `_svg_ancestor_transforms()`,
  composes all transforms using `numpy` matrix multiplication, and applies them to
  each path via `_apply_matrix_to_path()`. This ensures nail positions are in the
  SVG's viewBox coordinate space, not the raw path coordinate space.

## Known Issues / Gotchas

- **svgpathtools t-parameters are arc-length-based, not segment-index-based**:
  `path.point(t)`, `path.length(t_a, t_b)`, etc. all use t as fraction of total
  arc length. `get_corner_vertices()` uses cumulative arc length: `cum / total`
  for junction t values, with clamping via `min(cum/total, 1.0)`.
- **Missing closing segment bug (fixed)**: `get_corner_vertices()` did not check
  the corner between the last segment and the first (wrap-around), so t=1.0 was
  never included in `must_have`. Fixed by: (1) wrapping `get_corner_vertices`
  index with `(i + 1) % n`, (2) always including t=1.0 in the must-have set,
  and (3) deduping the wrap-around duplicate point via first/last distance check
  in the cleaning step.
- **`svgpathtools.svg2paths()` ignores ancestor `<g>` transforms**: The library
  returns paths in their raw coordinate space, ignoring any `transform` attributes
  on parent `<g>` elements. `parse_svg_paths()` works around this by walking
  the XML tree and composing ancestor transforms manually. This is relevant when
  processing SVGs with scaled/positioned group elements (e.g. star.svg had a
  `<g transform="matrix(0.32,0,0,0.32,15.4,4.6)">` — without this fix, nail
  count was 310 instead of ~99).

## Testing

```bash
make test        # pytest
make lint        # Python syntax check
make mesh-example # A -> SVG -> SCAD -> STL (see also: plan-example)
```

Test coverage: font lookup, glyph extraction, canvas-space coords, SVG parsing,
corner detection, nail positions, subpath splitting, signed area (winding),
offset containment, integration tests (square, letter O), outline mode.