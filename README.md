# gen_fraud_graph

> Synthetic fraud graph generator for training and benchmarking graph-based fraud detection models in financial services.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/gen-fraud-graph.svg)](https://pypi.org/project/gen-fraud-graph/)
[![CI](https://github.com/SantanderAI/gen-fraud-graph/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SantanderAI/gen-fraud-graph/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/SantanderAI/gen-fraud-graph/branch/main/graph/badge.svg)](https://codecov.io/gh/SantanderAI/gen-fraud-graph)
[![CodeQL](https://github.com/SantanderAI/gen-fraud-graph/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/SantanderAI/gen-fraud-graph/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/SantanderAI/gen-fraud-graph/badge)](https://scorecard.dev/viewer/?uri=github.com/SantanderAI/gen-fraud-graph)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://conventionalcommits.org)
[![GitHub last commit](https://img.shields.io/github/last-commit/SantanderAI/gen-fraud-graph)](https://github.com/SantanderAI/gen-fraud-graph/commits/main)

---

## Overview

**gen_fraud_graph** is an open-source Python tool that generates massive synthetic financial transaction graphs with injected fraud patterns and optional vector embeddings. It produces CSV datasets ready for ingestion into graph databases (TigerGraph, Neptune, Neo4j, JanusGraph) or for training graph neural networks (GNN).

The generator creates three types of data:
- **Account nodes** — synthetic customer accounts with balance, risk score, and optional embedding vectors
- **Transaction edges** — normal financial transactions between accounts
- **Fraud rings** — cyclic money-laundering patterns with suspicious transaction descriptions

### Key Features

- **Massive scale** — Generate from 1K to 100M+ accounts with configurable scale factor
- **Fraud pattern injection** — Cyclic money-laundering rings with configurable depth (4–7 hops)
- **Parallel generation** — Multi-process workers for fast generation on high-core machines
- **Vector embeddings** — Three providers: `fake` (random, fast), `local` (SentenceTransformers), `openai` (API)
- **Multiple formats** — Generic CSV, AWS Neptune bulk-load, or TuringDB-style Parquet format
- **Resume support** — Interrupted generation can resume from where it left off
- **Privacy by design** — All data is 100% synthetic; no real financial data is used

### Use Cases

- Training and evaluating **graph neural networks (GNN)** for fraud detection
- Benchmarking **anti-money laundering (AML)** detection algorithms
- Load-testing graph databases (TigerGraph, Neptune, JanusGraph, NebulaGraph, FalkorDB)
- Research in **financial crime detection** and **anomaly detection** on graphs
- Generating labeled datasets for **deep learning** on graph-structured data

---

## Quick Start

### Installation

> **Note:** `gen-fraud-graph` is not yet published to PyPI, so `pip install gen-fraud-graph` will fail with `No matching distribution found`. Until the first PyPI release, install from source as shown below. The PyPI badge above is pre-provisioned for the planned release.

Install from source using [uv](https://github.com/astral-sh/uv):
```bash
git clone https://github.com/SantanderAI/gen-fraud-graph.git
cd gen-fraud-graph
uv venv && source .venv/bin/activate
uv pip install -e '.[dev]'
```

With optional embedding providers (from the cloned source directory):
```bash
uv pip install -e '.[local]'    # SentenceTransformers (local model)
uv pip install -e '.[openai]'   # OpenAI API embeddings
uv pip install -e '.[all]'      # Everything including dev tools
```

If you prefer plain `pip` over `uv`, the source install works the same way:
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Once the package is published, `pip install gen-fraud-graph` will be the recommended path.

### CLI Usage

```bash
# Quick test (~1K accounts, ~9K transactions, fake embeddings)
gen-fraud-graph --scale 0.0001 --provider fake --output ./data

# Medium scale (~100K accounts, parallelized)
gen-fraud-graph --scale 0.01 --workers 4 --output ./data

# Full benchmark (~10M accounts, ~90M transactions)
gen-fraud-graph --scale 1.0 --workers 24 --output ./data

# Neptune bulk-load format
gen-fraud-graph --scale 0.01 --format neptune --output ./neptune_data

# TuringDB-style Parquet graph format
gen-fraud-graph --scale 0.01 --format parquet --output ./parquet_data

# Resume interrupted generation (skips completed files)
gen-fraud-graph --scale 1.0 --workers 24 --skip-accounts --output ./data
```

### CLI Arguments

| Flag | Default | Description |
|:---|:---|:---|
| `--scale` | `1.0` | Scale factor. `1.0` = ~10M accounts / ~90M transactions. `0.01` = ~100K accounts. |
| `--provider` | `fake` | Embedding provider: `fake` (random vectors), `local` (SentenceTransformers), `openai`. |
| `--output` | `data` | Output directory for generated CSV files. |
| `--workers` | `1` | Number of parallel worker processes. |
| `--batches` | `1` | Number of file chunks per worker. |
| `--format` | `csv` | Output format: `csv` (generic), `neptune` (AWS Neptune bulk-load), or `parquet` (TuringDB-style graph files). |
| `--fraud-rings` | auto | Number of fraud rings. Default: auto-scaled from `--scale`. |
| `--compress` | off | ZIP-compress output CSV files. |
| `--skip-accounts` | off | Skip account generation (useful when resuming). |

### Python API

```python
# Copyright (c) 2026 Santander Group
# SPDX-License-Identifier: Apache-2.0

from gen_fraud_graph import Config, FraudGraphGenerator

config = Config(
    scale_factor=0.001,         # ~10K accounts, ~90K transactions
    num_fraud_rings=50,         # 50 cyclic fraud patterns
    embedding_provider="fake",  # random vectors (fast, no model needed)
    workers=2,                  # 2 parallel processes
    output_dir="./output",
)

generator = FraudGraphGenerator(config)
generator.run()
```

### Verify Generated Patterns

```bash
python -m gen_fraud_graph.verify --data-dir ./data
```

---

## Output Structure

```
data/
├── accounts/
│   ├── accounts_0_0.csv       # Account nodes (CSV/Neptune output)
│   └── accounts_1_0.csv
├── transactions/
│   ├── transactions_0_0.csv   # Transaction edges (CSV/Neptune output)
│   └── transactions_1_0.csv
└── fraud/
    ├── transactions_fraud.csv  # Fraud ring transaction edges (CSV/Neptune output)
    └── fraud_cases.csv         # Fraud ring metadata (pattern_id, accounts, depth)

parquet_data/
├── graph/
│   ├── nodes_0_0.parquet       # TuringDB node table: id, label, properties
│   ├── edges_0_0.parquet       # TuringDB edge table: from, to, relation, properties
│   └── edges_fraud.parquet     # Fraud transaction edges
├── embeddings/
│   └── account_embeddings_0_0.parquet
└── fraud/
    └── fraud_cases.parquet
```

### CSV Schema

**accounts** (`accounts_*.csv`)

| Column | Type | Description |
|:---|:---|:---|
| `account_id` | string | Unique account identifier (`acc_0`, `acc_1`, ...) |
| `customer_name` | string | Synthetic customer name |
| `balance` | float | Account balance (100 – 100,000) |
| `risk_score` | float | Risk score (0.0 – 1.0) |
| `creation_date` | string | Account creation date |

**transactions** (`transactions_*.csv`)

| Column | Type | Description |
|:---|:---|:---|
| `tx_id` | string | Unique transaction identifier |
| `src_id` | string | Source account |
| `dst_id` | string | Destination account |
| `amount` | float | Transaction amount (10 – 500 for normal, 9999 for fraud) |
| `timestamp` | string | Transaction timestamp |
| `description` | string | Transaction description |
| `embedding` | string | Pipe-separated embedding vector |

**fraud_cases** (`fraud/fraud_cases.csv`)

| Column | Type | Description |
|:---|:---|:---|
| `pattern_id` | string | Pattern identifier (`pat_0`, `pat_1`, ...) |
| `start_acc_id` | string | First account in the ring |
| `pattern_type` | string | Always `"cycle"` |
| `depth` | int | Number of hops in the ring (4–7) |
| `involved_accounts` | string | Pipe-separated list of accounts |

**Parquet graph files** (`--format parquet`)

Parquet output follows the split graph table shape expected by TuringDB's `LOAD PARQUET` importer. At the end of a Parquet run, generated shards are automatically compacted to top-level `nodes.parquet` and `edges.parquet` files.

**Parquet node schema**

| Column | Type | Description |
|:---|:---|:---|
| `__id` | `int64` | Internal ascending graph node id used by edges. |
| `__labels` | `list<binary>` | Always `Account`. |
| `account_id` | `uint64` | Original account number, e.g. `42` for `acc_42`. |
| `customer_name` | `string` | Synthetic customer name. |
| `balance` | `float64` | Account balance. |
| `risk_score` | `float64` | Risk score. |
| `creation_date` | `string` | Account creation date. |

**Parquet edge schema**

| Column | Type | Description |
|:---|:---|:---|
| `__source` | `int64` | Source node `__id`. |
| `__target` | `int64` | Target node `__id`. |
| `__type` | `binary` | Always `TRANSFER`. |
| `tx_id` | `int64` | Transaction id. |
| `amount` | `float64` | Transaction amount. |
| `timestamp` | `string` | Transaction timestamp. |
| `description` | `string` | Transaction description. |
| `is_fraud` | `bool` | `true` for fraud edges. |

| File | Key columns | Notes |
|:---|:---|:---|
| `nodes.parquet` | `__id`, `__labels`, `account_id` | Compacted account nodes for `LOAD PARQUET`. |
| `edges.parquet` | `__source`, `__target`, `__type` | Compacted normal and fraud edges for `LOAD PARQUET`. |
| `graph/nodes_*.parquet` | `__id`, `__labels`, `account_id` | Intermediate account node shards. |
| `graph/edges_*.parquet` | `__source`, `__target`, `__type` | Intermediate normal and fraud edge shards. |
| `embeddings/account_embeddings_*.parquet` | `node_id`, `embedding` | Raw float32 embedding bytes stored as fixed-width binary for `LOAD EMBEDDING`; compact to one file if needed. |
| `fraud/fraud_cases.parquet` | `pattern_id`, `start_acc_id`, `depth`, `involved_accounts` | Fraud ring metadata sidecar. |

A TuringDB import directory should live under the TuringDB data directory and contain exactly:

```text
.turing/data/gen_fraud_graph_1m/
├── nodes.parquet
└── edges.parquet
```

Then import with:

```cypher
LOAD PARQUET 'gen_fraud_graph_1m' AS gen_fraud_graph_1m
```

---

## Scale Reference

| Scale | Accounts | Transactions | Fraud Rings | Approx. Size |
|:---|:---|:---|:---|:---|
| `0.0001` | 1,000 | 9,000 | 10 | ~2 MB |
| `0.001` | 10,000 | 90,000 | 10 | ~20 MB |
| `0.01` | 100,000 | 900,000 | 10 | ~200 MB |
| `0.1` | 1,000,000 | 9,000,000 | 100 | ~2 GB |
| `1.0` | 10,000,000 | 90,000,000 | 1,000 | ~20 GB |

---

## Benchmarks

Cold query latency for the whole-graph fraud-detection queries on the `0.1` graph
(~1M accounts / ~9M transactions), in milliseconds (ms) — lower is better.
Reproduce with [`benchmark/`](benchmark/) (TuringDB vs Neo4j vs Memgraph, cold and index-free).

| Query | Result | TuringDB (ms) | Memgraph (ms) | Neo4j (ms) | Speedup vs Memgraph | Speedup vs Neo4j |
|:---|--:|--:|--:|--:|--:|--:|
| 2-hop fraud chain     | 549 | 169 | 3,207 | 5,765 | 19.0× | 34.1× |
| 3-hop fraud chain     | 549 | 170 | 3,184 | 6,307 | 18.7× | 37.1× |
| 4-hop fraud chain     | 549 | 171 | 3,183 | 6,272 | 18.6× | 36.7× |
| 2-hop into high-risk  | 543 | 175 | 3,487 | 5,904 | 19.9× | 33.7× |
| High-amount aggregate | 549 | 173 | 3,171 | 5,562 | 18.3× | 32.2× |

---

## Project Structure

```
gen_fraud_graph/
├── src/gen_fraud_graph/
│   ├── __init__.py       # Package entry point
│   ├── cli.py            # CLI (gen-fraud-graph command)
│   ├── config.py         # Configuration dataclass
│   ├── embeddings.py     # Embedding providers (fake/local/openai)
│   ├── exporters.py      # CSV/ZIP output writers
│   ├── generator.py      # Core 3-phase pipeline orchestrator
│   ├── typologies.py     # Fraud ring generator
│   └── verify.py         # Pattern verification utility
├── tests/
│   └── test_generator.py # Unit and integration tests
├── examples/
│   └── basic_usage.py    # Minimal Python API example
├── .github/
│   ├── workflows/        # CI (ci, codeql, dep-scan, license-check,
│   │                     #     pattern-check, cla, stale, release)
│   ├── ISSUE_TEMPLATE/   # Bug + feature templates
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── dependabot.yml    # Weekly Python + Actions updates
│   └── pattern-check-allowlist.txt
├── pyproject.toml        # Package metadata and tool config
├── LICENSE               # Apache 2.0
├── NOTICE                # Apache 2.0 attribution
├── CONTRIBUTING.md       # Contribution guidelines
├── CODE_OF_CONDUCT.md    # Contributor Covenant v2.1
├── SECURITY.md           # Vulnerability disclosure policy
├── CODEOWNERS            # Maintainer approvals
└── CHANGELOG.md          # Release history
```

---

## Requirements

Core (always installed):
- Python >= 3.10
- NumPy >= 1.24
- Pandas >= 2.0
- tqdm >= 4.65
- PyArrow >= 15.0

Optional:
- `sentence-transformers >= 2.2` — for `--provider local`
- `openai >= 1.0` — for `--provider openai`

---

## Contributing

We welcome contributions from the community. Please read our [CONTRIBUTING.md](CONTRIBUTING.md) before submitting a pull request.

By contributing, you agree to the terms of our Contributor License Agreement (CLA).

---

## Security

To report a security vulnerability, please follow the process described in [SECURITY.md](SECURITY.md). **Do not open a public issue for security vulnerabilities.**

---

## Disclaimer

This software is an open source project from the **Santander AI Lab**, provided **"as is"** under its [license](LICENSE), without warranties or conditions of any kind. It is **not an official Banco Santander product or service**, carries no commitment of production support, and does not constitute financial, legal or professional advice.

"Santander" and its logo are registered trademarks of **Banco Santander, S.A.** The project license does not grant any right to use them beyond factual attribution.

If you believe you have found a security vulnerability, follow our [security policy](https://github.com/SantanderAI/.github/blob/main/SECURITY.md) — do not open a public issue. You are responsible for assessing the suitability of this software for your use case and for keeping your own deployments up to date.

## License

This project is licensed under the Apache License 2.0 — see the [LICENSE](LICENSE) file for details.

```
Copyright (c) 2026 Santander Group
SPDX-License-Identifier: Apache-2.0
```

---

## Citation

If you use this tool in your research, please cite:

```bibtex
@software{gen_fraud_graph,
  title     = {gen\_fraud\_graph: Synthetic Fraud Graph Generator},
  author    = {Santander AI Lab},
  year      = {2026},
  url       = {https://github.com/SantanderAI/gen-fraud-graph},
  license   = {Apache-2.0}
}
```

---

<!-- GitHub repository metadata (for reference — configured via GitHub UI/API):
  description: "Synthetic fraud graph generator for benchmarking graph-based fraud detection models"
  topics: machine-learning, artificial-intelligence, fraud-detection, graph-neural-network,
          deep-learning, synthetic-data, financial-crime, anti-money-laundering, gnn,
          anomaly-detection, finance, python
  visibility: public
  license: Apache-2.0
  custom_properties:
    category: tool
    track: fast
    status: active
    team: ai-labs
-->
