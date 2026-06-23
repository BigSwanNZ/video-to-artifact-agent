# Video-to-Artifact Agent

Agent-neutral workflow for turning training and demo videos into verified artifacts.

The initial target is the workflow we proved locally:

```text
online video URL
  -> video-capable VLM observes the video stream
  -> subtitles or ASR provide spoken logic
  -> evidence merger creates a build spec
  -> an artifact builder creates Excel, web, code, docs, or other outputs
  -> verifiers check formulas, visuals, coverage, and provenance
```

This project is not a Codex-only plugin. Codex, Hermes, Kimi Code, Claude Code,
OpenClaw, Cursor, or a custom agent should all be able to call the same core
through CLI, HTTP, MCP, or future ACP adapters.

## Status

Pre-alpha. The local proof of concept has validated:

- MiniCPM-V 4.6 can read an online video stream through a local MLX runtime.
- ASR can recover the spoken structure when official subtitles are missing.
- The merged evidence can drive an Excel financial model builder.
- The resulting workbook can be checked for formula errors and visible layout.

The public repository starts by turning that proof into a clean, reproducible,
privacy-aware toolkit.

## Design Principles

- **Agent-neutral core:** agents call the workflow; the workflow is not owned by any one agent product.
- **Evidence first:** generated artifacts should trace back to video, subtitles, ASR, user inputs, and verification results.
- **No silent media hoarding:** direct video streaming is preferred; any audio/video cache must be explicit, bounded, and disposable.
- **Runtime adapters:** Mac, Linux GPU, CPU fallback, remote API, and mobile deployments are separate adapters with declared capabilities.
- **Verification is mandatory:** builders must produce outputs that can be checked, not just plausible screenshots.

## Runtime Targets

| Runtime | First adapter target | Purpose |
| --- | --- | --- |
| Apple Silicon Mac | MLX / mlx-vlm / oMLX | Local video understanding and fast experimentation |
| Linux + NVIDIA | Transformers / CUDA | Server and team deployment |
| CPU fallback | Transformers CPU or future quantized backends | Slow but accessible smoke tests |
| Mobile | MiniCPM-V 4.6 on iOS / Android / HarmonyOS | Edge perception node |
| Remote API | OpenAI-compatible VLM endpoint | Hosted or enterprise deployments |

Each adapter reports a capability manifest so agents can choose the right path
without guessing.

## CLI Contract

```bash
v2a capabilities \
  --runtime mac-mlx \
  --model openbmb/MiniCPM-V-4.6 \
  --video-url \
  --local-video \
  --image \
  --max-num-frames 128

v2a analyze https://example.com/video \
  --artifact-type excel \
  --title "Demo model" \
  --runtime mac-mlx \
  --model openbmb/MiniCPM-V-4.6 \
  --out runs/demo/spec.json

v2a attach-transcript runs/demo/spec.json examples/data-center-excel-model/transcript.srt \
  --audio-duration-sec 12 \
  --require-coverage

v2a build runs/demo/spec.json --out artifacts/demo.xlsx
v2a verify artifacts/demo.xlsx --spec runs/demo/spec.json
v2a schema build-spec
v2a exit-codes
v2a mcp-manifest
```

The current implementation validates and emits the public contracts, and includes
an initial Apple Silicon `mac-mlx` adapter:

```bash
v2a mac-mlx-capabilities
v2a mac-mlx-command "https://example.com/video.mp4?signature=secret"
v2a mac-mlx-observe "https://example.com/video.mp4?signature=secret" \
  --artifact-type excel \
  --out runs/demo/spec.json
```

`mac-mlx-command` redacts signed URL query strings by default. Runtime execution
uses `mlx_vlm.generate --video` and writes L3 visual evidence into the build
spec. `attach-transcript` adds L2 subtitle or ASR evidence. Excel specs build to
real `.xlsx` workbooks with formula checks.

HTTP and MCP-style adapters expose the same contracts to non-Codex agents:

```bash
v2a serve-http --host 127.0.0.1 --port 8765
v2a mcp-call video_to_artifact.analyze \
  --arguments-json '{"source":"https://example.com/video.mp4","artifact_type":"excel"}'
```

## Repository Layout

```text
docs/                       architecture and safety notes
src/video_to_artifact_agent core package
examples/                   reproducible demos without private cookies or videos
tests/                      unit and smoke tests
```

## Task Management

GitHub Issues are the public collaboration surface. Paperclip can be used as an
internal agent coordination plane for goals, projects, assignees, and threaded
work logs. See [docs/task-management.md](docs/task-management.md).

## Privacy And Safety

Never commit cookies, signed CDN URLs, raw private transcripts, downloaded
training videos, model weights, or local cache paths. The project should support
redaction and cache cleanup by default.
