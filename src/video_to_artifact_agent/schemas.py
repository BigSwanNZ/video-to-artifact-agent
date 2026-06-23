from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


EvidenceLevel = Literal["L0", "L1", "L2", "L3", "L2+L3"]


class RuntimeCapability(BaseModel):
    runtime: str
    model: str
    supports_video_url: bool = False
    supports_local_video: bool = False
    supports_image: bool = False
    supports_asr: bool = False
    max_num_frames: int | None = None
    privacy: Literal["local", "remote", "hybrid"] = "local"


class SourceInfo(BaseModel):
    url: str | None = None
    title: str | None = None
    duration_sec: float | None = None
    evidence_level: EvidenceLevel = "L0"


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class VideoObservation(BaseModel):
    summary: str
    evidence_level: EvidenceLevel = "L3"
    raw_model: str | None = None


class BuildSpec(BaseModel):
    source: SourceInfo
    observations: list[VideoObservation] = Field(default_factory=list)
    transcript_segments: list[TranscriptSegment] = Field(default_factory=list)
    artifact_type: str
    requirements: dict = Field(default_factory=dict)

