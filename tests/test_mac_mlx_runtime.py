from pathlib import Path
import subprocess

from video_to_artifact_agent.privacy import redact_text, redact_url
from video_to_artifact_agent.runtimes.mac_mlx import (
    MacMlxRuntimeAdapter,
    MacMlxRuntimeConfig,
)
from video_to_artifact_agent.schemas import SourceInfo, SourceKind


def test_mac_mlx_capability_manifest() -> None:
    adapter = MacMlxRuntimeAdapter()
    capability = adapter.capability()

    assert capability.runtime == "mac-mlx"
    assert capability.engine == "mlx-vlm"
    assert capability.supports_video_url is True
    assert capability.supports_local_video is True
    assert capability.supports_stream_headers is True
    assert capability.supports_asr is False


def test_mac_mlx_builds_video_url_command_with_redaction() -> None:
    adapter = MacMlxRuntimeAdapter(MacMlxRuntimeConfig(model="mlx-test"))
    source = SourceInfo(
        kind=SourceKind.url,
        url="https://cdn.example.com/video.mp4?token=secret&expires=123",
    )

    command = adapter.build_command(source, "Summarize")
    redacted = adapter.redacted_command(source, "Summarize")

    assert "--video" in command
    assert "token=secret" in " ".join(command)
    assert "token=secret" not in " ".join(redacted)
    assert "https://cdn.example.com/video.mp4?<redacted>" in redacted
    assert "--max-width" not in command


def test_mac_mlx_builds_local_video_command() -> None:
    adapter = MacMlxRuntimeAdapter()
    source = SourceInfo(kind=SourceKind.local_file, local_path="/tmp/demo.mp4")

    command = adapter.build_command(source)

    assert "/tmp/demo.mp4" in command


def test_mac_mlx_auto_launcher_uses_configured_omlx_python(monkeypatch) -> None:
    monkeypatch.setenv("V2A_MAC_MLX_PYTHON", "/opt/omlx/bin/python3.11")
    monkeypatch.setenv("V2A_MAC_MLX_SITE_PACKAGES", "/opt/omlx/site-packages")
    adapter = MacMlxRuntimeAdapter(
        MacMlxRuntimeConfig(model="mlx-test", extra_site_packages=())
    )
    source = SourceInfo(kind=SourceKind.local_file, local_path="/tmp/demo.mp4")

    command = adapter.build_command(source)

    assert command[0] == "env"
    assert command[1].startswith("PYTHONPATH=")
    assert "/opt/omlx/site-packages" in command[1].removeprefix("PYTHONPATH=").split(
        ":"
    )
    assert command[2:4] == ["/opt/omlx/bin/python3.11", "-m"]
    assert command[4] == "mlx_vlm.generate"


def test_mac_mlx_auto_launcher_includes_extra_site_packages(monkeypatch) -> None:
    monkeypatch.setenv("V2A_MAC_MLX_PYTHON", "/opt/omlx/bin/python3.11")
    monkeypatch.setenv("V2A_MAC_MLX_SITE_PACKAGES", "/opt/omlx/site-packages")
    monkeypatch.setenv("V2A_MAC_MLX_EXTRA_SITE_PACKAGES", "/opt/cv2/site-packages")
    adapter = MacMlxRuntimeAdapter(MacMlxRuntimeConfig(model="mlx-test"))
    source = SourceInfo(kind=SourceKind.local_file, local_path="/tmp/demo.mp4")

    command = adapter.build_command(source)
    pythonpath = command[1].removeprefix("PYTHONPATH=").split(":")

    assert "/opt/omlx/site-packages" in pythonpath
    assert "/opt/cv2/site-packages" in pythonpath


def test_mac_mlx_explicit_executable_bypasses_auto_launcher(monkeypatch) -> None:
    monkeypatch.setenv("V2A_MAC_MLX_PYTHON", "/opt/omlx/bin/python3.11")
    adapter = MacMlxRuntimeAdapter(
        MacMlxRuntimeConfig(model="mlx-test", executable="mlx_vlm.generate")
    )
    source = SourceInfo(kind=SourceKind.local_file, local_path="/tmp/demo.mp4")

    command = adapter.build_command(source)

    assert command[0] == "mlx_vlm.generate"


def test_mac_mlx_diagnostics_reports_ready_configured_launcher(tmp_path: Path) -> None:
    python_bin = tmp_path / "python3.11"
    omlx_site = tmp_path / "omlx-site"
    cv2_site = tmp_path / "cv2-site"
    model_path = tmp_path / "MiniCPM-V-4.6-4bit"
    python_bin.write_text("#!/usr/bin/env python\n", encoding="utf-8")
    omlx_site.mkdir()
    cv2_site.mkdir()
    model_path.mkdir()

    adapter = MacMlxRuntimeAdapter(
        MacMlxRuntimeConfig(
            model=str(model_path),
            python_bin=str(python_bin),
            site_packages=str(omlx_site),
            extra_site_packages=(str(cv2_site),),
        )
    )

    diagnostics = adapter.diagnostics()

    assert diagnostics["status"] == "ready"
    assert diagnostics["model"]["exists"] is True
    assert diagnostics["launcher"]["python_exists"] is True
    assert str(omlx_site) in diagnostics["launcher"]["pythonpath"]
    assert str(cv2_site) in diagnostics["launcher"]["pythonpath"]


def test_mac_mlx_diagnostics_warns_on_explicit_launcher() -> None:
    adapter = MacMlxRuntimeAdapter(
        MacMlxRuntimeConfig(model="mlx-test", executable="mlx_vlm.generate")
    )

    diagnostics = adapter.diagnostics()

    assert diagnostics["status"] == "ready_with_warnings"
    assert (
        "Explicit executable bypasses the auto launcher" in diagnostics["warnings"][0]
    )


def test_redact_url_and_text() -> None:
    url = "https://example.com/path/video.mp4?auth=secret#frag"

    assert redact_url(url) == "https://example.com/path/video.mp4?<redacted>"
    assert "auth=secret" not in redact_text(f"fetch {url}")


def test_observe_uses_runner_and_returns_evidence() -> None:
    adapter = MacMlxRuntimeAdapter(MacMlxRuntimeConfig(model="mlx-test"))
    source = SourceInfo(
        kind=SourceKind.url, url="https://example.com/video.mp4?sig=secret"
    )

    def fake_runner(
        command: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        assert timeout == adapter.config.timeout_sec
        assert "--video" in command
        return subprocess.CompletedProcess(
            command, 0, stdout="Screen shows an Excel model.", stderr=""
        )

    result = adapter.observe(source, "Summarize", runner=fake_runner)

    assert result.observation.summary == "Screen shows an Excel model."
    assert result.evidence.level == "L3"
    assert result.evidence.source_ref == "https://example.com/video.mp4?<redacted>"
    assert "sig=secret" not in " ".join(result.redacted_command)


def test_observe_raises_on_runtime_failure() -> None:
    adapter = MacMlxRuntimeAdapter()
    source = SourceInfo(
        kind=SourceKind.local_file, local_path=str(Path("/tmp/missing.mp4"))
    )

    def fake_runner(
        command: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="model failed")

    try:
        adapter.observe(source, runner=fake_runner)
    except RuntimeError as exc:
        assert "exit 2" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
