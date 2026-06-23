from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import typer

from video_to_artifact_agent.privacy import redact_text, redact_url
from video_to_artifact_agent.runtimes.mac_mlx import (
    DEFAULT_MODEL as MAC_MLX_DEFAULT_MODEL,
    DEFAULT_PROMPT as MAC_MLX_DEFAULT_PROMPT,
    MacMlxRuntimeAdapter,
    MacMlxRuntimeConfig,
)
from video_to_artifact_agent.schemas import (
    CLI_EXIT_CODES,
    ArtifactRequirement,
    BuildSpec,
    EvidenceKind,
    EvidenceRecord,
    RuntimeCapability,
    SourceInfo,
    SourceKind,
    VerificationCheck,
    VerificationReport,
)

app = typer.Typer(help="Turn video evidence into verified artifacts.")


def write_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload + "\n", encoding="utf-8")


def source_info_from_input(source: str) -> SourceInfo:
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        return SourceInfo(kind=SourceKind.url, url=source, evidence_level="L0")
    return SourceInfo(kind=SourceKind.local_file, local_path=source, evidence_level="L0")


def display_source_info(source: SourceInfo) -> dict[str, object]:
    payload = source.model_dump(mode="json")
    if isinstance(payload.get("url"), str):
        payload["url"] = redact_url(payload["url"])
    return payload


def mac_mlx_adapter(
    model: str,
    executable: str,
    max_tokens: int,
    temperature: float,
    timeout_sec: int,
    max_num_frames: int,
    max_width: int | None,
) -> MacMlxRuntimeAdapter:
    return MacMlxRuntimeAdapter(
        MacMlxRuntimeConfig(
            model=model,
            executable=executable,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout_sec=timeout_sec,
            max_num_frames=max_num_frames,
            max_width=max_width,
        )
    )


@app.command()
def capabilities(
    runtime: str = typer.Option("dev-placeholder", help="Runtime adapter name."),
    model: str = typer.Option("not-configured", help="Model identifier."),
    engine: str | None = typer.Option(None, help="Execution engine such as mlx-vlm or transformers."),
    video_url: bool = typer.Option(False, "--video-url", help="Runtime supports direct video URLs."),
    local_video: bool = typer.Option(False, "--local-video", help="Runtime supports local video files."),
    image: bool = typer.Option(False, "--image", help="Runtime supports image inputs."),
    asr: bool = typer.Option(False, "--asr", help="Runtime supports ASR directly."),
    subtitles: bool = typer.Option(False, "--subtitles", help="Runtime can load subtitles."),
    stream_headers: bool = typer.Option(False, "--stream-headers", help="Runtime accepts stream headers."),
    max_num_frames: int | None = typer.Option(None, help="Maximum frames accepted by the runtime."),
) -> None:
    """Print a runtime capability manifest."""
    manifest = RuntimeCapability(
        runtime=runtime,
        model=model,
        engine=engine,
        supports_video_url=video_url,
        supports_local_video=local_video,
        supports_image=image,
        supports_asr=asr,
        supports_subtitles=subtitles,
        supports_stream_headers=stream_headers,
        max_num_frames=max_num_frames,
        privacy="local",
    )
    typer.echo(manifest.model_dump_json(indent=2))


@app.command(name="mac-mlx-capabilities")
def mac_mlx_capabilities(
    model: str = typer.Option(MAC_MLX_DEFAULT_MODEL, help="MLX model identifier."),
    executable: str = typer.Option("mlx_vlm.generate", help="mlx-vlm command to invoke."),
    max_tokens: int = typer.Option(512, help="Maximum response tokens for observation."),
    temperature: float = typer.Option(0.0, help="Model sampling temperature."),
    timeout_sec: int = typer.Option(420, help="Runtime timeout in seconds."),
    max_num_frames: int = typer.Option(128, help="Maximum video frames requested by the adapter."),
    max_width: int | None = typer.Option(1280, help="Optional video resize width."),
) -> None:
    """Print the Apple Silicon MLX MiniCPM-V runtime manifest."""
    adapter = mac_mlx_adapter(
        model=model,
        executable=executable,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout_sec=timeout_sec,
        max_num_frames=max_num_frames,
        max_width=max_width,
    )
    typer.echo(adapter.capability().model_dump_json(indent=2))


