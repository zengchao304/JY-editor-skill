# Project Context

## Purpose

本项目是一个面向 AI 编程助手的「剪映（JianYing/CapCut 中国版）自动剪辑 Skill」。它的目标不是替代剪映本体，而是让用户用自然语言驱动 AI 自动生成、修改和导出剪映草稿：从素材导入、文案生成、AI 配音、字幕对齐、配乐、特效转场、网页动效录屏，到最终通过剪映桌面端渲染导出 MP4。

项目主要服务以下场景：

- 短视频、Vlog、影视解说、教程录屏等内容的自动化剪辑。
- 将 Python 脚本写入剪映草稿目录，自动搭建多轨时间线。
- 将 HTML/Canvas/JS 动效录制为视频素材并导入剪映。
- 通过 AI 助手复用固定的剪辑规则、示例脚本和素材索引，降低普通用户使用门槛。

## Tech Stack

- Python 3.12：核心脚本、包装 API、测试和工具链的主要语言。
- pyJianYingDraft（内置于 `scripts/vendor/`）：底层剪映草稿读写能力。
- `uiautomation`、`pynput`、`psutil`：剪映桌面端自动导出、窗口与输入自动化。
- Playwright Chromium：网页动效录屏、Web-to-Video 工作流。
- `edge-tts`：微软语音合成，用于旁白与字幕对齐。
- OpenCV、NumPy、ImageIO、PyMediaInfo：视频分析、录屏处理、智能变焦、媒体信息读取。
- `requests`、`websockets`：云素材下载、外部服务通信和浏览器/录屏辅助能力。
- unittest / pytest：测试执行以 `tests/test_wrapper.py` 为主。
- Ruff、Black、EditorConfig、pre-commit：代码风格、格式化和提交前检查。
- OpenSpec：需求变更、能力规格和实现计划管理。

## Project Conventions

### Code Style

- Python 目标版本为 3.12，行宽统一为 100。
- 使用 4 空格缩进；Markdown 可保留行尾空格；YAML/JSON/TOML 使用 2 空格缩进。
- 使用 Ruff 检查 `E`、`F`、`I` 规则，并忽略 `E501`；使用 Black 进行格式化。
- `scripts/vendor/**` 和 `assets/**` 视为外部或素材内容，不做常规 Ruff 检查。
- 业务逻辑应保持函数/类命名直观，优先使用描述性变量名，不使用难懂缩写。
- CLI 工具应尽量支持稳定的 `--json` 输出协议：`ok`、`code`、`reason`、`data`。
- 时间参数在包装层统一支持友好格式，例如 `"3s"`、`"500ms"`、`"1m2.5s"`，内部以微秒为准。

### Architecture Patterns

- `SKILL.md` 是给 AI 助手阅读的入口说明，`README.md` 面向用户，`docs/` 放 API、SOP 和深度说明。
- `scripts/jy_wrapper.py` 暴露高层 `JyProject` API，是 AI 生成剪辑脚本时优先使用的稳定入口。
- `scripts/core/` 承载媒体、文本、特效、项目基础能力等模块化实现。
- `scripts/utils/` 承载路径探测、时间格式、日志、错误、媒体标准化和 CLI 协议等通用能力。
- `data/*.csv` 是剪映云素材、转场、滤镜、文字动画、TTS 音色等可搜索索引。
- `rules/*.md` 是按能力拆分的 AI 操作规范，复杂任务应先读取对应规则再生成脚本。
- `examples/*.py` 是可运行示例，也是新增 API 和工作流的参考实现。
- `tools/recording/` 是录屏与智能变焦相关工具，和通用 `scripts/` 分层管理。
- `references/` 存放参考资料和旧示例，默认不作为运行时依赖。
- 不要把用户的业务剪辑脚本放进 Skill 安装目录；应放在用户项目根目录或独立工作目录，便于本仓库后续升级。

### Testing Strategy

- 默认快速回归测试为 `python -m pytest tests/test_wrapper.py -q`。
- 必要检查包括：`ruff check scripts tests tools`、`black --check scripts tests tools`、`python tools/check_repo_hygiene.py`、`python tools/validate_data_schema.py`。
- 测试应优先覆盖包装层的稳定行为：项目初始化、路径安全、轨道去重、素材/文本添加、云下载安全、时间格式解析、音频自动分轨等。
- 对依赖剪映桌面端、真实素材、GUI 自动化或网络下载的能力，优先采用 mock、临时目录、数据结构验证和 CLI JSON 合约验证。
- 修改 API、数据 CSV schema、导出流程或路径安全逻辑时，必须补充或更新相邻测试与文档。
- 不应在测试中依赖用户本机真实剪映草稿目录，除非测试被明确标记为手动/集成验证。

