# ruff: noqa: E402

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.dirname(current_dir)
scripts_path = os.path.join(skill_root, "scripts")
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

from auto_exporter import (  # noqa: E402
    _default_draft_roi,
    _extract_ocr_text_boxes,
    _find_exact_ocr_match,
    _parse_region,
)
from utils.errors import UserInputError  # noqa: E402


class TestAutoExporterHelpers(unittest.TestCase):
    def test_parse_region(self):
        self.assertEqual(_parse_region("10,20,300,400"), (10, 20, 300, 400))
        self.assertIsNone(_parse_region(None))
        with self.assertRaises(UserInputError):
            _parse_region("10,20,0,400")

    def test_default_draft_roi_middle_lower_area(self):
        self.assertEqual(_default_draft_roi(1000, 800), (180, 256, 640, 448))

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


if __name__ == "__main__":
    unittest.main()
