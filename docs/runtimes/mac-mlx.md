# mac-mlx Runtime

The `mac-mlx` adapter is the first concrete runtime for direct video
understanding. It targets Apple Silicon and wraps:

```bash
python -m mlx_vlm.generate --model mlx-community/MiniCPM-V-4.6-4bit --video <source>
```

The model identifier can be overridden. The default points at an MLX-compatible
MiniCPM-V 4.6 conversion while keeping `openbmb/MiniCPM-V-4.6` as the upstream
model family in capability notes.

## Launcher Selection

The default executable is `auto`. On Mac it prefers the oMLX runtime:

```text
/Applications/oMLX.app/Contents/Resources/Python/cpython-3.11/bin/python3.11
/Applications/oMLX.app/Contents/Resources/Python/framework-mlx-base/lib/python3.11/site-packages
<workspace>/.venvs/omlx-vlm/lib/python3.11/site-packages
```

The generated command is equivalent to:

```bash
env PYTHONPATH=/Applications/oMLX.app/Contents/Resources/Python/framework-mlx-base/lib/python3.11/site-packages:<workspace>/.venvs/omlx-vlm/lib/python3.11/site-packages \
  /Applications/oMLX.app/Contents/Resources/Python/cpython-3.11/bin/python3.11 \
  -m mlx_vlm.generate \
  --model ~/.omlx/models/mlx-community/MiniCPM-V-4.6-4bit \
  --video <source>
```

This is intentional. A globally installed `mlx-vlm` can be too old; version
`0.3.13` does not support the `minicpmv4_6` architecture and can fail before
video decoding starts. Do not use bare `python3 -m mlx_vlm.generate` unless that
Python environment is known to contain a current MiniCPM-V 4.6-capable
`mlx-vlm`.

Override the launcher explicitly when needed:

```bash
export V2A_MAC_MLX_PYTHON=/path/to/python
export V2A_MAC_MLX_SITE_PACKAGES=/path/to/site-packages
export V2A_MAC_MLX_EXTRA_SITE_PACKAGES=/path/to/cv2-or-other-site-packages
export V2A_MAC_MLX_MODEL=/path/to/MiniCPM-V-4.6-4bit
```

## Commands

```bash
v2a mac-mlx-capabilities
v2a mac-mlx-command "https://example.com/video.mp4?signature=secret"
v2a mac-mlx-observe "https://example.com/video.mp4?signature=secret" \
  --artifact-type excel \
  --out runs/demo/spec.json
```

`mac-mlx-command` is an audit and debugging command. It prints redacted commands
by default, so signed CDN URLs do not leak into logs. The raw URL remains inside
the actual runtime call when `mac-mlx-observe` executes locally.

## Capability Shape

The adapter currently declares:

- direct video URL support
- local video file support
- image support through the underlying engine
- no built-in ASR or subtitle loading
- local privacy mode

ASR and subtitle evidence are separate stages. The workflow goal is to merge L3
visual observations from this adapter with L2 speech evidence before handing a
spec to Excel, web, code, document, or other builders.

## Security Notes

Do not commit generated `runs/` specs that contain private source URLs. Evidence
records and command logs redact URL query strings and fragments by default, but
the source itself can remain executable in local run artifacts so agents can
resume work within the same trusted environment.
