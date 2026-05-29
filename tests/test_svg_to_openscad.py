import math
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from svg_to_openscad import (
    parse_svg_paths,
    is_corner,
    get_corner_vertices,
    compute_nail_positions,
    _split_subpaths,
    _signed_area,
    offset_nails_inward,
    generate_scad,
)
from svgpathtools import Path, Line, CubicBezier, QuadraticBezier


TEST_DATA = os.path.join(os.path.dirname(__file__), "test_data")


def load_svg(basename):
    return os.path.join(TEST_DATA, basename)


class TestParseSvgPaths:
    def test_square_has_one_path(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        assert len(path_data) == 1

    def test_letter_o_has_one_path_with_two_contours(self):
        path_data = parse_svg_paths(load_svg("letter_O_outline.svg"))
        assert len(path_data) == 1
        assert len(path_data[0]["path"]) == 8  # 4 sides + 4 sides = 8 segments

    def test_empty_svg_has_no_paths(self):
        path_data = parse_svg_paths(load_svg("empty.svg"))
        assert len(path_data) == 0

    def test_polygon_is_parsed(self):
        path_data = parse_svg_paths(load_svg("polygon.svg"))
        assert len(path_data) >= 1


class TestIsCorner:
    def test_orthogonal_lines_are_corners(self):
        l1 = Line(0 + 0j, 10 + 0j)
        l2 = Line(10 + 0j, 10 + 10j)
        assert is_corner(l1, l2, threshold=10)

    def test_collinear_lines_not_corners(self):
        l1 = Line(0 + 0j, 10 + 0j)
        l2 = Line(10 + 0j, 20 + 0j)
        assert not is_corner(l1, l2, threshold=10)

    def test_gentle_curve_not_corner(self):
        cb1 = CubicBezier(0 + 0j, 5 + 2j, 15 + 2j, 20 + 0j)
        cb2 = CubicBezier(20 + 0j, 25 + -2j, 35 + -2j, 40 + 0j)
        assert not is_corner(cb1, cb2, threshold=30)


class TestComputeNailPositions:
    def test_square_strategy1_has_at_least_4_nails(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        nails = compute_nail_positions(path_data[0]["path"], 10, strategy=1)
        assert len(nails) >= 4

    def test_square_nails_are_on_path(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        path = path_data[0]["path"]
        nails = compute_nail_positions(path, 10, strategy=1)
        for x, y, t in nails:
            pt = complex(x, y)
            min_dist = min(
                abs(pt - path.point(t_)) for t_ in [i / 1000 for i in range(1001)]
            )
            assert min_dist < 0.5, (
                f"Nail ({x:.1f}, {y:.1f}) is {min_dist:.2f} from path"
            )

    def test_strategies_differ_for_square(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        nails1 = compute_nail_positions(path_data[0]["path"], 15, strategy=1)
        nails2 = compute_nail_positions(path_data[0]["path"], 15, strategy=2)
        assert len(nails2) >= len(nails1)

    def test_spacing_is_respected(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        nails = compute_nail_positions(path_data[0]["path"], 20, strategy=1)
        for i in range(1, len(nails)):
            x1, y1, _ = nails[i - 1]
            x2, y2, _ = nails[i]
            dist = math.hypot(x2 - x1, y2 - y1)
            assert dist <= 25, f"Distance {dist:.1f} > 25 between consecutive nails"


class TestGenerateScad:
    def test_scad_contains_expected_keywords(self):
        nails_1 = [(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)]
        nails_2 = [
            (10.0, 10.0),
            (50.0, 10.0),
            (90.0, 10.0),
            (90.0, 50.0),
            (90.0, 90.0),
            (50.0, 90.0),
            (10.0, 90.0),
            (10.0, 50.0),
        ]
        scad = generate_scad(
            svg_path="/tmp/test.svg",
            nail_positions_1=nails_1,
            nail_positions_2=nails_2,
            hole_diameter=8,
            thickness=5,
            default_strategy=1,
            scad_path="/tmp/output.scad",
            canvas_height=100,
        )
        assert "module letter_outline()" in scad
        assert "module nail_holes_strategy1()" in scad
        assert "module nail_holes_strategy2()" in scad
        assert "module nail_holes()" in scad
        assert "difference()" in scad
        assert "linear_extrude" in scad
        assert "cylinder" in scad
        assert "import(" in scad
        assert "thickness = 5" in scad
        assert "hole_d = 8" in scad
        assert "corner_strategy = 1" in scad

    def test_scad_has_correct_number_of_holes(self):
        nails_1 = [(10.0, 10.0), (20.0, 20.0)]
        nails_2 = [(30.0, 30.0), (40.0, 40.0)]
        scad = generate_scad(
            "/tmp/test.svg",
            nails_1,
            nails_2,
            8,
            5,
            2,
            "/tmp/output.scad",
            canvas_height=100,
        )
        count = scad.count("cylinder")
        assert count == len(nails_1) + len(nails_2), (
            f"Expected {len(nails_1) + len(nails_2)} cylinders, found {count}"
        )


class TestSplitSubpaths:
    def test_single_subpath(self):
        path = Path(Line(0 + 0j, 10 + 0j), Line(10 + 0j, 10 + 10j))
        subpaths, counts = _split_subpaths(path)
        assert len(subpaths) == 1
        assert counts == [2]

    def test_two_subpaths_letter_o(self):
        path_data = parse_svg_paths(load_svg("letter_O_outline.svg"))
        subpaths, counts = _split_subpaths(path_data[0]["path"])
        assert len(subpaths) == 2
        assert counts == [4, 4]

    def test_each_subpath_is_closed(self):
        path_data = parse_svg_paths(load_svg("letter_O_outline.svg"))
        subpaths, _ = _split_subpaths(path_data[0]["path"])
        for sp in subpaths:
            assert abs(sp[0].start - sp[-1].end) < 1e-6, "Subpath not closed"


class TestSignedArea:
    def test_clockwise_positive(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        subpaths, _ = _split_subpaths(path_data[0]["path"])
        area = _signed_area(subpaths[0])
        assert area > 0, f"Expected positive area for clockwise square, got {area}"

    def test_inner_contour_negative(self):
        path_data = parse_svg_paths(load_svg("letter_O_outline.svg"))
        subpaths, _ = _split_subpaths(path_data[0]["path"])
        # Inner contour is the second subpath
        assert len(subpaths) == 2
        area_inner = _signed_area(subpaths[1])
        assert area_inner < 0, (
            f"Expected negative area for inner contour, got {area_inner}"
        )

    def test_outer_positive_inner_negative(self):
        path_data = parse_svg_paths(load_svg("letter_O_outline.svg"))
        subpaths, _ = _split_subpaths(path_data[0]["path"])
        area_outer = _signed_area(subpaths[0])
        area_inner = _signed_area(subpaths[1])
        assert area_outer > 0
        assert area_inner < 0


class TestOffsetNailsInward:
    def test_offset_returns_original_positions(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        path = path_data[0]["path"]
        nails = compute_nail_positions(path, 20, strategy=1)
        assert len(nails) > 0

        raw_points = [(x, y) for x, y, t in nails]
        offset = offset_nails_inward(nails, path, hole_diameter=8)

        for i, (ox, oy) in enumerate(offset):
            rx, ry = raw_points[i]
            assert (ox, oy) == (rx, ry), f"Nail {i} was moved (should be on edge)"

    def test_outer_nails_are_raw_positions(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        path = path_data[0]["path"]
        nails = compute_nail_positions(path, 50, strategy=1)
        offset = offset_nails_inward(nails, path, hole_diameter=8)

        raw_flat = [(x, y) for x, y, t in nails]
        assert offset == raw_flat, "Offset should return raw nail positions unchanged"

    def test_inner_nails_are_raw_positions(self):
        path_data = parse_svg_paths(load_svg("letter_O_outline.svg"))
        path = path_data[0]["path"]
        nails = compute_nail_positions(path, 15, strategy=1)

        inner_nails = [(x, y, t) for x, y, t in nails if 25 < x < 75 and 25 < y < 75]
        assert len(inner_nails) >= 2, (
            f"Expected ≥2 nails on inner contour, got {len(inner_nails)}"
        )

        offset = offset_nails_inward(inner_nails, path, hole_diameter=8)
        raw_flat = [(x, y) for x, y, t in inner_nails]
        assert offset == raw_flat, "Offset should return raw nail positions unchanged"

    def test_zero_hole_diameter_no_offset(self):
        path_data = parse_svg_paths(load_svg("square.svg"))
        path = path_data[0]["path"]
        nails = compute_nail_positions(path, 20, strategy=1)
        offset = offset_nails_inward(nails, path, hole_diameter=0)
        for i, (ox, oy) in enumerate(offset):
            assert (ox, oy) == (nails[i][0], nails[i][1]), (
                f"Nail {i} moved despite zero diameter"
            )


class TestSvgToOpenscadIntegration:
    def test_end_to_end_square(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from svg_to_openscad import main as scad_main

        svg_path = load_svg("square.svg")
        with tempfile.NamedTemporaryFile(suffix=".scad", delete=False, mode="w") as tmp:
            tmp_path = tmp.name

        try:
            sys.argv = [
                "svg_to_openscad.py",
                "--input",
                svg_path,
                "--spacing",
                "15",
                "--hole-diameter",
                "8",
                "--thickness",
                "5",
                "--corner-strategy",
                "1",
                "--output",
                tmp_path,
            ]
            scad_main()

            assert os.path.isfile(tmp_path)
            with open(tmp_path) as f:
                content = f.read()
            assert "cylinder" in content
            assert "module letter_outline()" in content
            assert "module nail_holes()" in content
        finally:
            os.unlink(tmp_path)

    def test_end_to_end_letter_o_strategy2(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from svg_to_openscad import main as scad_main

        svg_path = load_svg("letter_O_outline.svg")
        with tempfile.NamedTemporaryFile(suffix=".scad", delete=False, mode="w") as tmp:
            tmp_path = tmp.name

        try:
            sys.argv = [
                "svg_to_openscad.py",
                "--input",
                svg_path,
                "--spacing",
                "15",
                "--hole-diameter",
                "8",
                "--thickness",
                "5",
                "--corner-strategy",
                "2",
                "--output",
                tmp_path,
            ]
            scad_main()

            assert os.path.isfile(tmp_path)
            with open(tmp_path) as f:
                content = f.read()
            assert "cylinder" in content
            assert "module letter_outline()" in content
            assert "module nail_holes()" in content
            assert "corner_strategy = 2" in content
        finally:
            os.unlink(tmp_path)
