#!/bin/bash
# Start Memgraph on Bolt port 7688 with the query plan cache disabled and
# properties-on-edges enabled (needed for the amount/is_fraud edge properties).
set -euo pipefail
MG="${MEMGRAPH_BIN:-$HOME/memgraph-bench/extracted/usr/lib/memgraph/memgraph}"
DATA="${MEMGRAPH_DATA:-$HOME/memgraph-bench/data}"
mkdir -p "$DATA"
exec "$MG" \
  --bolt-port=7688 \
  --data-directory="$DATA" \
  --log-file="$DATA/../mg.log" \
  --telemetry-enabled=false \
  --query-plan-cache-max-size=0 \
  --storage-properties-on-edges=true
