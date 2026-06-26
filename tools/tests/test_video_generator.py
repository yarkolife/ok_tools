from __future__ import annotations
from django.test import SimpleTestCase
from tools.services.video_generator import VideoGenerator
from tools.services.video_generator import VideoGeneratorError
from unittest.mock import patch
import subprocess


class VideoGeneratorValidationTest(SimpleTestCase):
    def setUp(self):
        self.generator = VideoGenerator.__new__(VideoGenerator)

    def test_video_encoder_args_force_h264_level_4_1(self):
        self.generator.video_bitrate = "5000k"
        self.generator.gop = 50

        args = self.generator.video_encoder_args("libx264")

        self.assertEqual(args[args.index("-level:v") + 1], "4.1")

    @patch.object(VideoGenerator, "_resolve_binary_path", return_value="/usr/bin/ffmpeg")
    @patch("tools.services.video_generator.subprocess.run")
    def test_validate_binary_retries_after_initial_timeout(self, run_mock, resolve_binary_mock):
        run_mock.side_effect = [
            subprocess.TimeoutExpired(cmd=["/usr/bin/ffmpeg", "-nostdin", "-version"], timeout=10),
            subprocess.CompletedProcess(
                args=["/usr/bin/ffmpeg", "-nostdin", "-version"],
                returncode=0,
                stdout="ffmpeg version 7.0",
                stderr="",
            ),
        ]

        self.generator._validate_binary("ffmpeg", "FFmpeg")

        resolve_binary_mock.assert_called_once_with("ffmpeg")
        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(run_mock.call_args_list[0].args[0], ["/usr/bin/ffmpeg", "-nostdin", "-version"])
        self.assertEqual(run_mock.call_args_list[0].kwargs["timeout"], 10)
        self.assertEqual(run_mock.call_args_list[1].kwargs["timeout"], 30)

    @patch.object(VideoGenerator, "_resolve_binary_path", return_value=None)
    def test_validate_binary_raises_when_executable_is_missing(self, resolve_binary_mock):
        with self.assertRaisesMessage(
            VideoGeneratorError,
            "FFmpeg executable not found: /usr/local/bin/ffmpeg",
        ):
            self.generator._validate_binary("/usr/local/bin/ffmpeg", "FFmpeg")

        resolve_binary_mock.assert_called_once_with("/usr/local/bin/ffmpeg")

    @patch.object(VideoGenerator, "_resolve_binary_path", return_value="/usr/bin/ffprobe")
    @patch("tools.services.video_generator.subprocess.run")
    def test_validate_binary_uses_plain_version_for_ffprobe(self, run_mock, resolve_binary_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["/usr/bin/ffprobe", "-version"],
            returncode=0,
            stdout="ffprobe version 7.0",
            stderr="",
        )

        self.generator._validate_binary("ffprobe", "FFprobe")

        resolve_binary_mock.assert_called_once_with("ffprobe")
        self.assertEqual(run_mock.call_args.args[0], ["/usr/bin/ffprobe", "-version"])

    @patch.object(VideoGenerator, "_resolve_binary_path", return_value="/usr/bin/ffmpeg")
    @patch("tools.services.video_generator.subprocess.run")
    def test_validate_binary_includes_probe_output_on_nonzero_exit(self, run_mock, resolve_binary_mock):
        run_mock.return_value = subprocess.CompletedProcess(
            args=["/usr/bin/ffmpeg", "-nostdin", "-version"],
            returncode=1,
            stdout="",
            stderr="broken shared library",
        )

        with self.assertRaisesMessage(
            VideoGeneratorError,
            "FFmpeg not working: ffmpeg (exit 1): broken shared library",
        ):
            self.generator._validate_binary("ffmpeg", "FFmpeg")

        resolve_binary_mock.assert_called_once_with("ffmpeg")
