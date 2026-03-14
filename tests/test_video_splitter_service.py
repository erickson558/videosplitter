from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.errors import SplitExecutionError
from backend.models import EQUAL_PARTS_SPLIT_MODE, SECONDS_SPLIT_MODE, SplitJobConfig
from backend.video_splitter_service import VideoSplitterService


class VideoSplitterServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = VideoSplitterService(ffmpeg_path=Path("ffmpeg.exe"), ffprobe_path=Path("ffprobe.exe"))

    def test_build_split_points_for_equal_parts(self) -> None:
        config = SplitJobConfig(
            input_video=Path("video.mp4"),
            output_dir=Path("out"),
            split_mode=EQUAL_PARTS_SPLIT_MODE,
            equal_parts_count=4,
        )

        split_points = self.service._build_split_points(config, 120.0)

        self.assertEqual(split_points, [30.0, 60.0, 90.0])

    def test_build_split_points_requires_duration(self) -> None:
        config = SplitJobConfig(
            input_video=Path("video.mp4"),
            output_dir=Path("out"),
            split_mode=EQUAL_PARTS_SPLIT_MODE,
            equal_parts_count=3,
        )

        with self.assertRaises(SplitExecutionError):
            self.service._build_split_points(config, None)

    def test_build_command_uses_segment_time_for_seconds_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = Path(temp_dir) / "video.mp4"
            output_dir = Path(temp_dir)
            input_video.write_bytes(b"video")
            config = SplitJobConfig(
                input_video=input_video,
                output_dir=output_dir,
                split_mode=SECONDS_SPLIT_MODE,
                segment_seconds=75,
            )

            command = self.service._build_command(config, output_dir / "video Parte %d.mp4", None)

            self.assertIn("-segment_time", command)
            self.assertIn("75", command)
            self.assertNotIn("-segment_times", command)

    def test_build_command_uses_segment_times_for_equal_parts_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = Path(temp_dir) / "video.mp4"
            output_dir = Path(temp_dir)
            input_video.write_bytes(b"video")
            config = SplitJobConfig(
                input_video=input_video,
                output_dir=output_dir,
                split_mode=EQUAL_PARTS_SPLIT_MODE,
                equal_parts_count=3,
            )

            command = self.service._build_command(
                config,
                output_dir / "video Parte %d.mp4",
                [40.0, 80.0],
            )

            self.assertIn("-segment_times", command)
            self.assertIn("40,80", command)
            self.assertNotIn("-segment_time", command)


if __name__ == "__main__":
    unittest.main()