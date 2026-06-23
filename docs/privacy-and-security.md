# Privacy And Security

Video-to-artifact workflows touch sensitive surfaces: cookies, paid videos,
private training material, signed CDN URLs, transcripts, screenshots, and model
cache paths. The project should be safe by default.

## Rules

- Do not log raw cookies, API keys, signed URLs, or local auth headers.
- Do not commit downloaded media, audio, transcripts, or model weights.
- Prefer direct video streaming when supported.
- If ASR needs an audio cache, make it explicit, bounded, and easy to delete.
- Redact source resolver outputs before saving specs.
- Put user-controlled inputs and generated artifacts in separate directories.

## Repository Defaults

The `.gitignore` excludes common media, cookie, model, cache, and run outputs.
Examples should use synthetic or clearly redistributable media only.

