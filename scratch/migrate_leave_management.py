import sqlite3
import os

def migrate():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()

    # Create leave_types table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leave_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(255) UNIQUE,
        days_per_year INTEGER DEFAULT 21,
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Created leave_types table.")

    # Create leave_applications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leave_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER REFERENCES staff(id),
        leave_type_id INTEGER REFERENCES leave_types(id),
        start_date DATE,
        end_date DATE,
        total_days INTEGER,
        reason TEXT,
        status VARCHAR(50) DEFAULT 'Pending',
        approved_by_id INTEGER REFERENCES staff(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Created leave_applications table.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
