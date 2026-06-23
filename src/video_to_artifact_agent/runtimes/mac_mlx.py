from __future__ import annotations

import os
from pathlib import Path
import shlex
import subprocess
from dataclasses import dataclass
from typing import Protocol

from video_to_artifact_agent.privacy import redact_text, redact_url
from video_to_artifact_agent.schemas import (
    EvidenceKind,
    EvidenceRecord,
    RuntimeCapability,
    SourceInfo,
    SourceKind,
    VideoObservation,
)


MODEL_REPO = "mlx-community/MiniCPM-V-4.6-4bit"
UPSTREAM_MODEL = "openbmb/MiniCPM-V-4.6"
DEFAULT_EXECUTABLE = "auto"
OMLX_PYTHON = Path(
    "/Applications/oMLX.app/Contents/Resources/Python/cpython-3.11/bin/python3.11"
)
OMLX_SITE_PACKAGES = Path(
    "/Applications/oMLX.app/Contents/Resources/Python/framework-mlx-base/lib/python3.11/site-packages"
)
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_OMLX_VENV_SITE_PACKAGES = (
    REPO_ROOT.parent / ".venvs/omlx-vlm/lib/python3.11/site-packages"
)
LOCAL_OMLX_MODEL = Path.home() / ".omlx/models/mlx-community/MiniCPM-V-4.6-4bit"
DEFAULT_PROMPT = (
    "Watch this video and describe the visible workflow, screen structure, "
    "important UI elements, and artifact requirements."
)


def default_model() -> str:
    override = os.environ.get("V2A_MAC_MLX_MODEL")
    if override:
        return override
    if LOCAL_OMLX_MODEL.exists():
        return str(LOCAL_OMLX_MODEL)
    return MODEL_REPO


DEFAULT_MODEL = default_model()


class CommandRunner(Protocol):
    def __call__(
        self, command: list[str], timeout: int
    ) -> subprocess.CompletedProcess[str]: ...


@dataclass(frozen=True)
class MacMlxRuntimeConfig:
    model: str = DEFAULT_MODEL
    executable: str = DEFAULT_EXECUTABLE
    python_bin: str | None = None
    site_packages: str | None = None
    extra_site_packages: tuple[str, ...] | None = None
    max_tokens: int = 512
    temperature: float = 0.0
    timeout_sec: int = 420
    max_num_frames: int = 128
    max_width: int | None = None


@dataclass(frozen=True)
class MacMlxObservationResult:
    command: list[str]
    redacted_command: list[str]
    observation: VideoObservation
    evidence: EvidenceRecord
    stderr: str = ""


def default_runner(
    command: list[str], timeout: int
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        timeout=timeout,
    )


