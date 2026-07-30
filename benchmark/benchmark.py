#!/usr/bin/env python3
"""
Cold multi-hop fraud-detection benchmark across TuringDB, Neo4j and Memgraph.

Runs an identical set of fraud-detection Cypher queries against each engine on the
same synthetic transaction graph (generated with turing-db/gen-fraud-graph) and
reports per-query latency.

The benchmark is deliberately **cold and index-free**:

  * No warmup runs (``--warmup 0`` by default) — the first timed run is reported
    as the cold latency.
  * No secondary indexes on any engine (this is a *loading*-time choice; load the
    same nodes/edges/properties into all three engines without creating indexes,
    so every query exercises traversal rather than an index lookup).
  * Query-plan caching is defeated: Neo4j queries are prefixed with
    ``CYPHER replan=force``; Memgraph is started with
    ``--query-plan-cache-max-size=0`` (see ``memgraph/start_memgraph.sh``);
    TuringDB has no plan cache.

The seed account for the fan-out queries is **auto-detected** from the dataset
(an account that sends a fraudulent transfer, so it has deep outgoing paths).
Pass ``--seed <account_id>`` to pin a specific account instead. When benchmarking
several engines at once, the seed resolved from the first engine is reused for
the rest so the seeded queries are identical everywhere.

Neo4j and Memgraph both speak the Bolt protocol, so they share a single client
path (the official ``neo4j`` Python driver). TuringDB is queried over its HTTP
API via the ``turingdb`` client. The queries are plain openCypher and identical
across all three engines (only the Neo4j ``replan=force`` prefix differs).

Examples:
    python benchmark.py --engine turingdb
    python benchmark.py --engine neo4j    --neo4j-password secret
    python benchmark.py --engine memgraph
    python benchmark.py --engine all      --neo4j-password secret
    python benchmark.py --engine all      --seed 292362

See README.md for data generation, loading and engine-startup instructions.
"""
import argparse
import statistics
import time
import warnings

warnings.filterwarnings("ignore")

# Picks a seed account that sends a fraudulent transfer (guaranteed deep outgoing
# paths). Standard openCypher, works on all three engines.
SEED_QUERY = ("MATCH (a:Account)-[t:TRANSFER]->() WHERE t.is_fraud = true "
              "RETURN a.account_id AS id LIMIT 1")
# Fallback if the dataset somehow has no fraud edges: any account with an outgoing transfer.
SEED_QUERY_FALLBACK = "MATCH (a:Account)-[:TRANSFER]->() RETURN a.account_id AS id LIMIT 1"


