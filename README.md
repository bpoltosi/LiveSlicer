# Live Slicer

Live Slicer is a lightweight video-capture project with two distinct parts: the existing C++/Qt RTSP recorder (formerly documented as NVRLite) and an independent Python pre-MVP that tests instant clip capture from a local webcam.

> **Project status:** the webcam pre-MVP is implemented in `pre_mvp/`, but final validation on the target computer is still required. Do not treat physical-webcam operation, long-session stability, or exported MP4 integrity as verified until those checks have been performed.

## Project components

### 1. C++ RTSP recorder

The original application captures configured RTSP streams and records H.264 packets to MP4 without re-encoding. It includes stream/recording controls over HTTP, a configurable pre-buffer, reconnect handling, and an OpenCV multi-camera preview.

See the architecture, dependencies, build instructions, configuration and REST API reference below.

### 2. Python webcam pre-MVP

The separate prototype uses the computer's webcam and the **Space** key to export the footage captured immediately before the keypress.

- Requests 1280×720 from webcam index 0; the camera may choose another supported mode.
- Maintains a rolling JPEG-frame buffer targeting up to 45 seconds, bounded by a 512 MiB memory cap.
- Exports MP4/H.264 through FFmpeg in a background worker, keeping capture and preview responsive during export.
- Uses a default minimum clip duration of 10 seconds; exports that do not meet the minimum are rejected.
- Allows only one export at a time to limit additional memory pressure.
- Uses H.264 CRF 18 and an encoder preset configured by the prototype. JPEG compression happens before H.264 encoding, so H.264 settings cannot recover detail already lost in the JPEG frames.
- Press **Q** or **Esc** to quit. If an export is running, the application waits for it to finish.

Start with the dedicated guide: **[Pre-MVP README](pre_mvp/README.md)**. It contains setup, command-line options, tests, resource considerations and manual acceptance checks.

**Important:** this Python prototype is independent of the C++/RTSP application; it does not replace or integrate with it.

## Validation and known gaps

Automated tests are useful but do not replace testing with the actual webcam and target computer. Before declaring the pre-MVP ready for release, verify:

- webcam capture, requested/actual resolution, and keyboard focus;
- Space-triggered clips contain the expected pre-event footage and duration;
- exported MP4 files open and play, with correct duration, resolution and frame rate;
- preview remains responsive during export;
- CPU and system/process memory remain acceptable during a prolonged session.

Benchmark scripts and resource-optimization work may exist on separate branches or open pull requests. They should not be considered part of `main` until merged. Run the repository's tests from the project root with:

```powershell
py -m unittest discover -s tests -v
```

Run the webcam and export benchmarks described in the relevant benchmark documentation on the target machine; retain measurements so future changes can be compared against a baseline.

## Documentation and roadmap

- [Documentation index and repository hygiene policy](docs/README.md)
- [Python pre-MVP setup and usage](pre_mvp/README.md)
- [45-second RTSP pre-buffer design and validation](docs/PREBUFFER_45S.md)
- [Legacy C++ release notes](ReleaseNotes.md)
- [Changelog](CHANGELOG.md)
- [Computer-vision future issue / roadmap](VISION_COMPUTER_VISION_FUTURE.md)

Computer vision is intentionally deferred to a future project issue; it is not a prerequisite for the current webcam-and-Space pre-MVP.

---

## Original C++/RTSP recorder documentation

The sections below document the existing C++ application and its REST API. They are retained as the reference for that application and should not be read as instructions for running the separate Python webcam prototype.

# NVRLite – Lightweight Multi-Camera RTSP NVR

NVRLite is a cross-platform (Win/Linux), lightweight, Qt‑based Network Video Recorder designed to handle multiple RTSP video streams with:

- Low‑latency preview via OpenCV
- MP4 recording **without re‑encoding** (H.264 passthrough)
- Pre‑record buffer (N seconds before trigger)
- Auto‑reconnect with “NO SIGNAL” overlay when streams drop
- HTTP (REST) control for starting/stopping recordings per camera

It targets a developer‑friendly workflow similar to known NVRs in the market , but in a lightweight C++ application.

---

## 1. High‑Level Architecture

