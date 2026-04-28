## ADDED Requirements

### Requirement: OCR ROI Measurement Helper

The system MUST provide a local helper that lets a user measure an OCR region on the current desktop screenshot and reuse that rectangle with the OCR/CV export flow.

#### Scenario: User measures a draft-list region

- **GIVEN** the user is on a real desktop session with JianYing visible
- **WHEN** the ROI measurement helper is launched
- **THEN** the user can drag a rectangle on a screenshot preview
- **AND** the helper outputs the rectangle as `x,y,width,height`
- **AND** the helper saves an annotated image showing the measured rectangle

#### Scenario: Measured ROI is reused by OCR/CV export

- **GIVEN** the user obtained `x,y,width,height` from the ROI measurement helper
- **WHEN** the user passes that value to `scripts/auto_exporter.py --draft-roi`
- **THEN** the OCR/CV export flow uses the provided ROI instead of the default inferred region
