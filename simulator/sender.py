"""Event Hub / Eventstream sender with rate control and batching."""

from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from azure.eventhub import EventData, EventHubProducerClient
from azure.eventhub.exceptions import EventHubError


@dataclass
class StreamConfig:
    """Configuration for the streaming session."""

    eps: Optional[float] = 1.0      # None = burst (no limit)
    burst: bool = False
    jitter: float = 0.0             # 0–100 percentage
    repeat: int = 1                 # 0 = infinite
    duration_seconds: Optional[float] = None
    batch_size: Optional[int] = None
    verbose: bool = False
    timestamp_field: Optional[str] = None
    timestamp_format: Optional[str] = None  # None = ISO 8601

    _DEFAULT_TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

    def format_timestamp(self) -> str:
        """Return the current UTC timestamp in the configured format."""
        fmt = self.timestamp_format or self._DEFAULT_TS_FORMAT
        return datetime.now(timezone.utc).strftime(fmt)

    @property
    def interval(self) -> Optional[float]:
        """Seconds between events. None if burst mode."""
        if self.burst or self.eps is None:
            return None
        return 1.0 / self.eps

    def jittered_interval(self) -> Optional[float]:
        """Return the interval with random jitter applied."""
        base = self.interval
        if base is None or self.jitter <= 0:
            return base
        factor = 1.0 + random.uniform(-self.jitter, self.jitter) / 100.0
        return max(0.0, base * factor)

    @property
    def rate_description(self) -> str:
        if self.burst:
            return "burst (no limit)"
        if self.eps is not None:
            desc = f"{self.eps:.1f} events/sec"
            if self.jitter > 0:
                desc += f" (jitter: ±{self.jitter:.0f}%)"
            return desc
        return "unknown"

    @property
    def playback_description(self) -> str:
        parts: list[str] = []
        if self.repeat == 0:
            parts.append("loop forever")
        elif self.repeat == 1:
            parts.append("single pass")
        else:
            parts.append(f"{self.repeat} passes")
        if self.duration_seconds is not None:
            parts.append(f"max {format_duration(self.duration_seconds)}")
        return ", ".join(parts)


@dataclass
class StreamStats:
    """Statistics from a streaming session."""

    events_sent: int = 0
    events_failed: int = 0
    passes_completed: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time if self.end_time else time.time()
        return max(0.0, end - self.start_time)

    @property
    def actual_eps(self) -> float:
        elapsed = self.elapsed_seconds
        if elapsed <= 0:
            return 0.0
        return self.events_sent / elapsed


def format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    if minutes < 60:
        return f"{minutes}m{secs:02d}s" if secs else f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins:
        return f"{hours}h{mins:02d}m"
    return f"{hours}h"


