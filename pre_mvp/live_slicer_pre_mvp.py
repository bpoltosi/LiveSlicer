#!/usr/bin/env python3
"""Live Slicer pre-MVP: rolling webcam buffer and asynchronous MP4 export."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import queue
import threading
import time
from pathlib import Path

import cv2


def parse_args():
    parser = argparse.ArgumentParser(description="Live Slicer webcam pre-MVP")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV webcam index")
    parser.add_argument("--duration", type=float, default=45.0, help="Maximum pre-event duration in seconds")
    parser.add_argument("--fps", type=float, default=30.0, help="Export FPS")
    parser.add_argument("--width", type=int, default=1280, help="Requested webcam width")
    parser.add_argument("--height", type=int, default=720, help="Requested webcam height")
    parser.add_argument("--output", type=Path, default=Path("recordings"))
    parser.add_argument("--jpeg-quality", type=int, default=98, help="In-memory frame quality (1-100)")
    parser.add_argument("--video-quality", type=int, default=100,
                        help="Encoder quality hint (0-100; backend-dependent)")
    parser.add_argument("--max-buffer-mib", type=int, default=512, help="RAM limit for the rolling buffer")
    return parser.parse_args()


def select_clip_window(frames, trigger_time, duration):
    """Return available frames and actual window bounds, including warm-up clips."""
    if not frames:
        raise RuntimeError("No webcam frames are buffered yet.")
    start_limit = trigger_time - duration
    eligible = [(timestamp, frame) for timestamp, frame in frames
                if start_limit <= timestamp <= trigger_time]
    if len(eligible) < 2:
        raise RuntimeError("Not enough webcam frames yet; keep the app running briefly and try again.")
    start_time = eligible[0][0]
    actual_duration = min(duration, max(0.0, trigger_time - start_time))
    if actual_duration <= 0:
        raise RuntimeError("The buffered clip is too short to export.")
    return eligible, start_time, actual_duration


def save_clip(frames, trigger_time, duration, fps, output_dir, video_quality=100):
    """Encode a stable frame snapshot. Call from the background exporter, not the UI loop."""
    eligible, start_time, actual_duration = select_clip_window(frames, trigger_time, duration)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    output_path = output_dir / f"live_slicer_{stamp}.mp4"
    first = cv2.imdecode(eligible[0][1], cv2.IMREAD_COLOR)
    if first is None:
        raise RuntimeError("Could not decode buffered webcam frame.")
    height, width = first.shape[:2]
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not open MP4 writer; check OpenCV mp4v support.")
    try:
        try:
            quality_supported = writer.set(cv2.VIDEOWRITER_PROP_QUALITY, float(video_quality))
        except cv2.error:
            quality_supported = False
        if not quality_supported:
            print("Note: this OpenCV video backend does not expose an encoder quality control; using its default.")
        frame_count = max(2, int(round(actual_duration * fps)) + 1)
        idx = 0
        written = 0
        for frame_no in range(frame_count):
            target = start_time + frame_no / fps
            while idx + 1 < len(eligible) and eligible[idx + 1][0] <= target:
                idx += 1
            decoded = cv2.imdecode(eligible[idx][1], cv2.IMREAD_COLOR)
            if decoded is not None and decoded.shape[1::-1] == (width, height):
                writer.write(decoded)
                written += 1
    finally:
        writer.release()
    if written < 2:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError("Fewer than two frames could be encoded; no usable clip was created.")
    return output_path


class BackgroundExporter:
    """One background export at a time; prevents repeated keypresses from queuing RAM-heavy snapshots."""

    def __init__(self, duration, fps, output_dir, video_quality):
        self.duration = duration
        self.fps = fps
        self.output_dir = output_dir
        self.video_quality = video_quality
        self.jobs = queue.Queue(maxsize=1)
        self.status = queue.Queue()
        self._lock = threading.Lock()
        self._pending = False
        self._thread = threading.Thread(target=self._run, name="LiveSlicerExporter", daemon=True)
        self._thread.start()

    def submit(self, frames, trigger_time):
        with self._lock:
            if self._pending:
                return False
            self._pending = True
            try:
                self.jobs.put_nowait((frames, trigger_time))
            except queue.Full:
                self._pending = False
                return False
        return True

    def is_pending(self):
        with self._lock:
            return self._pending

    def _run(self):
        while True:
            job = self.jobs.get()
            try:
                if job is None:
                    return
                frames, trigger_time = job
                try:
                    path = save_clip(frames, trigger_time, self.duration, self.fps,
                                     self.output_dir, self.video_quality)
                    self.status.put(("success", str(path)))
                except Exception as exc:
                    self.status.put(("error", str(exc)))
                finally:
                    with self._lock:
                        self._pending = False
            finally:
                self.jobs.task_done()

    def close(self):
        # Finish an in-progress export before the process exits, avoiding a truncated MP4.
        self.jobs.join()
        self.jobs.put(None)
        self._thread.join()


def main():
    args = parse_args()
    if args.duration <= 0 or args.fps <= 0:
        raise SystemExit("--duration and --fps must be greater than zero")
    if not 1 <= args.jpeg_quality <= 100 or not 0 <= args.video_quality <= 100:
        raise SystemExit("--jpeg-quality must be 1-100 and --video-quality must be 0-100")
    if args.width <= 0 or args.height <= 0 or args.max_buffer_mib <= 0:
        raise SystemExit("--width, --height and --max-buffer-mib must be greater than zero")

    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        raise SystemExit(f"Could not open webcam index {args.camera}. Try --camera 1 or check permissions.")
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    actual_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if (actual_width, actual_height) != (args.width, args.height):
        print(f"Webcam selected {actual_width}x{actual_height} (requested {args.width}x{args.height}).")

    buffer = collections.deque()
    buffer_lock = threading.Lock()
    buffer_window = args.duration + 1.0
    max_buffer_bytes = args.max_buffer_mib * 1024 * 1024
    buffer_bytes = 0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), args.jpeg_quality]
    window_name = "Live Slicer pre-MVP — SPACE saves previous window | Q quits"
    exporter = BackgroundExporter(args.duration, args.fps, args.output, args.video_quality)
    print(f"Live Slicer pre-MVP: camera={args.camera}, target={args.duration:.1f}s, "
          f"resolution={actual_width}x{actual_height}, fps={args.fps:g}, JPEG quality={args.jpeg_quality}")
    print(f"Buffer RAM limit: {args.max_buffer_mib} MiB. SPACE saves available footage; Q/ESC quits.")
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    try:
        while True:
            ok, frame = camera.read()
            now = time.monotonic()
            if not ok or frame is None:
                print("Warning: webcam frame read failed; retrying.")
                key = cv2.waitKey(100) & 0xFF
                if key in (ord("q"), 27):
                    break
                continue

            encoded_ok, encoded = cv2.imencode(".jpg", frame, encode_params)
            with buffer_lock:
                if encoded_ok:
                    buffer.append((now, encoded))
                    buffer_bytes += encoded.nbytes
                cutoff = now - buffer_window
                while buffer and (buffer[0][0] < cutoff or buffer_bytes > max_buffer_bytes):
                    _, old_frame = buffer.popleft()
                    buffer_bytes -= old_frame.nbytes
                elapsed = now - buffer[0][0] if buffer else 0.0
                current_buffer_bytes = buffer_bytes

            shown_elapsed = min(elapsed, args.duration)
            ready = elapsed >= args.duration
            preview = frame.copy()
            status = f"Buffer: {shown_elapsed:05.1f}/{args.duration:.0f}s"
            color = (40, 200, 40) if ready else (0, 180, 255)
            cv2.putText(preview, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            second_line = f"SPACE: save footage | RAM: {current_buffer_bytes / 1048576:.0f} MiB"
            if exporter.is_pending():
                second_line = "SAVING IN BACKGROUND | " + second_line
            cv2.putText(preview, second_line, (12, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                with buffer_lock:
                    snapshot = list(buffer)
                    trigger_time = time.monotonic()
                if exporter.submit(snapshot, trigger_time):
                    print("Clip export started in background.")
                else:
                    print("A clip is already being saved; wait for it to finish before saving another.")

            while True:
                try:
                    kind, message = exporter.status.get_nowait()
                except queue.Empty:
                    break
                if kind == "success":
                    print(f"Saved clip: {message}")
                else:
                    print(f"Could not save clip: {message}")
    finally:
        camera.release()
        cv2.destroyAllWindows()
        exporter.close()


if __name__ == "__main__":
    main()
