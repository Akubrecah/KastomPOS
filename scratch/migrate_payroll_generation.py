import sqlite3
import os

def migrate():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()

    # Add basic_salary to staff
    try:
        cursor.execute("ALTER TABLE staff ADD COLUMN basic_salary FLOAT DEFAULT 0.0")
        print("Added basic_salary to staff table.")
    except sqlite3.OperationalError:
        print("basic_salary already exists in staff table.")

    # Create payroll_records table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payroll_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER REFERENCES staff(id),
        store_id INTEGER REFERENCES stores(id),
        fiscal_year_id INTEGER REFERENCES fiscal_years(id),
        month INTEGER,
        basic_salary FLOAT DEFAULT 0.0,
        allowances FLOAT DEFAULT 0.0,
        gross_salary FLOAT DEFAULT 0.0,
        nssf FLOAT DEFAULT 0.0,
        sha FLOAT DEFAULT 0.0,
        housing_levy FLOAT DEFAULT 0.0,
        paye FLOAT DEFAULT 0.0,
        other_deductions FLOAT DEFAULT 0.0,
        net_salary FLOAT DEFAULT 0.0,
        status TEXT DEFAULT 'Pending',
        is_active BOOLEAN DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Created payroll_records table.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
