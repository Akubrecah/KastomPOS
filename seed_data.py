import sys
sys.path.insert(0, '.')
from database import SessionLocal, engine, Base
from models import *
import datetime, random
from hashlib import sha256

print("Dropping all tables to ensure clean schema state...")
Base.metadata.drop_all(bind=engine)
print("Creating all tables from SQLAlchemy models...")
Base.metadata.create_all(bind=engine)
db = SessionLocal()

def h(p): return sha256(p.encode()).hexdigest()

# Stores
stores = [Store(name="Main Restaurant", location="Ground Floor"), Store(name="Bar & Lounge", location="1st Floor"), Store(name="Main Store", location="Basement")]
db.add_all(stores); db.commit()
s1,s2,s3 = stores

# Units
units = [Unit(name="Piece"), Unit(name="Kg"), Unit(name="Litre"), Unit(name="Box"), Unit(name="Bottle")]
db.add_all(units); db.commit()

# Tax Types
taxes = [TaxType(name="VAT 16%", rate=16.0), TaxType(name="Exempt", rate=0.0)]
db.add_all(taxes); db.commit()

# Account Types
at1 = AccountType(name="Asset"); at2 = AccountType(name="Liability"); at3 = AccountType(name="Revenue"); at4 = AccountType(name="Expense"); at5 = AccountType(name="Equity")
db.add_all([at1,at2,at3,at4,at5]); db.commit()

# HR Constants
desigs = [HRConstant(category="designations", name=n) for n in ["Manager","Waiter","Chef","Cashier","Barman","Receptionist","Security","Housekeeper"]]
db.add_all(desigs); db.commit()
warnings = [HRConstant(category="warnings", name=n) for n in ["Verbal Warning","Written Warning","Final Warning"]]
awards = [HRConstant(category="awards", name=n) for n in ["Employee of Month","Best Performance","Long Service"]]
db.add_all(warnings+awards); db.commit()

# Staff
staff_data = [
    ("admin","Admin User","admin"),("james.mwangi","James Mwangi","manager"),
    ("grace.wanjiku","Grace Wanjiku","cashier"),("peter.ochieng","Peter Ochieng","waiter"),
    ("mary.njeri","Mary Njeri","waiter"),("john.kamau","John Kamau","chef"),
    ("alice.akinyi","Alice Akinyi","cashier"),("david.mutua","David Mutua","waiter"),
    ("sarah.chebet","Sarah Chebet","receptionist"),("paul.njoroge","Paul Njoroge","barman"),
]
staff_list = []
for i,(u,n,r) in enumerate(staff_data):
    s = Staff(username=u, password_hash=h("password123"), name=n, role=r, designation_id=desigs[i%len(desigs)].id, phone=f"07{random.randint(10000000,99999999)}", basic_salary=random.choice([35000,45000,55000,65000,80000,100000]))
    staff_list.append(s)
db.add_all(staff_list); db.commit()
admin = staff_list[0]; manager = staff_list[1]

# Accounts
accs = [
    Account(name="Cash in Hand", account_type="Asset", code="1001", balance=450000.0, account_type_id=at1.id, store_id=s1.id, is_key=True),
    Account(name="KCB Bank Account", account_type="Asset", code="1002", balance=1250000.0, account_type_id=at1.id, store_id=s1.id, is_key=True),
    Account(name="Mpesa Float", account_type="Asset", code="1003", balance=320000.0, account_type_id=at1.id, store_id=s1.id),
    Account(name="Food & Beverage Revenue", account_type="Revenue", code="4001", balance=850000.0, account_type_id=at3.id, store_id=s1.id, is_key=True),
    Account(name="Accommodation Revenue", account_type="Revenue", code="4002", balance=620000.0, account_type_id=at3.id, store_id=s1.id),
    Account(name="Bar Revenue", account_type="Revenue", code="4003", balance=280000.0, account_type_id=at3.id, store_id=s2.id),
    Account(name="Salaries Expense", account_type="Expense", code="5001", balance=420000.0, account_type_id=at4.id, store_id=s1.id, is_key=True),
    Account(name="Utilities Expense", account_type="Expense", code="5002", balance=85000.0, account_type_id=at4.id, store_id=s1.id),
    Account(name="Supplies Expense", account_type="Expense", code="5003", balance=120000.0, account_type_id=at4.id, store_id=s1.id),
    Account(name="Accounts Payable", account_type="Liability", code="2001", balance=180000.0, account_type_id=at2.id, store_id=s1.id),
    Account(name="Owner Equity", account_type="Equity", code="3001", balance=2000000.0, account_type_id=at5.id, store_id=s1.id),
    Account(name="Food Purchases", account_type="Expense", code="5004", balance=95000.0, account_type_id=at4.id, store_id=s1.id),
]
db.add_all(accs); db.commit()