### Git Workflow

- `main` 分支应保持可发布状态，所有改动使用小而聚焦的 feature branch。
- 提交信息应清楚表达意图和影响范围；涉及行为或 API 变化时同步更新文档。
- PR 需要说明用户影响、迁移风险、验证步骤，以及 API 变化的前后行为。
- 不提交运行时产物、缓存、日志、导出视频、`__pycache__`、`cloud_cache/` 等临时文件。
- 发布版本信息维护在 `VERSION` 与 `CHANGELOG.md` 中。
- 对新增能力、破坏性变化、架构调整、性能/安全策略变化，应先走 OpenSpec change proposal；普通 bugfix、格式修复和非破坏性配置更新可直接修改。

## Domain Context

- 剪映草稿本质是桌面端可读取的一组项目文件，本项目通过 Python 写入草稿结构，让剪映负责最终预览、渲染和导出。
- 用户经常通过 AI 助手表达剪辑意图，因此项目文档、规则和示例需要对 AI 友好、可复制、可执行。
- 剪映桌面端不会总是实时刷新草稿列表；生成新草稿后，用户可能需要重启剪映或进入旧草稿再返回。
- 自动导出依赖 GUI 自动化，运行时不应移动鼠标键盘，并且目前主要支持剪映专业版 5.9 或更低版本。
- Web-to-Video 能力把 HTML/JS/Canvas/SVG 动效录制为视频素材，因此网页动画应提供明确时长或 `window.animationFinished` 结束信号。
- 云端音乐、视频、音效、文字样式等能力依赖本地 CSV 索引和用户剪映缓存；部分素材需要用户先在剪映中播放/收藏以建立缓存。
- 轨道类型非常重要：BGM/旁白应进入音频轨，字幕应进入文本轨，视频/网页录屏应进入视频轨，特效和转场应使用对应 API。
- 用户可能使用 Antigravity、Trae、Claude Code、Cursor、VSCode 或通用目录安装本 Skill，因此路径探测必须兼容多种安装位置，并支持 `JY_SKILL_ROOT`。

## Important Constraints

- 不支持手机端剪映，只面向 Windows/Mac 桌面版剪映专业版。
- 自动导出强依赖剪映 5.9 及以下版本；6.0+ 弹窗和 UI 变化可能破坏自动化。
- 本项目不应调用或承诺剪映未开放的实时 GPU 能力，例如智能抠图、美颜、内置语音识别字幕、一键成片、图文成片等。
- 剪映安装目录和草稿目录因用户环境而异，代码必须允许显式传入 `drafts_root` 或通过配置/环境探测。
- 所有路径处理必须防止目录穿越，特别是项目名、模板克隆、云素材下载和输出路径。
- 云下载必须校验 URL、响应头、内容类型和大小限制，禁止访问 localhost、私网地址或下载 HTML/JSON 伪装内容。
- Skill 源码目录应保持可升级，不要写入用户业务脚本、缓存或大型生成物。
- 跨平台实现要谨慎：GUI 自动化和剪映路径强依赖操作系统，新增能力必须说明 Windows/Mac 支持范围。
- 不要修改 `scripts/vendor/**`，除非明确是在升级或修补内置第三方库。

## External Dependencies

- 剪映专业版桌面端：草稿读取、预览、渲染和最终导出依赖它完成。
- pyJianYingDraft：剪映草稿文件结构的底层操作库，随项目 vendored。
- Microsoft Edge TTS / `edge-tts`：用于生成旁白音频。
- Playwright Chromium：用于网页动效捕获和录屏。
- 剪映本地缓存与素材库：用于云音乐、云视频、音效、文字样式等素材解析。
- 本地媒体文件系统：视频、音频、图片、字幕、录屏产物均以本地路径为主要输入输出。
- 可选外部 AI/媒体生成服务：README 中提到可结合图片/视频生成模型产出素材，但本仓库核心能力应保持对具体服务的低耦合。