@app.command(name="mac-mlx-command")
def mac_mlx_command(
    source: str = typer.Argument(..., help="Direct video URL or local video path."),
    prompt: str = typer.Option(MAC_MLX_DEFAULT_PROMPT, help="Observation prompt."),
    model: str = typer.Option(MAC_MLX_DEFAULT_MODEL, help="MLX model identifier."),
    executable: str = typer.Option("mlx_vlm.generate", help="mlx-vlm command to invoke."),
    max_tokens: int = typer.Option(512, help="Maximum response tokens for observation."),
    temperature: float = typer.Option(0.0, help="Model sampling temperature."),
    timeout_sec: int = typer.Option(420, help="Runtime timeout in seconds."),
    max_num_frames: int = typer.Option(128, help="Maximum video frames requested by the adapter."),
    max_width: int | None = typer.Option(1280, help="Optional video resize width."),
    unsafe_show_secret_urls: bool = typer.Option(
        False,
        "--unsafe-show-secret-urls",
        help="Print raw URL query strings. Avoid in logs and shared output.",
    ),
) -> None:
    """Print the mac-mlx invocation envelope without running the model."""
    adapter = mac_mlx_adapter(
        model=model,
        executable=executable,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout_sec=timeout_sec,
        max_num_frames=max_num_frames,
        max_width=max_width,
    )
    source_info = source_info_from_input(source)
    raw_command = adapter.build_command(source_info, prompt)
    payload = {
        "runtime": adapter.capability().model_dump(mode="json"),
        "source": display_source_info(source_info),
        "command": raw_command if unsafe_show_secret_urls else adapter.redacted_command(source_info, prompt),
        "redacted_command": adapter.redacted_command(source_info, prompt),
        "secret_material_omitted": not unsafe_show_secret_urls,
    }
    typer.echo(json.dumps(payload, indent=2))


@app.command(name="mac-mlx-observe")
def mac_mlx_observe(
    source: str = typer.Argument(..., help="Direct video URL or local video path."),
    out: Path = typer.Option(Path("runs/mac-mlx/spec.json"), help="Output build spec path."),
    prompt: str = typer.Option(MAC_MLX_DEFAULT_PROMPT, help="Observation prompt."),
    artifact_type: str = typer.Option("unknown", help="Target artifact type."),
    title: str | None = typer.Option(None, help="Artifact title."),
    instructions: str | None = typer.Option(None, help="Builder instructions."),
    model: str = typer.Option(MAC_MLX_DEFAULT_MODEL, help="MLX model identifier."),
    executable: str = typer.Option("mlx_vlm.generate", help="mlx-vlm command to invoke."),
    max_tokens: int = typer.Option(512, help="Maximum response tokens for observation."),
    temperature: float = typer.Option(0.0, help="Model sampling temperature."),
    timeout_sec: int = typer.Option(420, help="Runtime timeout in seconds."),
    max_num_frames: int = typer.Option(128, help="Maximum video frames requested by the adapter."),
    max_width: int | None = typer.Option(1280, help="Optional video resize width."),
) -> None:
    """Run MiniCPM-V through mlx-vlm and write an L3 build spec."""
    adapter = mac_mlx_adapter(
        model=model,
        executable=executable,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout_sec=timeout_sec,
        max_num_frames=max_num_frames,
        max_width=max_width,
    )
    source_info = source_info_from_input(source)
    try:
        result = adapter.observe(source_info, prompt)
    except (RuntimeError, ValueError, TimeoutError) as exc:
        typer.echo(redact_text(str(exc)), err=True)
        raise typer.Exit(3) from exc

    spec = BuildSpec(
        source=source_info,
        runtime=adapter.capability(),
        observations=[result.observation],
        evidence=[result.evidence],
        artifact=ArtifactRequirement(
            artifact_type=artifact_type,  # type: ignore[arg-type]
            title=title,
            instructions=instructions,
        ),
        requirements={
            "workflow_stage": "visual_observation_complete",
            "prompt": prompt,
            "runtime_command": result.redacted_command,
        },
    )
    write_json(out, spec.model_dump_json(indent=2))
    typer.echo(f"Wrote mac-mlx build spec: {out}")


