# Copyright (C) 2022, Benjamin Drung <bdrung@posteo.de>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
# REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
# AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
# LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
# OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
# PERFORMANCE OF THIS SOFTWARE.

"""Test timelapse."""

import errno
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock

from .scripts.timelapse import Size, generate_timelapse, main, parse_args

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


class TestSize(unittest.TestCase):
    # pylint: disable=missing-function-docstring
    """Test Size class."""

    def test_from_image(self) -> None:
        self.assertEqual(Size.from_image(FIXTURES / "black_vga.jpg"), Size(640, 480))

    def test_from_str(self) -> None:
        self.assertEqual(Size.from_str("1920x1080"), Size(1920, 1080))

    def test_from_str_invalid(self) -> None:
        with self.assertRaisesRegex(ValueError, "is not in the format"):
            Size.from_str("1024")

    def test_str(self) -> None:
        self.assertEqual(str(Size(1920, 1080)), "1920x1080")

    def test_crop_horizontal(self) -> None:
        """Crop 3:2 to 9:16."""
        size = Size(6000, 4000)
        output_size = Size(1080, 1920)
        self.assertEqual(size.resolution_crop(output_size), Size(2250, 4000))

    def test_crop_vertical(self) -> None:
        """Crop 3:2 to 16:9."""
        size = Size(6000, 4000)
        output_size = Size(1920, 1080)
        self.assertEqual(size.resolution_crop(output_size), Size(6000, 3375))


class TestTimelapse(unittest.TestCase):
    # pylint: disable=missing-function-docstring
    """Test timelapse."""

    @unittest.mock.patch("subprocess.run")
    def test_generate_timelapse(self, run_mock: unittest.mock.MagicMock) -> None:
        """Basic test case for generate_timelapse()."""
        run_mock.return_value = subprocess.CompletedProcess(
            unittest.mock.MagicMock(), 0, None, None
        )
        expected_cmd = [
            "ffmpeg",
            "-r",
            "24",
            "-f",
            "image2",
            "-pattern_type",
            "glob",
            "-i",
            "./*.jpg",
            "-filter:v",
            "crop=6000:3375:0:312,scale=1920:1080",
            "-vcodec",
            "libx264",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-profile:v",
            "high",
            "output_name",
        ]
        args = parse_args([])
        returncode = generate_timelapse(
            args, pathlib.Path("output_name"), Size(1920, 1080), Size(6000, 4000)
        )
        self.assertEqual(returncode, 0)
        run_mock.assert_called_once_with(expected_cmd, check=False)

    @unittest.mock.patch("subprocess.run")
    def test_ffmpeg_missing(self, run_mock: unittest.mock.MagicMock) -> None:
        """Basic test case for generate_timelapse()."""
        run_mock.side_effect = FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), "ffmpeg")
        args = parse_args([])

        with self.assertLogs(level="WARNING") as context_manager:
            returncode = generate_timelapse(
                args, pathlib.Path("output_name"), Size(1920, 1080), Size(6000, 4000)
            )
        self.assertEqual(len(context_manager.output), 1, context_manager.output)
        self.assertRegex(
            context_manager.output[0], "^ERROR.*ffmpeg not found. Please install ffmpeg!$"
        )
        self.assertEqual(returncode, 1)
        run_mock.assert_called_once()

    def test_input_directory_is_not_a_directory(self) -> None:
        with self.assertRaisesRegex(SystemExit, "^2$"):
            parse_args(["-d", "/non-existing"])

    @unittest.mock.patch("subprocess.run")
    def test_main(self, run_mock: unittest.mock.MagicMock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            unittest.mock.MagicMock(), 0, None, None
        )
        with tempfile.TemporaryDirectory() as tempdir:
            input_dir = pathlib.Path(tempdir) / "Input directory"
            input_dir.mkdir()
            expected_cmd = [
                "ffmpeg",
                "-r",
                "24",
                "-f",
                "image2",
                "-pattern_type",
                "glob",
                "-i",
                f"{input_dir}/*.jpg",
                "-filter:v",
                "crop=640:360:0:60,scale=1920:1080",
                "-vcodec",
                "libx264",
                "-crf",
                "17",
                "-pix_fmt",
                "yuv420p",
                "-profile:v",
                "high",
                "Input_directory_1920x1080_24fps_libx264_crf17.mp4",
            ]
            shutil.copy(FIXTURES / "black_vga.jpg", input_dir)
            self.assertEqual(main(["-d", str(input_dir), "--crf", "17"]), 0)
        run_mock.assert_called_once_with(expected_cmd, check=False)

    def test_no_input_images(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            self.assertEqual(main(["-d", tempdir]), 1)

    def test_output_directory_is_not_a_directory(self) -> None:
        with self.assertRaisesRegex(SystemExit, "^2$"):
            parse_args(["-o", "/non-existing"])

    @unittest.mock.patch("subprocess.run")
    def test_output_video_exists(self, run_mock: unittest.mock.MagicMock) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            input_dir = pathlib.Path(tempdir) / "Input directory"
            input_dir.mkdir()
            shutil.copy(FIXTURES / "black_vga.jpg", input_dir)
            output_video = pathlib.Path(tempdir) / "output_1920x1080_24fps_libx264_crf23.mp4"
            output_video.touch()
            self.assertEqual(
                main(["-d", str(input_dir), "-o", str(output_video.parent), "-n", "output"]), 0
            )
        run_mock.assert_not_called()
