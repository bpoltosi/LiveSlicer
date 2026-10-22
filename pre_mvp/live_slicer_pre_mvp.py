#!/usr/bin/env python3
"""Live Slicer pre-MVP: webcam preview + Space-triggered 45-second pre-event clip."""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import time
from pathlib import Path
import cv2

def parse_args():
    parser = argparse.ArgumentParser(description="Live Slicer webcam pre-MVP")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV webcam index (default: 0)")
    parser.add_argument("--duration", type=float, default=45.0, help="Seconds to save before Space")
    parser.add_argument("--fps", type=float, default=20.0, help="FPS of exported MP4")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--output", type=Path, default=Path("recordings"))
    parser.add_argument("--jpeg-quality", type=int, default=80)
    return parser.parse_args()

def save_clip(frames, trigger_time, duration, fps, output_dir):
    start_time = trigger_time - duration
    eligible = [(t, jpg) for t, jpg in frames if start_time <= t <= trigger_time]
    if len(eligible) < 2 or eligible[0][0] > start_time + 1.0:
        raise RuntimeError("Full pre-event buffer is not ready; keep the app running.")
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_path = output_dir / f"live_slicer_{stamp}.mp4"
    first = cv2.imdecode(eligible[0][1], cv2.IMREAD_COLOR)
    if first is None:
        raise RuntimeError("Could not decode buffered webcam frame.")
    height, width = first.shape[:2]
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not open MP4 writer; check OpenCV mp4v support.")
    idx = 0
    try:
        count = max(1, int(round(duration * fps)))
        for frame_no in range(count):
            target = start_time + frame_no / fps
            while idx + 1 < len(eligible) and eligible[idx + 1][0] <= target:
                idx += 1
            decoded = cv2.imdecode(eligible[idx][1], cv2.IMREAD_COLOR)
            if decoded is not None:
                writer.write(decoded)
    finally:
        writer.release()
    return output_path

def main():
    args = parse_args()
    if args.duration <= 0 or args.fps <= 0:
        raise SystemExit("--duration and --fps must be greater than zero")
    if not 1 <= args.jpeg_quality <= 100:
        raise SystemExit("--jpeg-quality must be between 1 and 100")
    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        raise SystemExit(f"Could not open webcam index {args.camera}. Try --camera 1 or check permissions.")
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    buffer = collections.deque()
    buffer_window = args.duration + 1.0
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), args.jpeg_quality]
    window_name = "Live Slicer pre-MVP — SPACE saves previous window | Q quits"
    print(f"Live Slicer pre-MVP: camera={args.camera}, pre-event={args.duration:.1f}s, output={args.output}")
    print("Press SPACE to save the previous window. Press Q or ESC to quit.")
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
            cutoff = now - buffer_window
            while buffer and buffer[0][0] < cutoff:
                buffer.popleft()
            elapsed = now - buffer[0][0] if buffer else 0.0
            ready = elapsed >= args.duration
            preview = frame.copy()
            status = f"Buffer: {min(elapsed, args.duration):05.1f}/{args.duration:.0f}s"
            color = (40, 200, 40) if ready else (0, 180, 255)
            cv2.putText(preview, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(preview, "SPACE: save previous window | Q: quit", (12, 56),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
            cv2.imshow(window_name, preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord(" "):
                trigger_time = time.monotonic()
                try:
                    output_path = save_clip(list(buffer), trigger_time, args.duration, args.fps, args.output)
                    print(f"Saved pre-event clip: {output_path}")
                except Exception as exc:
                    print(f"Could not save clip: {exc}")
    finally:
        camera.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
