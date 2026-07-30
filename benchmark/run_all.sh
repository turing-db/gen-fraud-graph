#!/bin/bash
# Convenience wrapper: run the benchmark against all three engines and print a
# side-by-side comparison. Assumes TuringDB (6667), Neo4j (7687) and Memgraph
# (7688) are all running with the same graph loaded.
set -euo pipefail
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
python benchmark.py --engine all --neo4j-password "$NEO4J_PASSWORD" "$@"
