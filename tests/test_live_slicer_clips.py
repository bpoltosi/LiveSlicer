"""Tests for non-overlapping clip-window selection."""
import unittest

from pre_mvp.live_slicer_pre_mvp import select_clip_window


class ClipWindowTests(unittest.TestCase):
    def setUp(self):
        # Frame payloads are opaque here; selection only needs timestamps and references.
        self.frames = [(float(t), object()) for t in range(0, 31)]

    def test_first_clip_uses_pre_event_window(self):
        selected, start, duration = select_clip_window(
            self.frames, trigger_time=30.0, duration=15.0, min_clip_seconds=10.0
        )
        self.assertEqual(start, 15.0)
        self.assertEqual(duration, 15.0)
        self.assertEqual(selected[0][0], 15.0)
        self.assertEqual(selected[-1][0], 30.0)

    def test_followup_clip_starts_at_previous_clip_end(self):
        selected, start, duration = select_clip_window(
            self.frames, trigger_time=20.0, duration=15.0,
            min_clip_seconds=10.0, clip_start_time=10.0
        )
        self.assertEqual(start, 10.0)
        self.assertEqual(duration, 10.0)
        self.assertEqual(selected[0][0], 10.0)
        self.assertEqual(selected[-1][0], 20.0)

    def test_followup_clip_shorter_than_minimum_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "at least 10.0s"):
            select_clip_window(
                self.frames, trigger_time=19.9, duration=15.0,
                min_clip_seconds=10.0, clip_start_time=10.0
            )

    def test_followup_clip_rejects_missing_start_from_buffer(self):
        with self.assertRaisesRegex(RuntimeError, "older than the available buffer"):
            select_clip_window(
                self.frames[15:], trigger_time=30.0, duration=15.0,
                min_clip_seconds=10.0, clip_start_time=10.0
            )


if __name__ == "__main__":
    unittest.main()
