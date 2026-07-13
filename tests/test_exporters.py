# Copyright (c) 2026 Santander Group
# SPDX-License-Identifier: Apache-2.0

"""Tests for gen_fraud_graph.exporters (headers, write_output, append_csv)."""

from __future__ import annotations

import csv
import os

from gen_fraud_graph.exporters import (
    append_csv,
    compact_parquet_files,
    embedding_to_bytes,
    get_headers,
    parquet_schema,
    write_output,
    write_parquet_table,
)


class TestExporters:
    def test_csv_headers_account(self):
        h = get_headers("account", "csv")
        assert "account_id" in h
        assert "balance" in h

    def test_csv_headers_transaction(self):
        h = get_headers("transaction", "csv")
        assert "tx_id" in h
        assert "src_id" in h
        assert "dst_id" in h

    def test_neptune_headers_account(self):
        h = get_headers("account", "neptune")
        assert "~id" in h
        assert "~label" in h

    def test_neptune_headers_transaction(self):
        h = get_headers("transaction", "neptune")
        assert "~from" in h
        assert "~to" in h

    def test_write_output_csv(self, tmp_dir):
        path = os.path.join(tmp_dir, "test")
        write_output(path, ["a", "b"], [[1, 2], [3, 4]])
        assert os.path.exists(f"{path}.csv")

        with open(f"{path}.csv") as fh:
            reader = csv.reader(fh)
            rows = list(reader)
        assert rows[0] == ["a", "b"]
        assert len(rows) == 3

    def test_write_output_compressed(self, tmp_dir):
        path = os.path.join(tmp_dir, "test_zip")
        write_output(path, ["x"], [[1], [2]], compress=True)
        assert os.path.exists(f"{path}.csv.zip")


class TestAppendCsv:
    def test_append_creates_file_with_header(self, tmp_dir):
        path = os.path.join(tmp_dir, "x.csv")
        append_csv(path, ["a", "b"], [[1, 2]])
        with open(path) as fh:
            rows = list(csv.reader(fh))
        assert rows[0] == ["a", "b"]
        assert rows[1] == ["1", "2"]

    def test_append_existing_file_skips_header(self, tmp_dir):
        path = os.path.join(tmp_dir, "x.csv")
        append_csv(path, ["a", "b"], [[1, 2]])
        append_csv(path, ["a", "b"], [[3, 4]])
        with open(path) as fh:
            rows = list(csv.reader(fh))
        assert rows == [["a", "b"], ["1", "2"], ["3", "4"]]


class TestParquetExporters:
    def test_parquet_headers_account(self):
        h = get_headers("account", "parquet")
        assert "__id" in h
        assert "__labels" in h
        assert "account_id" in h

    def test_parquet_headers_transaction(self):
        h = get_headers("transaction", "parquet")
        assert "__source" in h
        assert "__target" in h
        assert "__type" in h

    def test_embedding_to_bytes_uses_float32_width(self):
        assert len(embedding_to_bytes([1.0, 2.0, 3.0])) == 12

    def test_write_parquet_table(self, tmp_dir):
        import os

        import pyarrow.parquet as pq

        schema = parquet_schema("embedding", dim=2)
        path = os.path.join(tmp_dir, "embeddings.parquet")
        write_parquet_table(
            path, schema, [[1, 2], [embedding_to_bytes([0.1, 0.2]), embedding_to_bytes([0.3, 0.4])]]
        )

        assert os.path.exists(path)
        assert pq.read_schema(path).field("embedding").type.byte_width == 8

    def test_compact_parquet_files(self, tmp_dir):
        import os

        import pyarrow.parquet as pq

        schema = parquet_schema("embedding", dim=1)
        part1 = os.path.join(tmp_dir, "part1.parquet")
        part2 = os.path.join(tmp_dir, "part2.parquet")
        out = os.path.join(tmp_dir, "combined.parquet")
        write_parquet_table(part1, schema, [[1], [embedding_to_bytes([0.1])]])
        write_parquet_table(part2, schema, [[2], [embedding_to_bytes([0.2])]])

        compact_parquet_files([part1, part2], out)

        assert pq.ParquetFile(out).metadata.num_rows == 2
