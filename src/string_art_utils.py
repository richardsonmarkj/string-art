import math
import os
from pathlib import Path


MAC_FONT_DIRS = [
    "/System/Library/Fonts",
    "/Library/Fonts",
    "/Library/Fonts/Microsoft",
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
                and os.path.getsize(fc_path) > 0
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


# ── SVG Path Parsing & Nail Geometry (shared by svg_to_* tools) ──

import xml.etree.ElementTree as ET

import svgpathtools
import numpy as np
from svgpathtools.parser import parse_transform


CORNER_ANGLE_THRESHOLD = 30


def _apply_matrix_to_point(z, matrix):
    x, y = z.real, z.imag
    return complex(
        matrix[0, 0] * x + matrix[0, 1] * y + matrix[0, 2],
        matrix[1, 0] * x + matrix[1, 1] * y + matrix[1, 2],
    )


def _apply_matrix_to_path(path, matrix):
    new_segs = []
    for seg in path:
        if isinstance(seg, svgpathtools.Arc):
            for c in seg.as_cubic_curves():
                pts = c.bpoints()
                new_pts = [_apply_matrix_to_point(p, matrix) for p in pts]
                new_segs.append(svgpathtools.CubicBezier(*new_pts))
        else:
            pts = seg.bpoints()
            new_pts = [_apply_matrix_to_point(p, matrix) for p in pts]
            new_segs.append(type(seg)(*new_pts))
    return svgpathtools.Path(*new_segs)


def _svg_ancestor_transforms(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()

    results = []

    def _walk(node, transforms):
        tag = node.tag.split("}")[-1] if "}" in node.tag else node.tag
        t = node.get("transform")
        current = transforms + [t] if t else transforms
        if tag == "path":
            results.append((node, current))
        for child in node:
            _walk(child, current)

    _walk(root, [])
    return results


def parse_svg_paths(svg_path):
    paths, attributes = svgpathtools.svg2paths(svg_path)

    transforms_by_elem = {}
    for elem, t_strs in _svg_ancestor_transforms(svg_path):
        d = elem.get("d", "").strip()
        identity = np.eye(3)
        matrix = identity
        for t_str in t_strs:
            m = parse_transform(t_str)
            matrix = m @ matrix
        transforms_by_elem[d] = matrix if not np.allclose(matrix, identity) else None

    path_data = []
    for i, (path, attrs) in enumerate(zip(paths, attributes)):
        d = attrs.get("d", "")
        matrix = transforms_by_elem.get(d)
        if matrix is not None:
            path = _apply_matrix_to_path(path, matrix)
        path_data.append(
            {
                "path": path,
                "fill": attrs.get("fill", ""),
                "fill_rule": attrs.get("fill-rule", attrs.get("fillRule", "nonzero")),
                "id": attrs.get("id", f"path_{i}"),
            }
        )
    return path_data


def is_corner(prev_seg, next_seg, threshold=CORNER_ANGLE_THRESHOLD):
    if prev_seg.length() < 0.001 or next_seg.length() < 0.001:
        return False
    try:
        d1 = prev_seg.derivative(1)
        if abs(d1) < 1e-10:
            return True
        t1 = d1 / abs(d1)

        d2 = next_seg.derivative(0)
        if abs(d2) < 1e-10:
            return True
        t2 = d2 / abs(d2)

        dot = t1.real * t2.real + t1.imag * t2.imag
        cos_a = max(-1.0, min(1.0, dot))
        angle = math.degrees(math.acos(cos_a))
        return angle > threshold
    except (ZeroDivisionError, ValueError):
        return True


def get_corner_vertices(path):
    n = len(path)
    total = path.length()
    cum = 0.0
    vertices = []
    for i, seg in enumerate(path):
        t = cum / total
        if i == 0:
            vertices.append((t, True))
        cum += seg.length()
        next_seg = path[(i + 1) % n]
        vertices.append((min(cum / total, 1.0), is_corner(seg, next_seg)))
    return vertices


def _build_arc_table(path, samples_per_mm=4):
    total = path.length()
    table = [(0.0, path.point(0).real, path.point(0).imag)]
    cum = 0.0
    for seg in path:
        seg_len = seg.length()
        n = max(2, int(seg_len * samples_per_mm))
        for i in range(1, n + 1):
            local_t = i / n
            pt = seg.point(local_t)
            arc = cum + seg.length(0, local_t)
            table.append((arc, pt.real, pt.imag))
        cum += seg_len
    table[-1] = (total, path.point(1).real, path.point(1).imag)
    return table


def _point_from_arc(arc_table, target_arc):
    if target_arc <= arc_table[0][0]:
        return arc_table[0][1], arc_table[0][2]
    if target_arc >= arc_table[-1][0]:
        return arc_table[-1][1], arc_table[-1][2]
    lo, hi = 0, len(arc_table) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if arc_table[mid][0] <= target_arc:
            lo = mid
        else:
            hi = mid
    a0, x0, y0 = arc_table[lo]
    a1, x1, y1 = arc_table[hi]
    if a1 - a0 < 1e-10:
        return x0, y0
    f = (target_arc - a0) / (a1 - a0)
    return x0 + f * (x1 - x0), y0 + f * (y1 - y0)


def _seg_intervals(path):
    intervals = []
    cum = 0.0
    n = len(path)
    for i, seg in enumerate(path):
        seg_len = seg.length()
        is_line = isinstance(seg, svgpathtools.Line)
        if is_line:
            prev_is_curve = not isinstance(path[(i - 1) % n], svgpathtools.Line)
            next_is_curve = not isinstance(path[(i + 1) % n], svgpathtools.Line)
            if prev_is_curve and next_is_curve:
                is_line = False
        intervals.append((cum, cum + seg_len, is_line))
        cum += seg_len
    return intervals


def compute_nail_positions(path, spacing, strategy, hole_diameter=0):
    total = path.length()
    if total < 0.01:
        return []

    arc_table = _build_arc_table(path)
    effective_spacing = spacing + hole_diameter

    if strategy == 1:
        vertices = get_corner_vertices(path)
    else:
        cum = 0.0
        vertices = []
        for seg in path:
            vertices.append((cum / total, True))
            cum += seg.length()
        vertices.append((1.0, True))

    must_have_ts = sorted({t for t, is_c in vertices if is_c})
    if 1.0 not in must_have_ts:
        must_have_ts.append(1.0)

    must_have_arcs = []
    for t in must_have_ts:
        x, y = _point_from_arc(arc_table, t * total)
        must_have_arcs.append((t * total, x, y, t))

    intervals = _seg_intervals(path)
    curve_spacing = spacing * 0.5 + hole_diameter
    straight_spacing = effective_spacing

    raw = []
    for i, (arc_a, x_a, y_a, t_a) in enumerate(must_have_arcs):
        raw.append((x_a, y_a, t_a))
        if i < len(must_have_arcs) - 1:
            arc_b = must_have_arcs[i + 1][0]
            if abs(arc_b - arc_a) < 1e-10:
                continue

            local = []
            for start, end, is_straight in intervals:
                if end <= arc_a:
                    continue
                if start >= arc_b:
                    break
                seg_start = max(start, arc_a)
                seg_end = min(end, arc_b)
                if seg_end - seg_start > 1e-10:
                    local.append((seg_start, seg_end, is_straight))

            total_in_seg = 0
            for seg_start, seg_end, is_straight in local:
                seg_arc_len = seg_end - seg_start
                s = straight_spacing if is_straight else curve_spacing
                num = max(0, int(seg_arc_len / s + 0.5) - 1)
                for j in range(1, num + 1):
                    target_arc = seg_start + seg_arc_len * j / (num + 1)
                    x, y = _point_from_arc(arc_table, target_arc)
                    raw.append((x, y, 0.0))
                total_in_seg += num

            interval_len = arc_b - arc_a
            if total_in_seg == 0 and interval_len > 2 * spacing:
                target_arc = (arc_a + arc_b) / 2
                x, y = _point_from_arc(arc_table, target_arc)
                raw.append((x, y, 0.0))

    cleaned = []
    for x, y, t in raw:
        if cleaned:
            lx, ly, _ = cleaned[-1]
            if math.hypot(x - lx, y - ly) < 0.5:
                continue
        cleaned.append((x, y, t))

    if len(cleaned) > 1:
        fx, fy, _ = cleaned[0]
        lx, ly, _ = cleaned[-1]
        if math.hypot(lx - fx, ly - fy) < 0.5:
            cleaned.pop()

    return cleaned


def _split_subpaths(path):
    subpaths = []
    current = []
    for i, seg in enumerate(path):
        current.append(seg)
        if i < len(path) - 1:
            if abs(seg.end - path[i + 1].start) > 1e-6:
                subpaths.append(svgpathtools.Path(*current))
                current = []
    if current:
        subpaths.append(svgpathtools.Path(*current))
    return subpaths, [len(sp) for sp in subpaths]


def _signed_area(subpath):
    area = 0.0
    samples_per_seg = 16
    for seg in subpath:
        seg_len = seg.length() if hasattr(seg, "length") else 1.0
        n = max(samples_per_seg, int(seg_len / 2))
        for i in range(n):
            t1 = i / n
            t2 = (i + 1) / n
            p1 = seg.point(t1)
            p2 = seg.point(t2)
            area += p1.real * p2.imag - p2.real * p1.imag
    return area


def offset_nails_inward(nails_with_t, path=None, hole_diameter=None, all_subpaths=None):
    return [(x, y) for x, y, t in nails_with_t]


def relative_svg_path(svg_path, scad_path):
    svg_abs = os.path.abspath(svg_path)
    scad_dir = os.path.dirname(os.path.abspath(scad_path))
    try:
        return os.path.relpath(svg_abs, scad_dir)
    except ValueError:
        return svg_abs


def svg_canvas_height(svg_path):
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        viewbox = root.get("viewBox")
        if viewbox:
            parts = viewbox.strip().split()
            if len(parts) == 4:
                return float(parts[3])
    except Exception:
        pass
    return None
