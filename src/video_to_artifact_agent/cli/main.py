from __future__ import annotations

import json
from pathlib import Path

import typer

from video_to_artifact_agent.schemas import RuntimeCapability

app = typer.Typer(help="Turn video evidence into verified artifacts.")


@app.command()
def capabilities() -> None:
    """Print the placeholder local capability manifest."""
    manifest = RuntimeCapability(
        runtime="dev-placeholder",
        model="not-configured",
        supports_video_url=False,
        supports_local_video=False,
        supports_image=False,
        supports_asr=False,
        privacy="local",
    )
    typer.echo(manifest.model_dump_json(indent=2))


@app.command()
def analyze(
    source: str = typer.Argument(..., help="Video URL or local video path."),
    out: Path = typer.Option(Path("runs/spec.json"), help="Output build spec path."),
) -> None:
    """Create a placeholder build spec for a video source."""
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": {"url": source, "evidence_level": "L0"},
        "observations": [],
        "transcript_segments": [],
        "artifact_type": "unknown",
        "requirements": {"status": "placeholder"},
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    typer.echo(f"Wrote placeholder spec: {out}")


@app.command()
def verify(path: Path) -> None:
    """Placeholder verifier command."""
    if not path.exists():
        raise typer.BadParameter(f"Path does not exist: {path}")
    typer.echo(f"Verification placeholder accepted: {path}")


if __name__ == "__main__":
    app()

