from __future__ import annotations

from urllib.parse import urlparse

from video_to_artifact_agent.privacy import redact_text, redact_url
from video_to_artifact_agent.schemas import (
    ArtifactRequirement,
    BuildSpec,
    EvidenceKind,
    EvidenceRecord,
    RuntimeCapability,
    SourceInfo,
    SourceKind,
    TranscriptEvidence,
    VideoObservation,
)


def source_info_from_input(source: str) -> SourceInfo:
    parsed = urlparse(source)
    if parsed.scheme in {"http", "https"}:
        return SourceInfo(kind=SourceKind.url, url=source, evidence_level="L0")
    if parsed.scheme == "synthetic":
        return SourceInfo(kind=SourceKind.synthetic, source_id=source, evidence_level="L0")
    return SourceInfo(kind=SourceKind.local_file, local_path=source, evidence_level="L0")


def redacted_source_info(source: SourceInfo) -> SourceInfo:
    if source.url:
        return source.model_copy(update={"url": redact_url(source.url)})
    return source


def create_initial_spec(
    source: str | SourceInfo,
    artifact_type: str = "unknown",
    title: str | None = None,
    instructions: str | None = None,
    runtime: RuntimeCapability | None = None,
) -> BuildSpec:
    source_info = redacted_source_info(source_info_from_input(source) if isinstance(source, str) else source)
    source_ref = (
        source
        if isinstance(source, str)
        else source.url or source.local_path or source.source_id or source.provider or source.kind.value
    )
    return BuildSpec(
        source=source_info,
        runtime=runtime,
        evidence=[
            EvidenceRecord(
                kind=EvidenceKind.metadata,
                level="L0",
                summary="Initial source registered; no video or ASR evidence has been collected yet.",
                source_ref=redact_text(source_ref),
            )
        ],
        artifact=ArtifactRequirement(
            artifact_type=artifact_type,  # type: ignore[arg-type]
            title=title,
            instructions=instructions,
        ),
        requirements={"workflow_stage": "analysis_requested"},
    )


def with_video_observation(
    spec: BuildSpec,
    observation: VideoObservation,
    evidence: EvidenceRecord | None = None,
) -> BuildSpec:
    records = list(spec.evidence)
    if evidence is not None:
        records.append(evidence)
    return spec.model_copy(
        update={
            "observations": [*spec.observations, observation],
            "evidence": records,
            "requirements": {**spec.requirements, "workflow_stage": "visual_observation_complete"},
        }
    )


def with_transcript(
    spec: BuildSpec,
    transcript: TranscriptEvidence,
    source_ref: str | None = None,
) -> BuildSpec:
    text_preview = " ".join(segment.text for segment in transcript.segments[:3]).strip()
    summary = text_preview or "Transcript evidence attached."
    records = [
        *spec.evidence,
        EvidenceRecord(
            kind=EvidenceKind(transcript.kind),
            level="L2",
            summary=summary,
            source_ref=redact_text(source_ref) if source_ref else None,
            metadata={
                "segment_count": len(transcript.segments),
                "coverage_pct": transcript.coverage_pct,
                "coverage_threshold_pct": transcript.coverage_threshold_pct,
                "passes_coverage_gate": transcript.passes_coverage_gate,
            },
        ),
    ]
    return spec.model_copy(
        update={
            "transcript": transcript,
            "evidence": records,
            "requirements": {**spec.requirements, "workflow_stage": "transcript_attached"},
        }
    )


def spec_summary(spec: BuildSpec) -> dict[str, object]:
    return {
        "artifact_type": spec.artifact.artifact_type,
        "title": spec.artifact.title,
        "achieved_evidence_level": spec.achieved_evidence_level,
        "evidence_count": len(spec.evidence),
        "observation_count": len(spec.observations),
        "transcript_segments": len(spec.transcript.segments) if spec.transcript else 0,
        "transcript_coverage_pct": spec.transcript.coverage_pct if spec.transcript else None,
    }
