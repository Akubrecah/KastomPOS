from fastapi import FastAPI, Request, Depends, Form, HTTPException, Query, UploadFile, File
from typing import Optional, List
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, distinct, literal
from app.core import models
from app.services.database import engine, get_db, SessionLocal
import os
import datetime
import calendar
import sys
import json
import secrets

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Create database tables
try:
    models.Base.metadata.create_all(bind=engine)
except Exception as e:
    print(f"Warning: Could not run metadata.create_all at startup: {e}")

def perform_db_seed(db: Session):
    # Only seed absolute system-level tables if they do not exist
    
    # Account types
    if not db.query(models.AccountType).first():
        at1 = models.AccountType(name="Asset", description="Resources owned by the business")
        at2 = models.AccountType(name="Liability", description="Obligations to third parties")
        at3 = models.AccountType(name="Equity", description="Owner's stake in the business")
        at4 = models.AccountType(name="Revenue", description="Income from business activities")
        at5 = models.AccountType(name="Expense", description="Costs incurred in business activities")
        db.add_all([at1, at2, at3, at4, at5])
        db.commit()

        # Add common subtypes
        db.add_all([
            models.AccountType(name='Current Asset', parent_id=at1.id),
            models.AccountType(name='Fixed Asset', parent_id=at1.id),
            models.AccountType(name='Current Liability', parent_id=at2.id),
            models.AccountType(name='Operating Expense', parent_id=at5.id),
            models.AccountType(name='Other Income', parent_id=at4.id)
        ])
        db.commit()

    # Tax types
    if not db.query(models.TaxType).first():
        db.add_all([
            models.TaxType(name="VAT 16%", rate=16.0),
            models.TaxType(name="Exempt", rate=0.0)
        ])
        db.commit()

    # Units
    if not db.query(models.Unit).first():
        db.add_all([
            models.Unit(name="Piece"),
            models.Unit(name="Kg"),
            models.Unit(name="Litre")
        ])
        db.commit()

    # Category
    if not db.query(models.Category).first():
        db.add(models.Category(name="General"))
        db.commit()

def auto_seed_on_startup():
    db = SessionLocal()
    try:
        if not db.query(models.Staff).first():
            print("Database is empty. Auto-seeding baseline data...")
            perform_db_seed(db)
    except Exception as e:
        print(f"Error during database auto-seeding: {e}")
    finally:
        db.close()

auto_seed_on_startup()

app = FastAPI()

# Mount static files
static_path = resource_path("static")
if not os.path.exists(static_path):
    os.makedirs(static_path)
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Templates setup
templates = Jinja2Templates(directory=resource_path("templates"))

# Custom Jinja2 filter for currency
def format_currency(value):
    try:
        return f"{float(value):,.2f}"
    except (ValueError, TypeError):
        return value

templates.env.filters["format_currency"] = format_currency

CURRENT_USER_ID = None

def get_current_user_global():
    db = SessionLocal()
    try:
        global CURRENT_USER_ID
        if CURRENT_USER_ID is not None:
            user = db.query(models.Staff).filter(models.Staff.id == CURRENT_USER_ID).first()
            if user:
                return user
        # Get the first staff user
        user = db.query(models.Staff).first()
        return user
    except Exception:
        return None
    finally:
        db.close()

def get_notifications_global():
    db = SessionLocal()
    try:
        notifications = []
        # Check low stock products
        low_stock = db.query(models.Product).filter(models.Product.stock_quantity <= models.Product.reorder_level).limit(3).all()
        for p in low_stock:
            notifications.append({
                "type": "stock",
                "title": f"Low Stock: {p.name}",
                "description": f"{p.name} quantity is {p.stock_quantity} (Reorder level: {p.reorder_level})",
                "time": "Stock Alert",
                "icon": "fas fa-exclamation-triangle",
                "class": "text-warning",
                "link": "/admin/inventory"
            })
        
        # Check pending petty cash requests
        pending_petty = db.query(models.PettyCashRequest).filter(models.PettyCashRequest.status == "Pending").limit(2).all()
        for r in pending_petty:
            notifications.append({
                "type": "petty_cash",
                "title": "Pending Petty Cash",
                "description": f"Request {r.ref_no} for KES {r.amount:,.2f} needs approval",
                "time": "Approval Needed",
                "icon": "fas fa-money-bill-wave",
                "class": "text-info",
                "link": "/admin/petty-cash"
            })
            
        # Check pending leave applications
        pending_leave = db.query(models.LeaveApplication).filter(models.LeaveApplication.status == "Pending").limit(2).all()
        for leave in pending_leave:
            employee_name = leave.employee.name if leave.employee else "Employee"
            notifications.append({
                "type": "leave",
                "title": "Pending Leave Request",
                "description": f"{employee_name} has requested leave for {leave.total_days} days",
                "time": "Leave Request",
                "icon": "fas fa-calendar-alt",
                "class": "text-teal",
                "link": "/admin/hr/leave-applications"
            })
            
        # If no notifications, add a friendly system notification
        if not notifications:
            notifications.append({
                "type": "system",
                "title": "System Active",
                "description": "KastomPOS ERP is running smoothly.",
                "time": "Just now",
                "icon": "fas fa-check-circle",
                "class": "text-success",
                "link": "/admin/staff"
            })
            
        return notifications
    except Exception:
        return []
    finally:
        db.close()

templates.env.globals["get_current_user"] = get_current_user_global
templates.env.globals["get_notifications"] = get_notifications_global

from app import __version__ as APP_VERSION
templates.env.globals["app_version"] = APP_VERSION

def translate_ui(request: Request, text: str) -> str:
    lang = request.cookies.get("language", "en")
    from app.core.translations import translate
    return translate(text, lang)

templates.env.globals["_"] = translate_ui

@app.get("/set-language/{lang}")
async def set_language(lang: str, request: Request):
    referer = request.headers.get("referer", "/")
    if "/set-language/" in referer:
        referer = "/"
    response = RedirectResponse(url=referer, status_code=303)
    response.set_cookie("language", lang, max_age=31536000)
    return response


# Serve React App from dist (if built)
if os.path.exists("dist"):
    app.mount("/pos-app", StaticFiles(directory="dist", html=True), name="pos-app")
    
@app.get("/pos", response_class=HTMLResponse)
async def serve_pos_app(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    products = db.query(models.Product).filter(models.Product.is_active).all()
    
    # Get current store from session (mocked for now, normally from cookie/session)
    # For now we'll just pick the first store if available
    current_store = stores[0] if stores else None
    
    open_sales_count = db.query(models.Order).filter(models.Order.status == 'open').count()
    
    return templates.TemplateResponse(
        request=request,
        name="pos.html",
        context={
            "settings": settings,
            "stores": stores,
            "products": products,
            "current_store": current_store,
            "open_sales_count": open_sales_count,
            "active_page": "pos"
        }
    )



# Helper to get settings
def get_settings(db: Session):
    settings = db.query(models.Setting).all()
    settings_dict = {s.key: s.value for s in settings}
    # Initialize defaults if not present
    defaults = {
        "offline_mode": "True",
        "kra_enabled": "False",
        "mpesa_enabled": "False",
        "business_name": "KastomPOS",
        "currency": "KES"
    }
    for key, val in defaults.items():
        if key not in settings_dict:
            db.add(models.Setting(key=key, value=val))
            db.commit()
            settings_dict[key] = val
    return settings_dict

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    today = datetime.datetime.utcnow().date()
    
    # Dashboard Nav Stats
    active_users = db.query(models.Staff).filter(models.Staff.is_active).count()
    sms_count = db.query(models.SMSOutbox).count()
    supplier_balance = db.query(func.sum(models.Supplier.balance)).scalar() or 0
    stores_count = db.query(models.Store).count()
    
    # Column 1 Stats
    due_invoices_total = db.query(func.sum(models.Purchase.balance)).filter(models.Purchase.status != "Cancelled").scalar() or 0.00
    due_invoices_count = db.query(models.Purchase).filter(models.Purchase.balance > 0, models.Purchase.status != "Cancelled").count()
    items_count = db.query(models.Product).count()
    needs_restock = db.query(models.Product).filter(models.Product.stock_quantity < 10).count()
    open_sales = db.query(models.Order).filter(models.Order.status == 'open').count()
    all_sales_count = db.query(models.Order).count()
    
    # Column 2 Stats
    fast_moving = db.query(models.Product.name, func.sum(models.OrderItem.quantity))\
        .join(models.OrderItem).join(models.Order)\
        .filter(models.Order.status == 'paid')\
        .group_by(models.Product.name).order_by(func.sum(models.OrderItem.quantity).desc()).limit(15).all()
        
    today_sales_summary = {
        "total_sales": db.query(func.sum(models.Order.total_amount)).filter(func.date(models.Order.created_at) == today).scalar() or 0,
        "complementary": 0.00,
        "paid": db.query(func.sum(models.Payment.amount_paid)).filter(func.date(models.Payment.paid_at) == today).scalar() or 0,
        "discounts": 0.00,
        "balance": 0.00
    }
    
    # Column 3 Accounts (dynamically calculated)
    db_accounts = db.query(models.Account).all()
    accounts = []
    for acc in db_accounts:
        in_sum = db.query(func.sum(models.JournalPosting.amount)).filter(
            models.JournalPosting.account_id == acc.id,
            models.JournalPosting.dr_cr == 'Debit'
        ).scalar() or 0.00
        
        out_sum = db.query(func.sum(models.JournalPosting.amount)).filter(
            models.JournalPosting.account_id == acc.id,
            models.JournalPosting.dr_cr == 'Credit'
        ).scalar() or 0.00
        
        acc_type_obj = acc.type
        acc_type_name = (acc_type_obj.name if (acc_type_obj and acc_type_obj.name) else (acc.account_type or "")).capitalize()
        
        if acc_type_name in ['Asset', 'Expense']:
            bal = in_sum - out_sum
        else:
            bal = out_sum - in_sum
            
        accounts.append({
            "name": acc.name,
            "code": acc.code or "-",
            "in": in_sum,
            "out": out_sum,
            "bal": bal
        })

    # Last 6 months performance data for line chart
    performance_data = []
    for i in range(5, -1, -1):
        first_of_current = today.replace(day=1)
        m = first_of_current.month - i
        y = first_of_current.year
        while m <= 0:
            m += 12
            y -= 1
        
        start_date = datetime.date(y, m, 1)
        if m == 12:
            end_date = datetime.date(y + 1, 1, 1)
        else:
            end_date = datetime.date(y, m + 1, 1)
            
        month_name = start_date.strftime('%b')
        
        month_sales = db.query(func.sum(models.Order.total_amount)).filter(
            models.Order.status == 'paid',
            models.Order.created_at >= start_date,
            models.Order.created_at < end_date
        ).scalar() or 0.00
        
        month_expenses = db.query(func.sum(models.Expense.amount)).filter(
            models.Expense.status != 'Cancelled',
            models.Expense.expense_date >= start_date,
            models.Expense.expense_date < end_date
        ).scalar() or 0.00
        
        performance_data.append({
            "month": month_name,
            "sales": month_sales,
            "expenses": month_expenses
        })

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "settings": settings,
            "active_page": "dashboard",
            "active_users": active_users,
            "sms_count": sms_count,
            "supplier_balance": supplier_balance,
            "stores_count": stores_count,
            "due_invoices": due_invoices_total,
            "due_invoices_count": due_invoices_count,
            "items_count": items_count,
            "needs_restock": needs_restock,
            "open_sales": open_sales,
            "all_sales_count": all_sales_count,
            "fast_moving": fast_moving,
            "today_summary": today_sales_summary,
            "accounts": accounts,
            "performance_data": performance_data,
            "current_month_name": today.strftime('%B'),
            "current_month_year": today.strftime('%B/%Y')
        }
    )

# --- BILLING & ORDERING ---

@app.get("/billing", response_class=HTMLResponse)
async def billing_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    categories = db.query(models.Category).all()
    products = db.query(models.Product).all()
    waiters = db.query(models.Staff).filter(models.Staff.role == 'waiter').all()
    customers = db.query(models.Customer).all()
    
    return templates.TemplateResponse(
        request=request,
        name="billing.html",
        context={
            "settings": settings,
            "categories": categories,
            "products": products,
            "waiters": waiters,
            "customers": customers,
            "active_page": "billing"
        }
    )

@app.post("/orders/create")
async def create_order(
    request: Request,
    db: Session = Depends(get_db)
):
    data = await request.json()
    # data format: {customer_id, waiter_id, table_number, items: [{product_id, quantity, note, price}]}
    
    new_order = models.Order(
        customer_id=data.get('customer_id'),
        waiter_id=data.get('waiter_id'),
        table_number=data.get('table_number'),
        status='open',
        total_amount=0.0
    )
    db.add(new_order)
    db.flush() # Get ID
    
    total = 0.0
    for item in data.get('items', []):
        order_item = models.OrderItem(
            order_id=new_order.id,
            product_id=item['product_id'],
            quantity=item['quantity'],
            unit_price=item['price'],
            note=item.get('note')
        )
        db.add(order_item)
        total += (item['price'] * item['quantity'])
        
        # Deduct stock
        product = db.query(models.Product).get(item['product_id'])
        if product and not product.is_service:
            product.stock_quantity -= item['quantity']
            
        # Deduct recipe ingredients if any
        for recipe in product.recipe_items:
            recipe.ingredient.stock_quantity -= (recipe.quantity_required * item['quantity'])

    new_order.total_amount = total
    db.commit()
    return {"status": "success", "order_id": new_order.id}

@app.post("/orders/pay/{order_id}")
async def pay_order(
    order_id: int,
    amount: float = Form(...),
    method: str = Form(...),
    cashier_id: int = Form(...),
    db: Session = Depends(get_db)
):
    order = db.query(models.Order).get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    payment = models.Payment(
        order_id=order_id,
        cashier_id=cashier_id,
        amount_paid=amount,
        method=method
    )
    db.add(payment)
    order.status = 'paid'
    
    # Generate Receipt
    receipt_no = f"REC-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}"
    new_receipt = models.Receipt(order_id=order_id, receipt_number=receipt_no)
    db.add(new_receipt)
    
    db.commit()
    return RedirectResponse(url=f"/receipt/{order_id}", status_code=303)

@app.get("/receipt/{order_id}", response_class=HTMLResponse)
async def view_receipt(order_id: int, request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    order = db.query(models.Order).get(order_id)
    receipt = db.query(models.Receipt).filter(models.Receipt.order_id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse(
        request=request,
        name="receipt.html",
        context={
            "settings": settings,
            "order": order,
            "receipt": receipt,
            "active_page": "billing"
        }
    )

# --- INVENTORY & STOCK ---

@app.get("/inventory", response_class=HTMLResponse)
async def list_inventory(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    categories = db.query(models.Category).all()
    products = db.query(models.Product).all()
    ingredients = db.query(models.Ingredient).all()
    return templates.TemplateResponse(
        request=request,
        name="inventory.html",
        context={
            "settings": settings,
            "categories": categories,
            "products": products,
            "ingredients": ingredients,
            "active_page": "inventory"
        }
    )
# --- VOIDING & AUDIT ---

@app.post("/orders/void-item/{item_id}")
async def void_item(
    item_id: int,
    staff_id: int = Form(...),
    reason: str = Form(...),
    db: Session = Depends(get_db)
):
    item = db.query(models.OrderItem).get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item.is_voided = True
    
    # Log the void
    void_log = models.VoidLog(
        order_id=item.order_id,
        item_id=item_id,
        staff_id=staff_id,
        reason=reason
    )
    db.add(void_log)
    
    # Update order total
    order = item.order
    order.total_amount -= (item.unit_price * item.quantity)
    
    db.commit()
    return {"status": "success", "message": "Item voided"}

@app.get("/reports/eod", response_class=HTMLResponse)
async def end_of_day_report(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    today = datetime.datetime.utcnow().date()
    
    # Summary of payments today
    payments = db.query(models.Payment.method, func.sum(models.Payment.amount_paid))\
        .filter(func.date(models.Payment.paid_at) == today)\
        .group_by(models.Payment.method).all()
    
    # Total sales
    total_sales = sum(p[1] for p in payments)
    
    # Voids today
    voids = db.query(models.VoidLog).filter(func.date(models.VoidLog.timestamp) == today).all()
    
    return templates.TemplateResponse(
        request=request,
        name="eod_report.html",
        context={
            "settings": settings,
            "payments": payments,
            "total_sales": total_sales,
            "voids_count": len(voids),
            "date": today,
            "active_page": "close_day"
        }
    )

@app.get("/admin/reports/close-day")
async def admin_close_day_redirect():
    """Redirect base close-day URL to general-sales tab."""
    return RedirectResponse(url="/admin/reports/close-day/general-sales", status_code=302)


@app.get("/admin/reports/close-day/general-sales", response_class=HTMLResponse)
async def admin_close_day_general_sales(
    request: Request,
    db: Session = Depends(get_db),
    org_id: Optional[int] = None,
    date_range: Optional[str] = None,
):
    settings = get_settings(db)
    orgs = db.query(models.Store).all()

    today = datetime.datetime.utcnow().date()
    start_date = today
    end_date = today

    # Parse the daterangepicker value: "MM/DD/YYYY hh:mm A - MM/DD/YYYY hh:mm A"
    if date_range and " - " in date_range:
        try:
            parts = date_range.split(" - ")
            start_date = datetime.datetime.strptime(parts[0].strip(), "%m/%d/%Y %I:%M %p").date()
            end_date = datetime.datetime.strptime(parts[1].strip(), "%m/%d/%Y %I:%M %p").date()
        except ValueError:
            try:
                start_date = datetime.datetime.strptime(parts[0].strip()[:10], "%m/%d/%Y").date()
                end_date = datetime.datetime.strptime(parts[1].strip()[:10], "%m/%d/%Y").date()
            except ValueError:
                start_date = today
                end_date = today

    query = db.query(models.Order).options(
        joinedload(models.Order.payments),
        joinedload(models.Order.customer),
        joinedload(models.Order.receipt),
        joinedload(models.Order.items).joinedload(models.OrderItem.product).joinedload(models.Product.category),
    )

    if org_id:
        query = query.filter(models.Order.store_id == org_id)

    query = query.filter(func.date(models.Order.created_at) >= start_date)
    query = query.filter(func.date(models.Order.created_at) <= end_date)

    sales = query.all()

    # --- Summary calculations ---
    total_gross = sum(s.total_amount for s in sales)
    total_paid = sum(sum(p.amount_paid for p in s.payments) for s in sales)
    total_balance = total_gross - total_paid
    total_discount = sum(getattr(s, 'discount', 0) or 0 for s in sales)
    sum(1 for s in sales if getattr(s, 'status', '') == 'voided')
    voided_value = sum(s.total_amount for s in sales if getattr(s, 'status', '') == 'voided')
    sum(1 for s in sales if getattr(s, 'status', '') == 'complementary')
    complementary_value = sum(s.total_amount for s in sales if getattr(s, 'status', '') == 'complementary')

    # Staff sales summary
    staff_sales = {}
    for s in sales:
        staff_name = s.customer.name if s.customer else "Walk-in"
        staff_sales[staff_name] = staff_sales.get(staff_name, 0) + s.total_amount

    # Cash distribution (payment method breakdown)
    cash_distribution = {}
    for s in sales:
        for p in s.payments:
            method = p.method or "Cash"
            cash_distribution[method] = cash_distribution.get(method, 0) + p.amount_paid

    # Items sales summary per category
    category_sales = {}
    for s in sales:
        for item in s.items:
            cat = item.product.category.name if (item.product and item.product.category) else "Uncategorized"
            category_sales[cat] = category_sales.get(cat, 0) + (item.quantity * item.unit_price)

    # Default date range string for the picker
    default_range = f"{start_date.strftime('%m/%d/%Y')} 12:00 AM - {end_date.strftime('%m/%d/%Y')} 11:59 PM"

    return templates.TemplateResponse(
        request=request,
        name="close_day_general_sales.html",
        context={
            "settings": settings,
            "orgs": orgs,
            "sales": sales,
            "total_gross": total_gross,
            "total_net": total_gross,
            "total_paid": total_paid,
            "total_balance": total_balance,
            "total_discount": total_discount,
            "voided_value": voided_value,
            "complementary_value": complementary_value,
            "staff_sales": staff_sales,
            "cash_distribution": cash_distribution,
            "category_sales": category_sales,
            "selected_org_id": org_id,
            "date_range": date_range or default_range,
            "today": today.strftime('%Y-%m-%d'),
            "active_page": "close_day",
        },
    )


@app.get("/admin/reports/close-day/invoices", response_class=HTMLResponse)
async def admin_close_day_invoices(
    request: Request,
    db: Session = Depends(get_db),
    org_id: Optional[int] = None,
    date_range: Optional[str] = None,
):
    settings = get_settings(db)
    orgs = db.query(models.Store).all()

    today = datetime.datetime.utcnow().date()
    start_date = today
    end_date = today

    if date_range and " - " in date_range:
        try:
            parts = date_range.split(" - ")
            start_date = datetime.datetime.strptime(parts[0].strip(), "%m/%d/%Y %I:%M %p").date()
            end_date = datetime.datetime.strptime(parts[1].strip(), "%m/%d/%Y %I:%M %p").date()
        except ValueError:
            try:
                start_date = datetime.datetime.strptime(parts[0].strip()[:10], "%m/%d/%Y").date()
                end_date = datetime.datetime.strptime(parts[1].strip()[:10], "%m/%d/%Y").date()
            except ValueError:
                start_date = today
                end_date = today

    # Quotations (used as invoices)
    q_query = db.query(models.Quotation).options(
        joinedload(models.Quotation.customer),
        joinedload(models.Quotation.items).joinedload(models.QuotationItem.product),
    )
    q_query = q_query.filter(func.date(models.Quotation.created_at) >= start_date)
    q_query = q_query.filter(func.date(models.Quotation.created_at) <= end_date)
    quotations = q_query.all()

    # Banquets
    b_query = db.query(models.Banquet).options(
        joinedload(models.Banquet.customer),
        joinedload(models.Banquet.items).joinedload(models.BanquetItem.product),
    )
    if org_id:
        b_query = b_query.filter(models.Banquet.store_id == org_id)
    b_query = b_query.filter(func.date(models.Banquet.created_at) >= start_date)
    b_query = b_query.filter(func.date(models.Banquet.created_at) <= end_date)
    banquets = b_query.all()

    # Aggregates for quotations
    quot_total = sum(q.total_amount for q in quotations)
    quot_pending = sum(q.total_amount for q in quotations if q.status == "pending")
    quot_paid = sum(q.total_amount for q in quotations if q.status == "paid")
    quot_cancelled = sum(q.total_amount for q in quotations if q.status == "cancelled")

    # Aggregates for banquets
    banq_total = sum(b.total_amount for b in banquets)
    banq_pending = sum(b.total_amount for b in banquets if b.status == "pending")
    banq_paid = sum(b.total_amount for b in banquets if b.status == "paid")

    grand_total = quot_total + banq_total
    grand_paid = quot_paid + banq_paid
    grand_balance = grand_total - grand_paid

    default_range = f"{start_date.strftime('%m/%d/%Y')} 12:00 AM - {end_date.strftime('%m/%d/%Y')} 11:59 PM"

    return templates.TemplateResponse(
        request=request,
        name="close_day_invoices.html",
        context={
            "settings": settings,
            "orgs": orgs,
            "quotations": quotations,
            "banquets": banquets,
            "quot_total": quot_total,
            "quot_pending": quot_pending,
            "quot_paid": quot_paid,
            "quot_cancelled": quot_cancelled,
            "banq_total": banq_total,
            "banq_pending": banq_pending,
            "banq_paid": banq_paid,
            "grand_total": grand_total,
            "grand_paid": grand_paid,
            "grand_balance": grand_balance,
            "selected_org_id": org_id,
            "date_range": date_range or default_range,
            "today": today.strftime('%Y-%m-%d'),
            "active_page": "close_day",
        },
    )


@app.get("/admin/reports/close-day/room-bookings", response_class=HTMLResponse)
async def admin_close_day_room_bookings(
    request: Request,
    db: Session = Depends(get_db),
    org_id: Optional[int] = None,
    date_range: Optional[str] = None,
):
    settings = get_settings(db)
    orgs = db.query(models.Store).all()

    today = datetime.datetime.utcnow().date()
    start_date = today
    end_date = today

    if date_range and " - " in date_range:
        try:
            parts = date_range.split(" - ")
            start_date = datetime.datetime.strptime(parts[0].strip(), "%m/%d/%Y %I:%M %p").date()
            end_date = datetime.datetime.strptime(parts[1].strip(), "%m/%d/%Y %I:%M %p").date()
        except ValueError:
            try:
                start_date = datetime.datetime.strptime(parts[0].strip()[:10], "%m/%d/%Y").date()
                end_date = datetime.datetime.strptime(parts[1].strip()[:10], "%m/%d/%Y").date()
            except ValueError:
                start_date = today
                end_date = today

    rb_query = db.query(models.RoomBooking).options(
        joinedload(models.RoomBooking.room)
    )
    rb_query = rb_query.filter(func.date(models.RoomBooking.created_at) >= start_date)
    rb_query = rb_query.filter(func.date(models.RoomBooking.created_at) <= end_date)
    bookings = rb_query.all()

    total_bookings = len(bookings)
    total_amount = sum(b.total_amount for b in bookings)
    total_paid = sum(b.paid_amount for b in bookings)
    total_balance = sum(b.balance for b in bookings)
    active_count = sum(1 for b in bookings if b.status == "active")
    checked_out_count = sum(1 for b in bookings if b.status == "checked_out")
    cancelled_count = sum(1 for b in bookings if b.status == "cancelled")

    # Payment method breakdown
    payment_breakdown = {}
    for b in bookings:
        m = b.payment_method or "Cash"
        payment_breakdown[m] = payment_breakdown.get(m, 0) + b.paid_amount

    # Room-type breakdown
    room_type_sales = {}
    for b in bookings:
        rtype = b.room.room_type if b.room and hasattr(b.room, 'room_type') else "Standard"
        room_type_sales[rtype] = room_type_sales.get(rtype, 0) + b.total_amount

    default_range = f"{start_date.strftime('%m/%d/%Y')} 12:00 AM - {end_date.strftime('%m/%d/%Y')} 11:59 PM"

    return templates.TemplateResponse(
        request=request,
        name="close_day_room_bookings.html",
        context={
            "settings": settings,
            "orgs": orgs,
            "bookings": bookings,
            "total_bookings": total_bookings,
            "total_amount": total_amount,
            "total_paid": total_paid,
            "total_balance": total_balance,
            "active_count": active_count,
            "checked_out_count": checked_out_count,
            "cancelled_count": cancelled_count,
            "payment_breakdown": payment_breakdown,
            "room_type_sales": room_type_sales,
            "selected_org_id": org_id,
            "date_range": date_range or default_range,
            "today": today.strftime('%Y-%m-%d'),
            "active_page": "close_day",
        },
    )


@app.get("/admin/reports/close-day/cash", response_class=HTMLResponse)
async def admin_close_day_cash(
    request: Request,
    db: Session = Depends(get_db),
    org_id: Optional[int] = None,
    date_range: Optional[str] = None,
):
    settings = get_settings(db)
    orgs = db.query(models.Store).all()

    today = datetime.datetime.utcnow().date()
    start_date = today
    end_date = today

    if date_range and " - " in date_range:
        try:
            parts = date_range.split(" - ")
            start_date = datetime.datetime.strptime(parts[0].strip(), "%m/%d/%Y %I:%M %p").date()
            end_date = datetime.datetime.strptime(parts[1].strip(), "%m/%d/%Y %I:%M %p").date()
        except ValueError:
            try:
                start_date = datetime.datetime.strptime(parts[0].strip()[:10], "%m/%d/%Y").date()
                end_date = datetime.datetime.strptime(parts[1].strip()[:10], "%m/%d/%Y").date()
            except ValueError:
                start_date = today
                end_date = today

    # POS Payments
    pay_query = db.query(models.Payment).options(
        joinedload(models.Payment.order)
    ).join(models.Order)
    if org_id:
        pay_query = pay_query.filter(models.Order.store_id == org_id)
    pay_query = pay_query.filter(func.date(models.Payment.paid_at) >= start_date)
    pay_query = pay_query.filter(func.date(models.Payment.paid_at) <= end_date)
    payments = pay_query.all()

    # Expenses in range
    exp_query = db.query(models.Expense)
    if org_id:
        exp_query = exp_query.filter(models.Expense.store_id == org_id)
    exp_query = exp_query.filter(func.date(models.Expense.expense_date) >= start_date)
    exp_query = exp_query.filter(func.date(models.Expense.expense_date) <= end_date)
    expenses = exp_query.all()

    # Cash in by method
    cash_in = {}
    for p in payments:
        m = p.method or "Cash"
        cash_in[m] = cash_in.get(m, 0) + p.amount_paid
    total_cash_in = sum(cash_in.values())

    # Cash out
    total_expenses = sum(e.amount for e in expenses)

    # Room booking payments in range
    rb_query = db.query(models.RoomBooking)
    rb_query = rb_query.filter(func.date(models.RoomBooking.created_at) >= start_date)
    rb_query = rb_query.filter(func.date(models.RoomBooking.created_at) <= end_date)
    room_bookings = rb_query.all()
    total_room_income = sum(b.paid_amount for b in room_bookings)

    total_income = total_cash_in + total_room_income
    net_cash = total_income - total_expenses

    default_range = f"{start_date.strftime('%m/%d/%Y')} 12:00 AM - {end_date.strftime('%m/%d/%Y')} 11:59 PM"

    return templates.TemplateResponse(
        request=request,
        name="close_day_cash.html",
        context={
            "settings": settings,
            "orgs": orgs,
            "cash_in": cash_in,
            "total_cash_in": total_cash_in,
            "total_room_income": total_room_income,
            "total_income": total_income,
            "expenses": expenses,
            "total_expenses": total_expenses,
            "net_cash": net_cash,
            "selected_org_id": org_id,
            "date_range": date_range or default_range,
            "today": today.strftime('%Y-%m-%d'),
            "active_page": "close_day",
        },
    )


@app.get("/admin/reports/close-day/cash-statement", response_class=HTMLResponse)
async def admin_close_day_cash_statement(
    request: Request,
    db: Session = Depends(get_db),
    org_id: Optional[int] = None,
    date_range: Optional[str] = None,
):
    settings = get_settings(db)
    orgs = db.query(models.Store).all()

    today = datetime.datetime.utcnow().date()
    start_date = today
    end_date = today

    if date_range and " - " in date_range:
        try:
            parts = date_range.split(" - ")
            start_date = datetime.datetime.strptime(parts[0].strip(), "%m/%d/%Y %I:%M %p").date()
            end_date = datetime.datetime.strptime(parts[1].strip(), "%m/%d/%Y %I:%M %p").date()
        except ValueError:
            try:
                start_date = datetime.datetime.strptime(parts[0].strip()[:10], "%m/%d/%Y").date()
                end_date = datetime.datetime.strptime(parts[1].strip()[:10], "%m/%d/%Y").date()
            except ValueError:
                start_date = today
                end_date = today

    # Build a unified transaction ledger
    transactions = []

    # POS payments (credit/income)
    pay_query = db.query(models.Payment).options(joinedload(models.Payment.order)).join(models.Order)
    if org_id:
        pay_query = pay_query.filter(models.Order.store_id == org_id)
    pay_query = pay_query.filter(func.date(models.Payment.paid_at) >= start_date)
    pay_query = pay_query.filter(func.date(models.Payment.paid_at) <= end_date)
    for p in pay_query.all():
        transactions.append({
            "date": p.paid_at,
            "description": f"POS Sale #{p.order_id} ({p.method})",
            "ref": f"ORD-{p.order_id}",
            "debit": 0,
            "credit": p.amount_paid,
            "type": "pos",
        })

    # Room booking payments (credit/income)
    rb_query = db.query(models.RoomBooking)
    rb_query = rb_query.filter(func.date(models.RoomBooking.created_at) >= start_date)
    rb_query = rb_query.filter(func.date(models.RoomBooking.created_at) <= end_date)
    for b in rb_query.all():
        if b.paid_amount > 0:
            transactions.append({
                "date": b.created_at,
                "description": f"Room Booking – {b.customer_name} ({b.payment_method})",
                "ref": b.reference or f"RB-{b.id}",
                "debit": 0,
                "credit": b.paid_amount,
                "type": "room",
            })

    # Expenses (debit/outflow)
    exp_query = db.query(models.Expense)
    if org_id:
        exp_query = exp_query.filter(models.Expense.store_id == org_id)
    exp_query = exp_query.filter(func.date(models.Expense.expense_date) >= start_date)
    exp_query = exp_query.filter(func.date(models.Expense.expense_date) <= end_date)
    for e in exp_query.all():
        transactions.append({
            "date": e.expense_date,
            "description": f"Expense – {e.paid_to} ({e.ref_no})",
            "ref": e.ref_no,
            "debit": e.amount,
            "credit": 0,
            "type": "expense",
        })

    # Sort by date
    transactions.sort(key=lambda x: x["date"] or datetime.datetime.min)

    # Running balance
    running_balance = 0.0
    for t in transactions:
        running_balance += t["credit"] - t["debit"]
        t["balance"] = running_balance

    total_credits = sum(t["credit"] for t in transactions)
    total_debits = sum(t["debit"] for t in transactions)
    closing_balance = total_credits - total_debits

    default_range = f"{start_date.strftime('%m/%d/%Y')} 12:00 AM - {end_date.strftime('%m/%d/%Y')} 11:59 PM"

    return templates.TemplateResponse(
        request=request,
        name="close_day_cash_statement.html",
        context={
            "settings": settings,
            "orgs": orgs,
            "transactions": transactions,
            "total_credits": total_credits,
            "total_debits": total_debits,
            "closing_balance": closing_balance,
            "selected_org_id": org_id,
            "date_range": date_range or default_range,
            "today": today.strftime('%Y-%m-%d'),
            "active_page": "close_day",
        },
    )


# --- ADMIN & REPORTS ---

@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    
    # Sales by category
    sales_by_cat = db.query(models.Category.name, func.sum(models.OrderItem.quantity * models.OrderItem.unit_price))\
        .join(models.Product, models.Product.category_id == models.Category.id)\
        .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)\
        .join(models.Order, models.Order.id == models.OrderItem.order_id)\
        .filter(models.Order.status == 'paid')\
        .group_by(models.Category.name).all()

    # Sales by waiter
    sales_by_waiter = db.query(models.Staff.name, func.sum(models.Order.total_amount))\
        .join(models.Order, models.Order.waiter_id == models.Staff.id)\
        .filter(models.Order.status == 'paid')\
        .group_by(models.Staff.name).all()

    # Payment method breakdown
    payment_breakdown = db.query(models.Payment.method, func.sum(models.Payment.amount_paid))\
        .group_by(models.Payment.method).all()

    # Item sales report
    item_sales = db.query(models.Product.name, func.sum(models.OrderItem.quantity), func.sum(models.OrderItem.quantity * models.OrderItem.unit_price))\
        .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)\
        .join(models.Order, models.Order.id == models.OrderItem.order_id)\
        .filter(models.Order.status == 'paid')\
        .group_by(models.Product.name).order_by(func.sum(models.OrderItem.quantity).desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="reports.html",
        context={
            "settings": settings,
            "sales_by_cat": sales_by_cat,
            "sales_by_waiter": sales_by_waiter,
            "payment_breakdown": payment_breakdown,
            "item_sales": item_sales,
            "active_page": "close_day"
        }
    )

@app.get("/admin/reports/cashier-performance", response_class=HTMLResponse)
async def admin_cashier_performance_report(
    request: Request,
    db: Session = Depends(get_db),
    from_date: str = Query(None),
    to_date: str = Query(None),
    date_range: str = Query(None)
):
    settings = get_settings(db)
    today = datetime.datetime.utcnow().date().strftime('%Y-%m-%d')
    
    # Parse date_range string "MM/DD/YYYY hh:mm A - MM/DD/YYYY hh:mm A"
    if date_range and " - " in date_range:
        try:
            parts = date_range.split(" - ")
            from_date = datetime.datetime.strptime(parts[0].strip(), "%m/%d/%Y %I:%M %p").strftime("%Y-%m-%d")
            to_date   = datetime.datetime.strptime(parts[1].strip(), "%m/%d/%Y %I:%M %p").strftime("%Y-%m-%d")
        except Exception:
            pass
            
    if not from_date:
        from_date = today
    if not to_date:
        to_date = today
        
    try:
        dr_start = datetime.datetime.strptime(from_date, "%Y-%m-%d").strftime("%m/%d/%Y 12:00 AM")
        dr_end   = datetime.datetime.strptime(to_date,   "%Y-%m-%d").strftime("%m/%d/%Y 11:59 PM")
        date_range_value = f"{dr_start} - {dr_end}"
    except Exception:
        date_range_value = f"{today} - {today}"
        
    start_dt = datetime.datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(to_date, "%Y-%m-%d") + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
    
    # Aggregate payment statistics per cashier (Staff member)
    performance_query = db.query(
        models.Staff.id.label("cashier_id"),
        models.Staff.name.label("name"),
        models.Staff.username.label("username"),
        models.Staff.role.label("role"),
        func.count(models.Payment.id).label("transaction_count"),
        func.sum(models.Payment.amount_paid).label("total_sales"),
        func.avg(models.Payment.amount_paid).label("average_transaction")
    ).join(models.Payment, models.Staff.id == models.Payment.cashier_id)\
     .filter(models.Payment.paid_at >= start_dt, models.Payment.paid_at <= end_dt)\
     .group_by(models.Staff.id, models.Staff.name, models.Staff.username, models.Staff.role)\
     .order_by(func.sum(models.Payment.amount_paid).desc())\
     .all()
     
    cashiers_performance = []
    for row in performance_query:
        cashiers_performance.append({
            "id": row.cashier_id,
            "name": row.name,
            "username": row.username,
            "role": row.role,
            "transaction_count": row.transaction_count,
            "total_sales": row.total_sales or 0.0,
            "average_transaction": row.average_transaction or 0.0
        })
        
    return templates.TemplateResponse(
        request=request,
        name="cashier_report.html",
        context={
            "settings": settings,
            "cashiers": cashiers_performance,
            "from_date": from_date,
            "to_date": to_date,
            "date_range": date_range_value,
            "active_page": "reports"
        }
    )

@app.get("/admin/reports/item-sales", response_class=HTMLResponse)
async def admin_item_sales_report(
    request: Request,
    db: Session = Depends(get_db),
    from_date: str = Query(None),
    to_date: str = Query(None),
    date_range: str = Query(None),
    store_id: str = Query(None),
    filtered: str = Query(None)
):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().date().strftime('%Y-%m-%d')

    # Parse date_range string "MM/DD/YYYY hh:mm A - MM/DD/YYYY hh:mm A"
    if date_range and " - " in date_range:
        try:
            parts = date_range.split(" - ")
            from_date = datetime.datetime.strptime(parts[0].strip(), "%m/%d/%Y %I:%M %p").strftime("%Y-%m-%d")
            to_date   = datetime.datetime.strptime(parts[1].strip(), "%m/%d/%Y %I:%M %p").strftime("%Y-%m-%d")
        except Exception:
            pass

    # Default to today if no filter applied
    if not from_date:
        from_date = today
    if not to_date:
        to_date = today

    # Rebuild display value for the picker
    try:
        dr_start = datetime.datetime.strptime(from_date, "%Y-%m-%d").strftime("%m/%d/%Y 12:00 AM")
        dr_end   = datetime.datetime.strptime(to_date,   "%Y-%m-%d").strftime("%m/%d/%Y 11:59 PM")
        date_range_value = f"{dr_start} - {dr_end}"
    except Exception:
        date_range_value = f"{today} - {today}"

    # Build aggregate query: per product
    query = db.query(
        models.Product.id.label("product_id"),
        models.Product.name.label("name"),
        models.Product.sku.label("sku"),
        func.sum(models.OrderItem.quantity).label("qty_sold"),
        func.sum(models.OrderItem.quantity * models.Product.cost_price).label("cost_of_sale"),
        func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).label("sale_value"),
        (func.sum(models.OrderItem.quantity * models.OrderItem.unit_price) -
         func.sum(models.OrderItem.quantity * models.Product.cost_price)).label("est_profit")
    ).join(models.OrderItem, models.OrderItem.product_id == models.Product.id)\
     .join(models.Order, models.Order.id == models.OrderItem.order_id)\
     .filter(models.Order.status == 'paid')

    if from_date:
        query = query.filter(func.date(models.Order.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(models.Order.created_at) <= to_date)
    if store_id and store_id not in ("", "All"):
        query = query.filter(models.Order.store_id == int(store_id))

    item_sales = query.group_by(
        models.Product.id, models.Product.name, models.Product.sku
    ).order_by(func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).desc()).all()

    # Compute totals
    total_qty    = sum((r.qty_sold or 0) for r in item_sales)
    total_cost   = sum((r.cost_of_sale or 0) for r in item_sales)
    total_sale   = sum((r.sale_value or 0) for r in item_sales)
    total_profit = sum((r.est_profit or 0) for r in item_sales)

    class Totals:
        pass
    totals = Totals()
    totals.qty_sold      = total_qty
    totals.cost_of_sale  = total_cost
    totals.sale_value    = total_sale
    totals.est_profit    = total_profit

    return templates.TemplateResponse(
        request=request,
        name="item_sales_report.html",
        context={
            "settings": settings,
            "stores": stores,
            "item_sales": item_sales,
            "totals": totals,
            "from_date": from_date,
            "to_date": to_date,
            "date_range_value": date_range_value,
            "selected_store": store_id or "",
            "active_page": "item_sales"
        }
    )

@app.get("/api/admin/reports/item-sales-data")
async def api_item_sales_data(
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    from_date: str = Query(None),
    to_date: str = Query(None),
    store_id: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(
        models.Product.name.label("item_name"),
        models.Category.name.label("category"),
        func.sum(models.OrderItem.quantity).label("qty_sold"),
        models.OrderItem.unit_price.label("unit_price"),
        func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).label("total_amount"),
        models.Store.name.label("store"),
        func.date(models.Order.created_at).label("date")
    ).join(models.OrderItem, models.OrderItem.product_id == models.Product.id)\
     .join(models.Order, models.Order.id == models.OrderItem.order_id)\
     .join(models.Category, models.Category.id == models.Product.category_id)\
     .join(models.Store, models.Store.id == models.Order.store_id)\
     .filter(models.Order.status == 'paid')

    if from_date:
        query = query.filter(func.date(models.Order.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(models.Order.created_at) <= to_date)
    if store_id and store_id != 'All':
        query = query.filter(models.Order.store_id == int(store_id))

    query = query.group_by(models.Product.name, models.Category.name, models.OrderItem.unit_price, models.Store.name, func.date(models.Order.created_at))
    
    total_records = query.count()
    results = query.offset(start).limit(length).all()

    data = []
    for r in results:
        data.append({
            "item_name": r.item_name,
            "category": r.category,
            "qty_sold": r.qty_sold,
            "unit_price": f"{r.unit_price:,.2f}",
            "total_amount": f"{r.total_amount:,.2f}",
            "store": r.store,
            "date": str(r.date)
        })

    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.get("/api/admin/reports/item-sales-stats")
async def api_item_sales_stats(
    from_date: str = Query(None),
    to_date: str = Query(None),
    store_id: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(
        func.sum(models.OrderItem.quantity * models.OrderItem.unit_price).label("total_amount"),
        func.sum(models.OrderItem.quantity).label("total_qty")
    ).join(models.Order, models.Order.id == models.OrderItem.order_id)\
     .filter(models.Order.status == 'paid')

    if from_date:
        query = query.filter(func.date(models.Order.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(models.Order.created_at) <= to_date)
    if store_id and store_id != 'All':
        query = query.filter(models.Order.store_id == int(store_id))

    stats = query.one()
    
    # Top item
    top_item_query = db.query(models.Product.name)\
        .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)\
        .join(models.Order, models.Order.id == models.OrderItem.order_id)\
        .filter(models.Order.status == 'paid')
    
    if from_date:
        top_item_query = top_item_query.filter(func.date(models.Order.created_at) >= from_date)
    if to_date:
        top_item_query = top_item_query.filter(func.date(models.Order.created_at) <= to_date)
    if store_id and store_id != 'All':
        top_item_query = top_item_query.filter(models.Order.store_id == int(store_id))
        
    top_item = top_item_query.group_by(models.Product.name).order_by(func.sum(models.OrderItem.quantity).desc()).first()

    # Active stores
    stores_count_query = db.query(func.count(distinct(models.Order.store_id)))\
        .filter(models.Order.status == 'paid')
    
    if from_date:
        stores_count_query = stores_count_query.filter(func.date(models.Order.created_at) >= from_date)
    if to_date:
        stores_count_query = stores_count_query.filter(func.date(models.Order.created_at) <= to_date)
    
    active_stores = stores_count_query.scalar() or 0

    return {
        "total_amount": f"{stats.total_amount or 0:,.2f}",
        "total_qty": stats.total_qty or 0,
        "top_item": top_item[0] if top_item else "-",
        "active_stores": active_stores
    }

@app.get("/admin/reports/periodic-revenue", response_class=HTMLResponse)
async def admin_periodic_revenue_report(
    request: Request,
    from_date: str = Query(None),
    to_date: str = Query(None),
    store_id: str = Query(None),
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().date().strftime('%Y-%m-%d')
    
    if not from_date: from_date = today
    if not to_date: to_date = today

    # Query logic for periodic revenue
    query = db.query(
        func.date(models.Order.created_at).label("date"),
        models.Store.name.label("store_name"),
        func.sum(models.Order.total_amount).label("gross"),
        func.sum(models.Order.total_amount * 0.16).label("tax_a"), # Mock VAT
        func.sum(models.Order.total_amount * 0.02).label("tax_b")  # Mock CTL
    ).join(models.Store, models.Store.id == models.Order.store_id)\
     .filter(models.Order.status == 'paid')\
     .filter(func.date(models.Order.created_at) >= from_date)\
     .filter(func.date(models.Order.created_at) <= to_date)

    if store_id and store_id != 'All':
        query = query.filter(models.Order.store_id == int(store_id))

    results = query.group_by(func.date(models.Order.created_at), models.Store.name).all()

    report_data = {}
    for r in results:
        date_str = str(r.date)
        if date_str not in report_data:
            report_data[date_str] = []
        report_data[date_str].append({
            "name": r.store_name,
            "gross": r.gross,
            "tax_a": r.tax_a,
            "tax_b": r.tax_b,
            "net": r.gross - (r.tax_a + r.tax_b)
        })

    return templates.TemplateResponse(
        request=request,
        name="periodic_revenue_report.html",
        context={
            "settings": settings,
            "stores": stores,
            "today": today,
            "report_data": report_data,
            "active_page": "periodic_revenue"
        }
    )

@app.get("/admin/reports/item-purchase")
async def admin_item_purchase_report(
    request: Request,
    store_id: str = Query("All"),
    from_date: str = Query(None),
    to_date: str = Query(None),
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    today = datetime.date.today().isoformat()
    if not from_date: from_date = today
    if not to_date: to_date = today

    stores = db.query(models.Store).all()
    
    # Query purchase items
    query = db.query(
        models.Product.name,
        models.Product.sku.label("code"),
        func.sum(models.PurchaseItem.quantity).label("qty"),
        func.sum(models.PurchaseItem.total_amount).label("value")
    ).join(models.Purchase, models.Purchase.id == models.PurchaseItem.purchase_id)\
     .join(models.Product, models.Product.id == models.PurchaseItem.product_id)\
     .filter(func.date(models.Purchase.purchase_date) >= from_date)\
     .filter(func.date(models.Purchase.purchase_date) <= to_date)

    if store_id != 'All':
        query = query.filter(models.Purchase.store_id == int(store_id))

    purchase_items = query.group_by(models.Product.name, models.Product.sku).all()
    
    total_qty = sum(item.qty for item in purchase_items)
    total_value = sum(item.value for item in purchase_items)

    # Query purchase expenses
    exp_query = db.query(
        models.Account.name,
        func.sum(models.Expense.amount).label("amount")
    ).join(models.Account, models.Account.id == models.Expense.account_id)\
     .filter(func.date(models.Expense.expense_date) >= from_date)\
     .filter(func.date(models.Expense.expense_date) <= to_date)

    if store_id != 'All':
        exp_query = exp_query.filter(models.Expense.store_id == int(store_id))
    
    purchase_expenses = exp_query.group_by(models.Account.name).all()
    total_expenses = sum(exp.amount for exp in purchase_expenses)

    return templates.TemplateResponse(
        request=request,
        name="items_purchase_report.html",
        context={
            "settings": settings,
            "stores": stores,
            "from_date": from_date,
            "to_date": to_date,
            "purchase_items": purchase_items,
            "total_qty": total_qty,
            "total_value": total_value,
            "purchase_expenses": purchase_expenses,
            "total_expenses": total_expenses,
            "active_page": "item_purchase"
        }
    )

@app.get("/admin/reports/room_sales")
@app.get("/admin/reports/room_sales/")
async def redirect_old_room_sales_underscore(request: Request):
    return RedirectResponse(url="/admin/reports/room-sales", status_code=302)

@app.get("/admin/reports/room-sales/room-booking-summaries")
@app.get("/admin/reports/room-sales/room-booking-summaries/")
async def redirect_room_booking_summaries(request: Request):
    return RedirectResponse(url="/admin/reports/room-sales", status_code=302)

@app.get("/admin/reports/room-sales")
@app.get("/admin/reports/room-sales/")
async def admin_room_sales_report(
    request: Request,
    store_id: str = Query("All"),
    from_date: str = Query(None),
    to_date: str = Query(None),
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    today = datetime.date.today().isoformat()
    if not from_date: from_date = today
    if not to_date: to_date = today

    stores = db.query(models.Store).all()

    query = db.query(
        models.RoomBooking.id,
        models.RoomBooking.created_at,
        models.RoomBooking.customer_name,
        models.Room.room_number.label("room_name"),
        models.RoomBooking.nights,
        models.RoomBooking.total_amount,
        models.RoomBooking.status
    ).join(models.Room, models.Room.id == models.RoomBooking.room_id)\
     .filter(func.date(models.RoomBooking.created_at) >= from_date)\
     .filter(func.date(models.RoomBooking.created_at) <= to_date)

    room_sales = query.all()

    total_nights = sum(b.nights for b in room_sales)
    total_room_revenue = sum(b.total_amount for b in room_sales)
    total_bookings = len(room_sales)

    return templates.TemplateResponse(
        request=request,
        name="room_sales_report.html",
        context={
            "settings": settings,
            "stores": stores,
            "from_date": from_date,
            "to_date": to_date,
            "room_sales": room_sales,
            "total_nights": total_nights,
            "total_room_revenue": total_room_revenue,
            "total_bookings": total_bookings,
            "active_page": "room_sales_report"
        }
    )

@app.get("/admin/reports/room-occupancy")
async def admin_room_occupancy_report(
    request: Request,
    store_id: str = Query("All"),
    status_filter: str = Query("All"),
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    
    rooms_query = db.query(models.Room)
    if status_filter != "All":
        rooms_query = rooms_query.filter(models.Room.status == status_filter)
    rooms = rooms_query.order_by(models.Room.room_number).all()
    
    active_bookings = db.query(models.RoomBooking).filter(models.RoomBooking.status == "active").all()
    booking_map = {b.room_id: b for b in active_bookings}
    
    rooms_data = []
    for r in rooms:
        booking = booking_map.get(r.id)
        rooms_data.append({
            "id": r.id,
            "room_number": r.room_number,
            "room_type": r.room_type,
            "category": r.category,
            "price_per_night": r.price_per_night,
            "status": r.status,
            "guest_name": booking.customer_name if booking else "—",
            "guest_phone": booking.customer_phone if booking else "—",
            "check_in": booking.from_date.strftime('%Y-%m-%d') if (booking and booking.from_date) else "—",
            "check_out": booking.to_date.strftime('%Y-%m-%d') if (booking and booking.to_date) else "—",
            "nights": booking.nights if booking else "—",
            "booking_type": booking.booking_type if booking else "—",
        })
        
    all_rooms = db.query(models.Room).all()
    total_rooms = len(all_rooms)
    occupied_rooms = sum(1 for r in all_rooms if r.status == "occupied")
    available_rooms = sum(1 for r in all_rooms if r.status == "available")
    maintenance_rooms = sum(1 for r in all_rooms if r.status == "maintenance")
    cleaning_rooms = sum(1 for r in all_rooms if r.status == "cleaning")
    occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0.0

    return templates.TemplateResponse(
        request=request,
        name="room_occupancy_report.html",
        context={
            "settings": settings,
            "stores": stores,
            "rooms": rooms_data,
            "total_rooms": total_rooms,
            "occupied_rooms": occupied_rooms,
            "available_rooms": available_rooms,
            "maintenance_rooms": maintenance_rooms,
            "cleaning_rooms": cleaning_rooms,
            "occupancy_rate": round(occupancy_rate, 1),
            "status_filter": status_filter,
            "store_id": store_id,
            "active_page": "room_occupancy_report"
        }
    )

@app.get("/admin/reports/room-collections")
@app.get("/admin/reports/room-collections/")
async def admin_room_collections_report(
    request: Request,
    store_id: str = Query("All"),
    from_date: str = Query(None),
    to_date: str = Query(None),
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    today = datetime.date.today().isoformat()
    if not from_date: from_date = today
    if not to_date: to_date = today

    stores = db.query(models.Store).all()

    query = db.query(
        models.RoomBooking.id,
        models.RoomBooking.created_at,
        models.RoomBooking.customer_name,
        models.Room.room_number.label("room_name"),
        models.RoomBooking.nights,
        models.RoomBooking.total_amount,
        models.RoomBooking.paid_amount,
        models.RoomBooking.balance,
        models.RoomBooking.payment_method,
        models.RoomBooking.status
    ).join(models.Room, models.Room.id == models.RoomBooking.room_id)\
     .filter(func.date(models.RoomBooking.created_at) >= from_date)\
     .filter(func.date(models.RoomBooking.created_at) <= to_date)

    room_collections = query.all()

    total_amount = sum(b.total_amount for b in room_collections)
    total_collected = sum(b.paid_amount for b in room_collections)
    total_balance = sum(b.balance for b in room_collections)
    total_bookings = len(room_collections)

    return templates.TemplateResponse(
        request=request,
        name="room_collections_report.html",
        context={
            "settings": settings,
            "stores": stores,
            "from_date": from_date,
            "to_date": to_date,
            "room_collections": room_collections,
            "total_amount": total_amount,
            "total_collected": total_collected,
            "total_balance": total_balance,
            "total_bookings": total_bookings,
            "active_page": "room_sales_report"
        }
    )

@app.get("/admin/reports/statement-profit")
async def admin_statement_profit_report(
    request: Request,
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    today = datetime.date.today().isoformat()
    stores = db.query(models.Store).all()
    return templates.TemplateResponse(
        request=request,
        name="statement_profit_report.html",
        context={
            "settings": settings,
            "stores": stores,
            "from_date": today,
            "to_date": today,
            "active_page": "statement_profit"
        }
    )

@app.get("/admin/reports/api/statement-profit")
async def api_statement_profit(
    from_date: str,
    to_date: str,
    store_id: str = "All",
    db: Session = Depends(get_db)
):
    # Logic to calculate profit/loss
    # 1. Total Sales (Revenue)
    sales_query = db.query(func.sum(models.Order.total_amount)).filter(
        models.Order.status == 'paid',
        func.date(models.Order.created_at) >= from_date,
        func.date(models.Order.created_at) <= to_date
    )
    if store_id != "All":
        sales_query = sales_query.filter(models.Order.store_id == int(store_id))
    total_sales = sales_query.scalar() or 0.0

    # 2. Total Purchases (COGS - simplified)
    purchase_query = db.query(func.sum(models.Purchase.total_amount)).filter(
        func.date(models.Purchase.purchase_date) >= from_date,
        func.date(models.Purchase.purchase_date) <= to_date
    )
    if store_id != "All":
        purchase_query = purchase_query.filter(models.Purchase.store_id == int(store_id))
    total_purchases = purchase_query.scalar() or 0.0

    # 3. Total Expenses
    expense_query = db.query(func.sum(models.Expense.amount)).filter(
        func.date(models.Expense.expense_date) >= from_date,
        func.date(models.Expense.expense_date) <= to_date
    )
    if store_id != "All":
        expense_query = expense_query.filter(models.Expense.store_id == int(store_id))
    total_expenses = expense_query.scalar() or 0.0

    gross_profit = total_sales - total_purchases
    net_profit = gross_profit - total_expenses

    data = [
        {"name": "REVENUE", "amount": 0, "level": 0, "is_total": True},
        {"name": "Total Sales", "amount": total_sales, "level": 1, "is_total": False},
        {"name": "TOTAL REVENUE", "amount": total_sales, "level": 0, "is_total": True},
        {"name": "COST OF SALES", "amount": 0, "level": 0, "is_total": True},
        {"name": "Total Purchases", "amount": total_purchases, "level": 1, "is_total": False},
        {"name": "TOTAL COST OF SALES", "amount": total_purchases, "level": 0, "is_total": True},
        {"name": "GROSS PROFIT", "amount": gross_profit, "level": 0, "is_total": True},
        {"name": "OPERATING EXPENSES", "amount": 0, "level": 0, "is_total": True},
        {"name": "Total Expenses", "amount": total_expenses, "level": 1, "is_total": False},
        {"name": "TOTAL EXPENSES", "amount": total_expenses, "level": 0, "is_total": True},
        {"name": "NET PROFIT / LOSS", "amount": net_profit, "level": 0, "is_total": True},
    ]

    return {"data": data}

@app.get("/admin/reports/item-ledger")
async def admin_item_ledger_report(
    request: Request,
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    today = datetime.date.today().isoformat()
    stores = db.query(models.Store).all()
    products = db.query(models.Product).all()
    return templates.TemplateResponse(
        request=request,
        name="item_ledger_report.html",
        context={
            "settings": settings,
            "stores": stores,
            "products": products,
            "from_date": today,
            "to_date": today,
            "active_page": "item_ledger"
        }
    )

@app.get("/admin/reports/api/item-ledger")
async def api_item_ledger(
    product_id: int,
    from_date: str,
    to_date: str,
    store_id: str = "All",
    db: Session = Depends(get_db)
):
    # Transactions: Sales (Out)
    sales = db.query(
        models.OrderItem.quantity.label("qty_out"),
        models.Order.created_at.label("date"),
        models.Order.id.label("ref"),
        literal("Sales").label("type")
    ).join(models.Order, models.Order.id == models.OrderItem.order_id)\
     .filter(models.OrderItem.product_id == product_id)\
     .filter(func.date(models.Order.created_at) >= from_date)\
     .filter(func.date(models.Order.created_at) <= to_date)
    
    if store_id != "All":
        sales = sales.filter(models.Order.store_id == int(store_id))
        
    # Transactions: Purchases (In)
    purchases = db.query(
        models.PurchaseItem.quantity.label("qty_in"),
        models.Purchase.purchase_date.label("date"),
        models.Purchase.id.label("ref"),
        literal("Purchase").label("type")
    ).join(models.Purchase, models.Purchase.id == models.PurchaseItem.purchase_id)\
     .filter(models.PurchaseItem.product_id == product_id)\
     .filter(func.date(models.Purchase.purchase_date) >= from_date)\
     .filter(func.date(models.Purchase.purchase_date) <= to_date)

    if store_id != "All":
        purchases = purchases.filter(models.Purchase.store_id == int(store_id))

    # Combine and sort
    transactions = []
    for s in sales.all():
        transactions.append({
            "date": s.date.strftime('%Y-%m-%d %H:%M'),
            "reference": f"Order #{s.ref}",
            "narrative": "Item Sale",
            "qty_in": 0,
            "qty_out": s.qty_out,
            "timestamp": s.date
        })
    for p in purchases.all():
        transactions.append({
            "date": p.date.strftime('%Y-%m-%d %H:%M'),
            "reference": f"Purchase #{p.ref}",
            "narrative": "Item Purchase",
            "qty_in": p.qty_in,
            "qty_out": 0,
            "timestamp": p.date
        })
        
    transactions.sort(key=lambda x: x['timestamp'])
    
    # Calculate running balance
    balance = 0
    for t in transactions:
        balance += (t['qty_in'] or 0) - (t['qty_out'] or 0)
        t['balance'] = balance
        
    return {"data": transactions, "opening_balance": 0}

# --- SEED DATA ---

@app.get("/seed")
async def seed_data(db: Session = Depends(get_db)):
    perform_db_seed(db)
    return {"message": "Database seeded with ERP data"}

@app.get("/admin/purchases", response_class=HTMLResponse)
async def list_purchases(
    request: Request, 
    store_id: str = None, 
    status: str = 'All',
    from_date: str = None,
    to_date: str = None,
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    
    query = db.query(models.Purchase)
    
    if store_id:
        query = query.filter(models.Purchase.store_id == int(store_id))
    
    if status == 'Due':
        query = query.filter(models.Purchase.balance > 0)
    elif status == 'Paid':
        query = query.filter(models.Purchase.balance == 0)
        
    if not from_date:
        from_date = (datetime.datetime.utcnow() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    if not to_date:
        to_date = datetime.datetime.utcnow().strftime('%Y-%m-%d')
        
    purchases = query.order_by(models.Purchase.purchase_date.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="purchases.html", 
        context={
            "purchases": purchases, 
            "stores": stores,
            "status": status,
            "store_id": store_id,
            "from_date": from_date,
            "to_date": to_date,
            "settings": settings,
            "active_page": "purchases"
        }
    )

@app.get("/admin/payment-schedules", response_class=HTMLResponse)
async def list_payment_schedules(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    schedules = db.query(models.PaymentSchedule).order_by(models.PaymentSchedule.date.desc()).all()
    pending_pos = db.query(models.Purchase).filter(models.Purchase.balance > 0, models.Purchase.payment_schedule_id is None).all()
    return templates.TemplateResponse(
        request=request,
        name="payment_schedule.html",
        context={
            "schedules": schedules,
            "pending_pos": pending_pos,
            "settings": settings,
            "active_page": "payments"
        }
    )

@app.get("/admin/lpos", response_class=HTMLResponse)
async def list_lpos(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="lpos.html",
        context={
            "settings": settings,
            "active_page": "lpos"
        }
    )

@app.get("/admin/all-lpos")
async def all_lpos(db: Session = Depends(get_db)):
    # Fetch purchases with status 'LPO'
    lpos = db.query(models.Purchase).filter(models.Purchase.status == "LPO").all()
    data = []
    for lpo in lpos:
        data.append([
            lpo.bill_no,
            lpo.supplier.name if lpo.supplier else "N/A",
            lpo.purchase_date.strftime('%Y-%m-%d'),
            "", # Due Date
            lpo.status,
            "VAT", # T.Type
            lpo.amount,
            lpo.attendant.name if lpo.attendant else "System",
            lpo.store.name if lpo.store else "Default",
            f'<a href="/admin/purchase/{lpo.id}" class="btn btn-xs btn-info">View</a>'
        ])
    return {"data": data}

@app.get("/admin/direct-purchase", response_class=HTMLResponse)
async def direct_purchase(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    suppliers = db.query(models.Supplier).all()
    stores = db.query(models.Store).all()
    products = db.query(models.Product).all()
    units = db.query(models.Unit).all()
    tax_types = db.query(models.TaxType).all()
    accounts = db.query(models.Account).all()
    
    # Define asset and expense accounts based on some logic or codes
    # For now, just passing all accounts and filtering in template
    
    return templates.TemplateResponse(
        request=request,
        name="direct_purchase.html",
        context={
            "settings": settings,
            "suppliers": suppliers,
            "stores": stores,
            "products": products,
            "units": units,
            "tax_types": tax_types,
            "accounts": accounts,
            "today_date": datetime.datetime.utcnow().strftime('%Y-%m-%d'),
            "today_time": datetime.datetime.utcnow().strftime('%H:%M:%S'),
            "active_page": "direct_purchase"
        }
    )

@app.get("/admin/new-lpo", response_class=HTMLResponse)
async def new_lpo(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    suppliers = db.query(models.Supplier).all()
    stores = db.query(models.Store).all()
    products = db.query(models.Product).all()
    units = db.query(models.Unit).all()
    tax_types = db.query(models.TaxType).all()
    accounts = db.query(models.Account).all()
    
    return templates.TemplateResponse(
        request=request,
        name="new_lpo.html",
        context={
            "settings": settings,
            "suppliers": suppliers,
            "stores": stores,
            "products": products,
            "units": units,
            "tax_types": tax_types,
            "accounts": accounts,
            "today_date": datetime.datetime.utcnow().strftime('%Y-%m-%d'),
            "today_time": datetime.datetime.utcnow().strftime('%H:%M:%S'),
            "active_page": "new_lpo"
        }
    )

@app.post("/admin/save-direct-purchase")
async def save_purchase(
    request: Request,
    db: Session = Depends(get_db),
    order_type: str = Form(...),
    supplier_id: int = Form(...),
    store_id: int = Form(...),
    order_date: str = Form(...),
    bill_no: str = Form(None),
    payment_due: str = Form(None),
    asset_account_id: str = Form(None),
    expense_account_id: str = Form(None),
    narrative: str = Form(None),
    total: float = Form(...),
    item: List[int] = Form(...),
    qty: List[float] = Form(...),
    rate: List[float] = Form(...),
    tax_id: List[float] = Form(...),
    amount: List[float] = Form(...),
    item_description: List[str] = Form(None),
    unit: List[int] = Form(None),
    payment_method_id: int = Form(None),
    paid_amount: float = Form(0.0),
    reference: str = Form(None)
):
    try:
        # 1. Create Purchase Record
        status = "LPO" if order_type == "lpo" else "Received"
        balance = total - paid_amount
        
        db_purchase = models.Purchase(
            bill_no=bill_no or f"PUR-{datetime.datetime.utcnow().strftime('%y%m%d%H%M%S')}",
            supplier_id=supplier_id,
            amount=total,
            balance=balance,
            store_id=store_id,
            purchase_date=datetime.datetime.strptime(order_date, '%Y-%m-%d'),
            status=status
        )
        db.add(db_purchase)
        db.flush() # Get ID
        
        # 2. Add Items
        for i in range(len(item)):
            p_item = models.PurchaseItem(
                purchase_id=db_purchase.id,
                product_id=item[i],
                description=item_description[i] if item_description and i < len(item_description) else None,
                quantity=qty[i],
                unit_price=rate[i],
                tax_rate=tax_id[i],
                total_amount=amount[i],
                unit_id=unit[i] if unit and i < len(unit) else None
            )
            db.add(p_item)
            
            # 3. Update Inventory if Received
            if status == "Received":
                product = db.query(models.Product).filter(models.Product.id == item[i]).first()
                if product:
                    product.stock_quantity += qty[i]
        
        # 4. Update Supplier Balance if Received
        if status == "Received" and balance > 0:
            supplier = db.query(models.Supplier).filter(models.Supplier.id == supplier_id).first()
            if supplier:
                supplier.balance += balance
                
        db.commit()
        
        # Redirect based on type
        if order_type == "lpo":
            return RedirectResponse(url="/admin/lpos", status_code=303)
        else:
            return RedirectResponse(url="/admin/purchases", status_code=303)
            
    except Exception as e:
        db.rollback()
        print(f"Error saving purchase: {e}")
        # In a real app, return error to user
        return RedirectResponse(url="/admin/direct-purchase?error=1", status_code=303)

@app.post("/admin/save-supplier")
async def save_supplier(
    request: Request,
    name: str = Form(...),
    phone: str = Form(None),
    db: Session = Depends(get_db)
):
    db_supplier = models.Supplier(name=name, phone=phone)
    db.add(db_supplier)
    db.commit()
    return RedirectResponse(url=request.headers.get("referer") or "/admin/purchases", status_code=303)

# --- INVENTORY PLACEHOLDER ROUTES ---

@app.get("/admin/serials", response_class=HTMLResponse)
async def inventory_serials(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    serials = db.query(models.ProductSerial).all()
    products = db.query(models.Product).all()
    return templates.TemplateResponse(
        request=request,
        name="serials.html",
        context={
            "settings": settings, 
            "title": "Item Serials", 
            "active_page": "serials",
            "serials": serials,
            "products": products
        }
    )

@app.post("/inventory/generate-serials")
async def generate_serials(
    request: Request,
    product_ids: list[int] = Form(...),
    quantities: list[int] = Form(...),
    narratives: list[str] = Form(...),
    db: Session = Depends(get_db)
):
    import random
    import string
    
    for i in range(len(product_ids)):
        prod_id = product_ids[i]
        qty = quantities[i]
        narrative = narratives[i] if i < len(narratives) else ""
        
        product = db.query(models.Product).filter(models.Product.id == prod_id).first()
        if not product:
            continue
            
        for _ in range(qty):
            # Generate a random serial if not provided
            # In a real app, this might come from user input or a specific format
            random_serial = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
            new_serial = models.ProductSerial(
                product_id=prod_id,
                serial_number=f"SR-{product.id}-{random_serial}",
                condition="Good",
                narrative=narrative,
                status="available"
            )
            db.add(new_serial)
    
    db.commit()
    return RedirectResponse(url="/admin/serials", status_code=303)

@app.get("/inventory/delete-serial/{serial_id}")
async def delete_serial(serial_id: int, db: Session = Depends(get_db)):
    serial = db.query(models.ProductSerial).filter(models.ProductSerial.id == serial_id).first()
    if serial:
        db.delete(serial)
        db.commit()
    return RedirectResponse(url="/admin/serials", status_code=303)

@app.get("/inventory/print-serials", response_class=HTMLResponse)
async def print_serials(request: Request):
    return "<h5>Serial Printing Service</h5><p>Printing labels for all available serials...</p>"

@app.get("/admin/requisition", response_class=HTMLResponse)
async def inventory_requisition(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    suppliers = db.query(models.Supplier).all()
    products = db.query(models.Product).all()
    requisitions = db.query(models.Requisition).order_by(models.Requisition.created_at.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="requisition.html",
        context={
            "settings": settings, 
            "title": "Requisition", 
            "active_page": "requisition",
            "stores": stores,
            "suppliers": suppliers,
            "products": products,
            "requisitions": requisitions
        }
    )

@app.post("/admin/add-requisition")
async def add_requisition(
    request: Request,
    receiving_store_id: int = Form(...),
    issuing_store_id: int = Form(None),
    supplier_id: int = Form(None),
    priority: str = Form("Medium"),
    request_type: str = Form("Internal"),
    product_ids: list[int] = Form(...),
    quantities: list[float] = Form(...),
    prices: list[float] = Form(...),
    narratives: list[str] = Form(...),
    db: Session = Depends(get_db)
):
    import random
    import string
    
    # Generate a unique code
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    req_code = f"REQ-{datetime.datetime.now().strftime('%y%m%d')}-{random_str}"
    
    # Use first staff as request person for now (simulating logged in user)
    staff = db.query(models.Staff).first()
    staff_id = staff.id if staff else None
    
    new_req = models.Requisition(
        code=req_code,
        receiving_store_id=receiving_store_id,
        issuing_store_id=issuing_store_id,
        supplier_id=supplier_id,
        request_person_id=staff_id,
        priority=priority,
        request_type=request_type,
        status="Pending"
    )
    db.add(new_req)
    db.flush() # Get the id
    
    for i in range(len(product_ids)):
        prod_id = product_ids[i]
        qty = quantities[i]
        price = prices[i] if i < len(prices) and prices[i] else 0.0
        narrative = narratives[i] if i < len(narratives) else ""
        
        if qty > 0:
            item = models.RequisitionItem(
                requisition_id=new_req.id,
                product_id=prod_id,
                quantity=qty,
                unit_price=price,
                narrative=narrative
            )
            db.add(item)
    
    db.commit()
    return RedirectResponse(url="/admin/requisition", status_code=303)

@app.get("/admin/delete-requisition/{req_id}")
async def delete_requisition(req_id: int, db: Session = Depends(get_db)):
    # Delete items first due to FK
    db.query(models.RequisitionItem).filter(models.RequisitionItem.requisition_id == req_id).delete()
    db.query(models.Requisition).filter(models.Requisition.id == req_id).delete()
    db.commit()
    return RedirectResponse(url="/admin/requisition", status_code=303)

@app.get("/admin/stock-balances", response_class=HTMLResponse)
async def inventory_balances(request: Request, store_id: int = None, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    products = db.query(models.Product).all()
    
    if store_id:
        stock_items = db.query(models.ProductStoreStock).filter(models.ProductStoreStock.store_id == store_id).all()
    else:
        # Default to the first store if available, or just show all if no stores exist
        first_store = db.query(models.Store).first()
        if first_store:
            store_id = first_store.id
            stock_items = db.query(models.ProductStoreStock).filter(models.ProductStoreStock.store_id == store_id).all()
        else:
            stock_items = []
            
    total_purchase_value = sum(item.product.cost_price * item.quantity for item in stock_items)
    total_markup_value = sum((item.product.selling_price - item.product.cost_price) * item.quantity for item in stock_items)
    
    return templates.TemplateResponse(
        request=request, 
        name="stock_balances.html", 
        context={
            "settings": settings, 
            "title": "Stock Balances", 
            "active_page": "balances",
            "stores": stores,
            "products": products,
            "stock_items": stock_items,
            "selected_store_id": store_id,
            "total_purchase_value": total_purchase_value,
            "total_markup_value": total_markup_value
        }
    )

@app.get("/admin/stock-take", response_class=HTMLResponse)
async def inventory_stock_take(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    categories = db.query(models.Category).all()
    instances = db.query(models.StockTakeInstance).order_by(models.StockTakeInstance.created_at.desc()).all()
    
    return templates.TemplateResponse(
        request=request, 
        name="stock_take.html", 
        context={
            "settings": settings, 
            "title": "Stock Takes", 
            "active_page": "stock_take",
            "stores": stores,
            "categories": categories,
            "instances": instances,
            "now": datetime.datetime.utcnow()
        }
    )

@app.post("/admin/stock-take/new")
async def new_stock_take_instance(
    request: Request,
    store_id: int = Form(...),
    name: str = Form(...),
    categories: list[str] = Form(...),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    # Generate reference
    import random
    import string
    ref = "J" + "".join(random.choices(string.ascii_uppercase + string.digits, k=9))
    
    instance = models.StockTakeInstance(
        name=name,
        reference=ref,
        store_id=store_id,
        narrative=narrative,
        status="Pending"
    )
    db.add(instance)
    db.flush()
    
    # Populate items based on categories and store
    query = db.query(models.ProductStoreStock).filter(models.ProductStoreStock.store_id == store_id)
    if "ALL" not in categories:
        cat_ids = [int(c) for c in categories]
        query = query.join(models.Product).filter(models.Product.category_id.in_(cat_ids))
    
    stocks = query.all()
    for s in stocks:
        st_item = models.StockTakeItem(
            instance_id=instance.id,
            product_id=s.product_id,
            expected_quantity=s.quantity,
            actual_quantity=s.quantity, # Default to expected
            variance=0.0
        )
        db.add(st_item)
    
    db.commit()
    return RedirectResponse(url="/admin/stock-take", status_code=303)

@app.get("/admin/stock-take/details/{instance_id}", response_class=HTMLResponse)
async def stock_take_details(request: Request, instance_id: int, db: Session = Depends(get_db)):
    settings = get_settings(db)
    instance = db.query(models.StockTakeInstance).filter(models.StockTakeInstance.id == instance_id).first()
    items = db.query(models.StockTakeItem).filter(models.StockTakeItem.instance_id == instance_id).all()
    
    return templates.TemplateResponse(
        request=request, 
        name="stock_take_details.html", 
        context={
            "settings": settings, 
            "instance": instance,
            "items": items,
            "active_page": "stock_take"
        }
    )

@app.post("/admin/stock-take/item-update")
async def stock_take_item_update(
    item_id: int = Form(...),
    actual_qty: float = Form(...),
    db: Session = Depends(get_db)
):
    item = db.query(models.StockTakeItem).filter(models.StockTakeItem.id == item_id).first()
    if item:
        item.actual_quantity = actual_qty
        item.variance = actual_qty - item.expected_quantity
        db.commit()
        return {"resp": "1"}
    return {"resp": "0"}

@app.get("/admin/stock-take/reconcile/{instance_id}")
async def reconcile_stock_take(instance_id: int, db: Session = Depends(get_db)):
    instance = db.query(models.StockTakeInstance).filter(models.StockTakeInstance.id == instance_id).first()
    if not instance or instance.status == "Reconciled":
        return RedirectResponse(url="/admin/stock-take", status_code=303)
        
    items = db.query(models.StockTakeItem).filter(models.StockTakeItem.instance_id == instance_id).all()
    total_variance_value = 0.0
    
    for item in items:
        # Update actual stock in ProductStoreStock
        store_stock = db.query(models.ProductStoreStock).filter(
            models.ProductStoreStock.store_id == instance.store_id,
            models.ProductStoreStock.product_id == item.product_id
        ).first()
        
        if store_stock:
            store_stock.quantity = item.actual_quantity
            store_stock.last_stock_take = datetime.datetime.utcnow()
            
        total_variance_value += item.variance * (item.product.cost_price or 0)
        
    instance.status = "Reconciled"
    instance.reconciled_at = datetime.datetime.utcnow()
    instance.reconciliation_value = total_variance_value
    
    db.commit()
    return RedirectResponse(url="/admin/stock-take", status_code=303)

@app.get("/admin/transfer-stock", response_class=HTMLResponse)
async def inventory_transfer(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    users = db.query(models.Staff).all()
    movements = db.query(models.StockMovement).order_by(models.StockMovement.created_at.desc()).limit(100).all()
    
    return templates.TemplateResponse(
        request=request, 
        name="stock_transfer.html", 
        context={
            "settings": settings, 
            "title": "Move Stock", 
            "active_page": "transfer",
            "stores": stores,
            "users": users,
            "movements": movements
        }
    )

@app.get("/admin/store-items-json/{store_id}")
async def store_items_json(store_id: int, db: Session = Depends(get_db)):
    stocks = db.query(models.ProductStoreStock).filter(models.ProductStoreStock.store_id == store_id).all()
    return [
        {
            "product_id": s.product_id,
            "product_name": s.product.name,
            "quantity": s.quantity
        } for s in stocks
    ]

@app.post("/admin/stock-transfer/process")
async def process_stock_transfer(
    request: Request,
    from_store_id: int = Form(...),
    to_store_id: int = Form(...),
    items: list[int] = Form(...),
    qty: list[float] = Form(...),
    notes: list[str] = Form(None),
    issued_to_id: int = Form(None),
    db: Session = Depends(get_db)
):
    import random
    import string
    ref = "TRF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
    
    movement = models.StockMovement(
        reference=ref,
        from_store_id=from_store_id,
        to_store_id=to_store_id,
        issued_to_id=issued_to_id,
        status="Completed"
    )
    db.add(movement)
    db.flush()
    
    for i in range(len(items)):
        prod_id = items[i]
        q = qty[i]
        notes[i] if notes and i < len(notes) else ""
        
        # Deduct from source
        src_stock = db.query(models.ProductStoreStock).filter(
            models.ProductStoreStock.store_id == from_store_id,
            models.ProductStoreStock.product_id == prod_id
        ).first()
        if src_stock:
            src_stock.quantity -= q
            
        # Add to destination
        dest_stock = db.query(models.ProductStoreStock).filter(
            models.ProductStoreStock.store_id == to_store_id,
            models.ProductStoreStock.product_id == prod_id
        ).first()
        if not dest_stock:
            dest_stock = models.ProductStoreStock(
                store_id=to_store_id,
                product_id=prod_id,
                quantity=0
            )
            db.add(dest_stock)
        dest_stock.quantity += q
        
        move_item = models.StockMovementItem(
            movement_id=movement.id,
            product_id=prod_id,
            quantity=q
        )
        db.add(move_item)
        
    db.commit()
    return RedirectResponse(url="/admin/transfer-stock", status_code=303)

@app.get("/admin/production", response_class=HTMLResponse)
async def inventory_production(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    units = db.query(models.Unit).all()
    categories = db.query(models.Category).all()
    tax_types = db.query(models.TaxType).all()
    stores = db.query(models.Store).all()
    products = db.query(models.Product).all()
    # Fetch products that have recipes
    recipes = db.query(models.Product).join(models.ProductRecipe, models.Product.id == models.ProductRecipe.product_id).distinct().all()
    
    return templates.TemplateResponse(
        request=request, 
        name="production.html", 
        context={
            "settings": settings, 
            "title": "Production", 
            "active_page": "production",
            "units": units,
            "categories": categories,
            "tax_types": tax_types,
            "stores": stores,
            "products": products,
            "recipes": recipes
        }
    )

@app.post("/admin/production/save")
async def save_production_recipe(
    request: Request,
    name: str = Form(...),
    unit_id: int = Form(...),
    category_id: int = Form(...),
    tax_type_id: int = Form(...),
    store_id: int = Form(...),
    purpose: str = Form(...),
    selling_price: float = Form(...),
    item_ids: list[int] = Form(...),
    quantities: list[float] = Form(...),
    db: Session = Depends(get_db)
):
    # Calculate total cost from ingredients
    total_cost = 0
    for i in range(len(item_ids)):
        prod = db.query(models.Product).filter(models.Product.id == item_ids[i]).first()
        if prod:
            total_cost += (prod.cost_price or 0) * quantities[i]
            
    # Create or Update Product
    product = models.Product(
        name=name,
        unit_id=unit_id,
        category_id=category_id,
        tax_type_id=tax_type_id,
        store_id=store_id,
        purpose=purpose,
        selling_price=selling_price,
        cost_price=total_cost
    )
    db.add(product)
    db.flush()
    
    # Save Recipe Ingredients
    for i in range(len(item_ids)):
        recipe_item = models.ProductRecipe(
            product_id=product.id,
            component_id=item_ids[i],
            quantity_required=quantities[i]
        )
        db.add(recipe_item)
        
    db.commit()
    return RedirectResponse(url="/admin/production", status_code=303)

@app.get("/admin/wastage", response_class=HTMLResponse)
async def inventory_wastage(request: Request, orgid: int = None, from_date: str = None, to_date: str = None, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    accounts = db.query(models.Account).all()
    
    return templates.TemplateResponse(
        request=request, 
        name="wastage.html", 
        context={
            "settings": settings, 
            "title": "Wastages & Damages", 
            "active_page": "wastage",
            "stores": stores,
            "accounts": accounts,
            "orgid": orgid,
            "from_date": from_date,
            "to_date": to_date
        }
    )

@app.post("/sys/add_wastage")
async def add_wastage(
    store_id: int = Form(...),
    item_id: int = Form(...),
    qty: float = Form(...),
    wastage_date: str = Form(...),
    expense_id: int = Form(...),
    asset_id: int = Form(...),
    narrative: str = Form(...),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == item_id).first()
    if not product:
        return RedirectResponse(url="/admin/wastage?error=ItemNotFound", status_code=303)
        
    unit_cost = product.cost_price or 0
    total_cost = unit_cost * qty
    
    ref_no = f"WST-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}"
    
    wastage = models.Wastage(
        ref_no=ref_no,
        product_id=item_id,
        store_id=store_id,
        quantity=qty,
        cost=total_cost,
        occurrence_date=datetime.datetime.strptime(wastage_date, '%Y-%m-%d'),
        narrative=narrative,
        expense_account_id=expense_id,
        asset_account_id=asset_id if asset_id != 0 else None
    )
    db.add(wastage)
    
    # Stock adjustment
    stock = db.query(models.ProductStoreStock).filter(
        models.ProductStoreStock.product_id == item_id,
        models.ProductStoreStock.store_id == store_id
    ).first()
    
    if stock:
        stock.quantity -= qty
    else:
        new_stock = models.ProductStoreStock(product_id=item_id, store_id=store_id, quantity=-qty)
        db.add(new_stock)
        
    db.commit()
    return RedirectResponse(url="/admin/wastage", status_code=303)

@app.get("/sys/all_item_wastages")
async def all_item_wastages(from_date: str = "", to_date: str = "", orgid: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Wastage)
    if orgid and orgid != "None":
        query = query.filter(models.Wastage.store_id == int(orgid))
    if from_date:
        query = query.filter(models.Wastage.occurrence_date >= datetime.datetime.strptime(from_date, '%Y-%m-%d'))
    if to_date:
        query = query.filter(models.Wastage.occurrence_date <= datetime.datetime.strptime(to_date, '%Y-%m-%d'))
        
    wastages = query.order_by(models.Wastage.created_at.desc()).all()
    
    data = []
    for w in wastages:
        data.append([
            w.ref_no,
            f"BC-{w.product_id}",
            w.product.name if w.product else "N/A",
            w.product.unit.name if w.product and w.product.unit else "N/A",
            w.product.category.name if w.product and w.product.category else "N/A",
            f"{w.quantity:,.2f}",
            f"{w.cost:,.2f}",
            w.store.name if w.store else "N/A",
            w.occurrence_date.strftime('%Y-%m-%d'),
            w.narrative,
            "Admin", # Placeholder
            w.created_at.strftime('%Y-%m-%d %H:%M'),
            f'<div class="text-center">'
            f'<button class="btn btn-xs btn-rgp mr-1" onclick="view_waste({w.id})"><i class="fa fa-eye"></i></button>'
            f'<button class="btn btn-xs btn-rgd" onclick="delete_waste({w.id})"><i class="fa fa-trash"></i></button>'
            f'</div>'
        ])
    
    return {"data": data}

@app.post("/data/org_items")
async def get_org_items(data: str = Form(...), db: Session = Depends(get_db)):
    # Fetch products. In a real system, filter by store availability if needed.
    products = db.query(models.Product).all()
    options = '<option value="">Select item</option>'
    for p in products:
        options += f'<option value="{p.id}">{p.name}</option>'
    return HTMLResponse(content=options)

@app.post("/data/set_org")
async def set_org(id: str = Form(...), db: Session = Depends(get_db)):
    # In a real app, you'd save this to session
    # For now we just return success
    return {"resp": "1", "message": "Store selected"}

@app.post("/data/search_barcode")
async def search_barcode(data: str = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.sku == data).first()
    if product:
        return {
            "data_control": "1",
            "item_id": product.id,
            "marked_price": product.selling_price,
            "barcode": product.sku,
            "scannerQty": 1
        }
    return {"data_control": "0", "message": "Item not found"}

@app.post("/data/specific_item")
async def specific_item(data: int = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == data).first()
    if product:
        return {
            "data_control": "1",
            "marked_price": product.selling_price,
            "barcode": product.sku,
            "buying_price": product.cost_price or 0
        }
    return {"data_control": "0", "message": "Item not found"}

@app.get("/delete/waste_record/{id}")
@app.post("/delete/waste_record/{id}")
async def delete_waste_record(id: int, db: Session = Depends(get_db)):
    waste = db.query(models.Wastage).filter(models.Wastage.id == id).first()
    if waste:
        # Revert stock
        stock = db.query(models.ProductStoreStock).filter(
            models.ProductStoreStock.product_id == waste.product_id,
            models.ProductStoreStock.store_id == waste.store_id
        ).first()
        if stock:
            stock.quantity += waste.quantity
        
        db.delete(waste)
        db.commit()
        return JSONResponse(content={"resp": "1", "message": "Record deleted successfully"})
    return JSONResponse(content={"resp": "0", "message": "Record not found"})

@app.get("/admin/fixed-assets", response_class=HTMLResponse)
async def inventory_assets(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    accounts = db.query(models.Account).all()
    depreciations = db.query(models.Depreciation).order_by(models.Depreciation.timestamp.desc()).all()
    
    return templates.TemplateResponse(
        request=request, 
        name="fixed_assets.html", 
        context={
            "settings": settings, 
            "title": "Fixed Assets", 
            "active_page": "assets",
            "accounts": accounts,
            "depreciations": depreciations
        }
    )

@app.get("/sys/all_items")
async def sys_all_items(
    request: Request, 
    class_type: str = Query("All", alias="class"), 
    assets: str = None,
    draw: int = 1,
    start: int = 0,
    length: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(models.Product)
    
    if assets == "Assets":
        # Filter for items that are assets
        query = query.filter(models.Product.purpose == "Fixed Asset")
    # If "All", don't filter by purpose
    
    total_count = query.count()
    items = query.offset(start).limit(length).all()
    
    data = []
    for item in items:
        data.append([
            item.name,
            item.sku or f"SKU-{item.id}",
            item.unit.name if item.unit else "N/A",
            item.category.name if item.category else "N/A",
            item.brand or "N/A",
            item.color or "N/A",
            f'<input type="number" step="0.01" class="form-control form-control-sm" id="item_id_{item.id}" value="{item.cost_price or 0}" onchange="save_buying_price({item.id})">',
            f"{(item.cost_price or 0):,.2f}", # Simplified NBV logic
            f'<input type="number" step="0.01" class="form-control form-control-sm" id="itemid_{item.id}" value="{item.selling_price or 0}" onchange="save_price({item.id})">',
            item.stock_quantity,
            item.reorder_level,
            '<span class="badge badge-success">Normal</span>',
            item.tax_type.name if item.tax_type else "N/A",
            f'<div class="text-center"><input type="checkbox" {"checked" if item.purpose == "For Production" else ""} onclick="for_kitchen({item.id})"></div>',
            f'<div class="text-center"><input type="checkbox" onclick="qty_predefined({item.id})"></div>',
            item.narrative or "",
            f'<div class="text-center">'
            f'<button class="btn btn-xs btn-rgp mr-1" onclick="mark_as_asset({item.id})"><i class="fa fa-tag"></i></button>'
            f'<button class="btn btn-xs btn-rgd" onclick="delete_item({item.id})"><i class="fa fa-trash"></i></button>'
            f'</div>'
        ])
    
    return {
        "draw": draw,
        "recordsTotal": total_count,
        "recordsFiltered": total_count,
        "data": data
    }

@app.post("/sys/asset_depreciation")
async def asset_depreciation(
    asset_id: int = Form(...),
    expense_id: int = Form(...),
    amount: float = Form(...),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    code = f"DEP-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}"
    
    depreciation = models.Depreciation(
        code=code,
        asset_account_id=asset_id,
        expense_account_id=expense_id,
        amount=amount,
        narrative=narrative
    )
    db.add(depreciation)
    db.commit()
    
    return JSONResponse(content={"resp": "1", "message": "Depreciation record saved successfully!"})

@app.post("/sys/delete_depreciation_instance")
async def delete_depreciation_instance(code: str = Form(...), db: Session = Depends(get_db)):
    dep = db.query(models.Depreciation).filter(models.Depreciation.code == code).first()
    if dep:
        db.delete(dep)
        db.commit()
        return JSONResponse(content={"resp": "1", "message": "Instance deleted"})
    return JSONResponse(content={"resp": "0", "message": "Not found"})

@app.post("/sys/save_item_price")
async def save_item_price(itemid: int = Form(...), itemprice: float = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == itemid).first()
    if product:
        product.selling_price = itemprice
        db.commit()
        return {"resp": "1", "message": "Marked price updated!"}
    return {"resp": "0", "message": "Item not found"}

@app.post("/sys/save_item_buying_price")
async def save_item_buying_price(itemid: int = Form(...), itemprice: float = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == itemid).first()
    if product:
        product.cost_price = itemprice
        db.commit()
        return {"resp": "1", "message": "Buying price updated!"}
    return {"resp": "0", "message": "Item not found"}

@app.post("/sys/for_kitchen")
async def for_kitchen(itemid: int = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == itemid).first()
    if product:
        product.purpose = "For Production" if product.purpose != "For Production" else "For Sale"
        db.commit()
        return "Kitchen item status updated!"
    return "Item not found"

@app.post("/sys/mark_as_asset")
async def mark_as_asset(itemid: int = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == itemid).first()
    if product:
        product.purpose = "Fixed Asset" if product.purpose != "Fixed Asset" else "For Sale"
        db.commit()
        return {"resp": "1", "message": f"Item '{product.name}' status updated to {product.purpose}!"}
    return {"resp": "0", "message": "Item not found"}

@app.post("/sys/qty_predefined")
async def qty_predefined(itemid: int = Form(...), db: Session = Depends(get_db)):
    return "Quantity predefined status updated!"

# --- INVENTORY ACTIONS & DATA ---

@app.get("/admin/all-items-json")
async def all_items_json(request: Request, db: Session = Depends(get_db)):
    # Basic DataTables server-side implementation
    items = db.query(models.Product).all()
    data = []
    for item in items:
        # Check stock against reorder level
        reorder_lvl = item.reorder_level if item.reorder_level is not None else 0
        stock_qty = item.stock_quantity if item.stock_quantity is not None else 0
        reorder_status = '<span class="badge badge-success">OK</span>' if stock_qty > reorder_lvl else '<span class="badge badge-danger">LOW</span>'
        
        data.append({
            "name": item.name,
            "sku": item.sku or "-",
            "unit": item.unit.name if item.unit else "-",
            "category": item.category.name if item.category else "-",
            "brand": item.brand or "-",
            "color": item.color or "-",
            "buying_price": f'<input type="number" step="0.01" class="form-control form-control-sm" id="buying_price_{item.id}" value="{item.cost_price or 0}" onchange="save_buying_price({item.id})">',
            "marked_price": f'<input type="number" step="0.01" class="form-control form-control-sm" id="marked_price_{item.id}" value="{item.selling_price or 0}" onchange="save_price({item.id})">',
            "total_qty": stock_qty,
            "reorder_level": reorder_lvl,
            "reorder_status": reorder_status,
            "tax_type": item.tax_type.name if item.tax_type else "-",
            "kitchen_item": f'<div class="custom-control custom-switch"><input type="checkbox" class="custom-control-input" id="kitchen_{item.id}" {"checked" if item.purpose == "For Production" else ""} onchange="$.post(\'/sys/for_kitchen\', {itemid: {item.id}})" ><label class="custom-control-label" for="kitchen_{item.id}"></label></div>',
            "qty_predefined": "-",
            "expiry_date": item.expiry_date.strftime("%Y-%m-%d") if item.expiry_date else "-",
            "narrative": item.narrative or "-",
            "action": f'<div class="btn-group"><a href="/admin/edit-item/{item.id}" class="btn btn-xs btn-info"><i class="fas fa-edit"></i></a><button class="btn btn-xs btn-danger" onclick="delete_item({item.id})"><i class="fas fa-trash"></i></button></div>'
        })
    
    return {
        "draw": int(request.query_params.get("draw", 1)),
        "recordsTotal": len(data),
        "recordsFiltered": len(data),
        "data": data
    }

@app.post("/admin/save-item-price")
async def admin_save_item_price(itemid: int = Form(...), itemprice: float = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == itemid).first()
    if product:
        product.selling_price = itemprice
        db.commit()
    return {"status": "success"}

@app.post("/admin/save-item-buying-price")
async def admin_save_item_buying_price(itemid: int = Form(...), itemprice: float = Form(...), db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == itemid).first()
    if product:
        product.cost_price = itemprice
        db.commit()
    return {"status": "success"}

@app.get("/admin/add-item", response_class=HTMLResponse)
async def admin_add_item_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    categories = db.query(models.Category).all()
    units = db.query(models.Unit).all()
    tax_types = db.query(models.TaxType).all()
    stores = db.query(models.Store).all()
    return templates.TemplateResponse(
        request=request,
        name="add_item.html",
        context={
            "settings": settings,
            "categories": categories,
            "units": units,
            "tax_types": tax_types,
            "stores": stores,
            "active_page": "inventory"
        }
    )

@app.post("/admin/add-item")
async def admin_add_item(
    name: str = Form(...),
    sku: Optional[str] = Form(None),
    category_id: int = Form(...),
    unit_id: Optional[int] = Form(None),
    cost_price: float = Form(...),
    selling_price: float = Form(...),
    tax_type_id: Optional[int] = Form(None),
    store_id: Optional[int] = Form(None),
    brand: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    stock_quantity: int = Form(0),
    reorder_level: int = Form(0),
    expiry_date: Optional[str] = Form(None),
    purpose: str = Form("For Sale"),
    is_active: str = Form("true"),
    narrative: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    exp_date = None
    if expiry_date:
        try:
            exp_date = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date()
        except ValueError:
            pass
            
    is_act = True if is_active == "true" else False
    
    product = models.Product(
        name=name,
        sku=sku if sku else None,
        category_id=category_id,
        unit_id=unit_id,
        cost_price=cost_price,
        selling_price=selling_price,
        tax_type_id=tax_type_id,
        store_id=store_id,
        brand=brand if brand else None,
        color=color if color else None,
        stock_quantity=stock_quantity,
        reorder_level=reorder_level,
        expiry_date=exp_date,
        purpose=purpose,
        is_active=is_act,
        narrative=narrative if narrative else None
    )
    db.add(product)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=303)

@app.get("/admin/edit-item/{item_id}", response_class=HTMLResponse)
async def admin_edit_item_page(item_id: int, request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    item = db.query(models.Product).filter(models.Product.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    categories = db.query(models.Category).all()
    units = db.query(models.Unit).all()
    tax_types = db.query(models.TaxType).all()
    stores = db.query(models.Store).all()
    return templates.TemplateResponse(
        request=request,
        name="edit_item.html",
        context={
            "settings": settings,
            "item": item,
            "categories": categories,
            "units": units,
            "tax_types": tax_types,
            "stores": stores,
            "active_page": "inventory"
        }
    )

@app.post("/admin/edit-item/{item_id}")
async def admin_edit_item(
    item_id: int,
    name: str = Form(...),
    sku: Optional[str] = Form(None),
    category_id: int = Form(...),
    unit_id: Optional[int] = Form(None),
    cost_price: float = Form(...),
    selling_price: float = Form(...),
    tax_type_id: Optional[int] = Form(None),
    store_id: Optional[int] = Form(None),
    brand: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    stock_quantity: int = Form(...),
    reorder_level: int = Form(0),
    expiry_date: Optional[str] = Form(None),
    purpose: str = Form("For Sale"),
    is_active: str = Form("true"),
    narrative: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == item_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Item not found")
        
    exp_date = None
    if expiry_date:
        try:
            exp_date = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date()
        except ValueError:
            pass
            
    is_act = True if is_active == "true" else False
    
    product.name = name
    product.sku = sku if sku else None
    product.category_id = category_id
    product.unit_id = unit_id
    product.cost_price = cost_price
    product.selling_price = selling_price
    product.tax_type_id = tax_type_id
    product.store_id = store_id
    product.brand = brand if brand else None
    product.color = color if color else None
    product.stock_quantity = stock_quantity
    product.reorder_level = reorder_level
    product.expiry_date = exp_date
    product.purpose = purpose
    product.is_active = is_act
    product.narrative = narrative if narrative else None
    
    db.commit()
    return RedirectResponse(url="/inventory", status_code=303)

@app.get("/admin/delete-item/{item_id}")
async def delete_item(item_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == item_id).first()
    if product:
        db.delete(product)
        db.commit()
        return {"resp": "1", "message": "Item deleted successfully"}
    return {"resp": "0", "message": "Item not found"}

@app.get("/admin/digitax-items-modal", response_class=HTMLResponse)
async def digitax_modal(request: Request):
    return "<h5>Digitax Upload Modal</h5><p>Integration with Digitax KRA system coming soon.</p>"
@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    product_count = db.query(models.Product).count()
    room_count = db.query(models.Room).count()
    receipt_count = db.query(models.Receipt).count()
    return templates.TemplateResponse(
        request=request,
        name="admin_dashboard.html",
        context={
            "settings": settings,
            "product_count": product_count,
            "room_count": room_count,
            "receipt_count": receipt_count,
            "active_page": "admin"
        }
    )

@app.get("/admin/open-sales", response_class=HTMLResponse)
async def open_sales_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().date()
    return templates.TemplateResponse(
        request=request,
        name="open_sales.html",
        context={
            "settings": settings,
            "stores": stores,
            "today": today.isoformat(),
            "active_page": "open_sales"
        }
    )

@app.get("/admin/all-open-sales-data")
async def all_open_sales_data(
    request: Request,
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    org_id: str = Query(None),
    due: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(models.Order).filter(models.Order.status == 'open')
    
    # Filters
    if org_id and org_id != 'All':
        # Assuming store_id exists or filtering by item store
        pass # Will implement properly once store_id is added
    
    if from_date:
        d = datetime.datetime.strptime(from_date, '%Y-%m-%d')
        query = query.filter(models.Order.created_at >= d)
    if to_date:
        d = datetime.datetime.strptime(to_date, '%Y-%m-%d') + datetime.timedelta(days=1)
        query = query.filter(models.Order.created_at < d)

    total_records = query.count()
    orders = query.offset(start).limit(length).all()
    
    data = []
    for i, order in enumerate(orders):
        data.append({
            "serial": start + i + 1,
            "bill_no": f"ORD-{order.id:04d}",
            "customer": order.customer.name if order.customer else "Walk-in",
            "sales_point": "Counter 1", # Placeholder or real value if available
            "created_at": order.created_at.strftime('%Y-%m-%d %H:%M'),
            "attendant": order.staff.name if order.staff else "Admin",
            "net_amount": f"{order.total_amount:,.2f}",
            "balance": f"{order.total_amount:,.2f}",
            "discount": "0.00",
            "store": order.store.name if order.store else "Main Store",
            "actions": f"""
                <button class="btn btn-xs btn-info" onclick="view_sale({order.id})"><i class="fa fa-eye"></i></button>
                <button class="btn btn-xs btn-danger" onclick="void_sale({order.id})"><i class="fa fa-trash"></i></button>
                <button class="btn btn-xs btn-warning" onclick="complement_sale({order.id})"><i class="fa fa-gift"></i></button>
                <button class="btn btn-xs btn-dark" onclick="extend_credit({order.id})"><i class="fa fa-credit-card"></i></button>
            """
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.post("/admin/void-sale")
async def void_sale(order_id: int = Form(...), reason: str = Form(...), db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        return {"status": "error", "message": "Order not found"}
    
    order.status = 'voided'
    # Optionally log to VoidLog
    void_log = models.VoidLog(order_id=order.id, reason=reason)
    db.add(void_log)
    
    # Restore stock
    for item in order.items:
        product = db.query(models.Product).get(item.product_id)
        if product and not product.is_service:
            product.stock_quantity += item.quantity
            
    db.commit()
    return {"status": "success", "message": "Sale voided successfully"}

@app.get("/admin/quotations", response_class=HTMLResponse)
async def quotations_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="quotations.html",
        context={
            "settings": settings,
            "active_page": "quotations"
        }
    )

@app.get("/admin/all-quotations-data")
async def all_quotations_data(
    request: Request,
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    db: Session = Depends(get_db)
):
    query = db.query(models.Quotation)
    total_records = query.count()
    quotations = query.order_by(models.Quotation.created_at.desc()).offset(start).limit(length).all()
    
    data = []
    for i, quote in enumerate(quotations):
        data.append({
            "serial": start + i + 1,
            "bill_no": f"QUO-{quote.id:04d}",
            "customer": quote.customer.name if quote.customer else "Guest",
            "contact": quote.customer.phone if quote.customer else "N/A",
            "date": quote.created_at.strftime('%Y-%m-%d %H:%M'),
            "taxes": f"{quote.tax_amount:,.2f}",
            "total": f"{quote.total_amount:,.2f}",
            "created_by": quote.staff.name if quote.staff else "Admin",
            "actions": f"""
                <button class="btn btn-xs btn-info" onclick="view_quote({quote.id})"><i class="fa fa-eye"></i></button>
                <button class="btn btn-xs btn-danger" onclick="delete_quote({quote.id})"><i class="fa fa-trash"></i></button>
                <button class="btn btn-xs btn-success" onclick="convert_to_order({quote.id})"><i class="fa fa-shopping-cart"></i></button>
            """
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.get("/admin/invoices", response_class=HTMLResponse)
async def invoices_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    return templates.TemplateResponse(
        request=request,
        name="invoices.html",
        context={
            "settings": settings,
            "stores": stores,
            "active_page": "invoices"
        }
    )

@app.get("/admin/all-invoices-data")
async def all_invoices_data(
    request: Request,
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    from_date: str = Query(None),
    to_date: str = Query(None),
    due: str = Query(None),
    org_id: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(models.Order).filter(models.Order.status != 'voided')
    
    if org_id and org_id != "All":
        query = query.filter(models.Order.store_id == int(org_id))
    
    if from_date:
        query = query.filter(models.Order.created_at >= from_date)
    if to_date:
        query = query.filter(models.Order.created_at <= to_date)
        
    # 'due' logic can be added here if you have a payments vs total check
    
    total_records = query.count()
    orders = query.order_by(models.Order.created_at.desc()).offset(start).limit(length).all()
    
    data = []
    for i, order in enumerate(orders):
        stamp_class = "badge-success" if order.is_stamped else "badge-danger"
        stamp_text = "Stamped" if order.is_stamped else "Not Stamped"
        
        data.append({
            "serial": start + i + 1,
            "bill_no": f"INV-{order.id:04d}",
            "customer": order.customer.name if order.customer else "Guest",
            "contact": order.customer.phone if order.customer else "N/A",
            "date": order.created_at.strftime('%Y-%m-%d %H:%M'),
            "taxes": f"{(order.total_amount * 0.16):,.2f}", # Example 16% VAT
            "total": f"{order.total_amount:,.2f}",
            "stamp": f'<span class="badge {stamp_class}">{stamp_text}</span>',
            "created_by": order.waiter.name if order.waiter else "Admin",
            "actions": f"""
                <button class="btn btn-xs btn-info" onclick="view_invoice({order.id})"><i class="fa fa-eye"></i></button>
                <button class="btn btn-xs btn-rgp" onclick="tax_stamping({order.id})"><i class="fa fa-stamp"></i> Stamp</button>
                <a href="/admin/print-invoice/{order.id}" target="_blank" class="btn btn-xs btn-dark"><i class="fa fa-print"></i></a>
            """
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.post("/admin/tax-stamping")
async def tax_stamping_route(orderid: int = Form(...), db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == orderid).first()
    if not order:
        return {"status": "error", "message": "Order not found"}
    
    order.is_stamped = not order.is_stamped
    db.commit()
    
    status = "Stamped" if order.is_stamped else "Unstamped"
    return {"status": "success", "message": f"Invoice successfully {status}"}

@app.get("/admin/banquets", response_class=HTMLResponse)
async def banquets_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    return templates.TemplateResponse(
        request=request,
        name="banquets.html",
        context={
            "settings": settings,
            "stores": stores,
            "active_page": "banquets"
        }
    )

@app.get("/admin/all-banquet-data")
async def all_banquet_data(
    request: Request,
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    from_date: str = Query(None),
    to_date: str = Query(None),
    org_id: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(models.Banquet)
    
    if org_id and org_id != "All":
        query = query.filter(models.Banquet.store_id == int(org_id))
    
    if from_date:
        query = query.filter(models.Banquet.created_at >= from_date)
    if to_date:
        query = query.filter(models.Banquet.created_at <= to_date)
        
    total_records = query.count()
    banquets = query.order_by(models.Banquet.created_at.desc()).offset(start).limit(length).all()
    
    data = []
    for i, banquet in enumerate(banquets):
        data.append({
            "serial": start + i + 1,
            "bill_no": f"BNQ-{banquet.id:04d}",
            "customer": banquet.customer.name if banquet.customer else "Guest",
            "contact": banquet.customer.phone if banquet.customer else "N/A",
            "date": banquet.created_at.strftime('%Y-%m-%d %H:%M'),
            "taxes": f"{banquet.tax_amount:,.2f}",
            "total": f"{banquet.total_amount:,.2f}",
            "created_by": banquet.staff.name if banquet.staff else "Admin",
            "actions": f"""
                <button class="btn btn-xs btn-info" onclick="view_banquet({banquet.id})"><i class="fa fa-eye"></i></button>
                <a href="/admin/print-banquet/{banquet.id}" target="_blank" class="btn btn-xs btn-dark"><i class="fa fa-print"></i></a>
            """
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.get("/admin/voided-sales", response_class=HTMLResponse)
async def voided_sales_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="voided_sales.html",
        context={
            "settings": settings,
            "active_page": "voided"
        }
    )

@app.get("/admin/all-voided-sales-data")
async def all_voided_sales_data(
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    db: Session = Depends(get_db)
):
    # Join with VoidLog to get reasons if possible
    query = db.query(models.Order).filter(models.Order.status == "Voided")
    
    total_records = query.count()
    orders = query.order_by(models.Order.created_at.desc()).offset(start).limit(length).all()
    
    data = []
    for i, order in enumerate(orders):
        # Try to find a void log for this order
        void_log = db.query(models.VoidLog).filter(models.VoidLog.order_id == order.id).first()
        
        data.append({
            "serial": start + i + 1,
            "bill_no": f"VOID-{order.id:04d}",
            "customer": order.customer.name if order.customer else "Guest",
            "sales_point": order.store.name if order.store else "Main POS",
            "status": '<span class="badge badge-danger">Voided</span>',
            "date": order.created_at.strftime('%Y-%m-%d %H:%M'),
            "transaction_type": "Direct",
            "net_amount": f"{order.total_amount:,.2f}",
            "narrative": "Order voided",
            "void_reason": void_log.reason if void_log else "N/A",
            "actions": f"""
                <button class="btn btn-xs btn-info" onclick="view_order({order.id})"><i class="fa fa-eye"></i></button>
            """
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.get("/admin/complementary-sales", response_class=HTMLResponse)
async def complementary_sales_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="complementary_sales.html",
        context={
            "settings": settings,
            "active_page": "complementary"
        }
    )

@app.get("/admin/all-complementary-sales-data")
async def all_complementary_sales_data(
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    db: Session = Depends(get_db)
):
    query = db.query(models.Order).filter(models.Order.status == "Complementary")
    
    total_records = query.count()
    orders = query.order_by(models.Order.created_at.desc()).offset(start).limit(length).all()
    
    data = []
    for i, order in enumerate(orders):
        data.append({
            "serial": start + i + 1,
            "bill_no": f"CMPL-{order.id:04d}",
            "customer": order.customer.name if order.customer else "Guest",
            "sales_point": order.store.name if order.store else "Main POS",
            "status": '<span class="badge badge-primary">Complementary</span>',
            "date": order.created_at.strftime('%Y-%m-%d %H:%M'),
            "transaction_type": "Complementary",
            "net_amount": f"{order.total_amount:,.2f}",
            "narrative": "Complementary Sale",
            "reason": "Promotional / VIP",
            "actions": f"""
                <button class="btn btn-xs btn-info" onclick="view_order({order.id})"><i class="fa fa-eye"></i></button>
            """
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.get("/admin/mpesa-till", response_class=HTMLResponse)
async def mpesa_till_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="mpesa_till_payments.html",
        context={
            "settings": settings,
            "active_page": "mpesa_till"
        }
    )

@app.get("/admin/all-mpesa-till-payments-data")
async def all_mpesa_till_payments_data(
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    db: Session = Depends(get_db)
):
    query = db.query(models.MpesaPayment)
    total_records = query.count()
    payments = query.order_by(models.MpesaPayment.timestamp.desc()).offset(start).limit(length).all()
    
    data = []
    for i, payment in enumerate(payments):
        data.append({
            "no": start + i + 1,
            "reference": payment.reference,
            "account_no": payment.account_no,
            "amount": f"{payment.amount:,.2f}",
            "name": payment.name,
            "status": f'<span class="badge badge-success">{payment.status}</span>' if payment.status == "Paid" else f'<span class="badge badge-warning">{payment.status}</span>',
            "date": payment.timestamp.strftime('%d %b %Y %H:%M:%S'),
            "actions": f"""
                <button class="btn btn-xs btn-success" onclick="mark_paid({payment.id})"><i class="fa fa-check"></i></button>
            """
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.post("/admin/mpesa-payment-paid")
async def mpesa_payment_paid(id: int = Form(...), db: Session = Depends(get_db)):
    payment = db.query(models.MpesaPayment).filter(models.MpesaPayment.id == id).first()
    if payment:
        payment.status = "Paid"
        db.commit()
        return "success"
    return "error"

@app.get("/admin/mpesa-stk", response_class=HTMLResponse)
async def mpesa_stk_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="mpesa_callbacks.html",
        context={
            "settings": settings,
            "active_page": "mpesa_stk"
        }
    )

@app.get("/admin/all-mpesa-callbacks-data")
async def all_mpesa_callbacks_data(
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    db: Session = Depends(get_db)
):
    query = db.query(models.MpesaCallback)
    total_records = query.count()
    callbacks = query.order_by(models.MpesaCallback.timestamp.desc()).offset(start).limit(length).all()
    
    data = []
    for i, cb in enumerate(callbacks):
        status_badge = f'<span class="badge badge-success">{cb.status}</span>' if cb.status == "Success" else f'<span class="badge badge-danger">{cb.status}</span>'
        data.append({
            "sn": start + i + 1,
            "mpesa_code": cb.mpesa_code or "N/A",
            "order_code": cb.order_code,
            "amount": f"{cb.amount:,.2f}",
            "phone": cb.phone,
            "name": cb.name or "N/A",
            "status": status_badge,
            "date": cb.timestamp.strftime('%d %b %Y %H:%M:%S')
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.post("/api/v1/mpesa/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_db)):
    try:
        payload = await request.json()
        body = payload.get("Body", {})
        stk = body.get("stkCallback", {})
        result_code = stk.get("ResultCode")
        merchant_request_id = stk.get("MerchantRequestID")
        checkout_request_id = stk.get("CheckoutRequestID")
        
        amount = 0.0
        mpesa_code = None
        phone = ""
        name = "M-Pesa Attendant"
        
        metadata = stk.get("CallbackMetadata", {}).get("Item", [])
        for item in metadata:
            k = item.get("Name")
            v = item.get("Value")
            if k == "Amount":
                amount = float(v)
            elif k == "MpesaReceiptNumber":
                mpesa_code = str(v)
            elif k == "PhoneNumber":
                phone = str(v)

        status = "Success" if result_code == 0 else "Failed"
        order_code = checkout_request_id or merchant_request_id or "UNKNOWN"
        
        callback = models.MpesaCallback(
            mpesa_code=mpesa_code,
            order_code=order_code,
            amount=amount,
            phone=phone,
            name=name,
            status=status
        )
        db.add(callback)
        db.commit()
        
        if result_code == 0:
            order = None
            if order_code != "UNKNOWN":
                order = db.query(models.Order).filter(models.Order.table_number == order_code, models.Order.status == "open").first()
            if not order:
                order = db.query(models.Order).filter(models.Order.total_amount == amount, models.Order.status == "open").order_by(models.Order.created_at.desc()).first()
                
            if order:
                payment = models.Payment(
                    order_id=order.id,
                    cashier_id=1,
                    amount_paid=amount,
                    method="M-Pesa"
                )
                db.add(payment)
                order.status = "paid"
                db.commit()
                
        return {"ResultCode": 0, "ResultDesc": "Accepted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Bad request: {e}")

@app.post("/api/v1/mpesa/mock-callback")
async def mpesa_mock_callback(
    order_id: int = Form(...),
    amount: float = Form(...),
    phone: str = Form(...),
    mpesa_code: str = Form(...),
    db: Session = Depends(get_db)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    callback = models.MpesaCallback(
        mpesa_code=mpesa_code,
        order_code=f"MOCK-{order_id}",
        amount=amount,
        phone=phone,
        name="Mock Customer",
        status="Success"
    )
    db.add(callback)
    
    payment = models.Payment(
        order_id=order.id,
        cashier_id=1,
        amount_paid=amount,
        method="M-Pesa"
    )
    db.add(payment)
    order.status = "paid"
    db.commit()
    
    return {"status": "success", "message": "Mock M-Pesa payment processed successfully"}

@app.get("/admin/returns", response_class=HTMLResponse)
async def returns_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="returns.html",
        context={
            "settings": settings,
            "active_page": "returns"
        }
    )

@app.post("/admin/get-return-orders")
async def get_return_orders(id: int = Form(...), db: Session = Depends(get_db)):
    html = '<option value="">Search and select order/purchase</option>'
    if id == 1:  # Purchase Return
        purchases = db.query(models.Purchase).order_by(models.Purchase.timestamp.desc()).limit(100).all()
        for p in purchases:
            html += f'<option value="{p.id}">{p.purchase_code} - {p.supplier.name if p.supplier else "N/A"}</option>'
    elif id == 2:  # Sale Return
        orders = db.query(models.Order).order_by(models.Order.timestamp.desc()).limit(100).all()
        for o in orders:
            html += f'<option value="{o.id}">{o.order_code} - {o.customer.name if o.customer else "Walk-in"}</option>'
    return HTMLResponse(content=html)

@app.post("/admin/get-return-order-items")
async def get_return_order_items(id: int = Form(...), type: int = Form(...), db: Session = Depends(get_db)):
    html = '<option value="">Search and select item</option>'
    if type == 1:  # Purchase Return
        items = db.query(models.PurchaseItem).filter(models.PurchaseItem.purchase_id == id).all()
        for item in items:
            html += f'<option value="{item.product_id}">{item.product.name} (Qty: {item.quantity})</option>'
    elif type == 2:  # Sale Return
        items = db.query(models.OrderItem).filter(models.OrderItem.order_id == id).all()
        for item in items:
            html += f'<option value="{item.product_id}">{item.product.name} (Qty: {item.quantity})</option>'
    return HTMLResponse(content=html)

@app.post("/admin/add-return")
async def add_return(
    item_status_id: int = Form(...),
    order_id: int = Form(...),
    order_item_id: int = Form(...),
    qty: float = Form(...),
    return_condition: str = Form(...),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    # For now, we assume staff_id=1 (admin) until we have proper session auth
    staff = db.query(models.Staff).first()
    staff_id = staff.id if staff else 1
    
    new_return = models.ItemReturn(
        product_id=order_item_id,
        qty=qty,
        return_type="Purchase" if item_status_id == 1 else "Sale",
        condition=return_condition,
        order_id=order_id if item_status_id == 2 else None,
        purchase_id=order_id if item_status_id == 1 else None,
        staff_id=staff_id,
        narrative=narrative
    )
    db.add(new_return)
    
    # Update stock
    product = db.query(models.Product).filter(models.Product.id == order_item_id).first()
    if product:
        if item_status_id == 1: # Purchase Return -> Decrease stock
            product.stock_quantity -= qty
        else: # Sale Return -> Increase stock if Good
            if return_condition == "Good":
                product.stock_quantity += qty
                
    db.commit()
    return RedirectResponse(url="/admin/returns", status_code=303)

@app.get("/admin/all-returns-data")
async def all_returns_data(
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    db: Session = Depends(get_db)
):
    query = db.query(models.ItemReturn)
    total_records = query.count()
    returns = query.order_by(models.ItemReturn.timestamp.desc()).offset(start).limit(length).all()
    
    data = []
    for r in returns:
        order_code = "N/A"
        if r.return_type == "Sale" and r.order:
            order_code = r.order.order_code
        elif r.return_type == "Purchase" and r.purchase:
            order_code = r.purchase.purchase_code
            
        data.append({
            "ref": f"RET-{r.id:04d}",
            "item": r.product.name if r.product else "N/A",
            "code": r.product.sku if r.product else "N/A",
            "qty": r.qty,
            "type": r.return_type,
            "staff": r.staff.name if r.staff else "System",
            "date": r.timestamp.strftime('%d %b %Y %H:%M:%S'),
            "order_code": order_code,
            "narrative": r.narrative or ""
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.get("/admin/rooms/online-bookings", response_class=HTMLResponse)
async def online_bookings_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    bookings = db.query(models.RoomBooking).filter(models.RoomBooking.source == "Online").all()
    return templates.TemplateResponse(
        request=request,
        name="bookings_online.html",
        context={
            "settings": settings,
            "bookings": bookings,
            "currency": settings.get("currency", "KES"),
            "active_page": "online_bookings"
        }
    )

@app.get("/admin/rooms/dashboard", response_class=HTMLResponse)
async def rooms_dashboard(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().date()
    
    # Calculate stats from DB
    total_rooms = db.query(models.Room).count()
    occupied_rooms = db.query(models.Room).filter(models.Room.status == "occupied").count()
    available_rooms = total_rooms - occupied_rooms
    occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
    
    # Calculate outstanding balances
    outstanding_balances = db.query(func.sum(models.RoomBooking.balance)).filter(models.RoomBooking.status != "cancelled").scalar() or 0.00
    
    # Calculate revenue today
    revenue_today = db.query(func.sum(models.RoomBooking.paid_amount)).filter(
        func.date(models.RoomBooking.created_at) == today,
        models.RoomBooking.status != "cancelled"
    ).scalar() or 0.00
    
    # Last 7 days reservation trend and revenue
    trend_data = []
    revenue_chart_data = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        day_name = d.strftime('%a')
        
        bookings_count = db.query(models.RoomBooking).filter(
            func.date(models.RoomBooking.created_at) == d,
            models.RoomBooking.status != "cancelled"
        ).count()
        
        day_revenue = db.query(func.sum(models.RoomBooking.paid_amount)).filter(
            func.date(models.RoomBooking.created_at) == d,
            models.RoomBooking.status != "cancelled"
        ).scalar() or 0.00
        
        trend_data.append({"day": day_name, "bookings": bookings_count})
        revenue_chart_data.append({"day": day_name, "revenue": day_revenue})
    
    return templates.TemplateResponse(
        request=request,
        name="rooms_dashboard.html",
        context={
            "settings": settings,
            "stores": stores,
            "today": today.isoformat(),
            "today_name": today.strftime('%a'),
            "total_rooms": total_rooms,
            "available_rooms": available_rooms,
            "occupied_rooms": occupied_rooms,
            "occupancy_rate": round(occupancy_rate, 1),
            "revenue_today": revenue_today,
            "outstanding_balances": outstanding_balances,
            "currency": settings.get("currency", "KES"),
            "active_page": "rooms_dashboard",
            "trend_data": trend_data,
            "revenue_chart_data": revenue_chart_data
        }
    )

@app.get("/admin/rooms/book-room", response_class=HTMLResponse)
async def book_room_page(
    request: Request, 
    query_type: str = "unoccupied",
    from_date: str = None,
    to_date: str = None,
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    today = datetime.datetime.utcnow().date()
    
    if not from_date: from_date = today.isoformat()
    if not to_date: to_date = today.isoformat()
    
    # Filter rooms based on status
    status_map = {
        "unoccupied": "available",
        "occupied": "occupied",
        "maintenance": "maintenance"
    }
    target_status = status_map.get(query_type, "available")
    
    rooms = db.query(models.Room).filter(models.Room.status == target_status).all()
    
    return templates.TemplateResponse(
        request=request,
        name="book_room.html",
        context={
            "settings": settings,
            "currency": settings.get("currency", "KES"),
            "today_display": today.strftime('%d-%m-%Y'),
            "from_date": from_date,
            "to_date": to_date,
            "query_type": query_type,
            "rooms": rooms,
            "active_page": "book_room"
        }
    )

@app.post("/api/admin/rooms/book")
async def process_booking(
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    
    try:
        # In the frontend, we might need to send the room_id
        # For now, let's try to get it from the form if added, or a hidden field
        room_id = form_data.get("room_id")
        if room_id:
            room = db.query(models.Room).filter(models.Room.id == int(room_id)).first()
            if room:
                if room.status == "dirty" or room.status == "cleaning":
                    return JSONResponse(status_code=400, content={"message": "Cannot book room: Room is dirty or being cleaned. It must be cleaned first."})
                if room.status == "maintenance":
                    return JSONResponse(status_code=400, content={"message": "Cannot book room: Room is undergoing maintenance."})
                
                active_maint = db.query(models.RoomMaintenance).filter(
                    models.RoomMaintenance.room_id == room.id,
                    models.RoomMaintenance.status.in_(["Open", "Assigned", "In Progress"])
                ).first()
                if active_maint:
                    return JSONResponse(status_code=400, content={"message": "Cannot book room: Room has an active maintenance ticket."})
                
                active_clean = db.query(models.RoomCleaning).filter(
                    models.RoomCleaning.room_id == room.id,
                    models.RoomCleaning.cleaning_status.in_(["Pending", "In Progress"])
                ).first()
                if active_clean:
                    return JSONResponse(status_code=400, content={"message": "Cannot book room: Room is currently being cleaned."})
        
        new_booking = models.RoomBooking(
            room_id=int(room_id) if room_id else None,
            customer_name=form_data.get("customer_name"),
            customer_phone=form_data.get("customer_phone"),
            from_date=datetime.datetime.now(), 
            to_date=datetime.datetime.now(),
            nights=int(form_data.get("nights", 1)),
            booking_type="Bed Only",
            occupancy=int(form_data.get("occupancy", 1)),
            narrative=form_data.get("narrative"),
            total_amount=float(form_data.get("total_amount", 0)),
            paid_amount=float(form_data.get("paid_amount", 0)),
            balance=float(form_data.get("total_amount", 0)) - float(form_data.get("paid_amount", 0)),
            payment_method=form_data.get("payment_method"),
            reference=form_data.get("reference")
        )
        
        db.add(new_booking)
        
        # Update room status if room_id is provided
        if room_id:
            room = db.query(models.Room).filter(models.Room.id == int(room_id)).first()
            if room:
                room.status = "occupied"
        
        db.commit()
        
        return RedirectResponse(url="/admin/rooms/bookings", status_code=303)
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.get("/admin/rooms/bookings", response_class=HTMLResponse)
async def bookings_page(
    request: Request, 
    from_date: str = None,
    to_date: str = None,
    due: str = "All",
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    query = db.query(models.RoomBooking)
    
    # Filter by date if provided
    if from_date:
        query = query.filter(models.RoomBooking.created_at >= datetime.datetime.fromisoformat(from_date))
    if to_date:
        # To include the whole to_date day
        to_dt = datetime.datetime.fromisoformat(to_date) + datetime.timedelta(days=1)
        query = query.filter(models.RoomBooking.created_at < to_dt)
    
    # Filter by payment status
    if due == "Due":
        query = query.filter(models.RoomBooking.balance > 0)
    elif due == "Paid":
        query = query.filter(models.RoomBooking.balance <= 0)
        
    bookings = query.order_by(models.RoomBooking.created_at.desc()).all()
    
    return templates.TemplateResponse(
        request=request,
        name="bookings.html",
        context={
            "settings": settings,
            "bookings": bookings,
            "currency": settings.get("currency", "KES"),
            "from_date": from_date or "",
            "to_date": to_date or "",
            "due": due,
            "active_page": "bookings"
        }
    )

@app.get("/admin/rooms", response_class=HTMLResponse)
async def rooms_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    rooms = db.query(models.Room).all()
    room_types = db.query(models.RoomType).all()
    return templates.TemplateResponse(
        request=request,
        name="rooms.html",
        context={
            "settings": settings,
            "rooms": rooms,
            "room_types": room_types,
            "currency": settings.get("currency", "KES"),
            "active_page": "rooms"
        }
    )

@app.post("/api/admin/rooms/booking-details")
async def booking_details(
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    booking_id = form_data.get("id")
    booking = db.query(models.RoomBooking).filter(models.RoomBooking.id == booking_id).first()
    if not booking:
        return HTMLResponse("<p class='text-danger'>Booking not found.</p>")
    
    html = f"""
    <div class='row'>
        <div class='col-6'><strong>Customer:</strong> {booking.customer_name}</div>
        <div class='col-6'><strong>Phone:</strong> {booking.customer_phone}</div>
        <div class='col-6'><strong>Nights:</strong> {booking.nights}</div>
        <div class='col-6'><strong>Amount:</strong> {booking.total_amount}</div>
        <div class='col-12'><hr><strong>Narrative:</strong> {booking.narrative or 'None'}</div>
    </div>
    """
    return HTMLResponse(html)

@app.post("/api/admin/rooms/void-booking")
async def void_booking_api(
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    booking_id = form_data.get("id")
    booking = db.query(models.RoomBooking).filter(models.RoomBooking.id == booking_id).first()
    if booking:
        booking.status = "cancelled"
        # Also free up the room
        if booking.room:
            booking.room.status = "available"
        db.commit()
        return JSONResponse({"resp": "1"})
    return JSONResponse({"resp": "0"})

@app.get("/admin/rooms/bookings-calendar")
async def bookings_calendar_page(
    request: Request,
    month: int = Query(None),
    year: int = Query(None),
    db: Session = Depends(get_db)
):
    settings = get_settings(db)
    now = datetime.datetime.now()
    if month is None: month = now.month
    if year is None: year = now.year
    
    # Get number of days in month
    num_days = calendar.monthrange(year, month)[1]
    
    # Create list of days with metadata
    days_in_month = []
    for d in range(1, num_days + 1):
        dt = datetime.date(year, month, d)
        days_in_month.append({
            "day": d,
            "date": dt,
            "weekday": dt.strftime("%a")
        })
    
    # Fetch rooms and group by category
    rooms = db.query(models.Room).all()
    rooms_by_type = {}
    for r in rooms:
        cat = r.category or "Other"
        if cat not in rooms_by_type:
            rooms_by_type[cat] = []
        rooms_by_type[cat].append(r)
        
    # Fetch bookings for this month
    # A booking overlaps with this month if from_date <= month_end and to_date >= month_start
    month_start = datetime.date(year, month, 1)
    month_end = datetime.date(year, month, num_days)
    month_start_dt = datetime.datetime(year, month, 1)
    month_end_dt = datetime.datetime(year, month, num_days, 23, 59, 59)
    
    bookings = db.query(models.RoomBooking).filter(
        models.RoomBooking.from_date <= month_end_dt,
        models.RoomBooking.to_date >= month_start_dt,
        models.RoomBooking.status != 'cancelled'
    ).all()
    
    # Organize bookings for the calendar
    # calendar_data[room_id][day] = booking_info
    calendar_data = {r.id: {} for r in rooms}
    
    for b in bookings:
        if not b.room_id or b.room_id not in calendar_data: continue
        
        # Determine duration within this month
        # Convert DateTime to Date for day calculation
        b_from = b.from_date.date()
        b_to = b.to_date.date()
        
        # Start day in month
        if b_from < month_start:
            start_day = 1
        else:
            start_day = b_from.day
            
        # End day in month
        if b_to > month_end:
            end_day = num_days
        else:
            end_day = b_to.day - 1 # check_out is day of leaving
            if end_day < start_day: end_day = start_day
        
        duration = end_day - start_day + 1
        if duration <= 0: continue
        
        color = "orangered" # default pending
        if b.status == "checked_in": color = "#0cb906"
        elif b.status == "checked_out": color = "#017870"
        elif b.status == "no_show": color = "#ffbf00"
        
        calendar_data[b.room_id][start_day] = {
            "is_start": True,
            "colspan": duration,
            "customer_name": b.customer_name,
            "color": color,
            "duration": b.nights,
            "id": b.id
        }
        
        # Mark other days as occupied but not start
        for d in range(start_day + 1, end_day + 1):
            calendar_data[b.room_id][d] = {"is_start": False}

    return templates.TemplateResponse(
        request=request,
        name="bookings_calendar.html",
        context={
            "settings": settings,
            "current_month": month,
            "selected_year": year,
            "current_year": now.year,
            "month_names": calendar.month_name[1:],
            "days_in_month": days_in_month,
            "rooms_by_type": rooms_by_type,
            "calendar_data": calendar_data,
            "today": now.date(),
            "active_page": "bookings_calendar"
        }
    )

@app.get("/admin/rooms/settings", response_class=HTMLResponse)
async def room_settings_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    room_types = db.query(models.RoomType).all()
    allocations = db.query(models.RevenueAllocation).all()
    
    # Initialize defaults if empty
    if not allocations:
        defaults = [
            {"meal_plan": "Bed & Breakfast", "food_revenue": 30, "accommodation_revenue": 50, "beverage_revenue": 20, "hall_revenue": 0},
            {"meal_plan": "Half Board", "food_revenue": 40, "accommodation_revenue": 40, "beverage_revenue": 20, "hall_revenue": 0},
            {"meal_plan": "Full Board", "food_revenue": 50, "accommodation_revenue": 30, "beverage_revenue": 20, "hall_revenue": 0}
        ]
        for d in defaults:
            db.add(models.RevenueAllocation(**d))
        db.commit()
        allocations = db.query(models.RevenueAllocation).all()

    # Query cleaning tasks
    cleanings = db.query(models.RoomCleaning).options(
        joinedload(models.RoomCleaning.room),
        joinedload(models.RoomCleaning.housekeeper)
    ).order_by(models.RoomCleaning.created_at.desc()).all()

    # Query maintenance tickets
    maintenances = db.query(models.RoomMaintenance).options(
        joinedload(models.RoomMaintenance.room),
        joinedload(models.RoomMaintenance.reporter),
        joinedload(models.RoomMaintenance.technician)
    ).order_by(models.RoomMaintenance.created_at.desc()).all()

    # Query active staff & rooms
    staff_list = db.query(models.Staff).filter(models.Staff.is_active == True).all()
    rooms_list = db.query(models.Room).all()

    # Cleaning Metrics
    total_dirty = sum(1 for c in cleanings if c.cleaning_status == "Pending")
    cleaning_in_progress = sum(1 for c in cleanings if c.cleaning_status == "In Progress")
    total_clean = sum(1 for r in rooms_list if r.status == "available")

    # Maintenance Metrics
    open_tickets = sum(1 for m in maintenances if m.status in ["Open", "Assigned", "In Progress"])
    urgent_tickets = sum(1 for m in maintenances if m.priority == "Urgent" and m.status != "Completed")
    total_maint_cost = sum(m.cost or 0.0 for m in maintenances)

    # Calculate housekeeper stats
    housekeep_stats = {}
    for c in cleanings:
        if c.cleaning_status == 'Completed' and c.housekeeper:
            if c.start_time and c.completion_time:
                try:
                    duration = (c.completion_time - c.start_time).total_seconds() / 60
                    name = c.housekeeper.name
                    if name not in housekeep_stats:
                        housekeep_stats[name] = {"count": 0, "sum": 0.0}
                    housekeep_stats[name]["count"] += 1
                    housekeep_stats[name]["sum"] += duration
                except Exception:
                    pass

    # Calculate issue stats
    issue_stats = {}
    for m in maintenances:
        itype = m.issue_type or "General"
        cost = m.cost or 0.0
        if itype not in issue_stats:
            issue_stats[itype] = {"count": 0, "cost": 0.0}
        issue_stats[itype]["count"] += 1
        issue_stats[itype]["cost"] += cost

    return templates.TemplateResponse(
        request=request,
        name="room_settings.html",
        context={
            "settings": settings,
            "room_types": room_types,
            "allocations": allocations,
            "cleanings": cleanings,
            "maintenances": maintenances,
            "staff_list": staff_list,
            "rooms_list": rooms_list,
            "total_dirty": total_dirty,
            "cleaning_in_progress": cleaning_in_progress,
            "total_clean": total_clean,
            "open_tickets": open_tickets,
            "urgent_tickets": urgent_tickets,
            "total_maint_cost": total_maint_cost,
            "housekeep_stats": housekeep_stats,
            "issue_stats": issue_stats,
            "active_page": "room_settings"
        }
    )

@app.post("/api/admin/rooms/revenue-allocations/update/{alloc_id}")
async def update_revenue_allocation(alloc_id: int, request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    alloc = db.query(models.RevenueAllocation).filter(models.RevenueAllocation.id == alloc_id).first()
    if not alloc: return JSONResponse(status_code=404, content={"message": "Allocation not found"})
    try:
        alloc.food_revenue = float(form_data.get("food_revenue", 0))
        alloc.accommodation_revenue = float(form_data.get("accommodation_revenue", 0))
        alloc.beverage_revenue = float(form_data.get("beverage_revenue", 0))
        alloc.hall_revenue = float(form_data.get("hall_revenue", 0))
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings", status_code=303)
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/types/add")
async def add_room_type(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    try:
        new_type = models.RoomType(
            name=form_data.get("name"),
            description=form_data.get("description"),
            base_rate=float(form_data.get("base_rate", 0))
        )
        db.add(new_type)
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings", status_code=303)
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/types/update/{type_id}")
async def update_room_type(type_id: int, request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    rt = db.query(models.RoomType).filter(models.RoomType.id == type_id).first()
    if not rt: return JSONResponse(status_code=404, content={"message": "Type not found"})
    try:
        rt.name = form_data.get("name")
        rt.description = form_data.get("description")
        rt.base_rate = float(form_data.get("base_rate", 0))
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings", status_code=303)
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/types/delete/{type_id}")
async def delete_room_type(type_id: int, db: Session = Depends(get_db)):
    rt = db.query(models.RoomType).filter(models.RoomType.id == type_id).first()
    if not rt: return JSONResponse(status_code=404, content={"message": "Type not found"})
    try:
        db.delete(rt)
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings", status_code=303)
    except Exception as e:
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/add")
async def add_room(
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    try:
        new_room = models.Room(
            room_number=form_data.get("room_number"),
            room_type=form_data.get("room_type"),
            price_per_night=float(form_data.get("price_per_night", 0)),
            day_rest_s=float(form_data.get("day_rest_s", 0)),
            bb_s=float(form_data.get("bb_s", 0)),
            hb_s=float(form_data.get("hb_s", 0)),
            fb_s=float(form_data.get("fb_s", 0)),
            day_rest_d=float(form_data.get("day_rest_d", 0)),
            bed_only_d=float(form_data.get("bed_only_d", 0)),
            bb_d=float(form_data.get("bb_d", 0)),
            hb_d=float(form_data.get("hb_d", 0)),
            fb_d=float(form_data.get("fb_d", 0)),
            status=form_data.get("status", "available"),
            narrative=form_data.get("narrative", "")
        )
        db.add(new_room)
        db.commit()
        return RedirectResponse(url="/admin/rooms", status_code=303)
    except Exception as e:
        print(f"Error adding room: {e}")
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/update/{room_id}")
async def update_room(
    room_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room:
        return JSONResponse(status_code=404, content={"message": "Room not found"})
    
    try:
        room.room_number = form_data.get("room_number")
        room.room_type = form_data.get("room_type")
        room.price_per_night = float(form_data.get("price_per_night", 0))
        room.day_rest_s = float(form_data.get("day_rest_s", 0))
        room.bb_s = float(form_data.get("bb_s", 0))
        room.hb_s = float(form_data.get("hb_s", 0))
        room.fb_s = float(form_data.get("fb_s", 0))
        room.day_rest_d = float(form_data.get("day_rest_d", 0))
        room.bed_only_d = float(form_data.get("bed_only_d", 0))
        room.bb_d = float(form_data.get("bb_d", 0))
        room.hb_d = float(form_data.get("hb_d", 0))
        room.fb_d = float(form_data.get("fb_d", 0))
        room.status = form_data.get("status", "available")
        room.narrative = form_data.get("narrative", "")
        
        db.commit()
        return RedirectResponse(url="/admin/rooms", status_code=303)
    except Exception as e:
        print(f"Error updating room: {e}")
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/delete/{room_id}")
async def delete_room(
    room_id: int,
    db: Session = Depends(get_db)
):
    room = db.query(models.Room).filter(models.Room.id == room_id).first()
    if not room:
        return JSONResponse(status_code=404, content={"message": "Room not found"})
    
    try:
        db.delete(room)
        db.commit()
        return RedirectResponse(url="/admin/rooms", status_code=303)
    except Exception as e:
        print(f"Error deleting room: {e}")
        return JSONResponse(status_code=400, content={"message": str(e)})

# --- Room Cleaning & Maintenance Schedules APIs ---

@app.post("/api/admin/rooms/checkout/{booking_id}")
async def checkout_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(models.RoomBooking).filter(models.RoomBooking.id == booking_id).first()
    if not booking:
        return JSONResponse(status_code=404, content={"message": "Booking not found"})
    
    try:
        booking.status = "checked_out"
        if booking.room:
            booking.room.status = "dirty"
            # Auto-create Checkout Clean task
            new_cleaning = models.RoomCleaning(
                room_id=booking.room_id,
                floor_wing=booking.room.category or "Default",
                cleaning_status="Pending",
                cleaning_type="Checkout Clean",
                notes=f"Auto-generated checkout clean for guest {booking.customer_name}.",
                scheduled_time=datetime.datetime.utcnow(),
                created_at=datetime.datetime.utcnow()
            )
            db.add(new_cleaning)
        db.commit()
        return JSONResponse({"success": True, "message": "Checkout processed successfully and cleaning task scheduled."})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/cleaning/create")
async def create_cleaning_task(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    try:
        room_id = int(form_data.get("room_id"))
        cleaning_type = form_data.get("cleaning_type", "Standard")
        notes = form_data.get("notes")
        assigned_housekeeper_id = form_data.get("assigned_housekeeper_id")
        
        room = db.query(models.Room).filter(models.Room.id == room_id).first()
        if not room:
            return JSONResponse(status_code=404, content={"message": "Room not found"})
        
        new_cleaning = models.RoomCleaning(
            room_id=room_id,
            floor_wing=room.category or "Default",
            cleaning_status="Pending",
            cleaning_type=cleaning_type,
            notes=notes,
            assigned_housekeeper_id=int(assigned_housekeeper_id) if assigned_housekeeper_id and assigned_housekeeper_id != "" else None,
            scheduled_time=datetime.datetime.utcnow(),
            created_at=datetime.datetime.utcnow()
        )
        
        # Set room status to cleaning if housekeeper is assigned, otherwise dirty
        room.status = "cleaning" if assigned_housekeeper_id and assigned_housekeeper_id != "" else "dirty"
        if room.status == "cleaning":
            new_cleaning.cleaning_status = "In Progress"
            new_cleaning.start_time = datetime.datetime.utcnow()
        
        db.add(new_cleaning)
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings#vert-room-maintenance", status_code=303)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/cleaning/assign")
async def assign_housekeeper(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    try:
        task_id = int(form_data.get("task_id"))
        housekeeper_id = int(form_data.get("housekeeper_id"))
        
        task = db.query(models.RoomCleaning).filter(models.RoomCleaning.id == task_id).first()
        if not task:
            return JSONResponse(status_code=404, content={"message": "Cleaning task not found"})
        
        task.assigned_housekeeper_id = housekeeper_id
        task.cleaning_status = "In Progress"
        task.start_time = datetime.datetime.utcnow()
        if task.room:
            task.room.status = "cleaning"
        
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings#vert-room-maintenance", status_code=303)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/cleaning/complete")
async def complete_cleaning_task(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    try:
        task_id = int(form_data.get("task_id"))
        notes = form_data.get("notes", "")
        
        task = db.query(models.RoomCleaning).filter(models.RoomCleaning.id == task_id).first()
        if not task:
            return JSONResponse(status_code=404, content={"message": "Cleaning task not found"})
        
        task.cleaning_status = "Completed"
        task.completion_time = datetime.datetime.utcnow()
        if notes:
            task.notes = (task.notes or "") + "\nCompletion Notes: " + notes
        
        if task.room:
            # Check if there is an active maintenance ticket blocking the room
            active_maint = db.query(models.RoomMaintenance).filter(
                models.RoomMaintenance.room_id == task.room_id,
                models.RoomMaintenance.status.in_(["Open", "Assigned", "In Progress"])
            ).first()
            if active_maint:
                task.room.status = "maintenance"
            else:
                task.room.status = "available"
        
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings#vert-room-maintenance", status_code=303)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/cleaning/skip")
async def skip_cleaning_task(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    try:
        task_id = int(form_data.get("task_id"))
        notes = form_data.get("notes", "")
        
        task = db.query(models.RoomCleaning).filter(models.RoomCleaning.id == task_id).first()
        if not task:
            return JSONResponse(status_code=404, content={"message": "Cleaning task not found"})
        
        task.cleaning_status = "Skipped"
        task.completion_time = datetime.datetime.utcnow()
        if notes:
            task.notes = (task.notes or "") + "\nSkip Notes: " + notes
        
        if task.room:
            active_maint = db.query(models.RoomMaintenance).filter(
                models.RoomMaintenance.room_id == task.room_id,
                models.RoomMaintenance.status.in_(["Open", "Assigned", "In Progress"])
            ).first()
            if active_maint:
                task.room.status = "maintenance"
            else:
                task.room.status = "available"
        
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings#vert-room-maintenance", status_code=303)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/maintenance/add")
async def add_maintenance_ticket(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    try:
        room_id = form_data.get("room_id")
        area = form_data.get("area")
        issue_type = form_data.get("issue_type")
        priority = form_data.get("priority", "Medium")
        reported_by_id = int(form_data.get("reported_by_id"))
        assigned_technician_id = form_data.get("assigned_technician_id")
        scheduled_date = form_data.get("scheduled_date")
        estimated_duration = form_data.get("estimated_duration")
        cost = form_data.get("cost", 0.0)
        notes = form_data.get("notes")
        is_recurring = form_data.get("is_recurring") == "true" or form_data.get("is_recurring") == "on"
        recurring_months = form_data.get("recurring_months")
        
        parsed_room_id = int(room_id) if room_id and room_id != "" else None
        
        if parsed_room_id:
            room = db.query(models.Room).filter(models.Room.id == parsed_room_id).first()
            if room:
                room.status = "maintenance"
                if not area or area.strip() == "":
                    area = f"Room {room.room_number}"
        
        new_ticket = models.RoomMaintenance(
            room_id=parsed_room_id,
            area=area or "Common Area",
            issue_type=issue_type,
            priority=priority,
            reported_by_id=reported_by_id,
            assigned_technician_id=int(assigned_technician_id) if assigned_technician_id and assigned_technician_id != "" else None,
            date_reported=datetime.datetime.utcnow(),
            scheduled_date=datetime.datetime.strptime(scheduled_date, '%Y-%m-%d') if scheduled_date else None,
            estimated_duration=float(estimated_duration) if estimated_duration else None,
            status="Assigned" if assigned_technician_id and assigned_technician_id != "" else "Open",
            cost=float(cost) if cost else 0.0,
            notes=notes,
            is_recurring=is_recurring,
            recurring_months=int(recurring_months) if recurring_months and recurring_months != "" else None,
            created_at=datetime.datetime.utcnow()
        )
        
        db.add(new_ticket)
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings#vert-room-maintenance", status_code=303)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.post("/api/admin/rooms/maintenance/update-status")
async def update_maintenance_status(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    try:
        ticket_id = int(form_data.get("ticket_id"))
        status = form_data.get("status")
        cost = float(form_data.get("cost") or 0.0)
        notes = form_data.get("notes", "")
        
        ticket = db.query(models.RoomMaintenance).filter(models.RoomMaintenance.id == ticket_id).first()
        if not ticket:
            return JSONResponse(status_code=404, content={"message": "Maintenance ticket not found"})
        
        ticket.status = status
        if cost > 0.0:
            ticket.cost = cost
        if notes:
            ticket.notes = (ticket.notes or "") + "\nUpdate Notes: " + notes
        
        if status == "Completed":
            ticket.completion_date = datetime.datetime.utcnow()
            # Log maintenance cost to expenses
            if ticket.cost > 0.0:
                maint_account = db.query(models.Account).filter(
                    (models.Account.name.ilike('%maintenance%')) | (models.Account.name.ilike('%repair%'))
                ).first()
                if not maint_account:
                    maint_account = db.query(models.Account).filter(models.Account.account_type == "Expense").first()
                if not maint_account:
                    maint_account = db.query(models.Account).first()
                
                if maint_account:
                    count = db.query(models.Expense).count()
                    ref_no = f"EXP-MAINT-{count+1:04d}"
                    new_exp = models.Expense(
                        ref_no=ref_no,
                        store_id=1,
                        account_id=maint_account.id,
                        amount=ticket.cost,
                        balance=0.0,
                        paid_to=f"Technician (Maintenance #{ticket.id})",
                        expense_date=datetime.datetime.utcnow(),
                        status="Completed",
                        narrative=f"Auto-generated expense for completed room maintenance #{ticket.id} on room/area: {ticket.area}. Issue: {ticket.issue_type}.",
                        is_active=True
                    )
                    db.add(new_exp)
            
            # If room is linked, release it (set to available) unless there is another active issue or dirty tasks
            if ticket.room_id:
                other_maint = db.query(models.RoomMaintenance).filter(
                    models.RoomMaintenance.room_id == ticket.room_id,
                    models.RoomMaintenance.id != ticket.id,
                    models.RoomMaintenance.status.in_(["Open", "Assigned", "In Progress"])
                ).first()
                if not other_maint:
                    # Check if needs cleaning
                    dirty_cleaning = db.query(models.RoomCleaning).filter(
                        models.RoomCleaning.room_id == ticket.room_id,
                        models.RoomCleaning.cleaning_status.in_(["Pending", "In Progress"])
                    ).first()
                    if dirty_cleaning:
                        ticket.room.status = "dirty"
                    else:
                        ticket.room.status = "available"
            
            # Generate next recurring ticket if applicable
            if ticket.is_recurring and ticket.recurring_months:
                next_sched = datetime.datetime.utcnow() + datetime.timedelta(days=30 * ticket.recurring_months)
                new_recurring = models.RoomMaintenance(
                    room_id=ticket.room_id,
                    area=ticket.area,
                    issue_type=ticket.issue_type,
                    priority=ticket.priority,
                    reported_by_id=ticket.reported_by_id,
                    assigned_technician_id=ticket.assigned_technician_id,
                    date_reported=datetime.datetime.utcnow(),
                    scheduled_date=next_sched,
                    status="Open" if not ticket.assigned_technician_id else "Assigned",
                    is_recurring=True,
                    recurring_months=ticket.recurring_months,
                    notes=f"Auto-generated recurring ticket following completed ticket #{ticket.id}.",
                    created_at=datetime.datetime.utcnow()
                )
                db.add(new_recurring)
                
        elif status in ["Open", "Assigned", "In Progress"]:
            if ticket.room_id and ticket.room:
                ticket.room.status = "maintenance"
                
        db.commit()
        return RedirectResponse(url="/admin/rooms/settings#vert-room-maintenance", status_code=303)
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=400, content={"message": str(e)})

@app.get("/api/admin/rooms/reports/cleaning/csv")
async def export_cleaning_csv(db: Session = Depends(get_db)):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    cleanings = db.query(models.RoomCleaning).options(
        joinedload(models.RoomCleaning.room),
        joinedload(models.RoomCleaning.housekeeper)
    ).order_by(models.RoomCleaning.created_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Task ID", "Room Number", "Cleaning Type", "Status", "Housekeeper", "Scheduled Time", "Start Time", "Completion Time", "Duration (Mins)", "Notes"])
    
    for c in cleanings:
        duration = ""
        if c.start_time and c.completion_time:
            duration = round((c.completion_time - c.start_time).total_seconds() / 60, 2)
            
        writer.writerow([
            c.id,
            c.room.room_number if c.room else "N/A",
            c.cleaning_type,
            c.cleaning_status,
            c.housekeeper.name if c.housekeeper else "Unassigned",
            c.scheduled_time.strftime("%Y-%m-%d %H:%M:%S") if c.scheduled_time else "",
            c.start_time.strftime("%Y-%m-%d %H:%M:%S") if c.start_time else "",
            c.completion_time.strftime("%Y-%m-%d %H:%M:%S") if c.completion_time else "",
            duration,
            c.notes or ""
        ])
        
    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=room_cleaning_report.csv"}
    return StreamingResponse(io.BytesIO(output.read().encode("utf-8")), media_type="text/csv", headers=headers)

@app.get("/api/admin/rooms/reports/maintenance/csv")
async def export_maintenance_csv(db: Session = Depends(get_db)):
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    maintenances = db.query(models.RoomMaintenance).options(
        joinedload(models.RoomMaintenance.room),
        joinedload(models.RoomMaintenance.reporter),
        joinedload(models.RoomMaintenance.technician)
    ).order_by(models.RoomMaintenance.created_at.desc()).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Ticket ID", "Room/Area", "Issue Type", "Priority", "Status", "Reported By", "Assigned Technician", "Date Reported", "Completion Date", "Cost (KES)", "Notes", "Recurring?"])
    
    for m in maintenances:
        writer.writerow([
            m.id,
            m.area,
            m.issue_type,
            m.priority,
            m.status,
            m.reporter.name if m.reporter else "Unknown",
            m.technician.name if m.technician else "Unassigned",
            m.date_reported.strftime("%Y-%m-%d %H:%M:%S") if m.date_reported else "",
            m.completion_date.strftime("%Y-%m-%d %H:%M:%S") if m.completion_date else "",
            m.cost,
            m.notes or "",
            "Yes" if m.is_recurring else "No"
        ])
        
    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=room_maintenance_report.csv"}
    return StreamingResponse(io.BytesIO(output.read().encode("utf-8")), media_type="text/csv", headers=headers)

@app.get("/admin/accounting/expenses", response_class=HTMLResponse)
async def expenses_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    expense_accounts = db.query(models.Account).filter(models.Account.account_type == "Expense").all()
    payable_accounts = db.query(models.Account).filter(models.Account.account_type == "Liability").all()
    today = datetime.datetime.utcnow().date()
    return templates.TemplateResponse(
        request=request,
        name="expenses.html",
        context={
            "settings": settings,
            "stores": stores,
            "expense_accounts": expense_accounts,
            "payable_accounts": payable_accounts,
            "today": today.isoformat(),
            "active_page": "expenses"
        }
    )

@app.get("/admin/accounting/all_expenses")
async def all_expenses_data(
    request: Request,
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    org_id: str = Query(None),
    status_id: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(models.Expense)
    
    # Filters
    if org_id and org_id != 'All':
        query = query.filter(models.Expense.store_id == int(org_id))
    
    if status_id and status_id != 'All':
        query = query.filter(models.Expense.status == status_id)
        
    if from_date:
        try:
            d = datetime.datetime.strptime(from_date, '%Y-%m-%d')
            query = query.filter(models.Expense.expense_date >= d)
        except: pass
    if to_date:
        try:
            d = datetime.datetime.strptime(to_date, '%Y-%m-%d') + datetime.timedelta(days=1)
            query = query.filter(models.Expense.expense_date < d)
        except: pass

    total_records = query.count()
    expenses = query.order_by(models.Expense.expense_date.desc()).offset(start).limit(length).all()
    
    def get_status_color(status):
        colors = {
            "Paid": "success",
            "Completed": "success",
            "Approved": "primary",
            "Pending": "warning",
            "Unpaid": "danger",
            "Cancelled": "danger",
            "Partial": "info",
            "Suspended": "secondary",
            "In Progress": "info"
        }
        return colors.get(status, "light")

    data = []
    for i, exp in enumerate(expenses):
        data.append({
            "no": start + i + 1,
            "ref_no": exp.ref_no,
            "date": exp.expense_date.strftime('%Y-%m-%d'),
            "type": exp.expense_account.name if exp.expense_account else "N/A",
            "payable_to": exp.paid_to or (exp.payable_account.name if exp.payable_account else "N/A"),
            "status": f'<span class="badge badge-{get_status_color(exp.status)}">{exp.status}</span>',
            "total": f"{exp.amount:,.2f}",
            "balance": f"{exp.balance:,.2f}",
            "timestamp": exp.created_at.strftime('%Y-%m-%d %H:%M:%S') if hasattr(exp, 'created_at') and exp.created_at else "",
            "action": f'''
                <div class="dropdown">
                    <button class="btn btn-xs btn-dark dropdown-toggle" type="button" data-toggle="dropdown">Action</button>
                    <div class="dropdown-menu">
                        <a class="dropdown-item" href="#" onclick="viewExpense({exp.id})"><i class="fa fa-eye"></i> View</a>
                        <a class="dropdown-item" href="#" onclick="addPayment({exp.id})"><i class="fa fa-money-bill"></i> Add Payment</a>
                        <div class="dropdown-divider"></div>
                        <a class="dropdown-item text-danger" href="#" onclick="deleteExpense({exp.id})"><i class="fa fa-trash"></i> Delete</a>
                    </div>
                </div>
            '''
        })

    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.get("/admin/accounting/all_budgets")
async def api_all_budgets(
    draw: int = Query(1),
    start: int = Query(0),
    length: int = Query(40),
    fiscal_year_id: str = Query(None),
    org_id: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(models.Budget)
    
    if fiscal_year_id and fiscal_year_id != "All":
        query = query.filter(models.Budget.fiscal_year_id == int(fiscal_year_id))
        
    if org_id and org_id != "All":
        # Note: Budget model might not have store_id directly if it's per account, 
        # but let's assume it has or we can link it.
        # If it doesn't have store_id, we'll skip this filter for now or check models.py
        pass
        
    total_records = query.count()
    budgets = query.order_by(models.Budget.id.desc()).offset(start).limit(length).all()
    
    data = []
    for i, b in enumerate(budgets):
        # Calculate spent for this budget
        spent = db.query(func.sum(models.Expense.amount)).filter(
            models.Expense.account_id == b.account_id,
            func.strftime('%Y', models.Expense.expense_date) == b.fiscal_year.year
        ).scalar() or 0.0
        
        balance = b.amount - spent
        
        data.append({
            "no": start + i + 1,
            "fiscal_year": b.fiscal_year.year if b.fiscal_year else "N/A",
            "store": "Main Store", # Default for now if not in model
            "account": b.account.name if b.account else "N/A",
            "quarter": f"Q{b.quarter}",
            "amount": f"{b.amount:,.2f}",
            "spent": f"{spent:,.2f}",
            "balance": f"{balance:,.2f}",
            "status": '<span class="badge badge-success">Active</span>' if b.is_active else '<span class="badge badge-danger">Inactive</span>',
            "action": f'''
                <button class="btn btn-xs btn-info" onclick="editBudget({b.id})"><i class="fas fa-edit"></i></button>
                <button class="btn btn-xs btn-danger" onclick="deleteBudget({b.id})"><i class="fas fa-trash"></i></button>
            '''
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.post("/api/admin/expenses/new")
async def create_expense(
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    try:
        # Map fields from the exact HTML provided by user
        store_id = int(form_data.get("store_id"))
        account_id = int(form_data.get("type_id")) # This is Expense Type
        payable_id = int(form_data.get("payable_id")) if form_data.get("payable_id") else None
        amount = float(form_data.get("amount"))
        amount_paid = float(form_data.get("amount_paid") or 0)
        balance = amount - amount_paid
        
        # Generate ref_no if not provided
        ref_no = form_data.get("ref_no")
        if not ref_no:
            count = db.query(models.Expense).count()
            ref_no = f"EXP-{count+1:04d}"
            
        new_exp = models.Expense(
            ref_no=ref_no,
            store_id=store_id,
            account_id=account_id,
            payable_id=payable_id,
            amount=amount,
            balance=balance,
            paid_to=form_data.get("paid_to", ""),
            expense_date=datetime.datetime.strptime(form_data.get("expense_date"), '%Y-%m-%d'),
            due_date=datetime.datetime.strptime(form_data.get("due_date"), '%Y-%m-%d') if form_data.get("due_date") else None,
            status=form_data.get("status", "Pending"),
            narrative=form_data.get("narrative"),
            is_active=True
        )
        db.add(new_exp)
        db.commit()
        return RedirectResponse(url="/admin/accounting/expenses", status_code=303)
    except Exception as e:
        print(f"Error creating expense: {e}")
        return JSONResponse(status_code=400, content={"message": str(e)})

# --- Budgeting Routes ---

@app.get("/admin/accounting/budgeting", response_class=HTMLResponse)
async def budgeting_page(request: Request, db: Session = Depends(get_db)):
    fiscal_years = db.query(models.FiscalYear).all()
    accounts = db.query(models.Account).all()
    staff = db.query(models.Staff).all()
    stores = db.query(models.Store).all()
    budgets = db.query(models.Budget).all()
    
    return templates.TemplateResponse(
        request=request,
        name="budgeting.html",
        context={
            "fiscal_years": fiscal_years,
            "accounts": accounts,
            "staff": staff,
            "stores": stores,
            "budgets": budgets,
            "active_page": "budgeting"
        }
    )

@app.post("/api/admin/budgeting/new")
async def create_budget(
    budget_name: str = Form(...),
    staff_id: int = Form(None),
    fiscal_year_id: int = Form(...),
    account_id: int = Form(...),
    quarter: int = Form(...),
    budget_amount: float = Form(...),
    active: str = Form(None),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    is_active = True if active == "1" else False
    
    new_budget = models.Budget(
        name=budget_name,
        staff_id=staff_id,
        fiscal_year_id=fiscal_year_id,
        account_id=account_id,
        quarter=quarter,
        amount=budget_amount,
        is_active=is_active,
        narrative=narrative
    )
    
    db.add(new_budget)
    db.commit()
    
    return RedirectResponse(url="/admin/accounting/budgeting", status_code=303)

@app.post("/api/admin/budgeting/delete/{budget_id}")
async def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    budget = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not budget:
        return JSONResponse(content={"resp": 0, "message": "Budget not found"}, status_code=404)
    
    db.delete(budget)
    db.commit()
    return JSONResponse(content={"resp": 1, "message": "Budget deleted successfully"})

@app.get("/api/admin/budgeting/get/{budget_id}")
async def get_budget(budget_id: int, db: Session = Depends(get_db)):
    budget = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not budget:
        return HTMLResponse(content="Budget not found", status_code=404)
    
    # Return a simple edit form for the modal
    fiscal_years = db.query(models.FiscalYear).all()
    accounts = db.query(models.Account).all()
    staff = db.query(models.Staff).all()
    
    # We can reuse the same form structure but with values filled in
    # For now, let's just return a basic HTML for the modal body
    html = f"""
    <form action="/api/admin/budgeting/update/{budget.id}" method="post">
        <div class="row">
            <div class="col-md-12">
                <label>Budget Name</label>
                <input type="text" name="budget_name" class="form-control" value="{budget.name}" required />
            </div>
            <div class="col-md-12">
                <label>Person Responsible</label>
                <select name="staff_id" class="form-control">
                    <option value=""> ~Select Staff~ </option>
                    {"".join([f'<option value="{s.id}" {"selected" if s.id == budget.staff_id else ""}>{s.name}</option>' for s in staff])}
                </select>
            </div>
            <div class="col-md-12">
                <label>Budget Year</label>
                <select name="fiscal_year_id" class="form-control" required>
                    {"".join([f'<option value="{fy.id}" {"selected" if fy.id == budget.fiscal_year_id else ""}>{fy.year}</option>' for fy in fiscal_years])}
                </select>
            </div>
            <div class="col-md-12">
                <label>Account Affected</label>
                <select name="account_id" class="form-control" required>
                    {"".join([f'<option value="{a.id}" {"selected" if a.id == budget.account_id else ""}>{a.name}</option>' for a in accounts])}
                </select>
            </div>
            <div class="col-md-12">
                <label>Quarter</label>
                <select name="quarter" class="form-control" required>
                    <option value="1" {"selected" if budget.quarter == 1 else ""}>First quarter</option>
                    <option value="2" {"selected" if budget.quarter == 2 else ""}>Second quarter</option>
                    <option value="3" {"selected" if budget.quarter == 3 else ""}>Third quarter</option>
                    <option value="4" {"selected" if budget.quarter == 4 else ""}>Fourth quarter</option>
                </select>
            </div>
            <div class="col-md-12">
                <label>Budget Amount</label>
                <input type="number" step="0.01" name="budget_amount" class="form-control" value="{budget.amount}" required />
            </div>
            <div class="col-md-12">
                <label>Active</label>
                <input type="checkbox" name="active" value="1" {"checked" if budget.is_active else ""} />
            </div>
            <div class="col-md-12">
                <label>Narrative</label>
                <textarea name="narrative" class="form-control">{budget.narrative or ""}</textarea>
            </div>
            <div class="col-md-12 mt-3">
                <button type="submit" class="btn btn-primary">Update Budget</button>
            </div>
        </div>
    </form>
    """
    return HTMLResponse(content=html)

@app.post("/api/admin/budgeting/update/{budget_id}")
async def update_budget(
    budget_id: int,
    budget_name: str = Form(...),
    staff_id: int = Form(None),
    fiscal_year_id: int = Form(...),
    account_id: int = Form(...),
    quarter: int = Form(...),
    budget_amount: float = Form(...),
    active: str = Form(None),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    budget = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if not budget:
        return RedirectResponse(url="/admin/accounting/budgeting", status_code=303)
    
    budget.name = budget_name
    budget.staff_id = staff_id
    budget.fiscal_year_id = fiscal_year_id
    budget.account_id = account_id
    budget.quarter = quarter
    budget.amount = budget_amount
    budget.is_active = True if active == "1" else False
    budget.narrative = narrative
    db.commit()
    return RedirectResponse(url="/admin/accounting/budgeting", status_code=303)

# --- PETTY CASH REQUEST ROUTES ---

@app.get("/admin/accounting/petty-cash", response_class=HTMLResponse)
async def admin_petty_cash_request(request: Request, db: Session = Depends(get_db)):
    stores = db.query(models.Store).all()
    return templates.TemplateResponse(
        request=request,
        name="petty_cash_request.html",
        context={
            "stores": stores,
            "active_page": "petty_cash",
            "today": datetime.datetime.now().strftime("%Y-%m-%d")
        }
    )

@app.get("/api/admin/petty-cash/all")
async def api_all_petty_cash_requests(
    draw: int = Query(1),
    start: int = Query(0),
    length: int = Query(40),
    from_date: str = Query(None),
    to_date: str = Query(None),
    org_id: str = Query(None),
    status_id: str = Query("All"),
    db: Session = Depends(get_db)
):
    query = db.query(models.PettyCashRequest)
    
    if org_id and org_id != "All" and org_id != "Select option":
        query = query.filter(models.PettyCashRequest.store_id == int(org_id))
    
    if status_id != "All":
        query = query.filter(models.PettyCashRequest.status == status_id)
        
    if from_date:
        try:
            query = query.filter(models.PettyCashRequest.request_date >= datetime.datetime.strptime(from_date, "%Y-%m-%d"))
        except: pass
    if to_date:
        try:
            query = query.filter(models.PettyCashRequest.request_date <= datetime.datetime.strptime(to_date, "%Y-%m-%d"))
        except: pass
        
    total_records = query.count()
    requests = query.order_by(models.PettyCashRequest.created_at.desc()).offset(start).limit(length).all()
    
    data = []
    for idx, r in enumerate(requests):
        requested_by = r.requested_by.name if r.requested_by else "Unknown"
        store_name = r.store.name if r.store else "Unknown"
        
        status_badge = f'<span class="badge badge-warning">{r.status}</span>'
        if r.status == "Approved":
            status_badge = f'<span class="badge badge-success">{r.status}</span>'
        elif r.status == "Cancelled":
            status_badge = f'<span class="badge badge-danger">{r.status}</span>'
        elif r.status == "Completed":
            status_badge = f'<span class="badge badge-info">{r.status}</span>'
            
        actions = f"""
        <div class="dropdown">
            <button class="btn btn-xs btn-dark dropdown-toggle" type="button" data-toggle="dropdown">Action</button>
            <div class="dropdown-menu">
                <a class="dropdown-item" href="#" onclick="view_request({r.id})"><i class="fa fa-eye"></i> View</a>
                <a class="dropdown-item" href="#" onclick="allocate_funds({r.id})"><i class="fa fa-check-circle"></i> Approve/Allocate</a>
                <div class="dropdown-divider"></div>
                <a class="dropdown-item text-danger" href="#" onclick="delete_cash_request({r.id})"><i class="fa fa-trash"></i> Delete</a>
            </div>
        </div>
        """
        
        data.append({
            "no": start + idx + 1,
            "reference": r.ref_no,
            "amount": f"{r.amount:,.2f}",
            "request_date": r.request_date.strftime("%Y-%m-%d") if r.request_date else "",
            "requested_by": requested_by,
            "status": status_badge,
            "description": r.narrative or "",
            "store": store_name,
            "timestamp": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "action": actions
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.post("/api/admin/petty-cash/add")
async def api_add_petty_cash_request(
    request_amount: float = Form(...),
    request_date: str = Form(...),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    count = db.query(models.PettyCashRequest).count()
    ref_no = f"PCREQ-{datetime.datetime.now().strftime('%y%m')}-{count+1:04d}"
    
    staff = db.query(models.Staff).first()
    store = db.query(models.Store).first()
    
    new_req = models.PettyCashRequest(
        ref_no=ref_no,
        amount=request_amount,
        request_date=datetime.datetime.strptime(request_date, "%Y-%m-%d"),
        narrative=narrative,
        requested_by_id=staff.id if staff else None,
        store_id=store.id if store else None,
        status="Pending"
    )
    db.add(new_req)
    db.commit()
    return RedirectResponse(url="/admin/accounting/petty-cash", status_code=303)

@app.get("/api/admin/petty-cash/get/{req_id}")
async def api_get_petty_cash_request(req_id: int, db: Session = Depends(get_db)):
    req = db.query(models.PettyCashRequest).filter(models.PettyCashRequest.id == req_id).first()
    if not req:
        return HTMLResponse("Request not found")
    
    html = f"""
    <div class="row">
        <div class="col-md-12">
            <table class="table table-sm table-bordered">
                <tr><th>Reference</th><td>{req.ref_no}</td></tr>
                <tr><th>Amount</th><td>{req.amount:,.2f}</td></tr>
                <tr><th>Date</th><td>{req.request_date.strftime("%Y-%m-%d")}</td></tr>
                <tr><th>Requested By</th><td>{req.requested_by.name if req.requested_by else ""}</td></tr>
                <tr><th>Store</th><td>{req.store.name if req.store else ""}</td></tr>
                <tr><th>Status</th><td>{req.status}</td></tr>
                <tr><th>Narrative</th><td>{req.narrative or ""}</td></tr>
            </table>
        </div>
        <div class="col-md-12">
            <button type="button" class="btn btn-danger" data-dismiss="modal">Close</button>
        </div>
    </div>
    """
    return HTMLResponse(content=html)

@app.get("/api/admin/petty-cash/allocate/{req_id}")
async def api_allocate_funds_form(req_id: int, db: Session = Depends(get_db)):
    req = db.query(models.PettyCashRequest).filter(models.PettyCashRequest.id == req_id).first()
    if not req:
        return HTMLResponse("Request not found")
    
    html = f"""
    <form action="/api/admin/petty-cash/update-status/{req.id}" method="POST">
        <div class="row">
            <div class="col-md-12">
                <h5>Approve/Allocate Funds for {req.ref_no}</h5>
                <label>Status</label>
                <select name="status" class="form-control">
                    <option value="Approved" {"selected" if req.status == "Approved" else ""}>Approved</option>
                    <option value="Cancelled" {"selected" if req.status == "Cancelled" else ""}>Cancelled</option>
                    <option value="Completed" {"selected" if req.status == "Completed" else ""}>Completed</option>
                    <option value="Pending" {"selected" if req.status == "Pending" else ""}>Pending</option>
                </select>
            </div>
            <div class="col-md-12 mt-2">
                <label>Amount to Allocate</label>
                <input type="number" step="0.01" name="amount" class="form-control" value="{req.amount}" />
            </div>
            <div class="col-md-12 mt-3">
                <button type="submit" class="btn btn-success">Update Status</button>
                <button type="button" class="btn btn-danger" data-dismiss="modal">Cancel</button>
            </div>
        </div>
    </form>
    """
    return HTMLResponse(content=html)

@app.post("/api/admin/petty-cash/update-status/{req_id}")
async def api_update_petty_cash_status(
    req_id: int,
    status: str = Form(...),
    amount: float = Form(...),
    db: Session = Depends(get_db)
):
    req = db.query(models.PettyCashRequest).filter(models.PettyCashRequest.id == req_id).first()
    if req:
        req.status = status
        req.amount = amount
        db.commit()
    return RedirectResponse(url="/admin/accounting/petty-cash", status_code=303)

@app.post("/api/admin/petty-cash/delete/{req_id}")
async def api_delete_petty_cash_request(req_id: int, db: Session = Depends(get_db)):
    req = db.query(models.PettyCashRequest).filter(models.PettyCashRequest.id == req_id).first()
    if req:
        db.delete(req)
        db.commit()
        return {"resp": "1", "message": "Request deleted successfully"}
    return {"resp": "0", "message": "Request not found"}

@app.get("/admin/accounting/income", response_class=HTMLResponse)
async def income_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    accounts = db.query(models.Account).filter(models.Account.account_type == "Revenue").all()
    departments = db.query(models.Department).all()
    current_date = datetime.datetime.utcnow().date().isoformat()
    return templates.TemplateResponse(
        request=request,
        name="income.html",
        context={
            "settings": settings,
            "stores": stores,
            "accounts": accounts,
            "departments": departments,
            "current_date": current_date,
            "active_page": "income"
        }
    )

@app.get("/admin/accounting/all_incomes")
async def all_incomes_data(
    draw: int = 1,
    start: int = 0,
    length: int = 10,
    db: Session = Depends(get_db)
):
    query = db.query(models.Income)
    total_count = query.count()
    incomes = query.order_by(models.Income.id.desc()).offset(start).limit(length).all()
    
    data = []
    for inc in incomes:
        data.append({
            "ref_no": inc.ref_no,
            "account": inc.account.name if inc.account else "N/A",
            "amount": f"{inc.amount:,.2f}",
            "balance": f"{inc.balance:,.2f}",
            "customer": inc.customer_name,
            "date": inc.income_date.strftime("%Y-%m-%d"),
            "status": inc.status,
            "department": inc.department.name if inc.department else "N/A",
            "narrative": inc.narrative or "",
            "action": f'<button class="btn btn-xs btn-info" onclick="view_income({inc.id})"><i class="fa fa-eye"></i></button>'
        })
    
    return {
        "draw": draw,
        "recordsTotal": total_count,
        "recordsFiltered": total_count,
        "data": data
    }

@app.post("/admin/accounting/new_income")
async def new_income(
    store_id: int = Form(...),
    account_id: int = Form(...),
    status: str = Form(...),
    department_id: Optional[int] = Form(None),
    amount: float = Form(...),
    income_date: str = Form(...),
    customer_name: str = Form(...),
    narrative: Optional[str] = Form(None),
    is_active: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    ref_no = f"INC-{datetime.datetime.utcnow().strftime('%Y%m%d')}-{db.query(models.Income).count() + 1:04d}"
    income = models.Income(
        ref_no=ref_no,
        store_id=store_id,
        account_id=account_id,
        status=status,
        department_id=department_id,
        amount=amount,
        balance=0.0,
        income_date=datetime.datetime.strptime(income_date, "%Y-%m-%d"),
        customer_name=customer_name,
        narrative=narrative,
        is_active=bool(is_active)
    )
    db.add(income)
    db.commit()
    return RedirectResponse(url="/admin/accounting/income", status_code=303)

@app.get("/admin/accounting/account-types", response_class=HTMLResponse)
async def account_types_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="account_types.html",
        context={
            "settings": settings,
            "active_page": "account_types"
        }
    )

@app.get("/admin/accounting/all_account_types")
async def all_account_types_data(
    draw: int = 1,
    start: int = 0,
    length: int = 10,
    db: Session = Depends(get_db)
):
    query = db.query(models.AccountType)
    total_count = query.count()
    types = query.offset(start).limit(length).all()
    
    data = []
    for t in types:
        data.append({
            "name": t.name,
            "description": t.description or "",
            "action": f'<button class="btn btn-xs btn-danger" onclick="delete_type({t.id})"><i class="fa fa-trash"></i></button>'
        })
    
    return {
        "draw": draw,
        "recordsTotal": total_count,
        "recordsFiltered": total_count,
        "data": data
    }

@app.post("/admin/accounting/new_account_type")
async def new_account_type(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    acc_type = models.AccountType(name=name, description=description)
    db.add(acc_type)
    db.commit()
    return RedirectResponse(url="/admin/accounting/account-types", status_code=303)

@app.get("/admin/accounting/charts-of-accounts", response_class=HTMLResponse)
async def charts_of_accounts_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    account_types = db.query(models.AccountType).filter(models.AccountType.parent_id is None).all()
    return templates.TemplateResponse(
        request=request,
        name="accounts.html",
        context={
            "settings": settings,
            "stores": stores,
            "account_types": account_types,
            "active_page": "charts_of_accounts"
        }
    )

@app.get("/admin/accounting/all_accounts")
async def all_accounts_data(
    draw: int = 1,
    start: int = 0,
    length: int = 10,
    db: Session = Depends(get_db)
):
    query = db.query(models.Account)
    total_count = query.count()
    accounts = query.order_by(models.Account.id.desc()).offset(start).limit(length).all()
    
    data = []
    for acc in accounts:
        active_icon = '<i class="text-green fa fa-check"></i>' if acc.is_active else '<i class="text-danger fa fa-close"></i>'
        data.append({
            "id": acc.id,
            "name": acc.name,
            "code": f'<a style="color: blue" href="/admin/accounting/account_ledger/{acc.code}">{acc.code}</a>',
            "sub_type": acc.sub_type.name if acc.sub_type else "N/A",
            "type": acc.type.name if acc.type else "N/A",
            "org": acc.store.name if acc.store else "N/A",
            "active": active_icon,
            "created_by": acc.user.name if acc.user else "Admin",
            "narrative": acc.narrative or "",
            "action": f'''
                <button type="button" onclick="get_account({acc.id})" class="btn btn-xs btn-rgp">Edit <i class="fa fa-edit"></i> </button>
                <button type="button" onclick="delete_account({acc.id})" class="btn btn-xs btn-rgd">Delete <i class="fa fa-trash"></i> </button>
            '''
        })
    
    return {
        "draw": draw,
        "recordsTotal": total_count,
        "recordsFiltered": total_count,
        "data": data
    }

@app.get("/admin/accounting/subaccount_types/{parent_id}")
async def get_subaccount_types(parent_id: int, db: Session = Depends(get_db)):
    sub_types = db.query(models.AccountType).filter(models.AccountType.parent_id == parent_id).all()
    return [{"id": st.id, "name": st.name} for st in sub_types]

@app.post("/admin/accounting/add_account")
async def add_account(
    org_id: int = Form(...),
    account_type_id: int = Form(...),
    subaccount_type_id: Optional[int] = Form(None),
    account_name: str = Form(...),
    account_code: str = Form(...),
    opening_balance: float = Form(0.0),
    other_category: Optional[str] = Form(None),
    narrative: Optional[str] = Form(None),
    is_key: int = Form(0),
    active: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    is_active = active == "true"
    acc = models.Account(
        name=account_name,
        account_type_id=account_type_id,
        subaccount_type_id=subaccount_type_id,
        code=account_code,
        balance=opening_balance,
        store_id=org_id,
        other_category=other_category,
        narrative=narrative,
        is_key=bool(is_key),
        is_active=is_active
    )
    db.add(acc)
    db.commit()
    return RedirectResponse(url="/admin/accounting/charts-of-accounts", status_code=303)

@app.get("/admin/accounting/bank-transfers", response_class=HTMLResponse)
async def bank_transfers_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    accounts = db.query(models.Account).all()
    fiscal_years = db.query(models.FiscalYear).all()
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    return templates.TemplateResponse(
        request=request,
        name="bank_transfers.html",
        context={
            "settings": settings,
            "stores": stores,
            "accounts": accounts,
            "fiscal_years": fiscal_years,
            "active_page": "bank_transfers",
            "today": today
        }
    )

@app.post("/admin/accounting/add_transfer")
async def add_transfer(
    request: Request,
    org_id: int = Form(...),
    account_idcr: int = Form(...),
    account_iddr: int = Form(...),
    amount: float = Form(...),
    reference: str = Form(...),
    transaction_date: str = Form(...),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    # Create transfer record
    ref_no = f"BT-{datetime.datetime.now().strftime('%y%m%d%H%M%S')}"
    transfer = models.BankTransfer(
        ref_no=ref_no,
        store_id=org_id,
        from_account_id=account_idcr,
        to_account_id=account_iddr,
        amount=amount,
        transaction_date=datetime.datetime.strptime(transaction_date, '%Y-%m-%d'),
        reference=reference,
        narrative=narrative
    )
    
    # Update account balances
    from_acc = db.query(models.Account).filter(models.Account.id == account_idcr).first()
    to_acc = db.query(models.Account).filter(models.Account.id == account_iddr).first()
    
    if from_acc:
        from_acc.balance -= amount
    if to_acc:
        to_acc.balance += amount
        
    db.add(transfer)
    db.commit()
    return RedirectResponse(url="/admin/accounting/bank-transfers", status_code=303)

@app.get("/admin/accounting/all_transfers")
async def api_all_transfers(
    draw: int = 1,
    start: int = 0,
    length: int = 10,
    from_date: str = None,
    to_date: str = None,
    org_id: str = "All",
    db: Session = Depends(get_db)
):
    query = db.query(models.BankTransfer)
    
    if from_date and to_date:
        try:
            f_date = datetime.datetime.strptime(from_date, '%Y-%m-%d')
            t_date = datetime.datetime.strptime(to_date, '%Y-%m-%d') + datetime.timedelta(days=1)
            query = query.filter(models.BankTransfer.transaction_date >= f_date, models.BankTransfer.transaction_date < t_date)
        except ValueError:
            pass
    
    if org_id != "All":
        query = query.filter(models.BankTransfer.store_id == int(org_id))
        
    total = query.count()
    transfers = query.order_by(models.BankTransfer.transaction_date.desc()).offset(start).limit(length).all()
    
    data = []
    for t in transfers:
        data.append({
            "date": t.transaction_date.strftime('%Y-%m-%d'),
            "ref_no": t.ref_no,
            "reference": t.reference,
            "account_name": f"{t.from_account.name} &rarr; {t.to_account.name}",
            "account_code": f"{t.from_account.code} &rarr; {t.to_account.code}",
            "narrative": t.narrative,
            "user": t.created_by.name if t.created_by else "Admin",
            "dr": f"{t.amount:,.2f}",
            "cr": f"{t.amount:,.2f}"
        })
        
    return {
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": data
    }

# --- Journal Entry Routes ---

@app.get("/admin/accounting/journal-entry", response_class=HTMLResponse)
async def journal_entry_list(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    accounts = db.query(models.Account).all()
    fiscal_years = db.query(models.FiscalYear).all()
    customers = db.query(models.Customer).all()
    suppliers = db.query(models.Supplier).all()
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    return templates.TemplateResponse(
        request=request,
        name="journal_entry.html",
        context={
            "settings": settings,
            "stores": stores,
            "accounts": accounts,
            "fiscal_years": fiscal_years,
            "customers": customers,
            "suppliers": suppliers,
            "active_page": "journal_entry",
            "today": today
        }
    )

@app.post("/admin/accounting/journal-entry/transfer")
async def create_journal_transfer(
    request: Request, 
    transaction_date: str = Form(...), 
    store_id: int = Form(...), 
    fiscal_year_id: int = Form(...), 
    from_account_id: int = Form(...), 
    to_account_id: int = Form(...), 
    amount: float = Form(...), 
    reference: str = Form(None), 
    narrative: str = Form(None), 
    db: Session = Depends(get_db)
):
    # Generate common ref_no for the transfer pair
    timestamp = datetime.datetime.utcnow().strftime('%y%m%d%H%M%S')
    ref_no = f"TRF-{timestamp}"
    t_date = datetime.datetime.strptime(transaction_date, '%Y-%m-%d')
    
    # Credit entry (From Account)
    credit_entry = models.JournalPosting(
        ref_no=f"{ref_no}-CR",
        store_id=store_id,
        fiscal_year_id=fiscal_year_id,
        account_id=from_account_id,
        amount=amount,
        dr_cr='Credit',
        transaction_date=t_date,
        reference=reference,
        narrative=narrative,
        created_by_id=1 # Default admin for now
    )
    
    # Debit entry (To Account)
    debit_entry = models.JournalPosting(
        ref_no=f"{ref_no}-DR",
        store_id=store_id,
        fiscal_year_id=fiscal_year_id,
        account_id=to_account_id,
        amount=amount,
        dr_cr='Debit',
        transaction_date=t_date,
        reference=reference,
        narrative=narrative,
        created_by_id=1
    )
    
    # No manual balance update here; reports will calculate current balance from opening balance + postings
    
    db.add_all([credit_entry, debit_entry])
    db.commit()
    return RedirectResponse(url="/admin/accounting/journal-entry", status_code=303)

@app.post("/admin/accounting/journal-entry/posting")
async def create_journal_posting(
    request: Request, 
    transaction_date: str = Form(...), 
    store_id: int = Form(...), 
    fiscal_year_id: int = Form(...), 
    account_id: int = Form(...), 
    dr_cr: str = Form(...), 
    amount: float = Form(...), 
    customer_supplier_id: str = Form(None),
    reference: str = Form(None), 
    narrative: str = Form(None), 
    db: Session = Depends(get_db)
):
    timestamp = datetime.datetime.utcnow().strftime('%y%m%d%H%M%S')
    ref_no = f"JRN-{timestamp}"
    t_date = datetime.datetime.strptime(transaction_date, '%Y-%m-%d')
    
    cust_id = None
    supp_id = None
    if customer_supplier_id:
        if customer_supplier_id.startswith('C'):
            cust_id = int(customer_supplier_id[1:])
        elif customer_supplier_id.startswith('S'):
            supp_id = int(customer_supplier_id[1:])

    posting = models.JournalPosting(
        ref_no=ref_no,
        store_id=store_id,
        fiscal_year_id=fiscal_year_id,
        account_id=account_id,
        customer_id=cust_id,
        supplier_id=supp_id,
        amount=amount,
        dr_cr=dr_cr,
        transaction_date=t_date,
        reference=reference,
        narrative=narrative,
        created_by_id=1
    )
    
    # Opening balance remains static; reports aggregate postings
            
    db.add(posting)
    db.commit()
    return RedirectResponse(url="/admin/accounting/journal-entry", status_code=303)

@app.get("/api/admin/accounting/journal-entry/data")
async def journal_entry_data(
    request: Request,
    draw: int = Query(...), 
    start: int = Query(...), 
    length: int = Query(...), 
    db: Session = Depends(get_db)
):
    query = db.query(models.JournalPosting).join(models.Account)
    
    # Search logic
    search_value = request.query_params.get('search[value]')
    if search_value:
        query = query.filter(
            or_(
                models.JournalPosting.ref_no.ilike(f"%{search_value}%"),
                models.Account.name.ilike(f"%{search_value}%"),
                models.JournalPosting.reference.ilike(f"%{search_value}%")
            )
        )
    
    total_records = db.query(models.JournalPosting).count()
    filtered_records = query.count()
    
    postings = query.order_by(models.JournalPosting.transaction_date.desc()).offset(start).limit(length).all()
    
    data = []
    for p in postings:
        entity_name = ""
        if p.customer:
            entity_name = f"Cust: {p.customer.name}"
        elif p.supplier:
            entity_name = f"Supp: {p.supplier.name}"
            
        data.append({
            "ref_no": p.ref_no,
            "transaction_date": p.transaction_date.strftime('%Y-%m-%d'),
            "store": p.store.name if p.store else "Global",
            "account_name": p.account.name,
            "entity": entity_name or "-",
            "debit": p.amount if p.dr_cr == 'Debit' else 0,
            "credit": p.amount if p.dr_cr == 'Credit' else 0,
            "reference": p.reference or "",
            "narrative": p.narrative or "",
            "created_by": p.created_by.name if p.created_by else "System"
        })
    
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": data
    }

# --- Cash Flow Routes ---

@app.get("/admin/accounting/cash-flow", response_class=HTMLResponse)
async def cash_flow_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    return templates.TemplateResponse(
        request=request,
        name="cash_flow.html",
        context={
            "settings": settings,
            "stores": stores,
            "today": today,
            "active_page": "cash_flow"
        }
    )

@app.post("/api/admin/accounting/get-cash-flow")
async def get_cash_flow(data: dict, db: Session = Depends(get_db)):
    from_date_str = data.get('from_date')
    to_date_str = data.get('to_date')
    store_id_raw = data.get('store_id')
    
    if not store_id_raw:
        return {"status": "error", "message": "Store ID is required"}
    
    store_id = int(store_id_raw)

    try:
        from_date = datetime.datetime.strptime(from_date_str, '%Y-%m-%d')
        to_date = datetime.datetime.strptime(to_date_str, '%Y-%m-%d') + datetime.timedelta(days=1)
    except (ValueError, TypeError):
        return {"status": "error", "message": "Invalid date format"}

    try:
        # Find relevant accounts (Cash/Bank/M-Pesa)
        acc_query = db.query(models.Account).filter(
            or_(
                models.Account.name.ilike('%cash%'),
                models.Account.name.ilike('%bank%'),
                models.Account.name.ilike('%m-pesa%'),
                models.Account.name.ilike('%mpesa%')
            )
        )
        
        # Filter by store if provided
        if store_id:
            acc_query = acc_query.filter(or_(models.Account.store_id == store_id, models.Account.store_id is None))
        
        cash_accounts = acc_query.all()
        cash_acc_ids = [a.id for a in cash_accounts]
        
        if not cash_accounts:
            return {
                "status": "success", 
                "opening_balance": 0, 
                "data": [], 
                "closing_balance": 0,
                "message": "No cash/bank accounts found"
            }

        # Opening Balance Calculation
        # Include base balance from Account model + Inflow (Debit) - Outflow (Credit)
        base_balance_sum = db.query(func.sum(models.Account.balance)).filter(
            models.Account.id.in_(cash_acc_ids)
        ).scalar() or 0

        opening_inflow = db.query(func.sum(models.JournalPosting.amount)).filter(
            models.JournalPosting.account_id.in_(cash_acc_ids),
            models.JournalPosting.store_id == store_id,
            models.JournalPosting.dr_cr == 'Debit',
            models.JournalPosting.transaction_date < from_date
        ).scalar() or 0
        
        opening_outflow = db.query(func.sum(models.JournalPosting.amount)).filter(
            models.JournalPosting.account_id.in_(cash_acc_ids),
            models.JournalPosting.store_id == store_id,
            models.JournalPosting.dr_cr == 'Credit',
            models.JournalPosting.transaction_date < from_date
        ).scalar() or 0
        
        opening_balance = base_balance_sum + opening_inflow - opening_outflow

        # Transactions in the period
        postings = db.query(models.JournalPosting).filter(
            models.JournalPosting.account_id.in_(cash_acc_ids),
            models.JournalPosting.store_id == store_id,
            models.JournalPosting.transaction_date >= from_date,
            models.JournalPosting.transaction_date < to_date
        ).order_by(models.JournalPosting.transaction_date.asc()).all()

        report_data = []
        running_balance = opening_balance
        
        for p in postings:
            inflow = p.amount if p.dr_cr == 'Debit' else 0
            outflow = p.amount if p.dr_cr == 'Credit' else 0
            running_balance += (inflow - outflow)
            
            report_data.append({
                "date": p.transaction_date.strftime('%Y-%m-%d'),
                "description": p.narrative or "",
                "ref_no": p.ref_no or "",
                "inflow": inflow,
                "outflow": outflow,
                "running_balance": round(running_balance, 2)
            })
            
        return {
            "status": "success",
            "opening_balance": round(opening_balance, 2),
            "data": report_data,
            "closing_balance": round(running_balance, 2)
        }
    except Exception as e:
        return {"status": "error", "message": f"Internal Server Error: {str(e)}"}

# --- Trial Balance Routes ---

@app.get("/admin/accounting/trial-balance", response_class=HTMLResponse)
async def trial_balance_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    return templates.TemplateResponse(
        request=request,
        name="trial_balance.html",
        context={
            "settings": settings,
            "stores": stores,
            "today": today,
            "active_page": "trial_balance"
        }
    )

@app.post("/api/admin/accounting/get-trial-balance")
async def get_trial_balance(data: dict, db: Session = Depends(get_db)):
    org_id_raw = data.get("org_id")
    sheet_date_str = data.get("sheet_date")
    
    if not sheet_date_str:
        return {"error": "Date is required"}
        
    try:
        end_date = datetime.datetime.strptime(sheet_date_str, '%Y-%m-%d') + datetime.timedelta(days=1)
    except ValueError:
        return {"error": "Invalid date format"}

    accounts = db.query(models.Account).all()
    
    report_data = []
    total_debit = 0
    total_credit = 0
    
    for acc in accounts:
        # Store filtering
        if org_id_raw and org_id_raw != 'All':
            if acc.store_id and acc.store_id != int(org_id_raw):
                continue
                
        base_dr = 0
        base_cr = 0
        
        # Determine normal balance side based on account type
        acc_type_obj = acc.type
        acc_type_name = (acc_type_obj.name if (acc_type_obj and acc_type_obj.name) else (acc.account_type or "")).capitalize()
        
        if acc_type_name in ['Asset', 'Expense']:
            base_dr = acc.balance or 0
        else:
            base_cr = acc.balance or 0
            
        # Sum postings
        query = db.query(
            func.sum(models.JournalPosting.amount).label('total_amount'),
            models.JournalPosting.dr_cr
        ).filter(
            models.JournalPosting.account_id == acc.id,
            models.JournalPosting.transaction_date < end_date
        )
        
        if org_id_raw and org_id_raw != 'All':
            query = query.filter(models.JournalPosting.store_id == int(org_id_raw))
            
        postings = query.group_by(models.JournalPosting.dr_cr).all()
        
        period_dr = 0
        period_cr = 0
        for p in postings:
            if p.dr_cr == 'Debit':
                period_dr = p.total_amount or 0
            elif p.dr_cr == 'Credit':
                period_cr = p.total_amount or 0
                
        final_dr = base_dr + period_dr
        final_cr = base_cr + period_cr
        
        net_balance = final_dr - final_cr
        
        if net_balance != 0:
            if net_balance > 0:
                report_data.append({
                    "name": acc.name,
                    "debit": round(net_balance, 2),
                    "credit": 0
                })
                total_debit += net_balance
            else:
                report_data.append({
                    "name": acc.name,
                    "debit": 0,
                    "credit": round(abs(net_balance), 2)
                })
                total_credit += abs(net_balance)
                
    return {
        "data": report_data,
        "total_debit": round(total_debit, 2),
        "total_credit": round(total_credit, 2)
    }

@app.post("/admin/accounting/trial-balance-report")
async def trial_balance_print(
    request: Request,
    org_id: str = Form(...),
    sheet_date: str = Form(...),
    db: Session = Depends(get_db)
):
    # This would typically generate a PDF. For now, we render a printable HTML view.
    settings = get_settings(db)
    data = await get_trial_balance({"org_id": org_id, "sheet_date": sheet_date}, db)
    
    store_name = "All Stores"
    if org_id != 'All':
        store = db.query(models.Store).filter(models.Store.id == int(org_id)).first()
        if store:
            store_name = store.name

    return templates.TemplateResponse(
        request=request,
        name="reports/trial_balance_print.html",
        context={
            "settings": settings,
            "data": data,
            "sheet_date": sheet_date,
            "store_name": store_name,
            "now": datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        }
    )

# --- Profit & Loss Routes ---

@app.get("/admin/accounting/profit-loss", response_class=HTMLResponse)
async def profit_loss_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    start_of_month = datetime.datetime.utcnow().replace(day=1).strftime('%Y-%m-%d')
    return templates.TemplateResponse(
        request=request,
        name="profit_loss.html",
        context={
            "settings": settings,
            "stores": stores,
            "today": today,
            "start_of_month": start_of_month,
            "active_page": "profit_loss"
        }
    )

@app.post("/api/admin/accounting/get-profit-loss")
async def get_profit_loss(data: dict, db: Session = Depends(get_db)):
    store_id_raw = data.get("store_id")
    from_date_str = data.get("from_date")
    to_date_str = data.get("to_date")
    
    if not from_date_str or not to_date_str:
        return {"error": "Date range is required"}
        
    try:
        from_date = datetime.datetime.strptime(from_date_str, '%Y-%m-%d')
        to_date = datetime.datetime.strptime(to_date_str, '%Y-%m-%d') + datetime.timedelta(days=1)

        accounts = db.query(models.Account).all()
        
        revenue_accounts = []
        expense_accounts = []
        total_revenue = 0
        total_expenses = 0
        
        for acc in accounts:
            acc_type_obj = acc.type
            acc_type_name = (acc_type_obj.name if (acc_type_obj and acc_type_obj.name) else (acc.account_type or "")).capitalize()
            
            if acc_type_name not in ['Revenue', 'Expense']:
                continue
                
            # Sum postings for the period
            query = db.query(
                func.sum(models.JournalPosting.amount).label('total_amount'),
                models.JournalPosting.dr_cr
            ).filter(
                models.JournalPosting.account_id == acc.id,
                models.JournalPosting.transaction_date >= from_date,
                models.JournalPosting.transaction_date < to_date
            )
            
            if store_id_raw and store_id_raw != 'All':
                query = query.filter(models.JournalPosting.store_id == int(store_id_raw))
                
            postings = query.group_by(models.JournalPosting.dr_cr).all()
            
            period_dr = 0
            period_cr = 0
            for p in postings:
                if p.dr_cr == 'Debit':
                    period_dr = p.total_amount or 0
                elif p.dr_cr == 'Credit':
                    period_cr = p.total_amount or 0
                    
            if acc_type_name == 'Revenue':
                balance = period_cr - period_dr
                if balance != 0:
                    revenue_accounts.append({"name": acc.name, "balance": balance})
                    total_revenue += balance
            else: # Expense
                balance = period_dr - period_cr
                if balance != 0:
                    expense_accounts.append({"name": acc.name, "balance": balance})
                    total_expenses += balance
                    
        return {
            "revenue_accounts": revenue_accounts,
            "expense_accounts": expense_accounts,
            "total_revenue": round(total_revenue, 2),
            "total_expenses": round(total_expenses, 2),
            "net_profit": round(total_revenue - total_expenses, 2)
        }
    except ValueError:
        return {"error": "Invalid date format"}
    except Exception as e:
        return {"error": f"Internal Server Error: {str(e)}"}

# --- Balance Sheet Routes ---

@app.get("/admin/accounting/balance-sheet", response_class=HTMLResponse)
async def balance_sheet_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    return templates.TemplateResponse(
        request=request,
        name="balance_sheet.html",
        context={
            "settings": settings,
            "stores": stores,
            "today": today,
            "active_page": "balance_sheet"
        }
    )

@app.post("/api/admin/accounting/get-balance-sheet")
async def get_balance_sheet(data: dict, db: Session = Depends(get_db)):
    store_id_raw = data.get("store_id")
    as_at_date_str = data.get("as_at_date")
    
    if not as_at_date_str:
        return {"error": "Date is required"}
        
    try:
        as_at_date = datetime.datetime.strptime(as_at_date_str, '%Y-%m-%d') + datetime.timedelta(days=1)
        
        accounts = db.query(models.Account).all()
        
        report = {
            "assets": {"current": [], "fixed": []},
            "liabilities": [],
            "equity": [],
            "total_assets": 0,
            "total_liabilities_equity": 0,
            "retained_earnings": 0
        }
        
        total_revenue = 0
        total_expenses = 0
        
        for acc in accounts:
            acc_type_obj = acc.type
            sub_type_obj = acc.sub_type
            
            acc_type_name = (acc_type_obj.name if (acc_type_obj and acc_type_obj.name) else (acc.account_type or "")).capitalize()
            sub_type_name = (sub_type_obj.name if (sub_type_obj and sub_type_obj.name) else (acc.other_category or "")).capitalize()
            
            # Calculate balance up to as_at_date
            query = db.query(
                func.sum(models.JournalPosting.amount).label('total_amount'),
                models.JournalPosting.dr_cr
            ).filter(
                models.JournalPosting.account_id == acc.id,
                models.JournalPosting.transaction_date < as_at_date
            )
            
            if store_id_raw and store_id_raw != 'All':
                query = query.filter(models.JournalPosting.store_id == int(store_id_raw))
                
            postings = query.group_by(models.JournalPosting.dr_cr).all()
            
            dr = 0
            cr = 0
            for p in postings:
                if p.dr_cr == 'Debit':
                    dr = p.total_amount or 0
                elif p.dr_cr == 'Credit':
                    cr = p.total_amount or 0
            
            # Add base balance from Account model
            if acc_type_name in ['Asset', 'Expense']:
                dr += (acc.balance or 0)
            else:
                cr += (acc.balance or 0)
                
            if acc_type_name == 'Asset':
                balance = dr - cr
                if balance != 0:
                    if 'Fixed' in sub_type_name:
                        report["assets"]["fixed"].append({"name": acc.name, "balance": balance})
                    else:
                        report["assets"]["current"].append({"name": acc.name, "balance": balance})
                    report["total_assets"] += balance
            elif acc_type_name == 'Liability':
                balance = cr - dr
                if balance != 0:
                    report["liabilities"].append({"name": acc.name, "balance": balance})
                    report["total_liabilities_equity"] += balance
            elif acc_type_name == 'Equity':
                balance = cr - dr
                if balance != 0:
                    report["equity"].append({"name": acc.name, "balance": balance})
                    report["total_liabilities_equity"] += balance
            elif acc_type_name == 'Revenue':
                total_revenue += (cr - dr)
            elif acc_type_name == 'Expense':
                total_expenses += (dr - cr)
                
        report["retained_earnings"] = round(total_revenue - total_expenses, 2)
        report["total_liabilities_equity"] += report["retained_earnings"]
        
        report["total_assets"] = round(report["total_assets"], 2)
        report["total_liabilities_equity"] = round(report["total_liabilities_equity"], 2)
        
        return report
    except ValueError:
        return {"error": "Invalid date format"}
    except Exception as e:
        return {"error": f"Internal Server Error: {str(e)}"}

# --- General Ledger Routes ---

@app.get("/admin/accounting/general-ledger", response_class=HTMLResponse)
async def general_ledger_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    accounts = db.query(models.Account).all()
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    start_of_month = datetime.datetime.utcnow().replace(day=1).strftime('%Y-%m-%d')
    return templates.TemplateResponse(
        request=request,
        name="general_ledger.html",
        context={
            "settings": settings,
            "accounts": accounts,
            "today": today,
            "start_of_month": start_of_month,
            "active_page": "general_ledger"
        }
    )

@app.post("/api/admin/accounting/get-general-ledger")
async def get_general_ledger(data: dict, db: Session = Depends(get_db)):
    account_id = data.get("account_id")
    from_date_str = data.get("from_date")
    to_date_str = data.get("to_date")
    
    if not from_date_str or not to_date_str:
        return {"error": "Date range is required"}
        
    try:
        from_date = datetime.datetime.strptime(from_date_str, '%Y-%m-%d')
        to_date = datetime.datetime.strptime(to_date_str, '%Y-%m-%d') + datetime.timedelta(days=1)
    except ValueError:
        return {"error": "Invalid date format"}

    if account_id == "All":
        # Global Ledger View: Flat list of all postings in period
        postings = db.query(models.JournalPosting).filter(
            models.JournalPosting.transaction_date >= from_date,
            models.JournalPosting.transaction_date < to_date
        ).order_by(models.JournalPosting.transaction_date.desc()).all()
        
        ledger_data = []
        for p in postings:
            acc = p.account
            creator = p.created_by
            acc_type = acc.type.name if acc.type else (acc.account_type or "-")
            sub_acc_type = acc.sub_type.name if acc.sub_type else "-"
            
            dr = p.amount if p.dr_cr == 'Debit' else 0
            cr = p.amount if p.dr_cr == 'Credit' else 0
            
            ledger_data.append({
                "date": p.transaction_date.strftime('%Y-%m-%d'),
                "account_name": acc.name,
                "account_code": acc.code or "-",
                "account_type_name": acc_type,
                "sub_account_type_name": sub_acc_type,
                "created_by": creator.name if creator else "System",
                "narrative": p.narrative or "",
                "ref": p.ref_no or "",
                "debit": dr,
                "credit": cr,
                "balance": 0 # Running balance is complex for a flat list of all accounts
            })
            
        return {
            "account_name": "All Accounts",
            "account_code": "Consolidated",
            "entries": ledger_data
        }

    # Specific Account View
    account = db.query(models.Account).filter(models.Account.id == int(account_id)).first()
    if not account:
        return {"error": "Account not found"}

    try:
        # Calculate Opening Balance
        acc_type_obj = account.type
        acc_type_name = (acc_type_obj.name if (acc_type_obj and acc_type_obj.name) else (account.account_type or "")).capitalize()
        
        opening_postings = db.query(
            func.sum(models.JournalPosting.amount).label('total_amount'),
            models.JournalPosting.dr_cr
        ).filter(
            models.JournalPosting.account_id == account.id,
            models.JournalPosting.transaction_date < from_date
        ).group_by(models.JournalPosting.dr_cr).all()
        
        dr_before = 0
        cr_before = 0
        for p in opening_postings:
            if p.dr_cr == 'Debit':
                dr_before = p.total_amount or 0
            elif p.dr_cr == 'Credit':
                cr_before = p.total_amount or 0
        
        if acc_type_name in ['Asset', 'Expense']:
            opening_balance = (account.balance or 0) + dr_before - cr_before
        else:
            opening_balance = (account.balance or 0) + cr_before - dr_before
            
        # Transactions in period
        postings = db.query(models.JournalPosting).filter(
            models.JournalPosting.account_id == account.id,
            models.JournalPosting.transaction_date >= from_date,
            models.JournalPosting.transaction_date < to_date
        ).order_by(models.JournalPosting.transaction_date.asc()).all()
        
        ledger_data = []
        running_balance = opening_balance
        
        for p in postings:
            dr = p.amount if p.dr_cr == 'Debit' else 0
            cr = p.amount if p.dr_cr == 'Credit' else 0
            
            if acc_type_name in ['Asset', 'Expense']:
                running_balance += (dr - cr)
            else:
                running_balance += (cr - dr)
                
            creator = p.created_by
            acc_type = account.type.name if account.type else (account.account_type or "-")
            sub_acc_type = account.sub_type.name if account.sub_type else "-"

            ledger_data.append({
                "date": p.transaction_date.strftime('%Y-%m-%d'),
                "account_name": account.name,
                "account_code": account.code or "-",
                "account_type_name": acc_type,
                "sub_account_type_name": sub_acc_type,
                "created_by": creator.name if creator else "System",
                "narrative": p.narrative or "",
                "ref": p.ref_no or "",
                "debit": dr,
                "credit": cr,
                "balance": round(running_balance, 2)
            })
            
        return {
            "account_name": account.name,
            "account_code": account.code or "-",
            "opening_balance": round(opening_balance, 2),
            "entries": ledger_data,
            "closing_balance": round(running_balance, 2)
        }
    except Exception as e:
        return {"error": f"Internal Server Error: {str(e)}"}

# --- VAT Report Routes ---

@app.get("/admin/accounting/vat", response_class=HTMLResponse)
async def vat_report_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    start_of_month = datetime.datetime.utcnow().replace(day=1).strftime('%Y-%m-%d')
    return templates.TemplateResponse(
        request=request,
        name="vat.html",
        context={
            "settings": settings,
            "today": today,
            "start_of_month": start_of_month,
            "active_page": "vat"
        }
    )

@app.post("/api/admin/accounting/get-vat-report")
async def get_vat_report(data: dict, db: Session = Depends(get_db)):
    option = data.get("option", "INPUT") # INPUT or OUTPUT
    from_date_str = data.get("from_date")
    to_date_str = data.get("to_date")
    
    try:
        from_date = datetime.datetime.strptime(from_date_str, '%Y-%m-%d')
        to_date = datetime.datetime.strptime(to_date_str, '%Y-%m-%d') + datetime.timedelta(days=1)
    except ValueError:
        return {"error": "Invalid date format"}

    # Find VAT accounts based on option
    if option == "INPUT":
        vat_accounts = db.query(models.Account).filter(models.Account.name.ilike('%VAT INPUT%')).all()
    else:
        vat_accounts = db.query(models.Account).filter(models.Account.name.ilike('%VAT OUTPUT%')).all()
    
    acc_ids = [acc.id for acc in vat_accounts]
    
    postings = db.query(models.JournalPosting).filter(
        models.JournalPosting.account_id.in_(acc_ids),
        models.JournalPosting.transaction_date >= from_date,
        models.JournalPosting.transaction_date < to_date
    ).all()
    
    entries = []
    total_vat = 0
    total_net = 0
    total_gross = 0
    
    for p in postings:
        vat_amount = p.amount
        # Assuming standard 16% VAT if we can't find the exact net posting easily
        # In a real system, we'd look for the corresponding Income/Expense posting
        net_amount = round(vat_amount / 0.16, 2) if vat_amount > 0 else 0
        gross_amount = round(net_amount + vat_amount, 2)
        
        name = "-"
        if option == "INPUT":
            name = p.supplier.name if p.supplier else (p.narrative or "Supplier")
        else:
            name = p.customer.name if p.customer else (p.narrative or "Customer")
            
        entries.append({
            "name": name,
            "tax_id": "-", # PIN could be added to models later
            "date": p.transaction_date.strftime('%Y-%m-%d'),
            "reference": p.ref_no or p.reference or "-",
            "gross_amount": gross_amount,
            "net_amount": net_amount,
            "vat_amount": vat_amount
        })
        
        total_vat += vat_amount
        total_net += net_amount
        total_gross += gross_amount
            
    return {
        "option": option,
        "entries": entries,
        "total_vat": round(total_vat, 2),
        "total_net": round(total_net, 2),
        "total_gross": round(total_gross, 2)
    }

# --- Customer Statement Routes ---

@app.get("/admin/accounting/customer-statements", response_class=HTMLResponse)
async def customer_statements_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    customers = db.query(models.Customer).all()
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
    start_of_month = datetime.datetime.utcnow().replace(day=1).strftime('%Y-%m-%d')
    
    return templates.TemplateResponse(
        request=request,
        name="customer_statements.html",
        context={
            "settings": settings,
            "customers": customers,
            "stores": stores,
            "today": today,
            "start_of_month": start_of_month,
            "active_page": "customer_statements"
        }
    )

@app.post("/accounting/get_customer_statement")
async def get_customer_statement(
    customer_id: int = Form(...),
    from_date: str = Form(...),
    to_date: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        from_dt = datetime.datetime.strptime(from_date, '%Y-%m-%d')
        to_dt = datetime.datetime.strptime(to_date, '%Y-%m-%d') + datetime.timedelta(days=1)
    except ValueError:
        return {"error": "Invalid date format"}

    # Get opening balance
    opening_postings = db.query(models.JournalPosting).filter(
        models.JournalPosting.customer_id == customer_id,
        models.JournalPosting.transaction_date < from_dt
    ).all()
    
    opening_balance = 0.0
    for p in opening_postings:
        if p.dr_cr == 'Debit':
            opening_balance += p.amount
        else:
            opening_balance -= p.amount
            
    # Get current period postings
    postings = db.query(models.JournalPosting).filter(
        models.JournalPosting.customer_id == customer_id,
        models.JournalPosting.transaction_date >= from_dt,
        models.JournalPosting.transaction_date < to_dt
    ).order_by(models.JournalPosting.transaction_date.asc()).all()
    
    statement_entries = []
    running_balance = opening_balance
    
    # Opening balance entry
    statement_entries.append({
        "date": from_date,
        "reference": "OPENING BALANCE",
        "narrative": "Balance Brought Forward",
        "debit": 0,
        "credit": 0,
        "balance": round(opening_balance, 2)
    })
    
    for p in postings:
        debit = p.amount if p.dr_cr == 'Debit' else 0
        credit = p.amount if p.dr_cr == 'Credit' else 0
        running_balance += (debit - credit)
        
        statement_entries.append({
            "date": p.transaction_date.strftime('%Y-%m-%d'),
            "reference": p.ref_no or p.reference or "-",
            "narrative": p.narrative or "-",
            "debit": debit,
            "credit": credit,
            "balance": round(running_balance, 2)
        })
        
    return {
        "entries": statement_entries,
        "opening_balance": round(opening_balance, 2),
        "closing_balance": round(running_balance, 2)
    }

@app.post("/accounting/get_customer_statement_pdf")
async def get_customer_statement_pdf(
    customer_id: int = Form(...),
    from_date: str = Form(...),
    to_date: str = Form(...),
    db: Session = Depends(get_db)
):
    # Reuse the same logic for now
    return await get_customer_statement(customer_id, from_date, to_date, db)

# Core HR Routes
@app.get("/admin/hr/constants", response_class=HTMLResponse)
async def hr_constants_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="hr_constants.html",
        context={
            "settings": settings,
            "active_page": "hr_constants"
        }
    )

@app.post("/api/admin/hr/get-constants")
async def get_hr_constants(data: dict, db: Session = Depends(get_db)):
    category = data.get("category", "warnings")
    constants = db.query(models.HRConstant).filter(
        models.HRConstant.category == category,
        models.HRConstant.is_active
    ).all()
    
    return [{"id": c.id, "name": c.name, "description": c.description} for c in constants]

@app.post("/api/admin/hr/add-constant")
async def add_hr_constant(data: dict, db: Session = Depends(get_db)):
    category = data.get("category")
    name = data.get("name")
    description = data.get("description")
    
    if not category or not name:
        return {"error": "Category and Name are required"}
        
    new_constant = models.HRConstant(
        category=category,
        name=name,
        description=description
    )
    db.add(new_constant)
    db.commit()
    db.refresh(new_constant)
    
    return {"message": "Saved successfully", "id": new_constant.id}

@app.post("/api/admin/hr/delete-constant")
async def delete_hr_constant(data: dict, db: Session = Depends(get_db)):
    id = data.get("id")
    constant = db.query(models.HRConstant).filter(models.HRConstant.id == id).first()
    if constant:
        constant.is_active = False # Soft delete
        db.commit()
        return {"message": "Deleted successfully"}
    return {"error": "Constant not found"}

# Awards Routes
@app.get("/admin/hr/awards", response_class=HTMLResponse)
async def hr_awards_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    staff = db.query(models.Staff).all()
    award_types = db.query(models.HRConstant).filter(models.HRConstant.category == "awards").all()
    
    return templates.TemplateResponse(
        request=request,
        name="hr_awards.html",
        context={
            "settings": settings,
            "active_page": "hr_awards",
            "staff": staff,
            "award_types": award_types
        }
    )

@app.get("/api/admin/hr/get-awards")
async def get_hr_awards(db: Session = Depends(get_db)):
    awards = db.query(models.HRAward).options(
        joinedload(models.HRAward.staff),
        joinedload(models.HRAward.award_type)
    ).order_by(models.HRAward.award_date.desc()).all()
    
    return [{
        "id": a.id,
        "staff_name": a.staff.name if a.staff else "Unknown",
        "award_title": a.award_type.name if a.award_type else "Unknown",
        "gift": a.gift,
        "cash": a.cash,
        "award_date": a.award_date.strftime("%Y-%m-%d") if a.award_date else "",
        "attachment": a.attachment_path
    } for a in awards]

@app.post("/api/admin/hr/add-award")
async def add_hr_award(
    staff_id: int = Form(...),
    award_type_id: int = Form(...),
    award_date: str = Form(...),
    gift: str = Form(None),
    cash: float = Form(0.0),
    description: str = Form(None),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        # Date conversion
        date_obj = datetime.datetime.strptime(award_date, "%Y-%m-%d").date()
        
        attachment_path = None
        if attachment and attachment.filename:
            # Basic file saving logic
            file_name = f"{datetime.datetime.now().timestamp()}_{attachment.filename}"
            upload_dir = "static/uploads/hr"
            os.makedirs(upload_dir, exist_ok=True)
            attachment_path = f"{upload_dir}/{file_name}"
            with open(attachment_path, "wb") as f:
                f.write(await attachment.read())

        new_award = models.HRAward(
            staff_id=staff_id,
            award_type_id=award_type_id,
            award_date=date_obj,
            gift=gift,
            cash=cash,
            description=description,
            attachment_path=attachment_path
        )
        db.add(new_award)
        db.commit()
        return {"message": "Award saved successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/admin/hr/delete-award")
async def delete_hr_award(data: dict, db: Session = Depends(get_db)):
    id = data.get("id")
    award = db.query(models.HRAward).filter(models.HRAward.id == id).first()
    if award:
        db.delete(award)
        db.commit()
        return {"message": "Deleted successfully"}
    return {"error": "Award not found"}

# Warnings Routes
@app.get("/admin/hr/warnings", response_class=HTMLResponse)
async def hr_warnings_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    staff = db.query(models.Staff).all()
    warning_types = db.query(models.HRConstant).filter(models.HRConstant.category == "warnings").all()
    
    return templates.TemplateResponse(
        request=request,
        name="hr_warnings.html",
        context={
            "settings": settings,
            "active_page": "hr_warnings",
            "staff": staff,
            "warning_types": warning_types
        }
    )

@app.get("/api/admin/hr/get-warnings")
async def get_hr_warnings(db: Session = Depends(get_db)):
    warnings = db.query(models.HRWarning).options(
        joinedload(models.HRWarning.staff),
        joinedload(models.HRWarning.warning_type)
    ).order_by(models.HRWarning.warning_date.desc()).all()
    
    return [{
        "id": w.id,
        "staff_name": w.staff.name if w.staff else "Unknown",
        "warning_title": w.warning_type.name if w.warning_type else "Unknown",
        "warning_date": w.warning_date.strftime("%Y-%m-%d") if w.warning_date else "",
        "attachment": w.attachment_path
    } for w in warnings]

@app.post("/api/admin/hr/add-warning")
async def add_hr_warning(
    staff_id: int = Form(...),
    warning_type_id: int = Form(...),
    warning_date: str = Form(...),
    description: str = Form(None),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        date_obj = datetime.datetime.strptime(warning_date, "%Y-%m-%d").date()
        
        attachment_path = None
        if attachment and attachment.filename:
            file_name = f"{datetime.datetime.now().timestamp()}_{attachment.filename}"
            upload_dir = "static/uploads/hr"
            os.makedirs(upload_dir, exist_ok=True)
            attachment_path = f"{upload_dir}/{file_name}"
            with open(attachment_path, "wb") as f:
                f.write(await attachment.read())

        new_warning = models.HRWarning(
            staff_id=staff_id,
            warning_type_id=warning_type_id,
            warning_date=date_obj,
            description=description,
            attachment_path=attachment_path
        )
        db.add(new_warning)
        db.commit()
        return {"message": "Warning saved successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/admin/hr/delete-warning")
async def delete_hr_warning(data: dict, db: Session = Depends(get_db)):
    id = data.get("id")
    warning = db.query(models.HRWarning).filter(models.HRWarning.id == id).first()
    if warning:
        db.delete(warning)
        db.commit()
        return {"message": "Deleted successfully"}
    return {"error": "Warning not found"}

# Resignations Routes
@app.get("/admin/hr/resignations", response_class=HTMLResponse)
async def hr_resignations_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    staff = db.query(models.Staff).all()
    
    return templates.TemplateResponse(
        request=request,
        name="hr_resignations.html",
        context={
            "settings": settings,
            "active_page": "hr_resignations",
            "staff": staff
        }
    )

@app.get("/api/admin/hr/get-resignations")
async def get_hr_resignations(db: Session = Depends(get_db)):
    resignations = db.query(models.HRResignation).options(
        joinedload(models.HRResignation.staff)
    ).order_by(models.HRResignation.resignation_date.desc()).all()
    
    return [{
        "id": r.id,
        "staff_name": r.staff.name if r.staff else "Unknown",
        "notice_date": r.notice_date.strftime("%Y-%m-%d") if r.notice_date else "",
        "resignation_date": r.resignation_date.strftime("%Y-%m-%d") if r.resignation_date else "",
        "attachment": r.attachment_path
    } for r in resignations]

@app.post("/api/admin/hr/add-resignation")
async def add_hr_resignation(
    staff_id: int = Form(...),
    notice_date: str = Form(...),
    resignation_date: str = Form(...),
    description: str = Form(None),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        n_date = datetime.datetime.strptime(notice_date, "%Y-%m-%d").date()
        r_date = datetime.datetime.strptime(resignation_date, "%Y-%m-%d").date()
        
        attachment_path = None
        if attachment and attachment.filename:
            file_name = f"{datetime.datetime.now().timestamp()}_{attachment.filename}"
            upload_dir = "static/uploads/hr"
            os.makedirs(upload_dir, exist_ok=True)
            attachment_path = f"{upload_dir}/{file_name}"
            with open(attachment_path, "wb") as f:
                f.write(await attachment.read())

        new_resignation = models.HRResignation(
            staff_id=staff_id,
            notice_date=n_date,
            resignation_date=r_date,
            description=description,
            attachment_path=attachment_path
        )
        db.add(new_resignation)
        db.commit()
        return {"message": "Resignation saved successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/admin/hr/delete-resignation")
async def delete_hr_resignation(data: dict, db: Session = Depends(get_db)):
    id = data.get("id")
    res = db.query(models.HRResignation).filter(models.HRResignation.id == id).first()
    if res:
        db.delete(res)
        db.commit()
        return {"message": "Deleted successfully"}
    return {"error": "Resignation not found"}

# Terminations Routes
@app.get("/admin/hr/terminations", response_class=HTMLResponse)
async def hr_terminations_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    staff = db.query(models.Staff).all()
    termination_types = db.query(models.HRConstant).filter(models.HRConstant.category == "terminations").all()
    
    return templates.TemplateResponse(
        request=request,
        name="hr_terminations.html",
        context={
            "settings": settings,
            "active_page": "hr_terminations",
            "staff": staff,
            "termination_types": termination_types
        }
    )

@app.get("/api/admin/hr/get-terminations")
async def get_hr_terminations(db: Session = Depends(get_db)):
    terminations = db.query(models.HRTermination).options(
        joinedload(models.HRTermination.staff),
        joinedload(models.HRTermination.termination_type)
    ).order_by(models.HRTermination.termination_date.desc()).all()
    
    return [{
        "id": t.id,
        "staff_name": t.staff.name if t.staff else "Unknown",
        "termination_title": t.termination_type.name if t.termination_type else "Unknown",
        "notice_date": t.notice_date.strftime("%Y-%m-%d") if t.notice_date else "",
        "termination_date": t.termination_date.strftime("%Y-%m-%d") if t.termination_date else "",
        "attachment": t.attachment_path
    } for t in terminations]

@app.post("/api/admin/hr/add-termination")
async def add_hr_termination(
    staff_id: int = Form(...),
    termination_type_id: int = Form(...),
    notice_date: str = Form(...),
    termination_date: str = Form(...),
    description: str = Form(None),
    attachment: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    try:
        n_date = datetime.datetime.strptime(notice_date, "%Y-%m-%d").date()
        t_date = datetime.datetime.strptime(termination_date, "%Y-%m-%d").date()
        
        attachment_path = None
        if attachment and attachment.filename:
            file_name = f"{datetime.datetime.now().timestamp()}_{attachment.filename}"
            upload_dir = "static/uploads/hr"
            os.makedirs(upload_dir, exist_ok=True)
            attachment_path = f"{upload_dir}/{file_name}"
            with open(attachment_path, "wb") as f:
                f.write(await attachment.read())

        new_termination = models.HRTermination(
            staff_id=staff_id,
            termination_type_id=termination_type_id,
            notice_date=n_date,
            termination_date=t_date,
            description=description,
            attachment_path=attachment_path
        )
        db.add(new_termination)
        db.commit()
        return {"message": "Termination saved successfully"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/admin/hr/delete-termination")
async def delete_hr_termination(data: dict, db: Session = Depends(get_db)):
    id = data.get("id")
    term = db.query(models.HRTermination).filter(models.HRTermination.id == id).first()
    if term:
        db.delete(term)
        db.commit()
        return {"message": "Deleted successfully"}
    return {"error": "Termination not found"}

# Performance Constants Routes
@app.get("/admin/performance/constants", response_class=HTMLResponse)
async def perf_constants_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="perf_constants.html",
        context={
            "settings": settings,
            "active_page": "perf_constants"
        }
    )

@app.post("/api/admin/performance/get-constant")
async def get_perf_constant_view(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    category = form_data.get("data")
    
    html = ""
    if category == "collections":
        items = db.query(models.PerfConstant).filter(models.PerfConstant.category == "collections").all()
        rows_list = []
        for i in items:
            onclick_action = f"delete_constant('collections', {i.id})"
            rows_list.append(f'<tr><td>{i.name}</td><td><button class="btn btn-xs btn-rgd" onclick="{onclick_action}">Delete <i class="fa fa-trash"></i></button></td></tr>')
        rows_html = "".join(rows_list) if items else '<tr><td colspan="2" class="text-center">No collections found</td></tr>'
        html = f"""
        <div class="row">
            <div class="col-md-5 pr-4">
                <div class="card">
                    <div class="card-body">
                        <form id="performance_form" onsubmit="event.preventDefault(); save_perf_constant('collections');">
                            <input type="hidden" name="category" value="collections" />
                            <h5><b>Add New Index Collection</b></h5><hr>
                            <div class="form-group">
                                <label>Collection Name</label>
                                <input type="text" name="name" required class="form-control" placeholder="e.g. Behavioral, Technical" />
                            </div>
                            <button type="submit" id="submit" class="btn btn-primary">Save</button>
                        </form>
                    </div>
                </div>
            </div>
            <div class="col-md-7">
                <div class="card">
                    <div class="card-body">
                        <h5><b>Index Collection List</b></h5><hr>
                        <table class="table table-sm table-bordered table-striped">
                            <thead><tr><th>Collection Name</th><th>Action</th></tr></thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        """
    elif category == "indexes":
        collections = db.query(models.PerfConstant).filter(models.PerfConstant.category == "collections").all()
        items = db.query(models.PerfConstant).filter(models.PerfConstant.category == "indexes").all()
        coll_options = "".join([f'<option value="{c.id}">{c.name}</option>' for c in collections])
        rows_list = []
        for i in items:
            onclick_action = f"delete_constant('indexes', {i.id})"
            rows_list.append(f'<tr><td>{i.name}</td><td>{i.collection.name if i.collection else "N/A"}</td><td>{i.weight}%</td><td><button class="btn btn-xs btn-rgd" onclick="{onclick_action}">Delete <i class="fa fa-trash"></i></button></td></tr>')
        rows_html = "".join(rows_list) if items else '<tr><td colspan="4" class="text-center">No indexes found</td></tr>'
        html = f"""
        <div class="row">
            <div class="col-md-5 pr-4">
                <div class="card">
                    <div class="card-body">
                        <form id="performance_form" onsubmit="event.preventDefault(); save_perf_constant('indexes');">
                            <input type="hidden" name="category" value="indexes" />
                            <h5><b>Add Performance Index</b></h5><hr>
                            <div class="form-group">
                                <label>Collection</label>
                                <select name="collection_id" class="form-control select2" required>
                                    <option value="">~Select Collection~</option>
                                    {coll_options}
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Index Name</label>
                                <input type="text" name="name" required class="form-control" />
                            </div>
                            <div class="form-group">
                                <label>Weightage (%)</label>
                                <input type="number" step="0.01" name="weight" required class="form-control" />
                            </div>
                            <button type="submit" id="submit" class="btn btn-primary">Save</button>
                        </form>
                    </div>
                </div>
            </div>
            <div class="col-md-7">
                <div class="card">
                    <div class="card-body">
                        <h5><b>Performance Indexes</b></h5><hr>
                        <table class="table table-sm table-bordered table-striped">
                            <thead><tr><th>Index</th><th>Collection</th><th>Weight</th><th>Action</th></tr></thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        """
    elif category == "matrix":
        collections = db.query(models.PerfConstant).filter(models.PerfConstant.category == "collections").all()
        items = db.query(models.PerfConstant).filter(models.PerfConstant.category == "matrix").all()
        coll_options = "".join([f'<option value="{c.id}">{c.name}</option>' for c in collections])
        rows_list = []
        for i in items:
            onclick_action = f"delete_constant('matrix', {i.id})"
            rows_list.append(f'<tr><td>{i.name}</td><td>{i.collection.name if i.collection else "N/A"}</td><td>{i.score}</td><td><button class="btn btn-xs btn-rgd" onclick="{onclick_action}">Delete <i class="fa fa-trash"></i></button></td></tr>')
        rows_html = "".join(rows_list) if items else '<tr><td colspan="4" class="text-center">No matrix entries found</td></tr>'
        html = f"""
        <div class="row">
            <div class="col-md-5 pr-4">
                <div class="card">
                    <div class="card-body">
                        <form id="performance_form" onsubmit="event.preventDefault(); save_perf_constant('matrix');">
                            <input type="hidden" name="category" value="matrix" />
                            <h5><b>Add Appraisal Matrix</b></h5><hr>
                            <div class="form-group">
                                <label>Collection</label>
                                <select name="collection_id" class="form-control select2" required>
                                    <option value="">~Select Collection~</option>
                                    {coll_options}
                                </select>
                            </div>
                            <div class="form-group">
                                <label>Rating Title</label>
                                <input type="text" name="name" required class="form-control" placeholder="e.g. Excellent, Good" />
                            </div>
                            <div class="form-group">
                                <label>Score</label>
                                <input type="number" step="0.01" name="score" required class="form-control" />
                            </div>
                            <button type="submit" id="submit" class="btn btn-primary">Save</button>
                        </form>
                    </div>
                </div>
            </div>
            <div class="col-md-7">
                <div class="card">
                    <div class="card-body">
                        <h5><b>Appraisal Matrix</b></h5><hr>
                        <table class="table table-sm table-bordered table-striped">
                            <thead><tr><th>Rating</th><th>Collection</th><th>Score</th><th>Action</th></tr></thead>
                            <tbody>
                                {rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        """
    return HTMLResponse(content=html)

@app.post("/api/admin/performance/add-constant")
async def add_perf_constant(
    category: str = Form(...),
    name: str = Form(...),
    collection_id: int = Form(None),
    weight: float = Form(0.0),
    score: float = Form(0.0),
    db: Session = Depends(get_db)
):
    try:
        new_const = models.PerfConstant(
            category=category,
            name=name,
            collection_id=collection_id,
            weight=weight,
            score=score
        )
        db.add(new_const)
        db.commit()
        return {"resp": "1", "message": "Saved successfully"}
    except Exception as e:
        return {"resp": "0", "message": str(e)}

@app.post("/api/admin/performance/delete-constant")
async def delete_perf_constant(
    category: str = Form(...),
    id: int = Form(...),
    db: Session = Depends(get_db)
):
    const = db.query(models.PerfConstant).filter(models.PerfConstant.id == id).first()
    if const:
        db.delete(const)
        db.commit()
        return {"resp": "1", "message": "Deleted successfully"}
    return {"resp": "0", "message": "Record not found"}

@app.get("/admin/performance/appraisal", response_class=HTMLResponse)
async def appraisal_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    employees = db.query(models.Staff).filter(models.Staff.is_active).all()
    designations = db.query(models.HRConstant).filter(models.HRConstant.category == "designations").all()
    
    now = datetime.datetime.now()
    current_month = now.month
    current_year = now.year
    
    months = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE', 'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER', 'DECEMBER']
    
    return templates.TemplateResponse(
        request=request,
        name="appraisal.html",
        context={
            "settings": settings,
            "employees": employees,
            "designations": designations,
            "current_month": current_month,
            "current_year": current_year,
            "months": months,
            "active_page": "perf_appraisal"
        }
    )

@app.post("/api/admin/performance/get-matrix")
async def get_performance_matrix(employee_id: int = Form(...), db: Session = Depends(get_db)):
    # In a real app, you'd link employee -> designation -> collection
    # For now, let's fetch all indexes grouped by collection
    collections = db.query(models.PerfConstant).filter(models.PerfConstant.category == "collections").all()
    matrix_options = db.query(models.PerfConstant).filter(models.PerfConstant.category == "matrix").all()
    
    html = ""
    for coll in collections:
        indexes = db.query(models.PerfConstant).filter(models.PerfConstant.category == "indexes", models.PerfConstant.collection_id == coll.id).all()
        if not indexes: continue
        
        html += f'<div class="card card-outline card-secondary mt-2"><div class="card-header"><h3 class="card-title">{coll.name}</h3></div><div class="card-body">'
        html += '<table class="table table-sm table-bordered"><thead><tr><th>Performance Index</th><th>Weight (%)</th><th>Rating/Score</th></tr></thead><tbody>'
        
        for idx in indexes:
            options_html = '<option value="0">~Select Rating~</option>'
            for m in matrix_options:
                if m.collection_id == coll.id:
                    options_html += f'<option value="{m.score}">{m.name} ({m.score})</option>'
            
            html += f"""
            <tr>
                <td>{idx.name}</td>
                <td>{idx.weight}%</td>
                <td>
                    <select name="score_{idx.id}" class="form-control select2" required>
                        {options_html}
                    </select>
                </td>
            </tr>
            """
        html += '</tbody></table></div></div>'
    
    if not html:
        html = '<div class="alert alert-warning">No performance collections or indexes found. Please configure them in Performance Constants.</div>'
        
    return HTMLResponse(content=html)

@app.post("/api/admin/performance/add-appraisal")
async def add_appraisal(
    request: Request,
    employee_id: int = Form(...),
    month: int = Form(...),
    year: int = Form(...),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        form_data = await request.form()
        # Find all score_ fields
        total_score = 0.0
        scores_to_add = []
        
        for key, value in form_data.items():
            if key.startswith("score_"):
                index_id = int(key.replace("score_", ""))
                score_val = float(value)
                total_score += score_val
                scores_to_add.append(models.AppraisalScore(index_id=index_id, score=score_val))
        
        new_appraisal = models.PerformanceAppraisal(
            employee_id=employee_id,
            month=month,
            year=year,
            narrative=narrative,
            total_score=total_score,
            appraised_by_id=1 # Default to first admin for now or current user if available
        )
        db.add(new_appraisal)
        db.flush() # Get ID
        
        for s in scores_to_add:
            s.appraisal_id = new_appraisal.id
            db.add(s)
            
        db.commit()
        return {"resp": "1", "message": "Appraisal submitted successfully"}
    except Exception as e:
        db.rollback()
        return {"resp": "0", "message": str(e)}

@app.post("/api/admin/performance/get-appraisals")
async def get_appraisals(
    designation: str = Form(None),
    month: str = Form(None),
    year: int = Form(None),
    db: Session = Depends(get_db)
):
    query = db.query(models.PerformanceAppraisal)
    
    if month and month != "ALL":
        query = query.filter(models.PerformanceAppraisal.month == int(month))
    if year:
        query = query.filter(models.PerformanceAppraisal.year == year)
        
    appraisals = query.order_by(models.PerformanceAppraisal.created_at.desc()).all()
    
    results = []
    months = ['', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
    
    for a in appraisals:
        # Filter by designation if needed
        if designation and designation != "ALL":
            if not a.employee.designation_id or a.employee.designation_id != int(designation):
                continue
                
        results.append({
            "id": a.id,
            "employee_name": a.employee.name,
            "designation": a.employee.designation.name if a.employee.designation else "N/A",
            "period": f"{months[a.month]} {a.year}",
            "total_score": round(a.total_score, 2),
            "appraiser_name": a.appraiser.name if a.appraiser else "System",
            "date": a.created_at.strftime("%Y-%m-%d %H:%M")
        })
        
    return results

@app.post("/api/admin/performance/view-appraisal")
async def view_appraisal(id: int = Form(...), db: Session = Depends(get_db)):
    a = db.query(models.PerformanceAppraisal).filter(models.PerformanceAppraisal.id == id).first()
    if not a:
        return HTMLResponse("Appraisal not found")
        
    html = f"""
    <div class="row">
        <div class="col-6">
            <p><b>Employee:</b> {a.employee.name}</p>
            <p><b>Designation:</b> {a.employee.designation.name if a.employee.designation else "N/A"}</p>
            <p><b>Period:</b> {a.month}/{a.year}</p>
        </div>
        <div class="col-6 text-right">
            <h3>Score: {round(a.total_score, 2)}</h3>
            <p><b>Appraised By:</b> {a.appraiser.name if a.appraiser else "System"}</p>
            <p><b>Date:</b> {a.created_at.strftime("%Y-%m-%d %H:%M")}</p>
        </div>
        <div class="col-12"><hr>
            <h5>Evaluation Details</h5>
            <table class="table table-sm table-bordered">
                <thead><tr><th>Index</th><th>Score</th></tr></thead>
                <tbody>
    """
    for s in a.scores:
        html += f"<tr><td>{s.index.name}</td><td>{s.score}</td></tr>"
        
    html += f"""
                </tbody>
            </table>
            <p><b>Narrative:</b><br>{a.narrative if a.narrative else "No notes provided."}</p>
        </div>
    </div>
    """
    return HTMLResponse(content=html)

@app.post("/api/admin/performance/delete-appraisal")
async def delete_appraisal(id: int = Form(...), db: Session = Depends(get_db)):
    a = db.query(models.PerformanceAppraisal).filter(models.PerformanceAppraisal.id == id).first()
    if a:
        db.delete(a)
        db.commit()
        return {"resp": "1", "message": "Appraisal deleted successfully"}
    return {"resp": "0", "message": "Appraisal not found"}

# --- PAYROLL ROUTES ---

@app.get("/admin/payroll/allowance-types", response_class=HTMLResponse)
async def payroll_allowances_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="payroll_allowances.html",
        context={"settings": settings, "active_page": "payroll_allowances"}
    )

@app.get("/api/admin/payroll/get-allowances")
async def get_payroll_allowances(db: Session = Depends(get_db)):
    allowances = db.query(models.PayrollConstant).filter(models.PayrollConstant.category == "allowances").order_by(models.PayrollConstant.created_at.desc()).all()
    return [{
        "id": a.id,
        "name": a.name,
        "is_taxable": a.is_taxable,
        "is_active": a.is_active,
        "narrative": a.narrative,
        "timestamp": a.created_at.strftime("%Y-%m-%d %H:%M:%S")
    } for a in allowances]

@app.post("/api/admin/payroll/add-allowance")
async def add_payroll_allowance(
    name: str = Form(...),
    is_taxable: int = Form(1),
    is_active: int = Form(0),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        new_allowance = models.PayrollConstant(
            category="allowances",
            name=name,
            is_taxable=bool(is_taxable),
            is_active=bool(is_active),
            narrative=narrative
        )
        db.add(new_allowance)
        db.commit()
        return {"resp": "1", "message": "Allowance type added successfully"}
    except Exception as e:
        db.rollback()
        return {"resp": "0", "message": str(e)}

@app.post("/api/admin/payroll/update-allowance")
async def update_payroll_allowance(
    id: int = Form(...),
    name: str = Form(...),
    is_taxable: int = Form(...),
    is_active: int = Form(0),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    allowance = db.query(models.PayrollConstant).filter(models.PayrollConstant.id == id).first()
    if not allowance:
        return {"resp": "0", "message": "Record not found"}
    
    try:
        allowance.name = name
        allowance.is_taxable = bool(is_taxable)
        allowance.is_active = bool(is_active)
        allowance.narrative = narrative
        db.commit()
        return {"resp": "1", "message": "Allowance type updated successfully"}
    except Exception as e:
        db.rollback()
        return {"resp": "0", "message": str(e)}

@app.post("/api/admin/payroll/delete-allowance")
async def delete_payroll_allowance(id: int = Form(...), db: Session = Depends(get_db)):
    allowance = db.query(models.PayrollConstant).filter(models.PayrollConstant.id == id).first()
    if allowance:
        db.delete(allowance)
        db.commit()
        return {"resp": "1", "message": "Deleted successfully"}
    return {"resp": "0", "message": "Record not found"}

@app.get("/admin/payroll/generate", response_class=HTMLResponse)
async def payroll_generate_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    fiscal_years = db.query(models.FiscalYear).all()
    return templates.TemplateResponse(
        request=request,
        name="payroll_generate.html",
        context={
            "settings": settings, 
            "active_page": "payroll_generate",
            "stores": stores,
            "fiscal_years": fiscal_years
        }
    )

@app.get("/api/admin/payroll/get-store-staff/{store_id}")
async def get_store_staff(store_id: int, db: Session = Depends(get_db)):
    staff = db.query(models.Staff).filter(models.Staff.is_active).all() # Filtering by store if needed
    return [{"id": s.id, "name": s.name} for s in staff]

@app.get("/api/admin/payroll/get-records")
async def get_payroll_records(
    store_id: int = None,
    fiscal_year_id: int = None,
    month: int = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.PayrollRecord).filter(models.PayrollRecord.is_active)
    if store_id:
        query = query.filter(models.PayrollRecord.store_id == store_id)
    if fiscal_year_id:
        query = query.filter(models.PayrollRecord.fiscal_year_id == fiscal_year_id)
    if month:
        query = query.filter(models.PayrollRecord.month == month)
    
    records = query.order_by(models.PayrollRecord.id.desc()).all()
    
    months = ["", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
    month_name = months[month] if month and month < len(months) else "N/A"
    year_name = db.query(models.FiscalYear).filter(models.FiscalYear.id == fiscal_year_id).first().year if fiscal_year_id else "N/A"

    return {
        "month_name": month_name,
        "year": year_name,
        "records": [{
            "id": r.id,
            "staff_name": r.employee.name,
            "store_name": r.store.name,
            "basic_salary": r.basic_salary,
            "allowances": r.allowances,
            "gross_salary": r.gross_salary,
            "nssf": r.nssf,
            "sha": r.sha,
            "housing_levy": r.housing_levy,
            "paye": r.paye,
            "other_deductions": r.other_deductions,
            "net_salary": r.net_salary,
            "status": r.status
        } for r in records]
    }

@app.post("/api/admin/payroll/generate")
async def generate_payroll(
    store_id: int = Form(...),
    fiscal_year_id: int = Form(...),
    month: int = Form(...),
    employee_ids: list = Form(...),
    db: Session = Depends(get_db)
):
    # If "all" is in employee_ids, fetch all active staff for that store
    if "all" in employee_ids:
        staff_list = db.query(models.Staff).filter(models.Staff.is_active).all()
    else:
        staff_list = db.query(models.Staff).filter(models.Staff.id.in_(employee_ids)).all()

    if not staff_list:
        return {"resp": "0", "message": "No staff selected to process."}

    try:
        # Delete existing records for same month/year/staff to prevent duplicates
        for s in staff_list:
            db.query(models.PayrollRecord).filter(
                models.PayrollRecord.employee_id == s.id,
                models.PayrollRecord.fiscal_year_id == fiscal_year_id,
                models.PayrollRecord.month == month
            ).delete()

        for s in staff_list:
            # Simple Payroll Calculation Logic
            basic = s.basic_salary or 0.0
            
            # Fetch active allowances
            allowance_total = 0.0 # Placeholder for actual allowance logic
            
            # Check for disbursed advances in this month that haven't been recovered
            advances = db.query(models.SalaryAdvance).filter(
                models.SalaryAdvance.employee_id == s.id,
                models.SalaryAdvance.fiscal_year_id == fiscal_year_id,
                models.SalaryAdvance.month == month,
                models.SalaryAdvance.is_disbursed,
                not models.SalaryAdvance.is_recovered
            ).all()
            
            advance_deduction = sum([a.amount for a in advances])
            
            gross = basic + allowance_total
            
            # Kenyan Statutory Deductions (Approximate for 2024-2026)
            nssf = min(basic * 0.06, 1080) # Tier 1 & 2 combined approx
            sha = gross * 0.0275 # 2.75%
            housing_levy = gross * 0.015 # 1.5%
            
            # PAYE (Graduated scale - simplified for now)
            taxable = gross - nssf
            paye = 0.0
            if taxable > 24000:
                paye = (taxable - 24000) * 0.10 # Very simplified 10% above threshold
            
            other_deductions = advance_deduction
            
            net = gross - (nssf + sha + housing_levy + paye + other_deductions)
            
            # Mark advances as recovered
            for a in advances:
                a.is_recovered = True

            new_record = models.PayrollRecord(
                employee_id=s.id,
                store_id=store_id,
                fiscal_year_id=fiscal_year_id,
                month=month,
                basic_salary=basic,
                allowances=allowance_total,
                gross_salary=gross,
                nssf=nssf,
                sha=sha,
                housing_levy=housing_levy,
                paye=paye,
                other_deductions=other_deductions,
                net_salary=net,
                status="Pending"
            )
            db.add(new_record)
        
        db.commit()
        return {"resp": "1", "message": f"Payroll generated successfully for {len(staff_list)} employees."}
    except Exception as e:
        db.rollback()
        return {"resp": "0", "message": str(e)}

@app.post("/api/admin/payroll/delete-batch")
async def delete_payroll_batch(
    store_id: int = Form(None),
    fiscal_year_id: int = Form(None),
    month: int = Form(None),
    db: Session = Depends(get_db)
):
    query = db.query(models.PayrollRecord)
    if store_id:
        query = query.filter(models.PayrollRecord.store_id == store_id)
    if fiscal_year_id:
        query = query.filter(models.PayrollRecord.fiscal_year_id == fiscal_year_id)
    if month:
        query = query.filter(models.PayrollRecord.month == month)
    
    deleted_count = query.delete(synchronize_session=False)
    db.commit()
    return {"resp": "1", "message": f"Deleted {deleted_count} payroll records successfully."}

@app.get("/admin/payroll/advances", response_class=HTMLResponse)
async def payroll_advances_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    fiscal_years = db.query(models.FiscalYear).all()
    return templates.TemplateResponse(
        request=request,
        name="payroll_advances.html",
        context={"settings": settings, "active_page": "payroll_advances", "stores": stores, "fiscal_years": fiscal_years}
    )

@app.post("/api/admin/payroll/save-advance")
async def save_payroll_advance(
    employee_id: int = Form(...),
    fiscal_year_id: int = Form(...),
    month: int = Form(...),
    amount: float = Form(...),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        new_advance = models.SalaryAdvance(
            employee_id=employee_id,
            fiscal_year_id=fiscal_year_id,
            month=month,
            amount=amount,
            narrative=narrative
        )
        db.add(new_advance)
        db.commit()
        return {"resp": "1", "message": "Salary advance recorded successfully."}
    except Exception as e:
        return {"resp": "0", "message": str(e)}

@app.get("/api/admin/payroll/get-advances")
async def get_payroll_advances(db: Session = Depends(get_db)):
    advances = db.query(models.SalaryAdvance).order_by(models.SalaryAdvance.id.desc()).all()
    months = ["", "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
    return [{
        "id": a.id,
        "staff_name": a.employee.name,
        "amount": a.amount,
        "month_name": months[a.month],
        "year": a.fiscal_year.year,
        "is_disbursed": a.is_disbursed,
        "is_recovered": a.is_recovered,
        "narrative": a.narrative,
        "created_at": a.created_at.strftime('%Y-%m-%d %H:%M')
    } for a in advances]

@app.post("/api/admin/payroll/disburse-advance/{id}")
async def disburse_advance(id: int, db: Session = Depends(get_db)):
    advance = db.query(models.SalaryAdvance).filter(models.SalaryAdvance.id == id).first()
    if advance:
        advance.is_disbursed = True
        db.commit()
        return {"resp": "1", "message": "Disbursement marked."}
    return {"resp": "0", "message": "Record not found."}

@app.post("/api/admin/payroll/delete-advance/{id}")
async def delete_advance(id: int, db: Session = Depends(get_db)):
    advance = db.query(models.SalaryAdvance).filter(models.SalaryAdvance.id == id).first()
    if advance:
        db.delete(advance)
        db.commit()
        return {"resp": "1", "message": "Deleted successfully."}
    return {"resp": "0", "message": "Record not found."}

@app.get("/admin/payroll/p9", response_class=HTMLResponse)
async def payroll_p9_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    staff = db.query(models.Staff).filter(models.Staff.is_active).all()
    fiscal_years = db.query(models.FiscalYear).all()
    return templates.TemplateResponse(
        request=request,
        name="payroll_p9.html",
        context={"settings": settings, "active_page": "payroll_p9", "staff": staff, "fiscal_years": fiscal_years, "now": datetime.datetime.now()}
    )

@app.get("/api/admin/payroll/generate-p9")
async def generate_p9_data(employee_id: int, fiscal_year_id: int, db: Session = Depends(get_db)):
    employee = db.query(models.Staff).filter(models.Staff.id == employee_id).first()
    year_obj = db.query(models.FiscalYear).filter(models.FiscalYear.id == fiscal_year_id).first()
    
    payroll_records = db.query(models.PayrollRecord).filter(
        models.PayrollRecord.employee_id == employee_id,
        models.PayrollRecord.fiscal_year_id == fiscal_year_id
    ).all()
    
    records_dict = {}
    for r in payroll_records:
        records_dict[r.month] = {
            "basic": r.basic_salary,
            "benefits": 0,
            "quarters": 0,
            "total_cash": r.gross_salary,
            "nssf": r.nssf,
            "interest": 0,
            "contrib": 0,
            "chargeable": r.gross_salary - r.nssf,
            "tax_charged": r.paye + 2400, # Approximate personal relief included
            "personal_relief": 2400,
            "ins_relief": 0,
            "paye": r.paye
        }
        
    return {
        "employee": {"name": employee.name, "pin": employee.id_number},
        "year": year_obj.year,
        "records": records_dict
    }

@app.get("/admin/payroll/deduction-types", response_class=HTMLResponse)
async def payroll_deductions_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    
    # Liability accounts (for Payable)
    liability_accounts = db.query(models.Account).join(models.AccountType, models.Account.account_type_id == models.AccountType.id)\
        .filter(models.AccountType.name == "Liability").all()
    
    # Expense accounts
    expense_accounts = db.query(models.Account).join(models.AccountType, models.Account.account_type_id == models.AccountType.id)\
        .filter(models.AccountType.name == "Expense").all()
        
    return templates.TemplateResponse(
        request=request,
        name="payroll_deductions.html",
        context={
            "settings": settings, 
            "active_page": "payroll_deductions",
            "liability_accounts": liability_accounts,
            "expense_accounts": expense_accounts
        }
    )

@app.get("/api/admin/payroll/get-deductions")
async def get_payroll_deductions(db: Session = Depends(get_db)):
    deductions = db.query(models.PayrollConstant).filter(models.PayrollConstant.category == "deductions").order_by(models.PayrollConstant.created_at.desc()).all()
    return [{
        "id": d.id,
        "name": d.name,
        "is_active": d.is_active,
        "narrative": d.narrative,
        "payable_account_id": d.payable_account_id,
        "expense_account_id": d.expense_account_id,
        "payable_account": d.payable_account.name if d.payable_account else "N/A",
        "expense_account": d.expense_account.name if d.expense_account else "N/A",
        "timestamp": d.created_at.strftime("%Y-%m-%d %H:%M:%S")
    } for d in deductions]

@app.post("/api/admin/payroll/add-deduction")
async def add_payroll_deduction(
    name: str = Form(...),
    payable_account_id: int = Form(...),
    expense_account_id: int = Form(...),
    is_active: int = Form(0),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        new_deduction = models.PayrollConstant(
            category="deductions",
            name=name,
            payable_account_id=payable_account_id,
            expense_account_id=expense_account_id,
            is_active=bool(is_active),
            narrative=narrative
        )
        db.add(new_deduction)
        db.commit()
        return {"resp": "1", "message": "Deduction type added successfully"}
    except Exception as e:
        db.rollback()
        return {"resp": "0", "message": str(e)}

@app.post("/api/admin/payroll/update-deduction")
async def update_payroll_deduction(
    id: int = Form(...),
    name: str = Form(...),
    payable_account_id: int = Form(...),
    expense_account_id: int = Form(...),
    is_active: int = Form(0),
    narrative: str = Form(None),
    db: Session = Depends(get_db)
):
    deduction = db.query(models.PayrollConstant).filter(models.PayrollConstant.id == id).first()
    if not deduction:
        return {"resp": "0", "message": "Record not found"}
    
    try:
        deduction.name = name
        deduction.payable_account_id = payable_account_id
        deduction.expense_account_id = expense_account_id
        deduction.is_active = bool(is_active)
        deduction.narrative = narrative
        db.commit()
        return {"resp": "1", "message": "Deduction type updated successfully"}
    except Exception as e:
        db.rollback()
        return {"resp": "0", "message": str(e)}

@app.post("/api/admin/payroll/delete-deduction")
async def delete_payroll_deduction(id: int = Form(...), db: Session = Depends(get_db)):
    deduction = db.query(models.PayrollConstant).filter(models.PayrollConstant.id == id).first()
    if deduction:
        db.delete(deduction)
        db.commit()
        return {"resp": "1", "message": "Deleted successfully"}
    return {"resp": "0", "message": "Record not found"}

@app.post("/admin/accounting/delete_account/{acc_id}")
async def delete_account(acc_id: int, db: Session = Depends(get_db)):
    acc = db.query(models.Account).filter(models.Account.id == acc_id).first()
    if acc:
        db.delete(acc)
        db.commit()
        return {"resp": "1", "message": "Account deleted successfully"}
    return {"resp": "0", "message": "Account not found"}

@app.get("/admin/sales", response_class=HTMLResponse)
async def sales_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    stores = db.query(models.Store).all()
    today = datetime.datetime.utcnow().date()
    return templates.TemplateResponse(
        request=request,
        name="sales_list.html",
        context={
            "settings": settings,
            "stores": stores,
            "today": today.isoformat(),
            "active_page": "sales_list"
        }
    )

@app.get("/admin/all-sales-data")
async def all_sales_data(
    request: Request,
    draw: int = Query(...),
    start: int = Query(...),
    length: int = Query(...),
    org_id: str = Query(None),
    due: str = Query(None),
    from_date: str = Query(None),
    to_date: str = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(models.Order).filter(models.Order.status != 'voided')
    
    # Filters
    if org_id and org_id != 'All':
        query = query.filter(models.Order.store_id == int(org_id))
    
    if from_date:
        d = datetime.datetime.strptime(from_date, '%Y-%m-%d')
        query = query.filter(models.Order.created_at >= d)
    if to_date:
        d = datetime.datetime.strptime(to_date, '%Y-%m-%d') + datetime.timedelta(days=1)
        query = query.filter(models.Order.created_at < d)

    total_records = query.count()
    orders = query.order_by(models.Order.created_at.desc()).offset(start).limit(length).all()
    
    data = []
    for i, order in enumerate(orders):
        data.append({
            "serial": start + i + 1,
            "bill_no": f"ORD-{order.id:04d}",
            "customer": order.customer.name if order.customer else "Walk-in",
            "sales_point": "POS",
            "created_at": order.created_at.strftime('%Y-%m-%d %H:%M'),
            "attendant": order.waiter.name if order.waiter else "Admin",
            "net_amount": f"{order.total_amount:,.2f}",
            "balance": "0.00" if order.status == 'paid' else f"{order.total_amount:,.2f}",
            "discount": "0.00",
            "store": order.store.name if order.store else "Main Store",
            "stamp": '<span class="badge badge-success">Stamped</span>' if getattr(order, 'is_stamped', False) else '<span class="badge badge-secondary">Pending</span>',
            "actions": f"""
                <button class="btn btn-xs btn-info" onclick="view_sale({order.id})"><i class="fa fa-eye"></i></button>
                <button class="btn btn-xs btn-danger" onclick="void_sale({order.id})"><i class="fa fa-trash"></i></button>
                <button class="btn btn-xs btn-warning" onclick="complement_sale({order.id})"><i class="fa fa-gift"></i></button>
                <button class="btn btn-xs btn-dark" onclick="extend_credit({order.id})"><i class="fa fa-credit-card"></i></button>
                <button class="btn btn-xs btn-success" onclick="tax_stamping({order.id})"><i class="fa fa-check"></i></button>
            """
        })
        
    return {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": total_records,
        "data": data
    }

@app.get("/admin/staff", response_class=HTMLResponse)
async def list_staff(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    staff = db.query(models.Staff).all()
    return templates.TemplateResponse(
        request=request,
        name="staff.html",
        context={
            "settings": settings,
            "staff_list": staff,
            "active_page": "staff"
        }
    )

@app.get("/admin/printers", response_class=HTMLResponse)
async def list_printers(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    printers = db.query(models.Printer).all()
    return templates.TemplateResponse(
        request=request,
        name="printers.html",
        context={
            "settings": settings,
            "printers": printers,
            "active_page": "admin"
        }
    )

@app.post("/admin/printers/add")
async def add_printer(
    name: str = Form(...),
    ip_address: str = Form(...),
    printer_type: str = Form(...),
    db: Session = Depends(get_db)
):
    new_printer = models.Printer(
        name=name,
        ip_address=ip_address,
        printer_type=printer_type
    )
    db.add(new_printer)
    db.commit()
    return RedirectResponse(url="/admin/printers", status_code=303)



@app.get("/admin/receipts", response_class=HTMLResponse)
async def list_receipts(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    receipts = db.query(models.Receipt).order_by(models.Receipt.generated_at.desc()).all()
    return templates.TemplateResponse(request=request, name="receipts.html", context={"settings": settings, "receipts": receipts, "active_page": "admin"})

@app.get("/admin/hr/leave-types", response_class=HTMLResponse)
async def leave_types_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    return templates.TemplateResponse(
        request=request,
        name="leave_types.html",
        context={"settings": settings, "active_page": "leave_types"}
    )

@app.post("/api/admin/hr/add-leave-type")
async def add_leave_type(
    name: str = Form(...),
    days_per_year: int = Form(...),
    is_active: bool = Form(True),
    db: Session = Depends(get_db)
):
    try:
        new_type = models.LeaveType(name=name, days_per_year=days_per_year, is_active=is_active)
        db.add(new_type)
        db.commit()
        return {"resp": "1", "message": "Leave type added."}
    except Exception as e:
        db.rollback()
        return {"resp": "0", "message": str(e)}

@app.post("/api/admin/hr/update-leave-type")
async def update_leave_type(
    id: int = Form(...),
    name: str = Form(...),
    days_per_year: int = Form(...),
    is_active: bool = Form(True),
    db: Session = Depends(get_db)
):
    lt = db.query(models.LeaveType).filter(models.LeaveType.id == id).first()
    if lt:
        lt.name = name
        lt.days_per_year = days_per_year
        lt.is_active = is_active
        db.commit()
        return {"resp": "1", "message": "Updated."}
    return {"resp": "0", "message": "Not found."}

@app.get("/api/admin/hr/get-leave-types")
async def get_leave_types(db: Session = Depends(get_db)):
    types = db.query(models.LeaveType).all()
    return [{
        "id": t.id,
        "name": t.name,
        "days_per_year": t.days_per_year,
        "is_active": t.is_active,
        "timestamp": t.created_at.strftime("%Y-%m-%d")
    } for t in types]

@app.post("/api/admin/hr/delete-leave-type/{id}")
async def delete_leave_type(id: int, db: Session = Depends(get_db)):
    lt = db.query(models.LeaveType).filter(models.LeaveType.id == id).first()
    if lt:
        db.delete(lt)
        db.commit()
        return {"resp": "1", "message": "Deleted."}
    return {"resp": "0", "message": "Not found."}

@app.get("/admin/hr/leave-applications", response_class=HTMLResponse)
async def leave_applications_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    staff = db.query(models.Staff).filter(models.Staff.is_active).all()
    leave_types = db.query(models.LeaveType).filter(models.LeaveType.is_active).all()
    return templates.TemplateResponse(
        request=request,
        name="leave_applications.html",
        context={"settings": settings, "active_page": "leave_applications", "staff": staff, "leave_types": leave_types}
    )

@app.post("/api/admin/hr/apply-leave")
async def apply_leave(
    employee_id: int = Form(...),
    leave_type_id: int = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    total_days: float = Form(...),
    stretch: str = Form("full"),
    reason: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        new_app = models.LeaveApplication(
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            start_date=datetime.datetime.strptime(start_date, "%Y-%m-%d").date(),
            end_date=datetime.datetime.strptime(end_date, "%Y-%m-%d").date(),
            total_days=total_days,
            stretch=stretch,
            reason=reason,
            status="Pending"
        )
        db.add(new_app)
        db.commit()
        return {"resp": "1", "message": "Application submitted."}
    except Exception as e:
        db.rollback()
        return {"resp": "0", "message": str(e)}

@app.get("/api/admin/hr/get-leave-applications")
async def get_leave_applications(db: Session = Depends(get_db)):
    apps = db.query(models.LeaveApplication).order_by(models.LeaveApplication.id.desc()).all()
    return [{
        "id": a.id,
        "staff_name": a.employee.name,
        "leave_type": a.leave_type.name,
        "start_date": a.start_date.strftime("%Y-%m-%d"),
        "end_date": a.end_date.strftime("%Y-%m-%d"),
        "total_days": a.total_days,
        "stretch": a.stretch,
        "reason": a.reason,
        "status": a.status,
        "approver_name": a.approver.name if a.approver else None,
        "timestamp": a.created_at.strftime("%Y-%m-%d")
    } for a in apps]

@app.post("/api/admin/hr/update-leave-status/{id}")
async def update_leave_status(id: int, status: str = Form(...), db: Session = Depends(get_db)):
    app_obj = db.query(models.LeaveApplication).filter(models.LeaveApplication.id == id).first()
    if app_obj:
        app_obj.status = status
        # In a real app, we'd get the current user's ID from the session. 
        # For now, let's assume an admin is doing this.
        # Placeholder: app_obj.approved_by_id = current_user.id
        db.commit()
        return {"resp": "1", "message": f"Status updated to {status}."}
    return {"resp": "0", "message": "Application not found."}

@app.get("/api/admin/hr/delete-leave-application/{id}")
async def delete_leave_application(id: int, db: Session = Depends(get_db)):
    app_obj = db.query(models.LeaveApplication).filter(models.LeaveApplication.id == id).first()
    if app_obj:
        db.delete(app_obj)
        db.commit()
        return {"resp": "1", "message": "Application deleted."}
    return {"resp": "0", "message": "Application not found."}

@app.get("/admin/attendance/transactions", response_class=HTMLResponse)
async def attendance_transactions(request: Request, db: Session = Depends(get_db)):
    transactions = db.query(models.Attendance).order_by(models.Attendance.id.desc()).all()
    staff = db.query(models.Staff).all()
    return templates.TemplateResponse(
        request=request,
        name="attendance_transactions.html",
        context={
            "active_page": "attendance_transactions",
            "transactions": transactions,
            "staff": staff
        }
    )

@app.get("/admin/attendance/time-card-report", response_class=HTMLResponse)
async def time_card_report(request: Request, start_date: str = None, end_date: str = None, employee_id: int = None, db: Session = Depends(get_db)):
    staff = db.query(models.Staff).all()
    return templates.TemplateResponse(
        request=request,
        name="time_card_report.html",
        context={
            "active_page": "time_card_report",
            "start_date": start_date,
            "end_date": end_date,
            "employee_id": employee_id,
            "staff": staff
        }
    )

@app.get("/admin/workflows/approvals", response_class=HTMLResponse)
async def workflows_approvals(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    today = datetime.datetime.utcnow().date()
    
    # Fetch pending requisitions
    pending_reqs = db.query(models.Requisition).filter(models.Requisition.status == 'Pending').all()
    
    # Fetch pending expenses
    pending_exps = db.query(models.Expense).filter(models.Expense.status == 'Pending').all()
    
    pending_approvals = []
    for req in pending_reqs:
        requester_name = req.request_person.name if req.request_person else "System"
        total_amt = sum(item.quantity * (item.unit_price or 0.0) for item in req.items)
        pending_approvals.append({
            "id": req.id,
            "ref_no": req.code or f"REQ-{req.id}",
            "type": "Requisition",
            "requester": requester_name,
            "amount": total_amt,
            "date": req.created_at.strftime('%Y-%m-%d') if req.created_at else "-",
            "status": "Pending"
        })
        
    for exp in pending_exps:
        pending_approvals.append({
            "id": exp.id,
            "ref_no": exp.ref_no or f"EXP-{exp.id}",
            "type": "Expense",
            "requester": exp.paid_to or "N/A",
            "amount": exp.amount or 0.00,
            "date": exp.expense_date.strftime('%Y-%m-%d') if exp.expense_date else (exp.created_at.strftime('%Y-%m-%d') if exp.created_at else "-"),
            "status": "Pending"
        })
        
    # Count approved today
    approved_reqs_today = db.query(models.Requisition).filter(
        models.Requisition.status == 'Approved',
        func.date(models.Requisition.created_at) == today
    ).count()
    approved_exps_today = db.query(models.Expense).filter(
        models.Expense.status == 'Approved',
        func.date(models.Expense.expense_date) == today
    ).count()
    approved_today = approved_reqs_today + approved_exps_today
    
    # Count rejected today
    rejected_reqs_today = db.query(models.Requisition).filter(
        models.Requisition.status == 'Cancelled',
        func.date(models.Requisition.created_at) == today
    ).count()
    rejected_exps_today = db.query(models.Expense).filter(
        models.Expense.status == 'Cancelled',
        func.date(models.Expense.expense_date) == today
    ).count()
    rejected_today = rejected_reqs_today + rejected_exps_today
    
    pending_count = len(pending_approvals)
    avg_time = 0.0
    
    return templates.TemplateResponse(
        request=request,
        name="approvals.html",
        context={
            "settings": settings,
            "active_page": "approvals",
            "pending_approvals": pending_approvals,
            "pending_count": pending_count,
            "approved_today": approved_today,
            "rejected_today": rejected_today,
            "avg_time": avg_time,
            "currency": settings.get("currency", "KES")
        }
    )

@app.post("/api/admin/workflows/approve/{item_type}/{item_id}")
async def approve_workflow_item(item_type: str, item_id: int, db: Session = Depends(get_db)):
    if item_type == "Requisition":
        item = db.query(models.Requisition).filter(models.Requisition.id == item_id).first()
        if item:
            item.status = "Approved"
            db.commit()
            return {"success": True, "message": "Requisition approved successfully!"}
    elif item_type == "Expense":
        item = db.query(models.Expense).filter(models.Expense.id == item_id).first()
        if item:
            item.status = "Approved"
            db.commit()
            return {"success": True, "message": "Expense approved successfully!"}
    return {"success": False, "message": "Item not found."}

@app.post("/api/admin/workflows/reject/{item_type}/{item_id}")
async def reject_workflow_item(item_type: str, item_id: int, db: Session = Depends(get_db)):
    if item_type == "Requisition":
        item = db.query(models.Requisition).filter(models.Requisition.id == item_id).first()
        if item:
            item.status = "Cancelled"
            db.commit()
            return {"success": True, "message": "Requisition rejected successfully!"}
    elif item_type == "Expense":
        item = db.query(models.Expense).filter(models.Expense.id == item_id).first()
        if item:
            item.status = "Cancelled"
            db.commit()
            return {"success": True, "message": "Expense rejected successfully!"}
    return {"success": False, "message": "Item not found."}

@app.get("/admin/workflows/settings", response_class=HTMLResponse)
async def workflows_settings(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="workflow_settings.html",
        context={"active_page": "workflow_settings"}
    )

@app.post("/admin/stock-redistribute")
async def redistribute_items(
    store_id: int = Form(...),
    product_ids: list[str] = Form(...),
    db: Session = Depends(get_db)
):
    # If "All" is selected, get all product IDs
    if "All" in product_ids:
        actual_product_ids = [p.id for p in db.query(models.Product).all()]
    else:
        actual_product_ids = [int(pid) for pid in product_ids]
        
    for pid in actual_product_ids:
        # Check if item already exists in this store
        existing = db.query(models.ProductStoreStock).filter(
            models.ProductStoreStock.product_id == pid,
            models.ProductStoreStock.store_id == store_id
        ).first()
        
        if not existing:
            # Add with 0 stock to the new store
            new_stock = models.ProductStoreStock(
                product_id=pid,
                store_id=store_id,
                quantity=0
            )
            db.add(new_stock)
            
    db.commit()
    return RedirectResponse(url=f"/admin/stock-balances?store_id={store_id}", status_code=303)

@app.post("/admin/update-store-stock")
async def update_store_stock(
    stock_id: int = Form(...),
    quantity: float = Form(...),
    db: Session = Depends(get_db)
):
    stock = db.query(models.ProductStoreStock).filter(models.ProductStoreStock.id == stock_id).first()
    if stock:
        stock.quantity = quantity
        stock.last_stock_take = datetime.datetime.utcnow()
        db.commit()
        return {"resp": "1", "message": "Stock updated"}
    return {"resp": "0", "message": "Stock item not found"}

# ==========================================
# 35 NEW SIDEBAR NAVIGATION ENDPOINTS & CRUDS
# ==========================================



def get_simulated_items(db: Session, key: str, default_items: list):
    setting = db.query(models.Setting).filter(models.Setting.key == key).first()
    if not setting:
        setting = models.Setting(key=key, value=json.dumps(default_items))
        db.add(setting)
        db.commit()
        return default_items
    try:
        return json.loads(setting.value)
    except:
        return default_items

def save_simulated_items(db: Session, key: str, items: list):
    setting = db.query(models.Setting).filter(models.Setting.key == key).first()
    if not setting:
        setting = models.Setting(key=key, value=json.dumps(items))
        db.add(setting)
    else:
        setting.value = json.dumps(items)
    db.commit()

# --- CONFIGURATIONS ---

# 1. Categories
@app.get("/admin/config/categories", response_class=HTMLResponse)
async def get_categories(request: Request, db: Session = Depends(get_db)):
    items = db.query(models.Category).all()
    formatted_items = [{"id": item.id, "name": item.name} for item in items]
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Item Categories",
            "description": "Organize your items and services into administrative groups.",
            "headers": ["ID", "Category Name"],
            "items": formatted_items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}],
            "delete_url_prefix": "/admin/config/categories/delete/",
            "add_url": "/admin/config/categories/add",
            "add_fields": [
                {"label": "Category Name", "type": "text", "name": "name", "required": True}
            ],
            "active_page": "categories"
        }
    )

@app.post("/admin/config/categories/add")
async def add_category(name: str = Form(...), db: Session = Depends(get_db)):
    cat = models.Category(name=name)
    db.add(cat)
    db.commit()
    return RedirectResponse(url="/admin/config/categories", status_code=303)

@app.get("/admin/config/categories/delete/{id}")
async def delete_category(id: int, db: Session = Depends(get_db)):
    cat = db.query(models.Category).filter(models.Category.id == id).first()
    if cat:
        db.delete(cat)
        db.commit()
    return RedirectResponse(url="/admin/config/categories", status_code=303)


# 2. Units
@app.get("/admin/config/units", response_class=HTMLResponse)
async def get_units(request: Request, db: Session = Depends(get_db)):
    items = db.query(models.Unit).all()
    formatted_items = [{"id": item.id, "name": item.name, "description": item.description} for item in items]
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Item Units",
            "description": "Define transaction measurement scales (e.g. Pcs, Box, Kg).",
            "headers": ["ID", "Unit Name", "Description"],
            "items": formatted_items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "description", "type": "text"}],
            "delete_url_prefix": "/admin/config/units/delete/",
            "add_url": "/admin/config/units/add",
            "add_fields": [
                {"label": "Unit Name", "type": "text", "name": "name", "required": True},
                {"label": "Description", "type": "text", "name": "description", "required": False}
            ],
            "active_page": "units"
        }
    )

@app.post("/admin/config/units/add")
async def add_unit(name: str = Form(...), description: Optional[str] = Form(""), db: Session = Depends(get_db)):
    unit = models.Unit(name=name, description=description)
    db.add(unit)
    db.commit()
    return RedirectResponse(url="/admin/config/units", status_code=303)

@app.get("/admin/config/units/delete/{id}")
async def delete_unit(id: int, db: Session = Depends(get_db)):
    unit = db.query(models.Unit).filter(models.Unit.id == id).first()
    if unit:
        db.delete(unit)
        db.commit()
    return RedirectResponse(url="/admin/config/units", status_code=303)


# 3. Tax Types
@app.get("/admin/config/tax-types", response_class=HTMLResponse)
async def get_tax_types(request: Request, db: Session = Depends(get_db)):
    items = db.query(models.TaxType).all()
    formatted_items = [{"id": item.id, "name": item.name, "rate": item.rate} for item in items]
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Tax Configurations",
            "description": "Manage standard corporate tax rates (e.g. VAT 16%, Zero Rated 0%).",
            "headers": ["ID", "Tax Name", "Rate (%)"],
            "items": formatted_items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "rate", "type": "number"}],
            "delete_url_prefix": "/admin/config/tax-types/delete/",
            "add_url": "/admin/config/tax-types/add",
            "add_fields": [
                {"label": "Tax Name", "type": "text", "name": "name", "required": True},
                {"label": "Tax Rate (%)", "type": "number", "name": "rate", "required": True}
            ],
            "active_page": "tax_types"
        }
    )

@app.post("/admin/config/tax-types/add")
async def add_tax_type(name: str = Form(...), rate: float = Form(...), db: Session = Depends(get_db)):
    tax = models.TaxType(name=name, rate=rate)
    db.add(tax)
    db.commit()
    return RedirectResponse(url="/admin/config/tax-types", status_code=303)

@app.get("/admin/config/tax-types/delete/{id}")
async def delete_tax_type(id: int, db: Session = Depends(get_db)):
    tax = db.query(models.TaxType).filter(models.TaxType.id == id).first()
    if tax:
        db.delete(tax)
        db.commit()
    return RedirectResponse(url="/admin/config/tax-types", status_code=303)


# 4. Stores
@app.get("/admin/config/stores", response_class=HTMLResponse)
async def get_stores(request: Request, db: Session = Depends(get_db)):
    items = db.query(models.Store).all()
    formatted_items = [{"id": item.id, "name": item.name, "location": item.location} for item in items]
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Business Stores",
            "description": "Manage multi-store inventories, POS warehouses, and outlet terminals.",
            "headers": ["ID", "Store Name", "Location"],
            "items": formatted_items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "location", "type": "text"}],
            "delete_url_prefix": "/admin/config/stores/delete/",
            "add_url": "/admin/config/stores/add",
            "add_fields": [
                {"label": "Store Name", "type": "text", "name": "name", "required": True},
                {"label": "Location Details", "type": "text", "name": "location", "required": True}
            ],
            "active_page": "stores"
        }
    )

@app.post("/admin/config/stores/add")
async def add_store(name: str = Form(...), location: str = Form(...), db: Session = Depends(get_db)):
    store = models.Store(name=name, location=location)
    db.add(store)
    db.commit()
    return RedirectResponse(url="/admin/config/stores", status_code=303)

@app.get("/admin/config/stores/delete/{id}")
async def delete_store(id: int, db: Session = Depends(get_db)):
    store = db.query(models.Store).filter(models.Store.id == id).first()
    if store:
        db.delete(store)
        db.commit()
    return RedirectResponse(url="/admin/config/stores", status_code=303)


# 5. Fiscal Years
@app.get("/admin/config/fiscal-years", response_class=HTMLResponse)
async def get_fiscal_years(request: Request, db: Session = Depends(get_db)):
    items = db.query(models.FiscalYear).all()
    formatted_items = [{"id": item.id, "year": item.year, "is_active": item.is_active} for item in items]
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Fiscal Years",
            "description": "Define corporate financial accounting cycles and locked ledger states.",
            "headers": ["ID", "Accounting Year", "Status"],
            "items": formatted_items,
            "fields": [{"key": "id", "type": "text"}, {"key": "year", "type": "text"}, {"key": "is_active", "type": "boolean"}],
            "delete_url_prefix": "/admin/config/fiscal-years/delete/",
            "add_url": "/admin/config/fiscal-years/add",
            "add_fields": [
                {"label": "Accounting Year (e.g. 2026)", "type": "text", "name": "year", "required": True},
                {"label": "Set as Active Year", "type": "boolean", "name": "is_active", "required": True}
            ],
            "active_page": "fiscal_years"
        }
    )

@app.post("/admin/config/fiscal-years/add")
async def add_fiscal_year(year: str = Form(...), is_active: str = Form("1"), db: Session = Depends(get_db)):
    active_bool = is_active == "1"
    if active_bool:
        db.query(models.FiscalYear).update({models.FiscalYear.is_active: False})
    fy = models.FiscalYear(year=year, is_active=active_bool)
    db.add(fy)
    db.commit()
    return RedirectResponse(url="/admin/config/fiscal-years", status_code=303)

@app.get("/admin/config/fiscal-years/delete/{id}")
async def delete_fiscal_year(id: int, db: Session = Depends(get_db)):
    fy = db.query(models.FiscalYear).filter(models.FiscalYear.id == id).first()
    if fy:
        db.delete(fy)
        db.commit()
    return RedirectResponse(url="/admin/config/fiscal-years", status_code=303)


# --- SIMULATED DYNAMIC CONFIGURATIONS ---

# 6. Attributes
@app.get("/admin/config/attributes", response_class=HTMLResponse)
async def get_attributes(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_attributes", [
        {"id": 1, "name": "Size", "description": "Product dimensions"},
        {"id": 2, "name": "Weight", "description": "Product weight in kg"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Custom Attributes",
            "description": "Configure product characteristics and variants.",
            "headers": ["ID", "Attribute Name", "Description"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "description", "type": "text"}],
            "delete_url_prefix": "/admin/config/attributes/delete/",
            "add_url": "/admin/config/attributes/add",
            "add_fields": [
                {"label": "Attribute Name", "type": "text", "name": "name", "required": True},
                {"label": "Description", "type": "text", "name": "description", "required": False}
            ],
            "active_page": "attributes"
        }
    )

@app.post("/admin/config/attributes/add")
async def add_attribute(name: str = Form(...), description: str = Form(""), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_attributes", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "description": description})
    save_simulated_items(db, "sim_attributes", items)
    return RedirectResponse(url="/admin/config/attributes", status_code=303)

@app.get("/admin/config/attributes/delete/{id}")
async def delete_attribute(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_attributes", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_attributes", items)
    return RedirectResponse(url="/admin/config/attributes", status_code=303)


# 7. Brands
@app.get("/admin/config/brands", response_class=HTMLResponse)
async def get_brands(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_brands", [
        {"id": 1, "name": "KastomSoft", "description": "Default ERP Brand"},
        {"id": 2, "name": "KastomPOS Premium", "description": "Premium branding option"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Brands Manager",
            "description": "Manage catalog product brands and manufacturer tags.",
            "headers": ["ID", "Brand Name", "Description"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "description", "type": "text"}],
            "delete_url_prefix": "/admin/config/brands/delete/",
            "add_url": "/admin/config/brands/add",
            "add_fields": [
                {"label": "Brand Name", "type": "text", "name": "name", "required": True},
                {"label": "Description", "type": "text", "name": "description", "required": False}
            ],
            "active_page": "brands"
        }
    )

@app.post("/admin/config/brands/add")
async def add_brand(name: str = Form(...), description: str = Form(""), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_brands", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "description": description})
    save_simulated_items(db, "sim_brands", items)
    return RedirectResponse(url="/admin/config/brands", status_code=303)

@app.get("/admin/config/brands/delete/{id}")
async def delete_brand(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_brands", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_brands", items)
    return RedirectResponse(url="/admin/config/brands", status_code=303)


# 8. Colors
@app.get("/admin/config/colors", response_class=HTMLResponse)
async def get_colors(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_colors", [
        {"id": 1, "name": "Classic Teal", "code": "#008080"},
        {"id": 2, "name": "Pure White", "code": "#ffffff"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Item Colors",
            "description": "Create attributes for retail product colors.",
            "headers": ["ID", "Color Name", "Color Hex Code"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "code", "type": "text"}],
            "delete_url_prefix": "/admin/config/colors/delete/",
            "add_url": "/admin/config/colors/add",
            "add_fields": [
                {"label": "Color Name", "type": "text", "name": "name", "required": True},
                {"label": "Hex Code (e.g. #008080)", "type": "text", "name": "code", "required": True}
            ],
            "active_page": "colors"
        }
    )

@app.post("/admin/config/colors/add")
async def add_color(name: str = Form(...), code: str = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_colors", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "code": code})
    save_simulated_items(db, "sim_colors", items)
    return RedirectResponse(url="/admin/config/colors", status_code=303)

@app.get("/admin/config/colors/delete/{id}")
async def delete_color(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_colors", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_colors", items)
    return RedirectResponse(url="/admin/config/colors", status_code=303)


# 9. Unit Conversion
@app.get("/admin/config/unit-conversion", response_class=HTMLResponse)
async def get_unit_conversions(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_unit_conversions", [
        {"id": 1, "from_unit": "Box", "to_unit": "Pieces", "factor": 12.0}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Unit Conversions",
            "description": "Establish volumetric or multiplier ratios between package configurations.",
            "headers": ["ID", "From Package", "To Base Unit", "Conversion Factor"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "from_unit", "type": "text"}, {"key": "to_unit", "type": "text"}, {"key": "factor", "type": "number"}],
            "delete_url_prefix": "/admin/config/unit-conversion/delete/",
            "add_url": "/admin/config/unit-conversion/add",
            "add_fields": [
                {"label": "From Package (e.g. Box)", "type": "text", "name": "from_unit", "required": True},
                {"label": "To Base Unit (e.g. Pieces)", "type": "text", "name": "to_unit", "required": True},
                {"label": "Conversion Factor Multiplier", "type": "number", "name": "factor", "required": True}
            ],
            "active_page": "unit_conversions"
        }
    )

@app.post("/admin/config/unit-conversion/add")
async def add_unit_conversion(from_unit: str = Form(...), to_unit: str = Form(...), factor: float = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_unit_conversions", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "from_unit": from_unit, "to_unit": to_unit, "factor": factor})
    save_simulated_items(db, "sim_unit_conversions", items)
    return RedirectResponse(url="/admin/config/unit-conversion", status_code=303)

@app.get("/admin/config/unit-conversion/delete/{id}")
async def delete_unit_conversion(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_unit_conversions", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_unit_conversions", items)
    return RedirectResponse(url="/admin/config/unit-conversion", status_code=303)


# 10. Document Types
@app.get("/admin/config/document-types", response_class=HTMLResponse)
async def get_document_types(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_document_types", [
        {"id": 1, "name": "LPO", "code": "LPO"},
        {"id": 2, "name": "Invoice", "code": "INV"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Document Types",
            "description": "Configure shortcodes for organizational accounting slips.",
            "headers": ["ID", "Slip Name", "Short Code"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "code", "type": "text"}],
            "delete_url_prefix": "/admin/config/document-types/delete/",
            "add_url": "/admin/config/document-types/add",
            "add_fields": [
                {"label": "Document/Slip Name", "type": "text", "name": "name", "required": True},
                {"label": "Short Code", "type": "text", "name": "code", "required": True}
            ],
            "active_page": "document_types"
        }
    )

@app.post("/admin/config/document-types/add")
async def add_document_type(name: str = Form(...), code: str = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_document_types", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "code": code})
    save_simulated_items(db, "sim_document_types", items)
    return RedirectResponse(url="/admin/config/document-types", status_code=303)

@app.get("/admin/config/document-types/delete/{id}")
async def delete_document_type(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_document_types", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_document_types", items)
    return RedirectResponse(url="/admin/config/document-types", status_code=303)


# 11. Countries
@app.get("/admin/config/countries", response_class=HTMLResponse)
async def get_countries(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_countries", [
        {"id": 1, "name": "Kenya", "code": "KE"},
        {"id": 2, "name": "Uganda", "code": "UG"},
        {"id": 3, "name": "Tanzania", "code": "TZ"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "System Countries",
            "description": "Configure primary countries in the localization profile.",
            "headers": ["ID", "Country Name", "ISO Code"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "code", "type": "text"}],
            "delete_url_prefix": "/admin/config/countries/delete/",
            "add_url": "/admin/config/countries/add",
            "add_fields": [
                {"label": "Country Name", "type": "text", "name": "name", "required": True},
                {"label": "ISO 2-Letter Code", "type": "text", "name": "code", "required": True}
            ],
            "active_page": "countries"
        }
    )

@app.post("/admin/config/countries/add")
async def add_country(name: str = Form(...), code: str = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_countries", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "code": code})
    save_simulated_items(db, "sim_countries", items)
    return RedirectResponse(url="/admin/config/countries", status_code=303)

@app.get("/admin/config/countries/delete/{id}")
async def delete_country(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_countries", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_countries", items)
    return RedirectResponse(url="/admin/config/countries", status_code=303)


# 12. Currencies
@app.get("/admin/config/currencies", response_class=HTMLResponse)
async def get_currencies(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_currencies", [
        {"id": 1, "name": "Kenyan Shilling", "code": "KES", "symbol": "KSh"},
        {"id": 2, "name": "US Dollar", "code": "USD", "symbol": "$"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "System Currencies",
            "description": "Manage multi-currency options for cashier terminal transactions.",
            "headers": ["ID", "Currency Name", "ISO Code", "Symbol"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "code", "type": "text"}, {"key": "symbol", "type": "text"}],
            "delete_url_prefix": "/admin/config/currencies/delete/",
            "add_url": "/admin/config/currencies/add",
            "add_fields": [
                {"label": "Currency Name", "type": "text", "name": "name", "required": True},
                {"label": "ISO Code (e.g. KES)", "type": "text", "name": "code", "required": True},
                {"label": "Symbol (e.g. KSh)", "type": "text", "name": "symbol", "required": True}
            ],
            "active_page": "currencies"
        }
    )

@app.post("/admin/config/currencies/add")
async def add_currency(name: str = Form(...), code: str = Form(...), symbol: str = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_currencies", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "code": code, "symbol": symbol})
    save_simulated_items(db, "sim_currencies", items)
    return RedirectResponse(url="/admin/config/currencies", status_code=303)

@app.get("/admin/config/currencies/delete/{id}")
async def delete_currency(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_currencies", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_currencies", items)
    return RedirectResponse(url="/admin/config/currencies", status_code=303)


# 13. Tables
@app.get("/admin/config/tables", response_class=HTMLResponse)
async def get_tables_config(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_tables", [
        {"id": 1, "number": "T1", "capacity": 4, "status": "Available"},
        {"id": 2, "number": "T2", "capacity": 2, "status": "Available"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Diner Table Counter",
            "description": "Establish dining tables for restaurant order routing.",
            "headers": ["ID", "Table Label/Number", "Seating Capacity", "Status"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "number", "type": "text"}, {"key": "capacity", "type": "number"}, {"key": "status", "type": "text"}],
            "delete_url_prefix": "/admin/config/tables/delete/",
            "add_url": "/admin/config/tables/add",
            "add_fields": [
                {"label": "Table Label/Number (e.g. Table 5)", "type": "text", "name": "number", "required": True},
                {"label": "Seating Capacity", "type": "number", "name": "capacity", "required": True},
                {"label": "Initial Status", "type": "select", "name": "status", "required": True, "options": [
                    {"value": "Available", "label": "Available"},
                    {"value": "Occupied", "label": "Occupied"},
                    {"value": "Reserved", "label": "Reserved"}
                ]}
            ],
            "active_page": "tables"
        }
    )

@app.post("/admin/config/tables/add")
async def add_table_config(number: str = Form(...), capacity: int = Form(...), status: str = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_tables", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "number": number, "capacity": capacity, "status": status})
    save_simulated_items(db, "sim_tables", items)
    return RedirectResponse(url="/admin/config/tables", status_code=303)

@app.get("/admin/config/tables/delete/{id}")
async def delete_table_config(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_tables", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_tables", items)
    return RedirectResponse(url="/admin/config/tables", status_code=303)


# 14. Event Types
@app.get("/admin/config/event-types", response_class=HTMLResponse)
async def get_event_types(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_event_types", [
        {"id": 1, "name": "Conference", "description": "Business meeting banquets"},
        {"id": 2, "name": "Wedding Reception", "description": "Large social banquets"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Banqueting Event Types",
            "description": "Categorize events for hall and booking packages.",
            "headers": ["ID", "Event Type Name", "Description"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "description", "type": "text"}],
            "delete_url_prefix": "/admin/config/event-types/delete/",
            "add_url": "/admin/config/event-types/add",
            "add_fields": [
                {"label": "Event Type Name", "type": "text", "name": "name", "required": True},
                {"label": "Description", "type": "text", "name": "description", "required": False}
            ],
            "active_page": "event_types"
        }
    )

@app.post("/admin/config/event-types/add")
async def add_event_type(name: str = Form(...), description: str = Form(""), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_event_types", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "description": description})
    save_simulated_items(db, "sim_event_types", items)
    return RedirectResponse(url="/admin/config/event-types", status_code=303)

@app.get("/admin/config/event-types/delete/{id}")
async def delete_event_type(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_event_types", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_event_types", items)
    return RedirectResponse(url="/admin/config/event-types", status_code=303)


# 15. Invoice Templates
@app.get("/admin/config/invoice-templates", response_class=HTMLResponse)
async def get_invoice_templates(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_invoice_templates", [
        {"id": 1, "name": "Teal Modern Invoice", "file_path": "templates/invoice_teal.html"},
        {"id": 2, "name": "Standard Classic Invoice", "file_path": "templates/invoice_classic.html"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Invoice Layout Templates",
            "description": "Establish pre-configured HTML themes for customer bills.",
            "headers": ["ID", "Template Name", "File Path Link"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "file_path", "type": "text"}],
            "delete_url_prefix": "/admin/config/invoice-templates/delete/",
            "add_url": "/admin/config/invoice-templates/add",
            "add_fields": [
                {"label": "Template Name", "type": "text", "name": "name", "required": True},
                {"label": "Internal File Path (e.g. templates/invoice_teal.html)", "type": "text", "name": "file_path", "required": True}
            ],
            "active_page": "invoice_templates"
        }
    )

@app.post("/admin/config/invoice-templates/add")
async def add_invoice_template(name: str = Form(...), file_path: str = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_invoice_templates", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "file_path": file_path})
    save_simulated_items(db, "sim_invoice_templates", items)
    return RedirectResponse(url="/admin/config/invoice-templates", status_code=303)

@app.get("/admin/config/invoice-templates/delete/{id}")
async def delete_invoice_template(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_invoice_templates", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_invoice_templates", items)
    return RedirectResponse(url="/admin/config/invoice-templates", status_code=303)


# --- API GATEWAY CREDS MANAGER ---

# 16. Integration APIs
@app.get("/admin/integration-apis", response_class=HTMLResponse)
async def get_integration_apis(request: Request, db: Session = Depends(get_db)):
    token_setting = db.query(models.Setting).filter(models.Setting.key == "api_token").first()
    if not token_setting:
        token_setting = models.Setting(key="api_token", value="kp_live_5f2d4e6a8b7c9f8a0e2d4c")
        db.add(token_setting)
        db.commit()
    return templates.TemplateResponse(
        request=request,
        name="integration_apis.html",
        context={
            "api_token": token_setting.value,
            "active_page": "integration_apis"
        }
    )

@app.post("/admin/integration-apis/regenerate")
async def regenerate_integration_apis(db: Session = Depends(get_db)):
    new_tok = "kp_live_" + secrets.token_hex(16)
    token_setting = db.query(models.Setting).filter(models.Setting.key == "api_token").first()
    if token_setting:
        token_setting.value = new_tok
    else:
        token_setting = models.Setting(key="api_token", value=new_tok)
        db.add(token_setting)
    db.commit()
    return RedirectResponse(url="/admin/integration-apis", status_code=303)


# --- ORGANIZATIONAL PARAMETERS ---

# 17. Departments
@app.get("/admin/org/departments", response_class=HTMLResponse)
async def get_departments(request: Request, db: Session = Depends(get_db)):
    items = db.query(models.Department).all()
    formatted_items = [{"id": item.id, "name": item.name, "is_active": item.is_active} for item in items]
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Business Departments",
            "description": "Manage administrative departments and payroll divisions.",
            "headers": ["ID", "Department Name", "Status"],
            "items": formatted_items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "is_active", "type": "boolean"}],
            "delete_url_prefix": "/admin/org/departments/delete/",
            "add_url": "/admin/org/departments/add",
            "add_fields": [
                {"label": "Department Name", "type": "text", "name": "name", "required": True},
                {"label": "Status", "type": "boolean", "name": "is_active", "required": True}
            ],
            "active_page": "departments"
        }
    )

@app.post("/admin/org/departments/add")
async def add_department(name: str = Form(...), is_active: str = Form("1"), db: Session = Depends(get_db)):
    dept = models.Department(name=name, is_active=(is_active == "1"))
    db.add(dept)
    db.commit()
    return RedirectResponse(url="/admin/org/departments", status_code=303)

@app.get("/admin/org/departments/delete/{id}")
async def delete_department(id: int, db: Session = Depends(get_db)):
    dept = db.query(models.Department).filter(models.Department.id == id).first()
    if dept:
        db.delete(dept)
        db.commit()
    return RedirectResponse(url="/admin/org/departments", status_code=303)


# 18. Settings
@app.get("/admin/org/settings", response_class=HTMLResponse)
async def get_settings_page(request: Request, db: Session = Depends(get_db)):
    settings_records = db.query(models.Setting).all()
    settings_dict = {item.key: item.value for item in settings_records}
    return templates.TemplateResponse(
        request=request,
        name="admin_settings.html",
        context={
            "settings": settings_dict,
            "active_page": "settings"
        }
    )

@app.post("/admin/org/settings/save")
async def save_settings_page(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    for key, val in form_data.items():
        record = db.query(models.Setting).filter(models.Setting.key == key).first()
        if record:
            record.value = val
        else:
            db.add(models.Setting(key=key, value=val))
    db.commit()
    return RedirectResponse(url="/admin/org/settings", status_code=303)


# 19. Stations
@app.get("/admin/org/stations", response_class=HTMLResponse)
async def get_stations(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_stations", [
        {"id": 1, "name": "Main POS Terminal", "ip_address": "192.168.100.15"},
        {"id": 2, "name": "Kitchen Printer Station", "ip_address": "192.168.100.20"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Business Stations",
            "description": "Establish designated terminal computer stations and hardware addresses.",
            "headers": ["ID", "Station Label", "Local IP Address"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "ip_address", "type": "text"}],
            "delete_url_prefix": "/admin/org/stations/delete/",
            "add_url": "/admin/org/stations/add",
            "add_fields": [
                {"label": "Station Name/Label", "type": "text", "name": "name", "required": True},
                {"label": "Local IP Address", "type": "text", "name": "ip_address", "required": True}
            ],
            "active_page": "stations"
        }
    )

@app.post("/admin/org/stations/add")
async def add_station(name: str = Form(...), ip_address: str = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_stations", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "ip_address": ip_address})
    save_simulated_items(db, "sim_stations", items)
    return RedirectResponse(url="/admin/org/stations", status_code=303)

@app.get("/admin/org/stations/delete/{id}")
async def delete_station(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_stations", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_stations", items)
    return RedirectResponse(url="/admin/org/stations", status_code=303)


# --- USER/STAFF PROFILES ---

# 20. Roles
@app.get("/admin/roles", response_class=HTMLResponse)
async def get_roles(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_roles", [
        {"id": 1, "name": "Owner", "description": "Full administrative access"},
        {"id": 2, "name": "Manager", "description": "Operational supervisor access"},
        {"id": 3, "name": "Cashier", "description": "Sales billing and collection access"},
        {"id": 4, "name": "Waiter", "description": "Order placement and guest table management"}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "System Access Roles",
            "description": "Establish security permission roles and system authorization tags.",
            "headers": ["ID", "Role Label", "Rights Description"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "description", "type": "text"}],
            "delete_url_prefix": "/admin/roles/delete/",
            "add_url": "/admin/roles/add",
            "add_fields": [
                {"label": "Role Label Name", "type": "text", "name": "name", "required": True},
                {"label": "Access Level Description", "type": "text", "name": "description", "required": True}
            ],
            "active_page": "roles"
        }
    )

@app.post("/admin/roles/add")
async def add_role(name: str = Form(...), description: str = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_roles", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "description": description})
    save_simulated_items(db, "sim_roles", items)
    return RedirectResponse(url="/admin/roles", status_code=303)

@app.get("/admin/roles/delete/{id}")
async def delete_role(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_roles", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_roles", items)
    return RedirectResponse(url="/admin/roles", status_code=303)


# 21. Staff / Users list
@app.get("/admin/users")
async def get_users_list():
    return RedirectResponse(url="/admin/staff", status_code=303)

@app.post("/admin/staff/add")
async def add_staff(
    name: str = Form(...),
    username: str = Form(...),
    phone: str = Form(None),
    id_number: str = Form(None),
    role: str = Form("waiter"),
    basic_salary: float = Form(0.0),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    existing = db.query(models.Staff).filter(models.Staff.username == username).first()
    if existing:
        return RedirectResponse(url="/admin/staff?error=username_exists", status_code=303)
    
    from hashlib import sha256
    password_hash = sha256(password.strip().encode()).hexdigest()
    
    new_staff = models.Staff(
        name=name,
        username=username,
        phone=phone,
        id_number=id_number,
        role=role,
        basic_salary=basic_salary,
        password_hash=password_hash,
        is_active=True
    )
    db.add(new_staff)
    db.commit()
    return RedirectResponse(url="/admin/staff?success=added", status_code=303)

@app.post("/admin/staff/edit/{id}")
async def edit_staff_post(
    id: int,
    name: str = Form(...),
    username: str = Form(...),
    phone: str = Form(None),
    id_number: str = Form(None),
    role: str = Form(...),
    basic_salary: float = Form(0.0),
    is_active: str = Form("true"),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    staff = db.query(models.Staff).filter(models.Staff.id == id).first()
    if not staff:
        return RedirectResponse(url="/admin/staff?error=not_found", status_code=303)
    
    existing = db.query(models.Staff).filter(models.Staff.username == username, models.Staff.id != id).first()
    if existing:
        return RedirectResponse(url="/admin/staff?error=username_exists", status_code=303)
    
    staff.name = name
    staff.username = username
    staff.phone = phone
    staff.id_number = id_number
    staff.role = role
    staff.basic_salary = basic_salary
    staff.is_active = (is_active == "true")
    
    if password and password.strip():
        from hashlib import sha256
        staff.password_hash = sha256(password.strip().encode()).hexdigest()
        
    db.commit()
    return RedirectResponse(url="/admin/staff?success=updated", status_code=303)

@app.get("/admin/staff/delete/{id}")
async def delete_staff_get(id: int, db: Session = Depends(get_db)):
    staff = db.query(models.Staff).filter(models.Staff.id == id).first()
    if staff:
        try:
            db.delete(staff)
            db.commit()
            return RedirectResponse(url="/admin/staff?success=deleted", status_code=303)
        except Exception:
            db.rollback()
            staff.is_active = False
            db.commit()
            return RedirectResponse(url="/admin/staff?success=deactivated", status_code=303)
    return RedirectResponse(url="/admin/staff?error=not_found", status_code=303)



# 22. Agents
@app.get("/admin/users/agents", response_class=HTMLResponse)
async def get_agents(request: Request, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_agents", [
        {"id": 1, "name": "Booking.com Agent", "commission_rate": 15.0},
        {"id": 2, "name": "Expedia Agent", "commission_rate": 12.0}
    ])
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Agency Commissions",
            "description": "Establish and track third-party agents and booking portals.",
            "headers": ["ID", "Agent Name", "Commission Rate (%)"],
            "items": items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "commission_rate", "type": "number"}],
            "delete_url_prefix": "/admin/users/agents/delete/",
            "add_url": "/admin/users/agents/add",
            "add_fields": [
                {"label": "Agent Name", "type": "text", "name": "name", "required": True},
                {"label": "Commission Rate (%)", "type": "number", "name": "commission_rate", "required": True}
            ],
            "active_page": "agents"
        }
    )

@app.post("/admin/users/agents/add")
async def add_agent(name: str = Form(...), commission_rate: float = Form(...), db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_agents", [])
    new_id = max([item["id"] for item in items] + [0]) + 1
    items.append({"id": new_id, "name": name, "commission_rate": commission_rate})
    save_simulated_items(db, "sim_agents", items)
    return RedirectResponse(url="/admin/users/agents", status_code=303)

@app.get("/admin/users/agents/delete/{id}")
async def delete_agent(id: int, db: Session = Depends(get_db)):
    items = get_simulated_items(db, "sim_agents", [])
    items = [item for item in items if item["id"] != id]
    save_simulated_items(db, "sim_agents", items)
    return RedirectResponse(url="/admin/users/agents", status_code=303)


# 23. Customers Manager
@app.get("/admin/users/customers", response_class=HTMLResponse)
async def get_customers_page(request: Request, db: Session = Depends(get_db)):
    customers = db.query(models.Customer).all()
    return templates.TemplateResponse(
        request=request,
        name="customers.html",
        context={
            "customers": customers,
            "active_page": "customers"
        }
    )

@app.post("/admin/users/customers/add")
async def add_customer_post(name: str = Form(...), phone: str = Form(...), customer_type: str = Form("new"), db: Session = Depends(get_db)):
    customer = models.Customer(name=name, phone=phone, customer_type=customer_type, created_at=datetime.datetime.utcnow())
    db.add(customer)
    db.commit()
    return RedirectResponse(url="/admin/users/customers", status_code=303)

@app.get("/admin/users/customers/delete/{id}")
async def delete_customer_get(id: int, db: Session = Depends(get_db)):
    cust = db.query(models.Customer).filter(models.Customer.id == id).first()
    if cust:
        db.delete(cust)
        db.commit()
    return RedirectResponse(url="/admin/users/customers", status_code=303)


# 24. Suppliers Manager
@app.get("/admin/users/suppliers", response_class=HTMLResponse)
async def get_suppliers_page(request: Request, db: Session = Depends(get_db)):
    items = db.query(models.Supplier).all()
    formatted_items = [{"id": item.id, "name": item.name, "contact_person": item.contact_person, "phone": item.phone, "balance": item.balance} for item in items]
    return templates.TemplateResponse(
        request=request,
        name="admin_crud.html",
        context={
            "title": "Inventory Suppliers",
            "description": "Establish and track procurement suppliers, contact channels, and transaction values.",
            "headers": ["ID", "Supplier Name", "Contact Person", "Phone Number", "Current Balance (KES)"],
            "items": formatted_items,
            "fields": [{"key": "id", "type": "text"}, {"key": "name", "type": "text"}, {"key": "contact_person", "type": "text"}, {"key": "phone", "type": "text"}, {"key": "balance", "type": "number"}],
            "delete_url_prefix": "/admin/users/suppliers/delete/",
            "add_url": "/admin/users/suppliers/add",
            "add_fields": [
                {"label": "Supplier/Company Name", "type": "text", "name": "name", "required": True},
                {"label": "Contact Person Name", "type": "text", "name": "contact_person", "required": True},
                {"label": "Phone Number", "type": "text", "name": "phone", "required": True},
                {"label": "Opening Ledger Balance (KES)", "type": "number", "name": "balance", "required": True}
            ],
            "active_page": "suppliers"
        }
    )

@app.post("/admin/users/suppliers/add")
async def add_supplier_post(name: str = Form(...), contact_person: str = Form(...), phone: str = Form(...), balance: float = Form(0.0), db: Session = Depends(get_db)):
    supplier = models.Supplier(name=name, contact_person=contact_person, phone=phone, balance=balance)
    db.add(supplier)
    db.commit()
    return RedirectResponse(url="/admin/users/suppliers", status_code=303)

@app.get("/admin/users/suppliers/delete/{id}")
async def delete_supplier_get(id: int, db: Session = Depends(get_db)):
    supp = db.query(models.Supplier).filter(models.Supplier.id == id).first()
    if supp:
        db.delete(supp)
        db.commit()
    return RedirectResponse(url="/admin/users/suppliers", status_code=303)


# --- TRANSACTIONAL REPORTS ---

# 25. General Sales Report
@app.get("/admin/reports/general-sales", response_class=HTMLResponse)
async def report_general_sales(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    if not from_date:
        from_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    if not to_date:
        to_date = datetime.date.today().isoformat()
        
    start_dt = datetime.datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(to_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    orders = db.query(models.Order).filter(
        models.Order.created_at >= start_dt,
        models.Order.created_at <= end_dt
    ).all()
    
    items = []
    total_sales = 0.0
    for order in orders:
        cust = db.query(models.Customer).filter(models.Customer.id == order.customer_id).first()
        waiter = db.query(models.Staff).filter(models.Staff.id == order.waiter_id).first()
        cust_name = cust.name if cust else "Walk-in Guest"
        waiter_name = waiter.name if waiter else "System Counter"
        
        items.append({
            "order_id": order.id,
            "table_number": f"Table {order.table_number}" if order.table_number else "Counter",
            "waiter_name": waiter_name,
            "customer_name": cust_name,
            "created_at": order.created_at,
            "total_amount": order.total_amount,
            "status": order.status.upper()
        })
        if order.status.lower() == "paid":
            total_sales += order.total_amount
            
    stats = [
        {"label": "Total Sales Revenue", "value": f"KES {total_sales:,.2f}", "bg": "success", "icon": "coins"},
        {"label": "Total Invoices Issued", "value": len(orders), "bg": "info", "icon": "file-invoice-dollar"}
    ]
    
    return templates.TemplateResponse(
        request=request,
        name="general_sales_report.html",
        context={
            "from_date": from_date,
            "to_date": to_date,
            "items": items,
            "stats": stats,
            "currency": "KES",
            "active_page": "general_sales"
        }
    )


# 26. Staff Sales Report
@app.get("/admin/reports/staff-sales", response_class=HTMLResponse)
async def report_staff_sales(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    if not from_date:
        from_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    if not to_date:
        to_date = datetime.date.today().isoformat()
        
    start_dt = datetime.datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(to_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    staff = db.query(models.Staff).all()
    items = []
    
    for s in staff:
        orders = db.query(models.Order).filter(
            models.Order.waiter_id == s.id,
            models.Order.created_at >= start_dt,
            models.Order.created_at <= end_dt
        ).all()
        
        tot_val = sum([o.total_amount for o in orders if o.status.lower() == "paid"])
        if len(orders) > 0:
            items.append({
                "username": s.username,
                "name": s.name,
                "role": s.role.upper(),
                "orders_count": len(orders),
                "sales_value": tot_val
            })
            
    items = sorted(items, key=lambda x: x["sales_value"], reverse=True)
    
    stats = [
        {"label": "Top Performer Sales", "value": f"KES {items[0]['sales_value']:,.2f}" if items else "KES 0.00", "bg": "success", "icon": "trophy"},
        {"label": "Total Active Attendants", "value": len(items), "bg": "info", "icon": "users"}
    ]
    
    return templates.TemplateResponse(
        request=request,
        name="admin_reports_generic.html",
        context={
            "title": "Attendant Sales Summary",
            "description": f"Analyze sales performance grouped by system operator and waiters from {from_date} to {to_date}.",
            "filter_url": "/admin/reports/staff-sales",
            "from_date": from_date,
            "to_date": to_date,
            "headers": ["Username ID", "Staff Member Name", "Assigned Role", "Orders Serviced", "Paid Revenue Generated"],
            "items": items,
            "fields": [
                {"key": "username", "type": "text"},
                {"key": "name", "type": "text"},
                {"key": "role", "type": "text"},
                {"key": "orders_count", "type": "text"},
                {"key": "sales_value", "type": "currency"}
            ],
            "stats": stats,
            "currency": "KES",
            "active_page": "staff_sales"
        }
    )


# 27. Cheques Report
@app.get("/admin/reports/cheques", response_class=HTMLResponse)
async def report_cheques(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    if not from_date:
        from_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    if not to_date:
        to_date = datetime.date.today().isoformat()
        
    start_dt = datetime.datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(to_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    cheques = db.query(models.Cheque).filter(
        models.Cheque.due_date >= start_dt.date(),
        models.Cheque.due_date <= end_dt.date()
    ).all()
    
    items = []
    tot_amt = 0.0
    for ch in cheques:
        items.append({
            "cheque_number": ch.cheque_number,
            "due_date": ch.due_date,
            "status": ch.status.upper(),
            "amount": ch.amount
        })
        tot_amt += float(ch.amount)
        
    stats = [
        {"label": "Total Ledger Cheques", "value": f"KES {tot_amt:,.2f}", "bg": "teal", "icon": "money-check-alt"},
        {"label": "Cheques Count", "value": len(items), "bg": "primary", "icon": "list-ol"}
    ]
    
    return templates.TemplateResponse(
        request=request,
        name="admin_reports_generic.html",
        context={
            "title": "Corporate Cheque Registry",
            "description": f"Overview of issued cheques with upcoming maturation dates from {from_date} to {to_date}.",
            "filter_url": "/admin/reports/cheques",
            "from_date": from_date,
            "to_date": to_date,
            "headers": ["Cheque Serial Number", "Maturity Due Date", "Clearing Status", "Face Value Amount"],
            "items": items,
            "fields": [
                {"key": "cheque_number", "type": "text"},
                {"key": "due_date", "type": "date"},
                {"key": "status", "type": "text"},
                {"key": "amount", "type": "currency"}
            ],
            "stats": stats,
            "currency": "KES",
            "active_page": "cheques_report"
        }
    )


# 28. General Expenses Report
@app.get("/admin/reports/general-expenses", response_class=HTMLResponse)
async def report_general_expenses(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    if not from_date:
        from_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    if not to_date:
        to_date = datetime.date.today().isoformat()
        
    start_dt = datetime.datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(to_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    expenses = db.query(models.Expense).filter(
        models.Expense.expense_date >= start_dt.date(),
        models.Expense.expense_date <= end_dt.date()
    ).all()
    
    items = []
    tot_amt = 0.0
    for ex in expenses:
        acc = db.query(models.Account).filter(models.Account.id == ex.account_id).first()
        acc_name = acc.name if acc else "Default Cost Center"
        items.append({
            "ref_no": ex.ref_no,
            "account_name": acc_name,
            "paid_to": ex.paid_to,
            "expense_date": ex.expense_date,
            "status": ex.status.upper(),
            "amount": ex.amount
        })
        tot_amt += float(ex.amount)
        
    stats = [
        {"label": "Total Cash Expenses", "value": f"KES {tot_amt:,.2f}", "bg": "danger", "icon": "arrow-alt-circle-down"},
        {"label": "Vouchers Issued", "value": len(items), "bg": "info", "icon": "file-invoice"}
    ]
    
    return templates.TemplateResponse(
        request=request,
        name="admin_reports_generic.html",
        context={
            "title": "Organizational Expense Registry",
            "description": f"Cash outlays and supplier expense logs from {from_date} to {to_date}.",
            "filter_url": "/admin/reports/general-expenses",
            "from_date": from_date,
            "to_date": to_date,
            "headers": ["Expense Ref No", "Cost Center Account", "Paid/Disbursed To", "Date Disbursed", "Clearing Status", "Total Paid Value"],
            "items": items,
            "fields": [
                {"key": "ref_no", "type": "text"},
                {"key": "account_name", "type": "text"},
                {"key": "paid_to", "type": "text"},
                {"key": "expense_date", "type": "date"},
                {"key": "status", "type": "text"},
                {"key": "amount", "type": "currency"}
            ],
            "stats": stats,
            "currency": "KES",
            "active_page": "general_expenses_report"
        }
    )


# 29. Suppliers Listing Report
@app.get("/admin/reports/suppliers", response_class=HTMLResponse)
async def report_suppliers(request: Request, db: Session = Depends(get_db)):
    return await get_suppliers_page(request, db)


# 30. Customers Listing Report
@app.get("/admin/reports/customers", response_class=HTMLResponse)
async def report_customers(request: Request, db: Session = Depends(get_db)):
    return await get_customers_page(request, db)


# 31. Customer Balances Report
@app.get("/admin/reports/customer-balances", response_class=HTMLResponse)
async def report_customer_balances(request: Request, db: Session = Depends(get_db)):
    customers = db.query(models.Customer).all()
    items = []
    for c in customers:
        items.append({
            "name": c.name,
            "phone": c.phone,
            "type": c.customer_type.upper(),
            "balance": 0.0
        })
    return templates.TemplateResponse(
        request=request,
        name="admin_reports_generic.html",
        context={
            "title": "Diner Ledger Balances",
            "description": "Overview of outstanding diner credit accounts.",
            "filter_url": "/admin/reports/customer-balances",
            "headers": ["Customer Name", "Phone Contact", "Customer Group Tag", "Outstanding Balance"],
            "items": items,
            "fields": [
                {"key": "name", "type": "text"},
                {"key": "phone", "type": "text"},
                {"key": "type", "type": "text"},
                {"key": "balance", "type": "currency"}
            ],
            "stats": [{"label": "Total Customer Credit", "value": "KES 0.00", "bg": "primary", "icon": "user-tag"}],
            "currency": "KES",
            "active_page": "customer_balances"
        }
    )


# 32. Customer Statements Report
@app.get("/admin/reports/customer-statements", response_class=HTMLResponse)
async def report_customer_statements(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="customer_statements.html",
        context={
            "active_page": "customer_statements",
            "customers": db.query(models.Customer).all()
        }
    )


# 33. Supplier Balances Report
@app.get("/admin/reports/supplier-balances", response_class=HTMLResponse)
async def report_supplier_balances(request: Request, db: Session = Depends(get_db)):
    suppliers = db.query(models.Supplier).all()
    items = []
    tot_bal = 0.0
    for s in suppliers:
        items.append({
            "name": s.name,
            "contact": s.contact_person,
            "phone": s.phone,
            "balance": s.balance
        })
        tot_bal += float(s.balance)
    return templates.TemplateResponse(
        request=request,
        name="admin_reports_generic.html",
        context={
            "title": "Supplier Accounts Balances",
            "description": "Audited outstanding credit records for active raw stock suppliers.",
            "filter_url": "/admin/reports/supplier-balances",
            "headers": ["Supplier/Company Name", "Contact Person", "Phone Number", "Total Outstanding Credit"],
            "items": items,
            "fields": [
                {"key": "name", "type": "text"},
                {"key": "contact", "type": "text"},
                {"key": "phone", "type": "text"},
                {"key": "balance", "type": "currency"}
            ],
            "stats": [{"label": "Accounts Payable Value", "value": f"KES {tot_bal:,.2f}", "bg": "danger", "icon": "truck-loading"}],
            "currency": "KES",
            "active_page": "supplier_balances"
        }
    )


# 34. Supplier Statements Report
@app.get("/admin/reports/supplier-statements", response_class=HTMLResponse)
async def report_supplier_statements(request: Request, db: Session = Depends(get_db)):
    suppliers = db.query(models.Supplier).all()
    items = []
    for s in suppliers:
        items.append({
            "ref_no": "STMT-00" + str(s.id),
            "supplier_name": s.name,
            "contact": s.contact_person,
            "phone": s.phone,
            "narrative": "Monthly procurement credit audit statement."
        })
    return templates.TemplateResponse(
        request=request,
        name="admin_reports_generic.html",
        context={
            "title": "Supplier Statement Directory",
            "description": "Chronological audit statements generated for outstanding vendor accounts.",
            "filter_url": "/admin/reports/supplier-statements",
            "headers": ["Statement Reference", "Supplier/Company Name", "Representative Contact", "Phone Channel", "Statement Context"],
            "items": items,
            "fields": [
                {"key": "ref_no", "type": "text"},
                {"key": "supplier_name", "type": "text"},
                {"key": "contact", "type": "text"},
                {"key": "phone", "type": "text"},
                {"key": "narrative", "type": "text"}
            ],
            "stats": [{"label": "Generated Statements", "value": len(items), "bg": "indigo", "icon": "file-invoice-dollar"}],
            "currency": "KES",
            "active_page": "supplier_statements"
        }
    )


# 35. Account Statements Report
@app.get("/admin/reports/account-statements", response_class=HTMLResponse)
async def report_account_statements(
    request: Request,
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    if not from_date:
        from_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    if not to_date:
        to_date = datetime.date.today().isoformat()
        
    start_dt = datetime.datetime.strptime(from_date, "%Y-%m-%d")
    end_dt = datetime.datetime.strptime(to_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
    
    postings = db.query(models.JournalPosting).filter(
        models.JournalPosting.transaction_date >= start_dt.date(),
        models.JournalPosting.transaction_date <= end_dt.date()
    ).all()
    
    items = []
    for p in postings:
        acc = db.query(models.Account).filter(models.Account.id == p.account_id).first()
        acc_name = acc.name if acc else "System Account"
        items.append({
            "ref_no": p.ref_no,
            "account_name": acc_name,
            "reference": p.reference,
            "dr_cr": p.dr_cr.upper(),
            "amount": p.amount,
            "transaction_date": p.transaction_date
        })
        
    stats = [
        {"label": "Total Ledger Postings", "value": len(items), "bg": "primary", "icon": "receipt"},
        {"label": "Postings Period", "value": f"{from_date} to {to_date}", "bg": "info", "icon": "calendar-alt"}
    ]
    
    return templates.TemplateResponse(
        request=request,
        name="admin_reports_generic.html",
        context={
            "title": "General Accounts Statements",
            "description": f"Ledger debit/credit post slips from {from_date} to {to_date}.",
            "filter_url": "/admin/reports/account-statements",
            "from_date": from_date,
            "to_date": to_date,
            "headers": ["Posting Reference", "Asset/Liability Account", "Source Reference", "Type (DR/CR)", "Transaction Face Value", "Posting Date"],
            "items": items,
            "fields": [
                {"key": "ref_no", "type": "text"},
                {"key": "account_name", "type": "text"},
                {"key": "reference", "type": "text"},
                {"key": "dr_cr", "type": "text"},
                {"key": "amount", "type": "currency"},
                {"key": "transaction_date", "type": "date"}
            ],
            "stats": stats,
            "currency": "KES",
            "active_page": "account_statements"
        }
    )

@app.get("/admin/profile", response_class=HTMLResponse)
async def get_profile(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    user = get_current_user_global()
    
    recent_logs = []
    if user:
        recent_logs = db.query(models.AuditLog).filter(models.AuditLog.staff_id == user.id).order_by(models.AuditLog.timestamp.desc()).limit(10).all()
        
    return templates.TemplateResponse(
        request=request,
        name="user_profile.html",
        context={
            "settings": settings,
            "user": user,
            "recent_logs": recent_logs,
            "active_page": "profile"
        }
    )

@app.post("/admin/profile/update")
async def update_profile(
    name: str = Form(...),
    phone: str = Form(None),
    id_number: str = Form(None),
    password: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    user = db.query(models.Staff).first()
    if user:
        user.name = name
        user.phone = phone
        user.id_number = id_number
        if password and password.strip():
            from hashlib import sha256
            user.password_hash = sha256(password.strip().encode()).hexdigest()
        db.commit()
    return RedirectResponse(url="/admin/profile?success=true", status_code=303)

@app.get("/admin/notifications", response_class=HTMLResponse)
async def get_notifications_page(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    
    low_stock = db.query(models.Product).filter(models.Product.stock_quantity <= models.Product.reorder_level).all()
    pending_petty = db.query(models.PettyCashRequest).filter(models.PettyCashRequest.status == "Pending").all()
    pending_leave = db.query(models.LeaveApplication).filter(models.LeaveApplication.status == "Pending").all()
    
    all_notifications = []
    
    for p in low_stock:
        all_notifications.append({
            "title": "Low Stock Warning",
            "description": f"Product '{p.name}' is running low. Current quantity: {p.stock_quantity} (Reorder level: {p.reorder_level}).",
            "category": "Stock",
            "icon": "exclamation-triangle",
            "badge_class": "badge-warning",
            "link": "/admin/inventory"
        })
        
    for r in pending_petty:
        all_notifications.append({
            "title": "Pending Petty Cash Approval",
            "description": f"Petty cash request '{r.ref_no}' of KES {r.amount:,.2f} is awaiting authorization. Narrative: {r.narrative or 'N/A'}.",
            "category": "Finance",
            "icon": "money-bill-wave",
            "badge_class": "badge-info",
            "link": "/admin/petty-cash"
        })
        
    for leave in pending_leave:
        employee_name = leave.employee.name if leave.employee else "Employee"
        all_notifications.append({
            "title": "Pending Leave Approval",
            "description": f"Leave application from {employee_name} for {leave.total_days} days is awaiting approval.",
            "category": "HR",
            "icon": "calendar-alt",
            "badge_class": "badge-teal",
            "link": "/admin/hr/leave-applications"
        })
        
    if not all_notifications:
        all_notifications.append({
            "title": "System Active",
            "description": "The KastomPOS ERP system is fully operational. All modules are reporting healthy.",
            "category": "System",
            "icon": "check-circle",
            "badge_class": "badge-success",
            "link": "/admin/staff"
        })
        
    return templates.TemplateResponse(
        request=request,
        name="notifications.html",
        context={
            "settings": settings,
            "notifications": all_notifications,
            "active_page": "notifications"
        }
    )


