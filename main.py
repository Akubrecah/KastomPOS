import sys
import hashlib
import threading
import socket
import time
import logging
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMessageBox, QMainWindow, QDialog,
    QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextBrowser
)
from PyQt6.QtCore import QUrl, QThread, pyqtSignal, Qt, QObject, QEvent, QTimer
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

# Handle reinstall prompt before importing database module
import os
def get_data_dir_lite():
    appName = "KastomPOS"
    if sys.platform == "win32":
        base_dir = os.getenv("PROGRAMDATA")
        if not base_dir:
            base_dir = os.getenv("APPDATA")
        if not base_dir:
            from pathlib import Path
            base_dir = str(Path.home() / ".kastompos")
        else:
            base_dir = os.path.join(base_dir, appName)
    elif sys.platform == "darwin":
        from pathlib import Path
        base_dir = str(Path.home() / "Library" / "Application Support" / appName)
    else:
        from pathlib import Path
        base_dir = str(Path.home() / ".kastompos")
    return base_dir

if "--reinstall" in sys.argv:
    db_path = os.path.join(get_data_dir_lite(), "pos.db")
    if os.path.exists(db_path):
        app_check = QApplication.instance()
        if not app_check:
            app_check = QApplication(sys.argv)
        
        reply = QMessageBox.question(
            None,
            "KastomPOS - Reinstall Detected",
            "An existing KastomPOS database was detected on this machine.\n\n"
            "Would you like to perform a Fresh Install (wipe existing data and start fresh)?\n"
            "Select 'No' to keep existing data (Repair Install).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            backup_path = os.path.join(get_data_dir_lite(), f"pos.db.bak_{int(time.time())}")
            try:
                os.rename(db_path, backup_path)
                print(f"Backed up existing database to {backup_path}")
            except Exception as e:
                print(f"Failed to wipe existing database: {e}")

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

# ----------------------------------------------------------------------
# REMOTE UPDATER IMPLEMENTATION
# ----------------------------------------------------------------------
class UpdateCheckerThread(QThread):
    update_checked = pyqtSignal(bool, str, str, str)

    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version

    def run(self):
        try:
            import urllib.request
            import json
            
            url = "https://api.github.com/repos/Akubrecah/KastomPOS/releases/latest"
            req = urllib.request.Request(
                url, 
                headers={"User-Agent": "KastomPOS-Updater"}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            remote_version = data.get("tag_name", "1.0.0")
            changelog = data.get("body", "No release notes provided.")
            html_url = data.get("html_url", "")
            
            # Find download URL for KastomPOS_Setup.exe
            download_url = None
            assets = data.get("assets", [])
            for asset in assets:
                name = asset.get("name", "")
                if name == "KastomPOS_Setup.exe":
                    download_url = asset.get("browser_download_url")
                    break
            
            if not download_url:
                for asset in assets:
                    name = asset.get("name", "")
                    if name.endswith(".exe"):
                        download_url = asset.get("browser_download_url")
                        break
            
            if not download_url:
                download_url = html_url

            available = self.is_new_version(self.current_version, remote_version)
            self.update_checked.emit(available, remote_version, changelog, download_url)
            
        except Exception as e:
            logging.getLogger("kastompos").warning(f"Failed to check for updates: {e}")
            self.update_checked.emit(False, "", "", "")

    def is_new_version(self, current: str, remote: str) -> bool:
        def parse(v):
            import re
            v_clean = re.sub(r'^[^\d]+', '', v)
            v_clean = re.split(r'[^\d.]', v_clean)[0]
            parts = []
            for x in v_clean.split('.'):
                try:
                    parts.append(int(x))
                except ValueError:
                    parts.append(0)
            return parts

        curr_parsed = parse(current)
        rem_parsed = parse(remote)
        
        max_len = max(len(curr_parsed), len(rem_parsed))
        curr_parsed += [0] * (max_len - len(curr_parsed))
        rem_parsed += [0] * (max_len - len(rem_parsed))
        
        return rem_parsed > curr_parsed


class FileDownloadThread(QThread):
    progress = pyqtSignal(int, int, int)
    finished = pyqtSignal(str, bool)

    def __init__(self, download_url, dest_path):
        super().__init__()
        self.download_url = download_url
        self.dest_path = dest_path
        self._is_cancelled = False

    def run(self):
        try:
            import urllib.request
            
            req = urllib.request.Request(
                self.download_url,
                headers={"User-Agent": "KastomPOS-Updater"}
            )
            
            with urllib.request.urlopen(req, timeout=20) as response:
                total_size = int(response.headers.get('content-length', 0))
                bytes_downloaded = 0
                block_size = 8192
                
                with open(self.dest_path, 'wb') as f:
                    while True:
                        if self._is_cancelled:
                            break
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        f.write(buffer)
                        bytes_downloaded += len(buffer)
                        
                        if total_size > 0:
                            percent = int((bytes_downloaded / total_size) * 100)
                            self.progress.emit(percent, bytes_downloaded, total_size)
                        else:
                            self.progress.emit(-1, bytes_downloaded, 0)
                            
            if self._is_cancelled:
                import os
                if os.path.exists(self.dest_path):
                    os.remove(self.dest_path)
                self.finished.emit("Download cancelled.", False)
            else:
                self.finished.emit(self.dest_path, True)
                
        except Exception as e:
            import os
            if os.path.exists(self.dest_path):
                try:
                    os.remove(self.dest_path)
                except Exception:
                    pass
            self.finished.emit(str(e), False)

    def cancel(self):
        self._is_cancelled = True


class UpdateDialog(QDialog):
    def __init__(self, current_version, new_version, changelog, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.resize(500, 400)
        self.setMinimumSize(450, 350)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #F7F6F3;
                font-family: 'Geist', sans-serif;
            }
            QLabel {
                color: #1c1917;
            }
            QLabel#title {
                font-family: 'Outfit', sans-serif;
                font-size: 18px;
                font-weight: bold;
                color: #008080;
            }
            QTextBrowser {
                background-color: #ffffff;
                border: 1px solid #e4e4e7;
                border-radius: 8px;
                padding: 10px;
                color: #334155;
                font-size: 13px;
            }
            QPushButton {
                font-family: 'Geist', sans-serif;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton#btnUpdate {
                background-color: #008080;
                color: white;
                border: 1px solid #008080;
            }
            QPushButton#btnUpdate:hover {
                background-color: #006666;
                border-color: #006666;
            }
            QPushButton#btnUpdate:pressed {
                background-color: #004d4d;
            }
            QPushButton#btnLater {
                background-color: #ffffff;
                color: #71717a;
                border: 1px solid #e4e4e7;
            }
            QPushButton#btnLater:hover {
                background-color: #f4f4f5;
                color: #18181b;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        title_label = QLabel("A new version of KastomPOS is available!")
        title_label.setObjectName("title")
        layout.addWidget(title_label)
        
        version_label = QLabel(f"Current version: <b>{current_version}</b> &nbsp;&nbsp;|&nbsp;&nbsp; New version: <b style='color:#008080;'>{new_version}</b>")
        layout.addWidget(version_label)
        
        notes_hdr = QLabel("Release Notes:")
        notes_hdr.setStyleSheet("font-weight: bold; color: #475569;")
        layout.addWidget(notes_hdr)
        
        self.notes_browser = QTextBrowser()
        self.notes_browser.setHtml(self.format_changelog(changelog))
        layout.addWidget(self.notes_browser)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()
        
        self.btn_later = QPushButton("Remind Me Later")
        self.btn_later.setObjectName("btnLater")
        self.btn_later.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_later)
        
        self.btn_update = QPushButton("Update Now")
        self.btn_update.setObjectName("btnUpdate")
        self.btn_update.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_update)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def format_changelog(self, text):
        if not text:
            return "No notes available."
        
        html = text.replace("\n", "<br>")
        import re
        html = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html)
        html = re.sub(r'\*(.*?)\*', r'<i>\1</i>', html)
        html = re.sub(r'^\s*-\s+(.*?)(?=<br>|$)', r'<li>\1</li>', html, flags=re.MULTILINE)
        html = re.sub(r'^\s*\*\s+(.*?)(?=<br>|$)', r'<li>\1</li>', html, flags=re.MULTILINE)
        return f"<div style='font-family:sans-serif;'>{html}</div>"


