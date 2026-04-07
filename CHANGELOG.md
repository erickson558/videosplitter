# Changelog

## V1.5.1 - 2026-04-07

- Release message: fix: add windows-style menu shortcuts, exit button, and non-intrusive GUI notifications
- Compare: https://github.com/erickson558/videosplitter/compare/v1.5.0...v1.5.1

### Fixes
- fix: add menu bar with Windows-style accelerators for key actions (open, start, cancel, exit, about)
- fix: add explicit Exit button in main action row
- fix: remove tkinter messagebox usage from operational flow and use status-based feedback

### Validation
- test: run full regression suite after GUI behavior updates (25 tests)

## V1.5.0 - 2026-04-07

- Release message: feat: add NVIDIA+AMD hybrid multiprocess encoding mode
- Compare: https://github.com/erickson558/videosplitter/compare/v1.4.0...v1.5.0

### Features
- feat: add new processing option in GUI for hybrid NVIDIA+AMD multiprocess encoding
- feat: distribute video segments across NVENC and AMF encoders in parallel when both are available
- feat: keep cancellation behavior and safe fallback to standard flow when hybrid mode cannot be used

### Tests
- test: add coverage for hybrid option detection and segment range generation in multiprocess mode

## V1.4.0 - 2026-04-07

- Release message: feat: add bilingual GUI support and all-GPU NVENC mode
- Compare: https://github.com/erickson558/videosplitter/compare/v1.3.2...v1.4.0

### Features
- feat: add multilingual GUI support (Espanol/English) with persisted language preference
- feat: add explicit NVIDIA all-GPU mode using `-gpu any` for FFmpeg NVENC

### Tests
- test: extend settings tests for language persistence
- test: add command generation test for NVENC all-GPU mode

## V1.3.2 - 2026-04-07

- Release message: fix: improve right-panel label readability and prevent option clipping
- Compare: https://github.com/erickson558/videosplitter/compare/v1.3.1...v1.3.2

### Fixes
- fix: increase contrast and font clarity for option labels and hints in the configuration panel
- fix: widen and rebalance layout to avoid clipped option labels and combobox content

### Validation
- test: run full suite after UI readability patch (22 tests)

## V1.3.1 - 2026-04-07

- Release message: fix: improve label contrast and persist selected input video in UI settings
- Compare: https://github.com/erickson558/videosplitter/compare/v1.3.0...v1.3.1

### Fixes
- fix: increase label and hint contrast in the desktop GUI for better readability
- fix: persist and restore the last selected input video path along with existing UI settings

### Tests
- test: extend settings persistence coverage to include input video field

## V1.3.0 - 2026-04-07

- Release message: feat: redesign desktop UI with structured cards and stronger visual hierarchy
- Compare: https://github.com/erickson558/videosplitter/compare/v1.2.1...v1.3.0

### Features
- feat: redesign main window into two responsive panels (Origen y Salida / Configuracion)
- feat: improve visual hierarchy with custom palette, typography and grouped controls for better usability
- feat: add clearer progress/status action zone with stronger primary and cancel button styling

### Validation
- test: run full suite after UI refactor to ensure no functional regressions

## V1.2.1 - 2026-04-07

- Release message: fix: harden ffmpeg cancellation lifecycle and rebuild executable (V1.2.1)
- Compare: https://github.com/erickson558/videosplitter/compare/v1.2.0...v1.2.1

### Fixes
- fix: ensure canceled conversions terminate and wait for FFmpeg process to avoid orphaned subprocesses

### Build and CI
- build: install tkinterdnd2 dependency and recompile VideoSplitter.exe with local .ico in project root

## V1.2.0 - 2026-04-07

- Release message: feat: add drag-and-drop UX, cancellation control, and adapter-aware GPU selection
- Compare: https://github.com/erickson558/videosplitter/compare/v1.1.3...v1.2.0

### Features
- feat: add drag-and-drop input zone in the GUI to load source videos without opening a file dialog
- feat: add Cancel button to stop active conversions and release FFmpeg process safely
- feat: display processed and pending percentages while the conversion is running
- feat: improve GPU detection by correlating FFmpeg encoder support with installed display adapters

### Tests
- test: add coverage for cancellation lifecycle and adapter-aware GPU option detection

## V1.1.3 - 2026-03-16

- Release message: fix: harden processing device label initialization during app startup
- Compare: https://github.com/erickson558/videosplitter/compare/v1.1.2...v1.1.3

### Fixes
- fix: make processing device label resolution safe even if the UI option dictionaries are not initialized yet
- fix: validate startup path by instantiating the Tkinter app before release

## V1.1.2 - 2026-03-16

- Release message: fix: initialize processing device lookup before status_var in main window
- Compare: https://github.com/erickson558/videosplitter/compare/v1.1.1...v1.1.2

### Fixes
- fix: move _processing_value_to_label initialization before status_var creation to resolve AttributeError on startup

## V1.1.1 - 2026-03-16

- Release message: build: compile release exe and expand documentation to project best practices
- Compare: https://github.com/erickson558/videosplitter/compare/v1.1.0...v1.1.1

### Build and CI
- build: recompile VideoSplitter.exe with V1.1.1 metadata using local .ico

### Documentation
- docs: rewrite README with feature table, GPU config guide, project structure, contributing section and Apache 2.0 badge
- docs: add CONTRIBUTING.md with commit conventions, test map and workflow guide

## V1.1.0 - 2026-03-16

- Release message: feat: add GPU device selector with automatic CPU fallback
- Compare: https://github.com/erickson558/videosplitter/compare/v1.0.4...v1.1.0

### Features
- feat: add GPU device selector in the desktop app (auto, CPU, NVIDIA per GPU, Intel QSV, AMD AMF)
- feat: use hardware encoder when available and retry automatically with CPU if GPU encode fails

### Tests
- test: cover GPU option detection defaults and explicit NVENC GPU index mapping

## V1.0.4 - 2026-03-13

- Release message: feat: add badges, integration test, and typed changelog release notes
- Compare: https://github.com/erickson558/videosplitter/compare/v1.0.3...v1.0.4

### Features
- feat: add badges, integration test, and typed changelog release notes

All notable changes to this project will be documented in this file.

