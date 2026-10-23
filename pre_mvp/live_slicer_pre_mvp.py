#!/usr/bin/env python3
"""Live Slicer pre-MVP: rolling webcam buffer and asynchronous H.264/MP4 export."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

import cv2

try:
    from .ffmpeg_bootstrap import ensure_ffmpeg
except ImportError:  # direct script execution from pre_mvp/
    from ffmpeg_bootstrap import ensure_ffmpeg


def parse_args():
    parser = argparse.ArgumentParser(description="Live Slicer webcam pre-MVP")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV webcam index")
    parser.add_argument("--duration", type=float, default=45.0, help="Maximum pre-event duration in seconds")
    parser.add_argument("--min-clip-seconds", type=float, default=10.0,
                        help="Minimum footage duration required to export (default: 10)")
    parser.add_argument("--fps", type=float, default=30.0, help="Export FPS")
    parser.add_argument("--width", type=int, default=1280, help="Requested webcam width")
    parser.add_argument("--height", type=int, default=720, help="Requested webcam height")
    parser.add_argument("--output", type=Path, default=Path("recordings"))
    parser.add_argument("--jpeg-quality", type=int, default=98, help="In-memory frame quality (1-100)")
    parser.add_argument("--h264-crf", type=int, default=18,
                        help="H.264 quality: lower is better; typical range 18-23 (default: 18)")
    parser.add_argument("--h264-preset", choices=("ultrafast", "superfast", "veryfast", "faster",
                        "fast", "medium", "slow", "slower", "veryslow"), default="medium",
                        help="libx264 speed/compression preset (default: medium)")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="FFmpeg executable path (default: ffmpeg on PATH)")
    parser.add_argument("--max-buffer-mib", type=int, default=512, help="RAM limit for the rolling buffer")
    return parser.parse_args()


def select_clip_window(frames, trigger_time, duration, min_clip_seconds=10.0, clip_start_time=None):
    """Select a pre-event window, or a non-overlapping segment after the previous clip."""
    if not frames:
        raise RuntimeError("No webcam frames are buffered yet.")
    start_limit = trigger_time - duration if clip_start_time is None else clip_start_time
    if clip_start_time is not None and frames[0][0] > clip_start_time + 0.1:
        raise RuntimeError(
            "Clip not saved: the previous clip's end is older than the available buffer; "
            "the segment cannot be exported without a gap."
        )
    eligible = [(timestamp, frame) for timestamp, frame in frames
                if start_limit <= timestamp <= trigger_time]
    if len(eligible) < 2:
        raise RuntimeError("Not enough webcam frames are buffered yet; keep the app running briefly and try again.")
    start_time = start_limit if clip_start_time is not None else eligible[0][0]
    actual_duration = max(0.0, trigger_time - start_time)
    if actual_duration < min_clip_seconds:
        remaining = max(0.0, min_clip_seconds - actual_duration)
        raise RuntimeError(
            f"Clip not saved: only {actual_duration:.1f}s since the previous clip; at least "
            f"{min_clip_seconds:.1f}s is required. Keep recording for {remaining:.1f}s more."
        )
    return eligible, start_time, actual_duration


def save_clip(frames, trigger_time, duration, fps, output_dir, ffmpeg="ffmpeg",
              h264_crf=18, h264_preset="medium", min_clip_seconds=10.0, clip_start_time=None):
    """Encode a stable frame snapshot to H.264 MP4 using FFmpeg."""
    executable = shutil.which(ffmpeg) if not Path(ffmpeg).is_file() else str(Path(ffmpeg))
    if executable is None:
        raise RuntimeError(
            f"FFmpeg executable not found ({ffmpeg!r}). Install FFmpeg and ensure it is on PATH, "
            "or pass --ffmpeg with its full path."
        )
    eligible, start_time, actual_duration = select_clip_window(
        frames, trigger_time, duration, min_clip_seconds=min_clip_seconds,
        clip_start_time=clip_start_time
    )
    first = cv2.imdecode(eligible[0][1], cv2.IMREAD_COLOR)
    if first is None:
        raise RuntimeError("Could not decode buffered webcam frame.")
    height, width = first.shape[:2]
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    output_path = output_dir / f"live_slicer_{stamp}.mp4"
    command = [
        executable, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pixel_format", "bgr24", "-video_size", f"{width}x{height}",
        "-framerate", str(fps), "-i", "pipe:0", "-an",
        "-c:v", "libx264", "-preset", h264_preset, "-crf", str(h264_crf),
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_path),
    ]
    process = None
    written = 0
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE)
        frame_count = max(2, int(round(actual_duration * fps)) + 1)
        idx = 0
        for frame_no in range(frame_count):
            target = start_time + frame_no / fps
            while idx + 1 < len(eligible) and eligible[idx + 1][0] <= target:
                idx += 1
            decoded = cv2.imdecode(eligible[idx][1], cv2.IMREAD_COLOR)
            if decoded is not None and decoded.shape[1::-1] == (width, height):
                process.stdin.write(decoded.tobytes())
                written += 1
        process.stdin.close()
        return_code = process.wait()
        if return_code != 0:
            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise RuntimeError(
                f"FFmpeg failed with exit code {return_code}. Check that this FFmpeg build includes libx264."
            )
    except (BrokenPipeError, OSError) as exc:
        if process is not None and process.poll() is None:
            process.kill()
        if process is not None:
            process.wait()
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(
            f"Could not stream frames to FFmpeg: {exc}. Check FFmpeg installation and libx264 support."
        ) from exc
    finally:
        if process is not None and process.stdin is not None and not process.stdin.closed:
            try:
                process.stdin.close()
            except OSError:
                pass
    if written < 2 or not output_path.exists() or output_path.stat().st_size == 0:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError("FFmpeg did not create a usable clip.")
    return output_path


class BackgroundExporter:
    """One background export at a time; prevents repeated keypresses queuing RAM-heavy snapshots."""

    def __init__(self, duration, min_clip_seconds, fps, output_dir, ffmpeg, h264_crf, h264_preset):
        self.duration = duration
        self.min_clip_seconds = min_clip_seconds
        self.fps = fps
        self.output_dir = output_dir
        self.ffmpeg = ffmpeg
        self.h264_crf = h264_crf
        self.h264_preset = h264_preset
        self.jobs = queue.Queue(maxsize=1)
        self.status = queue.Queue()
        self._lock = threading.Lock()
        self._pending = False
        self._thread = threading.Thread(target=self._run, name="LiveSlicerExporter", daemon=True)
        self._thread.start()

    def submit(self, frames, trigger_time, clip_start_time=None):
        with self._lock:
            if self._pending:
                return False
            self._pending = True
            try:
                self.jobs.put_nowait((frames, trigger_time, clip_start_time))
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
                frames, trigger_time, clip_start_time = job
                try:
                    path = save_clip(
                        frames, trigger_time, self.duration, self.fps, self.output_dir,
                        self.ffmpeg, self.h264_crf, self.h264_preset, self.min_clip_seconds,
                        clip_start_time
                    )
                    self.status.put(("success", str(path), trigger_time))
                except Exception as exc:
                    self.status.put(("error", str(exc), None))
                finally:
                    with self._lock:
                        self._pending = False
            finally:
                self.jobs.task_done()

    def close(self):
        self.jobs.join()
        self.jobs.put(None)
        self._thread.join()


def main():
    args = parse_args()
    if args.duration <= 0 or args.fps <= 0 or args.min_clip_seconds <= 0:
        raise SystemExit("--duration, --min-clip-seconds and --fps must be greater than zero")
    if args.min_clip_seconds > args.duration:
        raise SystemExit("--min-clip-seconds cannot be greater than --duration")
    if not 1 <= args.jpeg_quality <= 100:
        raise SystemExit("--jpeg-quality must be 1-100")
    if not 0 <= args.h264_crf <= 51:
        raise SystemExit("--h264-crf must be 0-51 (lower is higher quality)")
    if args.width <= 0 or args.height <= 0 or args.max_buffer_mib <= 0:
        raise SystemExit("--width, --height and --max-buffer-mib must be greater than zero")
    args.ffmpeg = ensure_ffmpeg(args.ffmpeg)

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
    exporter = BackgroundExporter(args.duration, args.min_clip_seconds, args.fps, args.output,
                                  args.ffmpeg, args.h264_crf, args.h264_preset)
    print(f"Live Slicer pre-MVP: camera={args.camera}, target={args.duration:.1f}s, "
          f"minimum clip={args.min_clip_seconds:.1f}s, resolution={actual_width}x{actual_height}, "
          f"fps={args.fps:g}, JPEG quality={args.jpeg_quality}, H.264 CRF={args.h264_crf}, "
          f"preset={args.h264_preset}")
    print(f"Buffer RAM limit: {args.max_buffer_mib} MiB. First SPACE saves up to "
          f"{args.duration:.0f}s before the event; later clips start exactly where the previous "
          f"saved clip ended and require at least {args.min_clip_seconds:.1f}s. Q/ESC quits.")
    last_clip_end = None
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
            ready = elapsed >= args.min_clip_seconds
            preview = frame.copy()
            status = f"Buffer: {shown_elapsed:05.1f}/{args.duration:.0f}s"
            color = (40, 200, 40) if ready else (0, 180, 255)
            cv2.putText(preview, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            second_line = (f"SPACE: save (min {args.min_clip_seconds:.0f}s) | "
                           f"RAM: {current_buffer_bytes / 1048576:.0f} MiB")
            if exporter.is_pending():
                second_line = "SAVING IN BACKGROUND | " + second_line
            elif not ready:
                second_line = f"WAIT {max(0.0, args.min_clip_seconds - elapsed):.1f}s | " + second_line
            cv2.putText(preview, second_line, (12, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                with buffer_lock:
                    snapshot = list(buffer)
                    trigger_time = time.monotonic()
                    clip_start_time = last_clip_end
                    if clip_start_time is not None and trigger_time - clip_start_time < args.min_clip_seconds:
                        interval = trigger_time - clip_start_time
                        print(f"Trigger ignored: only {interval:.1f}s since the previous clip; "
                              f"minimum is {args.min_clip_seconds:.1f}s.")
                        snapshot = None
                    else:
                        try:
                            select_clip_window(
                                snapshot, trigger_time, args.duration, args.min_clip_seconds,
                                clip_start_time=clip_start_time
                            )
                        except RuntimeError as exc:
                            print(str(exc))
                            snapshot = None
                if snapshot is not None:
                    if exporter.submit(snapshot, trigger_time, clip_start_time):
                        print("H.264 clip export started in background.")
                    else:
                        print("A clip is already being saved; this trigger was ignored.")

            while True:
                try:
                    kind, message, completed_trigger_time = exporter.status.get_nowait()
                except queue.Empty:
                    break
                if kind == "success":
                    last_clip_end = completed_trigger_time
                    print(f"Saved H.264 clip: {message}")
                else:
                    print(f"Could not save clip: {message}")
    finally:
        camera.release()
        cv2.destroyAllWindows()
        exporter.close()


if __name__ == "__main__":
    main()
