# ruff: noqa: E402

import os
import sys
import unittest
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.dirname(current_dir)
scripts_path = os.path.join(skill_root, "scripts")
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

from auto_exporter import (  # noqa: E402
    _build_paddle_ocr,
    _default_draft_roi,
    _extract_ocr_text_boxes,
    _find_exact_ocr_match,
    _ocr_find_draft_center,
    _parse_region,
)
from utils.errors import UserInputError  # noqa: E402


class TestAutoExporterHelpers(unittest.TestCase):
    def test_parse_region(self):
        self.assertEqual(_parse_region("10,20,300,400"), (10, 20, 300, 400))
        self.assertIsNone(_parse_region(None))
        with self.assertRaises(UserInputError):
            _parse_region("10,20,0,400")

    def test_default_draft_roi_uses_measured_1080p_region(self):
        self.assertEqual(_default_draft_roi(1920, 1080), (240, 550, 1150, 327))
        self.assertEqual(_default_draft_roi(960, 540), (120, 275, 575, 164))

    def test_extract_ocr_text_boxes_and_exact_match(self):
        ocr_result = [
            [
                [
                    [[10, 10], [110, 10], [110, 50], [10, 50]],
                    ("示例草稿", 0.98),
                ],
                [
                    [[20, 70], [120, 70], [120, 110], [20, 110]],
                    ("其他草稿", 0.93),
                ],
            ]
        ]
        boxes = _extract_ocr_text_boxes(ocr_result)
        self.assertEqual(len(boxes), 2)
        self.assertEqual((boxes[0].center_x, boxes[0].center_y), (60, 30))
        self.assertEqual(_find_exact_ocr_match(ocr_result, "示例草稿"), boxes[0])
        self.assertIsNone(_find_exact_ocr_match(ocr_result, "示例"))

    def test_build_paddle_ocr_disables_mkldnn_when_supported(self):
        recorded = {}

        def fake_paddleocr(**kwargs):
            recorded.update(kwargs)
            return "engine"

        with patch("auto_exporter._import_gui_dependencies", return_value=(None, None, None, None, fake_paddleocr)):
            engine = _build_paddle_ocr()

        self.assertEqual(engine, "engine")
        self.assertFalse(recorded["use_angle_cls"])
        self.assertEqual(recorded["lang"], "ch")
        self.assertFalse(recorded["enable_mkldnn"])

    def test_ocr_find_draft_center_wraps_onednn_runtime_error(self):
        class FakePyAutoGui:
            @staticmethod
            def screenshot(region=None):
                return "fake-image"

        class FakeCv2:
            COLOR_RGB2BGR = object()

            @staticmethod
            def cvtColor(image, mode):
                return image

        class FakeNp:
            @staticmethod
            def array(value):
                return value

        class FakeEngine:
            @staticmethod
            def ocr(image, cls=False):
                raise RuntimeError("OneDnnContext does not have the input Filter in fused_conv2d")

        with patch(
            "auto_exporter._import_gui_dependencies",
            return_value=(FakeCv2, FakeNp, FakePyAutoGui, None, None),
        ):
            with self.assertRaises(RuntimeError) as ctx:
                _ocr_find_draft_center(
                    "示例草稿",
                    region=(0, 0, 100, 100),
                    ocr_engine=FakeEngine(),
                    ocr_backend="paddle",
                )

        self.assertIn("oneDNN/MKLDNN", str(ctx.exception))

    def test_ocr_find_draft_center_auto_falls_back_to_rapidocr(self):
        class FakePyAutoGui:
            @staticmethod
            def screenshot(region=None):
                return "fake-image"

        class FakeCv2:
            COLOR_RGB2BGR = object()

            @staticmethod
            def cvtColor(image, mode):
                return image

        class FakeNp:
            @staticmethod
            def array(value):
                return value

        class FakePaddleEngine:
            @staticmethod
            def ocr(image, cls=False):
                raise RuntimeError("OneDnnContext does not have the input Filter in fused_conv2d")

        class FakeRapidResult:
            boxes = [[[10, 10], [110, 10], [110, 50], [10, 50]]]
            txts = ["示例草稿"]
            scores = [0.97]

        class FakeRapidEngine:
            def __call__(self, image):
                return FakeRapidResult()

        with patch(
            "auto_exporter._import_gui_dependencies",
            return_value=(FakeCv2, FakeNp, FakePyAutoGui, None, None),
        ), patch(
            "auto_exporter._build_rapidocr",
            return_value=FakeRapidEngine(),
        ):
            center = _ocr_find_draft_center(
                "示例草稿",
                region=(100, 200, 300, 400),
                ocr_engine=FakePaddleEngine(),
                ocr_backend="auto",
            )

        self.assertEqual(center, (160, 230))

    def test_ocr_find_draft_center_passes_debug_dir_without_breaking_match(self):
        class FakePyAutoGui:
            @staticmethod
            def screenshot(region=None):
                return "fake-image"

        class FakeCv2:
            COLOR_RGB2BGR = object()

            @staticmethod
            def cvtColor(image, mode):
                return image

        class FakeNp:
            @staticmethod
            def array(value):
                return value

        class FakeEngine:
            @staticmethod
            def ocr(image, cls=False):
                return [
                    [
                        [
                            [[10, 10], [110, 10], [110, 50], [10, 50]],
                            ("示例草稿", 0.98),
                        ]
                    ]
                ]

        with patch(
            "auto_exporter._import_gui_dependencies",
            return_value=(FakeCv2, FakeNp, FakePyAutoGui, None, None),
        ), patch(
            "auto_exporter._save_ocr_debug_images",
            return_value=None,
        ) as debug_mock:
            center = _ocr_find_draft_center(
                "示例草稿",
                region=(100, 200, 300, 400),
                ocr_engine=FakeEngine(),
                ocr_backend="paddle",
                debug_dir="debug-out",
            )

        self.assertEqual(center, (160, 230))
        debug_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
