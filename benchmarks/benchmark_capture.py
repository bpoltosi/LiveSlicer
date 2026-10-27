#!/usr/bin/env python3
"""Measure webcam capture rate and JPEG buffer costs without exporting a clip.

Run from the repository root:
  python benchmarks/benchmark_capture.py --seconds 60 --width 1280 --height 720
Press Q or Esc to stop early. Requires the same OpenCV dependency as the pre-MVP.
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--seconds", type=float, default=60)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--jpeg-quality", type=int, default=98)
    parser.add_argument("--window-seconds", type=float, default=45,
                        help="Window used to estimate rolling-buffer RAM (default: 45)")
    parser.add_argument("--report", type=Path, default=Path("benchmark-results/capture-benchmark.json"))
    parser.add_argument("--preview", action="store_true", help="Show preview window; otherwise run headless")
    args = parser.parse_args()
    if args.seconds <= 0 or args.width <= 0 or args.height <= 0 or args.window_seconds <= 0:
        parser.error("seconds, dimensions and window-seconds must be positive")
    if not 1 <= args.jpeg_quality <= 100:
        parser.error("jpeg-quality must be 1-100")

    camera = cv2.VideoCapture(args.camera)
    if not camera.isOpened():
        parser.error(f"Could not open camera index {args.camera}")
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    actual_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
    params = [int(cv2.IMWRITE_JPEG_QUALITY), args.jpeg_quality]
    capture_times, jpeg_times, decode_times, jpeg_sizes = [], [], [], []
    rolling_sizes = []
    started = time.perf_counter()
    last = started
    frame_count = 0
    window_name = "Live Slicer capture benchmark — Q/Esc quits"
    try:
        while time.perf_counter() - started < args.seconds:
            t0 = time.perf_counter()
            ok, frame = camera.read()
            t1 = time.perf_counter()
            if not ok or frame is None:
                continue
            capture_times.append(t1 - t0)
            ok, encoded = cv2.imencode(".jpg", frame, params)
            t2 = time.perf_counter()
            if not ok:
                continue
            jpeg_times.append(t2 - t1)
            decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            t3 = time.perf_counter()
            if decoded is None:
                continue
            decode_times.append(t3 - t2)
            jpeg_sizes.append(len(encoded))
            rolling_sizes.append((t3, len(encoded)))
            cutoff = t3 - args.window_seconds
            while rolling_sizes and rolling_sizes[0][0] < cutoff:
                rolling_sizes.pop(0)
            frame_count += 1
            now = time.perf_counter()
            if args.preview:
                cv2.putText(frame, f"Capture FPS: {frame_count / max(now-started, 1e-6):.1f}",
                            (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
            if now - last >= 5:
                print(f"elapsed={now-started:.1f}s frames={frame_count} "
                      f"fps={frame_count/max(now-started,1e-6):.2f} "
                      f"rolling_jpeg_mib={sum(n for _, n in rolling_sizes)/(1024*1024):.1f}")
                last = now
    finally:
        camera.release()
        if args.preview:
            cv2.destroyAllWindows()

    elapsed = time.perf_counter() - started
    def stats(values):
        if not values:
            return {"mean_ms": None, "median_ms": None, "p95_ms": None}
        ordered = sorted(values)
        return {
            "mean_ms": round(statistics.mean(values) * 1000, 3),
            "median_ms": round(statistics.median(values) * 1000, 3),
            "p95_ms": round(ordered[min(len(ordered)-1, int(0.95 * len(ordered)))] * 1000, 3),
        }

    report = {
        "benchmark": "live_slicer_capture_jpeg",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "opencv": cv2.__version__,
        "requested": {"camera": args.camera, "width": args.width, "height": args.height,
                      "jpeg_quality": args.jpeg_quality, "window_seconds": args.window_seconds},
        "actual_resolution": {"width": actual_width, "height": actual_height},
        "elapsed_seconds": round(elapsed, 3), "frames_processed": frame_count,
        "measured_processing_fps": round(frame_count / elapsed, 3) if elapsed else 0,
        "capture_read": stats(capture_times), "jpeg_encode": stats(jpeg_times),
        "jpeg_decode": stats(decode_times),
        "jpeg_size_bytes": {"mean": round(statistics.mean(jpeg_sizes), 1) if jpeg_sizes else None,
                            "median": round(statistics.median(jpeg_sizes), 1) if jpeg_sizes else None,
                            "max": max(jpeg_sizes) if jpeg_sizes else None},
        "estimated_full_window_jpeg_buffer_mib": round(
            statistics.mean(jpeg_sizes) * (frame_count / elapsed if elapsed else 0)
            * args.window_seconds / (1024 * 1024), 3) if jpeg_sizes else None,
        "observed_jpeg_buffer_mib_at_end": round(
            sum(n for _, n in rolling_sizes) / (1024 * 1024), 3),
        "notes": ["Run without --preview to measure headless capture/encode costs; repeat with --preview to check UI overhead.",
                  "FPS is measured processing throughput, not guaranteed sensor FPS.",
                  "The RAM estimate covers JPEG payloads only, not Python/OpenCV/deque overhead.",
                  "This benchmark opens the webcam exclusively; close the Live Slicer app before running."],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    csv_path = args.report.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["metric", "value"])
        for key in ("measured_processing_fps", "estimated_full_window_jpeg_buffer_mib",
                    "observed_jpeg_buffer_mib_at_end"):
            writer.writerow([key, report[key]])
        for stage in ("capture_read", "jpeg_encode", "jpeg_decode"):
            for metric, value in report[stage].items():
                writer.writerow([f"{stage}.{metric}", value])
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"JSON report: {args.report}\nCSV report:  {csv_path}")
    return 0 if frame_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
