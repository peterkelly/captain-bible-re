import hashlib
from pathlib import Path
import struct
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from render_art import (  # noqa: E402
    ArtFormatError,
    ArtResource,
    compose_canvas,
    expand_vga_palette,
    parse_vga_palette,
)
from extract_dd1 import DD1Archive  # noqa: E402


class ArtResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archive = DD1Archive.from_path(ROOT / "CB" / "DD1.DAT")
        cls.art_data = [
            cls.archive.extract(entry)
            for entry in cls.archive.entries
            if entry.extension == "ART"
        ]
        cls.palette_data = [
            cls.archive.extract(entry)
            for entry in cls.archive.entries
            if entry.extension == "PAL"
        ]

    @classmethod
    def member(cls, filename):
        entry = cls.archive.matching(filename)[0]
        return cls.archive.extract(entry)

    def test_every_art_resource_has_exact_frame_boundaries(self):
        resources = [ArtResource.from_bytes(data) for data in self.art_data]
        self.assertEqual(len(resources), 143)
        self.assertEqual(sum(len(resource.frames) for resource in resources), 1178)

    def test_every_palette_uses_six_bit_components(self):
        palettes = [parse_vga_palette(data) for data in self.palette_data]
        self.assertEqual(len(palettes), 37)
        self.assertTrue(all(max(palette) <= 0x3F for palette in palettes))

    def test_logo_descriptor_regression(self):
        art = ArtResource.from_bytes(self.member("LOGO.ART"))
        self.assertEqual(len(art.frames), 6)
        self.assertEqual(
            (
                art.frames[0].x,
                art.frames[0].y,
                art.frames[0].width,
                art.frames[0].height,
                art.frames[0].data_offset,
            ),
            (88, 54, 124, 74, 72),
        )
        self.assertEqual(
            (
                art.frames[4].x,
                art.frames[4].y,
                art.frames[4].width,
                art.frames[4].height,
            ),
            (-3, -3, 7, 9),
        )

    def test_intro_canvas_is_its_full_screen_frame(self):
        art = ArtResource.from_bytes(self.member("INTRO.ART"))
        self.assertEqual(len(art.frames), 1)
        self.assertEqual(compose_canvas(art), art.frames[0].pixels)

    def test_logo_canvas_regression(self):
        art = ArtResource.from_bytes(self.member("LOGO.ART"))
        pixels = compose_canvas(art)
        self.assertEqual(
            hashlib.sha256(pixels).hexdigest(),
            "e3234c620a873a2f91bb68e8e631d0a645b7958a24b3b07e5890f9bc7b5d62bc",
        )

    def test_expands_black_and_white_palette_endpoints(self):
        palette = bytes([0, 0, 0, 0x3F, 0x3F, 0x3F]) + bytes(762)
        expanded = expand_vga_palette(parse_vga_palette(palette))
        self.assertEqual(expanded[:6], [0, 0, 0, 255, 255, 255])

    def test_rejects_misaligned_descriptor_table(self):
        data = struct.pack("<hhHHI", 0, 0, 1, 1, 13) + b"x"
        with self.assertRaisesRegex(ArtFormatError, "descriptor-aligned"):
            ArtResource.from_bytes(data)

    def test_rejects_non_vga_palette_component(self):
        with self.assertRaisesRegex(ArtFormatError, "exceeds six bits"):
            parse_vga_palette(bytes([0x40]) + bytes(767))


if __name__ == "__main__":
    unittest.main()
