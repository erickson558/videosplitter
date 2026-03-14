from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.errors import InvalidSplitConfigError
from backend.models import EQUAL_PARTS_SPLIT_MODE, SECONDS_SPLIT_MODE, SplitJobConfig


class SplitJobConfigTests(unittest.TestCase):
    def test_validates_seconds_mode_and_creates_output_dir(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = Path(temp_dir) / "input.mp4"
            output_dir = Path(temp_dir) / "out"
            input_video.write_bytes(b"video")

            validated = SplitJobConfig(
                input_video=input_video,
                output_dir=output_dir,
                split_mode=SECONDS_SPLIT_MODE,
                segment_seconds=45,
            ).validated()

            self.assertEqual(validated.segment_seconds, 45)
            self.assertTrue(output_dir.exists())

    def test_equal_parts_requires_more_than_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = Path(temp_dir) / "input.mp4"
            input_video.write_bytes(b"video")

            with self.assertRaises(InvalidSplitConfigError):
                SplitJobConfig(
                    input_video=input_video,
                    output_dir=Path(temp_dir) / "out",
                    split_mode=EQUAL_PARTS_SPLIT_MODE,
                    equal_parts_count=1,
                ).validated()


if __name__ == "__main__":
    unittest.main()