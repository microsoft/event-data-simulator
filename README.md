# Event Data Simulator

> **Install in one command. Stream in seconds.**

Stream JSON events to **Microsoft Fabric Real-Time Intelligence (RTI) Eventstreams** and **Azure Event Hubs** — designed for Solution Engineers building custom demos.

```bash
pip install git+https://github.com/microsoft/event-data-simulator.git
rti-simulator
```

That's it. The guided wizard walks you through connecting and sending your first events.

---

## Installation

### Option 1: pip install (recommended)

```bash
pip install git+https://github.com/microsoft/event-data-simulator.git
```

This installs the `rti-simulator` command globally. You're ready to go.

### Option 2: Docker (zero Python needed)

```bash
# Launch the guided wizard
docker run -it --rm ghcr.io/microsoft/event-data-simulator

# Stream a local file
docker run -it --rm \
  -v ./my-data:/data \
  --env-file .env \
  ghcr.io/microsoft/event-data-simulator /data/events.json --eps 10 --loop
```

### Option 3: Clone for development

```bash
git clone https://github.com/microsoft/event-data-simulator.git
cd event-data-simulator
pip install -r requirements.txt
python -m simulator    # run via module
```

---

## Getting Started

### 1. Run the wizard

```bash
rti-simulator
```

Run with no arguments to launch the **guided setup wizard**. It walks you through:
1. Pasting your Eventstream connection string
2. Picking a sample dataset (finance, healthcare, retail, and more)
3. Sending a test stream to verify everything works

### 2. Or jump straight in

**Set up your connection** — create a `.env` file in your working directory:

```env
EVENT_HUB_CONNECTION_STRING=Endpoint=sb://your-namespace.servicebus.windows.net/;SharedAccessKeyName=...;SharedAccessKey=...;EntityPath=...
```

> Get this from: **Fabric → Eventstream → Custom Endpoint → Details → Event Hub tab → SAS Key Authentication → Connection string–primary key**

**Stream events:**

```bash
rti-simulator sample-data/finance.json
rti-simulator sample-data/healthcare.json --eps 10 --loop
rti-simulator sample-data/retail_commerce.json --duration 5m --timestamp-field timestamp
rti-simulator --config config.yaml
```

## Sample Datasets

The following industry-specific datasets are included for building RTI demos:

| File | Industry | Description |
|------|----------|-------------|
| `finance.json` | 💳 Finance | Credit card fraud detection events with risk scoring |
| `healthcare.json` | 🏥 Healthcare | Patient vital signs monitoring from hospital wards |
| `retail_commerce.json` | 🛒 Retail & Commerce | Point-of-sale transactions across store locations |
| `media_comms.json` | 📡 Media & Comms | Network interface traffic and throughput telemetry |
| `travel_transport.json` | 🚆 Travel & Transport | Live train departure and arrival events |
| `local_gov.json` | 🏛️ Local Government | Environmental sensor readings across council districts |

## JSON File Formats

The simulator auto-detects two formats:

**JSON Array** — a single array of objects:
```json
[
  {"id": 1, "value": 42.5, "timestamp": "2025-01-15T10:00:00Z"},
  {"id": 2, "value": 38.1, "timestamp": "2025-01-15T10:00:01Z"}
]
```

**NDJSON (Newline-Delimited JSON)** — one object per line:
```
{"id": 1, "value": 42.5, "timestamp": "2025-01-15T10:00:00Z"}
{"id": 2, "value": 38.1, "timestamp": "2025-01-15T10:00:01Z"}
```

Each JSON object becomes a separate event streamed to the Eventstream. Events are sent with `content_type: application/json` so downstream consumers (KQL, Eventstream processors, etc.) can auto-parse them.

## Configuration File

Instead of passing CLI flags every time, save your settings in a YAML file:

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with your settings, then:
rti-simulator --config config.yaml
```

**Example `config.yaml`:**

```yaml
file: sample-data/finance.json
connection_string: "Endpoint=sb://..."
eps: 10
jitter: 20
loop: true
duration: 5m
timestamp_field: timestamp
```

All CLI flags have a corresponding YAML key. CLI flags **override** config file values, so you can set defaults in the config and override one-off changes on the command line:

```bash
# Uses config.yaml settings but overrides EPS to 50
rti-simulator --config config.yaml --eps 50
```

**Configuration priority:** CLI flags > config file > `.env` file > defaults

| YAML Key | CLI Flag | Description |
|----------|----------|-------------|
| `file` | (positional) | Path to JSON data file (relative to config file) |
| `connection_string` | `--connection-string` | Event Hub / Eventstream connection string |
| `eventhub_name` | `--eventhub-name` | Event Hub name |
| `eps` | `--eps` | Events per second |
| `interval` | `--interval` | Seconds between events |
| `burst` | `--burst` | Send with no rate limit |
| `jitter` | `--jitter` | Random ±% timing variation |
| `loop` | `--loop` | Replay file continuously |
| `repeat` | `--repeat` | Number of passes |
| `duration` | `--duration` | Maximum run time |
| `timestamp_field` | `--timestamp-field` | JSON field to overwrite with current timestamp |
| `timestamp_format` | `--timestamp-format` | strftime format for injected timestamp |
| `dry_run` | `--dry-run` | Validate without sending |
| `preview` | `--preview` | Show first N events |
| `quiet` | `--quiet` | Suppress output |
| `verbose` | `--verbose` | Show event payloads |
| `no_progress` | `--no-progress` | Hide progress bar |
| `batch_size` | `--batch-size` | Max events per batch |

## CLI Reference

```
rti-simulator [FILE] [OPTIONS]
```

Run with no arguments to launch the **guided setup wizard**.

### Config File

| Flag | Description |
|------|-------------|
| `--config` | Path to a YAML configuration file. CLI flags override config values. |

### Connection Options

| Flag | Short | Description |
|------|-------|-------------|
| `--connection-string` | `-c` | Event Hub / Eventstream connection string. Overrides config file and `.env`. |
| `--eventhub-name` | `-n` | Event Hub name (only if connection string lacks `EntityPath`). |

### Rate Control

These are mutually exclusive — pick one:

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--eps` | `-e` | `1.0` | Events per second. Decimals OK (`0.5` = 1 event every 2s). |
| `--interval` | `-i` | — | Seconds between events. Alternative to `--eps`. |
| `--burst` | `-b` | off | Send as fast as possible. No rate limiting. |