@app.command()
def analyze(
    source: str = typer.Argument(..., help="Video URL or local video path."),
    out: Path = typer.Option(Path("runs/spec.json"), help="Output build spec path."),
    artifact_type: str = typer.Option("unknown", help="Target artifact type."),
    title: str | None = typer.Option(None, help="Artifact title."),
    instructions: str | None = typer.Option(None, help="Builder instructions."),
    runtime: str = typer.Option("unconfigured", help="Runtime adapter name."),
    model: str = typer.Option("unconfigured", help="Model identifier."),
) -> None:
    """Create an initial build spec for a video source.

    This command records the source and requested artifact without doing model
    inference. Runtime adapters enrich this spec with L2/L3 evidence.
    """
    spec = BuildSpec(
        source=source_info_from_input(source),
        runtime=RuntimeCapability(runtime=runtime, model=model),
        evidence=[
            EvidenceRecord(
                kind=EvidenceKind.metadata,
                level="L0",
                summary="Initial source registered by CLI; no video or ASR evidence has been collected yet.",
                source_ref=redact_text(source),
            )
        ],
        artifact=ArtifactRequirement(
            artifact_type=artifact_type,  # type: ignore[arg-type]
            title=title,
            instructions=instructions,
        ),
        requirements={"workflow_stage": "analysis_requested"},
    )
    write_json(out, spec.model_dump_json(indent=2))
    typer.echo(f"Wrote build spec: {out}")


@app.command()
def build(
    spec_path: Path = typer.Argument(..., help="Build spec JSON path."),
    out: Path = typer.Option(Path("artifacts/artifact-handoff.json"), help="Builder handoff output."),
) -> None:
    """Create a builder handoff manifest from a build spec.

    Real builders will replace this placeholder per artifact type. The command
    already validates the shared spec contract and writes an auditable handoff.
    """
    spec = BuildSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
    manifest = {
        "version": 1,
        "artifact_type": spec.artifact.artifact_type,
        "title": spec.artifact.title,
        "source": spec.source.model_dump(mode="json"),
        "achieved_evidence_level": spec.achieved_evidence_level,
        "builder": spec.artifact.builder or "handoff-placeholder",
        "status": "ready_for_builder",
    }
    write_json(out, json.dumps(manifest, indent=2))
    typer.echo(f"Wrote builder handoff: {out}")


@app.command()
def verify(
    path: Path = typer.Argument(..., help="Artifact or handoff path to verify."),
    spec: Path | None = typer.Option(None, help="Optional build spec path."),
    out: Path = typer.Option(Path("artifacts/verification-report.json"), help="Verification report path."),
) -> None:
    """Verify a generated artifact path and optional build spec."""
    checks: list[VerificationCheck] = []
    if not path.exists():
        report = VerificationReport(
            artifact_path=str(path),
            spec_path=str(spec) if spec else None,
            status="failed",
            checks=[
                VerificationCheck(
                    name="artifact_exists",
                    status="failed",
                    message=f"Artifact path does not exist: {path}",
                    expected=True,
                    observed=False,
                )
            ],
        )
        write_json(out, report.model_dump_json(indent=2))
        raise typer.Exit(2)

    checks.append(
        VerificationCheck(
            name="artifact_exists",
            status="passed",
            message="Artifact path exists.",
            expected=True,
            observed=True,
        )
    )
    if spec is not None:
        try:
            BuildSpec.model_validate_json(spec.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - exact pydantic exception can vary
            checks.append(
                VerificationCheck(
                    name="spec_contract",
                    status="failed",
                    message=str(exc),
                    expected="valid BuildSpec",
                    observed="invalid",
                )
            )
        else:
            checks.append(
                VerificationCheck(
                    name="spec_contract",
                    status="passed",
                    message="Build spec validates against the public schema.",
                    expected="valid BuildSpec",
                    observed="valid",
                )
            )

    report = VerificationReport(
        artifact_path=str(path),
        spec_path=str(spec) if spec else None,
        status="passed",
        checks=checks,
    )
    write_json(out, report.model_dump_json(indent=2))
    if report.status != "passed":
        raise typer.Exit(2)
    typer.echo(f"Wrote verification report: {out}")


@app.command(name="schema")
def schema_command(
    model: str = typer.Argument("build-spec", help="build-spec, capability, or verification-report"),
) -> None:
    """Print JSON schema for public contracts."""
    models = {
        "build-spec": BuildSpec,
        "capability": RuntimeCapability,
        "verification-report": VerificationReport,
    }
    selected = models.get(model)
    if selected is None:
        raise typer.BadParameter(f"Unknown schema model: {model}")
    typer.echo(json.dumps(selected.model_json_schema(), indent=2))


@app.command(name="exit-codes")
def exit_codes() -> None:
    """Print documented CLI exit codes."""
    typer.echo(json.dumps([code.model_dump() for code in CLI_EXIT_CODES], indent=2))


if __name__ == "__main__":
    app()
