import os
import sqlite3
import sys
from pathlib import Path

# Search directories
search_dirs = [
    "/Users/Akubrecah/Desktop/KastomPOS",
    str(Path.home() / "Library" / "Application Support" / "KastomPOS"),
    str(Path.home() / ".kastompos"),
    "/Users/Akubrecah"
]

print("Scanning for pos.db or other SQLite files containing C0001...")
found_any = False

for base_dir in search_dirs:
    if not os.path.exists(base_dir):
        continue
    
    # We will search recursively in base_dir up to depth 3 to avoid deep scans
    for root, dirs, files in os.walk(base_dir):
        # Limit depth
        depth = root[len(base_dir):].count(os.sep)
        if depth > 3:
            continue
        
        for file in files:
            if file.endswith(".db") or file.endswith(".sqlite"):
                db_path = os.path.join(root, file)
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'")
                    if cursor.fetchone():
                        cursor.execute("SELECT name, code FROM accounts WHERE code='C0001' OR name='Lipa na M-Pesa'")
                        res = cursor.fetchall()
                        if res:
                            print(f"FOUND MATCH in database: {db_path}")
                            print(f"  Records: {res}")
                            found_any = True
                    conn.close()
                except Exception as e:
                    pass

if not found_any:
    print("No matching database file found containing C0001.")
