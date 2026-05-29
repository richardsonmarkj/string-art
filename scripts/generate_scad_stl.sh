#!/bin/bash
# generate_scad_stl.sh — Convert SVG outline to OpenSCAD and optionally render STL
#
# Usage:
#   ./scripts/generate_scad_stl.sh --input letter_A.svg --spacing 10 --hole-diameter 8 --output template.scad
#
# Optional: pass --stl to also render an STL via the OpenSCAD CLI:
#   ./scripts/generate_scad_stl.sh --input letter_A.svg --spacing 10 --hole-diameter 8 --stl
#
# All other arguments (--spacing, --hole-diameter, --thickness, --corner-strategy)
# are forwarded to src/svg_to_openscad.py.
# See `python3 src/svg_to_openscad.py --help` for full options.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

RENDER_STL=false
POSITIONAL_ARGS=()

for arg in "$@"; do
    case "$arg" in
        --stl)
            RENDER_STL=true
            ;;
        *)
            POSITIONAL_ARGS+=("$arg")
            ;;
    esac
done

python3 "$SCRIPT_DIR/../src/svg_to_openscad.py" "${POSITIONAL_ARGS[@]}"

if $RENDER_STL; then
    # Extract output file from positional args
    SCAD_FILE=""
    for i in "${!POSITIONAL_ARGS[@]}"; do
        if [[ "${POSITIONAL_ARGS[$i]}" == "--output" ]] && [[ $((i + 1)) -lt ${#POSITIONAL_ARGS[@]} ]]; then
            SCAD_FILE="${POSITIONAL_ARGS[$((i + 1))]}"
            break
        fi
    done

    # Find OpenSCAD CLI — check PATH first, then macOS App bundle
    OPENSCAD=""
    if command -v openscad &>/dev/null; then
        OPENSCAD="openscad"
    elif [ -x "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD" ]; then
        OPENSCAD="/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD"
    fi

    if [ -n "$SCAD_FILE" ] && [ -n "$OPENSCAD" ]; then
        STL_FILE="${SCAD_FILE%.scad}.stl"
        echo "Rendering STL: $STL_FILE"
        "$OPENSCAD" -o "$STL_FILE" "$SCAD_FILE"
        echo "STL saved to $STL_FILE"
    elif [ -z "$OPENSCAD" ]; then
        echo "Warning: OpenSCAD not found. Install from https://openscad.org or render manually."
    fi
fi