# Categories
cats = [Category(name=n) for n in ["Food","Beverages","Spirits & Wines","Breakfast","Desserts","Room Service","Dry Goods","Toiletries"]]
db.add_all(cats); db.commit()

# Products
prod_data = [
    ("Grilled Tilapia","Food",850,420),("Nyama Choma (500g)","Food",950,430),("Chicken Biryani","Food",750,310),
    ("Ugali & Sukuma","Food",350,120),("Beef Stew","Food",650,280),("Fried Chips","Food",300,110),
    ("Mixed Salad","Food",350,130),("Vegetable Curry","Food",550,200),
    ("Tusker Lager","Beverages",250,120),("Soda 500ml","Beverages",100,40),("Fresh Juice","Beverages",200,80),
    ("Mineral Water","Beverages",80,30),("Coffee","Beverages",150,50),("Tea","Beverages",120,40),
    ("Whisky (Shot)","Spirits & Wines",400,180),("Red Wine (Glass)","Spirits & Wines",600,250),
    ("Gin & Tonic","Spirits & Wines",450,190),("Vodka (Shot)","Spirits & Wines",380,160),
    ("Full Breakfast","Breakfast",650,250),("Continental Breakfast","Breakfast",500,190),
    ("Chocolate Cake","Desserts",350,120),("Ice Cream","Desserts",250,90),
    ("Room Service Tray Fee","Room Service",150,50),
    ("Flour 2kg","Dry Goods",180,100),("Sugar 1kg","Dry Goods",120,65),("Cooking Oil 1L","Dry Goods",250,160),
    ("Soap Bar","Toiletries",60,30),("Shampoo","Toiletries",120,65),
]
products = []
for i,(name,cat,sp,cp) in enumerate(prod_data):
    c = next(x for x in cats if x.name==cat)
    p = Product(name=name, category_id=c.id, selling_price=sp, cost_price=cp, stock_quantity=random.randint(20,200), unit_id=units[0].id, tax_type_id=taxes[0].id, store_id=s3.id, sku=f"SKU{1000+i}", reorder_level=10)
    products.append(p)
db.add_all(products); db.commit()

# Customers
cust_names = [("James Kariuki","0722334455"),("Grace Waweru","0733445566"),("Peter Omondi","0711223344"),("Mary Kamau","0744556677"),("David Njoroge","0755667788"),("Sarah Mutua","0766778899"),("John Otieno","0777889900"),("Alice Maina","0788990011"),("Paul Kiprotich","0799001122"),("Esther Nyambura","0700112233"),("Robert Gitau","0711334455"),("Catherine Chebet","0722445566"),("Michael Oloo","0733556677"),("Purity Wanjiku","0744667788"),("Kevin Achieng","0755778899")]
customers = [Customer(name=n, phone=p, customer_type=random.choice(["regular","new","vip"])) for n,p in cust_names]
db.add_all(customers); db.commit()

# Suppliers
suppliers_data = [("Nairobi Meats Ltd","Samuel Weru","0722100200"),("Kenya Breweries","John Otieno","0733200300"),("Fresh Farms Produce","Anne Chebet","0744300400"),("Bidco Oils","Mark Kimani","0755400500"),("Metro Wholesale","Lucy Njoki","0766500600")]
suppliers = [Supplier(name=n, contact_person=c, phone=p, balance=random.uniform(10000,80000)) for n,c,p in suppliers_data]
db.add_all(suppliers); db.commit()

