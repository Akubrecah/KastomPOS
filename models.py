from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, Text, Date
from sqlalchemy.orm import relationship
from database import Base
import datetime

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    phone = Column(String, index=True)
    customer_type = Column(String, default="new")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    orders = relationship("Order", back_populates="customer")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    image_url = Column(String, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    selling_price = Column(Float)
    cost_price = Column(Float)
    stock_quantity = Column(Integer, default=0)
    is_service = Column(Boolean, default=False)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    tax_type_id = Column(Integer, ForeignKey("tax_types.id"), nullable=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    sku = Column(String, unique=True, index=True, nullable=True)
    brand = Column(String, nullable=True)
    color = Column(String, nullable=True)
    reorder_level = Column(Integer, default=0)
    narrative = Column(String, nullable=True)
    purpose = Column(String, default="For Sale") # For Sale, For Production, Fixed Asset
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    category = relationship("Category", back_populates="products")
    unit = relationship("Unit")
    tax_type = relationship("TaxType")
    store = relationship("Store")
    recipe_items = relationship("ProductRecipe", back_populates="product", foreign_keys="[ProductRecipe.product_id]")

class Ingredient(Base):
    __tablename__ = "ingredients"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    unit = Column(String)
    stock_quantity = Column(Float, default=0)
    cost_per_unit = Column(Float)

class ProductRecipe(Base):
    __tablename__ = "product_recipes"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    component_id = Column(Integer, ForeignKey("products.id"))
    quantity_required = Column(Float)
    
    product = relationship("Product", back_populates="recipe_items", foreign_keys=[product_id])
    component = relationship("Product", foreign_keys=[component_id])

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    waiter_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    table_number = Column(String, nullable=True)
    status = Column(String, default="open")
    total_amount = Column(Float, default=0.0)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    is_stamped = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    store = relationship("Store")
    
    customer = relationship("Customer", back_populates="orders")
    waiter = relationship("Staff", foreign_keys=[waiter_id])
    items = relationship("OrderItem", back_populates="order")
    payments = relationship("Payment", back_populates="order")
    receipt = relationship("Receipt", uselist=False, backref="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    unit_price = Column(Float)
    note = Column(String, nullable=True)
    is_voided = Column(Boolean, default=False)
    
    order = relationship("Order", back_populates="items")
    product = relationship("Product")

class Quotation(Base):
    __tablename__ = "quotations"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    total_amount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    customer = relationship("Customer")
    staff = relationship("Staff")
    items = relationship("QuotationItem", back_populates="quotation")

class QuotationItem(Base):
    __tablename__ = "quotation_items"
    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("quotations.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    unit_price = Column(Float)
    
    quotation = relationship("Quotation", back_populates="items")
    product = relationship("Product")

class Banquet(Base):
    __tablename__ = "banquets"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    total_amount = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    status = Column(String, default="pending")
    event_date = Column(DateTime, nullable=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    customer = relationship("Customer")
    staff = relationship("Staff")
    store = relationship("Store")
    items = relationship("BanquetItem", back_populates="banquet")

class BanquetItem(Base):
    __tablename__ = "banquet_items"
    id = Column(Integer, primary_key=True, index=True)
    banquet_id = Column(Integer, ForeignKey("banquets.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    unit_price = Column(Float)
    
    banquet = relationship("Banquet", back_populates="items")
    product = relationship("Product")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    cashier_id = Column(Integer, ForeignKey("staff.id"))
    amount_paid = Column(Float)
    method = Column(String)
    paid_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    order = relationship("Order", back_populates="payments")
    cashier = relationship("Staff")

class Receipt(Base):
    __tablename__ = "receipts"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    receipt_number = Column(String, unique=True)
    kra_control_number = Column(String, nullable=True)
    generated_at = Column(DateTime, default=datetime.datetime.utcnow)

# --- ERP & SUPPLIER MODELS ---

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    contact_person = Column(String)
    phone = Column(String)
    balance = Column(Float, default=0.0)

class SMSOutbox(Base):
    __tablename__ = "sms_outbox"
    id = Column(Integer, primary_key=True, index=True)
    recipient = Column(String)
    message = Column(Text)
    status = Column(String, default="pending")
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)

class Store(Base):
    __tablename__ = "stores"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    location = Column(String)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    account_type = Column(String, nullable=True) # Legacy: Asset, Liability, Equity, Revenue, Expense
    account_type_id = Column(Integer, ForeignKey("account_types.id"), nullable=True)
    subaccount_type_id = Column(Integer, ForeignKey("account_types.id"), nullable=True)
    code = Column(String, unique=True, nullable=True)
    balance = Column(Float, default=0.0)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    other_category = Column(String, nullable=True) # CA, NCA, CL, NCL
    narrative = Column(Text, nullable=True)
    is_key = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    store = relationship("Store")
    type = relationship("AccountType", foreign_keys=[account_type_id])
    sub_type = relationship("AccountType", foreign_keys=[subaccount_type_id])
    user = relationship("Staff")

class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    description = Column(String, nullable=True)

class TaxType(Base):
    __tablename__ = "tax_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    rate = Column(Float, default=0.0)

class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True, index=True)
    bill_no = Column(String, unique=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    attendant_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    amount = Column(Float)  # Net Amount
    balance = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    purchase_date = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default="Received")  # LPO, Received, Cancelled
    payment_schedule_id = Column(Integer, ForeignKey("payment_schedules.id"), nullable=True)
    
    supplier = relationship("Supplier")
    attendant = relationship("Staff")
    store = relationship("Store")
    payment_schedule = relationship("PaymentSchedule", back_populates="purchases")
    items = relationship("PurchaseItem", back_populates="purchase")

class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    id = Column(Integer, primary_key=True, index=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    description = Column(String, nullable=True)
    quantity = Column(Float)
    unit_price = Column(Float)
    tax_rate = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    total_amount = Column(Float)
    unit_id = Column(Integer, ForeignKey("units.id"), nullable=True)
    
    purchase = relationship("Purchase", back_populates="items")
    product = relationship("Product")
    unit = relationship("Unit")

class Expense(Base):
    __tablename__ = "expenses"
    id = Column(Integer, primary_key=True, index=True)
    ref_no = Column(String, unique=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    account_id = Column(Integer, ForeignKey("accounts.id")) # Expense Type
    payable_id = Column(Integer, ForeignKey("accounts.id"), nullable=True) # Payable Account
    amount = Column(Float)
    balance = Column(Float, default=0.0)
    paid_to = Column(String)
    expense_date = Column(DateTime, default=datetime.datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
    status = Column(String, default="Pending") # Completed, Approved, Pending, Cancelled, etc.
    narrative = Column(Text, nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    store = relationship("Store")
    expense_account = relationship("Account", foreign_keys=[account_id])
    payable_account = relationship("Account", foreign_keys=[payable_id])
    purchase = relationship("Purchase")

class Cheque(Base):
    __tablename__ = "cheques"
    id = Column(Integer, primary_key=True, index=True)
    cheque_number = Column(String, unique=True)
    amount = Column(Float)
    due_date = Column(DateTime)
    status = Column(String, default="pending")

class PaymentSchedule(Base):
    __tablename__ = "payment_schedules"
    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String, unique=True, index=True)
    status = Column(String, default="Suspended") # Suspended, Approved, Completed
    date = Column(DateTime, default=datetime.datetime.utcnow)
    amount = Column(Float, default=0.0)
    narrative = Column(String, nullable=True)
    created_by_id = Column(Integer, ForeignKey("staff.id"))
    
    created_by = relationship("Staff")
    purchases = relationship("Purchase", back_populates="payment_schedule")

class Setting(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(String)

class Staff(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String, default="waiter")
    designation_id = Column(Integer, ForeignKey("hr_constants.id"), nullable=True)
    id_number = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    basic_salary = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    designation = relationship("HRConstant")

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String, unique=True, index=True)
    room_type = Column(String)
    category = Column(String, nullable=True)
    price_per_night = Column(Float) # Bed Only Single
    day_rest_s = Column(Float, default=0.0)
    bb_s = Column(Float, default=0.0)
    hb_s = Column(Float, default=0.0)
    fb_s = Column(Float, default=0.0)
    day_rest_d = Column(Float, default=0.0)
    bed_only_d = Column(Float, default=0.0)
    bb_d = Column(Float, default=0.0)
    hb_d = Column(Float, default=0.0)
    fb_d = Column(Float, default=0.0)
    status = Column(String, default="available") # available, occupied, maintenance, cleaning
    narrative = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class RoomType(Base):
    __tablename__ = "room_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    base_rate = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class RevenueAllocation(Base):
    __tablename__ = "revenue_allocations"
    id = Column(Integer, primary_key=True, index=True)
    meal_plan = Column(String, unique=True) # e.g., "Bed & Breakfast", "Half Board", "Full Board"
    food_revenue = Column(Float, default=0.0)
    accommodation_revenue = Column(Float, default=0.0)
    beverage_revenue = Column(Float, default=0.0)
    hall_revenue = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class RoomBooking(Base):
    __tablename__ = "room_bookings"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"))
    customer_name = Column(String)
    customer_phone = Column(String)
    from_date = Column(DateTime)
    to_date = Column(DateTime)
    nights = Column(Integer)
    booking_type = Column(String) # Meal plan or type
    occupancy = Column(Integer)
    narrative = Column(Text, nullable=True)
    total_amount = Column(Float)
    paid_amount = Column(Float)
    balance = Column(Float)
    payment_method = Column(String)
    reference = Column(String, nullable=True)
    status = Column(String, default="active") # active, checked_out, cancelled
    source = Column(String, default="Walk-in") # Walk-in or Online
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    room = relationship("Room", backref="bookings")

class Printer(Base):
    __tablename__ = "printers"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    ip_address = Column(String, nullable=True)
    port = Column(Integer, default=9100)
    printer_type = Column(String)
    is_default = Column(Boolean, default=False)

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    action = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    details = Column(String)
    staff = relationship("Staff")

class VoidLog(Base):
    __tablename__ = "void_logs"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    item_id = Column(Integer, ForeignKey("order_items.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    reason = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    staff = relationship("Staff")
    order = relationship("Order")

class ProductSerial(Base):
    __tablename__ = "product_serials"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    serial_number = Column(String, unique=True, index=True)
    condition = Column(String, default="Good") # Good, Damaged, Refurbished
    narrative = Column(String, nullable=True)
    status = Column(String, default="available") # available, sold, reserved
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    product = relationship("Product")

class Requisition(Base):
    __tablename__ = "requisitions"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    receiving_store_id = Column(Integer, ForeignKey("stores.id"))
    issuing_store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    request_person_id = Column(Integer, ForeignKey("staff.id"))
    approved_by_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    priority = Column(String, default="Medium")
    request_type = Column(String, default="Internal")
    status = Column(String, default="Pending") # Pending, Approved, Completed, Cancelled
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    receiving_store = relationship("Store", foreign_keys=[receiving_store_id])
    issuing_store = relationship("Store", foreign_keys=[issuing_store_id])
    supplier = relationship("Supplier")
    request_person = relationship("Staff", foreign_keys=[request_person_id])
    approved_by = relationship("Staff", foreign_keys=[approved_by_id])
    items = relationship("RequisitionItem", back_populates="requisition")

class RequisitionItem(Base):
    __tablename__ = "requisition_items"
    id = Column(Integer, primary_key=True, index=True)
    requisition_id = Column(Integer, ForeignKey("requisitions.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Float)
    unit_price = Column(Float, nullable=True)
    narrative = Column(String, nullable=True)
    
    requisition = relationship("Requisition", back_populates="items")
    product = relationship("Product")

class ProductStoreStock(Base):
    __tablename__ = "product_store_stock"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    quantity = Column(Float, default=0.0)
    last_stock_take = Column(DateTime, nullable=True)
    
    product = relationship("Product")
    store = relationship("Store")

class StockTakeInstance(Base):
    __tablename__ = "stock_take_instances"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    reference = Column(String, unique=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    status = Column(String, default="Pending") # Pending, Completed, Reconciled
    narrative = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    reconciled_at = Column(DateTime, nullable=True)
    reconciliation_value = Column(Float, default=0.0)
    
    store = relationship("Store")
    items = relationship("StockTakeItem", back_populates="instance")

class StockTakeItem(Base):
    __tablename__ = "stock_take_items"
    id = Column(Integer, primary_key=True, index=True)
    instance_id = Column(Integer, ForeignKey("stock_take_instances.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    expected_quantity = Column(Float)
    actual_quantity = Column(Float, nullable=True)
    variance = Column(Float, nullable=True)
    
    instance = relationship("StockTakeInstance", back_populates="items")
    product = relationship("Product")

class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String, unique=True)
    from_store_id = Column(Integer, ForeignKey("stores.id"))
    to_store_id = Column(Integer, ForeignKey("stores.id"))
    movement_type = Column(String, default="Direct") # Direct, Cost
    status = Column(String, default="Completed")
    issued_to_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    narrative = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    from_store = relationship("Store", foreign_keys=[from_store_id])
    to_store = relationship("Store", foreign_keys=[to_store_id])
    issued_to = relationship("Staff")
    items = relationship("StockMovementItem", back_populates="movement")

class StockMovementItem(Base):
    __tablename__ = "stock_movement_items"
    id = Column(Integer, primary_key=True, index=True)
    movement_id = Column(Integer, ForeignKey("stock_movements.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Float)
    cost_price = Column(Float, nullable=True)
    
    movement = relationship("StockMovement", back_populates="items")
    product = relationship("Product")

class Wastage(Base):
    __tablename__ = "wastages"
    id = Column(Integer, primary_key=True, index=True)
    ref_no = Column(String, unique=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    quantity = Column(Float)
    cost = Column(Float) # Total cost (qty * unit_cost)
    occurrence_date = Column(DateTime)
    narrative = Column(Text)
    expense_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    asset_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    product = relationship("Product")
    store = relationship("Store")
    expense_account = relationship("Account", foreign_keys=[expense_account_id])
    asset_account = relationship("Account", foreign_keys=[asset_account_id])
    user = relationship("Staff")

class Depreciation(Base):
    __tablename__ = "depreciations"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True)
    asset_account_id = Column(Integer, ForeignKey("accounts.id"))
    expense_account_id = Column(Integer, ForeignKey("accounts.id"))
    amount = Column(Float)
    narrative = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    asset_account = relationship("Account", foreign_keys=[asset_account_id])
    expense_account = relationship("Account", foreign_keys=[expense_account_id])

class MpesaPayment(Base):
    __tablename__ = "mpesa_payments"
    id = Column(Integer, primary_key=True, index=True)
    reference = Column(String, unique=True, index=True)
    account_no = Column(String)
    amount = Column(Float)
    name = Column(String)
    status = Column(String, default="Paid")
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    order = relationship("Order")

class MpesaCallback(Base):
    __tablename__ = "mpesa_callbacks"
    id = Column(Integer, primary_key=True, index=True)
    mpesa_code = Column(String, unique=True, index=True, nullable=True)
    order_code = Column(String, index=True)
    amount = Column(Float)
    phone = Column(String)
    name = Column(String, nullable=True)
    status = Column(String, default="Success")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class ItemReturn(Base):
    __tablename__ = "item_returns"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    qty = Column(Float)
    return_type = Column(String)  # 'Sale' or 'Purchase'
    condition = Column(String)    # 'Good' or 'Spoilt'
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=True)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    narrative = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    product = relationship("Product")
    staff = relationship("Staff")
    order = relationship("Order")
    order = relationship("Order")
    purchase = relationship("Purchase")

class FiscalYear(Base):
    __tablename__ = "fiscal_years"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    quarter = Column(Integer) # 1, 2, 3, 4
    amount = Column(Float, default=0.0)
    practical_amount = Column(Float, default=0.0) # Actual spent
    narrative = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    staff = relationship("Staff")
    fiscal_year = relationship("FiscalYear")
    account = relationship("Account")

class PettyCashRequest(Base):
    __tablename__ = "petty_cash_requests"
    id = Column(Integer, primary_key=True, index=True)
    ref_no = Column(String, unique=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    requested_by_id = Column(Integer, ForeignKey("staff.id"))
    amount = Column(Float, default=0.0)
    request_date = Column(DateTime)
    status = Column(String, default="Pending") # Pending, Approved, Cancelled, Completed
    narrative = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    store = relationship("Store")
    requested_by = relationship("Staff")

class Department(Base):
    __tablename__ = "departments"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    store = relationship("Store")

class AccountType(Base):
    __tablename__ = "account_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    parent_id = Column(Integer, ForeignKey("account_types.id"), nullable=True)
    
    parent = relationship("AccountType", remote_side=[id], backref="sub_types")

class Income(Base):
    __tablename__ = "incomes"
    id = Column(Integer, primary_key=True, index=True)
    ref_no = Column(String, unique=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    amount = Column(Float, default=0.0)
    balance = Column(Float, default=0.0)
    customer_name = Column(String)
    income_date = Column(DateTime)
    status = Column(String, default="Completed")
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    narrative = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    account = relationship("Account")
    store = relationship("Store")
    department = relationship("Department")

class BankTransfer(Base):
    __tablename__ = "bank_transfers"
    id = Column(Integer, primary_key=True, index=True)
    ref_no = Column(String, unique=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    from_account_id = Column(Integer, ForeignKey("accounts.id"))
    to_account_id = Column(Integer, ForeignKey("accounts.id"))
    amount = Column(Float, default=0.0)
    transaction_date = Column(DateTime)
    reference = Column(String, nullable=True)
    narrative = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    store = relationship("Store")
    from_account = relationship("Account", foreign_keys=[from_account_id])
    to_account = relationship("Account", foreign_keys=[to_account_id])
    created_by = relationship("Staff")

class JournalPosting(Base):
    __tablename__ = "journal_postings"
    id = Column(Integer, primary_key=True, index=True)
    ref_no = Column(String, unique=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"))
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    amount = Column(Float, default=0.0)
    dr_cr = Column(String) # Debit or Credit
    transaction_date = Column(DateTime)
    reference = Column(String, nullable=True)
    narrative = Column(Text, nullable=True)
    created_by_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    store = relationship("Store")
    fiscal_year = relationship("FiscalYear")
    account = relationship("Account")
    customer = relationship("Customer")
    supplier = relationship("Supplier")
    created_by = relationship("Staff")

class HRConstant(Base):
    __tablename__ = "hr_constants"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True) # warnings, awards, terminations, documents, designations
    name = Column(String, index=True)
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class HRAward(Base):
    __tablename__ = "hr_awards"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    award_type_id = Column(Integer, ForeignKey("hr_constants.id"))
    award_date = Column(Date)
    gift = Column(String, nullable=True)
    cash = Column(Float, default=0.0)
    description = Column(String, nullable=True)
    attachment_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    staff = relationship("Staff")
    award_type = relationship("HRConstant")

class HRWarning(Base):
    __tablename__ = "hr_warnings"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    warning_type_id = Column(Integer, ForeignKey("hr_constants.id"))
    warning_date = Column(Date)
    description = Column(String, nullable=True)
    attachment_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    staff = relationship("Staff")
    warning_type = relationship("HRConstant")

class HRResignation(Base):
    __tablename__ = "hr_resignations"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    notice_date = Column(Date)
    resignation_date = Column(Date)
    description = Column(String, nullable=True)
    attachment_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    staff = relationship("Staff")

class HRTermination(Base):
    __tablename__ = "hr_terminations"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff.id"))
    termination_type_id = Column(Integer, ForeignKey("hr_constants.id"))
    notice_date = Column(Date)
    termination_date = Column(Date)
    description = Column(String, nullable=True)
    attachment_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    staff = relationship("Staff")
    termination_type = relationship("HRConstant")

class PerfConstant(Base):
    __tablename__ = "perf_constants"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True) # collections, indexes, matrix
    name = Column(String, index=True)
    collection_id = Column(Integer, ForeignKey("perf_constants.id"), nullable=True)
    weight = Column(Float, default=0.0) # For indexes
    score = Column(Float, default=0.0) # For matrix
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    collection = relationship("PerfConstant", remote_side=[id])

class PerformanceAppraisal(Base):
    __tablename__ = "perf_appraisals"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("staff.id"))
    month = Column(Integer)
    year = Column(Integer)
    narrative = Column(Text, nullable=True)
    appraised_by_id = Column(Integer, ForeignKey("staff.id"))
    total_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    employee = relationship("Staff", foreign_keys=[employee_id])
    appraiser = relationship("Staff", foreign_keys=[appraised_by_id])
    scores = relationship("AppraisalScore", back_populates="appraisal", cascade="all, delete-orphan")

class AppraisalScore(Base):
    __tablename__ = "perf_appraisal_scores"
    id = Column(Integer, primary_key=True, index=True)
    appraisal_id = Column(Integer, ForeignKey("perf_appraisals.id"))
    index_id = Column(Integer, ForeignKey("perf_constants.id"))
    score = Column(Float)
    
    appraisal = relationship("PerformanceAppraisal", back_populates="scores")
    index = relationship("PerfConstant")

class PayrollConstant(Base):
    __tablename__ = "payroll_constants"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True) # allowances, deductions
    name = Column(String, index=True)
    is_taxable = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    narrative = Column(Text, nullable=True)
    payable_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    expense_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    payable_account = relationship("Account", foreign_keys=[payable_account_id])
    expense_account = relationship("Account", foreign_keys=[expense_account_id])

class PayrollRecord(Base):
    __tablename__ = "payroll_records"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("staff.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"))
    month = Column(Integer) # 1-12
    basic_salary = Column(Float, default=0.0)
    allowances = Column(Float, default=0.0)
    gross_salary = Column(Float, default=0.0)
    nssf = Column(Float, default=0.0)
    sha = Column(Float, default=0.0)
    housing_levy = Column(Float, default=0.0)
    paye = Column(Float, default=0.0)
    other_deductions = Column(Float, default=0.0)
    net_salary = Column(Float, default=0.0)
    status = Column(String, default="Pending") # Pending, Approved, Paid
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    employee = relationship("Staff")
    store = relationship("Store")
    fiscal_year = relationship("FiscalYear")

class SalaryAdvance(Base):
    __tablename__ = "salary_advances"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("staff.id"))
    fiscal_year_id = Column(Integer, ForeignKey("fiscal_years.id"))
    month = Column(Integer)
    amount = Column(Float, default=0.0)
    is_disbursed = Column(Boolean, default=False)
    is_recovered = Column(Boolean, default=False) # Recovered from payroll
    narrative = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    employee = relationship("Staff")
    fiscal_year = relationship("FiscalYear")

class LeaveType(Base):
    __tablename__ = "leave_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    days_per_year = Column(Integer, default=21)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class LeaveApplication(Base):
    __tablename__ = "leave_applications"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("staff.id"))
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"))
    start_date = Column(Date)
    end_date = Column(Date)
    total_days = Column(Float)
    stretch = Column(String, default="full") # full, half
    reason = Column(Text, nullable=True)
    status = Column(String, default="Pending") # Pending, Approved, Rejected, Cancelled
    approved_by_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    employee = relationship("Staff", foreign_keys=[employee_id])
    leave_type = relationship("LeaveType")
    approver = relationship("Staff", foreign_keys=[approved_by_id])
class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("staff.id"))
    store_id = Column(Integer, ForeignKey("stores.id"))
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    status = Column(String, default="In") # In, Out
    device_info = Column(String, nullable=True) # e.g. IP or biometric device ID
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    employee = relationship("Staff")
    store = relationship("Store")

