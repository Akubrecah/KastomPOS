import sqlite3

def migrate():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()

    try:
        # Add stretch column
        cursor.execute("ALTER TABLE leave_applications ADD COLUMN stretch VARCHAR(50) DEFAULT 'full'")
        print("Added stretch column.")
    except Exception as e:
        print(f"Stretch column error (might exist): {e}")

    # total_days is already Integer, which works with Float in SQLite (Dynamic typing)
    # But let's check if we can add other info boxes data if needed.
    
    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