def build_queries(seed):
    """Fraud-detection query set for a given seed account_id. Identical openCypher
    across all engines. Queries 1-4 fan out from the seed; 5-9 are whole-graph
    fraud-detection scans (independent of the seed)."""
    return [
        ("1-hop from seed",
         f"MATCH (a:Account {{account_id: {seed}}})-[t1:TRANSFER]->(b) "
         "RETURN count(b) AS c"),
        ("2-hop from seed",
         f"MATCH (a:Account {{account_id: {seed}}})-[t1:TRANSFER]->(b)-[t2:TRANSFER]->(d) "
         "RETURN count(d) AS c"),
        ("3-hop from seed",
         f"MATCH (a:Account {{account_id: {seed}}})-[t1:TRANSFER]->(b)-[t2:TRANSFER]->(d)-[t3:TRANSFER]->(e) "
         "RETURN count(e) AS c"),
        ("4-hop from seed",
         f"MATCH (a:Account {{account_id: {seed}}})-[t1:TRANSFER]->(b)-[t2:TRANSFER]->(d)-[t3:TRANSFER]->(e)-[t4:TRANSFER]->(f) "
         "RETURN count(f) AS c"),
        ("2-hop fraud chain (whole graph)",
         "MATCH (a:Account)-[t1:TRANSFER]->(b)-[t2:TRANSFER]->(d) "
         "WHERE t1.is_fraud = true AND t2.is_fraud = true "
         "RETURN count(d) AS c"),
        ("3-hop fraud chain (whole graph)",
         "MATCH (a:Account)-[t1:TRANSFER]->(b)-[t2:TRANSFER]->(d)-[t3:TRANSFER]->(e) "
         "WHERE t1.is_fraud = true AND t2.is_fraud = true AND t3.is_fraud = true "
         "RETURN count(e) AS c"),
        ("4-hop fraud chain (whole graph)",
         "MATCH (a:Account)-[t1:TRANSFER]->(b)-[t2:TRANSFER]->(d)-[t3:TRANSFER]->(e)-[t4:TRANSFER]->(f) "
         "WHERE t1.is_fraud = true AND t2.is_fraud = true AND t3.is_fraud = true AND t4.is_fraud = true "
         "RETURN count(f) AS c"),
        ("2-hop into high-risk accounts",
         "MATCH (a:Account)-[t1:TRANSFER]->(b:Account)-[t2:TRANSFER]->(d:Account) "
         "WHERE t1.amount > 9000 AND d.risk_score > 0.9 "
         "RETURN count(d) AS c"),
        ("high-amount transfer aggregate",
         "MATCH (a:Account)-[t:TRANSFER]->(b) WHERE t.amount > 9000 RETURN count(t) AS c"),
    ]


def query_names():
    return [name for name, _ in build_queries(0)]


def _bench(run, queries, reps, warmup):
    """run(query) -> (wall_ms, server_ms_or_None, result). Reports cold (first
    timed run) plus median over the timed runs."""
    rows = []
    for name, q in queries:
        for _ in range(warmup):
            run(q)
        walls, servers, result = [], [], None
        for _ in range(reps):
            wall, server, result = run(q)
            walls.append(wall)
            if server is not None:
                servers.append(server)
        rows.append({
            "query": name,
            "result": result,
            "cold_ms": walls[0],
            "server_ms": statistics.median(servers) if servers else None,
            "wall_ms": statistics.median(walls),
        })
    return rows


def run_turingdb(host, graph, reps, warmup, seed):
    """Returns (rows, seed_used). Auto-detects the seed if seed is None."""
    from turingdb import TuringClient
    c = TuringClient(host=host)
    c.set_graph(graph)

    if seed is None:
        df = c.query(SEED_QUERY)
        if len(df) == 0:
            df = c.query(SEED_QUERY_FALLBACK)
        seed = int(df.iloc[0, 0])

    def run(q):
        t0 = time.perf_counter()
        df = c.query(q)
        wall = (time.perf_counter() - t0) * 1000
        try:
            srv = c.get_query_exec_time()
            srv = float(srv) if srv is not None else None
        except Exception:
            srv = None
        return wall, srv, int(df.iloc[0, 0])

    return _bench(run, build_queries(seed), reps, warmup), seed


def run_bolt(uri, user, password, reps, warmup, seed, replan=False):
    """Neo4j and Memgraph both use this (Bolt). Returns (rows, seed_used);
    auto-detects the seed if seed is None. Memgraph usually needs no auth.

    replan=True prepends `CYPHER replan=force` (Neo4j) to defeat the plan cache;
    Memgraph rejects that syntax, so it relies on --query-plan-cache-max-size=0.
    """
    from neo4j import GraphDatabase
    auth = (user, password) if user else None
    driver = GraphDatabase.driver(uri, auth=auth, notifications_min_severity="OFF")
    session = driver.session()
    prefix = "CYPHER replan=force " if replan else ""

    try:
        if seed is None:
            rec = session.run(SEED_QUERY).single() or session.run(SEED_QUERY_FALLBACK).single()
            seed = rec["id"]

        def run(q):
            t0 = time.perf_counter()
            res = session.run(prefix + q)
            rec = res.single()
            summ = res.consume()
            wall = (time.perf_counter() - t0) * 1000
            srv = float(summ.result_available_after + summ.result_consumed_after)  # 1ms granularity
            return wall, srv, rec["c"]

        return _bench(run, build_queries(seed), reps, warmup), seed
    finally:
        session.close()
        driver.close()


