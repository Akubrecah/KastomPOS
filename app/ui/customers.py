from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, 
    QTableWidgetItem, QHeaderView, QComboBox, QFormLayout, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from app.services.database import SessionLocal
from app.core import models
import datetime

class CustomersWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_customer_id = None
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
            QLineEdit, QComboBox {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f8fafc;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus {
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

        # Main horizontal split
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(25, 25, 25, 25)
        main_layout.setSpacing(20)

        # Left Column: Search & Table
        left_col = QVBoxLayout()
        left_col.setSpacing(15)

        # Title
        header_label = QLabel("Customer Management")
        header_label.setObjectName("header")
        header_label.setFont(QFont("Outfit", 20))
        left_col.addWidget(header_label)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search customers by name or phone...")
        self.search_input.textChanged.connect(self.load_customers)
        search_layout.addWidget(self.search_input)
        left_col.addLayout(search_layout)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Phone Number", "Type", "Registered On"])
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
        self.right_panel.setFixedWidth(320)
        
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)

        self.form_title = QLabel("Add New Customer")
        self.form_title.setFont(QFont("Outfit", 14, QFont.Weight.Bold))
        self.form_title.setStyleSheet("color: #00817a;")
        right_layout.addWidget(self.form_title)

        # Form layout
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.name_input = QLineEdit()
        form.addRow("Full Name:", self.name_input)

        self.phone_input = QLineEdit()
        form.addRow("Phone Number:", self.phone_input)

        self.type_combo = QComboBox()
        self.type_combo.addItems(["new", "returning"])
        form.addRow("Customer Type:", self.type_combo)

        right_layout.addLayout(form)

        # Actions Layout
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(8)

        self.save_btn = QPushButton("Save Customer")
        self.save_btn.clicked.connect(self.save_customer)
        btn_layout.addWidget(self.save_btn)

        self.delete_btn = QPushButton("Delete Customer")
        self.delete_btn.setObjectName("btn-delete")
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(self.delete_customer)
        btn_layout.addWidget(self.delete_btn)

        self.clear_btn = QPushButton("Clear / New")
        self.clear_btn.setObjectName("btn-clear")
        self.clear_btn.clicked.connect(self.clear_form)
        btn_layout.addWidget(self.clear_btn)

        right_layout.addLayout(btn_layout)
        right_layout.addStretch()

        main_layout.addWidget(self.right_panel)

        self.load_customers()

    def load_customers(self):
        search_text = self.search_input.text().strip()
        db = SessionLocal()
        try:
            query = db.query(models.Customer)
            if search_text:
                query = query.filter(
                    models.Customer.name.ilike(f"%{search_text}%") | 
                    models.Customer.phone.ilike(f"%{search_text}%")
                )
            
            customers = query.order_by(models.Customer.name.asc()).all()
            self.table.setRowCount(len(customers))

            for idx, c in enumerate(customers):
                name_item = QTableWidgetItem(c.name)
                name_item.setData(Qt.ItemDataRole.UserRole, c.id) # Store ID in item
                
                phone_item = QTableWidgetItem(c.phone)
                
                type_str = "New Guest" if c.customer_type == 'new' else "Returning Diner"
                type_item = QTableWidgetItem(type_str)
                
                reg_date = c.created_at.strftime('%d %b, %Y') if c.created_at else '-'
                reg_item = QTableWidgetItem(reg_date)

                self.table.setItem(idx, 0, name_item)
                self.table.setItem(idx, 1, phone_item)
                self.table.setItem(idx, 2, type_item)
                self.table.setItem(idx, 3, reg_item)
        except Exception as e:
            print(f"Error loading customers: {e}")
        finally:
            db.close()

    def handle_row_selection(self):
        selected_rows = self.table.selectedItems()
        if not selected_rows:
            self.clear_form()
            return

        # Fetch ID from the first cell's UserRole
        row = self.table.currentRow()
        name_item = self.table.item(row, 0)
        if not name_item:
            return

        customer_id = name_item.data(Qt.ItemDataRole.UserRole)
        self.selected_customer_id = customer_id

        db = SessionLocal()
        try:
            customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
            if customer:
                self.name_input.setText(customer.name)
                self.phone_input.setText(customer.phone)
                idx = self.type_combo.findText(customer.customer_type)
                if idx >= 0:
                    self.type_combo.setCurrentIndex(idx)
                
                self.form_title.setText("Edit Customer")
                self.delete_btn.setVisible(True)
        except Exception as e:
            print(f"Error fetching customer details: {e}")
        finally:
            db.close()

    def clear_form(self):
        self.selected_customer_id = None
        self.name_input.clear()
        self.phone_input.clear()
        self.type_combo.setCurrentIndex(0)
        self.form_title.setText("Add New Customer")
        self.delete_btn.setVisible(False)
        self.table.clearSelection()

    def save_customer(self):
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        cust_type = self.type_combo.currentText()

        if not name or not phone:
            QMessageBox.warning(self, "Validation Error", "Name and Phone Number are required fields.")
            return

        db = SessionLocal()
        try:
            if self.selected_customer_id:
                # Update existing
                customer = db.query(models.Customer).filter(models.Customer.id == self.selected_customer_id).first()
                if customer:
                    customer.name = name
                    customer.phone = phone
                    customer.customer_type = cust_type
                    db.commit()
                    QMessageBox.information(self, "Success", "Customer details updated successfully.")
            else:
                # Create new
                new_customer = models.Customer(
                    name=name,
                    phone=phone,
                    customer_type=cust_type,
                    created_at=datetime.datetime.utcnow()
                )
                db.add(new_customer)
                db.commit()
                QMessageBox.information(self, "Success", "New customer registered successfully.")

            self.clear_form()
            self.load_customers()
        except Exception as e:
            db.rollback()
            QMessageBox.critical(self, "Error", f"Failed to save customer: {e}")
        finally:
            db.close()

    def delete_customer(self):
        if not self.selected_customer_id:
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to delete this customer? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            db = SessionLocal()
            try:
                customer = db.query(models.Customer).filter(models.Customer.id == self.selected_customer_id).first()
                if customer:
                    db.delete(customer)
                    db.commit()
                    QMessageBox.information(self, "Success", "Customer deleted successfully.")
                self.clear_form()
                self.load_customers()
            except Exception as e:
                db.rollback()
                QMessageBox.critical(self, "Error", f"Failed to delete customer: {e}")
            finally:
                db.close()
