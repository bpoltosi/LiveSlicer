"""Unit tests for the pre-MVP rolling buffer and background exporter."""
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from pre_mvp.live_slicer_pre_mvp import BackgroundExporter, parse_args, select_clip_window


class ConfigurationTests(unittest.TestCase):
    def test_resource_aware_encoder_defaults(self):
        with patch.object(sys, "argv", ["live_slicer_pre_mvp.py"]):
            args = parse_args()
        self.assertEqual(args.h264_preset, "veryfast")
        self.assertEqual(args.h264_threads, 2)


class ClipWindowTests(unittest.TestCase):
    def test_clip_under_minimum_is_rejected(self):
        frames = [(10.0, b"a"), (10.1, b"b"), (19.0, b"c")]
        with self.assertRaisesRegex(RuntimeError, "at least 10.0s is required"):
            select_clip_window(frames, trigger_time=19.2, duration=45.0, min_clip_seconds=10.0)

    def test_clip_at_minimum_is_accepted(self):
        frames = [(float(t), str(t).encode()) for t in range(0, 11)]
        selected, start, duration = select_clip_window(
            frames, trigger_time=10.0, duration=45.0, min_clip_seconds=10.0
        )
        self.assertEqual(start, 0.0)
        self.assertEqual(selected[0][0], 0.0)
        self.assertEqual(selected[-1][0], 10.0)
        self.assertEqual(duration, 10.0)

    def test_full_buffer_is_trimmed_to_requested_window(self):
        frames = [(float(t), str(t).encode()) for t in range(0, 61)]
        selected, start, duration = select_clip_window(
            frames, trigger_time=60.0, duration=45.0, min_clip_seconds=10.0
        )
        self.assertEqual(start, 15.0)
        self.assertEqual(selected[0][0], 15.0)
        self.assertEqual(selected[-1][0], 60.0)
        self.assertEqual(duration, 45.0)

    def test_empty_buffer_has_actionable_error(self):
        with self.assertRaisesRegex(RuntimeError, "No webcam frames"):
            select_clip_window([], trigger_time=10.0, duration=45.0, min_clip_seconds=10.0)

    def test_single_frame_cannot_make_video(self):
        with self.assertRaisesRegex(RuntimeError, "Not enough webcam frames"):
            select_clip_window([(10.0, b"only")], trigger_time=10.1, duration=45.0, min_clip_seconds=10.0)


class BackgroundExporterTests(unittest.TestCase):
    def test_second_export_is_rejected_while_first_is_running(self):
        started = threading.Event()
        finish = threading.Event()

        def slow_export(*args, **kwargs):
            started.set()
            if not finish.wait(timeout=3):
                raise TimeoutError("test export timed out")
            return Path("fake.mp4")

        exporter = BackgroundExporter(
            45.0, 10.0, 30.0, Path("recordings"), "ffmpeg", 18, "medium"
        )
        try:
            with patch("pre_mvp.live_slicer_pre_mvp.save_clip", side_effect=slow_export):
                self.assertTrue(exporter.submit([(1.0, b"a"), (1.1, b"b")], 1.2))
                self.assertTrue(started.wait(timeout=2), "background worker did not start")
                self.assertFalse(exporter.submit([(1.0, b"a"), (1.1, b"b")], 1.2))
                finish.set()
                exporter.jobs.join()
                kind, message, completed_trigger_time = exporter.status.get(timeout=2)
                self.assertEqual(completed_trigger_time, 1.2)
                self.assertEqual(kind, "success")
                self.assertEqual(message, "fake.mp4")
        finally:
            finish.set()
            exporter.close()


if __name__ == "__main__":
    unittest.main()
