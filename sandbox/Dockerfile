FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/econ
COPY pyproject.toml ./
COPY catalog.yaml ./
COPY data/reference ./data/reference
COPY src ./src
RUN pip install --no-cache-dir -e ".[dev]"

RUN (useradd -u 1000 -m econ || true)
USER 1000:1000
WORKDIR /workspace

CMD ["python", "-c", "print('econ-agent ready')"]