class DownloadProgressDialog(QDialog):
    def __init__(self, download_url, new_version, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Downloading Update")
        self.resize(400, 150)
        self.setModal(True)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #F7F6F3;
                font-family: 'Geist', sans-serif;
            }
            QLabel {
                color: #1c1917;
                font-size: 13px;
            }
            QProgressBar {
                border: 1px solid #e4e4e7;
                border-radius: 6px;
                text-align: center;
                background-color: #ffffff;
                color: #1c1917;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #008080;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #ffffff;
                color: #71717a;
                border: 1px solid #e4e4e7;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f4f4f5;
                color: #18181b;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        self.status_label = QLabel(f"Preparing to download KastomPOS {new_version}...")
        layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        import tempfile
        import os
        self.temp_dir = tempfile.gettempdir()
        self.dest_path = os.path.join(self.temp_dir, "KastomPOS_Setup.exe")
        
        self.downloader = FileDownloadThread(download_url, self.dest_path)
        self.downloader.progress.connect(self.handle_progress)
        self.downloader.finished.connect(self.handle_finished)
        self.btn_cancel.clicked.connect(self.cancel_download)
        
        self.downloader.start()

    def handle_progress(self, percent, downloaded, total):
        if percent >= 0:
            self.progress_bar.setValue(percent)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.status_label.setText(
                f"Downloading update... {mb_downloaded:.1f} MB / {mb_total:.1f} MB ({percent}%)"
            )
        else:
            self.progress_bar.setRange(0, 0)
            mb_downloaded = downloaded / (1024 * 1024)
            self.status_label.setText(f"Downloading update... {mb_downloaded:.1f} MB (calculating size...)")

    def handle_finished(self, result_path, success):
        self.downloader.wait()
        if success:
            self.accept()
            self.launch_installer(result_path)
        else:
            if result_path != "Download cancelled.":
                QMessageBox.critical(self, "Download Error", f"Failed to download update: {result_path}")
            self.reject()

    def cancel_download(self):
        self.status_label.setText("Cancelling download...")
        self.downloader.cancel()

    def launch_installer(self, path):
        try:
            import subprocess
            import sys
            import os
            
            if sys.platform.startswith('win'):
                os.startfile(path)
            else:
                if path.endswith('.exe'):
                    QMessageBox.information(
                        self,
                        "Installer Downloaded",
                        f"The Windows installer was downloaded to:\n{path}\n\nSince you are on a non-Windows OS ({sys.platform}), please copy it to a Windows machine to install."
                    )
                    return
                else:
                    subprocess.Popen(['open', path])
            
            QApplication.quit()
            
        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"Failed to run installer: {e}")