Additional rate modifier:

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--jitter` | `-j` | `0` | Random ±% variation in timing (0–100). Makes the stream feel more realistic. |

### Playback & Duration

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--loop` | `-l` | off | Replay the file continuously until Ctrl+C or `--duration`. |
| `--repeat` | `-r` | `1` | Number of passes through the file. `0` = infinite (same as `--loop`). |
| `--duration` | `-d` | — | Max run time. Accepts `30s`, `5m`, `1h`, `1h30m`, or plain seconds. |

**How playback options combine:**

- Default: single pass through the file, then stop
- `--loop`: infinite replay until Ctrl+C
- `--repeat 5`: play file 5 times then stop
- `--duration 5m`: stream for 5 minutes, auto-looping if file ends early
- `--loop --duration 1h`: loop for 1 hour then stop
- `--repeat 3 --duration 10m`: 3 passes OR 10 minutes, whichever comes first

### Timestamp Injection

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--timestamp-field` | `-t` | — | JSON field name to overwrite with the current UTC timestamp on each send. |
| `--timestamp-format` | — | ISO 8601 | strftime format for the injected timestamp (e.g. `%Y-%m-%d %H:%M:%S`). |

This keeps timestamps fresh so downstream KQL queries, dashboards, and alerts see "live" data instead of stale dates from the original file.

### Output Options

| Flag | Short | Description |
|------|-------|-------------|
| `--dry-run` | — | Validate the file and show stats without sending. |
| `--preview` | `-p` | Show first N events and exit (e.g. `--preview 5`). |
| `--verbose` | `-v` | Print each event payload as it's sent. |
| `--quiet` | `-q` | Suppress all output except errors. |
| `--no-progress` | — | Hide the progress bar, keep banner and summary. |

### Advanced Options

| Flag | Description |
|------|-------------|
| `--batch-size` | Max events per Event Hub batch (default: auto, up to 1MB). |
| `--version` / `-V` | Show version and exit. |

## Examples

```bash
# Launch the guided wizard
rti-simulator

# Preview your data before sending
rti-simulator sample-data/finance.json --preview 3

# Dry run — check file validity and estimated duration
rti-simulator sample-data/healthcare.json --dry-run

# Stream at 10 eps with ±20% jitter for realistic timing
rti-simulator sample-data/finance.json --eps 10 --jitter 20

# Send one event every 2 seconds
rti-simulator sample-data/travel_transport.json --interval 2.0

# Burst-send everything (load test / seed data)
rti-simulator sample-data/retail_commerce.json --burst

# Stream for exactly 30 minutes with live timestamps, looping as needed
rti-simulator sample-data/local_gov.json --duration 30m --timestamp-field timestamp

# 3 passes at 5 eps, verbose output
rti-simulator sample-data/media_comms.json --eps 5 --repeat 3 --verbose

# Override connection string directly
rti-simulator sample-data/finance.json -c "Endpoint=sb://..."

# Quiet mode for scripting
rti-simulator sample-data/finance.json --eps 20 --loop --duration 1h --quiet
```

## Project Structure

```
event-data-simulator/
├── README.md
├── LICENSE                # MIT license
├── Dockerfile             # Docker image for zero-install usage
├── pyproject.toml
├── requirements.txt
├── config.example.yaml    # Example YAML configuration file
├── .gitignore
├── .github/
│   └── workflows/
│       └── docker-publish.yml  # CI to build/push Docker image
├── simulator/
│   ├── __init__.py        # Package version
│   ├── __main__.py        # python -m simulator fallback entry point
│   ├── cli.py             # Typer CLI with all options
│   ├── config.py          # YAML config file loader + merge logic
│   ├── loader.py          # JSON Array / NDJSON loader
│   ├── sender.py          # Event Hub sender + rate control
│   ├── display.py         # Rich progress, panels, summaries
│   └── wizard.py          # Guided first-run wizard
└── sample-data/
    ├── finance.json
    ├── healthcare.json
    ├── retail_commerce.json
    ├── media_comms.json
    ├── travel_transport.json
    └── local_gov.json
```

## Future Roadmap

- **CSV / XML support** — additional file formats
- **Web UI** — browser-based interface for non-CLI users
- **Multiple targets** — parallel streaming to multiple Eventstreams
- **PyPI publishing** — `pip install event-data-simulator` without GitHub access
