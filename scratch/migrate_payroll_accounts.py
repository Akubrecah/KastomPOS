import sqlite3

def migrate():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()

    # Add columns if they don't exist
    try:
        cursor.execute("ALTER TABLE payroll_constants ADD COLUMN payable_account_id INTEGER REFERENCES accounts(id)")
    except sqlite3.OperationalError:
        pass # Column already exists
    
    try:
        cursor.execute("ALTER TABLE payroll_constants ADD COLUMN expense_account_id INTEGER REFERENCES accounts(id)")
    except sqlite3.OperationalError:
        pass # Column already exists

    print("Updated payroll_constants table with account fields.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
