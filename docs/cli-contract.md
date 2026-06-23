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

### `v2a mac-mlx-capabilities`

Prints the built-in Apple Silicon MLX runtime capability manifest for
MiniCPM-V 4.6 through `mlx-vlm`.

### `v2a mac-mlx-command <source>`

Prints the `mlx_vlm.generate --video` invocation envelope without running the
model. The command redacts signed URL query strings by default. Use
`--unsafe-show-secret-urls` only for local debugging where raw URLs will not be
logged or shared.

### `v2a mac-mlx-observe <source>`

Runs the local MLX video runtime and writes a `BuildSpec` containing L3 visual
evidence. This command is the first concrete bridge from direct video
understanding into artifact builders.

### `v2a build <spec.json>`

Validates a `BuildSpec` and emits a builder handoff manifest. Real artifact
builders replace the placeholder by artifact type.

### `v2a verify <artifact> --spec <spec.json>`

Checks that the artifact path exists and that the optional spec validates. Real
verifiers add artifact-specific checks such as formula scans, screenshot checks,
or Playwright tests.

### `v2a schema <name>`

Prints JSON schema for public contracts:

- `build-spec`
- `capability`
- `verification-report`

### `v2a exit-codes`

Prints documented exit codes.

## Exit Codes

| Code | Name | Meaning |
| --- | --- | --- |
| 0 | success | Command completed successfully. |
| 2 | verification_failed | Artifact or evidence verification failed. |
| 3 | blocked | Input, access, or runtime limitation blocked progress. |
| 4 | unsafe_input | Input violated privacy or safety rules. |
