# Project documentation index

This directory contains focused engineering notes. Use this index to distinguish current guides from historical release notes and work that is still under review.

## Current project guides

- [Repository overview, setup, and project status](../README.md) — entry point for the C++/RTSP application and the independent Python webcam pre-MVP.
- [Python webcam pre-MVP guide](../pre_mvp/README.md) — installation, runtime options, tests, resource limits, and manual acceptance checks.
- [45-second RTSP pre-buffer design and acceptance checklist](PREBUFFER_45S.md) — design notes for the C++ recorder's RTSP packet buffer. This is separate from the Python webcam buffer.
- [Computer-vision future roadmap](../VISION_COMPUTER_VISION_FUTURE.md) — explicitly deferred work; not part of the current pre-MVP.
- [Security audit](../security/NVRLITE_SECURITY_AUDIT.md) — security findings and recommendations for the legacy C++/HTTP application.

## Change history

- [Changelog](../CHANGELOG.md) — recent project-level changes and known validation gaps.
- [Legacy C++ application release notes](../ReleaseNotes.md) — historical NVRLite releases (v0.1.0–v0.2.5); retained because they describe the original C++ application.

## Validation reminder

Unit tests do not verify physical webcam access, keyboard focus, sustained resource use, or the integrity of exported MP4s on the target computer. Complete the manual acceptance steps in the relevant guide before declaring the pre-MVP validated or publishing a release.

## Repository hygiene policy

- Keep files that are referenced by build scripts, tests, sample configurations, active pull requests, or historical release documentation.
- Do not delete bundled dependencies, media fixtures, or legacy documentation solely because they are large or old.
- Remove files only after checking references and confirming their purpose has been superseded.
- Keep `main`; retain branches associated with open pull requests until those requests are resolved.
