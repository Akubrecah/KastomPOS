import hashlib
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QComboBox, QFormLayout, QFrame, QMessageBox, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from app.services.database import SessionLocal
from app.core import models
import datetime

class StaffWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_staff_id = None
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLabel#header {
                color: #f8fafc;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QDoubleSpinBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #00817a;
            }
            QPushButton {
                background-color: #00817a;
                border: none;
                border-radius: 6px;
                color: #ffffff;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00968f;
            }
            QPushButton#btn-delete {
                background-color: #dc2626;
            }
            QPushButton#btn-delete:hover {
                background-color: #ef4444;
            }
            QPushButton#btn-clear {
                background-color: #475569;
            }
            QPushButton#btn-clear:hover {
                background-color: #64748b;
            }
            QTableWidget {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                gridline-color: #334155;
                color: #f8fafc;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #334155;
                color: #f8fafc;
                padding: 6px;
                border: none;
                font-weight: bold;
            }
            QFrame.card {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
        """)

        # Main horizontal split layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)

        # Left Column: Table & Search
        left_col = QVBoxLayout()
        left_col.setSpacing(15)

        # Title
        header_label = QLabel("Staff & Access Control")
        header_label.setObjectName("header")
        header_label.setFont(QFont("Outfit", 20))
        left_col.addWidget(header_label)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search staff by name or username...")
        self.search_input.textChanged.connect(self.load_staff)
        search_layout.addWidget(self.search_input)
        left_col.addLayout(search_layout)

        # Table
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Name", "Username", "Role", "Phone", "Salary", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.handle_row_selection)
        left_col.addWidget(self.table)

        main_layout.addLayout(left_col, 2)

        # Right Column: Editor Pane
        self.right_panel = QFrame()
        self.right_panel.setObjectName("right_panel")
        self.right_panel.setProperty("class", "card")
        self.right_panel.setFixedWidth(340)

        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(12)

        self.form_title = QLabel("Add New Employee")
        self.form_title.setFont(QFont("Outfit", 14, QFont.Weight.Bold))
        self.form_title.setStyleSheet("color: #00817a;")
        right_layout.addWidget(self.form_title)

        # Form fields
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.name_input = QLineEdit()
        form.addRow("Full Name:", self.name_input)

        self.username_input = QLineEdit()
        form.addRow("Username:", self.username_input)

        self.phone_input = QLineEdit()
        form.addRow("Phone Number:", self.phone_input)

        self.id_input = QLineEdit()
        form.addRow("National ID:", self.id_input)

        self.role_combo = QComboBox()
        self.role_combo.addItems([
            "waiter", "cashier", "manager", "admin", "owner", 
            "room_attendant", "chef", "cleaner"
        ])
        form.addRow("Role:", self.role_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Active", "Inactive"])
        form.addRow("Status:", self.status_combo)

        self.salary_input = QDoubleSpinBox()
        self.salary_input.setRange(0, 10000000)
        self.salary_input.setDecimals(2)
        self.salary_input.setSingleStep(1000)
        form.addRow("Basic Salary:", self.salary_input)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_label_text = QLabel("Password:")
        form.addRow(self.password_label_text, self.password_input)

        right_layout.addLayout(form)

        # Buttons
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self.save_btn = QPushButton("Register Employee")
        self.save_btn.clicked.connect(self.save_staff)
        btn_layout.addWidget(self.save_btn)

        self.delete_btn = QPushButton("Deactivate / Delete")
        self.delete_btn.setObjectName("btn-delete")
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(self.delete_staff)
        btn_layout.addWidget(self.delete_btn)

        self.clear_btn = QPushButton("Clear / New")
        self.clear_btn.setObjectName("btn-clear")
        self.clear_btn.clicked.connect(self.clear_form)
        btn_layout.addWidget(self.clear_btn)

        right_layout.addLayout(btn_layout)
        right_layout.addStretch()

        main_layout.addWidget(self.right_panel)

        self.load_staff()

    def load_staff(self):
        search_text = self.search_input.text().strip()
        db = SessionLocal()
        try:
            query = db.query(models.Staff)
            if search_text:
                query = query.filter(
                    models.Staff.name.ilike(f"%{search_text}%") | 
                    models.Staff.username.ilike(f"%{search_text}%")
                )
            
            staff_list = query.order_by(models.Staff.name.asc()).all()
            self.table.setRowCount(len(staff_list))

            for idx, s in enumerate(staff_list):
                name_item = QTableWidgetItem(s.name)
                name_item.setData(Qt.ItemDataRole.UserRole, s.id)

                user_item = QTableWidgetItem(s.username)
                role_item = QTableWidgetItem(s.role.upper())
                phone_item = QTableWidgetItem(s.phone or "-")
                
                salary_val = s.basic_salary or 0.0
                salary_item = QTableWidgetItem(f"{salary_val:,.2f}")
                
                status_str = "Active" if s.is_active else "Inactive"
                status_item = QTableWidgetItem(status_str)

                self.table.setItem(idx, 0, name_item)
                self.table.setItem(idx, 1, user_item)
                self.table.setItem(idx, 2, role_item)
                self.table.setItem(idx, 3, phone_item)
                self.table.setItem(idx, 4, salary_item)
                self.table.setItem(idx, 5, status_item)
        except Exception as e:
            print(f"Error loading staff: {e}")
        finally:
            db.close()

    def handle_row_selection(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            self.clear_form()
            return

        row = self.table.currentRow()
        name_item = self.table.item(row, 0)
        if not name_item:
            return

        staff_id = name_item.data(Qt.ItemDataRole.UserRole)
        self.selected_staff_id = staff_id

        db = SessionLocal()
        try:
            staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
            if staff:
                self.name_input.setText(staff.name)
                self.username_input.setText(staff.username)
                self.phone_input.setText(staff.phone or "")
                self.id_input.setText(staff.id_number or "")
                self.salary_input.setValue(staff.basic_salary or 0.0)
                
                idx_role = self.role_combo.findText(staff.role)
                if idx_role >= 0:
                    self.role_combo.setCurrentIndex(idx_role)
                
                status_str = "Active" if staff.is_active else "Inactive"
                idx_status = self.status_combo.findText(status_str)
                if idx_status >= 0:
                    self.status_combo.setCurrentIndex(idx_status)

                self.password_label_text.setText("New Password:")
                self.password_input.setPlaceholderText("(leave blank to keep current)")
                
                self.form_title.setText("Edit Employee Details")
                self.save_btn.setText("Save Changes")
                self.delete_btn.setVisible(True)
        except Exception as e:
            print(f"Error fetching staff details: {e}")
        finally:
            db.close()

    def clear_form(self):
        self.selected_staff_id = None
        self.name_input.clear()
        self.username_input.clear()
        self.phone_input.clear()
        self.id_input.clear()
        self.salary_input.setValue(0.0)
        self.role_combo.setCurrentIndex(0)
        self.status_combo.setCurrentIndex(0)
        self.password_input.clear()
        self.password_label_text.setText("Password:")
        self.password_input.setPlaceholderText("Enter password")
        self.form_title.setText("Add New Employee")
        self.save_btn.setText("Register Employee")
        self.delete_btn.setVisible(False)
        self.table.clearSelection()

    def save_staff(self):
        name = self.name_input.text().strip()
        username = self.username_input.text().strip()
        phone = self.phone_input.text().strip()
        id_number = self.id_input.text().strip()
        role = self.role_combo.currentText()
        is_active = self.status_combo.currentText() == "Active"
        salary = self.salary_input.value()
        password = self.password_input.text()

        if not name or not username:
            QMessageBox.warning(self, "Validation Error", "Full Name and Username are required.")
            return

        db = SessionLocal()
        try:
            # Check unique username
            existing = db.query(models.Staff).filter(models.Staff.username == username).first()
            if existing and existing.id != self.selected_staff_id:
                QMessageBox.warning(self, "Conflict Error", f"Username '{username}' is already taken.")
                return

            if self.selected_staff_id:
                # Edit Existing
                staff = db.query(models.Staff).filter(models.Staff.id == self.selected_staff_id).first()
                if staff:
                    staff.name = name
                    staff.username = username
                    staff.phone = phone
                    staff.id_number = id_number
                    staff.role = role
                    staff.is_active = is_active
                    staff.basic_salary = salary
                    
                    if password:
                        staff.password_hash = hashlib.sha256(password.encode()).hexdigest()
                    
                    db.commit()
                    QMessageBox.information(self, "Success", "Employee details updated successfully.")
            else:
                # Register New
                if not password:
                    QMessageBox.warning(self, "Validation Error", "Password is required for new employees.")
                    return
                
                hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
                new_staff = models.Staff(
                    name=name,
                    username=username,
                    phone=phone,
                    id_number=id_number,
                    role=role,
                    is_active=is_active,
                    basic_salary=salary,
                    password_hash=hashed_pwd,
                    created_at=datetime.datetime.utcnow()
                )
                db.add(new_staff)
                db.commit()
                QMessageBox.information(self, "Success", "New employee registered successfully.")

            self.clear_form()
            self.load_staff()
        except Exception as e:
            db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save staff member: {e}")
        finally:
            db.close()

    def delete_staff(self):
        if not self.selected_staff_id:
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to delete or soft-delete this employee record?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            db = SessionLocal()
            try:
                # Soft delete or deactivate instead of deleting completely if they have logs/records
                staff = db.query(models.Staff).filter(models.Staff.id == self.selected_staff_id).first()
                if staff:
                    # Let's perform a soft delete by setting active to False, or try full delete if allowed
                    # If they have orders, SQLAlchemy will block or raise IntegrityError. So we soft delete.
                    staff.is_active = False
                    db.commit()
                    QMessageBox.information(self, "Deactivated", "Employee has been marked as Inactive to protect historical data.")
                self.clear_form()
                self.load_staff()
            except Exception as e:
                db.rollback()
                QMessageBox.critical(self, "Error", f"Failed to deactivate employee: {e}")
            finally:
                db.close()
