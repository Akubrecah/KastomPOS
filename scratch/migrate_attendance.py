import sqlite3

def migrate():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()

    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            store_id INTEGER,
            check_in DATETIME,
            check_out DATETIME,
            status VARCHAR(50) DEFAULT 'In',
            device_info TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(employee_id) REFERENCES staff(id),
            FOREIGN KEY(store_id) REFERENCES stores(id)
        )
        """)
        print("Attendance table created.")
    except Exception as e:
        print(f"Error creating attendance table: {e}")

    conn.commit()
    conn.close()
    print("Migration completed.")

if __name__ == "__main__":
    migrate()
