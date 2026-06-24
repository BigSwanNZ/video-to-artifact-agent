from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


EvidenceLevel = Literal["L0", "L1", "L2", "L3", "L2+L3"]
PrivacyMode = Literal["local", "remote", "hybrid"]
ArtifactType = Literal["excel", "web", "code", "doc", "comfyui_workflow", "generic", "unknown"]
VerificationStatus = Literal["passed", "failed", "blocked", "not_run"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SourceKind(str, Enum):
    url = "url"
    local_file = "local_file"
    synthetic = "synthetic"
    unknown = "unknown"


class EvidenceKind(str, Enum):
    metadata = "metadata"
    page_context = "page_context"
    subtitle = "subtitle"
    asr = "asr"
    video_observation = "video_observation"
    ocr = "ocr"
    user_input = "user_input"
    verification = "verification"


class RuntimeCapability(BaseModel):
    runtime: str
    model: str
    engine: str | None = None
    supports_video_url: bool = False
    supports_local_video: bool = False
    supports_image: bool = False
    supports_asr: bool = False
    supports_subtitles: bool = False
    supports_stream_headers: bool = False
    max_num_frames: int | None = None
    max_inline_bytes: int | None = None
    downsample_modes: list[str] = Field(default_factory=list)
    privacy: PrivacyMode = "local"
    notes: list[str] = Field(default_factory=list)


class SourceInfo(BaseModel):
    kind: SourceKind = SourceKind.unknown
    url: str | None = None
    local_path: str | None = None
    provider: str | None = None
    source_id: str | None = None
    title: str | None = None
    duration_sec: float | None = None
    evidence_level: EvidenceLevel = "L0"

    @model_validator(mode="after")
    def require_location_for_concrete_source(self) -> "SourceInfo":
        if self.kind == SourceKind.url and not self.url:
            raise ValueError("url source requires url")
        if self.kind == SourceKind.local_file and not self.local_path:
            raise ValueError("local_file source requires local_path")
        return self


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str

    @field_validator("end")
    @classmethod
    def end_must_be_non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("end must be non-negative")
        return value

    @model_validator(mode="after")
    def end_must_follow_start(self) -> "TranscriptSegment":
        if self.start < 0:
            raise ValueError("start must be non-negative")
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self


class TranscriptEvidence(BaseModel):
    kind: Literal["subtitle", "asr"]
    model: str | None = None
    language: str | None = None
    segments: list[TranscriptSegment] = Field(default_factory=list)
    audio_duration_sec: float | None = None
    last_segment_end_sec: float | None = None
    coverage_pct: float | None = None
    coverage_threshold_pct: float = 95.0

    @model_validator(mode="after")
    def derive_coverage(self) -> "TranscriptEvidence":
        if self.last_segment_end_sec is None and self.segments:
            self.last_segment_end_sec = max(segment.end for segment in self.segments)
        if (
            self.coverage_pct is None
            and self.audio_duration_sec
            and self.audio_duration_sec > 0
            and self.last_segment_end_sec is not None
        ):
            self.coverage_pct = round(self.last_segment_end_sec / self.audio_duration_sec * 100, 2)
        return self

    @property
    def passes_coverage_gate(self) -> bool:
        return self.coverage_pct is not None and self.coverage_pct >= self.coverage_threshold_pct


class VideoObservation(BaseModel):
    summary: str
    evidence_level: EvidenceLevel = "L3"
    time_start_sec: float | None = None
    time_end_sec: float | None = None
    raw_model: str | None = None
    confidence: float | None = None


class EvidenceRecord(BaseModel):
    kind: EvidenceKind
    level: EvidenceLevel
    summary: str
    source_ref: str | None = None
    time_start_sec: float | None = None
    time_end_sec: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRequirement(BaseModel):
    artifact_type: ArtifactType
    title: str | None = None
    instructions: str | None = None
    acceptance: list[str] = Field(default_factory=list)
    builder: str | None = None


class BuildSpec(BaseModel):
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    source: SourceInfo
    runtime: RuntimeCapability | None = None
    observations: list[VideoObservation] = Field(default_factory=list)
    transcript: TranscriptEvidence | None = None
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    artifact: ArtifactRequirement
    requirements: dict[str, Any] = Field(default_factory=dict)

    @property
    def achieved_evidence_level(self) -> EvidenceLevel:
        levels = {record.level for record in self.evidence}
        if self.transcript and self.transcript.segments:
            levels.add("L2")
        if self.observations:
            levels.add("L3")
        if "L2" in levels and "L3" in levels:
            return "L2+L3"
        if "L3" in levels:
            return "L3"
        if "L2" in levels:
            return "L2"
        if "L1" in levels:
            return "L1"
        return self.source.evidence_level


class VerificationCheck(BaseModel):
    name: str
    status: VerificationStatus
    message: str | None = None
    observed: Any | None = None
    expected: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerificationReport(BaseModel):
    version: int = 1
    created_at: datetime = Field(default_factory=utc_now)
    artifact_path: str
    spec_path: str | None = None
    status: VerificationStatus
    checks: list[VerificationCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def status_matches_checks(self) -> "VerificationReport":
        if self.status == "not_run" and self.checks:
            raise ValueError("not_run report cannot include checks")
        if self.checks and any(check.status == "failed" for check in self.checks):
            self.status = "failed"
        elif self.checks and any(check.status == "blocked" for check in self.checks):
            self.status = "blocked"
        elif self.checks:
            self.status = "passed"
        return self


class WorkflowExitCode(BaseModel):
    code: int
    name: str
    meaning: str


CLI_EXIT_CODES = [
    WorkflowExitCode(code=0, name="success", meaning="Command completed successfully."),
    WorkflowExitCode(code=2, name="verification_failed", meaning="Artifact or evidence verification failed."),
    WorkflowExitCode(code=3, name="blocked", meaning="Input, access, or runtime limitation blocked progress."),
    WorkflowExitCode(code=4, name="unsafe_input", meaning="Input violated privacy or safety rules."),
]