def print_table(engine, rows):
    print(f"\n=== {engine} ===")
    print(f"{'query':<38}{'result':>14}{'cold_ms':>11}{'server_ms':>12}{'wall_ms':>11}")
    print("-" * 86)
    for r in rows:
        srv = f"{r['server_ms']:.2f}" if r["server_ms"] is not None else "n/a"
        print(f"{r['query']:<38}{r['result']:>14,}{r['cold_ms']:>11.2f}{srv:>12}{r['wall_ms']:>11.2f}")


def print_comparison(results, field, label):
    engs = list(results)
    names = query_names()
    print(f"\n=== {label} comparison ===")
    print(f"{'query':<38}" + "".join(f"{e:>13}" for e in engs))
    print("-" * (38 + 13 * len(engs)))
    for i, name in enumerate(names):
        line = f"{name:<38}"
        for e in engs:
            v = results[e][i][field]
            line += f"{(f'{v:.2f}' if v is not None else 'n/a'):>13}"
        print(line)


def main():
    ap = argparse.ArgumentParser(description="Cold TuringDB vs Neo4j vs Memgraph fraud-query benchmark")
    ap.add_argument("--engine", required=True, choices=["turingdb", "neo4j", "memgraph", "all"])
    ap.add_argument("--seed", type=int, default=None,
                    help="seed account_id for the fan-out queries (default: auto-detect from the dataset)")
    ap.add_argument("--reps", type=int, default=5, help="timed repetitions per query (rep 1 = cold)")
    ap.add_argument("--warmup", type=int, default=0, help="untimed warmup runs (0 = cold, default)")
    ap.add_argument("--no-replan", action="store_true", help="do not force Neo4j replan (keep its plan cache)")
    ap.add_argument("--graph", default="fraud_1m", help="TuringDB graph name")
    ap.add_argument("--turingdb-host", default="http://localhost:6667")
    ap.add_argument("--neo4j-uri", default="bolt://localhost:7687")
    ap.add_argument("--neo4j-user", default="neo4j")
    ap.add_argument("--neo4j-password", default="password")
    ap.add_argument("--memgraph-uri", default="bolt://localhost:7688")
    args = ap.parse_args()

    # seed resolved from the first engine run, then reused for the rest so the
    # seeded queries are identical across engines.
    seed = args.seed
    results = {}
    if args.engine in ("turingdb", "all"):
        results["TuringDB"], seed = run_turingdb(args.turingdb_host, args.graph, args.reps, args.warmup, seed)
    if args.engine in ("neo4j", "all"):
        results["Neo4j"], seed = run_bolt(args.neo4j_uri, args.neo4j_user, args.neo4j_password,
                                          args.reps, args.warmup, seed, replan=not args.no_replan)
    if args.engine in ("memgraph", "all"):
        results["Memgraph"], seed = run_bolt(args.memgraph_uri, None, None, args.reps, args.warmup, seed, replan=False)

    print(f"seed account_id={seed} ({'given' if args.seed is not None else 'auto-detected'})  "
          f"reps={args.reps}  warmup={args.warmup}  mode={'cold' if args.warmup == 0 else 'warm'}  "
          f"neo4j_replan={not args.no_replan}")

    for eng, rows in results.items():
        print_table(eng, rows)
    if len(results) > 1:
        print_comparison(results, "cold_ms", "cold latency (first run, ms)")
        print_comparison(results, "server_ms", "server-reported latency (median ms)")

    print("\nnote: cold_ms is the first timed run (no warmup); server_ms is the engine's own "
          "reported execution time; wall_ms includes protocol + client overhead (localhost).")


if __name__ == "__main__":
    main()
