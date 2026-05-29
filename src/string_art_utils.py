import math
import os
from pathlib import Path


MAC_FONT_DIRS = [
    "/System/Library/Fonts",
    "/Library/Fonts",
    os.path.expanduser("~/Library/Fonts"),
]


def system_font_path(font_name):
    if os.path.isfile(font_name):
        return font_name

    name_lower = font_name.lower()
    best = None

    def match(ext):
        return ext in (".ttf", ".otf", ".ttc")

    for font_dir in MAC_FONT_DIRS:
        if not os.path.isdir(font_dir):
            continue
        for f in sorted(os.listdir(font_dir)):
            f_lower = f.lower()
            ext = Path(f).suffix.lower()
            if ext not in (".ttf", ".otf", ".ttc"):
                continue
            stem = Path(f).stem.lower()
            if stem == name_lower or f_lower.startswith(name_lower):
                full = os.path.join(font_dir, f)
                if ext in (".ttf", ".otf"):
                    return full
                best = full

    if best is None:
        for font_dir in MAC_FONT_DIRS:
            if not os.path.isdir(font_dir):
                continue
            for f in sorted(os.listdir(font_dir)):
                f_lower = f.lower()
                ext = Path(f).suffix.lower()
                if ext not in (".ttf", ".otf", ".ttc"):
                    continue
                if name_lower in f_lower:
                    full = os.path.join(font_dir, f)
                    if ext in (".ttf", ".otf"):
                        return full
                    best = full

    if best is None:
        try:
            import subprocess

            family_result = subprocess.run(
                ["fc-match", "--format=%{family}", font_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            fc_family = family_result.stdout.strip().lower()
            name_normalized = font_name.lower().replace(" ", "")
            family_normalized = fc_family.replace(" ", "")
            if (
                name_normalized not in family_normalized
                and font_name.lower() not in fc_family
            ):
                fc_family = ""  # fc-match returned a fallback, not a real match

            result = subprocess.run(
                ["fc-match", "--format=%{file}", font_name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            fc_path = result.stdout.strip()
            if (
                fc_family
                and fc_path
                and os.path.isfile(fc_path)
                and fc_path != "/dev/null"
                and not fc_path.endswith(".pcf.gz")
            ):
                return fc_path
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    if best is not None:
        return best

    raise FileNotFoundError(
        f"Font '{font_name}' not found in system font directories. "
        "Use --font-file to specify a direct path."
    )


def _open_font(font_path):
    from fontTools.ttLib import TTFont

    try:
        return TTFont(font_path)
    except Exception:
        pass
    for font_num in range(32):
        try:
            return TTFont(font_path, fontNumber=font_num)
        except (ValueError, IndexError, Exception):
            continue
    raise ValueError(f"Could not open any font in collection: {font_path}")


def glyph_to_svg_path(letter, font_path, canvas_w=170, canvas_h=170, padding=0.1):
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.misc.transform import Transform

    font = _open_font(font_path)
    cmap = font.getBestCmap()
    glyph_name = cmap.get(ord(letter))
    if glyph_name is None:
        raise ValueError(f"Character '{letter}' not found in font")

    glyph_set = font.getGlyphSet()
    glyph = glyph_set[glyph_name]

    bounds_pen = BoundsPen(glyph_set)
    glyph.draw(bounds_pen)
    if bounds_pen.bounds is None:
        raise ValueError(f"Character '{letter}' has no visible outline")
    xmin, ymin, xmax, ymax = bounds_pen.bounds

    glyph_w = xmax - xmin
    glyph_h = ymax - ymin
    if glyph_w < 0.001 or glyph_h < 0.001:
        raise ValueError(f"Character '{letter}' has zero width or height")

    glyph_cx = (xmin + xmax) / 2
    glyph_cy = (ymin + ymax) / 2

    avail_w = canvas_w * (1 - 2 * padding)
    avail_h = canvas_h * (1 - 2 * padding)
    scale = min(avail_w / glyph_w, avail_h / glyph_h)

    # fonttools composes right-to-left, so list operations from last to first
    transform = Transform()
    transform = transform.translate(canvas_w / 2, canvas_h / 2)
    transform = transform.scale(scale, -scale)
    transform = transform.translate(-glyph_cx, -glyph_cy)

    svg_pen = SVGPathPen(glyph_set)
    tpen = TransformPen(svg_pen, transform)
    glyph.draw(tpen)
    path_d = svg_pen.getCommands()

    return path_d, scale
