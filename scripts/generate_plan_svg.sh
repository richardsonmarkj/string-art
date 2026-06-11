#!/bin/bash
# generate_plan_svg.sh — Generate a 2D nail plan SVG from an SVG outline
#
# Usage:
#   ./scripts/generate_plan_svg.sh --input letter_A.svg --hole-diameter 3 --output plan_A.svg
#
# All arguments (e.g. --hole-diameter, --max-spacing) are forwarded to
# src/svg_to_nail_plan_svg.py.  See `python3 src/svg_to_nail_plan_svg.py
# --help` for full options.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/../src/svg_to_nail_plan_svg.py" "$@"
