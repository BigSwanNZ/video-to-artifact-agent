# Local Mac Kimi + oMLX + MiniCPM-V 4.6 Route

This example records the sanitized route that succeeded on the maintainer's
local Mac. It is not the generic install guide. It is a public, reproducible
shape of the working node graph so contributors can see which parts were proven
together and which parts are local-machine configuration.

No cookies, signed video URLs, raw downloaded videos, private transcripts, model
weights, or local run artifacts are committed here.

## Boundary

The local Codex skill `minicpm-video-artifact` is the maintainer-machine memory:
it tells local agents how this Mac is already configured. The public repository
documents the portable contract and a sanitized validation trace. Other machines
should reproduce the route by supplying their own model cache, video source, and
runtime paths.

## Validated Node Graph

```text
Codex Desktop or Kimi Code style agent host
  -> video-to-artifact-agent CLI contract
  -> v2a mac-mlx-command for redacted command inspection
  -> v2a mac-mlx-observe for L3 visual evidence
  -> mac-mlx runtime adapter
  -> oMLX bundled Python runtime
  -> oMLX framework-mlx-base site-packages for mlx-vlm
  -> workspace venv site-packages for cv2 video decoding
  -> mlx_vlm.generate --video
  -> mlx-community/MiniCPM-V-4.6-4bit
  -> BuildSpec with L3 video_observation evidence
  -> optional L2 subtitles or ASR
  -> artifact builder, such as Excel
  -> verifier
```

Kimi Code is not vendored into this repository. It is an acknowledged agent
surface and design reference because the target workflow is the same class of
agent task: give the agent a video and ask it to recreate the demonstrated
artifact. Kimi Code, Codex, Hermes, or another host should call the same CLI,
HTTP, or MCP-style contracts rather than requiring separate project logic.

## Local Runtime Shape

The successful Mac route used:

```text
/Applications/oMLX.app/Contents/Resources/Python/cpython-3.11/bin/python3.11
/Applications/oMLX.app/Contents/Resources/Python/framework-mlx-base/lib/python3.11/site-packages
<workspace>/.venvs/omlx-vlm/lib/python3.11/site-packages
~/.omlx/models/mlx-community/MiniCPM-V-4.6-4bit
```

The first site-packages path provides `mlx_vlm`. The workspace venv path provides
`cv2`, which `mlx_vlm` needs when loading video. The public adapter exposes these
as overrideable settings:

```bash
export V2A_MAC_MLX_PYTHON=/path/to/python3.11
export V2A_MAC_MLX_SITE_PACKAGES=/path/to/mlx-vlm/site-packages
export V2A_MAC_MLX_EXTRA_SITE_PACKAGES=/path/to/cv2/site-packages
export V2A_MAC_MLX_MODEL=/path/to/MiniCPM-V-4.6-4bit
```

## Smoke Test

From the repository root:

```bash
PYTHONPATH=src uv run v2a mac-mlx-command "/path/to/smoke.mp4"
```

Inspect the redacted command before running inference. It should show
`python -m mlx_vlm.generate --video`, the oMLX Python, and both site-packages
paths.

Then run:

```bash
PYTHONPATH=src uv run v2a mac-mlx-observe "/path/to/smoke.mp4" \
  --prompt "List the visible colored segments and text briefly." \
  --artifact-type excel \
  --out runs/local-mac-smoke/spec.json \
  --max-tokens 64
```

The maintainer-machine smoke produced an L3 build spec and summarized a synthetic
video containing:

```text
red apple code 731
green circle code 842
blue star code 953
```

This proves the route consumed video through MiniCPM-V 4.6. It does not prove a
particular private training video, because those assets stay outside the public
repository.

## Known Pitfalls

- `minicpmv4_6` unknown architecture means the command probably hit an old
  `mlx-vlm`, such as a global Python package. Fix the launcher before changing
  models.
- `No module named cv2` means the runtime found `mlx_vlm` but not the video
  decoding dependency. Add a site-packages path containing OpenCV.
- `--max-width` is not accepted by the oMLX-bundled `mlx_vlm.generate` used in
  this route. Resize controls should be adapter-specific, not blindly appended.
- `No Metal device available` can happen in sandboxed or headless shells. Run the
  local MLX smoke where the Mac Metal device is visible.

## Next Reproduction Target

Use this example as the Mac-local baseline. Non-Mac reproductions should keep the
same BuildSpec and evidence levels but swap the runtime adapter, for example to
Transformers/CUDA or a GGUF/llama.cpp MiniCPM-V 4.6 route.
