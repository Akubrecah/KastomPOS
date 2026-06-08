import sys
import hashlib
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
from app.services.database import SessionLocal
from app.core import models

class LoginDialog(QDialog):
    login_success = pyqtSignal(models.Staff)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KastomPOS - Secure Login")
        self.setFixedSize(400, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.init_ui()

    def init_ui(self):
        # Apply premium dark theme styles
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
            }
            QLabel {
                color: #f8fafc;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #00817a;
            }
            QPushButton {
                background-color: #00817a;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                padding: 12px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00968f;
            }
            QPushButton:pressed {
                background-color: #006c66;
            }
            QFrame#card {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Center card frame
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 40, 30, 40)
        card_layout.setSpacing(20)

        # Logo and Title
        title_label = QLabel("KastomPOS")
        title_label.setFont(QFont("Outfit", 26, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #00817a;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle_label = QLabel("Point of Sale & ERP")
        subtitle_label.setFont(QFont("Outfit", 12))
        subtitle_label.setStyleSheet("color: #64748b;")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout = QVBoxLayout()
        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        card_layout.addLayout(header_layout)

        # Inputs layout
        form_layout = QVBoxLayout()
        form_layout.setSpacing(12)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.setMinimumHeight(40)
        form_layout.addWidget(self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(40)
        self.password_input.returnPressed.connect(self.handle_login)
        form_layout.addWidget(self.password_input)

        card_layout.addLayout(form_layout)

        # Login button
        self.login_btn = QPushButton("Sign In")
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.clicked.connect(self.handle_login)
        card_layout.addWidget(self.login_btn)

        layout.addWidget(card)
        self.setLayout(layout)

    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            QMessageBox.warning(self, "Validation Error", "Please enter both username and password.")
            return

        db = SessionLocal()
        try:
            # Query staff by username
            staff = db.query(models.Staff).filter(models.Staff.username == username).first()
            if not staff:
                QMessageBox.critical(self, "Access Denied", "Invalid username or password.")
                return

            if not staff.is_active:
                QMessageBox.warning(self, "Account Disabled", "Your account has been deactivated.")
                return

            # Verify password hash
            hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
            if staff.password_hash != hashed_pwd:
                QMessageBox.critical(self, "Access Denied", "Invalid username or password.")
                return

            # Success
            self.login_success.emit(staff)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to authenticate: {e}")
        finally:
            db.close()
