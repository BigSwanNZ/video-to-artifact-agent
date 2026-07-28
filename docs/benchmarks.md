# Benchmarks

The benchmark layer tracks whether a video-to-artifact run met evidence,
artifact, and verification expectations. It starts with lightweight JSON
manifests so teams can add cases without committing private videos.

Seed manifest:

```bash
examples/benchmark-manifest.json
```

Each case records:

- source reference, usually synthetic or user supplied
- target artifact type
- expected evidence level
- acceptance checks

The Python API in `video_to_artifact_agent.benchmarks` can load a manifest and
evaluate a `BuildSpec` plus optional `VerificationReport`.
