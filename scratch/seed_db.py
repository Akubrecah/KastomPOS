import sqlite3

def seed_data():
    conn = sqlite3.connect('pos.db')
    cursor = conn.cursor()
    
    # Seed Units
    units = [('Pcs', 'Pieces'), ('Kg', 'Kilograms'), ('Ltr', 'Liters'), ('Box', 'Boxes')]
    for unit in units:
        cursor.execute("INSERT OR IGNORE INTO units (name, description) VALUES (?, ?)", unit)
    
    # Seed Tax Types
    taxes = [('VAT 16%', 16.0), ('VAT 8%', 8.0), ('Zero Rated', 0.0), ('Exempt', 0.0)]
    for tax in taxes:
        cursor.execute("INSERT OR IGNORE INTO tax_types (name, rate) VALUES (?, ?)", tax)
    
    conn.commit()
    conn.close()
    print("Seeding complete.")

if __name__ == "__main__":
    seed_data()
