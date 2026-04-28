## Why

最新版 PC 端剪映使用自绘渲染引擎，传统 UIAutomation/控件树定位在草稿列表和导出面板中不稳定。现有自动导出能力需要补充一条纯本地、免费、视觉驱动的路径，通过窗口句柄控制、局部 OCR、CV 视觉等待和快捷键驱动，实现指定草稿的自动打开与导出。

## What Changes

- 新增 OCR + CV 驱动的自动导出函数 `auto_export_jianying(draft_name, anchor_images)`。
- 使用 `pygetwindow` 激活并最大化剪映窗口，保证视觉坐标稳定。
- 使用 PaddleOCR 极速配置在草稿列表 ROI 内精确匹配草稿名并双击进入。
- 使用灰度模板匹配轮询等待编辑器加载和导出完成，避免固定长时间死等。
- 提供 CLI 入口与中文日志，方便人工排错和脚本集成。
- 更新依赖、文档和示例，说明锚点截图、ROI、超时和平台限制。

## Impact

- Affected code: `scripts/auto_exporter.py`, `requirements.txt`, `README.md`, `docs/api.md`, examples/tests as needed.
- Affected users: 需要在新版剪映自绘 UI 下自动打开指定草稿并导出的用户。
- Runtime dependencies: `paddleocr`, `pygetwindow`, `pyautogui`, `pynput`, `opencv-python`, `numpy`.
- Platform constraints: GUI 自动化仍依赖真实桌面会话；运行期间不应移动鼠标键盘。
