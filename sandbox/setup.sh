#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OFFLINE_NETWORK="${OFFLINE_NETWORK:-econ-internal}"
DATA_NETWORK="${DATA_NETWORK:-econ-data-internal}"
EGRESS_NETWORK="${EGRESS_NETWORK:-econ-egress}"
PROXY_OFFLINE_HOSTS="${PROXY_OFFLINE_HOSTS:-opencode.ai,models.dev,api.anthropic.com}"
PROXY_DATA_HOSTS="${PROXY_DATA_HOSTS:-api.bcb.gov.br,servicodados.ibge.gov.br,olinda.bcb.gov.br}"
PROXY_PORT="${PROXY_PORT:-3128}"

echo "building econ-agent image"
docker build -t econ-agent:latest -f "$ROOT/sandbox/Dockerfile" "$ROOT"

for net in "$OFFLINE_NETWORK" "$DATA_NETWORK"; do
  docker network inspect "$net" >/dev/null 2>&1 || docker network create --internal "$net"
done
docker network inspect "$EGRESS_NETWORK" >/dev/null 2>&1 || docker network create "$EGRESS_NETWORK"

docker rm -f econ-proxy econ-data-proxy >/dev/null 2>&1 || true

docker run -d \
  --name econ-proxy \
  --restart unless-stopped \
  --network "$EGRESS_NETWORK" \
  -e ALLOW_HOSTS="$PROXY_OFFLINE_HOSTS" \
  -e PORT="$PROXY_PORT" \
  -v "$ROOT/sandbox/proxy.py:/proxy.py:ro" \
  python:3.12-slim python /proxy.py

docker network connect "$OFFLINE_NETWORK" econ-proxy

docker run -d \
  --name econ-data-proxy \
  --restart unless-stopped \
  --network "$EGRESS_NETWORK" \
  -e ALLOW_HOSTS="$PROXY_DATA_HOSTS" \
  -e PORT="$PROXY_PORT" \
  -v "$ROOT/sandbox/proxy.py:/proxy.py:ro" \
  python:3.12-slim python /proxy.py

docker network connect "$DATA_NETWORK" econ-data-proxy

echo "networks: $OFFLINE_NETWORK (internal), $DATA_NETWORK (internal), $EGRESS_NETWORK"
echo "proxies: econ-proxy -> $PROXY_OFFLINE_HOSTS; econ-data-proxy -> $PROXY_DATA_HOSTS"
docker ps --filter name=econ-proxy --filter name=econ-data-proxy --format '{{.Names}} {{.Status}}'
