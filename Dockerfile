FROM python:3.12-slim AS base

LABEL org.opencontainers.image.source="https://github.com/microsoft/event-data-simulator"
LABEL org.opencontainers.image.description="Stream JSON events to Microsoft Fabric Eventstreams and Azure Event Hubs"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and sample data
COPY simulator/ simulator/
COPY sample-data/ sample-data/
COPY config.example.yaml .
COPY pyproject.toml .
COPY README.md .

# Install the package itself so `rti-simulator` entry point is available
RUN pip install --no-cache-dir .

ENTRYPOINT ["rti-simulator"]
