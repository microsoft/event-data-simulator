"""YAML configuration file support."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SimulatorConfig:
    """Merged configuration from config file + CLI flags.

    All fields default to None/sentinel to distinguish 'not set'
    from an explicit value. The merge logic layers:
      hardcoded defaults → config file → CLI flags
    """

    file: Optional[Path] = None
    connection_string: Optional[str] = None
    eventhub_name: Optional[str] = None
    eps: Optional[float] = None
    interval: Optional[float] = None
    burst: Optional[bool] = None
    jitter: Optional[float] = None
    loop: Optional[bool] = None
    repeat: Optional[int] = None
    duration: Optional[str] = None
    dry_run: Optional[bool] = None
    preview: Optional[int] = None
    quiet: Optional[bool] = None
    verbose: Optional[bool] = None
    no_progress: Optional[bool] = None
    batch_size: Optional[int] = None
    timestamp_field: Optional[str] = None
    timestamp_format: Optional[str] = None


# Maps YAML keys to SimulatorConfig field names
_YAML_KEY_MAP: dict[str, str] = {
    "file": "file",
    "connection_string": "connection_string",
    "eventhub_name": "eventhub_name",
    "eps": "eps",
    "interval": "interval",
    "burst": "burst",
    "jitter": "jitter",
    "loop": "loop",
    "repeat": "repeat",
    "duration": "duration",
    "dry_run": "dry_run",
    "preview": "preview",
    "quiet": "quiet",
    "verbose": "verbose",
    "no_progress": "no_progress",
    "batch_size": "batch_size",
    "timestamp_field": "timestamp_field",
    "timestamp_format": "timestamp_format",
}


def load_config_file(path: Path) -> SimulatorConfig:
    """Load a YAML configuration file and return a SimulatorConfig."""
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required for config file support. Install it with: pip install pyyaml"
        )

    raw = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)

    if data is None:
        return SimulatorConfig()

    if not isinstance(data, dict):
        raise ValueError(f"Config file must be a YAML mapping, got {type(data).__name__}.")

    config = SimulatorConfig()

    for yaml_key, field_name in _YAML_KEY_MAP.items():
        if yaml_key in data:
            value = data[yaml_key]

            # Resolve file path relative to config file's directory
            if field_name == "file" and value is not None:
                file_path = Path(value)
                if not file_path.is_absolute():
                    config_relative = path.parent / file_path
                    if config_relative.exists():
                        value = config_relative.resolve()
                    else:
                        # Keep as bare Path — CLI sample resolution handles fallback
                        value = file_path
                else:
                    value = file_path

            # Coerce duration to string (YAML may parse '5m' as string, but '60' as int)
            if field_name == "duration" and value is not None:
                value = str(value)

            setattr(config, field_name, value)

    # Warn about unrecognised keys
    unknown = set(data.keys()) - set(_YAML_KEY_MAP.keys())
    if unknown:
        from rich.console import Console
        Console().print(
            f"[yellow]⚠ Warning:[/yellow] Unknown config keys ignored: {', '.join(sorted(unknown))}"
        )

    return config


def merge_configs(
    cli: SimulatorConfig,
    file_cfg: SimulatorConfig | None,
) -> SimulatorConfig:
    """Merge CLI values over config file values.

    CLI values (non-None) always win. Config file fills in the gaps.
    """
    if file_cfg is None:
        return cli

    merged = SimulatorConfig()

    for field_name in _YAML_KEY_MAP.values():
        cli_val = getattr(cli, field_name)
        file_val = getattr(file_cfg, field_name)
        # CLI wins if it was explicitly set (not None)
        setattr(merged, field_name, cli_val if cli_val is not None else file_val)

    return merged


def apply_defaults(config: SimulatorConfig) -> SimulatorConfig:
    """Fill in hardcoded defaults for any values still None after merge."""
    if config.burst is None:
        config.burst = False
    if config.jitter is None:
        config.jitter = 0.0
    if config.loop is None:
        config.loop = False
    if config.repeat is None:
        config.repeat = 1
    if config.dry_run is None:
        config.dry_run = False
    if config.quiet is None:
        config.quiet = False
    if config.verbose is None:
        config.verbose = False
    if config.no_progress is None:
        config.no_progress = False
    return config