NVRLite is built around three main components:

1. **Capture layer** – `RtspCaptureThread`
   - One `QThread` per RTSP stream
   - Opens RTSP with FFmpeg, decodes frames for display, and emits encoded H.264 packets for recording
   - Auto‑retry when RTSP is down (every 5 seconds)
   - Emits **NO SIGNAL** frames when offline

2. **Recording layer** – `Mp4RecorderWorker`
   - One recorder instance per stream (can be run in its own `QThread`)
   - Receives encoded packets and writes MP4 files **without re‑encoding**
   - Supports pre‑buffering: when recording starts, it also writes the last *N* seconds of video

3. **Control / HTTP layer** – `HttpDataServer`
   - Runs an embedded HTTP server using **cpp‑httplib**
   - Exposes APIs to start and stop recording for each `stream_id`
   - Tracks last output file per stream and returns it on `/record/stop`

Display uses **OpenCV** windows (no Qt GUI), with a **grid layout** that shows all active cameras in a single window.

The core application uses `QCoreApplication` (no `QMainWindow`, no `QtGui`/`QtWidgets`).

---

## 2. Dependencies

### System packages (Ubuntu / Debian)

You need:

- Qt5 core:
  - `qtbase5-dev`
- FFmpeg and dev headers:
  - `ffmpeg libavcodec-dev libavformat-dev libavutil-dev libswscale-dev`
- OpenCV:
  - `libopencv-dev`
- Build tools:
  - `build-essential cmake pkg-config`

Install (example):

```bash
sudo apt update
sudo apt install -y \
  qtbase5-dev \
  libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
  libopencv-dev \
  ffmpeg \
  build-essential cmake pkg-config
```

### Manual install (Windows)

- Use OpenCV and QT5 installer from website and provide path in cmake-gui

---


## 3. Build & Run Instructions

### Build

#### Linux

```
mkdir build
cd build
cmake ..
make -j8
```

#### Windows

- Use cmake-gui to generate the visual studio solution. 
- Launch the solution in visual studio and select the release build



### Run

Open a terminal (cmd on windows) and launch the executable with the config json as parameters

<b>Linux</b>

```
./NVRLite --config config.json
```

<b>Win</b>

```
NVRLite.exe --config config.json
```

See (6) for json configuration

---

## 4. Controls

### 4.1 REST API

**Routes**
- Start Stream : POST /stream/start
- Stop Stream : POST /stream/stop
- Start Record : POST /record/start
- Stop Record : POST /record/stop
- Get Status : GET /stream/status<?stream_id=xxxx>
- Remove file : POST /files/remove?file=<filename>"
- Get file info : GET /files/status?file=<filename>"
- list files : GET /files/list[?ext=mp4]/[?all=1]"


#### 4.1.1 Start streaming

**Endpoint**

```http
POST /stream/start
Content-Type: application/json
```

**Request body**

```json
{
  "stream_id": "stream_1"
}
```

**Behavior**

- Parses JSON.
- If `stream_id` is missing or not a string:
  - Returns `400` and `{"status":"error","message":"Missing or invalid 'stream_id'"}`.
- Otherwise:
  - Emits Qt signal:

    ```cpp
    emit startStreamRequested(streamId);
    ```

  - Returns:

    ```json
    {
      "status": "ok",
      "stream_id": "stream_1"
    }
    ```

#### 4.1.2 Stop streaming

**Endpoint**

```http
POST /stream/stop
Content-Type: application/json
```

**Request body**

```json
{
  "stream_id": "stream_1"
}
```

**Behavior**

- Parses JSON.
- If `stream_id` is missing or not a string:
  - Returns `400` and `{"status":"error","message":"Missing or invalid 'stream_id'"}`.
- Otherwise:
  - Emits Qt signal:

    ```cpp
    emit stopStreamRequested(streamId);
    ```

  - Returns:

    ```json
    {
      "status": "ok",
      "stream_id": "stream_1"
    }
    ```

#### 4.1.3 Start recording

**Endpoint**

```http
POST /record/start
Content-Type: application/json
```

**Request body**

```json
{
  "stream_id": "stream_1"
}
```

**Behavior**

