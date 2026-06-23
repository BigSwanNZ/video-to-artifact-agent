# Roadmap

## Milestone 0: Public Skeleton

- Create the public repository.
- Publish architecture, safety rules, and contribution conventions.
- Define the capability manifest and evidence spec schemas.
- Open GitHub Issues mirroring the first Paperclip task tree.

## Milestone 1: Local Mac Proof

- Implement `mac-mlx` MiniCPM-V 4.6 adapter. Done in PR #11.
- Support direct video URL analysis where the backend can stream the source. Done in PR #11.
- Add ASR/subtitle ingestion with coverage checks. MVP implemented.
- Reproduce the data-center Excel demo from a sanitized spec. MVP implemented with synthetic transcript.

## Milestone 2: Agent-Neutral Interfaces

- Add stable CLI commands. MVP implemented.
- Add HTTP API. MVP implemented.
- Add MCP-style tool manifest and dispatch. MVP implemented.
- Document how Codex, Hermes, Kimi Code, and custom agents call the same workflow.

## Milestone 3: Builders And Verification

- Excel builder with formula checks. MVP implemented.
- Visual render checks.
- Web app builder with Playwright verification.
- Generic artifact spec and provenance report.

## Milestone 4: Runtime Matrix

- Linux CUDA / Transformers adapter.
- CPU fallback adapter.
- Remote OpenAI-compatible VLM adapter.
- Mobile perception-node design for MiniCPM-V 4.6.

## Milestone 5: Benchmarks

Benchmark across:

- Excel financial modeling training videos.
- Software tutorials.
- Web/product recreation demos.
- Quant trading education videos.
- Data analysis dashboard walkthroughs.
