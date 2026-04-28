## ADDED Requirements

### Requirement: OCR/CV Draft Auto Export

The system MUST provide a pure local Python workflow that opens a specified JianYing draft by exact draft name and starts video export using window activation, local OCR, CV visual waits, and keyboard/mouse automation.

#### Scenario: Draft is found and export is started
- **GIVEN** JianYing is running and its home draft list contains a draft named exactly `draft_name`
- **AND** the caller provides a valid `timeline_icon` anchor image
- **WHEN** `auto_export_jianying(draft_name, anchor_images)` is executed
- **THEN** the JianYing window is activated and maximized
- **AND** only the configured draft-list ROI is captured for OCR
- **AND** the matching draft text center is double-clicked
- **AND** the workflow waits visually for the editor anchor before pressing `Ctrl+E`
- **AND** the workflow presses `Enter` to start export

#### Scenario: Draft is not found
- **GIVEN** JianYing is running and the configured ROI does not contain an exact OCR match for `draft_name`
- **WHEN** the workflow searches for the draft
- **THEN** it raises a clear exception that includes the draft name
- **AND** it does not press export shortcuts

### Requirement: Visual Wait Without Long Dead Sleeps

The system MUST expose a reusable `wait_for_image_appear(image_path, timeout, confidence=0.8)` helper that repeatedly searches the screen using grayscale template matching until an anchor appears or the timeout expires.

#### Scenario: Anchor appears before timeout
- **GIVEN** an anchor image is visible on screen
- **WHEN** `wait_for_image_appear` is called with that anchor path
- **THEN** it returns the anchor center coordinates
- **AND** it uses grayscale matching with the requested confidence threshold

#### Scenario: Anchor does not appear
- **GIVEN** an anchor image is not visible on screen
- **WHEN** `wait_for_image_appear` exceeds the configured timeout
- **THEN** it raises a timeout exception that includes the image path

### Requirement: Local OCR and Logging Defaults

The OCR/CV exporter MUST use local/free dependencies and emit clear Chinese step logs suitable for GUI automation troubleshooting.

#### Scenario: OCR engine is initialized
- **WHEN** the exporter creates a PaddleOCR instance
- **THEN** it initializes with `use_angle_cls=False`, `lang="ch"`, and `show_log=False` when supported by the installed PaddleOCR version

#### Scenario: Workflow runs each step
- **WHEN** the workflow advances through window setup, OCR lookup, editor wait, export shortcut, and completion monitoring
- **THEN** it prints Chinese `INFO` logs with step numbers and key parameters
