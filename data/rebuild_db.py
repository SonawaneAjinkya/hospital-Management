"""
Rebuilds data/hospital.db from schema.sql + the CSV files.
Use this any time the .db file seems empty, corrupted, or out of sync
with the CSVs (e.g. after a download/extraction that mangled the binary
file, or after re-running generate_sample_data.py).

Run from the project root: python3 data/rebuild_db.py
"""

import sqlite3
import pandas as pd
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "hospital.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "..", "sql", "schema.sql")

TABLES = ["patients", "beds", "admissions", "staff", "staff_shifts",
          "medicines", "medicine_transactions"]

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed old {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    print("Schema applied.")

    for t in TABLES:
        csv_path = os.path.join(BASE_DIR, f"{t}.csv")
        if not os.path.exists(csv_path):
            print(f"WARNING: {csv_path} not found — run generate_sample_data.py first. Skipping {t}.")
            continue
        df = pd.read_csv(csv_path)
        df.to_sql(t, conn, if_exists="append", index=False)
        print(f"Loaded {t}: {len(df)} rows")

    conn.commit()

    # Verify
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print("\nTables now in DB:", [r[0] for r in cur.fetchall()])
    conn.close()

    print(f"\nRebuilt {DB_PATH} successfully.")
