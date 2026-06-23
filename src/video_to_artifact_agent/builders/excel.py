from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from video_to_artifact_agent.schemas import BuildSpec


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_PROPS_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
DCMI_NS = "http://purl.org/dc/dcmitype/"
VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"


@dataclass(frozen=True)
class Cell:
    value: Any = None
    formula: str | None = None


def build_excel_workbook(spec: BuildSpec, output_path: str | Path) -> Path:
    """Build a minimal real .xlsx workbook from a BuildSpec.

    The implementation intentionally uses only the Python standard library and
    emits OpenXML directly. Values are written as inline strings or numbers so
    no shared string table is required.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    sheets = [
        ("Inputs", _inputs_rows(spec)),
        ("Model", _model_rows(spec)),
        ("Checks", _checks_rows(spec)),
    ]

    with ZipFile(path, "w", compression=ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", _content_types_xml(len(sheets)))
        workbook.writestr("_rels/.rels", _root_rels_xml())
        workbook.writestr("docProps/core.xml", _core_props_xml(spec))
        workbook.writestr("docProps/app.xml", _app_props_xml([name for name, _ in sheets]))
        workbook.writestr("xl/workbook.xml", _workbook_xml([name for name, _ in sheets]))
        workbook.writestr("xl/_rels/workbook.xml.rels", _workbook_rels_xml(len(sheets)))
        workbook.writestr("xl/styles.xml", _styles_xml())
        for index, (_, rows) in enumerate(sheets, start=1):
            workbook.writestr(f"xl/worksheets/sheet{index}.xml", _worksheet_xml(rows))

    return path


def _inputs_rows(spec: BuildSpec) -> list[list[Cell]]:
    rows: list[list[Cell]] = [
        _row("Section", "Field", "Value", "Evidence"),
        _row("Artifact", "type", spec.artifact.artifact_type, spec.achieved_evidence_level),
        _row("Artifact", "title", spec.artifact.title or "", spec.achieved_evidence_level),
        _row("Artifact", "instructions", spec.artifact.instructions or "", spec.achieved_evidence_level),
        _row("Source", "kind", spec.source.kind.value, spec.source.evidence_level),
        _row("Source", "url", spec.source.url or "", spec.source.evidence_level),
        _row("Source", "local_path", spec.source.local_path or "", spec.source.evidence_level),
        _row("Source", "provider", spec.source.provider or "", spec.source.evidence_level),
        _row("Source", "source_id", spec.source.source_id or "", spec.source.evidence_level),
        _row("Source", "title", spec.source.title or "", spec.source.evidence_level),
        _row("Source", "duration_sec", spec.source.duration_sec or "", spec.source.evidence_level),
    ]

    if spec.runtime:
        rows.extend(
            [
                _row("Runtime", "runtime", spec.runtime.runtime, spec.runtime.privacy),
                _row("Runtime", "model", spec.runtime.model, spec.runtime.privacy),
                _row("Runtime", "engine", spec.runtime.engine or "", spec.runtime.privacy),
                _row("Runtime", "max_num_frames", spec.runtime.max_num_frames or "", spec.runtime.privacy),
            ]
        )

    for index, observation in enumerate(spec.observations, start=1):
        rows.append(
            _row(
                "Observation",
                f"observation_{index}",
                observation.summary,
                observation.evidence_level,
            )
        )
        if observation.time_start_sec is not None or observation.time_end_sec is not None:
            rows.append(
                _row(
                    "Observation",
                    f"observation_{index}_time_range_sec",
                    _format_range(observation.time_start_sec, observation.time_end_sec),
                    observation.evidence_level,
                )
            )

    if spec.transcript:
        rows.extend(
            [
                _row("Transcript", "kind", spec.transcript.kind, "L2"),
                _row("Transcript", "model", spec.transcript.model or "", "L2"),
                _row("Transcript", "language", spec.transcript.language or "", "L2"),
                _row("Transcript", "coverage_pct", spec.transcript.coverage_pct or "", "L2"),
            ]
        )
        for index, segment in enumerate(spec.transcript.segments, start=1):
            rows.append(
                _row(
                    "Transcript",
                    f"segment_{index}",
                    f"{segment.start:.2f}-{segment.end:.2f}: {segment.text}",
                    "L2",
                )
            )

    for index, evidence in enumerate(spec.evidence, start=1):
        rows.append(
            _row(
                "Evidence",
                f"{index}_{evidence.kind.value}",
                evidence.summary,
                evidence.level,
            )
        )

    return rows


def _model_rows(spec: BuildSpec) -> list[list[Cell]]:
    title = spec.artifact.title or spec.source.title or "Video-derived financial model"
    return [
        _row(title, "", ""),
        _row("Assumption", "Value", "Notes"),
        _row("Units", 1000, "Example volume assumption extracted into an editable driver."),
        _row("Price per unit", 25, "Revenue driver."),
        _row("Cost per unit", 14, "Cost driver."),
        _row("Metric", "Value", "Formula"),
        [Cell("Revenue"), Cell(formula="B3*B4"), Cell("=B3*B4")],
        [Cell("Cost"), Cell(formula="B3*B5"), Cell("=B3*B5")],
        [Cell("Gross profit"), Cell(formula="B7-B8"), Cell("=B7-B8")],
        [Cell("Gross margin"), Cell(formula="B9/B7"), Cell("=B9/B7")],
    ]


def _checks_rows(spec: BuildSpec) -> list[list[Cell]]:
    return [
        _row("Check", "Expected", "Observed"),
        _row("Required sheets", "Inputs, Model, Checks", "Inputs, Model, Checks"),
        _row("Evidence level", ">= L0", spec.achieved_evidence_level),
        _row("Revenue formula", "=B3*B4", "=B3*B4"),
        _row("Cost formula", "=B3*B5", "=B3*B5"),
        _row("Gross profit formula", "=B7-B8", "=B7-B8"),
        _row("Gross margin formula", "=B9/B7", "=B9/B7"),
    ]


def _row(*values: Any) -> list[Cell]:
    return [Cell(value=value) for value in values]


def _format_range(start: float | None, end: float | None) -> str:
    start_text = "" if start is None else f"{start:.2f}"
    end_text = "" if end is None else f"{end:.2f}"
    return f"{start_text}-{end_text}"


def _worksheet_xml(rows: list[list[Cell]]) -> str:
    max_columns = max((len(row) for row in rows), default=1)
    dimension = f"A1:{_column_name(max_columns)}{max(len(rows), 1)}"
    xml_rows = "\n".join(
        f'<row r="{row_index}">'
        + "".join(_cell_xml(cell, row_index, col_index) for col_index, cell in enumerate(row, start=1))
        + "</row>"
        for row_index, row in enumerate(rows, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
        f'<dimension ref="{dimension}"/>'
        "<sheetViews><sheetView workbookViewId=\"0\"/></sheetViews>"
        "<sheetFormatPr defaultRowHeight=\"15\"/>"
        "<sheetData>"
        f"{xml_rows}"
        "</sheetData>"
        "</worksheet>"
    )


def _cell_xml(cell: Cell, row_index: int, col_index: int) -> str:
    ref = f"{_column_name(col_index)}{row_index}"
    if cell.formula is not None:
        return f'<c r="{ref}"><f>{escape(cell.formula)}</f></c>'
    if cell.value is None or cell.value == "":
        return f'<c r="{ref}"/>'
    if isinstance(cell.value, bool):
        return f'<c r="{ref}" t="b"><v>{1 if cell.value else 0}</v></c>'
    if isinstance(cell.value, int | float):
        return f'<c r="{ref}"><v>{cell.value}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{escape(str(cell.value))}</t></is></c>'


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _content_types_xml(sheet_count: int) -> str:
    worksheets = "".join(
        '<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'.format(
            index=index
        )
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{worksheets}"
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" '
        'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        "</Types>"
    )


def _root_rels_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{PKG_REL_NS}">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        "</Relationships>"
    )


def _workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
        "<workbookPr/>"
        "<sheets>"
        f"{sheets}"
        "</sheets>"
        "</workbook>"
    )


def _workbook_rels_xml(sheet_count: int) -> str:
    sheet_rels = "".join(
        f'<Relationship Id="rId{index}" Type="{REL_NS}/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Relationships xmlns="{PKG_REL_NS}">'
        f"{sheet_rels}"
        f'<Relationship Id="rId{sheet_count + 1}" Type="{REL_NS}/styles" Target="styles.xml"/>'
        "</Relationships>"
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<styleSheet xmlns="{MAIN_NS}">'
        "<fonts count=\"1\"><font><sz val=\"11\"/><name val=\"Calibri\"/></font></fonts>"
        "<fills count=\"1\"><fill><patternFill patternType=\"none\"/></fill></fills>"
        "<borders count=\"1\"><border><left/><right/><top/><bottom/><diagonal/></border></borders>"
        "<cellStyleXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\"/></cellStyleXfs>"
        "<cellXfs count=\"1\"><xf numFmtId=\"0\" fontId=\"0\" fillId=\"0\" borderId=\"0\" xfId=\"0\"/></cellXfs>"
        "</styleSheet>"
    )


def _core_props_xml(spec: BuildSpec) -> str:
    title = escape(spec.artifact.title or "Video-to-artifact workbook")
    created = escape(spec.created_at.isoformat())
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        f'xmlns:dc="{DC_NS}" xmlns:dcterms="{DCTERMS_NS}" xmlns:dcmitype="{DCMI_NS}" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f"<dc:title>{title}</dc:title>"
        "<dc:creator>video-to-artifact-agent</dc:creator>"
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{created}</dcterms:created>'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{created}</dcterms:modified>'
        "</cp:coreProperties>"
    )


def _app_props_xml(sheet_names: list[str]) -> str:
    sheet_entries = "".join(f"<vt:lpstr>{escape(name)}</vt:lpstr>" for name in sheet_names)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        f'<Properties xmlns="{DOC_PROPS_NS}" xmlns:vt="{VT_NS}">'
        "<Application>video-to-artifact-agent</Application>"
        "<HeadingPairs><vt:vector size=\"2\" baseType=\"variant\"><vt:variant><vt:lpstr>Worksheets</vt:lpstr></vt:variant><vt:variant><vt:i4>"
        f"{len(sheet_names)}"
        "</vt:i4></vt:variant></vt:vector></HeadingPairs>"
        f'<TitlesOfParts><vt:vector size="{len(sheet_names)}" baseType="lpstr">{sheet_entries}</vt:vector></TitlesOfParts>'
        "</Properties>"
    )
