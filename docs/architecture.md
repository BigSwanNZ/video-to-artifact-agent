# Architecture

Video-to-Artifact Agent is organized around a small set of replaceable stages.

```text
Agent / Operator
  -> Protocol Adapter
  -> Workflow Core
  -> Runtime Adapter
  -> Evidence Merger
  -> Artifact Builder
  -> Verifier
```

## Protocol Adapters

Protocol adapters expose the same workflow to different callers:

- CLI for local operators and CI.
- HTTP API for remote agents and services.
- MCP for agent tool ecosystems.
- ACP adapter when the protocol surface is available.

## Workflow Core

The core owns orchestration, not model-specific details:

1. Resolve source URL and metadata.
2. Ask runtime adapters for capabilities.
3. Produce video observations.
4. Load official subtitles or run ASR.
5. Merge visual and spoken evidence into a build spec.
6. Dispatch to an artifact builder.
7. Run verification and emit a report.

## Runtime Adapter Capability Manifest

Adapters must declare what they can actually do:

```json
{
  "runtime": "mac-mlx",
  "model": "openbmb/MiniCPM-V-4.6",
  "supports_video_url": true,
  "supports_local_video": true,
  "supports_image": true,
  "supports_asr": false,
  "max_num_frames": 128,
  "privacy": "local"
}
```

The orchestrator should never assume video support from a model name alone.

## Evidence Levels

- `L0`: metadata only.
- `L1`: page text, description, comments, or other non-time-aligned context.
- `L2`: subtitles, ASR transcript, or spoken-content evidence.
- `L3`: video frames, OCR, screenshots, or video-observation evidence.

Generated artifacts should include their achieved evidence level.

