# Copyright (c) 2026 Santander Group
# SPDX-License-Identifier: Apache-2.0

"""Output writers for generated graph data."""

from __future__ import annotations

import csv
import io
import os
import zipfile
from collections.abc import Sequence
from typing import Literal

import numpy as np

OutputFormat = Literal["csv", "neptune", "parquet"]


def get_headers(
    doc_type: Literal["account", "transaction"],
    fmt: OutputFormat,
) -> list[str]:
    """Return CSV-style column headers for *doc_type* in the given *fmt*."""
    if fmt == "neptune":
        if doc_type == "account":
            return [
                "~id",
                "~label",
                "customer_name:String",
                "balance:Double",
                "risk_score:Double",
                "creation_date:String",
                "embedding:vector",
            ]
        return [
            "~id",
            "~from",
            "~to",
            "~label",
            "amount:Double",
            "timestamp:String",
            "description:String",
        ]

    if fmt == "parquet":
        if doc_type == "account":
            return [
                "__id",
                "__labels",
                "account_id",
                "customer_name",
                "balance",
                "risk_score",
                "creation_date",
            ]
        return [
            "__source",
            "__target",
            "__type",
            "tx_id",
            "amount",
            "timestamp",
            "description",
            "is_fraud",
        ]

    # Default CSV
    if doc_type == "account":
        return ["account_id", "customer_name", "balance", "risk_score", "creation_date"]
    return ["tx_id", "src_id", "dst_id", "amount", "timestamp", "description", "embedding"]


def _require_pyarrow():
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise ImportError(
            "pyarrow is required for output_format='parquet'. "
            "Install with: pip install pyarrow or uv pip install pyarrow."
        ) from exc
    return pa, pq


def embedding_to_bytes(vector: Sequence[float] | np.ndarray) -> bytes:
    """Encode an embedding vector as raw float32 bytes for fixed binary Parquet columns."""
    data: bytes = np.asarray(vector, dtype=np.float32).tobytes(order="C")
    return data


def parquet_schema(
    kind: Literal["account", "transaction", "embedding", "fraud_case"], dim: int = 0
):
    """Return TuringDB-oriented PyArrow schemas used by the Parquet exporter."""
    pa, _ = _require_pyarrow()

    if kind == "account":
        return pa.schema(
            [
                ("__id", pa.int64()),
                ("__labels", pa.list_(pa.binary())),
                ("account_id", pa.uint64()),
                ("customer_name", pa.string()),
                ("balance", pa.float64()),
                ("risk_score", pa.float64()),
                ("creation_date", pa.string()),
            ]
        )

    if kind == "transaction":
        return pa.schema(
            [
                ("__source", pa.int64()),
                ("__target", pa.int64()),
                ("__type", pa.binary()),
                ("tx_id", pa.int64()),
                ("amount", pa.float64()),
                ("timestamp", pa.string()),
                ("description", pa.string()),
                ("is_fraud", pa.bool_()),
            ]
        )

    if kind == "embedding":
        return pa.schema(
            [
                ("node_id", pa.int64()),
                ("embedding", pa.binary(dim * 4)),
            ]
        )

    return pa.schema(
        [
            ("pattern_id", pa.string()),
            ("start_acc_id", pa.int64()),
            ("pattern_type", pa.string()),
            ("depth", pa.int64()),
            ("involved_accounts", pa.string()),
        ]
    )


def write_parquet_table(
    file_path: str, schema, columns: Sequence[Sequence], *, row_group_size: int = 65536
) -> str:
    """Write one Parquet table with zstd compression."""
    pa, pq = _require_pyarrow()
    output_dir = os.path.dirname(file_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    arrays = [
        pa.array(values, type=field.type) for values, field in zip(columns, schema, strict=True)
    ]
    table = pa.Table.from_arrays(arrays, schema=schema)
    pq.write_table(table, file_path, compression="zstd", row_group_size=row_group_size)
    return file_path


def compact_parquet_files(
    input_paths: Sequence[str],
    output_path: str,
    *,
    row_group_size: int = 65536,
) -> str:
    """Combine Parquet shards with identical schemas into one output file."""
    if not input_paths:
        raise ValueError("input_paths must not be empty")

    _, pq = _require_pyarrow()
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    writer = None
    try:
        for path in input_paths:
            parquet_file = pq.ParquetFile(path)
            if writer is None:
                writer = pq.ParquetWriter(
                    output_path, parquet_file.schema_arrow, compression="zstd"
                )
            for batch in parquet_file.iter_batches(batch_size=row_group_size):
                writer.write_batch(batch)
    finally:
        if writer is not None:
            writer.close()

    return output_path


def write_output(
    file_base_name: str,
    headers: Sequence[str],
    rows: Sequence[Sequence],
    *,
    compress: bool = False,
) -> str:
    """Write *rows* to a CSV file, optionally ZIP-compressed.

    Returns:
        The path of the written file.
    """
    csv_filename = f"{file_base_name}.csv"

    if compress:
        zip_filename = f"{file_base_name}.csv.zip"
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        writer.writerows(rows)
        with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(os.path.basename(csv_filename), buf.getvalue())
        buf.close()
        return zip_filename

    with open(csv_filename, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)
    return csv_filename


def append_csv(
    csv_path: str,
    headers: Sequence[str],
    rows: Sequence[Sequence],
    *,
    resume_from: int = 0,
) -> None:
    """Append *rows* to an existing or new CSV file.

    If the file already exists, writing resumes after its current content.
    """
    file_exists = os.path.exists(csv_path)

    with open(csv_path, "a", newline="") as fh:
        writer = csv.writer(fh)
        if not file_exists:
            writer.writerow(headers)
        writer.writerows(rows)
