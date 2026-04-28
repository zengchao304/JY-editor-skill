import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.cli_protocol import emit_result, make_result
from utils.env_setup import setup_env
from utils.errors import UserInputError

setup_env()


@dataclass(frozen=True)
class RoiSelection:
    x: int
    y: int
    width: int
    height: int

    @property
    def cli_value(self) -> str:
        return f"{self.x},{self.y},{self.width},{self.height}"


def _normalize_selection(start: tuple[int, int], end: tuple[int, int]) -> RoiSelection:
    x1, y1 = start
    x2, y2 = end
    left = min(x1, x2)
    top = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)
    if width <= 0 or height <= 0:
        raise UserInputError("ROI 必须是非零矩形，请拖拽出有效区域。")
    return RoiSelection(left, top, width, height)


def _default_output_path(output: str | None) -> Path:
    if output:
        return Path(output).expanduser().resolve()
    return (Path.cwd() / "ocr_roi_measurement.png").resolve()


def _load_gui_modules() -> tuple[Any, Any, Any, Any]:
    try:
        import cv2
        import numpy as np
        import pyautogui
        from PIL import ImageDraw
    except ImportError as exc:
        missing = getattr(exc, "name", str(exc))
        raise UserInputError(
            "ROI 测量依赖未安装: "
            f"{missing}。请先运行 `pip install -r requirements.txt`。"
        ) from exc
    return cv2, np, pyautogui, ImageDraw


def _annotate_screenshot(
    screenshot: Any,
    selection: RoiSelection,
    output_path: Path,
    image_draw: Any,
) -> None:
    annotated = screenshot.copy()
    draw = image_draw.Draw(annotated)
    left = selection.x
    top = selection.y
    right = selection.x + selection.width
    bottom = selection.y + selection.height
    for inset in range(3):
        draw.rectangle(
            [left + inset, top + inset, right - inset, bottom - inset],
            outline=(255, 0, 0),
        )
    draw.text((left + 6, max(0, top - 22)), selection.cli_value, fill=(255, 0, 0))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    annotated.save(output_path)


def measure_roi(output: str | None = None, window_title: str = "Measure OCR ROI") -> dict[str, Any]:
    cv2, np, pyautogui, image_draw = _load_gui_modules()
    screenshot = pyautogui.screenshot()
    frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    try:
        selection_box = cv2.selectROI(window_title, frame, showCrosshair=True, fromCenter=False)
    finally:
        cv2.destroyWindow(window_title)
    x, y, width, height = [int(value) for value in selection_box]
    selection = _normalize_selection((x, y), (x + width, y + height))

    output_path = _default_output_path(output)
    _annotate_screenshot(screenshot, selection, output_path, image_draw)
    return {
        "roi": selection.cli_value,
        "x": selection.x,
        "y": selection.y,
        "width": selection.width,
        "height": selection.height,
        "annotated_image": str(output_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure a desktop OCR ROI and print x,y,width,height for auto_exporter.py."
    )
    parser.add_argument(
        "--output",
        help="Annotated screenshot path; default: ./ocr_roi_measurement.png",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON result")
    args = parser.parse_args()

    try:
        data = measure_roi(output=args.output)
        if args.json:
            emit_result(make_result(True, "ok", data=data), True)
        else:
            print(data["roi"])
            print(f"Annotated screenshot: {data['annotated_image']}")
            print(
                "Use with: python scripts/auto_exporter.py \"草稿名\" --ocr-cv "
                f"--draft-roi {data['roi']} ..."
            )
        return 0
    except Exception as exc:
        if args.json:
            emit_result(make_result(False, "error", str(exc)), True)
        else:
            print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
