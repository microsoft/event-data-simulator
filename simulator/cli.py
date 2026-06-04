"""Typer CLI application for the Event Data Simulator."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env BEFORE Typer parses envvar= defaults
load_dotenv()

import typer
from typing_extensions import Annotated

from simulator import __version__
from simulator.config import (
    SimulatorConfig,
    apply_defaults,
    load_config_file,
    merge_configs,
)

app = typer.Typer(
    name="rti-simulator",
    help="Stream JSON events to Microsoft Fabric Eventstreams and Azure Event Hubs.",
    add_completion=False,
    rich_markup_mode="rich",
)


def parse_duration(value: str) -> float:
    """Parse a human-readable duration string into seconds.

    Accepted formats: '30s', '5m', '1h', '1h30m', '90' (plain seconds).
    """
    if not value:
        raise typer.BadParameter("Duration cannot be empty.")

    # Plain number = seconds
    try:
        return float(value)
    except ValueError:
        pass

    pattern = re.compile(
        r"^(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?$",
        re.IGNORECASE,
    )
    match = pattern.match(value.strip())
    if not match or not any(match.groups()):
        raise typer.BadParameter(
            f"Invalid duration '{value}'. Use formats like '30s', '5m', '1h', '1h30m', or plain seconds."
        )

    hours = float(match.group(1) or 0)
    minutes = float(match.group(2) or 0)
    seconds = float(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def version_callback(value: bool) -> None:
    if value:
        typer.echo(f"Event Data Simulator v{__version__}")
        raise typer.Exit()


@app.command()
def main(
    # ── Positional argument ──────────────────────────────────────────────
    file: Annotated[
        Optional[Path],
        typer.Argument(
            help="Path to the JSON data file. Optional if specified in --config.",
        ),
    ] = None,
    # ── Config file option ───────────────────────────────────────────────
    config_file: Annotated[
        Optional[Path],
        typer.Option(
            "--config",
            help="Path to a YAML configuration file. CLI flags override config file values.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ] = None,
    # ── Connection options ───────────────────────────────────────────────
    connection_string: Annotated[
        Optional[str],
        typer.Option(
            "--connection-string",
            "-c",
            help="Event Hub / Eventstream connection string. Overrides config file and .env.",
            envvar="EVENT_HUB_CONNECTION_STRING",
        ),
    ] = None,
    eventhub_name: Annotated[
        Optional[str],
        typer.Option(
            "--eventhub-name",
            "-n",
            help="Event Hub name. Only needed if the connection string lacks EntityPath.",
        ),
    ] = None,
    # ── Rate control options ─────────────────────────────────────────────
    eps: Annotated[
        Optional[float],
        typer.Option(
            "--eps",
            "-e",
            help="Events per second. Accepts decimals (e.g. 0.5 = one event every 2s).",
            min=0.001,
        ),
    ] = None,
    interval: Annotated[
        Optional[float],
        typer.Option(
            "--interval",
            "-i",
            help="Seconds between events. Alternative to --eps. Mutually exclusive with --eps.",
            min=0.0,
        ),
    ] = None,
    burst: Annotated[
        Optional[bool],
        typer.Option(
            "--burst",
            "-b",
            help="Send all events as fast as possible with no rate limiting.",
        ),
    ] = None,
    jitter: Annotated[
        Optional[float],
        typer.Option(
            "--jitter",
            "-j",
            help="Random ±variation in send interval as a percentage (0–100). Makes timing more realistic.",
            min=0.0,
            max=100.0,
        ),
    ] = None,
    # ── Playback / duration options ──────────────────────────────────────
    loop: Annotated[
        Optional[bool],
        typer.Option(
            "--loop",
            "-l",
            help="Continuously replay the file until Ctrl+C or --duration is hit.",
        ),
    ] = None,
    repeat: Annotated[
        Optional[int],
        typer.Option(
            "--repeat",
            "-r",
            help="Number of times to play through the file. 0 = infinite (same as --loop).",
            min=0,
        ),
    ] = None,
    duration: Annotated[
        Optional[str],
        typer.Option(
            "--duration",
            "-d",
            help="Maximum run duration. Accepts '30s', '5m', '1h', '1h30m', or plain seconds.",
        ),
    ] = None,
    # ── Output / display options ─────────────────────────────────────────
    dry_run: Annotated[
        Optional[bool],
        typer.Option(
            "--dry-run",
            help="Validate the file and display stats without sending any events.",
        ),
    ] = None,
    preview: Annotated[
        Optional[int],
        typer.Option(
            "--preview",
            "-p",
            help="Show the first N events from the file and exit.",
            min=1,
        ),
    ] = None,
    quiet: Annotated[
        Optional[bool],
        typer.Option(
            "--quiet",
            "-q",
            help="Suppress all output except errors.",
        ),
    ] = None,
    verbose: Annotated[
        Optional[bool],
        typer.Option(
            "--verbose",
            "-v",
            help="Show each event payload as it is sent.",
        ),
    ] = None,
    no_progress: Annotated[
        Optional[bool],
        typer.Option(
            "--no-progress",
            help="Disable the live progress bar but keep banner and summary.",
        ),
    ] = None,
    # ── Batch / advanced options ─────────────────────────────────────────
    batch_size: Annotated[
        Optional[int],
        typer.Option(
            "--batch-size",
            help="Maximum events per Event Hub batch. Default: auto (up to 1MB limit).",
            min=1,
        ),
    ] = None,
    # ── Timestamp injection ──────────────────────────────────────────────
    timestamp_field: Annotated[
        Optional[str],
        typer.Option(
            "--timestamp-field",
            "-t",
            help="JSON field name to overwrite with the current timestamp on each send (e.g. 'timestamp', 'event_time').",
        ),
    ] = None,
    timestamp_format: Annotated[
        Optional[str],
        typer.Option(
            "--timestamp-format",
            help="strftime format for the injected timestamp. Default: ISO 8601 (%%Y-%%m-%%dT%%H:%%M:%%SZ).",
        ),
    ] = None,
    # ── Meta ─────────────────────────────────────────────────────────────
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """Stream JSON events to Microsoft Fabric Eventstreams and Azure Event Hubs.

    Each JSON record in FILE is sent as a separate event. Supports JSON arrays
    and newline-delimited JSON (NDJSON) formats, auto-detected.

    Use --config to load settings from a YAML file. CLI flags override config
    file values.

    Run with no arguments to launch the guided setup wizard.
    """
    from simulator.display import SimulatorDisplay
    from simulator.loader import load_json_file
    from simulator.sender import EventSender, StreamConfig
    from simulator.wizard import run_wizard, should_launch_wizard

    # ── Launch wizard if no file/config/action was given ─────────────────
    if should_launch_wizard(file, config_file, dry_run, preview):
        run_wizard()
        raise typer.Exit()

    # ── Build CLI config (only values explicitly set) ────────────────────
    cli_cfg = SimulatorConfig(
        file=file if file else None,
        connection_string=connection_string,
        eventhub_name=eventhub_name,
        eps=eps,
        interval=interval,
        burst=burst,
        jitter=jitter,
        loop=loop,
        repeat=repeat,
        duration=duration,
        dry_run=dry_run,
        preview=preview,
        quiet=quiet,
        verbose=verbose,
        no_progress=no_progress,
        batch_size=batch_size,
        timestamp_field=timestamp_field,
        timestamp_format=timestamp_format,
    )

    # ── Load and merge config file ───────────────────────────────────────
    file_cfg = None
    if config_file:
        try:
            file_cfg = load_config_file(config_file)
        except Exception as exc:
            from rich.console import Console
            Console().print(f"[bold red]✖ Error:[/bold red] Failed to load config file: {exc}")
            raise typer.Exit(1)

    cfg = apply_defaults(merge_configs(cli_cfg, file_cfg))

    display = SimulatorDisplay(quiet=cfg.quiet)

    # ── Validate FILE is provided ────────────────────────────────────────
    if cfg.file is None:
        display.show_error(
            "No data file specified. Provide FILE as an argument or set 'file' in your config YAML."
        )
        raise typer.Exit(1)

    # Resolve file path — try bundled samples as fallback
    from simulator.samples import resolve_data_file

    resolved = resolve_data_file(cfg.file)
    if resolved is None:
        from simulator.samples import list_available_samples

        available = [s["file"] for s in list_available_samples()]
        hint = ""
        if available:
            hint = f"\n  Bundled samples: {', '.join(available)}"
        display.show_error(f"File not found: {cfg.file}{hint}")
        raise typer.Exit(1)
    cfg.file = resolved

    # ── Validate mutual exclusivity ──────────────────────────────────────
    rate_opts = sum([cfg.eps is not None, cfg.interval is not None, cfg.burst])
    if rate_opts > 1:
        display.show_error("Options --eps, --interval, and --burst are mutually exclusive.")
        raise typer.Exit(1)

    if cfg.loop and cfg.repeat != 1:
        display.show_error("Options --loop and --repeat are mutually exclusive. Use --repeat 0 for infinite.")
        raise typer.Exit(1)

    # ── Resolve effective rate ───────────────────────────────────────────
    if cfg.burst:
        effective_eps: Optional[float] = None
    elif cfg.interval is not None:
        effective_eps = 1.0 / cfg.interval if cfg.interval > 0 else None
    elif cfg.eps is not None:
        effective_eps = cfg.eps
    else:
        effective_eps = 1.0

    # ── Resolve playback ────────────────────────────────────────────────
    effective_repeat = 0 if cfg.loop else cfg.repeat
    duration_seconds = parse_duration(cfg.duration) if cfg.duration else None

    # ── Load data ────────────────────────────────────────────────────────
    try:
        load_result = load_json_file(cfg.file)
    except Exception as exc:
        display.show_error(f"Failed to load {cfg.file.name}: {exc}")
        raise typer.Exit(1)

    if not load_result.records:
        display.show_error(f"No records found in {cfg.file.name}.")
        raise typer.Exit(1)

    # ── Handle preview mode ──────────────────────────────────────────────
    if cfg.preview is not None:
        display.show_preview(load_result.records, cfg.preview)
        raise typer.Exit()

    # ── Build stream config ──────────────────────────────────────────────
    stream_config = StreamConfig(
        eps=effective_eps,
        burst=cfg.burst,
        jitter=cfg.jitter,
        repeat=effective_repeat,
        duration_seconds=duration_seconds,
        batch_size=cfg.batch_size,
        verbose=cfg.verbose,
        timestamp_field=cfg.timestamp_field,
        timestamp_format=cfg.timestamp_format,
    )

    # ── Handle dry-run mode ──────────────────────────────────────────────
    if cfg.dry_run:
        display.show_dry_run(load_result, stream_config)
        raise typer.Exit()

    # ── Validate connection ──────────────────────────────────────────────
    if not cfg.connection_string:
        display.show_error(
            "No connection string provided. Set it in your config YAML, .env file, or use --connection-string."
        )
        raise typer.Exit(1)

    # ── Stream events ────────────────────────────────────────────────────
    display.show_banner(load_result, stream_config, cfg.connection_string)

    sender = EventSender(
        connection_string=cfg.connection_string,
        eventhub_name=cfg.eventhub_name,
    )

    try:
        stats = sender.stream(
            records=load_result.records,
            config=stream_config,
            display=display,
            show_progress=not cfg.no_progress,
        )
        display.show_summary(stats)
    except KeyboardInterrupt:
        display.show_summary(sender.get_stats(), interrupted=True)
    finally:
        sender.close()


if __name__ == "__main__":
    app()
