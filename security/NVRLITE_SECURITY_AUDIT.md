# NVRLite security and Live Slicer fit assessment

**Assessment date:** 2026-10-22  
**Scope:** Initial source-level review of the NVRLite snapshot already present in this repository. This is not a penetration test, dependency CVE scan, build, or runtime test.

## Provenance and copy status

- Upstream: https://github.com/obraun-sl/NVRLite
- Upstream snapshot inspected: `main`, commit `1b08baef2f4563745d1b238ff46797df428bc5a3` (release notes identify v0.2.5).
- The upstream and `bpoltosi/LiveSlicer` `main` trees returned the same Git tree SHA: `1b08baef2f4563745d1b238ff46797df428bc5a3`. The existing repository already contains the same tree; no bulk copy or source replacement was needed.
- The upstream `LICENSE` is the MIT License, copyright Olivier Braun (2025). Keep that notice and the license in redistributed copies. Audit and track the licenses/notices of bundled and linked third-party dependencies separately.

## Executive summary

**Do not expose the HTTP control API to an untrusted network in its current form.** The program starts the HTTP server on `0.0.0.0`, and the reviewed route handlers contain no authentication or authorization checks. The API can start/stop streams and recordings, list recording files, report file metadata, and delete files. A reachable unauthenticated API therefore creates a material control and data-loss risk.

This is a source-review finding, not evidence that the host is reachable from the internet: actual exposure depends on routing, firewall rules, host configuration, and network segmentation.

## Findings

### F-01 — HTTP control and file operations have no visible authentication
**Severity: High if reachable by untrusted clients; otherwise Medium pending deployment controls.**

Evidence: `src/main.cpp` starts the server with `httpServer.start("0.0.0.0", mAppConfig.httpPort)`. Reviewed handlers in `src/http/HttpHandler.cpp` register control and file routes without visible authentication or per-user authorization.

Potential impact: clients that can reach the port may start/stop streams and recordings, enumerate recordings and metadata, or delete recordings using `POST /files/remove`.

Recommended remediation before deployment:
1. Bind to loopback by default where possible, or make the bind address configurable and default to a trusted interface.
2. Until authentication exists, firewall the port so only the local button/controller host can reach it; do not port-forward it.
3. Add authentication and authorization for every route before allowing LAN-wide access. Use TLS if traffic crosses an untrusted network.
4. Add tests proving unauthenticated requests are rejected and authorized users cannot exceed their permissions.

### F-02 — Configuration is logged as serialized JSON
**Severity: Medium; potentially High when RTSP URLs include credentials and logs are broadly accessible.**

Evidence: `include/Utils.hpp` logs `j.dump(1)` after loading the config, and stream URLs are read from the `url` fields. RTSP URLs can embed usernames/passwords.

Potential impact: credentials may be written to application logs, depending on the Qt logging configuration/build and deployment log handling.

Recommended remediation: never log full configuration or raw RTSP URLs. Redact user-info and secrets; review existing logs before sharing them. Keep production logs access-restricted.

### F-03 — Bundled FFmpeg binaries are old ABI generation; exact version and vulnerability status unverified
**Severity: Medium pending inventory.**

Evidence: the repository includes Windows FFmpeg libraries named with ABI generations such as `avcodec-58.dll`, and corresponding headers/libraries under `ext/ffmpeg_win`. The filename alone does not establish the exact FFmpeg release or a specific CVE.

Recommended remediation: identify the precise upstream build/version and compile options; check vendor advisories/CVEs; document FFmpeg's license/build configuration; replace bundled binaries with a supported, reproducible build after compatibility tests. Repeat for OpenCV, Qt, cpp-httplib, nlohmann/json, and other dependencies.

### F-04 — CI test script downloads and executes MediaMTX without checksum verification
**Severity: Low to Medium; supply-chain hardening needed.**

Evidence: `ci/test.sh` downloads MediaMTX v1.8.4 over HTTPS if it is absent, extracts the executable, and runs it. The reviewed script does not verify a pinned checksum/signature before execution.

