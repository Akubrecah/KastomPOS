import sqlite3
import os

db_path = "pos.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(accounts)")
    columns = cursor.fetchall()
    print(f"Columns in {db_path} accounts table:")
    for col in columns:
        print(col)
    conn.close()
else:
    print(f"{db_path} does not exist")

# Check other potential DBs
for f in ["database.db", "pos_erp.db"]:
    if os.path.exists(f):
        conn = sqlite3.connect(f)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
        if cursor.fetchone():
            cursor.execute(f"PRAGMA table_info(accounts)")
            columns = cursor.fetchall()
            print(f"Columns in {f} accounts table:")
            for col in columns:
                print(col)
        else:
            print(f"No accounts table in {f}")
        conn.close()
