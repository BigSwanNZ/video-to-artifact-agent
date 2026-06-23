from video_to_artifact_agent.benchmarks import BenchmarkCase, evaluate_case, results_to_json
from video_to_artifact_agent.schemas import (
    ArtifactRequirement,
    BuildSpec,
    SourceInfo,
    SourceKind,
    TranscriptEvidence,
    TranscriptSegment,
    VideoObservation,
    VerificationCheck,
    VerificationReport,
)


def test_benchmark_case_passes_for_l2_l3_verified_spec() -> None:
    case = BenchmarkCase(
        id="excel-demo",
        title="Excel demo",
        domain="excel",
        source="synthetic://excel-demo",
        artifact_type="excel",
    )
    spec = BuildSpec(
        source=SourceInfo(kind=SourceKind.synthetic),
        observations=[VideoObservation(summary="workbook UI")],
        transcript=TranscriptEvidence(
            kind="subtitle",
            segments=[TranscriptSegment(start=0, end=5, text="create the formulas")],
        ),
        artifact=ArtifactRequirement(artifact_type="excel"),
    )
    report = VerificationReport(
        artifact_path="artifact.xlsx",
        status="passed",
        checks=[VerificationCheck(name="exists", status="passed")],
    )

    result = evaluate_case(case, spec, report)

    assert result.status == "passed"
    assert "excel-demo" in results_to_json([result])
