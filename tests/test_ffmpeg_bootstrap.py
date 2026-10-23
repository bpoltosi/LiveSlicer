"""Tests for FFmpeg startup checks without running a real package installer."""
import unittest
from unittest.mock import patch

from pre_mvp import ffmpeg_bootstrap


class FfmpegBootstrapTests(unittest.TestCase):
    def test_existing_ffmpeg_with_libx264_is_reused(self):
        with patch.object(ffmpeg_bootstrap, "_find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
                patch.object(ffmpeg_bootstrap, "_has_libx264", return_value=True):
            self.assertEqual(ffmpeg_bootstrap.ensure_ffmpeg("ffmpeg"), "/usr/bin/ffmpeg")

    def test_existing_ffmpeg_without_libx264_stops_with_clear_error(self):
        with patch.object(ffmpeg_bootstrap, "_find_ffmpeg", return_value="/usr/bin/ffmpeg"), \
                patch.object(ffmpeg_bootstrap, "_has_libx264", return_value=False):
            with self.assertRaisesRegex(SystemExit, "libx264"):
                ffmpeg_bootstrap.ensure_ffmpeg("ffmpeg")

    def test_declining_install_does_not_run_installer(self):
        with patch.object(ffmpeg_bootstrap, "_find_ffmpeg", return_value=None), \
                patch.object(ffmpeg_bootstrap, "_installer_command", return_value=["fake-installer"]), \
                patch("builtins.input", return_value="n"), \
                patch.object(ffmpeg_bootstrap.subprocess, "run") as run:
            with self.assertRaises(SystemExit):
                ffmpeg_bootstrap.ensure_ffmpeg("ffmpeg")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