_update_checker = None

def check_for_updates(parent_window, current_version):
    global _update_checker
    log.info(f"Checking for updates. Current version: {current_version}")
    
    _update_checker = UpdateCheckerThread(current_version)
    
    def on_check_completed(available, remote_version, changelog, download_url):
        if available and download_url:
            log.info(f"Update available: {remote_version}")
            dialog = UpdateDialog(current_version, remote_version, changelog, parent_window)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                log.info(f"User approved download of version {remote_version}")
                
                import webbrowser
                if not download_url.startswith("http") or not (download_url.endswith(".exe") or "releases/download" in download_url):
                    log.info("Download URL is release page - opening in browser.")
                    webbrowser.open(download_url)
                    return
                
                dl_dialog = DownloadProgressDialog(download_url, remote_version, parent_window)
                dl_dialog.exec()
        else:
            log.info("No new updates available or error during check.")

    _update_checker.update_checked.connect(on_check_completed)
    _update_checker.start()


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
    pass

def main():
    # 1. Initialize SQLite Database
    try:
        Base.metadata.create_all(bind=engine)
        from app.services.database import run_migrations
        run_migrations(engine)
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
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    
    # Check if Setup Wizard needs to run
    db = SessionLocal()
    try:
        wizard_completed = db.query(models.Setting).filter(models.Setting.key == "wizard_completed").first()
        needs_wizard = not wizard_completed or wizard_completed.value != "true"
    except Exception as e:
        needs_wizard = True
    finally:
        db.close()
        
    if needs_wizard:
        from app.ui.setup_wizard import SetupWizardDialog
        wizard = SetupWizardDialog()
        if wizard.exec() != SetupWizardDialog.DialogCode.Accepted:
            log.info("Setup wizard cancelled/failed. Exiting application.")
            sys.exit(0)
            
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
            
            # Start background update checker
            from app import __version__ as APP_VERSION
            check_for_updates(main_window, APP_VERSION)
            
            # Setup cashier idle timeout auto-lock (5 minutes = 300,000 ms)
            class IdleEventFilter(QObject):
                def __init__(self, timeout_ms, callback_fn):
                    super().__init__()
                    self.timer = QTimer()
                    self.timer.setInterval(timeout_ms)
                    self.timer.timeout.connect(callback_fn)
                    self.timer.start()

                def eventFilter(self, obj, event):
                    if event.type() in (
                        QEvent.Type.MouseMove,
                        QEvent.Type.MouseButtonPress,
                        QEvent.Type.KeyPress,
                        QEvent.Type.MouseButtonRelease,
                        QEvent.Type.Wheel
                    ):
                        self.timer.start()
                    return super().eventFilter(obj, event)

            def auto_lock():
                log.info("Inactivity timeout reached. Automatically locking screen...")
                main_window.logged_out = True
                main_window.close()

            idle_filter = IdleEventFilter(300000, auto_lock)
            app.installEventFilter(idle_filter)
            
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

