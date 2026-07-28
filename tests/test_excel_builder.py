from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from zipfile import ZipFile

from video_to_artifact_agent.builders.excel import build_excel_workbook
from video_to_artifact_agent.schemas import (
    ArtifactRequirement,
    BuildSpec,
    EvidenceKind,
    EvidenceRecord,
    RuntimeCapability,
    SourceInfo,
    SourceKind,
    TranscriptEvidence,
    TranscriptSegment,
    VideoObservation,
)
from video_to_artifact_agent.verifiers.excel import verify_excel_workbook


def test_excel_builder_writes_real_workbook(tmp_path: Path) -> None:
    workbook_path = build_excel_workbook(_sample_spec(), tmp_path / "model.xlsx")

    assert workbook_path.exists()
    with ZipFile(workbook_path) as workbook:
        names = set(workbook.namelist())
        assert "[Content_Types].xml" in names
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        assert "xl/worksheets/sheet2.xml" in names
        assert "xl/worksheets/sheet3.xml" in names
        model_xml = workbook.read("xl/worksheets/sheet2.xml").decode("utf-8")

    assert "<f>B3*B4</f>" in model_xml
    assert "<f>B3*B5</f>" in model_xml
    assert "<f>B7-B8</f>" in model_xml
    assert "<f>B9/B7</f>" in model_xml


def test_excel_verifier_passes_generated_workbook(tmp_path: Path) -> None:
    workbook_path = build_excel_workbook(_sample_spec(), tmp_path / "model.xlsx")

    report = verify_excel_workbook(workbook_path)

    assert report.status == "passed"
    assert {check.name for check in report.checks} >= {
        "xlsx_package_parts",
        "workbook_sheets",
        "required_sheets",
        "model_formulas",
    }


def test_excel_verifier_fails_missing_sheet(tmp_path: Path) -> None:
    workbook_path = build_excel_workbook(_sample_spec(), tmp_path / "model.xlsx")
    broken_path = tmp_path / "missing-checks.xlsx"
    _rewrite_entry(
        workbook_path,
        broken_path,
        "xl/workbook.xml",
        lambda text: text.replace('<sheet name="Checks" sheetId="3" r:id="rId3"/>', ""),
    )

    report = verify_excel_workbook(broken_path)

    assert report.status == "failed"
    required_sheets = next(check for check in report.checks if check.name == "required_sheets")
    assert required_sheets.status == "failed"
    assert required_sheets.metadata["missing"] == ["Checks"]


def test_excel_verifier_fails_missing_formula(tmp_path: Path) -> None:
    workbook_path = build_excel_workbook(_sample_spec(), tmp_path / "model.xlsx")
    broken_path = tmp_path / "missing-formula.xlsx"
    _rewrite_entry(
        workbook_path,
        broken_path,
        "xl/worksheets/sheet2.xml",
        lambda text: text.replace("<f>B9/B7</f>", ""),
    )

    report = verify_excel_workbook(broken_path)

    assert report.status == "failed"
    formulas = next(check for check in report.checks if check.name == "model_formulas")
    assert formulas.status == "failed"
    assert formulas.metadata["missing"] == ["B9/B7"]


def _sample_spec() -> BuildSpec:
    return BuildSpec(
        source=SourceInfo(
            kind=SourceKind.url,
            url="https://example.com/demo.mp4",
            provider="example",
            title="Data center buildout walkthrough",
            duration_sec=120.0,
            evidence_level="L1",
        ),
        runtime=RuntimeCapability(
            runtime="mac-mlx",
            model="openbmb/MiniCPM-V-4.6",
            engine="mlx-vlm",
            supports_video_url=True,
            max_num_frames=128,
        ),
        observations=[
            VideoObservation(
                summary="Presenter shows a revenue and cost model for new GPU capacity.",
                time_start_sec=12.0,
                time_end_sec=55.0,
            )
        ],
        transcript=TranscriptEvidence(
            kind="asr",
            model="local-asr",
            audio_duration_sec=100,
            segments=[
                TranscriptSegment(start=0, end=25, text="Revenue equals units times price."),
                TranscriptSegment(start=25, end=95, text="Gross profit subtracts cost and margin divides by revenue."),
            ],
        ),
        evidence=[
            EvidenceRecord(
                kind=EvidenceKind.video_observation,
                level="L3",
                summary="Spreadsheet logic visible in the video.",
                source_ref="frame-window-1",
            )
        ],
        artifact=ArtifactRequirement(
            artifact_type="excel",
            title="Data center model",
            instructions="Create a verifiable financial model.",
        ),
    )


def _rewrite_entry(source: Path, destination: Path, entry_name: str, transform: Callable[[str], str]) -> None:
    with ZipFile(source) as source_zip, ZipFile(destination, "w") as destination_zip:
        for item in source_zip.infolist():
            content = source_zip.read(item.filename)
            if item.filename == entry_name:
                text = content.decode("utf-8")
                content = transform(text).encode("utf-8")
            destination_zip.writestr(item, content)
