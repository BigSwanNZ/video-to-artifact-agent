from __future__ import annotations

import json
from pathlib import Path
import typer

from video_to_artifact_agent.adapters.http import make_server
from video_to_artifact_agent.adapters.mcp import dispatch_tool, tool_manifest
from video_to_artifact_agent.builders.excel import build_excel_workbook
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
    RuntimeCapability,
    SourceInfo,
    VerificationCheck,
    VerificationReport,
)
from video_to_artifact_agent.transcripts import (
    TranscriptCoverageError,
    merge_transcript_evidence,
    parse_transcript_file,
)
from video_to_artifact_agent.verifiers.excel import verify_excel_workbook
from video_to_artifact_agent.workflow import create_initial_spec, redacted_source_info, source_info_from_input

app = typer.Typer(help="Turn video evidence into verified artifacts.")


def write_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload + "\n", encoding="utf-8")


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
        source=redacted_source_info(source_info),
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
    spec = create_initial_spec(
        source,
        artifact_type=artifact_type,
        title=title,
        instructions=instructions,
        runtime=RuntimeCapability(runtime=runtime, model=model),
    )
    write_json(out, spec.model_dump_json(indent=2))
    typer.echo(f"Wrote build spec: {out}")


@app.command(name="attach-transcript")
def attach_transcript(
    spec_path: Path = typer.Argument(..., help="Build spec JSON path."),
    transcript_path: Path = typer.Argument(..., help="SRT, WebVTT, or JSON transcript path."),
    out: Path | None = typer.Option(None, help="Output spec path; defaults to overwriting spec_path."),
    kind: str = typer.Option("subtitle", help="Transcript evidence kind: subtitle or asr."),
    language: str | None = typer.Option(None, help="Transcript language code."),
    audio_duration_sec: float | None = typer.Option(None, help="Audio/video duration for coverage calculation."),
    model: str | None = typer.Option(None, help="ASR/subtitle model or provider identifier."),
    coverage_threshold_pct: float = typer.Option(95.0, help="Minimum transcript coverage percentage."),
    require_coverage: bool = typer.Option(False, help="Fail if coverage is below threshold."),
) -> None:
    """Attach L2 subtitle or ASR evidence to a build spec."""
    spec = BuildSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
    try:
        transcript = parse_transcript_file(
            transcript_path,
            kind=kind,  # type: ignore[arg-type]
            language=language,
            audio_duration_sec=audio_duration_sec,
            model=model,
            coverage_threshold_pct=coverage_threshold_pct,
            require_coverage=require_coverage,
        )
    except (TranscriptCoverageError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc

    merge_transcript_evidence(spec, transcript, source_ref=str(transcript_path))
    output_path = out or spec_path
    write_json(output_path, spec.model_dump_json(indent=2))
    typer.echo(f"Wrote transcript-enriched spec: {output_path}")


@app.command()
def build(
    spec_path: Path = typer.Argument(..., help="Build spec JSON path."),
    out: Path = typer.Option(Path("artifacts/artifact-handoff.json"), help="Builder handoff output."),
) -> None:
    """Build an artifact or handoff manifest from a build spec."""
    spec = BuildSpec.model_validate_json(spec_path.read_text(encoding="utf-8"))
    if spec.artifact.artifact_type == "excel":
        workbook_path = out if out.suffix.lower() == ".xlsx" else out.with_suffix(".xlsx")
        build_excel_workbook(spec, workbook_path)
        typer.echo(f"Wrote Excel workbook: {workbook_path}")
        return

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
    if path.suffix.lower() == ".xlsx":
        report = verify_excel_workbook(path, spec_path=spec)
        write_json(out, report.model_dump_json(indent=2))
        if report.status != "passed":
            raise typer.Exit(2)
        typer.echo(f"Wrote verification report: {out}")
        return

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


@app.command(name="mcp-manifest")
def mcp_manifest() -> None:
    """Print MCP-style tool manifest for agent hosts."""
    typer.echo(json.dumps(tool_manifest(), indent=2))


@app.command(name="mcp-call")
def mcp_call(
    name: str = typer.Argument(..., help="MCP tool name."),
    arguments_json: str = typer.Option("{}", help="JSON object passed to the tool."),
) -> None:
    """Dispatch a MCP-style tool call locally."""
    try:
        arguments = json.loads(arguments_json)
    except json.JSONDecodeError as exc:
        typer.echo(f"Invalid --arguments-json: {exc}", err=True)
        raise typer.Exit(2) from exc
    if not isinstance(arguments, dict):
        typer.echo("--arguments-json must decode to an object", err=True)
        raise typer.Exit(2)

    result = dispatch_tool(name, arguments, capabilities=[MacMlxRuntimeAdapter().capability()])
    typer.echo(json.dumps(result, indent=2))
    if not result.get("ok"):
        raise typer.Exit(2)


@app.command(name="serve-http")
def serve_http(
    host: str = typer.Option("127.0.0.1", help="Host interface to bind."),
    port: int = typer.Option(8765, help="TCP port to bind."),
) -> None:
    """Run the lightweight HTTP adapter until interrupted."""
    server = make_server(host=host, port=port, capabilities=[MacMlxRuntimeAdapter().capability()])
    address, bound_port = server.server_address
    typer.echo(f"Serving video-to-artifact-agent HTTP adapter on http://{address}:{bound_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        typer.echo("Stopping HTTP adapter.")
    finally:
        server.server_close()


if __name__ == "__main__":
    app()
