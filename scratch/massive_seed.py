import random
import datetime
import sys
import os
sys.path.append(os.getcwd())
import models
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///./pos.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_or_create_unit(db, name):
    unit = db.query(models.Unit).filter(models.Unit.name == name).first()
    if not unit:
        unit = models.Unit(name=name)
        db.add(unit)
        db.flush()
    return unit

def get_or_create_tax(db, name, rate):
    tax = db.query(models.TaxType).filter(models.TaxType.name == name).first()
    if not tax:
        tax = models.TaxType(name=name, rate=rate)
        db.add(tax)
        db.flush()
    return tax

def get_or_create_account(db, name, type_name):
    acc_type = db.query(models.AccountType).filter(models.AccountType.name == type_name).first()
    if not acc_type:
        acc_type = models.AccountType(name=type_name)
        db.add(acc_type)
        db.flush()
    
    acc = db.query(models.Account).filter(models.Account.name == name).first()
    if not acc:
        acc = models.Account(
            name=name,
            code=f"ACC-{random.randint(1000, 9999)}",
            account_type_id=acc_type.id
        )
        db.add(acc)
        db.flush()
    return acc

def seed_massive_data():
    db = SessionLocal()
    try:
        print("Starting massive seeding...")

        # 1. Units
        units = []
        for u_name in ['Pcs', 'Kg', 'Ltr', 'Box', 'Nights']:
            units.append(get_or_create_unit(db, u_name))

        # 2. Tax Types
        taxes = []
        for t_name, rate in [('VAT 16%', 16.0), ('VAT 8%', 8.0), ('Zero Rated', 0.0)]:
            taxes.append(get_or_create_tax(db, t_name, rate))

        # 3. Store
        stores = db.query(models.Store).all()
        if not stores:
            for i in range(1, 6):
                store = models.Store(name=f"Store {i}", location=f"Location {i}")
                db.add(store)
            db.flush()
            stores = db.query(models.Store).all()

        # 4. Accounts
        cash_acc = get_or_create_account(db, "Cash", "Asset")
        sales_acc = get_or_create_account(db, "Sales Income", "Revenue")
        cogs_acc = get_or_create_account(db, "Cost of Goods Sold", "Expense")
        pay_acc = get_or_create_account(db, "Accounts Payable", "Liability")
        receiv_acc = get_or_create_account(db, "Accounts Receivable", "Asset")
        
        expense_accs = [
            get_or_create_account(db, "Electricity Expense", "Expense"),
            get_or_create_account(db, "Water Expense", "Expense"),
            get_or_create_account(db, "Rent Expense", "Expense"),
            get_or_create_account(db, "Marketing Expense", "Expense")
        ]

        # 5. Categories
        categories = db.query(models.Category).all()
        if not categories:
            cat_names = ["Food", "Drinks", "Electronics", "Clothing", "Home", "Rooms"]
            for name in cat_names:
                category = models.Category(name=name)
                db.add(category)
            db.flush()
            categories = db.query(models.Category).all()

        # 6. Products
        current_prod_count = db.query(models.Product).count()
        if current_prod_count < 1000:
            for i in range(current_prod_count + 1, 1001):
                price = round(random.uniform(10.0, 5000.0), 2)
                product = models.Product(
                    name=f"Product {i}",
                    category_id=random.choice(categories).id,
                    unit_id=random.choice(units).id,
                    tax_type_id=random.choice(taxes).id,
                    store_id=random.choice(stores).id,
                    selling_price=price,
                    cost_price=price * 0.7,
                    stock_quantity=random.randint(10, 500),
                    sku=f"SKU-{i:04d}-{random.randint(100,999)}",
                    is_service=False,
                    narrative=f"Massive seed product {i}"
                )
                db.add(product)
            db.flush()
            print(f"Added Products up to 1000.")
        
        products = db.query(models.Product).all()

        # 7. Staff
        staff_members = db.query(models.Staff).all()
        if not staff_members:
            roles = ['admin', 'waiter', 'cashier', 'kitchen']
            for i in range(1, 11):
                s = models.Staff(
                    name=f"Staff {i}",
                    username=f"staff{i}",
                    password_hash="hashed_password",
                    role=random.choice(roles),
                    phone=f"0722000{i:03d}"
                )
                db.add(s)
            db.flush()
            staff_members = db.query(models.Staff).all()

        # 8. Customers
        current_cust_count = db.query(models.Customer).count()
        if current_cust_count < 1000:
            for i in range(current_cust_count + 1, 1001):
                customer = models.Customer(
                    name=f"Customer {i}",
                    phone=f"0712345{i:03d}",
                    customer_type=random.choice(['new', 'regular', 'corporate'])
                )
                db.add(customer)
            db.flush()
            print(f"Added Customers up to 1000.")
        
        customers = db.query(models.Customer).all()

        # 9. Suppliers
        suppliers = db.query(models.Supplier).all()
        if not suppliers:
            for i in range(1, 21):
                supplier = models.Supplier(
                    name=f"Supplier {i}",
                    contact_person=f"Contact {i}",
                    phone=f"0733000{i:03d}",
                    balance=0.0
                )
                db.add(supplier)
            db.flush()
            suppliers = db.query(models.Supplier).all()

        # 10. Room Types & Rooms
        room_types = db.query(models.RoomType).all()
        if not room_types:
            rt_names = ["Single", "Double", "Deluxe", "Suite"]
            for name in rt_names:
                rt = models.RoomType(name=name, base_rate=random.uniform(2000, 10000))
                db.add(rt)
            db.flush()
            room_types = db.query(models.RoomType).all()

        rooms = db.query(models.Room).all()
        if not rooms:
            for i in range(1, 31):
                rt = random.choice(room_types)
                room = models.Room(
                    room_number=f"Room-{i:03d}",
                    room_type=rt.name,
                    price_per_night=rt.base_rate,
                    status="available"
                )
                db.add(room)
            db.flush()
            rooms = db.query(models.Room).all()

        # 11. Fiscal Year
        fiscal_year = db.query(models.FiscalYear).filter_by(year="2025").first()
        if not fiscal_year:
            fiscal_year = models.FiscalYear(year="2025", is_active=True)
            db.add(fiscal_year)
            db.flush()

        # 12. Seeding Transactions
        print("Seeding 1000 orders, 200 purchases, 200 bookings, 200 expenses...")
        
        # Orders
        for i in range(1, 1001):
            customer = random.choice(customers)
            waiter = random.choice([s for s in staff_members if s.role == 'waiter'] or staff_members)
            store = random.choice(stores)
            created_date = datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(0, 365))
            order = models.Order(
                customer_id=customer.id,
                waiter_id=waiter.id,
                store_id=store.id,
                status='paid',
                total_amount=0.0,
                created_at=created_date
            )
            db.add(order)
            db.flush()

            order_total = 0.0
            for _ in range(random.randint(1, 5)):
                prod = random.choice(products)
                qty = random.randint(1, 5)
                item = models.OrderItem(order_id=order.id, product_id=prod.id, quantity=qty, unit_price=prod.selling_price)
                db.add(item)
                order_total += (prod.selling_price * qty)
            
            order.total_amount = order_total
            
            # Payment
            cashier = random.choice([s for s in staff_members if s.role == 'cashier'] or staff_members)
            db.add(models.Payment(
                order_id=order.id, cashier_id=cashier.id, amount_paid=order_total,
                method=random.choice(['Cash', 'M-Pesa', 'Card']), paid_at=created_date
            ))

            # Journal Postings
            ref = f"ORD-{order.id}"
            db.add(models.JournalPosting(
                ref_no=f"DR-{ref}-{random.randint(100,999)}", account_id=cash_acc.id, customer_id=customer.id,
                amount=order_total, dr_cr='Debit', transaction_date=created_date, narrative=f"Order Payment #{order.id}"
            ))
            db.add(models.JournalPosting(
                ref_no=f"CR-{ref}-{random.randint(100,999)}", account_id=sales_acc.id, amount=order_total, dr_cr='Credit',
                transaction_date=created_date, narrative=f"Sales from Order #{order.id}"
            ))

            if i % 250 == 0: print(f"{i} orders seeded...")

        # Purchases
        for i in range(1, 201):
            supplier = random.choice(suppliers)
            store = random.choice(stores)
            purchase_date = datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(0, 365))
            purchase = models.Purchase(
                bill_no=f"BILL-{i:04d}-{random.randint(1000,9999)}",
                supplier_id=supplier.id,
                amount=0.0,
                store_id=store.id,
                purchase_date=purchase_date,
                status="Received"
            )
            db.add(purchase)
            db.flush()

            purchase_total = 0.0
            for _ in range(random.randint(2, 6)):
                prod = random.choice(products)
                qty = random.uniform(5, 50)
                item = models.PurchaseItem(
                    purchase_id=purchase.id, product_id=prod.id, quantity=qty,
                    unit_price=prod.cost_price, total_amount=qty * prod.cost_price
                )
                db.add(item)
                purchase_total += (qty * prod.cost_price)
            
            purchase.amount = purchase_total
            
            # Journal for Purchase
            db.add(models.JournalPosting(
                ref_no=f"PUR-{purchase.id}-DR-{random.randint(100,999)}", account_id=cogs_acc.id, supplier_id=supplier.id,
                amount=purchase_total, dr_cr='Debit', transaction_date=purchase_date, narrative=f"Purchase Bill #{purchase.bill_no}"
            ))
            db.add(models.JournalPosting(
                ref_no=f"PUR-{purchase.id}-CR-{random.randint(100,999)}", account_id=pay_acc.id, supplier_id=supplier.id,
                amount=purchase_total, dr_cr='Credit', transaction_date=purchase_date, narrative=f"Purchase Liability #{purchase.bill_no}"
            ))

        # Room Bookings
        for i in range(1, 201):
            room = random.choice(rooms)
            from_date = datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(0, 300))
            nights = random.randint(1, 7)
            to_date = from_date + datetime.timedelta(days=nights)
            booking = models.RoomBooking(
                room_id=room.id,
                customer_name=f"Guest {i}",
                customer_phone=f"0755000{i:03d}",
                from_date=from_date,
                to_date=to_date,
                nights=nights,
                booking_type=random.choice(["Bed Only", "BB", "HB", "FB"]),
                occupancy=random.randint(1, 2),
                total_amount=room.price_per_night * nights,
                paid_amount=room.price_per_night * nights,
                balance=0.0,
                payment_method="M-Pesa",
                status="checked_out",
                created_at=from_date
            )
            db.add(booking)
            
            # Revenue journal for booking
            db.add(models.JournalPosting(
                ref_no=f"BK-{i}-{random.randint(100,999)}", account_id=sales_acc.id, amount=booking.total_amount,
                dr_cr='Credit', transaction_date=from_date, narrative=f"Room Booking {room.room_number}"
            ))

        # Expenses
        for i in range(1, 201):
            store = random.choice(stores)
            acc = random.choice(expense_accs)
            amount = random.uniform(500, 20000)
            expense_date = datetime.datetime.utcnow() - datetime.timedelta(days=random.randint(0, 365))
            expense = models.Expense(
                ref_no=f"EXP-{i:04d}-{random.randint(1000,9999)}",
                store_id=store.id,
                account_id=acc.id,
                amount=amount,
                paid_to="Service Provider",
                expense_date=expense_date,
                status="Completed",
                narrative=f"Monthly {acc.name}"
            )
            db.add(expense)
            
            # Expense Journal
            db.add(models.JournalPosting(
                ref_no=f"J-EXP-{i}-{random.randint(100,999)}", account_id=acc.id, amount=amount,
                dr_cr='Debit', transaction_date=expense_date, narrative=f"Expense: {acc.name}"
            ))
            db.add(models.JournalPosting(
                ref_no=f"J-EXP-PY-{i}-{random.randint(100,999)}", account_id=cash_acc.id, amount=amount,
                dr_cr='Credit', transaction_date=expense_date, narrative=f"Payment for {acc.name}"
            ))

        db.commit()
        print("Massive seeding completed successfully!")

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        print(f"Error during seeding: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_massive_data()