Recommended remediation: pin the expected SHA-256 (or verify the upstream signature), fail closed on mismatch, and keep the downloaded test binary isolated from production builds.

### F-05 — File path checks exist, but file-management endpoints remain sensitive
**Severity: Medium due to missing authorization; path-traversal exploit not established in reviewed code.**

Evidence: `isSafeBasename()` rejects empty names, `..`, slash, and backslash; both `/files/remove` and `/files/status` use it before resolving a name under the configured base directory. This is a useful defensive check, but it does not replace authorization or tests for platform-specific paths, symlinks, races, and filesystem permissions.

Recommended remediation: retain strict path confinement, canonicalize/verify the final path remains under the recording root, test Windows and Linux edge cases, and require authorization for all file operations. Keep recording storage separate from application/configuration files and restrict filesystem permissions.

### F-06 — No dependency inventory/SBOM or automated vulnerability gate identified in the reviewed files
**Severity: Medium, pending broader repository/CI review.**

Recommended remediation: generate an SBOM, inventory bundled binaries and licenses, add dependency scanning and static analysis to CI, and define a repeatable update process. This review did not establish whether separate external scanning is already used.

## Fit against the Live Slicer MVP

| Requirement | Current evidence | Assessment / change needed |
|---|---|---|
| 2–4 simultaneous RTSP cameras | Config accepts an array of streams; main creates one capture thread and recorder per configured stream | Promising; run 2- and 4-camera stability tests with the target cameras/codecs |
| Keep the last 45 seconds | Default `pre_buffering_time` is 5 seconds; recorder maintains an in-memory encoded-packet prebuffer | Configure to at least 45 seconds and validate keyframe/timestamp behavior and memory caps. Current behavior is not yet proven to guarantee a complete 45-second clip |
| Approximately 60-second fallback | No evidence of a 60-second on-disk rolling-segment store in the reviewed code; prebuffer is memory-based | Add explicit retention/segment design if disk-backed fallback is required |
| Trigger via physical button | HTTP start/stop API exists; no physical button integration identified in reviewed files | Add a small local button adapter (USB HID/serial/GPIO as hardware dictates), with debounce and failure handling |
| Save clips when triggered | API starts/stops recording; prebuffer flushes when recording starts | Validate exact event semantics: desired clip is the 45 seconds *before* the press. Current start/stop recording flow may continue recording after the press and is not yet shown to create a bounded pre-event-only clip |
| Security for local deployment | HTTP listener binds to all interfaces; no auth seen in reviewed routes | Restrict network exposure immediately; add authenticated control before broad LAN use |
| Portability | CMake targets Qt5, OpenCV, and FFmpeg; Windows FFmpeg binaries are bundled | Build and test on the selected OS; document dependency versions and licensing |

## Prioritized work plan

1. **Containment:** do not expose the API beyond a trusted local interface; firewall the configured port.
2. **Audit closure:** inventory exact dependency versions/licenses, scan source and dependencies, inspect all HTTP routes and the complete CI workflow, and run tests under sanitizers where supported.
3. **Requirements prototype:** define trigger semantics precisely; prove multi-camera buffering for 45 seconds and the intended 60-second fallback.
4. **MVP changes on a separate branch:** configurable safe bind address; auth or local-only IPC; redacted logging; robust pre-event clip export and protected buffer segments; physical-button adapter; test suite.
5. **Validation:** malformed HTTP input, unauthenticated access, path traversal/symlink cases, disk-full behavior, RTSP disconnect/reconnect, camera clock/timestamp drift, rapid/repeated button presses, and 2–4 camera soak tests.

## Limitations

This is a preliminary manual source inspection of selected files at the pinned snapshot. No binary execution, fuzzing, penetration test, CVE database scan, exhaustive route review, build, or camera hardware test was performed. Findings should be treated as review items with the evidence and limitations above, not as a certification or exhaustive list of vulnerabilities.
