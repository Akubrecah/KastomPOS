import sqlite3

def migrate():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()

    # Add columns to staff table
    columns_to_add = [
        ("designation_id", "INTEGER"),
        ("id_number", "VARCHAR"),
        ("phone", "VARCHAR")
    ]

    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE staff ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to staff table.")
        except sqlite3.OperationalError:
            print(f"Column {col_name} already exists in staff table.")

    # Create perf_constants table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS perf_constants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category VARCHAR,
        name VARCHAR,
        collection_id INTEGER,
        weight FLOAT DEFAULT 0.0,
        score FLOAT DEFAULT 0.0,
        description VARCHAR,
        is_active BOOLEAN DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(collection_id) REFERENCES perf_constants(id)
    )
    """)
    print("Checked/Created perf_constants table.")

    # Create perf_appraisals table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS perf_appraisals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER,
        month INTEGER,
        year INTEGER,
        narrative TEXT,
        appraised_by_id INTEGER,
        total_score FLOAT DEFAULT 0.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(employee_id) REFERENCES staff(id),
        FOREIGN KEY(appraised_by_id) REFERENCES staff(id)
    )
    """)
    print("Checked/Created perf_appraisals table.")

    # Create perf_appraisal_scores table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS perf_appraisal_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        appraisal_id INTEGER,
        index_id INTEGER,
        score FLOAT,
        FOREIGN KEY(appraisal_id) REFERENCES perf_appraisals(id),
        FOREIGN KEY(index_id) REFERENCES perf_constants(id)
    )
    """)
    print("Checked/Created perf_appraisal_scores table.")

    conn.commit()
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate()
