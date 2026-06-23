# Runtime Matrix

Adapters declare capability manifests so agents choose by evidence need, privacy
mode, and local hardware instead of guessing from model names.

| Runtime | Status | Video URL | Local Video | Privacy | Notes |
| --- | --- | ---: | ---: | --- | --- |
| `mac-mlx` | implemented | yes | yes | local | Apple Silicon, `mlx-vlm`, MiniCPM-V 4.6 family |
| `linux-transformers-cuda` | planned | yes | yes | local/hybrid | Server deployment for NVIDIA GPUs |
| `cpu-transformers` | planned | limited | yes | local | Slow smoke tests and CI fixtures |
| `remote-openai-compatible` | planned | provider dependent | provider dependent | remote/hybrid | Enterprise or hosted VLM endpoint |
| `mobile-minicpm` | design | no | yes | local | Edge perception node for iOS, Android, HarmonyOS |

## Selection Rules

1. Prefer local runtimes for private training material.
2. Prefer direct URL support when the source resolver can produce a short-lived
   stream URL without writing media to disk.
3. Require L3 visual evidence for UI/product recreation and spreadsheet screen
   replication.
4. Require L2 transcript or ASR evidence when spoken logic affects formulas,
   workflows, or business rules.
5. Treat mobile runtimes as perception nodes: they can observe and summarize, but
   builders and verifiers usually run elsewhere.
