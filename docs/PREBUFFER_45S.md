# 45-second pre-event buffer: implementation and validation

## Change summary

This branch changes the default pre-buffer duration from 5 seconds to 45 seconds and timestamps each encoded RTSP packet with a local monotonic clock at capture time.

The recorder trims its in-memory packet deque using that monotonic receive timestamp rather than RTSP PTS/DTS. This avoids buffer-duration calculations being disrupted by missing, non-monotonic, or reset stream timestamps. Trimming retains the latest keyframe at or before the 45-second cutoff, so the buffer normally contains at least 45 seconds plus up to one GOP of video.

The existing packet-count and 512 MiB caps remain active as safety limits. They may force the buffer below the requested duration under unusually high bitrate, pathological streams, or long GOPs. The current buffer remains in RAM; this change does not add a disk-backed rolling segment store.

## Configuration

- Application fallback/default: `pre_buffering_time = 45.0`
- Example config: `pre_buffering_time = 45.0`
- Explicit values in a user's own config still override the default.

## Acceptance checks before declaring this feature validated

1. Build the application on the target OS against the intended FFmpeg/Qt/OpenCV versions.
2. Run at least 60 seconds of a stable RTSP stream with timestamps increasing normally; verify a prebuffer snapshot covers at least 45 seconds and begins on a keyframe.
3. Repeat with missing PTS/DTS and with PTS/DTS reset after a simulated reconnect; verify the buffer uses monotonic receive time and remains bounded.
4. Test GOP intervals of 1, 2, and 5 seconds; verify the retained pre-roll starts at the latest keyframe at/before the cutoff.
5. Test high-bitrate streams and 2–4 cameras; verify whether the 512 MiB per-camera cap preserves 45 seconds. If not, tune a configurable cap or implement disk-backed segments.
6. Verify a stream stall does not claim the buffer contains 45 seconds of recent video merely because old packets remain in memory.
7. On a real camera, export a clip and inspect it with FFprobe/player for decodability, duration, timestamp monotonicity, and audio expectations (the current packet structure is video-only).

## Current validation status

Source changes are committed on `feature/prebuffer-45-seconds`. Runtime/build/integration checks have not been run by this GitHub-only workflow. Do not treat this change as production-validated until the acceptance checks above pass.

## Remaining engineering concern

A keyframe-aware in-memory packet deque is an incremental improvement, not a full segmented rolling recorder. A robust MVP should eventually expose buffer coverage per camera and fail the trigger clearly if a camera has less than 45 seconds of valid recent footage, rather than silently saving a shorter clip.
