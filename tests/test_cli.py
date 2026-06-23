from pathlib import Path

from typer.testing import CliRunner

from video_to_artifact_agent.cli.main import app


runner = CliRunner()


def test_cli_analyze_build_verify_round_trip(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.json"
    artifact_path = tmp_path / "model.xlsx"
    report_path = tmp_path / "report.json"

    result = runner.invoke(
        app,
        [
            "analyze",
            "https://example.com/demo.mp4",
            "--artifact-type",
            "excel",
            "--title",
            "Demo model",
            "--runtime",
            "mac-mlx",
            "--model",
            "openbmb/MiniCPM-V-4.6",
            "--out",
            str(spec_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert spec_path.exists()
    assert '"artifact_type": "excel"' in spec_path.read_text()

    result = runner.invoke(app, ["build", str(spec_path), "--out", str(artifact_path)])
    assert result.exit_code == 0, result.output
    assert artifact_path.exists()

    result = runner.invoke(
        app,
        ["verify", str(artifact_path), "--spec", str(spec_path), "--out", str(report_path)],
    )
    assert result.exit_code == 0, result.output
    assert report_path.exists()
    assert '"status": "passed"' in report_path.read_text()


def test_cli_attach_transcript_enriches_spec(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.json"
    transcript_path = tmp_path / "demo.srt"
    transcript_path.write_text(
        """1
00:00:00,000 --> 00:00:05,000
Build revenue from units and price.
""",
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "analyze",
            "https://example.com/demo.mp4?signature=secret",
            "--artifact-type",
            "excel",
            "--out",
            str(spec_path),
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        app,
        [
            "attach-transcript",
            str(spec_path),
            str(transcript_path),
            "--audio-duration-sec",
            "5",
            "--require-coverage",
        ],
    )

    assert result.exit_code == 0, result.output
    spec_text = spec_path.read_text()
    assert '"transcript"' in spec_text
    assert '"achieved_evidence_level"' not in spec_text
    assert "signature=secret" not in spec_text


def test_cli_schema_command() -> None:
    result = runner.invoke(app, ["schema", "build-spec"])

    assert result.exit_code == 0, result.output
    assert "BuildSpec" in result.output or "artifact" in result.output


def test_cli_mac_mlx_capabilities() -> None:
    result = runner.invoke(app, ["mac-mlx-capabilities", "--model", "mlx-test"])

    assert result.exit_code == 0, result.output
    assert '"runtime": "mac-mlx"' in result.output
    assert '"engine": "mlx-vlm"' in result.output
    assert '"model": "mlx-test"' in result.output


def test_cli_mac_mlx_command_redacts_url_secrets() -> None:
    result = runner.invoke(
        app,
        [
            "mac-mlx-command",
            "https://cdn.example.com/demo.mp4?token=secret",
            "--prompt",
            "Summarize",
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"secret_material_omitted": true' in result.output
    assert "token=secret" not in result.output
    assert "https://cdn.example.com/demo.mp4?<redacted>" in result.output


def test_cli_mcp_manifest_and_call() -> None:
    result = runner.invoke(app, ["mcp-manifest"])

    assert result.exit_code == 0, result.output
    assert "video_to_artifact.analyze" in result.output

    result = runner.invoke(
        app,
        [
            "mcp-call",
            "video_to_artifact.analyze",
            "--arguments-json",
            '{"source":"https://example.com/demo.mp4?token=secret","artifact_type":"excel"}',
        ],
    )

    assert result.exit_code == 0, result.output
    assert '"ok": true' in result.output
    assert "token=secret" not in result.output


def test_cli_verify_missing_artifact_exits_2(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    result = runner.invoke(app, ["verify", str(tmp_path / "missing.json"), "--out", str(report_path)])

    assert result.exit_code == 2
    assert report_path.exists()
    assert '"status": "failed"' in report_path.read_text()
