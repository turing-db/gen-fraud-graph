# Copyright (c) 2026 Santander Group
# SPDX-License-Identifier: Apache-2.0

"""Verify that generated fraud patterns actually exist in the transaction data."""

from __future__ import annotations

import csv
import os
import sys
from collections import defaultdict


def verify_fraud_patterns(
    fraud_cases_path: str,
    transactions_dir: str,
) -> bool:
    """Check that every fraud-case cycle is backed by real transaction edges.

    Args:
        fraud_cases_path: Path to ``fraud_cases.csv``.
        transactions_dir: Directory containing ``transactions_fraud.csv``
            (or the fraud subdirectory).

    Returns:
        ``True`` if all patterns are valid, ``False`` otherwise.
    """
    fraud_dir = os.path.dirname(fraud_cases_path)
    fraud_tx_path = os.path.join(fraud_dir, "transactions_fraud.csv")
    parquet_tx_path = os.path.join(os.path.dirname(fraud_dir), "graph", "edges_fraud.parquet")

    print("Loading fraud transaction edges...")
    edges: dict[str, set[str]] = defaultdict(set)
    if os.path.exists(fraud_tx_path):
        with open(fraud_tx_path) as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                src = row.get("src_id") or row.get("~from", "")
                dst = row.get("dst_id") or row.get("~to", "")
                if src and dst:
                    edges[str(src)].add(str(dst))
    elif os.path.exists(parquet_tx_path):
        import pyarrow.parquet as pq

        schema_names = pq.read_schema(parquet_tx_path).names
        if "from" in schema_names and "to" in schema_names:
            table = pq.read_table(parquet_tx_path, columns=["from", "to"])
            sources = table.column("from").to_pylist()
            targets = table.column("to").to_pylist()
            for src, dst in zip(sources, targets, strict=True):
                edges[src.decode("utf-8") if isinstance(src, bytes) else str(src)].add(
                    dst.decode("utf-8") if isinstance(dst, bytes) else str(dst)
                )
        else:
            table = pq.read_table(parquet_tx_path, columns=["__source", "__target"])
            sources = table.column("__source").to_pylist()
            targets = table.column("__target").to_pylist()
            for src, dst in zip(sources, targets, strict=True):
                edges[str(src)].add(str(dst))
    else:
        print(f"ERROR: {fraud_tx_path} or {parquet_tx_path} not found", file=sys.stderr)
        return False

    print("Verifying fraud cases...")
    all_valid = True
    case_rows: list[dict[str, object]]
    if fraud_cases_path.endswith(".parquet"):
        import pyarrow.parquet as pq

        case_rows = pq.read_table(fraud_cases_path).to_pylist()
    else:
        with open(fraud_cases_path) as fh:
            case_rows = list(csv.DictReader(fh))

    for row in case_rows:
        pattern_id = str(row["pattern_id"])
        accounts = str(row["involved_accounts"]).split("|")
        depth = int(str(row["depth"]))

        # Check that the cycle edges exist
        for k in range(depth):
            src = accounts[k]
            dst = accounts[(k + 1) % depth]
            if dst not in edges.get(src, set()):
                print(f"  FAIL: {pattern_id} — missing edge {src} -> {dst}")
                all_valid = False
                break
        else:
            continue

    if all_valid:
        print("All fraud patterns verified successfully.")
    else:
        print("Some fraud patterns failed verification.", file=sys.stderr)

    return all_valid


def main() -> None:
    """CLI entry point for verification."""
    import argparse

    parser = argparse.ArgumentParser(description="Verify generated fraud patterns.")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        help="Root output directory (contains fraud/ subdirectory).",
    )
    args = parser.parse_args()

    cases = os.path.join(args.data_dir, "fraud", "fraud_cases.csv")
    parquet_cases = os.path.join(args.data_dir, "fraud", "fraud_cases.parquet")
    if not os.path.exists(cases):
        if os.path.exists(parquet_cases):
            cases = parquet_cases
        else:
            print(f"ERROR: {cases} not found. Run gen-fraud-graph first.", file=sys.stderr)
            sys.exit(1)

    ok = verify_fraud_patterns(cases, args.data_dir)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
