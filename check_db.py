import os
import sqlite3
import sys
from pathlib import Path

appName = "KastomPOS"
if sys.platform == "darwin":
    base_dir = str(Path.home() / "Library" / "Application Support" / appName)
else:
    base_dir = "."
db_path = os.path.join(base_dir, "pos.db")

print(f"Database path: {db_path}")
if not os.path.exists(db_path):
    print("Database file does not exist!")
    sys.exit(0)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]

print("Table row counts:")
for table in sorted(tables):
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")
    except Exception as e:
        print(f"  {table}: Error: {e}")

print("\nAccounts list:")
try:
    cursor.execute("SELECT id, name, code, account_type FROM accounts")
    for row in cursor.fetchall():
        print(f"  {row}")
except Exception as e:
    print(f"Error fetching accounts: {e}")

print("\nJournal postings:")
try:
    cursor.execute("SELECT id, account_id, dr_cr, amount FROM journal_postings LIMIT 10")
    for row in cursor.fetchall():
        print(f"  {row}")
except Exception as e:
    print(f"Error fetching journal postings: {e}")

conn.close()
