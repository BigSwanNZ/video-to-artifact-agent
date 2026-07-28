from video_to_artifact_agent.schemas import TranscriptEvidence, TranscriptSegment, VideoObservation
from video_to_artifact_agent.workflow import (
    create_initial_spec,
    source_info_from_input,
    spec_summary,
    with_transcript,
    with_video_observation,
)


def test_workflow_recognizes_synthetic_sources() -> None:
    source = source_info_from_input("synthetic://excel-demo")

    assert source.kind == "synthetic"
    assert source.source_id == "synthetic://excel-demo"


def test_workflow_merges_l2_and_l3_evidence() -> None:
    spec = create_initial_spec(
        "https://example.com/demo.mp4?signature=secret",
        artifact_type="excel",
        title="Demo model",
    )
    spec = with_video_observation(spec, VideoObservation(summary="screen shows a workbook"))
    spec = with_transcript(
        spec,
        TranscriptEvidence(
            kind="asr",
            audio_duration_sec=10,
            segments=[TranscriptSegment(start=0, end=10, text="build revenue and margin tabs")],
        ),
        source_ref="https://example.com/demo.vtt?signature=secret",
    )

    assert spec.achieved_evidence_level == "L2+L3"
    assert "signature=secret" not in (spec.evidence[0].source_ref or "")
    assert spec.evidence[-1].metadata["passes_coverage_gate"] is True
    assert spec_summary(spec)["transcript_segments"] == 1
