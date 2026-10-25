#!/usr/bin/env python3
"""Compare reconstructed SQLite snapshot rows with the released SQLite reference.

Numerical deviations <= 1e-10 are allowed; this is not a byte-level file test.
"""
import argparse
import json
import sqlite3
from pathlib import Path

base = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--rebuilt", required=True)
args = parser.parse_args()
a = sqlite3.connect(base / "03_Data_Release/database/haplod_v1.1.sqlite")
b = sqlite3.connect(args.rebuilt)
results = []
for (name,) in a.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
    rows_a = a.execute(f'SELECT * FROM "{name}"').fetchall()
    rows_b = b.execute(f'SELECT * FROM "{name}"').fetchall()
    if len(rows_a) != len(rows_b):
        raise AssertionError((name, len(rows_a), len(rows_b)))
    rounding, biggest = 0, 0.0
    for row_i, (ra, rb) in enumerate(zip(rows_a, rows_b)):
        for col_i, (x, y) in enumerate(zip(ra, rb)):
            if x == y:
                continue
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                diff = abs(x - y)
                biggest = max(biggest, diff)
                rounding += 1
                if diff <= 1e-10:
                    continue
            raise AssertionError(f"{name}[{row_i},{col_i}]: {x!r} != {y!r}")
    results.append({"table": name, "rows": len(rows_a), "rounding_only_cells": rounding, "max_absolute_float_error": biggest})
if b.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
    raise RuntimeError("SQLite integrity check failed")
print(json.dumps({"result": "PASS", "tables": len(results), "total_rows": sum(row["rows"] for row in results), "float_tolerance": 1e-10, "results": results}, indent=2))
