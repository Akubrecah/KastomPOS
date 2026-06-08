import sqlite3
import os

db_path = "pos.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if store_id exists in orders
    cursor.execute("PRAGMA table_info(orders)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "store_id" not in columns:
        print("Adding store_id column to orders table...")
        cursor.execute("ALTER TABLE orders ADD COLUMN store_id INTEGER REFERENCES stores(id)")
    else:
        print("store_id column already exists in orders.")
        
    conn.commit()
    conn.close()
    print("Database upgrade complete.")
else:
    print("Database file not found. It will be created with correct schema on next app run.")
