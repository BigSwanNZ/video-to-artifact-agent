from pathlib import Path

from typer.testing import CliRunner

from video_to_artifact_agent.cli.main import app


runner = CliRunner()


def test_cli_analyze_build_verify_round_trip(tmp_path: Path) -> None:
    spec_path = tmp_path / "spec.json"
    handoff_path = tmp_path / "handoff.json"
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

    result = runner.invoke(app, ["build", str(spec_path), "--out", str(handoff_path)])
    assert result.exit_code == 0, result.output
    assert handoff_path.exists()

    result = runner.invoke(
        app,
        ["verify", str(handoff_path), "--spec", str(spec_path), "--out", str(report_path)],
    )
    assert result.exit_code == 0, result.output
    assert report_path.exists()
    assert '"status": "passed"' in report_path.read_text()


def test_cli_schema_command() -> None:
    result = runner.invoke(app, ["schema", "build-spec"])

    assert result.exit_code == 0, result.output
    assert "BuildSpec" in result.output or "artifact" in result.output


def test_cli_verify_missing_artifact_exits_2(tmp_path: Path) -> None:
    report_path = tmp_path / "report.json"
    result = runner.invoke(app, ["verify", str(tmp_path / "missing.json"), "--out", str(report_path)])

    assert result.exit_code == 2
    assert report_path.exists()
    assert '"status": "failed"' in report_path.read_text()
