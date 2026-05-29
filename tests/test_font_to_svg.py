import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from string_art_utils import system_font_path, glyph_to_svg_path


class TestSystemFontPath:
    def test_known_font(self):
        path = system_font_path("Arial")
        assert os.path.isfile(path), f"Arial font not found at {path}"
        assert path.lower().endswith((".ttf", ".otf", ".ttc"))

    def test_direct_path_returns_itself(self):
        arial = system_font_path("Arial")
        result = system_font_path(arial)
        assert result == arial

    def test_unknown_font_raises(self):
        with pytest.raises(FileNotFoundError):
            system_font_path("ZZZxwqjNonexistentFontName123")

    def test_case_insensitive(self):
        path = system_font_path("arial")
        assert os.path.isfile(path)


class TestGlyphToSvgPath:
    @pytest.fixture
    def font_path(self):
        return system_font_path("Arial")

    def test_basic_letter_a(self, font_path):
        path_d, scale = glyph_to_svg_path("A", font_path)
        assert isinstance(path_d, str)
        assert len(path_d) > 0
        assert path_d.startswith("M") or path_d.startswith("m")
        assert 0 < scale < 1

    def test_letter_o_two_contours(self, font_path):
        path_d, scale = glyph_to_svg_path("O", font_path)
        # 'O' should have at least two subpaths (outer + inner)
        assert path_d.count("M") >= 2 or path_d.count("m") >= 2

    def test_unmapped_char_raises(self, font_path):
        with pytest.raises(ValueError, match="not found"):
            glyph_to_svg_path("\x00", font_path)

    def test_different_font_different_outlines(self):
        arial = system_font_path("Arial")
        times = system_font_path("Times New Roman")
        path_a, _ = glyph_to_svg_path("A", arial)
        path_t, _ = glyph_to_svg_path("A", times)
        assert path_a != path_t


class TestGlyphCoordinatesInCanvasSpace:
    def test_coordinates_within_canvas(self):
        font_path = system_font_path("Arial")
        path_d, scale = glyph_to_svg_path("A", font_path, canvas_w=170, canvas_h=170)
        # Path data should now be in canvas-space (0-170)
        assert "170" in path_d or "85" in path_d  # centered, scaled

    def test_different_canvas_size(self):
        font_path = system_font_path("Arial")
        path_a, scale_a = glyph_to_svg_path("A", font_path, canvas_w=170, canvas_h=170)
        path_b, scale_b = glyph_to_svg_path("A", font_path, canvas_w=100, canvas_h=100)
        assert scale_a != scale_b


class TestFontToSvgIntegration:
    def test_generate_svg_file(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from font_to_svg import main as font_to_svg_main

        font_path = system_font_path("Arial")
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            sys.argv = [
                "font_to_svg.py",
                "--letter",
                "B",
                "--font-file",
                font_path,
                "--width",
                "170",
                "--height",
                "170",
                "--output",
                tmp_path,
            ]
            font_to_svg_main()

            assert os.path.isfile(tmp_path)
            with open(tmp_path) as f:
                content = f.read()
            assert "<svg" in content
            assert "viewBox" in content
            assert "path" in content or "Path" in content
        finally:
            os.unlink(tmp_path)
