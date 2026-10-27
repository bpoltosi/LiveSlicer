# Live Slicer pre-MVP (webcam + Space)

This standalone Python prototype tests rolling pre-event capture using one computer webcam and the Space key. It is separate from the existing C++/RTSP application.

## Current behavior

- Opens webcam index 0 by default and requests 1280x720; the camera may choose a different supported resolution.
- Continuously keeps a rolling, in-memory buffer of JPEG-compressed frames, targeting the preceding 45 seconds.
- Press **Space** to export the available footage before the keypress to an H.264 MP4 in `recordings/`.
- **Minimum clip duration is 10 seconds by default.** If fewer than 10 seconds of footage are available, the export is rejected and the app reports how much more footage is needed. This prevents tiny clips created during startup or by accidental early keypresses.
- The minimum can be changed with `--min-clip-seconds`, but cannot exceed the target buffer duration.
- **Exports in a background worker.** The capture/preview loop continues while FFmpeg encodes and writes the MP4.
- Allows one export at a time. Further Space presses while a save is in progress are rejected, avoiding multiple large snapshots accumulating in RAM.
- Shows buffer duration, approximate buffer RAM, and a background-saving status in the preview.
- Press **Q** or **Esc** to quit. If an export is in progress, the app waits for it to finish so the MP4 is not intentionally abandoned mid-write.
- Requests a 1-frame camera capture buffer where supported to reduce latency.

## H.264 quality and performance

Video is encoded by the FFmpeg command-line executable using `libx264` and H.264 in an MP4 container. Defaults are:

- 30 FPS output
- JPEG quality 98/100 for frames in the rolling RAM buffer
- H.264 CRF 18 (lower CRF generally means higher quality and larger files)
- x264 preset `veryfast` to reduce CPU time during export
- x264 encoder limited to 2 worker threads by default, to leave more CPU headroom for webcam capture and the rest of the computer
- 512 MiB rolling-buffer memory cap

The `--h264-crf` option accepts values from 0 to 51. As a practical starting point, CRF 18 is high quality; CRF 20–23 generally reduces file size at some quality cost. CRF 0 is not a guarantee of lossless capture end-to-end because webcam acquisition and the in-memory JPEG buffer are already lossy. The `--h264-preset` option controls encoding speed/compression efficiency: slower presets can reduce file size at similar CRF but use more CPU and take longer to export. The default `veryfast` preset was selected after target-machine testing showed noticeably lower CPU usage with nearly unchanged perceived quality and file size. The `--h264-threads` option caps x264 worker threads (default `2`) so encoding is less likely to monopolize the CPU; this can make exports take longer, which is intentional to protect live capture and overall responsiveness. Export runs in a background thread, although JPEG compression and decoding can still compete with capture for CPU time.

The buffer stores JPEG-compressed frames, not original camera frames, so increasing H.264 quality cannot restore details lost during JPEG compression. Higher camera resolution or JPEG quality increases CPU and RAM requirements. If the RAM cap is reached, the available pre-event window may be shorter than 45 seconds. Actual camera resolution and frame rate depend on the webcam and driver.

**FFmpeg setup:** At startup, the app checks that FFmpeg exists and includes the `libx264` encoder. If it is missing, it asks permission to install it using the system package manager (Windows: `winget`; macOS: Homebrew; Linux: `apt`, `dnf`, `pacman` or `zypper`, depending on what is available). After a successful installation, the app validates FFmpeg and automatically restarts itself, passing the discovered executable path so the current process's stale `PATH` does not prevent launch. The installer may request administrator privileges. If no supported package manager is available, the app explains that manual installation is required. If an installed FFmpeg lacks `libx264`, the app stops with a clear message rather than silently producing a different codec. If FFmpeg is installed at a custom location, pass its executable path with `--ffmpeg`. The Python requirements file installs OpenCV, not FFmpeg.

## Requirements and launch

- Python 3.9+
- OpenCV Python package
- FFmpeg with `libx264`

Install Python dependencies:

```bash
python -m pip install -r pre_mvp/requirements.txt
```

Check FFmpeg and H.264 encoder support:

```bash
ffmpeg -version
ffmpeg -hide_banner -encoders
```

Confirm that the encoder list contains `libx264`.

From the repository root:

```bash
python pre_mvp/live_slicer_pre_mvp.py
```

If needed, select another camera:

```bash
python pre_mvp/live_slicer_pre_mvp.py --camera 1
```

Example higher-resolution / higher-quality settings:

```bash
python pre_mvp/live_slicer_pre_mvp.py --duration 45 --min-clip-seconds 10 --fps 30 --width 1920 --height 1080 --jpeg-quality 100 --h264-crf 16 --h264-preset slow --h264-threads 2 --max-buffer-mib 768 --output recordings
```

Useful options:
- `--camera`: webcam index (default `0`)
- `--duration`: maximum rolling pre-event duration in seconds (default `45`)
- `--min-clip-seconds`: minimum duration allowed for an export (default `10`)
- `--fps`: exported frame rate (default `30`)
- `--width`, `--height`: requested camera resolution (defaults `1280x720`)
- `--jpeg-quality`: intermediate JPEG quality from 1 to 100 (default `98`)
- `--h264-crf`: H.264 quality level from 0 to 51; lower means higher quality (default `18`)
- `--h264-preset`: x264 speed/compression preset (default `medium`)
- `--ffmpeg`: FFmpeg executable or full path (default `ffmpeg`)
- `--max-buffer-mib`: rolling buffer memory limit in MiB (default `512`)
- `--output`: output folder (default `recordings/`)

## Automated tests

Run from the repository root:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

Tests cover FFmpeg startup checks and installation opt-in, rejection below the minimum duration, acceptance at the minimum, selection of a full buffer window, empty/single-frame errors, and the background exporter's one-job-at-a-time behavior. They do not replace a real FFmpeg export test and a test with the target computer's physical webcam.

## Manual acceptance test (required before release)

1. Install FFmpeg and confirm `libx264` is listed by `ffmpeg -encoders`.
2. Launch the script and confirm the webcam preview appears.
3. Press Space before 10 seconds have elapsed; confirm no file is generated and the app reports the minimum-duration rule.
4. Wait until at least 10 seconds are available, press Space, and verify an H.264 MP4 is created and plays.
5. Wait until the indicator reaches 45 seconds, press Space, and verify an approximately 45-second playable MP4.
6. While a clip is saving, verify the preview continues updating and the window still responds.
7. Press Space again during export; confirm the app reports that an export is already in progress.
8. Inspect codec, resolution, frame rate, duration, visual quality, and file size (for example with FFprobe).
9. Test camera permissions, an alternate camera index, Q/Esc, sustained load, and the RAM cap.

## Known limitations

- The OpenCV preview window must have keyboard focus for Space to be received.
- The source frames are JPEG-compressed before H.264 encoding, so this is not lossless end-to-end.
- JPEG compression and H.264 encoding use CPU; background export should avoid a long UI freeze, but system load may still cause preview stutter or webcam frame gaps.
- A webcam stall can cause a gap or repeated frames in the exported clip.
- The RAM cap can shorten the available pre-event window on high-resolution/high-motion footage.
- This prototype is not connected to the C++ service or multi-camera RTSP capture.
- Real webcam, keyboard-focus, sustained-load, and output-quality checks on the target computer remain required before declaring the pre-MVP validated or publishing a release.