class EventSender:
    """Sends events to an Event Hub / Eventstream Custom Endpoint.

    Events are sent as JSON with content_type='application/json' per
    the MS Learn EventData documentation (RFC2045 Section 5).
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0  # seconds

    def __init__(
        self,
        connection_string: str,
        eventhub_name: Optional[str] = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if eventhub_name:
            kwargs["eventhub_name"] = eventhub_name

        self._producer = EventHubProducerClient.from_connection_string(
            conn_str=connection_string,
            **kwargs,
        )
        self._stats = StreamStats()
        self._stopped = False

    def close(self) -> None:
        """Close the producer client."""
        try:
            self._producer.close()
        except Exception:
            pass

    def get_stats(self) -> StreamStats:
        """Return current streaming statistics."""
        if self._stats.end_time == 0.0 and self._stats.start_time > 0:
            self._stats.end_time = time.time()
        return self._stats

    def stream(
        self,
        records: list[dict[str, Any]],
        config: StreamConfig,
        display: Any,
        show_progress: bool = True,
    ) -> StreamStats:
        """Stream records to Event Hub with rate control and batching."""
        from simulator.display import SimulatorDisplay

        display: SimulatorDisplay = display
        self._stats = StreamStats(start_time=time.time())
        self._stopped = False

        is_infinite = config.repeat == 0
        total_events = None if is_infinite else len(records) * config.repeat
        deadline = (
            time.time() + config.duration_seconds
            if config.duration_seconds
            else None
        )

        pass_num = 0
        progress_ctx = display.create_progress(total=total_events, show=show_progress)

        with progress_ctx as progress_info:
            progress, task_id = progress_info

            try:
                while not self._stopped:
                    # Check repeat limit
                    if not is_infinite and pass_num >= config.repeat:
                        break

                    pass_num += 1
                    self._stream_pass(
                        records=records,
                        config=config,
                        display=display,
                        progress=progress,
                        task_id=task_id,
                        pass_num=pass_num,
                        deadline=deadline,
                    )
                    self._stats.passes_completed += 1

                    # Check deadline after each pass
                    if deadline and time.time() >= deadline:
                        break

            except KeyboardInterrupt:
                self._stopped = True
                raise
            finally:
                self._stats.end_time = time.time()

        return self._stats

    def _stream_pass(
        self,
        records: list[dict[str, Any]],
        config: StreamConfig,
        display: Any,
        progress: Any,
        task_id: Any,
        pass_num: int,
        deadline: Optional[float],
    ) -> None:
        """Stream one complete pass through the records."""
        batch = self._producer.create_batch()
        batch_count = 0

        progress.update(task_id, pass_info=f"Pass {pass_num}")

        for i, record in enumerate(records):
            if self._stopped:
                break

            # Check deadline
            if deadline and time.time() >= deadline:
                self._stopped = True
                break

            # Inject current timestamp if configured
            if config.timestamp_field:
                record = {**record, config.timestamp_field: config.format_timestamp()}

            event_data = EventData(json.dumps(record, default=str).encode("utf-8"))
            event_data.content_type = "application/json"

            try:
                batch.add(event_data)
                batch_count += 1
            except ValueError:
                # Batch is full — send it, then start new batch
                if batch_count > 0:
                    self._send_batch_with_retry(batch, config, display)
                batch = self._producer.create_batch()
                try:
                    batch.add(event_data)
                    batch_count = 1
                except ValueError:
                    # Single event exceeds batch size limit
                    self._stats.events_failed += 1
                    self._stats.errors.append(
                        f"Event {i} exceeds max batch size — skipped."
                    )
                    display.show_warning(f"Event {i} too large — skipped.")
                    continue

            # Check if we've hit the batch size limit
            send_now = config.batch_size and batch_count >= config.batch_size

            # In non-burst mode, send after each event for rate control
            if not config.burst and not send_now:
                send_now = True

            if send_now and batch_count > 0:
                self._send_batch_with_retry(batch, config, display)
                batch = self._producer.create_batch()
                batch_count = 0

                # Rate limiting (non-burst mode)
                if not config.burst:
                    sleep_time = config.jittered_interval()
                    if sleep_time and sleep_time > 0:
                        time.sleep(sleep_time)

            # Show verbose output
            if config.verbose:
                display.show_event(i, record)

        # Flush remaining batch
        if batch_count > 0:
            self._send_batch_with_retry(batch, config, display)

    def _send_batch_with_retry(
        self,
        batch: Any,
        config: StreamConfig,
        display: Any,
    ) -> None:
        """Send a batch with exponential backoff retry."""
        event_count = len(batch)

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self._producer.send_batch(batch)
                self._stats.events_sent += event_count
                display.advance_progress(event_count)
                return
            except EventHubError as exc:
                if attempt < self.MAX_RETRIES:
                    delay = self.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    display.show_warning(
                        f"Send failed (attempt {attempt}/{self.MAX_RETRIES}): {exc}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    self._stats.events_failed += event_count
                    self._stats.errors.append(f"Batch send failed after {self.MAX_RETRIES} attempts: {exc}")
                    display.show_error(f"Batch send failed: {exc}")
