#!/usr/bin/env python3
"""Execute every distributed SQL example against the HAPLoD v1.1 SQLite snapshot."""
import argparse
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--db", type=Path, default=ROOT / "03_Data_Release/database/haplod_v1.1.sqlite")
args = parser.parse_args()
if not args.db.is_file():
    raise SystemExit(f"Released SQLite database missing: {args.db}")
sql_file = ROOT / "04_Code/SQL_EXAMPLES.sql"
text = "\n".join(
    line for line in sql_file.read_text(encoding="utf-8").splitlines()
    if not line.lstrip().startswith("--")
)
statements = [part.strip() for part in text.split(";") if part.strip()]
if len(statements) != 6:
    raise SystemExit(f"Expected 6 SQL examples, found {len(statements)}")
with sqlite3.connect(f"file:{args.db.resolve()}?mode=ro", uri=True) as db:
    db.execute("PRAGMA query_only = TRUE")
    for index, sql in enumerate(statements, start=1):
        if not sql.lstrip().upper().startswith("SELECT"):
            raise ValueError(f"SQL example {index} is not a SELECT statement")
        row_count = sum(1 for _ in db.execute(sql))
        print(f"SQL {index}: {row_count} rows; PASS")
print("All 6 SQL examples passed")
