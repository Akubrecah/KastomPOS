import sqlite3

def upgrade_db():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()
    
    print("Checking for missing columns in 'purchases' table...")
    
    # Add 'status' column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE purchases ADD COLUMN status TEXT DEFAULT 'Received'")
        print("Added 'status' column to 'purchases' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("'status' column already exists.")
        else:
            print(f"Error adding 'status': {e}")

    # Add 'payment_schedule_id' column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE purchases ADD COLUMN payment_schedule_id INTEGER REFERENCES payment_schedules(id)")
        print("Added 'payment_schedule_id' column to 'purchases' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("'payment_schedule_id' column already exists.")
        else:
            print(f"Error adding 'payment_schedule_id': {e}")

    # Create 'payment_schedules' table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference TEXT UNIQUE,
        status TEXT DEFAULT 'Suspended',
        date DATETIME DEFAULT CURRENT_TIMESTAMP,
        amount FLOAT DEFAULT 0.0,
        narrative TEXT,
        created_by_id INTEGER REFERENCES staff(id)
    )
    """)
    print("Ensured 'payment_schedules' table exists.")

    # Create 'purchase_items' table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS purchase_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER REFERENCES purchases(id),
        product_id INTEGER REFERENCES products(id),
        description TEXT,
        quantity FLOAT,
        unit_price FLOAT,
        tax_rate FLOAT DEFAULT 0.0,
        tax_amount FLOAT DEFAULT 0.0,
        total_amount FLOAT,
        unit_id INTEGER REFERENCES units(id)
    )
    """)
    print("Ensured 'purchase_items' table exists.")

    # Create 'units' table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT
    )
    """)
    print("Ensured 'units' table exists.")

    # Create 'tax_types' table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tax_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        rate FLOAT DEFAULT 0.0
    )
    """)
    print("Ensured 'tax_types' table exists.")

    # Create 'quotations' table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER REFERENCES customers(id),
        staff_id INTEGER REFERENCES staff(id),
        total_amount FLOAT DEFAULT 0.0,
        tax_amount FLOAT DEFAULT 0.0,
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Ensured 'quotations' table exists.")

    # Create 'quotation_items' table if it doesn't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quotation_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quotation_id INTEGER REFERENCES quotations(id),
        product_id INTEGER REFERENCES products(id),
        quantity INTEGER,
        unit_price FLOAT
    )
    """)
    print("Ensured 'quotation_items' table exists.")

    # Create 'banquets' table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banquets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            staff_id INTEGER,
            total_amount REAL DEFAULT 0.0,
            tax_amount REAL DEFAULT 0.0,
            status TEXT DEFAULT 'pending',
            event_date DATETIME,
            store_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(staff_id) REFERENCES staff(id),
            FOREIGN KEY(store_id) REFERENCES stores(id)
        )
    """)
    print("Ensured 'banquets' table exists.")

    # Create 'banquet_items' table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS banquet_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            banquet_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            FOREIGN KEY(banquet_id) REFERENCES banquets(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    print("Ensured 'banquet_items' table exists.")

    # Add 'is_stamped' column to 'orders' table
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN is_stamped BOOLEAN DEFAULT 0")
        print("Added 'is_stamped' column to 'orders' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("'is_stamped' column already exists.")
        else:
            print(f"Error adding 'is_stamped': {e}")

    # Create 'rooms' table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_number TEXT UNIQUE,
        room_type TEXT,
        price_per_night FLOAT,
        status TEXT DEFAULT 'available',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Ensured 'rooms' table exists.")

    # Create 'room_bookings' table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS room_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_id INTEGER REFERENCES rooms(id),
        customer_name TEXT,
        customer_phone TEXT,
        from_date DATETIME,
        to_date DATETIME,
        nights INTEGER,
        booking_type TEXT,
        occupancy INTEGER,
        narrative TEXT,
        total_amount FLOAT,
        paid_amount FLOAT,
        balance FLOAT,
        payment_method TEXT,
        reference TEXT,
        status TEXT DEFAULT 'active',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    print("Ensured 'room_bookings' table exists.")

    # Add 'source' column to 'room_bookings' if it doesn't exist
    try:
        cursor.execute("ALTER TABLE room_bookings ADD COLUMN source TEXT DEFAULT 'Walk-in'")
        print("Added 'source' column to 'room_bookings' table.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print("'source' column already exists.")
        else:
            print(f"Error adding 'source': {e}")

    conn.commit()
    conn.close()
    print("Database upgrade complete.")

if __name__ == "__main__":
    upgrade_db()
