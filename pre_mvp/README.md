# Live Slicer pre-MVP (webcam + Space)

This standalone Python prototype leaves the existing C++/RTSP application untouched. It uses one computer webcam and the Space key to test pre-event capture.

## Behavior

- Opens the webcam (camera index 0 by default) and requests 1280x720 at the camera's supported rate.
- Keeps a rolling, in-memory buffer of JPEG-compressed frames.
- Press **Space** to save up to the preceding 45 seconds to an MP4 in `recordings/`.
- **Short clips are supported:** pressing Space before the buffer reaches 45 seconds saves the footage currently available, provided at least two frames have been captured.
- Press **Q** or **Esc** to quit.
- The preview shows buffered duration and approximate RAM use.
- The buffer is capped at 512 MiB by default to prevent unbounded memory growth.

The frames are re-encoded to MP4 on export. JPEG quality defaults to 95/100 and MP4 encoder quality is requested at 95 where the installed OpenCV backend supports that control. Actual webcam resolution, frame rate, codec support, and output quality depend on the hardware and OpenCV/video backend. The prototype does not promise lossless video.

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

If needed, choose another camera:

```bash
python pre_mvp/live_slicer_pre_mvp.py --camera 1
```

Example options:

```bash
python pre_mvp/live_slicer_pre_mvp.py --duration 45 --fps 30 --width 1920 --height 1080 --jpeg-quality 98 --video-quality 98 --max-buffer-mib 768 --output recordings
```

Higher resolution/quality and longer buffers use more CPU and RAM. The webcam may reject requested dimensions; the app reports the actual selected resolution. The MP4 encoder's quality option is backend-dependent.

## Automated tests

Run the buffer-selection tests from the repository root:

```bash
python -m unittest discover -s tests -p 'test_pre_mvp.py'
```

## Manual acceptance test (required before release)

1. Launch the script and confirm the webcam preview appears.
2. Immediately press Space; verify a short MP4 is created and plays.
3. Repeat after 5–10 seconds; verify the clip includes the available pre-event footage.
4. Wait until the indicator reaches 45 seconds, press Space, and verify an approximately 45-second playable MP4.
5. Trigger twice and confirm separate files are created.
6. Inspect resolution, frame rate, and duration in a media player or with FFprobe.
7. Test camera permissions, an alternate camera index, Q/Esc, and the RAM cap.

## Known limitations

- The OpenCV preview window must have keyboard focus for Space to be received.
- Frames stay in RAM as JPEGs; the configured memory cap can shorten the available pre-event window on high-resolution/high-motion footage.
- A webcam stall can cause a gap or repeated frames in the exported clip.
- Export is re-encoded, not a lossless copy of the camera stream.
- This prototype is not connected to the C++ service or multi-camera RTSP capture.
- Automated tests can check window selection, but a real webcam and the target operating system are required to validate capture, keyboard focus, and the final MP4. Do not declare the pre-MVP fully validated or publish a release until that manual test passes.