# Rooms
room_types = ["Standard Single","Standard Double","Deluxe Double","Family Room","Executive Suite"]
rooms = []
for i in range(1,21):
    rt = room_types[i%len(room_types)]
    base = [3500,5500,7500,9500,15000][i%5]
    rooms.append(Room(room_number=f"{100+i}", room_type=rt, category="Standard" if base<7000 else "Premium", price_per_night=float(base), bb_s=base+500.0, hb_s=base+1200.0, fb_s=base+2000.0, bed_only_d=base+1500.0, bb_d=base+2000.0, hb_d=base+2800.0, fb_d=base+3500.0, status=random.choice(["available","available","available","occupied","maintenance"])))
db.add_all(rooms); db.commit()

# Room Bookings
booking_types = ["Bed Only","Bed & Breakfast","Half Board","Full Board"]
sources = ["Walk-in","Online","Phone"]
booking_names = [("Kamau James","0712334455"),("Auma Grace","0723445566"),("Mwamba Peter","0734556677"),("Chebet Sarah","0745667788"),("Otieno David","0756778899"),("Wanjiku Rose","0767889900"),("Gitau Kevin","0778990011"),("Njeri Alice","0789001122"),("Omondi Paul","0790112233"),("Maina Esther","0701223344")]
bookings = []
for i,room in enumerate(rooms[:10]):
    nm,ph = booking_names[i]
    fd = datetime.datetime.now() - datetime.timedelta(days=random.randint(1,60))
    nights = random.randint(1,5)
    td = fd + datetime.timedelta(days=nights)
    total = room.price_per_night * nights
    paid = total * random.choice([0.5,0.75,1.0])
    b = RoomBooking(room_id=room.id, customer_name=nm, customer_phone=ph, from_date=fd, to_date=td, nights=nights, booking_type=random.choice(booking_types), occupancy=random.randint(1,3), total_amount=total, paid_amount=paid, balance=total-paid, payment_method=random.choice(["Cash","Mpesa","Bank Transfer"]), status=random.choice(["active","checked_out","active"]), source=random.choice(sources))
    bookings.append(b)
db.add_all(bookings); db.commit()

# Orders & Payments
methods = ["Cash","Mpesa","Card"]
# Create 50 historical orders
for i in range(50):
    cust = random.choice(customers)
    waiter = random.choice(staff_list[3:8])
    dt = datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 90), hours=random.randint(0, 12))
    order = Order(customer_id=cust.id, waiter_id=waiter.id, table_number=str(random.randint(1,20)), status=random.choice(["closed","closed","closed","open"]), store_id=s1.id, created_at=dt)
    db.add(order); db.flush()
    total = 0
    for _ in range(random.randint(1,4)):
        prod = random.choice(products[:22])
        qty = random.randint(1,3)
        item = OrderItem(order_id=order.id, product_id=prod.id, quantity=qty, unit_price=prod.selling_price)
        db.add(item); total += qty * prod.selling_price
    order.total_amount = total
    if order.status == "closed":
        cashier = random.choice(staff_list[2:4])
        pay = Payment(order_id=order.id, cashier_id=cashier.id, amount_paid=total, method=random.choice(methods), paid_at=dt)
        db.add(pay)
        rec = Receipt(order_id=order.id, receipt_number=f"RCP{10000+i}", generated_at=dt)
        db.add(rec)

# Create 10 orders for today specifically
for i in range(10):
    cust = random.choice(customers)
    waiter = random.choice(staff_list[3:8])
    # Distribute within the current day (some hours ago)
    dt = datetime.datetime.now() - datetime.timedelta(hours=random.randint(1, 10))
    # 8 closed (paid), 2 open (unpaid)
    status = "closed" if i < 8 else "open"
    order = Order(customer_id=cust.id, waiter_id=waiter.id, table_number=str(random.randint(1,20)), status=status, store_id=s1.id, created_at=dt)
    db.add(order); db.flush()
    total = 0
    for _ in range(random.randint(1,4)):
        prod = random.choice(products[:22])
        qty = random.randint(1,3)
        item = OrderItem(order_id=order.id, product_id=prod.id, quantity=qty, unit_price=prod.selling_price)
        db.add(item); total += qty * prod.selling_price
    order.total_amount = total
    if order.status == "closed":
        cashier = random.choice(staff_list[2:4])
        pay = Payment(order_id=order.id, cashier_id=cashier.id, amount_paid=total, method=random.choice(methods), paid_at=dt)
        db.add(pay)
        rec = Receipt(order_id=order.id, receipt_number=f"RCP{20000+i}", generated_at=dt)
        db.add(rec)
