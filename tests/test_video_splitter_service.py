from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.errors import SplitCancelledError, SplitExecutionError
from backend.models import EQUAL_PARTS_SPLIT_MODE, SECONDS_SPLIT_MODE, SplitJobConfig
from backend.video_splitter_service import VideoSplitterService


class VideoSplitterServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = VideoSplitterService(ffmpeg_path=Path("ffmpeg.exe"), ffprobe_path=Path("ffprobe.exe"))
        self.service._preferred_video_encoder = "libx264"

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
            self.assertIn("libx264", command)

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

    def test_build_command_uses_gpu_encoder_when_requested(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = Path(temp_dir) / "video.mp4"
            output_dir = Path(temp_dir)
            input_video.write_bytes(b"video")
            config = SplitJobConfig(
                input_video=input_video,
                output_dir=output_dir,
                split_mode=SECONDS_SPLIT_MODE,
                segment_seconds=30,
            )

            command = self.service._build_command(
                config,
                output_dir / "video Parte %d.mp4",
                None,
                video_encoder="h264_nvenc",
            )

            self.assertIn("h264_nvenc", command)

    def test_build_command_maps_gpu_index_for_nvenc(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = Path(temp_dir) / "video.mp4"
            output_dir = Path(temp_dir)
            input_video.write_bytes(b"video")
            config = SplitJobConfig(
                input_video=input_video,
                output_dir=output_dir,
                split_mode=SECONDS_SPLIT_MODE,
                segment_seconds=30,
                processing_device="gpu_1",
            )

            command = self.service._build_command(
                config,
                output_dir / "video Parte %d.mp4",
                None,
                video_encoder="h264_nvenc",
            )

            self.assertIn("-gpu", command)
            self.assertIn("1", command)

    def test_build_command_uses_gpu_any_for_all_gpu_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            input_video = Path(temp_dir) / "video.mp4"
            output_dir = Path(temp_dir)
            input_video.write_bytes(b"video")
            config = SplitJobConfig(
                input_video=input_video,
                output_dir=output_dir,
                split_mode=SECONDS_SPLIT_MODE,
                segment_seconds=30,
                processing_device="gpu_all",
            )

            command = self.service._build_command(
                config,
                output_dir / "video Parte %d.mp4",
                None,
                video_encoder="h264_nvenc",
            )

            gpu_index = command.index("-gpu")
            self.assertEqual(command[gpu_index + 1], "any")

    def test_detect_processing_options_without_ffmpeg_returns_safe_defaults(self) -> None:
        options = VideoSplitterService.detect_processing_options(Path("missing_ffmpeg.exe"))
        option_keys = [item[0] for item in options]

        self.assertEqual(option_keys, ["auto", "cpu"])

    def test_detect_processing_options_includes_intel_qsv_only_when_intel_adapter_exists(self) -> None:
        with patch.object(VideoSplitterService, "_read_encoders_output", return_value="V..... h264_qsv"):
            with patch.object(VideoSplitterService, "_detect_display_adapters", return_value=["Intel Iris Xe"]):
                options = VideoSplitterService.detect_processing_options(Path("ffmpeg.exe"))

        option_keys = [item[0] for item in options]
        self.assertIn("gpu_qsv", option_keys)

    def test_detect_processing_options_omits_amd_when_no_amd_adapter_exists(self) -> None:
        with patch.object(VideoSplitterService, "_read_encoders_output", return_value="V..... h264_amf"):
            with patch.object(VideoSplitterService, "_detect_display_adapters", return_value=["Intel UHD"]):
                options = VideoSplitterService.detect_processing_options(Path("ffmpeg.exe"))

        option_keys = [item[0] for item in options]
        self.assertNotIn("gpu_amf", option_keys)

    def test_detect_processing_options_includes_nvidia_auto_when_nvidia_adapter_exists(self) -> None:
        with patch.object(VideoSplitterService, "_read_encoders_output", return_value="V..... h264_nvenc"):
            with patch.object(VideoSplitterService, "_detect_nvidia_gpus", return_value=[]):
                with patch.object(VideoSplitterService, "_detect_display_adapters", return_value=["NVIDIA RTX 4070"]):
                    options = VideoSplitterService.detect_processing_options(Path("ffmpeg.exe"))

        option_map = dict(options)
        self.assertIn("gpu_all", option_map)
        self.assertIn("any", option_map["gpu_all"].lower())

    def test_detect_processing_options_includes_hybrid_when_nvenc_and_amf_with_mixed_adapters(self) -> None:
        with patch.object(
            VideoSplitterService,
            "_read_encoders_output",
            return_value="V..... h264_nvenc\nV..... h264_amf\n",
        ):
            with patch.object(VideoSplitterService, "_detect_nvidia_gpus", return_value=[(0, "RTX 2050")]):
                with patch.object(
                    VideoSplitterService,
                    "_detect_display_adapters",
                    return_value=["NVIDIA GeForce RTX 2050", "AMD Radeon(TM) Graphics"],
                ):
                    options = VideoSplitterService.detect_processing_options(Path("ffmpeg.exe"))

        option_keys = [item[0] for item in options]
        self.assertIn("gpu_hybrid", option_keys)

    def test_segment_ranges_for_seconds_mode(self) -> None:
        config = SplitJobConfig(
            input_video=Path("video.mp4"),
            output_dir=Path("out"),
            split_mode=SECONDS_SPLIT_MODE,
            segment_seconds=30,
        )

        segments = self.service._segment_ranges(config, 95.0)

        self.assertEqual(segments, [(1, 0.0, 30.0), (2, 30.0, 60.0), (3, 60.0, 90.0), (4, 90.0, 95.0)])

    def test_select_video_encoder_prefers_nvenc_then_qsv_then_amf(self) -> None:
        selected_nvenc = self.service._select_video_encoder(" V..... h264_qsv\n V..... h264_nvenc\n")
        selected_qsv = self.service._select_video_encoder(" V..... h264_qsv\n")
        selected_amf = self.service._select_video_encoder(" V..... h264_amf\n")
        selected_cpu = self.service._select_video_encoder(" V..... libx264\n")

        self.assertEqual(selected_nvenc, "h264_nvenc")
        self.assertEqual(selected_qsv, "h264_qsv")
        self.assertEqual(selected_amf, "h264_amf")
        self.assertEqual(selected_cpu, "libx264")

    def test_cancel_current_job_returns_false_when_idle(self) -> None:
        self.assertFalse(self.service.cancel_current_job())

    def test_cancel_current_job_terminates_active_process(self) -> None:
        class DummyProcess:
            def __init__(self) -> None:
                self._terminated = False

            def poll(self) -> None:
                return None

            def terminate(self) -> None:
                self._terminated = True

        process = DummyProcess()
        with self.service._process_lock:
            self.service._active_process = process
            self.service._active_processes = {process}

        self.assertTrue(self.service.cancel_current_job())
        self.assertTrue(process._terminated)

    def test_run_ffmpeg_raises_cancelled_if_requested_before_spawn(self) -> None:
        self.service._cancel_requested.set()

        with patch("subprocess.Popen") as popen:
            with self.assertRaisesRegex(SplitCancelledError, "cancelada"):
                self.service._run_ffmpeg(["ffmpeg", "-version"], None, None)

        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()