"""Bundled sample dataset discovery and resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

_SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"

SAMPLES: list[dict[str, str]] = [
    {
        "file": "finance.json",
        "label": "💳 Finance",
        "description": "Credit card fraud detection events with risk scoring",
    },
    {
        "file": "healthcare.json",
        "label": "🏥 Healthcare",
        "description": "Patient vital signs monitoring from hospital wards",
    },
    {
        "file": "retail_commerce.json",
        "label": "🛒 Retail & Commerce",
        "description": "Point-of-sale transactions across store locations",
    },
    {
        "file": "media_comms.json",
        "label": "📡 Media & Communications",
        "description": "Network interface traffic and throughput telemetry",
    },
    {
        "file": "travel_transport.json",
        "label": "🚆 Travel & Transport",
        "description": "Live train departure and arrival events",
    },
    {
        "file": "local_gov.json",
        "label": "🏛️  Local Government",
        "description": "Environmental sensor readings across council districts",
    },
]


def get_sample_dir() -> Path:
    """Return the path to the bundled sample-data directory."""
    return _SAMPLE_DIR


def list_available_samples() -> list[dict[str, str]]:
    """Return only samples whose files exist on disk."""
    return [s for s in SAMPLES if (_SAMPLE_DIR / s["file"]).exists()]


def resolve_data_file(user_path: Path) -> Optional[Path]:
    """Resolve a user-provided file path, falling back to bundled samples.

    Resolution order:
      1. If the path exists as-is (absolute or relative to CWD), use it.
      2. If the filename (with or without .json) matches a bundled sample, use that.
      3. Return None if nothing matched.
    """
    if user_path.exists():
        return user_path.resolve()

    name = user_path.name

    # Try exact filename match against bundled samples
    candidate = _SAMPLE_DIR / name
    if candidate.exists():
        return candidate

    # Try appending .json extension
    if not name.endswith(".json"):
        candidate = _SAMPLE_DIR / (name + ".json")
        if candidate.exists():
            return candidate

    return None
