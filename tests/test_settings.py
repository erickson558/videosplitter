from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app_metadata import APP_VERSION
from backend import settings
from backend.models import EQUAL_PARTS_SPLIT_MODE


class SettingsTests(unittest.TestCase):
    def test_save_ui_settings_persists_version_and_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            with patch("backend.settings.runtime_root", return_value=runtime_root):
                settings.save_ui_settings(
                    split_mode=EQUAL_PARTS_SPLIT_MODE,
                    segment_seconds=60,
                    equal_parts_count=4,
                    video_profile="original",
                    container_format="mov",
                    processing_device="gpu_0",
                    output_dir="C:/exports",
                )

                payload = json.loads((runtime_root / "videosplitter.settings.json").read_text(encoding="utf-8"))
                self.assertEqual(payload["app_version"], APP_VERSION)
                self.assertEqual(payload["equal_parts_count"], 4)
                self.assertEqual(payload["processing_device"], "gpu_0")
                self.assertEqual(payload["output_dir"], "C:/exports")

    def test_get_ui_settings_falls_back_for_invalid_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_root = Path(temp_dir)
            settings_path = runtime_root / "videosplitter.settings.json"
            settings_path.write_text(
                json.dumps(
                    {
                        "split_mode": "invalid",
                        "segment_seconds": "abc",
                        "equal_parts_count": 0,
                        "video_profile": "short_9_16",
                        "container_format": "mp4",
                    }
                ),
                encoding="utf-8",
            )

            with patch("backend.settings.runtime_root", return_value=runtime_root):
                ui_settings = settings.get_ui_settings()

            self.assertEqual(ui_settings["split_mode"], "seconds")
            self.assertEqual(ui_settings["segment_seconds"], 60)
            self.assertEqual(ui_settings["equal_parts_count"], 2)


if __name__ == "__main__":
    unittest.main()