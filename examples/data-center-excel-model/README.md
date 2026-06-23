# Data Center Excel Model Demo

This demo will reproduce the validated local experiment in a sanitized form.

The private/local experiment proved:

- MiniCPM-V 4.6 read the online training video stream directly.
- ASR added spoken modeling logic with greater than 95% coverage.
- The merged evidence produced an Excel data-center development model.
- Formula checks and rendered workbook previews passed.

The public demo must not include the original cookies, media cache, signed URLs,
or private transcripts. It should use either a synthetic redistributable video
or a user-supplied video URL at runtime.

## Local Synthetic Run

This run uses a user-supplied or synthetic source URL plus the checked-in
synthetic transcript. No private media is committed.

```bash
PYTHONPATH=src python3 -m video_to_artifact_agent.cli.main analyze \
  synthetic://data-center-excel-model \
  --artifact-type excel \
  --title "Data center model" \
  --instructions "Create a verifiable revenue, cost, gross profit, and margin workbook." \
  --out runs/data-center/spec.json

PYTHONPATH=src python3 -m video_to_artifact_agent.cli.main attach-transcript \
  runs/data-center/spec.json \
  examples/data-center-excel-model/transcript.srt \
  --audio-duration-sec 12 \
  --require-coverage

PYTHONPATH=src python3 -m video_to_artifact_agent.cli.main build \
  runs/data-center/spec.json \
  --out artifacts/data-center-model.xlsx

PYTHONPATH=src python3 -m video_to_artifact_agent.cli.main verify \
  artifacts/data-center-model.xlsx \
  --spec runs/data-center/spec.json \
  --out artifacts/data-center-verification.json
```

For a real video, replace the `analyze` step with `mac-mlx-observe` after
installing `mlx-vlm` and a MiniCPM-V 4.6 MLX-compatible model.

For the maintainer-machine route that has already succeeded with Kimi Code as an
agent-surface reference, oMLX, `mlx-vlm`, and MiniCPM-V 4.6, see
[../local-mac-kimi-omlx-minicpm/README.md](../local-mac-kimi-omlx-minicpm/README.md).
