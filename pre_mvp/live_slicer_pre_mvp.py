#!/usr/bin/env python3
"""Live Slicer pre-MVP: rolling webcam buffer and Space-triggered MP4 export."""
from __future__ import annotations

import argparse
import collections
import datetime as dt
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
    parser.add_argument("--jpeg-quality", type=int, default=95, help="In-memory frame quality (1-100)")
    parser.add_argument("--video-quality", type=int, default=95, help="Encoder quality hint (0-100; backend-dependent)")
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
    # Do not require the full requested duration: save everything available during warm-up.
    start_time = eligible[0][0]
    actual_duration = min(duration, max(0.0, trigger_time - start_time))
    # A clip shorter than one frame interval is not a useful/decodable video.
    if actual_duration <= 0:
        raise RuntimeError("The buffered clip is too short to export.")
    return eligible, start_time, actual_duration


def save_clip(frames, trigger_time, duration, fps, output_dir, video_quality=95):
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
    quality_supported = writer.set(cv2.VIDEOWRITER_PROP_QUALITY, float(video_quality))
    if not quality_supported:
        print("Note: this OpenCV video backend does not expose an encoder quality control; using its default.")
    # Include the endpoint frame count; this also works for clips shorter than the target duration.
    frame_count = max(2, int(round(actual_duration * fps)))
    idx = 0
    written = 0
    try:
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
    buffer_window = args.duration + 1.0
    max_buffer_bytes = args.max_buffer_mib * 1024 * 1024
    buffer_bytes = 0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), args.jpeg_quality]
    window_name = "Live Slicer pre-MVP — SPACE saves previous window | Q quits"
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
            if encoded_ok:
                buffer.append((now, encoded))
                buffer_bytes += encoded.nbytes
            cutoff = now - buffer_window
            while buffer and (buffer[0][0] < cutoff or buffer_bytes > max_buffer_bytes):
                _, old_frame = buffer.popleft()
                buffer_bytes -= old_frame.nbytes

            elapsed = now - buffer[0][0] if buffer else 0.0
            shown_elapsed = min(elapsed, args.duration)
            ready = elapsed >= args.duration
            preview = frame.copy()
            status = f"Buffer: {shown_elapsed:05.1f}/{args.duration:.0f}s"
            color = (40, 200, 40) if ready else (0, 180, 255)
            cv2.putText(preview, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(preview, f"SPACE: save available footage | RAM: {buffer_bytes / 1048576:.0f} MiB",
                        (12, 56), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                try:
                    output_path = save_clip(list(buffer), time.monotonic(), args.duration, args.fps,
                                            args.output, args.video_quality)
                    print(f"Saved clip (available pre-event footage): {output_path}")
                except Exception as exc:
                    print(f"Could not save clip: {exc}")
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