class MacMlxRuntimeAdapter:
    """Apple Silicon MLX adapter for MiniCPM-V video observation.

    This adapter wraps `mlx_vlm.generate --video` without making the workflow
    depend on Codex. It accepts local video paths and direct URLs when the MLX
    backend can stream them. Source URL resolution, cookies, and ASR remain
    separate stages.
    """

    runtime_name = "mac-mlx"

    def __init__(self, config: MacMlxRuntimeConfig | None = None) -> None:
        self.config = config or MacMlxRuntimeConfig()

    def capability(self) -> RuntimeCapability:
        return RuntimeCapability(
            runtime=self.runtime_name,
            model=self.config.model,
            engine="mlx-vlm",
            supports_video_url=True,
            supports_local_video=True,
            supports_image=True,
            supports_asr=False,
            supports_subtitles=False,
            supports_stream_headers=True,
            max_num_frames=self.config.max_num_frames,
            privacy="local",
            notes=[
                f"Upstream model family: {UPSTREAM_MODEL}",
                "Uses mlx_vlm.generate --video for video observation.",
                "Default auto launcher prefers the oMLX bundled Python runtime on Apple Silicon.",
                "ASR/subtitles are handled by separate evidence stages.",
            ],
        )

    def build_command(
        self, source: SourceInfo, prompt: str = DEFAULT_PROMPT
    ) -> list[str]:
        video_input = self._source_to_video_arg(source)
        command = [
            *self._launcher_command(),
            "--model",
            self.config.model,
            "--video",
            video_input,
            "--prompt",
            prompt,
            "--max-tokens",
            str(self.config.max_tokens),
            "--temperature",
            str(self.config.temperature),
        ]
        return command

    def diagnostics(self) -> dict[str, object]:
        launcher = self._launcher_command()
        python_bin = self._launcher_python_bin(launcher)
        pythonpath = self._launcher_pythonpath(launcher)
        issues: list[str] = []
        warnings: list[str] = []

        if self.config.executable != "auto":
            warnings.append(
                "Explicit executable bypasses the auto launcher; verify it is not an old global mlx-vlm."
            )
        if python_bin is None:
            warnings.append(
                "Launcher does not expose a Python interpreter; PATH must contain a compatible mlx_vlm.generate."
            )
        elif "/" in python_bin and not Path(python_bin).exists():
            issues.append(f"Python executable does not exist: {python_bin}")

        model_path = Path(self.config.model).expanduser()
        model_is_path = "/" in self.config.model or self.config.model.startswith(".")
        if model_is_path and not model_path.exists():
            issues.append(f"Model path does not exist: {self.config.model}")

        if not pythonpath and self.config.executable == "auto":
            warnings.append(
                "Auto launcher did not resolve PYTHONPATH; mlx-vlm and cv2 must be importable by the selected Python."
            )

        site_packages = [
            {"path": path, "exists": Path(path).expanduser().exists()}
            for path in pythonpath
        ]
        if (
            self.config.executable == "auto"
            and site_packages
            and not any(item["exists"] for item in site_packages)
        ):
            issues.append("No resolved PYTHONPATH entries exist on this machine.")

        status = "blocked" if issues else "ready_with_warnings" if warnings else "ready"
        return {
            "status": status,
            "runtime": self.capability().model_dump(mode="json"),
            "launcher": {
                "mode": self.config.executable,
                "command_prefix": [redact_text(part) for part in launcher],
                "python_bin": python_bin,
                "python_exists": Path(python_bin).exists()
                if python_bin and "/" in python_bin
                else None,
                "pythonpath": pythonpath,
                "site_packages": site_packages,
            },
            "model": {
                "value": self.config.model,
                "kind": "local_path" if model_is_path else "model_id",
                "exists": model_path.exists() if model_is_path else None,
            },
            "issues": issues,
            "warnings": warnings,
        }

    def _launcher_command(self) -> list[str]:
        if self.config.executable != "auto":
            return shlex.split(self.config.executable)

        python_bin = self.config.python_bin or os.environ.get("V2A_MAC_MLX_PYTHON")
        site_packages = self.config.site_packages or os.environ.get(
            "V2A_MAC_MLX_SITE_PACKAGES"
        )

        if python_bin is None and OMLX_PYTHON.exists():
            python_bin = str(OMLX_PYTHON)
        if site_packages is None and OMLX_SITE_PACKAGES.exists():
            site_packages = str(OMLX_SITE_PACKAGES)

        if python_bin:
            command = [python_bin, "-m", "mlx_vlm.generate"]
            pythonpath = self._pythonpath(site_packages)
            if pythonpath:
                return ["env", f"PYTHONPATH={pythonpath}", *command]
            return command

        return ["mlx_vlm.generate"]

    def _pythonpath(self, primary_site_packages: str | None) -> str | None:
        paths: list[str] = []
        if primary_site_packages:
            paths.append(primary_site_packages)

        if self.config.extra_site_packages is None:
            env_extra = os.environ.get("V2A_MAC_MLX_EXTRA_SITE_PACKAGES")
            if env_extra:
                paths.extend(path for path in env_extra.split(os.pathsep) if path)
            if WORKSPACE_OMLX_VENV_SITE_PACKAGES.exists():
                paths.append(str(WORKSPACE_OMLX_VENV_SITE_PACKAGES))
        else:
            paths.extend(self.config.extra_site_packages)

        existing_pythonpath = os.environ.get("PYTHONPATH")
        if existing_pythonpath:
            paths.extend(path for path in existing_pythonpath.split(os.pathsep) if path)

        deduped = list(dict.fromkeys(paths))
        if not deduped:
            return None
        return os.pathsep.join(deduped)

    def _launcher_python_bin(self, launcher: list[str]) -> str | None:
        if launcher and launcher[0] == "env":
            for index, part in enumerate(launcher):
                if part == "-m" and index > 0:
                    return launcher[index - 1]
            return None
        if "-m" in launcher:
            return launcher[0]
        return None

    def _launcher_pythonpath(self, launcher: list[str]) -> list[str]:
        for part in launcher:
            if part.startswith("PYTHONPATH="):
                return [
                    path
                    for path in part.removeprefix("PYTHONPATH=").split(os.pathsep)
                    if path
                ]
        return []

    def redacted_command(
        self, source: SourceInfo, prompt: str = DEFAULT_PROMPT
    ) -> list[str]:
        return [redact_text(part) for part in self.build_command(source, prompt)]

    def observe(
        self,
        source: SourceInfo,
        prompt: str = DEFAULT_PROMPT,
        runner: CommandRunner = default_runner,
    ) -> MacMlxObservationResult:
        command = self.build_command(source, prompt)
        try:
            completed = runner(command, self.config.timeout_sec)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"mac-mlx runtime timed out after {self.config.timeout_sec}s"
            ) from exc
        stdout = redact_text(completed.stdout or "").strip()
        stderr = redact_text(completed.stderr or "").strip()
        if completed.returncode != 0:
            raise RuntimeError(
                f"mac-mlx runtime failed with exit {completed.returncode}: {stderr}"
            )

        summary = stdout or "No visible output captured from mac-mlx runtime."
        observation = VideoObservation(
            summary=summary,
            evidence_level="L3",
            raw_model=self.config.model,
        )
        evidence = EvidenceRecord(
            kind=EvidenceKind.video_observation,
            level="L3",
            summary=summary,
            source_ref=self._redacted_source_ref(source),
            metadata={
                "runtime": self.runtime_name,
                "engine": "mlx-vlm",
                "model": self.config.model,
                "command": [redact_text(part) for part in command],
            },
        )
        return MacMlxObservationResult(
            command=command,
            redacted_command=[redact_text(part) for part in command],
            observation=observation,
            evidence=evidence,
            stderr=stderr,
        )

    def _source_to_video_arg(self, source: SourceInfo) -> str:
        if source.kind == SourceKind.url and source.url:
            return source.url
        if source.kind == SourceKind.local_file and source.local_path:
            return source.local_path
        raise ValueError("mac-mlx runtime requires a URL or local video source")

    def _redacted_source_ref(self, source: SourceInfo) -> str | None:
        if source.url:
            return redact_url(source.url)
        return source.local_path
