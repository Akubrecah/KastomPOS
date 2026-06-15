import sys
import os
import shutil
import hashlib
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QFrame, QStackedWidget, QComboBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from app.services.database import SessionLocal, get_data_dir
from app.core import models

class SetupWizardDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KastomPOS - Initial Setup Wizard")
        self.setFixedSize(550, 650)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.logo_path = ""
        self.init_ui()

    def init_ui(self):
        # Dark Theme stylesheet consistent with login screen
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
            }
            QLabel {
                color: #f8fafc;
                font-size: 14px;
            }
            QLineEdit, QComboBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus, QComboBox:focus {
                border: 1px solid #00817a;
            }
            QPushButton {
                background-color: #00817a;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                padding: 12px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00968f;
            }
            QPushButton:pressed {
                background-color: #006c66;
            }
            QPushButton#secondary {
                background-color: #334155;
            }
            QPushButton#secondary:hover {
                background-color: #475569;
            }
            QFrame#card {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(25, 25, 25, 25)

        # Title / Progress Area
        header_layout = QVBoxLayout()
        self.title_label = QLabel("KastomPOS Setup Wizard")
        self.title_label.setFont(QFont("Outfit", 20, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #00817a;")
        header_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel("Step 1 of 3: Create Administrator Account")
        self.subtitle_label.setFont(QFont("Outfit", 12))
        self.subtitle_label.setStyleSheet("color: #94a3b8; margin-bottom: 15px;")
        header_layout.addWidget(self.subtitle_label)
        main_layout.addLayout(header_layout)

        # Stacked Widget for Setup Steps
        self.stacked_widget = QStackedWidget()

        # Step 1 Frame: Admin Account
        self.page_admin = QFrame()
        admin_layout = QVBoxLayout(self.page_admin)
        admin_layout.setSpacing(15)

        admin_desc = QLabel("Set up the default administrator account credentials.\nYou will use these to log into KastomPOS and manage other users.")
        admin_desc.setWordWrap(True)
        admin_desc.setStyleSheet("color: #94a3b8; font-size: 13px; margin-bottom: 10px;")
        admin_layout.addWidget(admin_desc)

        admin_layout.addWidget(QLabel("Admin Username *"))
        self.admin_user_input = QLineEdit()
        self.admin_user_input.setPlaceholderText("e.g. admin")
        admin_layout.addWidget(self.admin_user_input)

        admin_layout.addWidget(QLabel("Password *"))
        self.admin_pass_input = QLineEdit()
        self.admin_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_pass_input.setPlaceholderText("Enter secure password")
        admin_layout.addWidget(self.admin_pass_input)

        admin_layout.addWidget(QLabel("Confirm Password *"))
        self.confirm_pass_input = QLineEdit()
        self.confirm_pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_pass_input.setPlaceholderText("Repeat password")
        admin_layout.addWidget(self.confirm_pass_input)
        admin_layout.addStretch()

        self.stacked_widget.addWidget(self.page_admin)

        # Step 2 Frame: Business Info
        self.page_business = QFrame()
        biz_layout = QVBoxLayout(self.page_business)
        biz_layout.setSpacing(12)

        biz_layout.addWidget(QLabel("Business / Company Name *"))
        self.biz_name_input = QLineEdit()
        self.biz_name_input.setPlaceholderText("e.g. Kastom Supermarket")
        biz_layout.addWidget(self.biz_name_input)

        biz_layout.addWidget(QLabel("Physical Address / Location"))
        self.biz_address_input = QLineEdit()
        self.biz_address_input.setPlaceholderText("e.g. Kimathi Street, Nairobi")
        biz_layout.addWidget(self.biz_address_input)

        biz_row = QHBoxLayout()
        phone_layout = QVBoxLayout()
        phone_layout.addWidget(QLabel("Phone Number"))
        self.biz_phone_input = QLineEdit()
        self.biz_phone_input.setPlaceholderText("e.g. +254 700 123456")
        phone_layout.addWidget(self.biz_phone_input)
        biz_row.addLayout(phone_layout)

        pin_layout = QVBoxLayout()
        pin_layout.addWidget(QLabel("KRA PIN"))
        self.biz_pin_input = QLineEdit()
        self.biz_pin_input.setPlaceholderText("e.g. A001234567Z")
        pin_layout.addWidget(self.biz_pin_input)
        biz_row.addLayout(pin_layout)
        biz_layout.addLayout(biz_row)

        biz_layout.addWidget(QLabel("County / Region"))
        self.biz_county_input = QComboBox()
        self.biz_county_input.addItems([
            "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Kiambu", 
            "Machakos", "Uasin Gishu", "Nyeri", "Kilifi", "Kajiado", "Meru", "Others"
        ])
        biz_layout.addWidget(self.biz_county_input)

        biz_layout.addWidget(QLabel("Logo Image"))
        logo_row = QHBoxLayout()
        self.logo_label = QLabel("No logo selected")
        self.logo_label.setStyleSheet("color: #64748b; font-size: 13px;")
        logo_btn = QPushButton("Browse...")
        logo_btn.clicked.connect(self.browse_logo)
        logo_row.addWidget(self.logo_label)
        logo_row.addWidget(logo_btn)
        biz_layout.addLayout(logo_row)
        biz_layout.addStretch()

        self.stacked_widget.addWidget(self.page_business)

        # Step 3 Frame: Settings & Integrations
        self.page_settings = QFrame()
        settings_layout = QVBoxLayout(self.page_settings)
        settings_layout.setSpacing(12)

        settings_layout.addWidget(QLabel("VAT System Configuration"))
        self.vat_select = QComboBox()
        self.vat_select.addItems(["VAT Active (16%)", "VAT Disabled / Exempt"])
        settings_layout.addWidget(self.vat_select)

        settings_layout.addWidget(QLabel("Receipt Header (custom text shown on top of receipt)"))
        self.receipt_header_input = QLineEdit()
        self.receipt_header_input.setPlaceholderText("e.g. Welcome to Kastom POS")
        settings_layout.addWidget(self.receipt_header_input)

        settings_layout.addWidget(QLabel("Receipt Footer"))
        self.receipt_footer_input = QLineEdit()
        self.receipt_footer_input.setPlaceholderText("e.g. Thank you for your business")
        settings_layout.addWidget(self.receipt_footer_input)

        settings_layout.addWidget(QLabel("M-Pesa Setup (Paybill / Till Number)"))
        self.mpesa_input = QLineEdit()
        self.mpesa_input.setPlaceholderText("e.g. Buy Goods Till 123456")
        settings_layout.addWidget(self.mpesa_input)

        settings_layout.addWidget(QLabel("Thermal Printer Type"))
        self.printer_select = QComboBox()
        self.printer_select.addItems(["Thermal Printer (80mm)", "A4 / Regular Document Printer"])
        settings_layout.addWidget(self.printer_select)
        settings_layout.addStretch()

        self.stacked_widget.addWidget(self.page_settings)

        main_layout.addWidget(self.stacked_widget)

        # Navigation Buttons Area
        nav_layout = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.setObjectName("secondary")
        self.back_btn.clicked.connect(self.go_back)
        self.back_btn.setEnabled(False)

        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.go_next)

        nav_layout.addWidget(self.back_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.next_btn)
        main_layout.addLayout(nav_layout)

        self.setLayout(main_layout)

    def browse_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Logo Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.logo_path = file_path
            self.logo_label.setText(os.path.basename(file_path))

    def update_wizard_state(self):
        idx = self.stacked_widget.currentIndex()
        self.back_btn.setEnabled(idx > 0)
        
        self.subtitle_label.setText(f"Step {idx + 1} of 3: " + [
            "Create Administrator Account",
            "Business Profile Settings",
            "Receipt & Hardware Configurations"
        ][idx])

        if idx == 2:
            self.next_btn.setText("Finish Setup")
        else:
            self.next_btn.setText("Next")

    def go_back(self):
        idx = self.stacked_widget.currentIndex()
        if idx > 0:
            self.stacked_widget.setCurrentIndex(idx - 1)
            self.update_wizard_state()

    def go_next(self):
        idx = self.stacked_widget.currentIndex()
        
        # Validation per step
        if idx == 0:
            admin_user = self.admin_user_input.text().strip()
            admin_pass = self.admin_pass_input.text()
            confirm_pass = self.confirm_pass_input.text()
            if not admin_user:
                QMessageBox.warning(self, "Validation Error", "Admin Username is required.")
                return
            if not admin_pass or len(admin_pass) < 4:
                QMessageBox.warning(self, "Validation Error", "Password must be at least 4 characters.")
                return
            if admin_pass != confirm_pass:
                QMessageBox.warning(self, "Validation Error", "Passwords do not match.")
                return
        elif idx == 1:
            biz_name = self.biz_name_input.text().strip()
            if not biz_name:
                QMessageBox.warning(self, "Validation Error", "Business Name is required.")
                return

        if idx < 2:
            self.stacked_widget.setCurrentIndex(idx + 1)
            self.update_wizard_state()
        else:
            self.finish_setup()

    def finish_setup(self):
        admin_user = self.admin_user_input.text().strip()
        admin_pass = self.admin_pass_input.text()
        biz_name = self.biz_name_input.text().strip()
        biz_address = self.biz_address_input.text().strip()
        biz_phone = self.biz_phone_input.text().strip()
        biz_pin = self.biz_pin_input.text().strip()
        biz_county = self.biz_county_input.currentText()
        
        vat_enabled = self.vat_select.currentText() == "VAT Active (16%)"
        receipt_header = self.receipt_header_input.text().strip()
        receipt_footer = self.receipt_footer_input.text().strip()
        mpesa_paybill = self.mpesa_input.text().strip()
        printer_type = self.printer_select.currentText()

        # Save logo
        logo_url = ""
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                ext = os.path.splitext(self.logo_path)[1]
                dest_dir = get_data_dir()
                os.makedirs(dest_dir, exist_ok=True)
                dest_logo = os.path.join(dest_dir, f"logo{ext}")
                shutil.copy(self.logo_path, dest_logo)
                logo_url = dest_logo
            except Exception as e:
                QMessageBox.warning(self, "Logo Save Error", f"Failed to save logo file: {e}")

        # Seed Database
        db = SessionLocal()
        try:
            # 1. Create admin user
            hashed_pwd = hashlib.sha256(admin_pass.encode()).hexdigest()
            admin = db.query(models.Staff).filter(models.Staff.username == admin_user).first()
            if not admin:
                admin = models.Staff(
                    username=admin_user,
                    password_hash=hashed_pwd,
                    name="Administrator",
                    role="admin",
                    is_active=True
                )
                db.add(admin)
            else:
                admin.password_hash = hashed_pwd
                admin.is_active = True

            # 2. Seed Baseline tables
            # Tax types
            vat_tax = db.query(models.TaxType).filter(models.TaxType.name == "VAT 16%").first()
            if not vat_tax:
                vat_tax = models.TaxType(name="VAT 16%", rate=16.0)
                db.add(vat_tax)
            
            exempt_tax = db.query(models.TaxType).filter(models.TaxType.name == "Exempt").first()
            if not exempt_tax:
                exempt_tax = models.TaxType(name="Exempt", rate=0.0)
                db.add(exempt_tax)

            # Account types
            at1 = db.query(models.AccountType).filter(models.AccountType.name == "Asset").first()
            if not at1:
                at1 = models.AccountType(name="Asset")
                db.add(at1)
            at2 = db.query(models.AccountType).filter(models.AccountType.name == "Liability").first()
            if not at2:
                at2 = models.AccountType(name="Liability")
                db.add(at2)
            at3 = db.query(models.AccountType).filter(models.AccountType.name == "Equity").first()
            if not at3:
                at3 = models.AccountType(name="Equity")
                db.add(at3)
            at4 = db.query(models.AccountType).filter(models.AccountType.name == "Revenue").first()
            if not at4:
                at4 = models.AccountType(name="Revenue")
                db.add(at4)
            at5 = db.query(models.AccountType).filter(models.AccountType.name == "Expense").first()
            if not at5:
                at5 = models.AccountType(name="Expense")
                db.add(at5)
            
            db.flush()

            # Units
            u1 = db.query(models.Unit).filter(models.Unit.name == "Piece").first()
            if not u1:
                u1 = models.Unit(name="Piece")
                db.add(u1)
            u2 = db.query(models.Unit).filter(models.Unit.name == "Kg").first()
            if not u2:
                u2 = models.Unit(name="Kg")
                db.add(u2)
            u3 = db.query(models.Unit).filter(models.Unit.name == "Litre").first()
            if not u3:
                u3 = models.Unit(name="Litre")
                db.add(u3)

            # Category
            cat = db.query(models.Category).filter(models.Category.name == "General").first()
            if not cat:
                cat = models.Category(name="General")
                db.add(cat)

            # Store location
            store = db.query(models.Store).filter(models.Store.name == biz_name).first()
            if not store:
                store = models.Store(name=biz_name, location=biz_address or "Main Branch")
                db.add(store)
            
            db.flush()

            # Default key accounting ledger accounts
            acc1 = db.query(models.Account).filter(models.Account.code == "1001").first()
            if not acc1:
                acc1 = models.Account(name="Cash in Hand", account_type="Asset", code="1001", balance=0.0, account_type_id=at1.id, store_id=store.id, is_key=True)
                db.add(acc1)
            acc2 = db.query(models.Account).filter(models.Account.code == "1002").first()
            if not acc2:
                acc2 = models.Account(name="Bank Account", account_type="Asset", code="1002", balance=0.0, account_type_id=at1.id, store_id=store.id, is_key=True)
                db.add(acc2)
            acc3 = db.query(models.Account).filter(models.Account.code == "4001").first()
            if not acc3:
                acc3 = models.Account(name="Sales Revenue", account_type="Revenue", code="4001", balance=0.0, account_type_id=at4.id, store_id=store.id, is_key=True)
                db.add(acc3)

            # Settings
            settings_data = {
                "business_name": biz_name,
                "phone": biz_phone,
                "location": biz_address,
                "kra_pin": biz_pin,
                "county": biz_county,
                "logo_url": logo_url,
                "currency": "KES",
                "tax_rate": "16.0" if vat_enabled else "0.0",
                "receipt_header": receipt_header,
                "receipt_footer": receipt_footer,
                "mpesa_paybill": mpesa_paybill,
                "printer_type": printer_type,
                "wizard_completed": "true"
            }

            for k, v in settings_data.items():
                setting_obj = db.query(models.Setting).filter(models.Setting.key == k).first()
                if not setting_obj:
                    db.add(models.Setting(key=k, value=v))
                else:
                    setting_obj.value = v

            db.commit()
            QMessageBox.information(self, "Setup Completed", "KastomPOS baseline installation setup completed successfully!")
            self.accept()
        except Exception as e:
            db.rollback()
            QMessageBox.critical(self, "Database Error", f"Failed to complete wizard setup: {e}")
        finally:
            db.close()
