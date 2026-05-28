"""JSON file loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LoadResult:
    """Result of loading a JSON data file."""

    records: list[dict[str, Any]]
    format_detected: str  # "JSON Array" or "NDJSON"
    file_path: Path
    file_size_bytes: int
    record_count: int
    warnings: list[str] = field(default_factory=list)

    @property
    def avg_record_bytes(self) -> float:
        if not self.records:
            return 0.0
        total = sum(len(json.dumps(r).encode("utf-8")) for r in self.records)
        return total / len(self.records)


def load_json_file(path: Path) -> LoadResult:
    """Load a JSON file and return parsed records.

    Supports two formats (auto-detected):
    - JSON Array: file contains a single JSON array of objects
    - NDJSON: one JSON object per line (blank lines and lines starting with // are skipped)
    """
    raw = path.read_text(encoding="utf-8")
    file_size = path.stat().st_size
    stripped = raw.strip()

    if not stripped:
        return LoadResult(
            records=[],
            format_detected="Empty",
            file_path=path,
            file_size_bytes=file_size,
            record_count=0,
            warnings=["File is empty."],
        )

    if stripped.startswith("["):
        return _parse_json_array(stripped, path, file_size)
    else:
        return _parse_ndjson(stripped, path, file_size)


def _parse_json_array(content: str, path: Path, file_size: int) -> LoadResult:
    """Parse file as a JSON array of objects."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}.")

    records: list[dict[str, Any]] = []
    warnings: list[str] = []

    for i, item in enumerate(data):
        if isinstance(item, dict):
            records.append(item)
        else:
            warnings.append(f"Record {i} is {type(item).__name__}, not an object — skipped.")

    return LoadResult(
        records=records,
        format_detected="JSON Array",
        file_path=path,
        file_size_bytes=file_size,
        record_count=len(records),
        warnings=warnings,
    )


def _parse_ndjson(content: str, path: Path, file_size: int) -> LoadResult:
    """Parse file as newline-delimited JSON (one object per line)."""
    records: list[dict[str, Any]] = []
    warnings: list[str] = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("//"):
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            warnings.append(f"Line {line_num}: invalid JSON — {exc}. Skipped.")
            continue

        if isinstance(obj, dict):
            records.append(obj)
        else:
            warnings.append(f"Line {line_num}: {type(obj).__name__}, not an object — skipped.")

    return LoadResult(
        records=records,
        format_detected="NDJSON",
        file_path=path,
        file_size_bytes=file_size,
        record_count=len(records),
        warnings=warnings,
    )