db.commit()

# Banquets
event_names = [("Mwangi Wedding Reception","James Mwangi","0722334455"),("Omondi Corporate Dinner","Omondi Events","0733445566"),("Kamau Birthday Party","Mary Kamau","0744556677"),("Nairobi Business Forum","KBC Ltd","0755667788"),("Chebet Anniversary","Peter Chebet","0766778899")]
for i,(ev,cust_name,phone) in enumerate(event_names):
    cust = random.choice(customers)
    staff = random.choice(staff_list[1:4])
    ev_date = datetime.datetime.now() + datetime.timedelta(days=random.randint(-30,60))
    banq = Banquet(customer_id=cust.id, staff_id=staff.id, total_amount=0, tax_amount=0, status=random.choice(["pending","confirmed","completed"]), event_date=ev_date, store_id=s1.id)
    db.add(banq); db.flush()
    total = 0
    for _ in range(random.randint(3,6)):
        prod = random.choice(products[:10])
        qty = random.randint(10,50)
        bi = BanquetItem(banquet_id=banq.id, product_id=prod.id, quantity=qty, unit_price=prod.selling_price)
        db.add(bi); total += qty * prod.selling_price
    banq.total_amount = total; banq.tax_amount = total * 0.16
db.commit()

# Purchases
bill_nums = [f"PO{2024001+i}" for i in range(30)]
for i in range(30):
    sup = random.choice(suppliers)
    att = random.choice(staff_list[1:4])
    pd = datetime.datetime.now() - datetime.timedelta(days=random.randint(1,90))
    purch = Purchase(bill_no=bill_nums[i], supplier_id=sup.id, attendant_id=att.id, amount=0, balance=0, purchase_date=pd, status=random.choice(["Received","Received","LPO"]), store_id=s3.id)
    db.add(purch); db.flush()
    total = 0
    for _ in range(random.randint(2,5)):
        prod = random.choice(products[22:])
        qty = random.randint(5,50)
        up = prod.cost_price
        ta = qty * up * 0.16
        pi = PurchaseItem(purchase_id=purch.id, product_id=prod.id, quantity=qty, unit_price=up, tax_rate=16.0, tax_amount=ta, total_amount=qty*up+ta, unit_id=units[0].id)
        db.add(pi); total += qty*up+ta
    purch.amount = total; purch.balance = total * random.choice([0.0,0.5,1.0])
db.commit()

# Expenses
exp_descs = [("KPLC Electricity","Kenya Power"),("Water Bill","Nairobi City Water"),("Internet & WIFI","Safaricom Business"),("Cleaning Supplies","Metro Wholesale"),("Security Services","G4S Kenya"),("Maintenance","Handyman Services"),("Newspaper & Stationery","Text Book Centre"),("Fuel for Generator","Total Energies")]
for i,( narr, paid_to) in enumerate(exp_descs*2):
    ed = datetime.datetime.now() - datetime.timedelta(days=random.randint(1,60))
    exp = Expense(ref_no=f"EXP{3000+i}", store_id=s1.id, account_id=accs[7].id, payable_id=accs[9].id, amount=random.uniform(5000,45000), balance=0, paid_to=paid_to, expense_date=ed, status=random.choice(["Completed","Pending","Approved"]), narrative=narr)
    db.add(exp)
db.commit()

