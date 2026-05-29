#!/bin/bash
# generate_svg.sh — Generate an SVG outline of a single letter
#
# Usage:
#   ./scripts/generate_svg.sh --letter A --font Arial --output letter_A.svg
#   ./scripts/generate_svg.sh --letter B --font-file /path/to/font.ttf --output letter_B.svg
#   ./scripts/generate_svg.sh --letter C --font Arial --width 170 --height 170 --output letter_C.svg
#
# All arguments are forwarded to src/font_to_svg.py.
# See `python3 src/font_to_svg.py --help` for full options.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/../src/font_to_svg.py" "$@"