- Parses JSON.
- If `stream_id` is missing or not a string:
  - Returns `400` and `{"status":"error","message":"Missing or invalid 'stream_id'"}`.
- Otherwise:
  - Emits Qt signal:

    ```cpp
    emit startRecordingRequested(streamId);
    ```

  - Returns:

    ```json
    {
      "status": "ok",
      "stream_id": "stream_1"
    }
    ```
 
#### 4.1.4 Stop recording

**Endpoint**

```http
POST /record/stop
Content-Type: application/json
```

**Request body**

```json
{
  "stream_id": "stream_1"
}
```

**Behavior**

- Parses JSON.
- Emits:

  ```cpp
  emit stopRecordingRequested(streamId);
  ```

- Looks up last known recording file for this `streamId` via `m_lastRecordingFile` (filled in `onRecordingStarted`).

**Responses**

- If a filename is known:

  ```json
  {
    "status": "ok",
    "stream_id": "stream_1",
    "file": "rec_stream_1_2025-12-04_11-43-27.mp4"
  }
  ```

- If no recording file is known yet (e.g. recording never started):

  ```json
  {
    "status": "warning",
    "stream_id": "stream_1",
    "file": null,
    "message": "No known recording file for this stream (maybe never started?)"
  }
  ```

- On JSON parse error or malformed body:

  ```json
  {
    "status": "error",
    "message": "JSON parse error: ..."
  }
  ```

with HTTP `400`.


#### 4.1.5 Check stream/rec status

**Endpoint**

```http
GET /stream/status
Content-Type: application/json
```


**Behavior**

  - Returns:

In case of all streams (no filtering)

  ```json
    {
      "status": "ok",
      "streams": [
        { "stream_id": "stream_1", "recording": true, "streaming":true,  "file": "rec_stream_1_....mp4" },
        { "stream_id": "stream_2", "recording": false, "streaming":true, "file": null },
        { "stream_id": "stream_3", "recording": false, "streaming":false, "file": null }
      ]
    }   
  ```
    
In case of one single stream (endpoint : ?stream_id=<id>)

  ```json     
    {
      "status": "ok",
      "stream": {
        "stream_id": "stream_1",
        "recording": true,
        "straming":true,
        "file": "rec_stream_1_....mp4"
      }
    }
  ```
    
#### 4.1.6 Remove file

**Endpoint**

```http
POST /files/remove?file=xxxxxx
Content-Type: application/json
```


**Behavior**

  - Returns:

  ```json
    {
      "status": "ok",
      "file": "<name_of_the_file_deleted>"
    }   
  ```
    
In case of failure

  ```json     
    {
      "status": "failed",
      "message": "xxxxxxx"
    }
  ```
  

#### 4.1.7 Get file info

**Endpoint**

```http
GET /files/status?file=xxxxxx
Content-Type: application/json
```


**Behavior**

  - Returns:

  ```json
    {
      "status": "ok" or "failure",
      "file": "<name_of_the_file>",
      "path": "<full path>",
      "folder_base": "<folder>",
      "size_bytes": <size in bytes>,
      "suffix": "extension",
      "last_modified_utc": "date",
      "birth_time_utc": "date",
      "created_utc": "date",
      "is_readable": <true or false>,
    }   
  ```


#### 4.1.8 list files

**Endpoint**

```http
GET /files/list
// Optional:
//   ?ext=mp4   (default: mp4)
//   ?all=1     (list all files, ignore ext)
Content-Type: application/json
```


**Behavior**

  - Returns:

  ```json
    {
      "status": "ok",
      "folder_base": "<name_of_the_file_deleted>",
      "count": <numberoffiles>, 
      "files":[xxxxxx]
    }   
  ```
  
}
---

## 5. Display

- A **single OpenCV window** (e.g. `"NVRLite"`) shows all cameras in a **grid**.
- For each frame, capture threads emit:

  ```cpp
  emit frameReady(streamId, bgrMat);
  ```

- A display manager collects frames from all `streamId`s, arranges them into a grid (`cv::hconcat` + `cv::vconcat`), and shows the result.
- When a stream is offline, the capture thread periodically emits a **NO SIGNAL** frame instead.

