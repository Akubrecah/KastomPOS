from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QIcon
from app.ui.dashboard import DashboardWidget
from app.ui.customers import CustomersWidget
from app.ui.staff import StaffWidget
from app.core import models

class MainWindow(QMainWindow):
    def __init__(self, logged_in_user: models.Staff, parent=None):
        super().__init__(parent)
        self.user = logged_in_user
        self.setWindowTitle("KastomPOS - Enterprise Management & POS")
        self.resize(1200, 800)
        self.setMinimumSize(1024, 700)
        self.init_ui()

    def init_ui(self):
        # Set premium stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0f172a;
            }
            QFrame#sidebar {
                background-color: #0b0f19;
                border-right: 1px solid #1e293b;
            }
            QLabel#sidebar-title {
                color: #00817a;
                font-weight: bold;
            }
            QPushButton.nav-btn {
                background-color: transparent;
                border: none;
                border-radius: 6px;
                color: #94a3b8;
                padding: 12px 20px;
                text-align: left;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton.nav-btn:hover {
                background-color: #1e293b;
                color: #f8fafc;
            }
            QPushButton.nav-btn:checked {
                background-color: #00817a;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#signout-btn {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                color: #f87171;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton#signout-btn:hover {
                background-color: #dc2626;
                color: #ffffff;
            }
        """)

        # Main horizontal layout
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setCentralWidget(central_widget)

        # ----------------------------------------------------
        # SIDEBAR
        # ----------------------------------------------------
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(240)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(15, 25, 15, 25)
        sidebar_layout.setSpacing(20)

        # Brand header
        brand_label = QLabel("KastomPOS")
        brand_label.setObjectName("sidebar-title")
        brand_label.setFont(QFont("Outfit", 22, QFont.Weight.Bold))
        brand_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(brand_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("background-color: #1e293b;")
        sidebar_layout.addWidget(divider)

        # Navigation buttons container
        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(8)

        self.btn_dashboard = QPushButton("  Dashboard")
        self.btn_dashboard.setCheckable(True)
        self.btn_dashboard.setChecked(True)
        self.btn_dashboard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_dashboard.setProperty("class", "nav-btn")
        self.btn_dashboard.clicked.connect(lambda: self.switch_view(0))
        nav_layout.addWidget(self.btn_dashboard)

        self.btn_customers = QPushButton("  Customers")
        self.btn_customers.setCheckable(True)
        self.btn_customers.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_customers.setProperty("class", "nav-btn")
        self.btn_customers.clicked.connect(lambda: self.switch_view(1))
        nav_layout.addWidget(self.btn_customers)

        self.btn_staff = QPushButton("  Staff Control")
        self.btn_staff.setCheckable(True)
        self.btn_staff.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_staff.setProperty("class", "nav-btn")
        self.btn_staff.clicked.connect(lambda: self.switch_view(2))
        nav_layout.addWidget(self.btn_staff)

        sidebar_layout.addWidget(nav_container)
        sidebar_layout.addStretch()

        # User Profile area
        user_box = QFrame()
        user_box.setStyleSheet("background-color: #111827; border-radius: 8px; padding: 10px;")
        user_layout = QVBoxLayout(user_box)
        
        user_name_lbl = QLabel(self.user.name)
        user_name_lbl.setFont(QFont("Outfit", 12, QFont.Weight.Bold))
        user_name_lbl.setStyleSheet("color: #f8fafc;")
        
        user_role_lbl = QLabel(self.user.role.upper())
        user_role_lbl.setFont(QFont("Outfit", 9))
        user_role_lbl.setStyleSheet("color: #64748b;")
        
        user_layout.addWidget(user_name_lbl)
        user_layout.addWidget(user_role_lbl)
        sidebar_layout.addWidget(user_box)

        # Sign out button
        self.signout_btn = QPushButton("Sign Out")
        self.signout_btn.setObjectName("signout-btn")
        self.signout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.signout_btn.clicked.connect(self.handle_signout)
        sidebar_layout.addWidget(self.signout_btn)

        main_layout.addWidget(sidebar)

        # ----------------------------------------------------
        # STACKED PAGES AREA
        # ----------------------------------------------------
        self.stacked_widget = QStackedWidget()
        
        self.view_dashboard = DashboardWidget()
        self.view_customers = CustomersWidget()
        self.view_staff = StaffWidget()

        self.stacked_widget.addWidget(self.view_dashboard) # Index 0
        self.stacked_widget.addWidget(self.view_customers) # Index 1
        self.stacked_widget.addWidget(self.view_staff)     # Index 2

        main_layout.addWidget(self.stacked_widget, 1)

        # Group button selection
        self.nav_buttons = [self.btn_dashboard, self.btn_customers, self.btn_staff]

    def switch_view(self, index: int):
        self.stacked_widget.setCurrentIndex(index)
        
        # Keep selected state for navigation buttons
        for idx, btn in enumerate(self.nav_buttons):
            btn.setChecked(idx == index)

        # Refresh data dynamically on current view
        if index == 0:
            self.view_dashboard.refresh_data()
        elif index == 1:
            self.view_customers.load_customers()
        elif index == 2:
            self.view_staff.load_staff()

    def handle_signout(self):
        confirm = QMessageBox.question(
            self, "Sign Out", "Are you sure you want to sign out?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            # Import dynamically to avoid circular references
            from app.ui.login import LoginDialog
            self.close()
            login = LoginDialog()
            if login.exec() == LoginDialog.DialogCode.Accepted:
                # Re-launch with the logged-in user
                self.user = login.user # Wait, LoginDialog doesn't set login.user directly but we emit it. Let's fix that in main.py entry point where dialog execution is handled.
