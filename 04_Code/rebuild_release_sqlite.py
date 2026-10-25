#!/usr/bin/env python3
"""Rebuild the published SQLite *snapshot* from CSV exports and the published SQL schema.

This is NOT regeneration of upstream source catalogues from original observations.
"""
from pathlib import Path
import argparse
import csv
import gzip
import sqlite3

root = Path(__file__).resolve().parents[1]
data = root / "03_Data_Release"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", default=str(root / "reconstructed_haplod_v1.1.sqlite"))
args = parser.parse_args()
out = Path(args.output)
if out.exists():
    raise SystemExit(f"Refusing to overwrite existing database: {out}")
schema = data / "metadata/database_schema_v1_1.sql"
if not schema.is_file():
    raise SystemExit(f"Missing published database schema: {schema}")
db = sqlite3.connect(out)
try:
    db.executescript(schema.read_text(encoding="utf-8"))
    files = sorted((data / "csv_complete").glob("*.csv.gz"))
    if not files:
        raise RuntimeError("No released CSV tables available")
    for filename in files:
        table = filename.name[:-7]
        if not table.replace("_", "").isalnum():
            raise ValueError(f"Invalid table name {table!r}")
        with gzip.open(filename, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            columns = next(reader)
            placeholders = ",".join("?" for _ in columns)
            insert = f'INSERT INTO "{table}" VALUES ({placeholders})'
            batch = []
            for row in reader:
                if len(row) != len(columns):
                    raise ValueError(f"Wrong column count in {filename}")
                batch.append(tuple(None if value == r"\N" else value for value in row))
                if len(batch) >= 2000:
                    db.executemany(insert, batch)
                    batch.clear()
            if batch:
                db.executemany(insert, batch)
        print(table, db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    db.commit()
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise RuntimeError("SQLite integrity check failed")
finally:
    db.close()
print(f"Snapshot reconstruction successful: {out}")
