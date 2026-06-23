from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from video_to_artifact_agent.schemas import VerificationCheck, VerificationReport


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
REQUIRED_SHEETS = ("Inputs", "Model", "Checks")
REQUIRED_MODEL_FORMULAS = ("B3*B4", "B3*B5", "B7-B8", "B9/B7")


def verify_excel_workbook(
    artifact_path: str | Path,
    *,
    spec_path: str | Path | None = None,
    required_sheets: tuple[str, ...] = REQUIRED_SHEETS,
    required_model_formulas: tuple[str, ...] = REQUIRED_MODEL_FORMULAS,
) -> VerificationReport:
    """Verify basic .xlsx workbook integrity and expected financial formulas."""
    path = Path(artifact_path)
    checks: list[VerificationCheck] = []

    if not path.exists():
        return VerificationReport(
            artifact_path=str(path),
            spec_path=str(spec_path) if spec_path else None,
            status="failed",
            checks=[
                VerificationCheck(
                    name="artifact_exists",
                    status="failed",
                    message="Workbook path does not exist.",
                    expected=True,
                    observed=False,
                )
            ],
        )

    checks.append(VerificationCheck(name="artifact_exists", status="passed", observed=str(path)))

    try:
        with ZipFile(path) as workbook:
            names = set(workbook.namelist())
            package_checks = _package_checks(names)
            checks.extend(package_checks)
            if any(check.status == "failed" for check in package_checks):
                return VerificationReport(
                    artifact_path=str(path),
                    spec_path=str(spec_path) if spec_path else None,
                    status="failed",
                    checks=checks,
                )
            sheet_map = _read_sheet_map(workbook, checks)
            checks.extend(_required_sheet_checks(sheet_map, required_sheets))
            checks.extend(_worksheet_xml_checks(workbook, sheet_map))
            checks.extend(_formula_checks(workbook, sheet_map, required_model_formulas))
    except BadZipFile as exc:
        checks.append(
            VerificationCheck(
                name="xlsx_zip",
                status="failed",
                message=f"Artifact is not a readable zip-based .xlsx: {exc}",
            )
        )
    except KeyError as exc:
        checks.append(
            VerificationCheck(
                name="xlsx_package_read",
                status="failed",
                message=f"Required workbook package entry could not be read: {exc}",
            )
        )
    except ET.ParseError as exc:
        checks.append(
            VerificationCheck(
                name="workbook_xml_parse",
                status="failed",
                message=f"Workbook XML is not well formed: {exc}",
            )
        )

    return VerificationReport(
        artifact_path=str(path),
        spec_path=str(spec_path) if spec_path else None,
        status="passed",
        checks=checks,
    )


def _package_checks(names: set[str]) -> list[VerificationCheck]:
    required_parts = (
        "[Content_Types].xml",
        "_rels/.rels",
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
    )
    missing = [part for part in required_parts if part not in names]
    if missing:
        return [
            VerificationCheck(
                name="xlsx_package_parts",
                status="failed",
                message="Required OpenXML package parts are missing.",
                expected=list(required_parts),
                observed=sorted(names),
                metadata={"missing": missing},
            )
        ]
    return [
        VerificationCheck(
            name="xlsx_package_parts",
            status="passed",
            expected=list(required_parts),
            observed=list(required_parts),
        )
    ]


def _read_sheet_map(workbook: ZipFile, checks: list[VerificationCheck]) -> dict[str, str]:
    workbook_xml = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_xml = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {
        rel.attrib["Id"]: _normalize_workbook_target(rel.attrib["Target"])
        for rel in rels_xml.findall(f"{{{PKG_REL_NS}}}Relationship")
        if "Id" in rel.attrib and "Target" in rel.attrib
    }

    sheets: dict[str, str] = {}
    for sheet in workbook_xml.findall(f".//{{{MAIN_NS}}}sheet"):
        name = sheet.attrib.get("name")
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        if name and rel_id and rel_id in rel_targets:
            sheets[name] = rel_targets[rel_id]

    status = "passed" if sheets else "failed"
    checks.append(
        VerificationCheck(
            name="workbook_sheets",
            status=status,
            message=None if sheets else "No worksheets were declared in xl/workbook.xml.",
            observed=sorted(sheets),
        )
    )
    return sheets


def _normalize_workbook_target(target: str) -> str:
    return target if target.startswith("xl/") else f"xl/{target}"


def _required_sheet_checks(sheet_map: dict[str, str], required_sheets: tuple[str, ...]) -> list[VerificationCheck]:
    missing = [sheet for sheet in required_sheets if sheet not in sheet_map]
    if missing:
        return [
            VerificationCheck(
                name="required_sheets",
                status="failed",
                message="Workbook is missing required sheets.",
                expected=list(required_sheets),
                observed=sorted(sheet_map),
                metadata={"missing": missing},
            )
        ]
    return [
        VerificationCheck(
            name="required_sheets",
            status="passed",
            expected=list(required_sheets),
            observed=sorted(sheet_map),
        )
    ]


def _worksheet_xml_checks(workbook: ZipFile, sheet_map: dict[str, str]) -> list[VerificationCheck]:
    names = set(workbook.namelist())
    missing = [target for target in sheet_map.values() if target not in names]
    checks: list[VerificationCheck] = []
    if missing:
        checks.append(
            VerificationCheck(
                name="worksheet_xml_parts",
                status="failed",
                message="A declared worksheet XML part is missing.",
                observed=sorted(names),
                metadata={"missing": missing},
            )
        )
        return checks

    for sheet_name, target in sheet_map.items():
        try:
            ET.fromstring(workbook.read(target))
        except ET.ParseError as exc:
            checks.append(
                VerificationCheck(
                    name=f"worksheet_xml:{sheet_name}",
                    status="failed",
                    message=f"Worksheet XML is not well formed: {exc}",
                    observed=target,
                )
            )
        else:
            checks.append(
                VerificationCheck(
                    name=f"worksheet_xml:{sheet_name}",
                    status="passed",
                    observed=target,
                )
            )
    return checks


def _formula_checks(
    workbook: ZipFile,
    sheet_map: dict[str, str],
    required_model_formulas: tuple[str, ...],
) -> list[VerificationCheck]:
    model_target = sheet_map.get("Model")
    if not model_target:
        return [
            VerificationCheck(
                name="model_formulas",
                status="failed",
                message="Model sheet is required before formulas can be checked.",
                expected=list(required_model_formulas),
                observed=[],
            )
        ]
    if model_target not in workbook.namelist():
        return [
            VerificationCheck(
                name="model_formulas",
                status="failed",
                message="Model worksheet XML part is missing.",
                expected=list(required_model_formulas),
                observed=[],
            )
        ]

    worksheet = ET.fromstring(workbook.read(model_target))
    formulas = [
        formula.text or ""
        for formula in worksheet.findall(f".//{{{MAIN_NS}}}f")
    ]
    missing = [formula for formula in required_model_formulas if formula not in formulas]
    if missing:
        return [
            VerificationCheck(
                name="model_formulas",
                status="failed",
                message="Model sheet is missing required formulas.",
                expected=list(required_model_formulas),
                observed=formulas,
                metadata={"missing": missing},
            )
        ]
    return [
        VerificationCheck(
            name="model_formulas",
            status="passed",
            expected=list(required_model_formulas),
            observed=formulas,
        )
    ]
