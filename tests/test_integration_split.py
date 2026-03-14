from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.models import SECONDS_SPLIT_MODE, SplitJobConfig
from backend.video_splitter_service import VideoSplitterService


def _candidate_binary_paths(binary_name: str) -> list[Path]:
    project_root = Path(__file__).resolve().parents[1]
    candidates = [
        project_root / "third_party" / "ffmpeg" / f"{binary_name}.exe",
        project_root / "third_party" / "ffmpeg" / binary_name,
    ]

    from_path = shutil.which(binary_name)
    if from_path:
        candidates.append(Path(from_path))

    return candidates


def _find_binary(binary_name: str) -> Path | None:
    for candidate in _candidate_binary_paths(binary_name):
        if candidate.exists():
            return candidate.resolve()
    return None


class VideoSplitterIntegrationTests(unittest.TestCase):
    def test_split_video_seconds_mode_with_generated_input(self) -> None:
        ffmpeg_path = _find_binary("ffmpeg")
        ffprobe_path = _find_binary("ffprobe")
        if ffmpeg_path is None:
            self.skipTest("FFmpeg no disponible en el entorno de pruebas")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            input_video = temp_root / "integration_input.mp4"
            output_dir = temp_root / "out"

            create_source_command = [
                str(ffmpeg_path),
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=640x360:rate=30",
                "-t",
                "3",
                "-pix_fmt",
                "yuv420p",
                str(input_video),
            ]
            subprocess.run(create_source_command, check=True)

            service = VideoSplitterService(ffmpeg_path=ffmpeg_path, ffprobe_path=ffprobe_path)
            config = SplitJobConfig(
                input_video=input_video,
                output_dir=output_dir,
                split_mode=SECONDS_SPLIT_MODE,
                segment_seconds=1,
                video_profile="original",
                container_format="mp4",
            )

            output_files = service.split_video(config)
            self.assertGreaterEqual(len(output_files), 2)
            self.assertTrue(all(file.exists() for file in output_files))


if __name__ == "__main__":
    unittest.main()