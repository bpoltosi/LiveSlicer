# Live Slicer pre-MVP (webcam + Space)

This standalone prototype leaves the existing C++/RTSP application untouched. It uses the computer's webcam and Space to test the pre-event capture workflow.

## Behavior

- Opens one webcam (OpenCV camera index 0 by default).
- Maintains a rolling in-memory buffer of JPEG-compressed frames.
- Pressing **Space** saves the preceding 45 seconds to an MP4 in recordings/.
- Pressing **Q** or **Esc** exits.
- The preview shows how much buffer has accumulated. A clip is only saved after the full window has warmed up.

The exported MP4 is re-encoded from buffered frames. This is intentional for the prototype and separate from the existing C++ H.264 passthrough design.

## Requirements

- Python 3.9+
- OpenCV Python package

Install:

\`\`\`bash
python -m pip install opencv-python
\`\`\`

Run from the repository root:

\`\`\`bash
python pre_mvp/live_slicer_pre_mvp.py
\`\`\`

If the webcam is not camera index 0, try:

\`\`\`bash
python pre_mvp/live_slicer_pre_mvp.py --camera 1
\`\`\`

Optional settings:

\`\`\`bash
python pre_mvp/live_slicer_pre_mvp.py --duration 45 --fps 20 --width 640 --height 480 --output recordings
\`\`\`

## Acceptance test before calling the pre-MVP functional

1. Launch the script and confirm the webcam preview appears.
2. Wait until the buffer indicator reaches 45 seconds.
3. Press Space once; verify a new MP4 appears under recordings/.
4. Open the MP4 and confirm it plays and is approximately 45 seconds long, ending at the Space trigger.
5. Repeat with two or more triggers and confirm separate files are produced.
6. Test webcam permissions, another camera index, and quitting with Q/Esc.

## Known prototype limitations

- The OpenCV preview window must have keyboard focus for Space to be received.
- Buffer contents are held in RAM; JPEG compression limits but does not eliminate memory use.
- A capture outage can make the saved footage contain repeated frames or fail the full-window check.
- The MP4 is re-encoded, so quality and frame cadence depend on settings and the webcam.
- This prototype is not yet connected to the C++ service or multi-camera RTSP capture.
- No build or physical webcam test was run in the cloud environment. Validate locally before calling it functional or creating a release.
