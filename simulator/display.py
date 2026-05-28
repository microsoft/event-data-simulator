"""Rich console display for the Event Data Simulator."""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text


class SimulatorDisplay:
    """Manages all Rich console output for the simulator."""

    def __init__(self, quiet: bool = False) -> None:
        self.console = Console()
        self.quiet = quiet
        self._progress: Optional[Progress] = None
        self._task_id: Optional[Any] = None

    # ── Startup banner ───────────────────────────────────────────────────

    def show_banner(
        self,
        load_result: Any,
        config: Any,
        connection_string: str,
    ) -> None:
        """Display the startup configuration panel."""
        if self.quiet:
            return

        from simulator.sender import StreamConfig

        # Extract target from connection string
        target = _extract_target(connection_string)

        lines = [
            f"[bold]📄 File:[/bold]       {load_result.file_path.name}",
            f"[bold]📊 Records:[/bold]    {load_result.record_count:,} events loaded ({load_result.format_detected} format)",
            f"[bold]🔗 Target:[/bold]     {target}",
            f"[bold]⚡ Rate:[/bold]       {config.rate_description}",
            f"[bold]🔁 Playback:[/bold]   {config.playback_description}",
        ]

        if config.batch_size:
            lines.append(f"[bold]📦 Batch size:[/bold] {config.batch_size}")
        else:
            lines.append("[bold]📦 Batch size:[/bold] auto (1MB limit)")

        if config.timestamp_field:
            fmt_desc = config.timestamp_format or "ISO 8601"
            lines.append(f"[bold]🕐 Timestamp:[/bold]  field '{config.timestamp_field}' → {fmt_desc}")

        panel = Panel(
            "\n".join(lines),
            title="[bold blue]Event Data Simulator[/bold blue]",
            border_style="blue",
            padding=(1, 2),
        )
        self.console.print(panel)

    # ── Progress bar ─────────────────────────────────────────────────────

    @contextmanager
    def create_progress(self, total: Optional[int] = None, show: bool = True):
        """Create a Rich progress bar context manager.

        Yields (progress, task_id) tuple.
        """
        if self.quiet or not show:
            # Yield a no-op progress that silently ignores updates
            yield _NoOpProgress(), 0
            return

        columns = [
            SpinnerColumn(),
            TextColumn("[bold blue]Streaming"),
            BarColumn(bar_width=40),
        ]

        if total is not None:
            columns.append(MofNCompleteColumn())
            columns.append(TaskProgressColumn())
        else:
            columns.append(TextColumn("{task.fields[events_sent]:,} events"))

        columns.extend([
            TextColumn("•"),
            TextColumn("{task.fields[rate]:.1f} eps"),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TextColumn("{task.fields[pass_info]}"),
        ])

        progress = Progress(*columns, console=self.console, transient=False)
        task_id = progress.add_task(
            "Streaming",
            total=total,
            events_sent=0,
            rate=0.0,
            pass_info="Pass 1",
        )
        self._progress = progress
        self._task_id = task_id

        with progress:
            yield progress, task_id

        self._progress = None
        self._task_id = None

    def advance_progress(self, advance: int = 1) -> None:
        """Advance the progress bar by N events."""
        if self._progress and self._task_id is not None:
            task = self._progress.tasks[self._task_id]
            events_sent = task.fields.get("events_sent", 0) + advance
            elapsed = task.elapsed or 0.001
            rate = events_sent / elapsed if elapsed > 0 else 0.0

            self._progress.update(
                self._task_id,
                advance=advance,
                events_sent=events_sent,
                rate=rate,
            )

    # ── Verbose event display ────────────────────────────────────────────

    def show_event(self, index: int, record: dict[str, Any]) -> None:
        """Display a single event payload (verbose mode)."""
        if self.quiet:
            return
        formatted = json.dumps(record, indent=2, default=str)
        self.console.print(f"  [dim]► Event #{index + 1}:[/dim]")
        syntax = Syntax(formatted, "json", theme="monokai", line_numbers=False)
        self.console.print(syntax)

    # ── Completion summary ───────────────────────────────────────────────

    def show_summary(self, stats: Any, interrupted: bool = False) -> None:
        """Display the completion summary panel."""
        if self.quiet:
            return

        from simulator.sender import format_duration

        status = "⚠️  Interrupted (Ctrl+C)" if interrupted else "✅ Completed"

        lines = [
            f"[bold]Status:[/bold]         {status}",
            f"[bold]📨 Events sent:[/bold]  {stats.events_sent:,}",
            f"[bold]⏱️  Duration:[/bold]     {format_duration(stats.elapsed_seconds)}",
            f"[bold]📈 Average rate:[/bold] {stats.actual_eps:.1f} eps",
            f"[bold]🔁 Passes:[/bold]       {stats.passes_completed}",
            f"[bold]❌ Errors:[/bold]       {stats.events_failed}",
        ]

        if stats.errors:
            lines.append("")
            lines.append("[bold red]Error details:[/bold red]")
            for err in stats.errors[:5]:
                lines.append(f"  • {err}")
            if len(stats.errors) > 5:
                lines.append(f"  ... and {len(stats.errors) - 5} more")

        title = "[bold yellow]Simulation Interrupted[/bold yellow]" if interrupted else "[bold green]Simulation Complete[/bold green]"
        panel = Panel(
            "\n".join(lines),
            title=title,
            border_style="yellow" if interrupted else "green",
            padding=(1, 2),
        )
        self.console.print()
        self.console.print(panel)

    # ── Dry run report ───────────────────────────────────────────────────

    def show_dry_run(self, load_result: Any, config: Any) -> None:
        """Display the dry run validation report."""
        from simulator.sender import format_duration

        est_duration = "N/A"
        if config.eps and config.eps > 0:
            total_events = load_result.record_count
            if config.repeat > 0:
                total_events *= config.repeat
            est_seconds = total_events / config.eps
            est_duration = format_duration(est_seconds)
            if config.duration_seconds:
                capped = min(est_seconds, config.duration_seconds)
                est_duration = format_duration(capped)

        file_size_kb = load_result.file_size_bytes / 1024
        avg_bytes = load_result.avg_record_bytes

        lines = [
            f"[bold]📄 File:[/bold]          {load_result.file_path.name}",
            f"[bold]📊 Format:[/bold]        {load_result.format_detected}",
            f"[bold]📝 Records:[/bold]       {load_result.record_count:,}",
            f"[bold]📏 File size:[/bold]     {file_size_kb:.1f} KB",
            f"[bold]📐 Avg record:[/bold]   {avg_bytes:.0f} bytes",
            f"[bold]⏱️  Est. duration:[/bold] {est_duration} (at {config.rate_description})",
        ]

        if load_result.warnings:
            lines.append("")
            lines.append(f"[bold yellow]⚠️  Warnings ({len(load_result.warnings)}):[/bold yellow]")
            for w in load_result.warnings[:5]:
                lines.append(f"  • {w}")
            if len(load_result.warnings) > 5:
                lines.append(f"  ... and {len(load_result.warnings) - 5} more")
            lines.append("")
            lines.append(f"[green]✅ {load_result.record_count:,} valid records ready to stream[/green]")
        else:
            lines.append(f"[green]✅ All {load_result.record_count:,} records are valid JSON objects[/green]")

        panel = Panel(
            "\n".join(lines),
            title="[bold cyan]Dry Run Report[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
        self.console.print(panel)

    # ── Preview ──────────────────────────────────────────────────────────

    def show_preview(self, records: list[dict[str, Any]], n: int) -> None:
        """Display the first N events as formatted JSON."""
        show_n = min(n, len(records))
        lines: list[str] = []

        for i, record in enumerate(records[:show_n], start=1):
            lines.append(f"[bold]{i}.[/bold] {json.dumps(record, default=str)}")

        title = f"[bold cyan]Preview: first {show_n} of {len(records):,} events[/bold cyan]"
        panel = Panel(
            "\n".join(lines),
            title=title,
            border_style="cyan",
            padding=(1, 2),
        )
        self.console.print(panel)

    # ── Error / warning display ──────────────────────────────────────────

    def show_error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(f"[bold red]✖ Error:[/bold red] {message}")

    def show_warning(self, message: str) -> None:
        """Display a warning message."""
        if not self.quiet:
            self.console.print(f"[yellow]⚠ Warning:[/yellow] {message}")


class _NoOpProgress:
    """A no-op progress bar for quiet mode."""

    def add_task(self, *args: Any, **kwargs: Any) -> int:
        return 0

    def update(self, *args: Any, **kwargs: Any) -> None:
        pass

    @property
    def tasks(self) -> list:
        return []

    def __enter__(self) -> tuple:
        return self, 0

    def __exit__(self, *args: Any) -> None:
        pass


def _extract_target(connection_string: str) -> str:
    """Extract the hostname from an Event Hub connection string."""
    for part in connection_string.split(";"):
        part = part.strip()
        if part.lower().startswith("endpoint="):
            endpoint = part.split("=", 1)[1]
            # Remove protocol prefix
            endpoint = endpoint.replace("sb://", "").replace("Sb://", "")
            return endpoint.rstrip("/")
    return "unknown"
