# Live Slicer pre-MVP benchmarks

These scripts establish repeatable measurements before performance changes. Run them from the repository root with the same Python environment used for the prototype.

## 1. Webcam capture and JPEG buffer

Close the Live Slicer app first; this benchmark needs exclusive access to the camera.

\`\`\`powershell
py benchmarks/benchmark_capture.py --seconds 60 --width 1280 --height 720 --jpeg-quality 98
\`\`\`

Add \`--preview\` to include the preview window in the measurement. The headless run isolates camera-read, JPEG-encode and JPEG-decode costs. Reports are written to \`benchmark-results/capture-benchmark.json\` and \`.csv\`.

## 2. Synthetic end-to-end export

This benchmark generates a repeatable moving test scene, JPEG-compresses it like the rolling buffer, then calls the prototype's actual \`save_clip\` export function. It does not require a webcam.

\`\`\`powershell
py benchmarks/benchmark_export.py --seconds 10 --presets veryfast medium --threads 2 --crf 18
\`\`\`

For a more representative comparison, use 30-second runs and repeat each preset at least three times. Keep resolution, FPS, JPEG quality, CRF and thread count identical. Reports include wall-clock time, process CPU time, approximate CPU core utilization, real-time factor, output file size, output FPS/frame count, and before/after RSS when the optional \`psutil\` package is installed.

\`\`\`powershell
py -m pip install psutil
py benchmarks/benchmark_export.py --seconds 30 --presets veryfast medium --threads 2 --crf 18
\`\`\`

Results are written under \`benchmark-results/\`, which should normally remain untracked because the numbers are machine-specific. Do not compare a run with the preview enabled to a headless run as if they were equivalent.

## Suggested protocol

1. Close other camera apps and avoid changing power mode or resolution between runs.
2. Run the capture benchmark three times; record median FPS, JPEG encode/decode latency, and estimated 45-second buffer size.
3. Run the export benchmark with \`veryfast\` and \`medium\` at identical settings, at least three repetitions each. Alternate the preset order to reduce thermal/order bias.
4. Save JSON/CSV outputs outside version control and note CPU model, RAM, camera model, OS, and FFmpeg version in your test notes.
5. Finally run the real app for 60 seconds, save a clip with Space, and check preview smoothness, duration, frame count, codec, audio expectation (none in current prototype), file size, and playback. Synthetic tests cannot validate real webcam smoothness or capture gaps.

## Interpreting results

- \`measured_processing_fps\` is the script's processing throughput, not a guarantee of the camera's sensor FPS.
- JPEG buffer estimates count compressed payload bytes only; Python/OpenCV object overhead is extra.
- \`realtime_factor\` greater than 1 means encoding ran faster than real-time for the synthetic clip; less than 1 means slower.
- RSS is sampled before and after an export, not a peak measurement. CPU time is process CPU time and may omit FFmpeg child-process CPU on some platforms, so use Windows Task Manager or an OS process monitor to observe total system/FFmpeg load during an export.
- Compare medians across repeated runs; a single result is not enough to justify a code change.

## Optimization backlog after baseline

1. Reduce avoidable frame allocations and measure the effect.
2. Measure JPEG encode/decode cost separately before changing the buffer representation.
3. Prototype dedicated capture thread plus bounded frame queue; verify no added gaps and no unbounded queue growth.
4. Consider a disk-backed circular buffer only if measured RAM pressure justifies the extra I/O and recovery complexity.
5. Consider PyAV/GStreamer only after profiling identifies a limitation that simpler changes cannot address.
