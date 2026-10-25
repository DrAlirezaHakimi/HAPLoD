#!/usr/bin/env python3
"""Execute each archived SQL example against the released SQLite database."""
from pathlib import Path
import sqlite3
root = Path(__file__).resolve().parents[1]
dbpath = root / "03_Data_Release/database/haplod_v1.1.sqlite"
if not dbpath.is_file():
    raise SystemExit(f"Missing released dataset: {dbpath}")
db = sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True)
script = (root / "04_Code/SQL_EXAMPLES.sql").read_text(encoding="utf-8")
for index, sql in enumerate(script.split(";"), 1):
    sql = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--")).strip()
    if not sql:
        continue
    rows = db.execute(sql).fetchall()
    print(f"SQL {index}: {len(rows)} rows; OK")
print("All SQL examples passed")
