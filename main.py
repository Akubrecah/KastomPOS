import sys
import hashlib
import threading
import socket
import time
import logging
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox, QMainWindow
from PyQt6.QtCore import QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView

# CRITICAL FIX: In PyInstaller --onefile/--windowed mode, the bundle extraction
# directory (sys._MEIPASS) is NOT automatically on sys.path.
# We must add it manually before importing ANY local modules.
if getattr(sys, "frozen", False):
    _bundle_dir = getattr(sys, "_MEIPASS", None)
    if _bundle_dir and _bundle_dir not in sys.path:
        sys.path.insert(0, _bundle_dir)

# Ensure sys.stdout and sys.stderr are not None when running in windowed/no-console mode (e.g., under pythonw or PyInstaller --noconsole)
class DummyStream:
    def write(self, data):
        pass
    def flush(self):
        pass
    def isatty(self):
        return False
    def writable(self):
        return True

if sys.stdout is None:
    sys.stdout = DummyStream()
if sys.stderr is None:
    sys.stderr = DummyStream()

# Load database services, core models and login dialog
from app.services.database import engine, SessionLocal, Base
from app.core import models
from app.ui.login import LoginDialog

# Import the FastAPI main application module
import main_fastapi

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("kastompos")

_server_error = None

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0

def start_server():
    global _server_error
    try:
        import uvicorn
        uvicorn.run(
            main_fastapi.app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
        )
    except Exception:
        _server_error = traceback.format_exc()
        log.error("Server failed to start:\n%s", _server_error)

def wait_for_server(port: int, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_port_in_use(port):
            return True
        if _server_error:
            return False
        time.sleep(0.5)
    return False

class MainWindow(QMainWindow):
    def __init__(self, user):
        super().__init__()
        self.setWindowTitle(f"KastomPOS - ERP & Point of Sale ({user.name})")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 768)
        self.logged_out = False

        self.browser = QWebEngineView()
        self.browser.setUrl(QUrl("http://127.0.0.1:8000"))
        self.browser.urlChanged.connect(self.handle_url_change)
        self.setCentralWidget(self.browser)

    def handle_url_change(self, qurl):
        # Check if navigating to the logout route
        if qurl.path() == "/logout":
            log.info("Logout URL detected. Triggering sign-out...")
            self.logged_out = True
            self.close()

    def closeEvent(self, event):
        if self.logged_out:
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Exit KastomPOS",
            "Are you sure you want to exit KastomPOS?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

def auto_seed_on_startup():
    db = SessionLocal()
    try:
        if not db.query(models.Staff).first():
            print("Database is empty. Auto-seeding baseline data...")
            hashed_password = hashlib.sha256('password123'.encode()).hexdigest()
            
            # Add Default Staff
            admin = models.Staff(
                username='admin', 
                password_hash=hashed_password, 
                name='Admin User', 
                role='admin', 
                is_active=True
            )
            cashier = models.Staff(
                username='cashier1', 
                password_hash=hashed_password, 
                name='Main Cashier', 
                role='cashier', 
                is_active=True
            )
            waiter = models.Staff(
                username='waiter1', 
                password_hash=hashed_password, 
                name='James Waiter', 
                role='waiter', 
                is_active=True
            )
            db.add_all([admin, cashier, waiter])
            db.commit()

            # Add Default Categories
            cats = ['Food', 'Drinks', 'Rooms', 'Services']
            for c in cats:
                category = models.Category(name=c)
                db.add(category)
            db.commit()

            # Add Default Store
            store = models.Store(name="Main Restaurant", location="Ground Floor")
            db.add(store)
            db.commit()

            # Add Default Settings
            settings = [
                models.Setting(key="business_name", value="KastomPOS"),
                models.Setting(key="currency", value="KES"),
                models.Setting(key="receipt_footer", value="Thank you for choosing KastomPOS.")
            ]
            db.add_all(settings)
            db.commit()
            
            print("Auto-seeding complete.")
    except Exception as e:
        print(f"Error during database auto-seeding: {e}")
    finally:
        db.close()

def main():
    # 1. Initialize SQLite Database
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Database table creation failed: {e}")
        sys.exit(1)

    # 2. Run Seeding if empty
    auto_seed_on_startup()

    # 3. Start the FastAPI server early in a background thread if not already running
    if is_port_in_use(8000):
        log.info("Server already running on port 8000 - reusing it.")
    else:
        log.info("Starting background server thread...")
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()

    # 4. Start Qt GUI Loop
    app = QApplication(sys.argv)
    
    while True:
        # Show Secure Login dialog
        login = LoginDialog()
        if login.exec() == LoginDialog.DialogCode.Accepted:
            db = SessionLocal()
            try:
                username = login.username_input.text().strip()
                user = db.query(models.Staff).filter(models.Staff.username == username).first()
                if not user:
                    QMessageBox.critical(None, "Authentication Error", "User record lost during session hand-off.")
                    sys.exit(1)
            finally:
                db.close()

            # Bridge user session to FastAPI backend
            main_fastapi.CURRENT_USER_ID = user.id

            # Ensure background server is responsive before showing Main Window
            log.info("Waiting for local server to be ready...")
            if not wait_for_server(8000, timeout=30):
                error_detail = _server_error or "Server did not respond within 30 seconds."
                QMessageBox.critical(None, "Startup Error", f"Failed to start internal server: {error_detail}")
                sys.exit(1)

            # Show browser main window
            main_window = MainWindow(user)
            main_window.show()
            
            exit_code = app.exec()
            
            # Check if closed due to logout redirect
            if getattr(main_window, "logged_out", False):
                log.info("User logged out. Re-showing login dialog...")
                main_fastapi.CURRENT_USER_ID = None
                continue
            else:
                log.info("Window closed normally. Exiting application.")
                sys.exit(exit_code)
        else:
            sys.exit(0)

if __name__ == "__main__":
    main()

