# Change: add OCR ROI measurement helper

## Why

OCR/CV 自动导出在新版剪映首页中高度依赖草稿列表 ROI。当前用户只能手工猜测 `--draft-roi`，排查成本高，容易因为坐标不准导致 OCR 返回空结果。

## What Changes

- 新增一个本地 ROI 测量工具，允许用户在当前屏幕截图上拖拽矩形并直接得到 `x,y,width,height`。
- 工具保存带标注的截图，便于把测量结果回填到 `auto_exporter.py --draft-roi`。
- 更新文档，给出 Windows 手动验证和回填 ROI 的最短步骤。

## Impact

- Affected code: `scripts/` 下新增测量脚本，`README.md`/`docs/` 相关说明，必要的测试。
- Affected users: 需要调试 OCR 草稿区域、排查“识别到空”的用户。
- Platform constraints: 首版优先支持 Windows 本地桌面会话；需要真实屏幕截图与鼠标拖拽。
