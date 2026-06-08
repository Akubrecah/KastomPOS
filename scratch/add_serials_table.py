import sqlite3

def upgrade_db():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()
    
    print("Creating 'product_serials' table...")
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS product_serials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                serial_number VARCHAR UNIQUE,
                condition VARCHAR DEFAULT 'Good',
                narrative VARCHAR,
                status VARCHAR DEFAULT 'available',
                created_at DATETIME,
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_product_serials_id ON product_serials (id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_product_serials_serial_number ON product_serials (serial_number)')
        conn.commit()
        print("Success: 'product_serials' table created.")
    except Exception as e:
        print(f"Error creating table: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade_db()
