import sqlite3

def upgrade_products():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()
    
    columns = [
        ("sku", "TEXT"),
        ("brand", "TEXT"),
        ("color", "TEXT"),
        ("reorder_level", "INTEGER DEFAULT 0"),
        ("narrative", "TEXT")
    ]
    
    print("Checking for missing columns in 'products' table...")
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
            print(f"Added '{col_name}' column to 'products' table.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"'{col_name}' column already exists.")
            else:
                print(f"Error adding '{col_name}': {e}")

    conn.commit()
    conn.close()
    print("Products table upgrade complete.")

if __name__ == "__main__":
    upgrade_products()
