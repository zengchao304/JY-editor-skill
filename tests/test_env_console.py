# ruff: noqa: E402

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

current_dir = os.path.dirname(os.path.abspath(__file__))
skill_root = os.path.dirname(current_dir)
scripts_path = os.path.join(skill_root, "scripts")
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

from utils.console import safe_text  # noqa: E402
from utils.env_setup import _ensure_ffprobe_path  # noqa: E402


class TestConsoleAndEnvSetup(unittest.TestCase):
    def test_safe_text_is_gbk_encodable(self):
        original_stdout = sys.stdout
        try:
            sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="gbk", errors="strict")
            text = safe_text("✅ ❌ 🚀 ⚠️ ok")
            text.encode("gbk")
        finally:
            sys.stdout = original_stdout
        self.assertEqual(text, "[OK] [ERROR] [INFO] [WARN] ok")

    def test_ffprobe_path_env_is_prepended(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ffprobe_path = Path(temp_dir) / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
            ffprobe_path.write_text("")
            with patch("utils.env_setup.shutil.which", return_value=None), patch.dict(
                os.environ,
                {"FFPROBE_PATH": str(ffprobe_path), "PATH": ""},
                clear=False,
            ):
                _ensure_ffprobe_path(None)
                self.assertEqual(os.environ["PATH"].split(os.pathsep)[0], temp_dir)


if __name__ == "__main__":
    unittest.main()
