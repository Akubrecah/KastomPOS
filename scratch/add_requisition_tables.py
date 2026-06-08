import sqlite3

def upgrade_db():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()
    
    print("Creating 'requisitions' and 'requisition_items' tables...")
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requisitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR UNIQUE,
                receiving_store_id INTEGER,
                issuing_store_id INTEGER,
                supplier_id INTEGER,
                request_person_id INTEGER,
                approved_by_id INTEGER,
                priority VARCHAR DEFAULT 'Medium',
                request_type VARCHAR DEFAULT 'Internal',
                status VARCHAR DEFAULT 'Pending',
                created_at DATETIME,
                FOREIGN KEY (receiving_store_id) REFERENCES stores (id),
                FOREIGN KEY (issuing_store_id) REFERENCES stores (id),
                FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
                FOREIGN KEY (request_person_id) REFERENCES staff (id),
                FOREIGN KEY (approved_by_id) REFERENCES staff (id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_requisitions_id ON requisitions (id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_requisitions_code ON requisitions (code)')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS requisition_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                requisition_id INTEGER,
                product_id INTEGER,
                quantity FLOAT,
                unit_price FLOAT,
                narrative TEXT,
                FOREIGN KEY (requisition_id) REFERENCES requisitions (id),
                FOREIGN KEY (product_id) REFERENCES products (id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS ix_requisition_items_id ON requisition_items (id)')
        
        conn.commit()
        print("Success: Requisition tables created.")
    except Exception as e:
        print(f"Error creating tables: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    upgrade_db()
