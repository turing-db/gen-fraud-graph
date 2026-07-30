# Fraud-graph multi-hop benchmark — TuringDB vs Neo4j vs Memgraph

A small, reproducible benchmark that runs an identical set of fraud-detection
Cypher queries against **TuringDB**, **Neo4j** and **Memgraph** on the same
synthetic transaction graph, and reports per-query latency.

The workload is deep multi-hop traversal — the pattern that dominates real
transaction-fraud detection (chains of transfers, high-risk fan-out) and the one
that stresses a graph engine's traversal path rather than its indexes.

## The graph

Generated with [`turing-db/gen-fraud-graph`](https://github.com/turing-db/gen-fraud-graph):
a directed transaction graph of `:Account` nodes connected by `:TRANSFER` edges.

Relevant properties:

| Element | Property | Notes |
|---|---|---|
| `:Account` | `account_id` | unique id used to seed the fan-out queries |
| `:Account` | `risk_score` | 0–1, used by the high-risk query |
| `:TRANSFER` | `amount` | transfer amount |
| `:TRANSFER` | `is_fraud` | boolean, marks edges in a fraud typology |

The reference runs used a ~1M-account / ~9M-transfer graph (`fraud_1m`).

## The queries

All nine queries are plain openCypher and **byte-for-byte identical across the
three engines** (see `benchmark.py`):

1–4. `N`-hop fan-out from a seed account (`account_id`), N = 1..4
5–7. `N`-hop **fraud chains** over the whole graph (`is_fraud = true` on every edge), N = 2..4
8. 2-hop into high-risk accounts (`amount > 9000` and `risk_score > 0.9`)
9. high-amount transfer aggregate (`amount > 9000`)

## Benchmarks

Cold query latency for the whole-graph fraud-detection queries, in milliseconds
(ms) — lower is better.

| Query | Result | TuringDB (ms) | Memgraph (ms) | Neo4j (ms) | Speedup vs Memgraph | Speedup vs Neo4j |
|:---|--:|--:|--:|--:|--:|--:|
| 2-hop fraud chain     | 549 | 169 | 3,207 | 5,765 | 19.0× | 34.1× |
| 3-hop fraud chain     | 549 | 170 | 3,184 | 6,307 | 18.7× | 37.1× |
| 4-hop fraud chain     | 549 | 171 | 3,183 | 6,272 | 18.6× | 36.7× |
| 2-hop into high-risk  | 543 | 175 | 3,487 | 5,904 | 19.9× | 33.7× |
| High-amount aggregate | 549 | 173 | 3,171 | 5,562 | 18.3× | 32.2× |

## Setup

### 1. Generate the data

The generator is this repo's own `gen-fraud-graph` CLI. Install it from the
repository root:

```bash
pip install -e .          # run from the gen-fraud-graph repo root
```

It emits several formats via `--format`. Generate **parquet for TuringDB** and
**CSV for Neo4j / Memgraph** at the *same* `--scale` so all three engines get an
identical graph:

```bash
# TuringDB-style parquet graph files (nodes.parquet / edges.parquet + chunks)
gen-fraud-graph --scale 0.1 --format parquet --output ./fraud_1m_parquet

# generic CSV (nodes.csv / edges.csv) for Neo4j & Memgraph LOAD CSV
gen-fraud-graph --scale 0.1 --format csv     --output ./fraud_1m_csv
```

`--scale 0.1` produces the ~1M-account / ~9M-transfer graph (`fraud_1m`) used for
the reference runs. Run `gen-fraud-graph -h` for the full list; the flags that
matter here:

| Flag | Default | Meaning |
|---|---|---|
| `--scale` | `1.0` | dataset size. `1.0` ≈ 10M accounts / 90M transactions; `0.1` ≈ 1M; `0.01` ≈ 100K |
| `--format` | `csv` | `csv` (generic), `parquet` (TuringDB-style graph files), or `neptune` (AWS Neptune bulk-load) |
| `--output` | `data` | output directory |
| `--fraud-rings` | auto | number of fraud rings to inject (these create the `is_fraud = true` edges the fraud queries match) |
| `--workers` / `--batches` | `1` / `1` | parallel worker processes / file chunks per worker (speeds up large scales) |
| `--provider` | `fake` | embedding provider (`fake` = random vectors, no deps) |
| `--compress` | off | ZIP-compress the CSV output |

Both formats contain the same nodes/edges and the same `account_id`, `risk_score`,
`amount` and `is_fraud` properties, so the queries and result counts match across
engines.

### 2. Load into each engine

- **TuringDB** — load the parquet directly: `LOAD PARQUET './fraud_1m_parquet' AS fraud_1m` (or via the Python client).
- **Neo4j** (community) — import `./fraud_1m_csv/nodes.csv` / `edges.csv` with `neo4j-admin database import` or `LOAD CSV`.
- **Memgraph** — import the same `./fraud_1m_csv` files with `LOAD CSV`.

> For a *fair* comparison, load identical nodes/edges/properties into all three and
> apply the **same** indexing policy (the reference runs used **no** secondary
> indexes on any engine, so every query exercises traversal, not index lookup).

### 3. Start the engines
```bash
# TuringDB (HTTP, default port 6667)
turingdb start -turing-dir ./turing-data -p 6667 -load fraud_1m -demon

# Neo4j (Bolt 7687) — start your neo4j-community install
neo4j-community-*/bin/neo4j console

# Memgraph (Bolt 7688) — see memgraph/start_memgraph.sh
bash memgraph/start_memgraph.sh
```

## Run

The benchmark runs **cold and index-free by default** (no warmup, plan caches
defeated — see below).

```bash
pip install -r requirements.txt

# one engine at a time
python benchmark.py --engine turingdb
python benchmark.py --engine neo4j    --neo4j-password <your-password>
python benchmark.py --engine memgraph

# or all three + side-by-side comparison tables
python benchmark.py --engine all --neo4j-password <your-password>
# (or: NEO4J_PASSWORD=<pw> ./run_all.sh)
```

Options: `--seed` (see below), `--reps` (timed repetitions, default 5; rep 1 is
the cold run), `--warmup` (default `0` = cold), `--no-replan` (keep Neo4j's plan
cache), `--graph`, `--turingdb-host`, `--neo4j-uri`, `--memgraph-uri`. Run
`python benchmark.py -h` for all flags.

### Seed account

Queries 1–4 fan out from a single seed account. Since `account_id`s differ from
one generated dataset to the next, the seed is **auto-detected by default** — the
script picks an account that sends a fraudulent transfer (so it has deep outgoing
paths). Pin a specific account with `--seed <account_id>`:

```bash
python benchmark.py --engine all --seed 292362
```

When several engines are benchmarked together (`--engine all`), the seed resolved
from the first engine is reused for the others, so the seeded queries are
identical across engines. The five whole-graph fraud-detection queries (5–9) do
not depend on the seed.

## Cold / no-index methodology

The point of the benchmark is raw traversal speed, so caches and indexes are
removed on every engine:

- **No indexes.** Load the same nodes/edges/properties into all three engines
  **without creating any secondary index**, so each query traverses rather than
  looks up.
- **No warmup.** `--warmup 0` (default); the first timed run is reported as the
  cold latency.
- **No plan-cache reuse.** Neo4j queries are prefixed with `CYPHER replan=force`;
  Memgraph is started with `--query-plan-cache-max-size=0`
  (`memgraph/start_memgraph.sh`); TuringDB has no plan cache.

For every query the script reports:

- **cold_ms** — the first timed run (true cold, no warmup).
- **server_ms** — the engine's own reported execution time
  (TuringDB: `get_query_exec_time()`; Bolt engines: `result_available_after +
  result_consumed_after`, 1 ms granularity).
- **wall_ms** — client-side wall time, including protocol + client overhead
  (measured over localhost).

Neo4j and Memgraph share the Bolt driver path, so their client overhead is
directly comparable; TuringDB's HTTP + pandas overhead shows up as the gap
between its `server_ms` and `wall_ms`.

Result counts are printed alongside latencies — they should match across engines
(a quick correctness check that the same graph is loaded everywhere).

## License

Part of `gen-fraud-graph`; licensed under Apache-2.0 (see the repository `LICENSE`).
