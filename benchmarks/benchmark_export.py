#!/usr/bin/env python3
"""Benchmark Live Slicer's JPEG-buffer-to-H.264 export without requiring a webcam.

Run from the repository root:
  python benchmarks/benchmark_export.py --seconds 10 --presets veryfast medium
Optional process RSS sampling requires: python -m pip install psutil
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pre_mvp.live_slicer_pre_mvp import save_clip


def rss_mib() -> float | None:
    try:
        import psutil
        return psutil.Process().memory_info().rss / (1024 * 1024)
    except ImportError:
        return None


def make_frames(seconds: float, fps: float, width: int, height: int, jpeg_quality: int):
    """Create a deterministic synthetic scene and JPEG-compress it like the live buffer."""
    count = max(2, int(seconds * fps) + 1)
    frames = []
    params = [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality]
    for i in range(count):
        frame = __import__("numpy").zeros((height, width, 3), dtype="uint8")
        # Moving high-contrast shapes exercise both JPEG and H.264 without a camera.
        x = int((i / max(1, count - 1)) * max(1, width - 160))
        cv2.rectangle(frame, (x, height // 4), (min(width - 1, x + 160), height // 2), (30, 180, 240), -1)
        cv2.putText(frame, f"Live Slicer benchmark {i:05d}", (20, height - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, max(0.5, width / 1280), (240, 240, 240), 2)
        ok, encoded = cv2.imencode(".jpg", frame, params)
        if not ok:
            raise RuntimeError("OpenCV failed to JPEG-encode a synthetic frame")
        frames.append((i / fps, encoded))
    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=10, help="Synthetic clip duration per run (default: 10)")
    parser.add_argument("--fps", type=float, default=30, help="Input/output timeline FPS (default: 30)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--jpeg-quality", type=int, default=98)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--presets", nargs="+", default=["veryfast", "medium"],
                        choices=["ultrafast", "superfast", "veryfast", "faster", "fast",
                                 "medium", "slow", "slower", "veryslow"])
    parser.add_argument("--threads", type=int, default=2)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--output-dir", type=Path, default=Path("benchmark-results/exports"))
    parser.add_argument("--report", type=Path, default=Path("benchmark-results/export-benchmark.json"))
    args = parser.parse_args()

    if args.seconds <= 0 or args.fps <= 0 or args.width <= 0 or args.height <= 0:
        parser.error("seconds, fps, width and height must be positive")
    if not 1 <= args.jpeg_quality <= 100 or not 0 <= args.crf <= 51 or args.threads <= 0:
        parser.error("jpeg-quality must be 1-100, crf 0-51 and threads positive")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    print("Preparing synthetic JPEG buffer; this setup time is excluded from export timings...")
    frames = make_frames(args.seconds, args.fps, args.width, args.height, args.jpeg_quality)
    encoded_buffer_mib = sum(len(frame) for _, frame in frames) / (1024 * 1024)
    results = []
    for preset in args.presets:
        before_rss = rss_mib()
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        try:
            output = save_clip(
                frames=frames,
                trigger_time=frames[-1][0],
                duration=args.seconds,
                fps=args.fps,
                output_dir=args.output_dir,
                ffmpeg=args.ffmpeg,
                h264_crf=args.crf,
                h264_preset=preset,
                min_clip_seconds=min(1.0, args.seconds),
                h264_threads=args.threads,
            )
            wall_seconds = time.perf_counter() - wall_start
            cpu_seconds = time.process_time() - cpu_start
            size_bytes = output.stat().st_size
            # Verify container metadata via OpenCV; this is a smoke check, not a full quality metric.
            cap = cv2.VideoCapture(str(output))
            output_fps = cap.get(cv2.CAP_PROP_FPS)
            output_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            row = {
                "preset": preset, "status": "ok", "duration_seconds_requested": args.seconds,
                "wall_seconds": round(wall_seconds, 4), "process_cpu_seconds": round(cpu_seconds, 4),
                "cpu_cores_average_estimate": round(cpu_seconds / wall_seconds, 3) if wall_seconds else None,
                "realtime_factor": round(args.seconds / wall_seconds, 3) if wall_seconds else None,
                "output_size_bytes": size_bytes, "output_size_mib": round(size_bytes / (1024 * 1024), 3),
                "output_fps_reported": round(output_fps, 3), "output_frame_count": output_frames,
                "rss_before_mib": round(before_rss, 2) if before_rss is not None else None,
                "rss_after_mib": round(rss_mib(), 2) if rss_mib() is not None else None,
                "output_path": str(output),
            }
        except Exception as exc:
            row = {"preset": preset, "status": "error", "error": str(exc)}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False))
    report = {
        "benchmark": "live_slicer_synthetic_export",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(), "python": platform.python_version(), "opencv": cv2.__version__,
        "settings": {"seconds": args.seconds, "fps": args.fps, "width": args.width, "height": args.height,
                     "jpeg_quality": args.jpeg_quality, "crf": args.crf, "threads": args.threads,
                     "encoded_input_buffer_mib": round(encoded_buffer_mib, 3)},
        "results": results,
        "notes": ["Synthetic scene; not representative of every webcam or real-world motion.",
                  "RSS is sampled before/after each export, not a peak measurement.",
                  "Run each configuration more than once and compare medians for meaningful results."],
    }
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    csv_path = args.report.with_suffix(".csv")
    flat = [r for r in results if r.get("status") == "ok"]
    if flat:
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(flat[0].keys()))
            writer.writeheader()
            writer.writerows(flat)
    print(f"JSON report: {args.report}")
    if flat:
        print(f"CSV report:  {csv_path}")
    return 0 if any(r.get("status") == "ok" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