# Quotations
for i in range(10):
    cust = random.choice(customers)
    st = random.choice(staff_list[1:4])
    q = Quotation(customer_id=cust.id, staff_id=st.id, total_amount=0, tax_amount=0, status=random.choice(["pending","approved","rejected"]))
    db.add(q); db.flush()
    total = 0
    for _ in range(random.randint(2,4)):
        prod = random.choice(products[:15])
        qty = random.randint(1,10)
        qi = QuotationItem(quotation_id=q.id, product_id=prod.id, quantity=qty, unit_price=prod.selling_price)
        db.add(qi); total += qty * prod.selling_price
    q.total_amount = total; q.tax_amount = total * 0.16
db.commit()

# Fiscal Year & Payroll
fy = FiscalYear(year="2024/2025", is_active=True)
db.add(fy); db.commit()

for emp in staff_list[1:]:
    for month in range(1,6):
        basic = emp.basic_salary
        allow = basic * 0.15
        gross = basic + allow
        nssf = 200.0; sha = gross * 0.0275; housing = gross * 0.015
        paye = max(0, (gross - 24000) * 0.25)
        net = gross - nssf - sha - housing - paye
        pr = PayrollRecord(employee_id=emp.id, store_id=s1.id, fiscal_year_id=fy.id, month=month, basic_salary=basic, allowances=allow, gross_salary=gross, nssf=nssf, sha=sha, housing_levy=housing, paye=paye, net_salary=net, status=random.choice(["Paid","Paid","Pending"]))
        db.add(pr)
db.commit()

# Leave Types & Applications
lt_data = [("Annual Leave",21),("Sick Leave",14),("Maternity Leave",90),("Paternity Leave",14),("Compassionate Leave",5)]
leave_types = [LeaveType(name=n, days_per_year=d) for n,d in lt_data]
db.add_all(leave_types); db.commit()

for i in range(8):
    emp = random.choice(staff_list[1:])
    lt = random.choice(leave_types)
    sd = datetime.date.today() - datetime.timedelta(days=random.randint(10,120))
    days = random.randint(2,10)
    ed = sd + datetime.timedelta(days=days)
    la = LeaveApplication(employee_id=emp.id, leave_type_id=lt.id, start_date=sd, end_date=ed, total_days=days, reason="Personal reasons", status=random.choice(["Approved","Pending","Rejected"]), approved_by_id=manager.id)
    db.add(la)
db.commit()

# Settings
settings_data = [
    ("business_name", "KastomPOS"),
    ("email", "info@kastompos.co.ke"),
    ("phone", "+254 700 123456"),
    ("location", "Kimathi Street, Nairobi, Kenya"),
    ("logo_url", ""),
    ("currency", "KES"),
    ("country", "Kenya"),
    ("tax_rate", "16.0"),
    ("fiscal_start", "2026-01-01"),
    ("receipt_footer", "Thank you for choosing KastomPOS. Powered by KastomPOS ERP."),
    ("sms_gateway", "disabled")
]
for k, v in settings_data:
    existing = db.query(Setting).filter(Setting.key == k).first()
    if not existing:
        db.add(Setting(key=k, value=v))
    else:
        existing.value = v
db.commit()

# Incomes
inc_descs = [("Conference Hall Booking","Safaricom PLC"),("Wedding Hall","Mwangi Wedding"),("Parking Fees","Various"),("Laundry Services","Hotel Guests")]
for i,(narr,cname) in enumerate(inc_descs*3):
    inc = Income(ref_no=f"INC{4000+i}", account_id=accs[3].id, amount=random.uniform(15000,150000), balance=0, customer_name=cname, income_date=datetime.datetime.now()-datetime.timedelta(days=random.randint(1,60)), status="Completed", store_id=s1.id, narrative=narr)
    db.add(inc)
db.commit()

# HR Awards & Warnings
for i in range(5):
    emp = random.choice(staff_list[1:])
    aw_type = next(x for x in awards if x.name=="Employee of Month")
    db.add(HRAward(staff_id=emp.id, award_type_id=aw_type.id, award_date=datetime.date.today()-datetime.timedelta(days=random.randint(10,90)), gift="Certificate + Hamper", cash=5000.0, description="Exceptional service delivery"))
