import sqlite3
import os

def migrate():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()

    # Create salary_advances table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS salary_advances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER REFERENCES staff(id),
        fiscal_year_id INTEGER REFERENCES fiscal_years(id),
        month INTEGER,
        amount FLOAT DEFAULT 0.0,
        is_disbursed BOOLEAN DEFAULT 0,
        is_recovered BOOLEAN DEFAULT 0,
        narrative TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Created salary_advances table.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
