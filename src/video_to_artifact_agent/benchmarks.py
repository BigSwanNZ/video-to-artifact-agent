from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from video_to_artifact_agent.schemas import BuildSpec, VerificationReport


BenchmarkDomain = Literal["excel", "software", "web", "quant", "analytics", "generic"]


class BenchmarkCase(BaseModel):
    id: str
    title: str
    domain: BenchmarkDomain = "generic"
    source: str
    artifact_type: str
    expected_evidence_level: str = "L2+L3"
    acceptance: list[str] = Field(default_factory=list)
    notes: str | None = None


class BenchmarkManifest(BaseModel):
    version: int = 1
    name: str
    cases: list[BenchmarkCase] = Field(default_factory=list)


class BenchmarkResult(BaseModel):
    case_id: str
    status: Literal["passed", "failed", "blocked"]
    achieved_evidence_level: str | None = None
    report_status: str | None = None
    messages: list[str] = Field(default_factory=list)


def load_manifest(path: Path) -> BenchmarkManifest:
    return BenchmarkManifest.model_validate_json(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, manifest: BenchmarkManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(manifest.model_dump_json(indent=2) + "\n", encoding="utf-8")


def evaluate_case(
    case: BenchmarkCase,
    spec: BuildSpec,
    report: VerificationReport | None = None,
) -> BenchmarkResult:
    messages: list[str] = []
    status: Literal["passed", "failed", "blocked"] = "passed"
    if spec.artifact.artifact_type != case.artifact_type:
        status = "failed"
        messages.append(f"artifact_type expected {case.artifact_type}, got {spec.artifact.artifact_type}")
    if spec.achieved_evidence_level != case.expected_evidence_level:
        status = "failed"
        messages.append(
            f"evidence_level expected {case.expected_evidence_level}, got {spec.achieved_evidence_level}"
        )
    if report is not None and report.status != "passed":
        status = "failed" if report.status == "failed" else "blocked"
        messages.append(f"verification report status: {report.status}")
    return BenchmarkResult(
        case_id=case.id,
        status=status,
        achieved_evidence_level=spec.achieved_evidence_level,
        report_status=report.status if report else None,
        messages=messages,
    )


def results_to_json(results: list[BenchmarkResult]) -> str:
    return json.dumps([result.model_dump(mode="json") for result in results], indent=2)
