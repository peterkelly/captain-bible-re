from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from extract_dd1 import DD1Archive  # noqa: E402
from render_fullscreen_gallery import (  # noqa: E402
    discover_fullscreen_frames,
    render_gallery,
)


class FullscreenGalleryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = DD1Archive.from_path(ROOT / "CB" / "DD1.DAT")
        cls.frames = discover_fullscreen_frames(archive)

    def test_discovers_all_fullscreen_identifiers(self):
        self.assertEqual(
            tuple(item.art_name for item in self.frames),
            (
                "INTRO.ART",
                "PRAY.ART",
                "OVER.ART",
                "LAW1.ART",
                "KABLAM1.ART",
                "SPEAKER.ART",
                "HOLE.ART",
                "DOME.ART",
                "DENY1.ART",
                "CULTA.ART",
                "BOSS.ART",
            ),
        )

    def test_infers_script_selected_palettes(self):
        self.assertEqual(
            {item.art_name: item.palette_name for item in self.frames},
            {
                "INTRO.ART": "TITLE.PAL",
                "PRAY.ART": "PRAY.PAL",
                "OVER.ART": "1.PAL",
                "LAW1.ART": "LAW.PAL",
                "KABLAM1.ART": "KABLAM.PAL",
                "SPEAKER.ART": "1.PAL",
                "HOLE.ART": "HOLE.PAL",
                "DOME.ART": "DOME.PAL",
                "DENY1.ART": "DENY.PAL",
                "CULTA.ART": "1.PAL",
                "BOSS.ART": "BOSS.PAL",
            },
        )

    def test_native_gallery_has_expected_layout(self):
        gallery = render_gallery(self.frames, columns=4, scale=1)
        self.assertEqual(gallery.size, (1348, 816))
        self.assertEqual(gallery.mode, "RGB")


if __name__ == "__main__":
    unittest.main()
