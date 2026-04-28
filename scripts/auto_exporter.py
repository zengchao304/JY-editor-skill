import argparse
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from utils.cli_protocol import emit_result, make_result
from utils.env_setup import setup_env
from utils.errors import UserInputError
from utils.logging_utils import setup_logger

setup_env()
logger = setup_logger("auto_exporter")


@dataclass(frozen=True)
class OcrTextBox:
    text: str
    score: float
    center_x: int
    center_y: int
    box: tuple[tuple[float, float], ...]

    @property
    def left_x(self) -> int:
        return round(min(point[0] for point in self.box))


def _step_log(step: int, message: str) -> None:
    print(f"INFO: [Step {step}] {message}")


def _import_gui_dependencies() -> tuple[Any, Any, Any, Any, Any]:
    # 显式关闭 Paddle 全局 MKLDNN 标志，避免 Windows CPU 上意外走到
    # oneDNN fused_conv2d 加速路径。
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    try:
        import cv2  # noqa: F401
        import numpy as np
        import pyautogui
        import pygetwindow as gw
        from paddleocr import PaddleOCR
        from pynput.keyboard import Controller as KeyboardController  # noqa: F401
    except ImportError as exc:
        missing = getattr(exc, "name", str(exc))
        raise UserInputError(
            "OCR/CV 自动导出依赖未安装: "
            f"{missing}。请先运行 `pip install -r requirements.txt`。"
        ) from exc
    return cv2, np, pyautogui, gw, PaddleOCR


def _import_rapidocr() -> Any:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        missing = getattr(exc, "name", str(exc))
        raise UserInputError(
            "RapidOCR 自动导出依赖未安装: "
            f"{missing}。请先运行 `pip install rapidocr-onnxruntime onnxruntime`。"
        ) from exc
    return RapidOCR


def _import_draft_module() -> Any:
    try:
        import pyJianYingDraft as draft_module
    except ImportError as exc:
        missing = getattr(exc, "name", str(exc))
        raise UserInputError(
            "传统 UIAutomation 导出依赖未安装: "
            f"{missing}。请先运行 `pip install -r requirements.txt`。"
        ) from exc
    return draft_module


def _build_paddle_ocr() -> Any:
    _, _, _, _, paddle_ocr = _import_gui_dependencies()
    init_variants = [
        {
            "use_angle_cls": False,
            "lang": "ch",
            "show_log": False,
            # Windows CPU 上某些 Paddle/PaddleOCR 组合会在 oneDNN fused_conv2d
            # 路径崩溃，这里默认禁用 MKLDNN 以换取稳定性。
            "enable_mkldnn": False,
        },
        {
            "use_angle_cls": False,
            "lang": "ch",
            "enable_mkldnn": False,
        },
        {
            "use_angle_cls": False,
            "lang": "ch",
        },
    ]
    last_error: Exception | None = None
    for kwargs in init_variants:
        try:
            return paddle_ocr(**kwargs)
        except (TypeError, ValueError) as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return paddle_ocr(use_angle_cls=False, lang="ch")


def _build_rapidocr() -> Any:
    rapid_ocr = _import_rapidocr()
    return rapid_ocr()


