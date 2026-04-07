# Changelog

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

