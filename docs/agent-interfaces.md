# Agent Interfaces

The workflow core is agent-neutral. Codex, Hermes, Kimi Code, Claude Code,
Cursor, OpenClaw, or a custom orchestrator should call the same contracts.

## CLI

The CLI is the lowest common denominator and works in local shells, CI, and
agent subprocess tools:

```bash
v2a analyze <source> --artifact-type excel --out runs/demo/spec.json
v2a attach-transcript runs/demo/spec.json transcript.srt --audio-duration-sec 120
v2a build runs/demo/spec.json --out artifacts/demo.xlsx
v2a verify artifacts/demo.xlsx --spec runs/demo/spec.json
```

## HTTP

Run the adapter:

```bash
v2a serve-http --host 127.0.0.1 --port 8765
```

Useful routes:

- `GET /health`
- `GET /capabilities`
- `GET /schemas/build-spec`
- `POST /analyze`

## MCP-Style Tool Calls

Hosts that support MCP-style tools can inspect:

```bash
v2a mcp-manifest
```

Shell-only hosts can dispatch locally:

```bash
v2a mcp-call video_to_artifact.analyze \
  --arguments-json '{"source":"https://example.com/video.mp4","artifact_type":"excel"}'
```

## Evidence Contract

Agents should treat the build spec as the handoff object:

- L3 video observations describe visible screens, UI state, formulas, and layout.
- L2 transcript evidence captures spoken logic and time-aligned instructions.
- Builders consume the merged spec.
- Verifiers produce a `VerificationReport`.

Adapters must not log cookies, signed URL query strings, raw private
transcripts, or model cache paths.
