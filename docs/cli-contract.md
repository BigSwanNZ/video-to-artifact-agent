# CLI Contract

The CLI is the lowest common denominator for agents. Codex, Hermes, Kimi Code,
Claude Code, OpenClaw, or a custom script should all be able to call it without
depending on a specific agent host.

## Commands

### `v2a capabilities`

Prints a runtime capability manifest.

### `v2a analyze <source>`

Creates a `BuildSpec` JSON file. At this stage, the command only records source
metadata and requested artifact type. Runtime adapters enrich the spec with L2
and L3 evidence.

Signed URL query strings and fragments are redacted before being written to the
spec.

### `v2a mac-mlx-capabilities`

Prints the built-in Apple Silicon MLX runtime capability manifest for
MiniCPM-V 4.6 through `mlx-vlm`.

### `v2a mac-mlx-command <source>`

Prints the `mlx_vlm.generate --video` invocation envelope without running the
model. The command redacts signed URL query strings by default. Use
`--unsafe-show-secret-urls` only for local debugging where raw URLs will not be
logged or shared.

The default launcher is `auto`; on Apple Silicon this should resolve to the oMLX
bundled Python plus its `framework-mlx-base` site-packages. Agents should not
replace it with bare `python3` unless that environment is known to support the
MiniCPM-V 4.6 `minicpmv4_6` architecture.

### `v2a mac-mlx-observe <source>`

Runs the local MLX video runtime and writes a `BuildSpec` containing L3 visual
evidence. This command is the first concrete bridge from direct video
understanding into artifact builders.

### `v2a attach-transcript <spec.json> <transcript>`

Parses SRT, WebVTT, or JSON transcript segments and attaches L2 subtitle or ASR
evidence to a build spec. Coverage gates can block short transcripts:

```bash
v2a attach-transcript runs/demo/spec.json demo.srt \
  --audio-duration-sec 300 \
  --coverage-threshold-pct 95 \
  --require-coverage
```

### `v2a build <spec.json>`

Validates a `BuildSpec` and emits an artifact. Excel specs produce a real
`.xlsx` workbook with `Inputs`, `Model`, and `Checks` sheets. Other artifact
types currently emit a builder handoff manifest.

### `v2a verify <artifact> --spec <spec.json>`

Checks that the artifact path exists and that the optional spec validates. Excel
workbooks run OpenXML package, required sheet, and formula checks.

### `v2a schema <name>`

Prints JSON schema for public contracts:

- `build-spec`
- `capability`
- `verification-report`

### `v2a exit-codes`

Prints documented exit codes.

### `v2a serve-http`

Runs the lightweight HTTP adapter with `/health`, `/capabilities`,
`/schemas/build-spec`, and `/analyze`.

### `v2a mcp-manifest`

Prints the MCP-style tool manifest.

### `v2a mcp-call <tool>`

Dispatches a MCP-style tool call locally for hosts that can shell out to the
CLI.

## Exit Codes

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | success | Command completed successfully. |
| 2 | verification_failed | Artifact or evidence verification failed. |
| 3 | blocked | Input, access, or runtime limitation blocked progress. |
| 4 | unsafe_input | Input violated privacy or safety rules. |
