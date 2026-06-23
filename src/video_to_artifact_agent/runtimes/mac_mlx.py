from __future__ import annotations

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


DEFAULT_MODEL = "mlx-community/MiniCPM-V-4.6-4bit"
UPSTREAM_MODEL = "openbmb/MiniCPM-V-4.6"
DEFAULT_PROMPT = (
    "Watch this video and describe the visible workflow, screen structure, "
    "important UI elements, and artifact requirements."
)


class CommandRunner(Protocol):
    def __call__(self, command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        ...


@dataclass(frozen=True)
class MacMlxRuntimeConfig:
    model: str = DEFAULT_MODEL
    executable: str = "mlx_vlm.generate"
    max_tokens: int = 512
    temperature: float = 0.0
    timeout_sec: int = 420
    max_num_frames: int = 128
    max_width: int | None = 1280


@dataclass(frozen=True)
class MacMlxObservationResult:
    command: list[str]
    redacted_command: list[str]
    observation: VideoObservation
    evidence: EvidenceRecord
    stderr: str = ""


def default_runner(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
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
                "ASR/subtitles are handled by separate evidence stages.",
            ],
        )

    def build_command(self, source: SourceInfo, prompt: str = DEFAULT_PROMPT) -> list[str]:
        video_input = self._source_to_video_arg(source)
        command = [
            self.config.executable,
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
        if self.config.max_width is not None:
            command.extend(["--max-width", str(self.config.max_width)])
        return command

    def redacted_command(self, source: SourceInfo, prompt: str = DEFAULT_PROMPT) -> list[str]:
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
            raise RuntimeError(f"mac-mlx runtime timed out after {self.config.timeout_sec}s") from exc
        stdout = redact_text(completed.stdout or "").strip()
        stderr = redact_text(completed.stderr or "").strip()
        if completed.returncode != 0:
            raise RuntimeError(f"mac-mlx runtime failed with exit {completed.returncode}: {stderr}")

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