---

## 6. Configure NVRLite options

### 6.1 Json configuration

The config file must be formatted the following way : 

```json
{
  "streams": [
    { "id": "<name_of_camera>", "url": "<url>" },
    { "id": "<name_of_camera>", "url": "<url>" }
  ],
  "http_port": 8090,
  "autostart":0,
  "display_mode":0,
  "pre_buffering_time":5.0,
  "post_buffering_time":0.5,
  "rec_base_folder":"/home/user/recordings/"   
}
```


- `streams` contains the list of rtsp stream and associated name
- `http_port` defines the REST API port to contact (0 - 65535)
- `autostart` defines if the stream must start at launch
- `display_mode` defines if the display grid is visible  ( 0 = off, 1 = on)
- `pre_buffering_time` defines the time to buffer the packet stream when start is called in seconds ( i.e. will save the last N seconds in the mp4 when the start call is made). This is used to compensate latency
- `post_buffering_time` defines the time to keep recording when stop is called (in seconds) ( i.e. will save N seconds more in the mp4 when the stop call is made)
- `rec_base_folder` defines the folder to save MP4. Will be created if does not exist

Note : Granularity of time is ms inside the app. 

See provided example.json
 
### 6.2 Basic workflow
1. Start NVRLite (QCoreApplication).
2. Capture threads start and either:
   - connect to RTSP and start sending frames and packets, or
   - go into “retry every 5s” + NO SIGNAL display mode.
3. OpenCV window shows all streams in a grid (if autostart)
4. To start reading/streaming for `stream_1`:

    ```bash
    curl -X POST http://<ip>:<port>/stream/start \
         -H "Content-Type: application/json" \
         -d '{"stream_id":"stream_1"}'
    ```
    
5. To start recording for `stream_1`:

   ```bash
   curl -X POST http://<ip>:<port>/record/start \
        -H "Content-Type: application/json" \
        -d '{"stream_id":"stream_1"}'
   ```

6. To stop recording and get the output file path:

   ```bash
   curl -X POST http://<ip>:<port>/record/stop \
        -H "Content-Type: application/json" \
        -d '{"stream_id":"stream_1"}'
   ```

If correct, the response will be  
 
  ```json
  {
    "status": "ok",
    "stream_id": "<camera_name>",
    "file": "<name_of_the_mp4>"
  }
  ```


6. MP4 files are written as:

   ```text
   rec_<streamId>_YYYY-MM-DD_HH-MM-SS.mp4
   ```

---

## 7. Notes & Tips

- Ensure your RTSP source is sending **SPS/PPS** in-band so that FFmpeg can capture `extradata` and the MP4 is playable.
- If you see “dimensions not set” or invalid MP4s:
  - Make sure `StreamInfo.width/height` are updated after the **first decoded frame** (as in the current code).
  - Ensure you pass correct `codec_id` and `extradata` into the MP4 muxer.
- For heavy loads (many cameras), make sure:
  - Each `RtspCaptureThread` runs in its own thread.
  - Each `Mp4RecorderWorker` is in a separate `QThread` to avoid blocking.

---

## 8. Roadmap

- Stream Start/Stop control and autostart
- MQTT controls
- ONVIF device discovery
- Metadata overlay (timestamps, camera name, etc.)
- Export / share segments via HTTP

---



## Live Slicer pre-MVP (webcam)

O repositório também contém um protótipo independente em Python para validar o fluxo de captura de clipes curtos: webcam do computador, buffer circular de até 45 segundos e tecla Espaço para exportar MP4/H.264.

Consulte [pre_mvp/README.md](pre_mvp/README.md) para instalação, uso, opções, testes e critérios de validação manual. Este protótipo não substitui nem está integrado ao aplicativo C++/RTSP descrito acima.

**Status:** implementação pré-MVP; a validação final com webcam física, foco do teclado e reprodução dos arquivos deve ocorrer no computador-alvo antes de considerar a versão validada.

**Futuro:** recursos de visão computacional permanecem fora do escopo atual e estão documentados em [VISION_COMPUTER_VISION_FUTURE.md](VISION_COMPUTER_VISION_FUTURE.md).
