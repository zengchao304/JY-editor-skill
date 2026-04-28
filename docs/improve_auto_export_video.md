# Role
你是一个资深的 Python RPA 自动化工程师，精通基于机器视觉（CV）和本地光学字符识别（OCR）的桌面 GUI 自动化开发。

# Context & Goal
由于最新版 PC 端剪映（JianYing）采用了自绘渲染引擎，传统的 UIAutomation / 控件树方案已经失效。
目前的任务是：开发一个纯 Python 脚本，通过“窗口句柄控制 + 本地 OCR 定位 + CV 视觉等待 + 快捷键驱动”的融合流派，实现“全自动打开指定名称的剪映草稿并完成视频导出”。

# Tech Stack & Dependencies
该方案必须是纯本地、100%免费的，请严格使用以下库来实现：
1. `paddleocr`: 用于纯本地极速离线文字识别（定位动态草稿名称）。
2. `pyautogui` + `pynput`: 用于模拟鼠标移动、点击和全局快捷键发送。
3. `opencv-python` (`cv2`) + `numpy`: 结合 pyautogui 实现基于灰度图和容错率（confidence）的模板匹配（CV找图）。
4. `pygetwindow`: 用于寻找剪映主窗口并进行激活、最大化操作。

# Core Execution Flow (业务逻辑)
请编写一个主函数 `auto_export_jianying(draft_name: str, anchor_images: dict)`，严格按照以下步骤流转：

**Step 1: 窗口环境初始化**
- 寻找标题包含“剪映”或“剪映专业版”的窗口。
- 将窗口激活到前台，并强制最大化（以保证绝对分辨率一致性，极大提高 CV 准确率）。
- 适度休眠 1 秒等待动画完成。

**Step 2: ROI 区域 OCR 找草稿并进入**
- 【关键提速】：不要全屏截图。使用 `pyautogui.screenshot(region=...)` 仅截取屏幕中间偏下区域（即草稿列表大概率出现的区域）。
- 调用 PaddleOCR 识别截图中的文字，寻找与入参 `draft_name` 完全匹配的文本块。
- 获取该文本块的中心坐标，换算为屏幕绝对坐标，执行鼠标双击操作（`pyautogui.doubleClick`）。

**Step 3: 视觉轮询等待（Visual Wait）**
- 双击草稿后，剪映进入编辑界面需要一定时间（可能 2 秒到 10 秒不等，取决于视频大小）。
- 【强制规范】：严禁使用死等（如 `time.sleep(10)`）。
- 必须编写一个轮询找图函数 `wait_for_image_appear(image_path, timeout, confidence=0.8)`。
- 循环寻找编辑器特有的标志物（如入参传入的 `anchor_images['timeline_icon']`，比如时间轴指针或播放按钮截图）。
- 当找到该标志物，说明项目加载完毕，跳出循环进入下一步。超时则抛出异常。

**Step 4: 快捷键唤起导出**
- 项目加载完毕后，使用 `pyautogui.hotkey('ctrl', 'e')` 唤起导出面板。
- 延时 1.5 秒等待导出面板动画弹出。

**Step 5: 执行导出**
- 导出面板弹出后，焦点默认在“导出”按钮上。
- 直接发送回车键 `pyautogui.press('enter')` 执行导出。

**Step 6: 视觉监控导出进度（可选闭环）**
- 调用刚才的轮询找图函数，不断寻找“关闭按钮”或“打开文件夹”图标的截图（`anchor_images['export_done_icon']`）。
- 找到后说明导出100%完成，按 `esc` 或点击关闭按钮退出面板，然后按 `ctrl+w` 关闭当前项目回到首页，完成闭环。

# Coding Specifications (极简提速规范)
1. **PaddleOCR 初始化极速模式**：初始化时必须加入参数 `use_angle_cls=False`（不需要判断方向）和 `lang="ch"`（指定中文模型），以及 `show_log=False`，最大化 OCR 推理速度。
2. **CV 找图灰度化与容错**：在使用 `pyautogui.locateOnScreen` 或 `locateCenterOnScreen` 时，必须设置 `confidence=0.8`（或 0.85）并且加上 `grayscale=True`，以应对浅色/深色主题或微小抗锯齿差异。
3. **日志输出**：在每一步的控制台打印清晰的中文日志（如："INFO: [Step 2] 正在局部区域 OCR 寻找草稿: xxx"），方便排错。

请提供结构清晰、包含详细注释的完整 Python 代码。