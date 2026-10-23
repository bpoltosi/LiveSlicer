# Live Slicer pre-MVP (webcam + Space)

This standalone Python prototype tests rolling pre-event capture using one computer webcam and the Space key. It is separate from the existing C++/RTSP application.

## Current behavior

- Opens webcam index 0 by default and requests 1280x720; the camera may choose a different supported resolution.
- Continuously keeps a rolling, in-memory buffer of JPEG-compressed frames, targeting the preceding 45 seconds.
- Press **Space** to export the available footage before the keypress to an MP4 in `recordings/`.
- Supports short clips during startup: if fewer than 45 seconds have accumulated, the footage available is saved (at least two frames are required).
- **Exports in a background worker.** The capture/preview loop continues while MP4 encoding and disk writes run, instead of doing the entire export in the UI loop.
- Allows one export at a time. Further Space presses while a save is in progress are rejected with a console message, preventing multiple large snapshots from accumulating in RAM.
- Shows buffer duration, approximate buffer RAM, and a background-saving status in the preview.
- Press **Q** or **Esc** to quit. If an export is already in progress, the app waits for it to finish so the MP4 is not intentionally abandoned mid-write.
- Requests a 1-frame camera capture buffer where supported to reduce latency.

## Quality, performance, and limits

Defaults are 30 FPS export, JPEG quality 98/100 for the in-memory rolling buffer, an MP4 quality hint of 100/100, and a 512 MiB RAM cap. The MP4 uses OpenCV's `mp4v` writer.

**Important:** JPEG quality controls the intermediate frames, while `--video-quality` is only a hint to the installed OpenCV video backend. Some backends ignore or do not expose this control. Therefore, setting the hint to 100 does **not** guarantee lossless or maximum-quality MP4 output. The export is re-encoded and is not a bit-for-bit copy of the webcam stream.

Higher JPEG quality and resolution can increase CPU use, frame-processing time, and RAM consumption. If the memory cap is reached, the available rolling window may become shorter than 45 seconds. The actual resolution/FPS and encoder quality depend on the webcam, system load, OpenCV build, and video backend. Background export removes the main source of UI blocking, but encoding and JPEG compression still consume CPU and may affect preview smoothness on slower computers.

For genuinely higher and more predictable output quality, a future iteration should use an explicit FFmpeg encoding pipeline (for example, a configurable H.264 CRF/preset or a high-bitrate/lossless codec where appropriate) rather than relying on OpenCV's backend-dependent quality hint. That change should be benchmarked against CPU usage, disk space, and dropped-frame behavior before becoming the default.

## Requirements and launch

- Python 3.9+
- OpenCV Python package

Install dependencies:

```bash
python -m pip install -r pre_mvp/requirements.txt
```

From the repository root:

```bash
python pre_mvp/live_slicer_pre_mvp.py
```

If needed, select another camera:

```bash
python pre_mvp/live_slicer_pre_mvp.py --camera 1
```

Example higher-resolution settings:

```bash
python pre_mvp/live_slicer_pre_mvp.py --duration 45 --fps 30 --width 1920 --height 1080 --jpeg-quality 100 --video-quality 100 --max-buffer-mib 768 --output recordings
```

Options:
- `--camera`: webcam index (default `0`)
- `--duration`: maximum rolling pre-event duration in seconds (default `45`)
- `--fps`: exported frame rate (default `30`)
- `--width`, `--height`: requested camera resolution (defaults `1280x720`)
- `--jpeg-quality`: intermediate JPEG quality from 1 to 100 (default `98`)
- `--video-quality`: encoder quality hint from 0 to 100 (default `100`; backend-dependent)
- `--max-buffer-mib`: rolling buffer memory limit in MiB (default `512`)
- `--output`: output folder (default `recordings/`)

## Automated tests

Run from the repository root:

```bash
python -m unittest discover -s tests -p 'test_pre_mvp.py'
```

The tests cover clip-window selection and the background export worker's one-job-at-a-time behavior. They do not replace a test with the target computer's physical webcam.

## Manual acceptance test (required before release)

1. Launch the script and confirm the webcam preview appears.
2. Immediately press Space; verify a short MP4 is created and plays.
3. Repeat after 5–10 seconds; verify the clip contains the available pre-event footage.
4. Wait until the indicator reaches 45 seconds, press Space, and verify an approximately 45-second playable MP4.
5. While a clip is saving, verify the preview continues updating and the window still responds.
6. Press Space again during export; confirm the app explains that an export is already in progress rather than queuing another clip.
7. Inspect output resolution, frame rate, duration, and visual quality in a media player or with FFprobe.
8. Test camera permissions, an alternate camera index, Q/Esc, and the RAM cap.

## Known limitations

- The OpenCV preview window must have keyboard focus for Space to be received.
- JPEG compression and MP4 encoding use CPU; background export should avoid a long UI freeze, but system load may still cause preview stutter or webcam frame gaps.
- A webcam stall can cause a gap or repeated frames in the exported clip.
- The buffer is RAM-resident and its configured cap can shorten the available pre-event window on high-resolution/high-motion footage.
- The MP4 encoder quality hint may be ignored by the installed OpenCV backend.
- This prototype is not connected to the C++ service or multi-camera RTSP capture.
- Real webcam, keyboard-focus, sustained-load, and final-MP4 quality checks on the target computer remain required before declaring the pre-MVP validated or publishing a release.