for i in range(3):
    emp = random.choice(staff_list[3:])
    wt = random.choice(warnings)
    db.add(HRWarning(staff_id=emp.id, warning_type_id=wt.id, warning_date=datetime.date.today()-datetime.timedelta(days=random.randint(5,60)), description="Late reporting to duty"))
db.commit()

# Departments
depts = [Department(name=n, store_id=s1.id) for n in ["Kitchen","Front Office","Housekeeping","Bar & Restaurant","Finance","Security"]]
db.add_all(depts); db.commit()

# Payroll Constants
pc_data = [("allowances","House Allowance",False),("allowances","Transport Allowance",False),("allowances","Airtime Allowance",False),("deductions","SACCO Loan",True),("deductions","Staff Canteen",False)]
for cat,name,taxable in pc_data:
    db.add(PayrollConstant(category=cat, name=name, is_taxable=taxable, is_active=True))
db.commit()

# Salary Advances
for i in range(4):
    emp = random.choice(staff_list[2:])
    db.add(SalaryAdvance(employee_id=emp.id, fiscal_year_id=fy.id, month=random.randint(1,5), amount=random.uniform(5000,20000), is_disbursed=True, is_recovered=False, narrative="Emergency advance"))
db.commit()

# Audit Logs
actions = ["Login","Logout","Created Order","Voided Item","Processed Payment","Updated Product","Added Customer","Generated Receipt"]
for i in range(20):
    st = random.choice(staff_list)
    db.add(AuditLog(staff_id=st.id, action=random.choice(actions), details=f"Action performed by {st.name}", timestamp=datetime.datetime.now()-datetime.timedelta(hours=random.randint(1,720))))
db.commit()

# MpesaPayments
for i in range(15):
    db.add(MpesaPayment(reference=f"QJK{random.randint(100000,999999)}ABC", account_no=f"ORDER{random.randint(1000,9999)}", amount=random.uniform(500,5000), name=random.choice(customers).name, status="Paid"))
db.commit()

# Requisitions
for i in range(6):
    req_person = random.choice(staff_list[3:])
    req = Requisition(code=f"REQ{5000+i}", receiving_store_id=s1.id, issuing_store_id=s3.id, request_person_id=req_person.id, approved_by_id=manager.id, priority=random.choice(["High","Medium","Low"]), request_type="Internal", status=random.choice(["Pending","Approved","Completed"]))
    db.add(req); db.flush()
    for _ in range(random.randint(2,4)):
        prod = random.choice(products[22:])
        db.add(RequisitionItem(requisition_id=req.id, product_id=prod.id, quantity=random.randint(5,20), unit_price=prod.cost_price))
db.commit()

# Petty Cash
for i in range(8):
    req_by = random.choice(staff_list[2:])
    db.add(PettyCashRequest(ref_no=f"PCR{6000+i}", store_id=s1.id, requested_by_id=req_by.id, amount=random.uniform(500,5000), request_date=datetime.datetime.now()-datetime.timedelta(days=random.randint(1,30)), status=random.choice(["Pending","Approved","Completed"]), narrative=random.choice(["Kitchen supplies","Office stationery","Cleaning materials","Generator fuel"])))
db.commit()

# Wastage
for i in range(5):
    prod = random.choice(products[:10])
    db.add(Wastage(ref_no=f"WST{7000+i}", product_id=prod.id, store_id=s3.id, quantity=random.uniform(0.5,5), cost=prod.cost_price * random.uniform(0.5,5), occurrence_date=datetime.datetime.now()-datetime.timedelta(days=random.randint(1,30)), narrative="Spoilage during storage", expense_account_id=accs[8].id, created_by=admin.id))
db.commit()

# Attendance (last 7 days)
for day_back in range(7):
    d = datetime.datetime.now() - datetime.timedelta(days=day_back)
    for emp in staff_list[1:8]:
        ci = d.replace(hour=8, minute=random.randint(0,30))
        co = d.replace(hour=17, minute=random.randint(0,30))
        db.add(Attendance(employee_id=emp.id, store_id=s1.id, check_in=ci, check_out=co, status="Out"))
db.commit()

db.close()
print("Seed complete! Database populated with realistic KastomPOS data.")
