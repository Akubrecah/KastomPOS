import sqlite3

def migrate():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()

    # Create payroll_constants table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payroll_constants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category VARCHAR,
        name VARCHAR,
        is_taxable BOOLEAN DEFAULT 1,
        is_active BOOLEAN DEFAULT 1,
        narrative TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Checked/Created payroll_constants table.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
