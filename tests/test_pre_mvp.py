"""Unit tests for the pre-MVP rolling-buffer selection logic."""
import pytest

from pre_mvp.live_slicer_pre_mvp import select_clip_window


def test_short_warmup_returns_available_frames():
    frames = [(10.0, b"a"), (10.1, b"b"), (10.2, b"c")]
    selected, start, duration = select_clip_window(frames, trigger_time=10.25, duration=45.0)
    assert selected == frames
    assert start == pytest.approx(10.0)
    assert duration == pytest.approx(0.25)


def test_full_buffer_is_trimmed_to_requested_window():
    frames = [(float(t), str(t).encode()) for t in range(0, 61)]
    selected, start, duration = select_clip_window(frames, trigger_time=60.0, duration=45.0)
    assert start == 15.0
    assert selected[0][0] == 15.0
    assert selected[-1][0] == 60.0
    assert duration == 45.0


def test_empty_buffer_has_actionable_error():
    with pytest.raises(RuntimeError, match="No webcam frames"):
        select_clip_window([], trigger_time=10.0, duration=45.0)


def test_single_frame_cannot_make_video():
    with pytest.raises(RuntimeError, match="Not enough webcam frames"):
        select_clip_window([(10.0, b"only")], trigger_time=10.1, duration=45.0)