def _default_draft_roi(screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
    return (240, 550, 1150, 327)


def _parse_region(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise UserInputError("ROI 必须是 `x,y,width,height` 格式。")
    try:
        x, y, width, height = [int(part) for part in parts]
    except ValueError as exc:
        raise UserInputError("ROI 坐标必须全部是整数。") from exc
    if width <= 0 or height <= 0:
        raise UserInputError("ROI 的 width/height 必须大于 0。")
    return x, y, width, height


def _normalize_anchor_images(anchor_images: dict[str, str | os.PathLike[str]]) -> dict[str, str]:
    required = ["timeline_icon"]
    missing = [key for key in required if not anchor_images.get(key)]
    if missing:
        raise UserInputError(f"缺少必需锚点截图: {', '.join(missing)}")

    normalized: dict[str, str] = {}
    for key, image_path in anchor_images.items():
        if not image_path:
            continue
        path = Path(image_path).expanduser().resolve()
        if not path.exists():
            raise UserInputError(f"锚点截图不存在: {key}={path}")
        normalized[key] = str(path)
    return normalized


def _activate_jianying_window(window_keywords: tuple[str, ...] = ("剪映专业版", "剪映")) -> Any:
    _, _, _, gw, _ = _import_gui_dependencies()
    windows = [window for window in gw.getAllWindows() if getattr(window, "title", "")]
    target = next(
        (window for window in windows if any(keyword in window.title for keyword in window_keywords)),
        None,
    )
    if target is None:
        titles = ", ".join(window.title for window in windows[:8])
        raise RuntimeError(f"未找到标题包含“剪映/剪映专业版”的窗口。当前窗口: {titles}")

    _step_log(1, f"找到剪映窗口: {target.title}")
    if getattr(target, "isMinimized", False):
        target.restore()
    target.activate()
    time.sleep(0.2)
    try:
        target.maximize()
    except Exception as exc:
        logger.warning("Maximize JianYing window failed: %s", exc)
    time.sleep(1.0)
    return target


def _iter_ocr_lines(ocr_result: Any) -> list[tuple[Any, tuple[str, float]]]:
    if not ocr_result:
        return []

    candidates: list[Any]
    if isinstance(ocr_result, list) and len(ocr_result) == 1 and isinstance(ocr_result[0], list):
        candidates = ocr_result[0]
    elif isinstance(ocr_result, list):
        candidates = ocr_result
    else:
        return []

    lines: list[tuple[Any, tuple[str, float]]] = []
    for item in candidates:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        box = item[0]
        payload = item[1]
        if isinstance(payload, (list, tuple)) and payload:
            text = str(payload[0])
            try:
                score = float(payload[1]) if len(payload) > 1 else 1.0
            except (TypeError, ValueError):
                score = 1.0
            lines.append((box, (text, score)))
    return lines


def _box_center(box: Any) -> tuple[int, int]:
    points = [(float(point[0]), float(point[1])) for point in box if len(point) >= 2]
    if not points:
        raise ValueError("OCR 文本框坐标为空。")
    center_x = round(sum(point[0] for point in points) / len(points))
    center_y = round(sum(point[1] for point in points) / len(points))
    return center_x, center_y


def _extract_ocr_text_boxes(ocr_result: Any) -> list[OcrTextBox]:
    boxes: list[OcrTextBox] = []
    for box, (text, score) in _iter_ocr_lines(ocr_result):
        try:
            center_x, center_y = _box_center(box)
            normalized_box = tuple((float(point[0]), float(point[1])) for point in box)
        except (TypeError, ValueError):
            continue
        boxes.append(
            OcrTextBox(
                text=text.strip(),
                score=score,
                center_x=center_x,
                center_y=center_y,
                box=normalized_box,
            )
        )
    return boxes


def _find_exact_ocr_match(ocr_result: Any, draft_name: str) -> OcrTextBox | None:
    target = draft_name.strip()
    for text_box in _extract_ocr_text_boxes(ocr_result):
        if text_box.text == target:
            return text_box
    return None


def _iter_rapidocr_items(ocr_result: Any) -> list[tuple[Any, str, float]]:
    boxes = getattr(ocr_result, "boxes", None)
    txts = getattr(ocr_result, "txts", None)
    scores = getattr(ocr_result, "scores", None)
    if boxes is not None and txts is not None:
        normalized_scores = scores if scores is not None else [1.0] * len(txts)
        return list(zip(boxes, txts, normalized_scores))

    if isinstance(ocr_result, tuple) and ocr_result and isinstance(ocr_result[0], list):
        candidates = ocr_result[0]
    elif isinstance(ocr_result, list):
        candidates = ocr_result
    else:
        return []

    items: list[tuple[Any, str, float]] = []
    for candidate in candidates:
        if not isinstance(candidate, (list, tuple)) or len(candidate) < 2:
            continue
        box = candidate[0]
        text = str(candidate[1])
        try:
            score = float(candidate[2]) if len(candidate) > 2 else 1.0
        except (TypeError, ValueError):
            score = 1.0
        items.append((box, text, score))
    return items


def _extract_rapidocr_text_boxes(ocr_result: Any) -> list[OcrTextBox]:
    extracted: list[OcrTextBox] = []
    for box, text, score in _iter_rapidocr_items(ocr_result):
        try:
            center_x, center_y = _box_center(box)
            normalized_box = tuple((float(point[0]), float(point[1])) for point in box)
        except (TypeError, ValueError):
            continue
        extracted.append(
            OcrTextBox(
                text=text.strip(),
                score=score,
                center_x=center_x,
                center_y=center_y,
                box=normalized_box,
            )
        )
    return extracted


def _normalize_draft_match_text(value: str) -> str:
    return re.sub(r"[\s_]+", "_", value.strip()).casefold()


def _find_exact_text_box(boxes: list[OcrTextBox], draft_name: str) -> OcrTextBox | None:
    target = draft_name.strip()
    normalized_target = _normalize_draft_match_text(target)
    for text_box in boxes:
        if text_box.text == target:
            return text_box
    for text_box in boxes:
        if _normalize_draft_match_text(text_box.text) == normalized_target:
            return text_box
    return None


def _is_onednn_runtime_error(exc: Exception) -> bool:
    message = str(exc)
    return "OneDnnContext" in message or "fused_conv2d" in message


def _save_ocr_debug_images(
    screenshot: Any,
    region: tuple[int, int, int, int],
    debug_dir: str | os.PathLike[str],
) -> None:
    cv2, np, pyautogui, _, _ = _import_gui_dependencies()
    debug_path = Path(debug_dir).expanduser().resolve()
    debug_path.mkdir(parents=True, exist_ok=True)

    roi_path = debug_path / "draft_roi.png"
    screenshot.save(roi_path)

    full_screen = pyautogui.screenshot()
    annotated = cv2.cvtColor(np.array(full_screen), cv2.COLOR_RGB2BGR)
    x, y, width, height = region
    cv2.rectangle(annotated, (x, y), (x + width, y + height), (0, 0, 255), 3)
    cv2.imwrite(str(debug_path / "draft_roi_annotated.png"), annotated)


def _ocr_find_draft_center(
    draft_name: str,
    region: tuple[int, int, int, int] | None = None,
    ocr_engine: Any | None = None,
    ocr_backend: str = "auto",
    debug_dir: str | os.PathLike[str] | None = None,
) -> tuple[int, int]:
    backend = ocr_backend.strip().lower()
    if backend not in {"auto", "paddle", "rapidocr"}:
        raise UserInputError("ocr_backend 必须是 auto、paddle 或 rapidocr。")

    cv2 = np = gw = paddle_ocr = None
    if backend == "rapidocr":
        import pyautogui
        import cv2  # type: ignore
        import numpy as np  # type: ignore
    else:
        cv2, np, pyautogui, gw, paddle_ocr = _import_gui_dependencies()

    if region is None:
        screen_width, screen_height = pyautogui.size()
        region = _default_draft_roi(screen_width, screen_height)

    _step_log(2, f"正在局部区域 OCR 寻找草稿: {draft_name}，ROI={region}")
    screenshot = pyautogui.screenshot(region=region)
    if debug_dir:
        _save_ocr_debug_images(screenshot, region, debug_dir)
    image = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

    def _run_paddle(engine: Any) -> list[OcrTextBox]:
        try:
            result = engine.ocr(image, cls=False)
        except Exception as exc:
            if _is_onednn_runtime_error(exc):
                raise RuntimeError(
                    "PaddleOCR 在当前环境触发了 oneDNN/MKLDNN 卷积推理错误。"
                ) from exc
            raise
        return _extract_ocr_text_boxes(result)

    def _run_rapidocr(engine: Any) -> list[OcrTextBox]:
        result = engine(image)
        return _extract_rapidocr_text_boxes(result)

    used_backend = backend
    try:
        if backend == "rapidocr":
            text_boxes = _run_rapidocr(ocr_engine or _build_rapidocr())
        else:
            used_backend = "paddle"
            text_boxes = _run_paddle(ocr_engine or _build_paddle_ocr())
    except RuntimeError as exc:
        if backend == "auto" and "oneDNN/MKLDNN" in str(exc):
            _step_log(2, "PaddleOCR 推理失败，正在自动切换到 RapidOCR(ONNXRuntime) 重试。")
            used_backend = "rapidocr"
            text_boxes = _run_rapidocr(_build_rapidocr())
        else:
            if "oneDNN/MKLDNN" in str(exc):
                raise RuntimeError(
                    "PaddleOCR 在当前环境触发了 oneDNN/MKLDNN 卷积推理错误。"
                    "建议改用 `--ocr-backend rapidocr`，或安装 `rapidocr-onnxruntime onnxruntime` 后重试。"
                ) from exc
            raise

    match = _find_exact_text_box(text_boxes, draft_name)
    if match is None:
        found = ", ".join(box.text for box in text_boxes[:10])
        raise RuntimeError(
            f"未在局部 OCR 区域找到草稿“{draft_name}”。"
            f"OCR 后端={used_backend}，识别到: {found or '空'}"
        )

    click_offset_x = 15
    absolute_x = region[0] + match.left_x - click_offset_x
    absolute_y = region[1] + match.center_y
    _step_log(
        2,
        f"命中草稿: {match.text}，OCR 后端={used_backend}，"
        f"置信度={match.score:.3f}，点击坐标=({absolute_x}, {absolute_y})",
    )
    return absolute_x, absolute_y


def wait_for_image_appear(
    image_path: str | os.PathLike[str],
    timeout: float,
    confidence: float = 0.8,
    interval: float = 0.3,
) -> tuple[int, int]:
    _, _, pyautogui, _, _ = _import_gui_dependencies()
    path = str(Path(image_path).expanduser().resolve())
    if not os.path.exists(path):
        raise UserInputError(f"视觉锚点截图不存在: {path}")
    if timeout <= 0:
        raise UserInputError("视觉等待 timeout 必须大于 0。")

    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            point = pyautogui.locateCenterOnScreen(
                path,
                confidence=confidence,
                grayscale=True,
            )
        except Exception as exc:
            last_error = exc
            point = None
        if point is not None:
            center = (int(point.x), int(point.y)) if hasattr(point, "x") else (int(point[0]), int(point[1]))
            return center
        time.sleep(interval)

    reason = f" 最后一次错误: {last_error}" if last_error else ""
    raise TimeoutError(f"等待视觉锚点超时: {path}，timeout={timeout}s，confidence={confidence}.{reason}")


def auto_export_jianying(
    draft_name: str,
    anchor_images: dict[str, str | os.PathLike[str]],
    *,
    draft_region: tuple[int, int, int, int] | None = None,
    ocr_backend: str = "auto",
    ocr_debug_dir: str | os.PathLike[str] | None = None,
    editor_timeout: float = 15.0,
    export_timeout: float = 600.0,
    confidence: float = 0.8,
    wait_export_done: bool = True,
) -> dict[str, Any]:
    if not draft_name or not draft_name.strip():
        raise UserInputError("draft_name 不能为空。")
    anchors = _normalize_anchor_images(anchor_images)
    _, _, pyautogui, _, _ = _import_gui_dependencies()

    _step_log(1, "正在初始化窗口环境并最大化剪映。")
    _activate_jianying_window()

    center_x, center_y = _ocr_find_draft_center(
        draft_name.strip(),
        draft_region,
        ocr_backend=ocr_backend,
        debug_dir=ocr_debug_dir,
    )
    pyautogui.doubleClick(center_x, center_y)

    _step_log(3, f"正在视觉轮询等待编辑器加载，timeout={editor_timeout}s。")
    timeline_center = wait_for_image_appear(
        anchors["timeline_icon"],
        timeout=editor_timeout,
        confidence=confidence,
    )
    _step_log(3, f"已检测到编辑器锚点，坐标={timeline_center}。")

    _step_log(4, "正在发送 Ctrl+E 唤起导出面板。")
    pyautogui.hotkey("ctrl", "e")
    time.sleep(1.5)

    _step_log(5, "正在按 Enter 执行导出。")
    pyautogui.press("enter")

    export_done_center: tuple[int, int] | None = None
    if wait_export_done and anchors.get("export_done_icon"):
        _step_log(6, f"正在视觉监控导出完成，timeout={export_timeout}s。")
        export_done_center = wait_for_image_appear(
            anchors["export_done_icon"],
            timeout=export_timeout,
            confidence=confidence,
        )
        _step_log(6, f"导出完成锚点已出现，坐标={export_done_center}，正在关闭面板并返回首页。")
        pyautogui.press("esc")
        time.sleep(0.5)
        pyautogui.hotkey("ctrl", "w")
    elif wait_export_done:
        _step_log(6, "未提供 export_done_icon，已跳过导出完成闭环监控。")

    return {
        "draft": draft_name.strip(),
        "timeline_anchor": timeline_center,
        "export_done_anchor": export_done_center,
        "wait_export_done": bool(wait_export_done and anchors.get("export_done_icon")),
    }


def auto_export(
    draft_name: str, output_path: str, resolution: str = None, framerate: str = None
) -> tuple[int, dict]:
    draft = _import_draft_module()
    res_map = {
        "480": draft.ExportResolution.RES_480P,
        "720": draft.ExportResolution.RES_720P,
        "1080": draft.ExportResolution.RES_1080P,
        "2K": draft.ExportResolution.RES_2K,
        "4K": draft.ExportResolution.RES_4K,
        "8K": draft.ExportResolution.RES_8K,
    }
    fr_map = {
        "24": draft.ExportFramerate.FR_24,
        "25": draft.ExportFramerate.FR_25,
        "30": draft.ExportFramerate.FR_30,
        "50": draft.ExportFramerate.FR_50,
        "60": draft.ExportFramerate.FR_60,
    }

    target_res = res_map.get(str(resolution).upper() if resolution else "")
    target_fr = fr_map.get(str(framerate) if framerate else "")

    if resolution and target_res is None:
        raise UserInputError(
            f"Unsupported resolution: {resolution} (allowed: {', '.join(res_map.keys())})"
        )
    if framerate and target_fr is None:
        raise UserInputError(
            f"Unsupported framerate: {framerate} (allowed: {', '.join(fr_map.keys())})"
        )

    try:
        output_dir = os.path.dirname(os.path.abspath(output_path))
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        logger.info("Preparing export: draft=%s", draft_name)
        ctrl = draft.JianyingController()
        ctrl.export_draft(draft_name, output_path, resolution=target_res, framerate=target_fr)
        logger.info("Export succeeded: %s", output_path)
        return 0, make_result(
            True,
            "ok",
            "",
            {
                "draft": draft_name,
                "output": output_path,
                "resolution": resolution,
                "fps": framerate,
            },
        )
    except Exception as e:
        logger.error("Export failed: %s", e)
        logger.error("Hint: restart JianYing and keep it on Home/Edit page before retry.")
        return 1, make_result(
            False,
            "export_failed",
            str(e),
            {"draft": draft_name, "output": output_path},
        )


def _run_ocr_cv_export(args: argparse.Namespace) -> tuple[int, dict]:
    anchors = {
        "timeline_icon": args.timeline_icon,
        "export_done_icon": args.export_done_icon,
    }
    result = auto_export_jianying(
        args.name,
        anchors,
        draft_region=_parse_region(args.draft_roi),
        ocr_backend=args.ocr_backend,
        ocr_debug_dir=args.ocr_debug_dir,
        editor_timeout=args.editor_timeout,
        export_timeout=args.export_timeout,
        confidence=args.confidence,
        wait_export_done=not args.no_wait_done,
    )
    return 0, make_result(True, "ok", "", result)


def main() -> int:
    parser = argparse.ArgumentParser(description="JianYing draft exporter")
    parser.add_argument("name", help="Draft name")
    parser.add_argument("output", nargs="?", help="Output mp4 path for legacy UIAutomation export")
    parser.add_argument("--res", help="Resolution: 480/720/1080/2K/4K/8K")
    parser.add_argument("--fps", help="Framerate: 24/25/30/50/60")
    parser.add_argument("--ocr-cv", action="store_true", help="Use OCR/CV GUI automation export flow")
    parser.add_argument("--timeline-icon", help="Editor/timeline anchor image for OCR/CV flow")
    parser.add_argument("--export-done-icon", help="Export completion anchor image for OCR/CV flow")
    parser.add_argument("--draft-roi", help="Draft-list OCR ROI: x,y,width,height")
    parser.add_argument(
        "--ocr-backend",
        default="auto",
        help="OCR backend for OCR/CV flow: auto/paddle/rapidocr",
    )
    parser.add_argument(
        "--ocr-debug-dir",
        help="Save OCR ROI debug images into this directory",
    )
    parser.add_argument("--editor-timeout", type=float, default=15.0, help="Editor visual wait timeout")
    parser.add_argument("--export-timeout", type=float, default=600.0, help="Export completion timeout")
    parser.add_argument("--confidence", type=float, default=0.8, help="CV confidence threshold")
    parser.add_argument("--no-wait-done", action="store_true", help="Do not wait for export completion")
    parser.add_argument("--json", action="store_true", help="Output JSON summary")
    args = parser.parse_args()

    try:
        if args.ocr_cv:
            if not args.timeline_icon:
                raise UserInputError("使用 --ocr-cv 时必须提供 --timeline-icon。")
            code, summary = _run_ocr_cv_export(args)
        else:
            if not args.output:
                raise UserInputError("传统导出模式必须提供 output；OCR/CV 模式请加 --ocr-cv。")
            code, summary = auto_export(args.name, args.output, args.res, args.fps)
    except UserInputError as e:
        logger.error(str(e))
        summary = make_result(False, "invalid_input", str(e), {"draft": args.name})
        code = 2
    except Exception as e:
        logger.error("Export failed: %s", e)
        summary = make_result(False, "export_failed", str(e), {"draft": args.name})
        code = 1
    emit_result(summary, args.json)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
