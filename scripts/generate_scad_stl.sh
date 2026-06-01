#!/bin/bash
# generate_scad_stl.sh — Convert SVG outline to OpenSCAD mesh model and optionally render STL
#
# Usage:
#   ./scripts/generate_scad_stl.sh --input letter_A.svg --spacing 10 --hole-diameter 5 --output mesh.scad
#
# Optional: pass --stl to also render an STL via the OpenSCAD CLI:
#   ./scripts/generate_scad_stl.sh --input letter_A.svg --spacing 10 --hole-diameter 5 --wall-thickness 1 --stl
#
# Arguments (--spacing, --hole-diameter, --wall-thickness, --thickness, --corner-strategy)
# are forwarded to src/svg_to_mesh_openscad.py.
# See `python3 src/svg_to_mesh_openscad.py --help` for full options.

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

python3 "$SCRIPT_DIR/../src/svg_to_mesh_openscad.py" "${POSITIONAL_ARGS[@]}"

if $RENDER_STL; then
    SCAD_FILE=""
    for i in "${!POSITIONAL_ARGS[@]}"; do
        if [[ "${POSITIONAL_ARGS[$i]}" == "--output" ]] && [[ $((i + 1)) -lt ${#POSITIONAL_ARGS[@]} ]]; then
            SCAD_FILE="${POSITIONAL_ARGS[$((i + 1))]}"
            break
        fi
    done
    # If no --output was given, derive it the same way the Python script does
    if [[ -z "$SCAD_FILE" ]]; then
        for i in "${!POSITIONAL_ARGS[@]}"; do
            if [[ "${POSITIONAL_ARGS[$i]}" == "--input" ]] && [[ $((i + 1)) -lt ${#POSITIONAL_ARGS[@]} ]]; then
                INPUT_FILE="${POSITIONAL_ARGS[$((i + 1))]}"
                BASENAME="$(basename "$INPUT_FILE")"
                SCAD_FILE="${BASENAME%.*}.scad"
                break
            fi
        done
    fi
    # The Python tool always appends .scad; ensure we look for the right path
    if [[ -n "$SCAD_FILE" && "$SCAD_FILE" != *.scad ]]; then
        SCAD_FILE="${SCAD_FILE}.scad"
    fi

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
