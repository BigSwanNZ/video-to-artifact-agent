from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from video_to_artifact_agent.privacy import redact_text
from video_to_artifact_agent.schemas import (
    BuildSpec,
    EvidenceKind,
    EvidenceRecord,
    TranscriptEvidence,
    TranscriptSegment,
)

TranscriptFormat = Literal["srt", "vtt", "json"]
TranscriptKind = Literal["subtitle", "asr"]

_TIMING_RE = re.compile(
    r"(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{3}|\d{1,2}:\d{2}[,.]\d{3})"
    r"\s+-->\s+"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{3}|\d{1,2}:\d{2}[,.]\d{3})"
)


class TranscriptParseError(ValueError):
    """Raised when transcript text cannot be parsed into timed segments."""


class TranscriptCoverageError(ValueError):
    """Raised when transcript coverage does not meet the requested threshold."""


def parse_transcript(
    text: str,
    *,
    fmt: TranscriptFormat,
    kind: TranscriptKind,
    language: str | None = None,
    audio_duration_sec: float | None = None,
    model: str | None = None,
    coverage_threshold_pct: float = 95.0,
    require_coverage: bool = False,
) -> TranscriptEvidence:
    """Parse transcript text into the shared TranscriptEvidence schema."""
    if fmt == "json":
        segments, json_language, json_duration = _parse_json_segments(text)
        language = language or json_language
        audio_duration_sec = audio_duration_sec if audio_duration_sec is not None else json_duration
    elif fmt in {"srt", "vtt"}:
        segments = _parse_timed_text(text, fmt=fmt)
    else:
        raise TranscriptParseError(f"Unsupported transcript format: {fmt}")

    transcript = TranscriptEvidence(
        kind=kind,
        model=model,
        language=language,
        segments=segments,
        audio_duration_sec=audio_duration_sec,
        coverage_threshold_pct=coverage_threshold_pct,
    )
    if require_coverage and not transcript.passes_coverage_gate:
        raise TranscriptCoverageError(
            "Transcript coverage "
            f"{transcript.coverage_pct}% is below required threshold {coverage_threshold_pct}%"
        )
    return transcript


def parse_transcript_file(
    path: str | Path,
    *,
    kind: TranscriptKind,
    language: str | None = None,
    audio_duration_sec: float | None = None,
    model: str | None = None,
    coverage_threshold_pct: float = 95.0,
    require_coverage: bool = False,
) -> TranscriptEvidence:
    """Read a transcript file and infer its parser from the file suffix."""
    transcript_path = Path(path)
    return parse_transcript(
        transcript_path.read_text(encoding="utf-8-sig"),
        fmt=_format_from_suffix(transcript_path),
        kind=kind,
        language=language,
        audio_duration_sec=audio_duration_sec,
        model=model,
        coverage_threshold_pct=coverage_threshold_pct,
        require_coverage=require_coverage,
    )


def merge_transcript_evidence(
    spec: BuildSpec,
    transcript: TranscriptEvidence,
    *,
    source_ref: str | None = None,
    summary: str | None = None,
) -> BuildSpec:
    """Attach transcript evidence to a BuildSpec and append its L2 evidence record."""
    spec.transcript = transcript
    spec.evidence.append(
        EvidenceRecord(
            kind=EvidenceKind(transcript.kind),
            level="L2",
            summary=summary or _evidence_summary(transcript),
            source_ref=redact_text(source_ref) if source_ref else None,
            time_start_sec=transcript.segments[0].start if transcript.segments else None,
            time_end_sec=transcript.last_segment_end_sec,
            metadata={
                "language": transcript.language,
                "audio_duration_sec": transcript.audio_duration_sec,
                "coverage_pct": transcript.coverage_pct,
                "coverage_threshold_pct": transcript.coverage_threshold_pct,
                "segment_count": len(transcript.segments),
                "passes_coverage_gate": transcript.passes_coverage_gate,
                "model": transcript.model,
            },
        )
    )
    return spec


def _parse_timed_text(text: str, *, fmt: TranscriptFormat) -> list[TranscriptSegment]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    segments: list[TranscriptSegment] = []
    for block in blocks:
        lines = [line.strip("\ufeff ") for line in block.split("\n") if line.strip()]
        if not lines or lines[0] == "WEBVTT" or lines[0].startswith(("NOTE", "STYLE", "REGION")):
            continue

        timing_index = _find_timing_line(lines)
        if timing_index is None:
            continue

        timing = _TIMING_RE.search(lines[timing_index])
        if timing is None:
            continue

        text_lines = [
            _clean_cue_text(line)
            for line in lines[timing_index + 1 :]
            if not line.startswith(("NOTE", "STYLE", "REGION"))
        ]
        cue_text = " ".join(line for line in text_lines if line).strip()
        if not cue_text:
            continue

        segments.append(
            TranscriptSegment(
                start=_timestamp_to_seconds(timing.group("start")),
                end=_timestamp_to_seconds(timing.group("end")),
                text=cue_text,
            )
        )

    if not segments:
        raise TranscriptParseError(f"No timed transcript segments found in {fmt} input")
    return segments


def _parse_json_segments(text: str) -> tuple[list[TranscriptSegment], str | None, float | None]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TranscriptParseError(f"Invalid JSON transcript: {exc}") from exc

    language: str | None = None
    duration: float | None = None
    raw_segments: Any
    if isinstance(payload, list):
        raw_segments = payload
    elif isinstance(payload, dict):
        raw_segments = payload.get("segments")
        language_value = payload.get("language")
        language = language_value if isinstance(language_value, str) else None
        duration = _number_or_none(
            payload.get("audio_duration_sec", payload.get("duration_sec", payload.get("duration")))
        )
    else:
        raise TranscriptParseError("JSON transcript must be a list or object with segments")

    if not isinstance(raw_segments, list):
        raise TranscriptParseError("JSON transcript requires a segments list")

    segments = [_json_segment_to_schema(segment) for segment in raw_segments]
    if not segments:
        raise TranscriptParseError("JSON transcript contains no segments")
    return segments, language, duration


def _json_segment_to_schema(segment: Any) -> TranscriptSegment:
    if not isinstance(segment, dict):
        raise TranscriptParseError("JSON transcript segments must be objects")
    start = _number_or_none(segment.get("start", segment.get("start_sec")))
    end = _number_or_none(segment.get("end", segment.get("end_sec")))
    text = segment.get("text")
    if start is None or end is None or not isinstance(text, str) or not text.strip():
        raise TranscriptParseError("JSON transcript segment requires start, end, and text")
    return TranscriptSegment(start=start, end=end, text=text.strip())


def _find_timing_line(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if "-->" in line:
            return index
    return None


def _timestamp_to_seconds(value: str) -> float:
    normalized = value.replace(",", ".")
    parts = normalized.split(":")
    if len(parts) == 2:
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    hours, minutes, seconds = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _clean_cue_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    return without_tags.strip()


def _number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_from_suffix(path: Path) -> TranscriptFormat:
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return "srt"
    if suffix in {".vtt", ".webvtt"}:
        return "vtt"
    if suffix == ".json":
        return "json"
    raise TranscriptParseError(f"Cannot infer transcript format from suffix: {path.suffix}")


def _evidence_summary(transcript: TranscriptEvidence) -> str:
    segment_label = "segment" if len(transcript.segments) == 1 else "segments"
    coverage = (
        f", {transcript.coverage_pct}% coverage"
        if transcript.coverage_pct is not None
        else ""
    )
    return f"Ingested {len(transcript.segments)} {transcript.kind} {segment_label}{coverage}."
