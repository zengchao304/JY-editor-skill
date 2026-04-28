# ruff: noqa: E402

import os
import sys
import unittest

current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.dirname(current_dir)
scripts_path = os.path.join(skill_root, "scripts")
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

from measure_ocr_roi import RoiSelection, _normalize_selection  # noqa: E402
from utils.errors import UserInputError  # noqa: E402


class TestMeasureOcrRoiHelpers(unittest.TestCase):
    def test_normalize_selection_top_left_to_bottom_right(self):
        selection = _normalize_selection((10, 20), (110, 220))

        self.assertEqual(selection, RoiSelection(10, 20, 100, 200))
        self.assertEqual(selection.cli_value, "10,20,100,200")

    def test_normalize_selection_bottom_right_to_top_left(self):
        selection = _normalize_selection((110, 220), (10, 20))

        self.assertEqual(selection, RoiSelection(10, 20, 100, 200))
        self.assertEqual(selection.cli_value, "10,20,100,200")

    def test_normalize_selection_rejects_zero_area(self):
        with self.assertRaises(UserInputError):
            _normalize_selection((10, 20), (10, 220))


if __name__ == "__main__":
    unittest.main()
