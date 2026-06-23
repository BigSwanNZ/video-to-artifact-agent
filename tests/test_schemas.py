from video_to_artifact_agent.schemas import (
    ArtifactRequirement,
    BuildSpec,
    RuntimeCapability,
    SourceInfo,
    SourceKind,
    TranscriptEvidence,
    TranscriptSegment,
    VideoObservation,
    VerificationCheck,
    VerificationReport,
)


def test_runtime_capability_manifest() -> None:
    capability = RuntimeCapability(
        runtime="mac-mlx",
        model="openbmb/MiniCPM-V-4.6",
        supports_video_url=True,
        supports_local_video=True,
        supports_image=True,
        max_num_frames=128,
    )

    assert capability.supports_video_url is True
    assert capability.privacy == "local"


def test_transcript_evidence_derives_coverage() -> None:
    transcript = TranscriptEvidence(
        kind="asr",
        audio_duration_sec=100,
        segments=[
            TranscriptSegment(start=0, end=20, text="intro"),
            TranscriptSegment(start=20, end=98, text="body"),
        ],
    )

    assert transcript.last_segment_end_sec == 98
    assert transcript.coverage_pct == 98.0
    assert transcript.passes_coverage_gate is True


def test_build_spec_reports_combined_evidence_level() -> None:
    spec = BuildSpec(
        source=SourceInfo(kind=SourceKind.url, url="https://example.com/video"),
        observations=[VideoObservation(summary="screen shows spreadsheet")],
        transcript=TranscriptEvidence(
            kind="asr",
            audio_duration_sec=10,
            segments=[TranscriptSegment(start=0, end=10, text="build a model")],
        ),
        artifact=ArtifactRequirement(artifact_type="excel", title="Demo model"),
    )

    assert spec.achieved_evidence_level == "L2+L3"


def test_verification_report_status_follows_checks() -> None:
    report = VerificationReport(
        artifact_path="artifact.xlsx",
        status="passed",
        checks=[
            VerificationCheck(name="exists", status="passed"),
            VerificationCheck(name="formula_errors", status="failed"),
        ],
    )

    assert report.status == "failed"
