import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor
from sqlalchemy import func
from app.services.database import SessionLocal
from app.core import models

class DashboardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # Premium Dark styling
        self.setStyleSheet("""
            QWidget {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QLabel#header {
                color: #f8fafc;
                font-weight: bold;
            }
            QFrame.card {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QLabel.card-title {
                color: #94a3b8;
                font-size: 11px;
                font-weight: bold;
                text-transform: uppercase;
            }
            QLabel.card-value {
                color: #f8fafc;
                font-size: 20px;
                font-weight: bold;
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
        """)

        # Main Layout wrapper (with Scroll Area for smaller screens)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        outer_layout.addWidget(scroll_area)

        main_widget = QWidget()
        scroll_area.setWidget(main_widget)

        layout = QVBoxLayout(main_widget)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # Header Title
        header_label = QLabel("Dashboard")
        header_label.setObjectName("header")
        header_label.setFont(QFont("Outfit", 24))
        layout.addWidget(header_label)

        # Grid for Info cards
        grid_layout = QGridLayout()
        grid_layout.setSpacing(15)

        # Card 1: Active Users
        self.users_card = self.create_info_card("Active Users", "0", "#00817a")
        self.users_val = self.users_card.findChild(QLabel, "val")
        grid_layout.addWidget(self.users_card, 0, 0)

        # Card 2: SMS Outbox
        self.sms_card = self.create_info_card("SMS Outbox", "0", "#d97706")
        self.sms_val = self.sms_card.findChild(QLabel, "val")
        grid_layout.addWidget(self.sms_card, 0, 1)

        # Card 3: Supplier Balances
        self.supplier_card = self.create_info_card("Supplier Balances", "KES 0", "#dc2626")
        self.supplier_val = self.supplier_card.findChild(QLabel, "val")
        grid_layout.addWidget(self.supplier_card, 0, 2)

        # Card 4: Stores
        self.stores_card = self.create_info_card("Stores", "0", "#2563eb")
        self.stores_val = self.stores_card.findChild(QLabel, "val")
        grid_layout.addWidget(self.stores_card, 0, 3)

        layout.addLayout(grid_layout)

        # Content Row layout (Split: Left side summary lists, Right side Account balances)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)

        # Left Column: Today's Summary & Notifications
        left_col = QVBoxLayout()
        left_col.setSpacing(15)

        # Today's Sales Box
        sales_box = QFrame()
        sales_box.setProperty("class", "card")
        sales_box_layout = QVBoxLayout(sales_box)
        sales_box_layout.setContentsMargins(15, 15, 15, 15)
        
        sales_title = QLabel("Today's sales summary")
        sales_title.setFont(QFont("Outfit", 14, QFont.Weight.Bold))
        sales_title.setStyleSheet("color: #00817a; margin-bottom: 5px;")
        sales_box_layout.addWidget(sales_title)

        self.total_paid_label = QLabel("Total Paid: KES 0.00")
        self.total_paid_label.setFont(QFont("Outfit", 12))
        self.total_paid_val = self.total_paid_label # mapping alias
        sales_box_layout.addWidget(self.total_paid_label)
        
        left_col.addWidget(sales_box)

        # Notifications Box
        notif_box = QFrame()
        notif_box.setProperty("class", "card")
        notif_box_layout = QVBoxLayout(notif_box)
        notif_box_layout.setContentsMargins(15, 15, 15, 15)

        notif_title = QLabel("Quick Notifications")
        notif_title.setFont(QFont("Outfit", 14, QFont.Weight.Bold))
        notif_title.setStyleSheet("color: #00817a; margin-bottom: 5px;")
        notif_box_layout.addWidget(notif_title)

        self.items_count_badge = QLabel("Total Items: 0")
        self.items_count_badge.setFont(QFont("Outfit", 11))
        notif_box_layout.addWidget(self.items_count_badge)

        self.open_sales_badge = QLabel("Open Bills: 0")
        self.open_sales_badge.setFont(QFont("Outfit", 11))
        notif_box_layout.addWidget(self.open_sales_badge)

        left_col.addWidget(notif_box)
        content_layout.addLayout(left_col, 1)

        # Right Column: Accounts Report
        right_col = QVBoxLayout()
        
        accounts_box = QFrame()
        accounts_box.setProperty("class", "card")
        accounts_layout = QVBoxLayout(accounts_box)
        accounts_layout.setContentsMargins(15, 15, 15, 15)

        accounts_title = QLabel("Key Accounts Report")
        accounts_title.setFont(QFont("Outfit", 14, QFont.Weight.Bold))
        accounts_title.setStyleSheet("color: #00817a; margin-bottom: 10px;")
        accounts_layout.addWidget(accounts_title)

        # Accounts Table
        self.accounts_table = QTableWidget(0, 3)
        self.accounts_table.setHorizontalHeaderLabels(["Account", "Code", "Balance"])
        self.accounts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.accounts_table.setMinimumHeight(200)
        self.accounts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.accounts_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        accounts_layout.addWidget(self.accounts_table)

        right_col.addWidget(accounts_box)
        content_layout.addLayout(right_col, 1)

        layout.addLayout(content_layout)
        layout.addStretch()

        self.refresh_data()

    def create_info_card(self, title, initial_value, border_color):
        card = QFrame()
        card.setProperty("class", "card")
        card.setStyleSheet(f"QFrame {{ border-top: 4px solid {border_color}; }}")
        card.setMinimumHeight(90)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setProperty("class", "card-title")
        layout.addWidget(title_lbl)

        val_lbl = QLabel(initial_value)
        val_lbl.setObjectName("val")
        val_lbl.setProperty("class", "card-value")
        layout.addWidget(val_lbl)

        return card

    def refresh_data(self):
        db = SessionLocal()
        try:
            # Active Users
            active_users = db.query(models.Staff).filter(models.Staff.is_active == True).count()
            self.users_val.setText(str(active_users))

            # SMS Count
            sms_count = db.query(models.SMSOutbox).count()
            self.sms_val.setText(str(sms_count))

            # Supplier Balance
            supplier_bal = db.query(func.sum(models.Supplier.balance)).scalar() or 0.0
            self.supplier_val.setText(f"KES {supplier_bal:,.0f}")

            # Stores
            stores_count = db.query(models.Store).count()
            self.stores_val.setText(str(stores_count))

            # Today's Sales Summary
            today = datetime.date.today()
            today_start = datetime.datetime.combine(today, datetime.time.min)
            today_end = datetime.datetime.combine(today, datetime.time.max)

            # Query total payments today
            today_payments = db.query(func.sum(models.Payment.amount_paid)).filter(
                models.Payment.paid_at >= today_start,
                models.Payment.paid_at <= today_end
            ).scalar() or 0.0
            self.total_paid_label.setText(f"Total Paid Today: KES {today_payments:,.2f}")

            # Total items count
            items_count = db.query(models.Product).count()
            self.items_count_badge.setText(f"Total Items in Catalog: {items_count}")

            # Open Sales
            open_sales = db.query(models.Order).filter(models.Order.status == 'open').count()
            self.open_sales_badge.setText(f"Open Bills (Active Tables): {open_sales}")

            # Accounts report (fetch accounts)
            accounts = db.query(models.Account).filter(models.Account.is_active == True).limit(5).all()
            self.accounts_table.setRowCount(len(accounts))
            for row_idx, acc in enumerate(accounts):
                self.accounts_table.setItem(row_idx, 0, QTableWidgetItem(acc.name))
                self.accounts_table.setItem(row_idx, 1, QTableWidgetItem(acc.code or "N/A"))
                
                # Check for negative balance
                bal_item = QTableWidgetItem(f"KES {acc.balance:,.2f}")
                if acc.balance < 0:
                    bal_item.setForeground(QColor("#f87171")) # lighter red
                self.accounts_table.setItem(row_idx, 2, bal_item)
        except Exception as e:
            print(f"Error loading dashboard data: {e}")
        finally:
            db.close()
