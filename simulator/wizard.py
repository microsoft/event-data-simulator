"""Guided first-run wizard for new users."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.syntax import Syntax
from rich.table import Table

from simulator import __version__
from simulator.samples import get_sample_dir, list_available_samples

console = Console()


def should_launch_wizard(
    file: Optional[Path],
    config_file: Optional[Path],
    dry_run: Optional[bool],
    preview: Optional[int],
) -> bool:
    """Return True if no file/config/action was specified — i.e. the user
    ran bare ``python -m simulator`` and likely needs guidance."""
    return (
        file is None
        and config_file is None
        and not dry_run
        and preview is None
    )


def run_wizard() -> None:
    """Interactive first-run wizard."""

    # ── Welcome ──────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            "[bold]Welcome to the Event Data Simulator![/bold]\n\n"
            "This wizard will walk you through:\n"
            "  [cyan]1.[/cyan] Connecting to your Eventstream or Event Hub\n"
            "  [cyan]2.[/cyan] Choosing a dataset to stream\n"
            "  [cyan]3.[/cyan] Sending a test stream\n\n"
            "[dim]You can skip this wizard next time by providing a file argument or --config.[/dim]",
            title=f"[bold blue]Event Data Simulator v{__version__}[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
    )

    # ── Step 1: Connection string ────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 1 of 3 — Connection String[/bold cyan]")
    console.print()
    console.print(
        "Paste the connection string from your Eventstream Custom Endpoint.\n"
        "[dim]Find it in: Fabric → Eventstream → Custom Endpoint → Details → "
        "Event Hub tab → SAS Key Authentication → Connection string–primary key[/dim]"
    )
    console.print()

    connection_string = Prompt.ask(
        "[bold]Connection string[/bold]",
    ).strip()

    if not connection_string:
        console.print("[red]No connection string provided. Exiting.[/red]")
        raise SystemExit(1)

    # Quick validation
    if "Endpoint=sb://" not in connection_string and "endpoint=sb://" not in connection_string.lower():
        console.print(
            "[yellow]⚠ Warning:[/yellow] This doesn't look like a standard Event Hub "
            "connection string (expected 'Endpoint=sb://...'). Continuing anyway."
        )

    # Offer to save to .env
    console.print()
    save_env = Confirm.ask(
        "Save this connection string to [bold].env[/bold] so you don't need to paste it again?",
        default=True,
    )
    if save_env:
        _save_connection_string(connection_string)

    # ── Step 2: Choose dataset ───────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 2 of 3 — Choose a Dataset[/bold cyan]")
    console.print()

    # Build table of sample options
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("#", style="cyan", width=3)
    table.add_column("Dataset", min_width=20)
    table.add_column("Description")

    available_samples = list_available_samples()

    for i, sample in enumerate(available_samples, 1):
        table.add_row(str(i), sample["label"], sample["description"])
    table.add_row(str(len(available_samples) + 1), "📂 Your own file", "Provide a path to your JSON file")

    console.print(table)
    console.print()

    choice = IntPrompt.ask(
        "[bold]Select a dataset[/bold]",
        choices=[str(i) for i in range(1, len(available_samples) + 2)],
        default=1,
    )

    if choice <= len(available_samples):
        sample = available_samples[choice - 1]
        data_file = get_sample_dir() / sample["file"]
        console.print(f"  Selected: [bold]{sample['label']}[/bold]")
    else:
        file_path = Prompt.ask("[bold]Path to your JSON file[/bold]")
        data_file = Path(file_path.strip()).resolve()
        if not data_file.exists():
            console.print(f"[red]File not found: {data_file}[/red]")
            raise SystemExit(1)

    # Preview the data
    console.print()
    try:
        raw = data_file.read_text(encoding="utf-8")
        records = json.loads(raw) if raw.strip().startswith("[") else [
            json.loads(line) for line in raw.strip().splitlines() if line.strip()
        ]
        preview_n = min(2, len(records))
        console.print(f"[dim]Preview ({preview_n} of {len(records)} events):[/dim]")
        for r in records[:preview_n]:
            syntax = Syntax(json.dumps(r, indent=2), "json", theme="monokai")
            console.print(syntax)
    except Exception:
        console.print("[dim]Could not preview file.[/dim]")
        records = []

    # ── Step 3: Test stream ──────────────────────────────────────────────
    console.print()
    console.print("[bold cyan]Step 3 of 3 — Test Stream[/bold cyan]")
    console.print()

    num_events = min(5, len(records)) if records else 5
    console.print(
        f"Ready to send [bold]{num_events} events[/bold] at [bold]1 event/sec[/bold] "
        f"to verify your connection works.\n"
        "[dim]Timestamps will be injected automatically so events appear fresh.[/dim]"
    )
    console.print()

    go = Confirm.ask("Start the test stream?", default=True)

    if not go:
        _show_next_steps(data_file)
        raise SystemExit(0)

    # Run the test stream
    console.print()
    _run_test_stream(
        connection_string=connection_string,
        data_file=data_file,
        num_events=num_events,
    )

    # ── Done ─────────────────────────────────────────────────────────────
    _show_next_steps(data_file)


def _save_connection_string(conn_str: str) -> None:
    """Save the connection string to a .env file."""
    env_path = Path.cwd() / ".env"
    try:
        if env_path.exists():
            # Append or update
            content = env_path.read_text(encoding="utf-8")
            if "EVENT_HUB_CONNECTION_STRING" in content:
                lines = content.splitlines()
                new_lines = []
                for line in lines:
                    if line.strip().startswith("EVENT_HUB_CONNECTION_STRING"):
                        new_lines.append(f"EVENT_HUB_CONNECTION_STRING={conn_str}")
                    else:
                        new_lines.append(line)
                env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            else:
                with env_path.open("a", encoding="utf-8") as f:
                    f.write(f"\nEVENT_HUB_CONNECTION_STRING={conn_str}\n")
        else:
            env_path.write_text(
                f"EVENT_HUB_CONNECTION_STRING={conn_str}\n",
                encoding="utf-8",
            )
        console.print(f"  [green]✓[/green] Saved to [bold]{env_path}[/bold]")
    except OSError as exc:
        console.print(f"  [yellow]⚠ Could not save .env: {exc}[/yellow]")


def _run_test_stream(
    connection_string: str,
    data_file: Path,
    num_events: int,
) -> None:
    """Send a small test stream."""
    from simulator.display import SimulatorDisplay
    from simulator.loader import load_json_file
    from simulator.sender import EventSender, StreamConfig

    display = SimulatorDisplay(quiet=False)

    try:
        load_result = load_json_file(data_file)
    except Exception as exc:
        console.print(f"[red]Failed to load file: {exc}[/red]")
        raise SystemExit(1)

    # Take only the first N records
    test_records = load_result.records[:num_events]

    config = StreamConfig(
        eps=1.0,
        burst=False,
        jitter=0.0,
        repeat=1,
        duration_seconds=None,
        batch_size=None,
        verbose=True,
        timestamp_field=_detect_timestamp_field(test_records),
    )

    sender = EventSender(
        connection_string=connection_string,
    )

    try:
        stats = sender.stream(
            records=test_records,
            config=config,
            display=display,
            show_progress=True,
        )
        display.show_summary(stats)
    except KeyboardInterrupt:
        display.show_summary(sender.get_stats(), interrupted=True)
    except Exception as exc:
        console.print(f"\n[bold red]✖ Connection failed:[/bold red] {exc}")
        console.print(
            "\n[dim]Check that your connection string is correct and that your "
            "Eventstream Custom Endpoint has been published.[/dim]"
        )
        raise SystemExit(1)
    finally:
        sender.close()


def _detect_timestamp_field(records: list[dict]) -> Optional[str]:
    """Auto-detect a timestamp field from the first record."""
    if not records:
        return None
    common_names = ["timestamp", "event_time", "eventTime", "time", "created_at", "ts", "datetime"]
    for name in common_names:
        if name in records[0]:
            return name
    return None


def _show_next_steps(data_file: Path) -> None:
    """Display next-steps guidance."""
    console.print()
    console.print(
        Panel(
            "[bold]You're all set! Here are some things to try next:[/bold]\n\n"
            f"  [cyan]▸[/cyan] Stream this file:        [bold]rti-simulator {data_file.name}[/bold]\n"
            f"  [cyan]▸[/cyan] Stream at 10 events/sec: [bold]rti-simulator {data_file.name} --eps 10[/bold]\n"
            f"  [cyan]▸[/cyan] Loop for 5 minutes:      [bold]rti-simulator {data_file.name} --loop --duration 5m[/bold]\n"
            f"  [cyan]▸[/cyan] Use a config file:       [bold]rti-simulator --config config.yaml[/bold]\n"
            f"  [cyan]▸[/cyan] View all options:        [bold]rti-simulator --help[/bold]\n\n"
            "[dim]Tip: Copy config.example.yaml to config.yaml to save your settings for reuse.[/dim]",
            title="[bold green]Next Steps[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )
