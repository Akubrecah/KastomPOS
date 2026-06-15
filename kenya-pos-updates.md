# KastomPOS Enhancements for the Kenyan Market

Extend KastomPOS with essential functionality, UI updates, and compliance features specific to Kenyan SMEs: Cashier auto-lock screen, M-Pesa Daraja API callback processing, Swahili localization, KRA ETR/TIMS receipt metadata, inventory expiry tracking, and cashier performance reports.

## User Review Required

> [!IMPORTANT]
> **PyQt6 Application Event Filter**
> To detect cashier idle state, we will subclass `QApplication` (or install a custom event filter) in `main.py`. This will monitor user actions (mouse movement, clicks, keystrokes) across the desktop shell wrapper. When no events are received for 5 minutes (or 300 seconds), it will automatically log the user out and show the login dialog, preventing unauthorized sales.

> [!WARNING]
> **Database Schema Migrations**
> Adding the `expiry_date` column to the `products` table requires updating the SQLAlchemy definition in `models.py`. Since SQLite is used, we will add safe fallback initialization logic on startup so that the column is added automatically if it doesn't already exist in the database schema.

## Open Questions

> [!IMPORTANT]
> **1. Swahili Localization Scope**
> We plan to provide translation dictionary lookups for key interface elements (e.g. Navigation titles, POS buttons, headers, totals). Is this sufficient, or do you require complete translation for all transaction records and system logs?

> [!IMPORTANT]
> **2. M-Pesa Callback Simulation**
> The Safaricom Daraja Callback API makes HTTP POST requests to the local server. Since the app is running locally, we will implement a simulation mock endpoint `/api/v1/mpesa/mock-callback` to allow cashiers to trigger STK response simulation locally, as well as a live route for webhook forwarding. Do you have a preference for the mock transaction payload?

---

## Proposed Changes

### 1. Database Model Updates
#### [MODIFY] [models.py](file:///Users/Akubrecah/Desktop/KastomPOS/models.py)
- Add the `expiry_date` column to the `Product` model.
  ```python
  expiry_date = Column(Date, nullable=True)
  ```

---

### 2. Desktop Shell Idle Timeout / Auto-Lock
#### [MODIFY] [main.py](file:///Users/Akubrecah/Desktop/KastomPOS/main.py)
- Create `IdleEventFilter` to capture mouse/keyboard events.
- Set up a QTimer initialized to 300 seconds (5 minutes).
- Reset the timer on any input event.
- Trigger logout and loop back to the `LoginDialog` when the timer expires.

---

### 3. Swahili Translation Toggle
#### [NEW] [app/core/translations.py](file:///Users/Akubrecah/Desktop/KastomPOS/app/core/translations.py)
- Create a dictionary mapping English strings to Swahili equivalents.
- Provide toggle buttons in the web UI header to store `language` state in a cookie/session.

#### [MODIFY] [main_fastapi.py](file:///Users/Akubrecah/Desktop/KastomPOS/main_fastapi.py)
- Create a template filter `trans` to translate UI labels dynamically.
- Register it in Jinja2: `templates.env.filters["trans"] = translate_text`.

#### [MODIFY] [layout.html](file:///Users/Akubrecah/Desktop/KastomPOS/templates/layout.html)
- Add a language toggle widget in the navbar header.
- Wrap UI labels (e.g., Home, Bookings, Reports, Logout) in the translation filter.

---

### 4. M-Pesa Daraja Callback & simulation
#### [MODIFY] [main_fastapi.py](file:///Users/Akubrecah/Desktop/KastomPOS/main_fastapi.py)
- Add a POST route `/api/v1/mpesa/callback` to handle Safaricom Daraja STK Push callbacks.
- Parse payload to record callbacks in the `MpesaCallback` database table.
- Auto-complete linked `open` orders when a success response is received.

---

### 5. KRA ETR / TIMS Compliance & Receipt Styling
#### [MODIFY] [templates/receipt.html](file:///Users/Akubrecah/Desktop/KastomPOS/templates/receipt.html)
- Include KRA PIN (e.g., `A001234567Z`).
- Generate and display a simulated TIMS control number and signature.
- Render 16% VAT tax calculations explicitly.

---

### 6. Inventory Expiry Dates
#### [MODIFY] [templates/inventory.html](file:///Users/Akubrecah/Desktop/KastomPOS/templates/inventory.html)
- Display `Expiry Date` for each product.
- Add styling alerts for items expiring within 30 days.

---

### 7. Cashier Performance & Excel Export
#### [NEW] [templates/cashier_report.html](file:///Users/Akubrecah/Desktop/KastomPOS/templates/cashier_report.html)
- Render summary table of cashier performance (sales count, total value, payment breakdown).
- Add buttons to export data as CSV (which opens natively in Microsoft Excel).

#### [MODIFY] [main_fastapi.py](file:///Users/Akubrecah/Desktop/KastomPOS/main_fastapi.py)
- Add router `/admin/reports/cashier-performance` aggregating cashier sales.

---

## Verification Plan

### Automated Tests
- **`tests/test_enhancements.py`**:
  - Test the translation filter for English and Swahili text strings.
  - Test M-Pesa callback payload parsing and database transaction insertion.
  - Verify product expiry date columns.

### Manual Verification
1. **Test Auto-Lock**: Set idle timeout to 10 seconds in dev mode, verify that the window locks and requests login.
2. **Toggle Language**: Toggle the header dropdown and confirm that labels switch between English and Swahili.
3. **Verify KRA Receipt**: Generate a sale, inspect the receipt, and ensure the TIMS control block and KRA PIN are visible.
