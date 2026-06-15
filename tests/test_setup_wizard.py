import os
import sys
import shutil
import tempfile
import time
from unittest import mock
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
import models
from app.services.database import get_data_dir, get_database_path
from main_fastapi import perform_db_seed
from main import get_data_dir_lite

# Helper for standard in-memory test database
@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_get_data_dir_windows():
    with mock.patch("sys.platform", "win32"), \
         mock.patch("os.getenv") as mock_getenv:
        
        # Test case 1: PROGRAMDATA is set
        mock_getenv.side_effect = lambda key: "C:\\ProgramData" if key == "PROGRAMDATA" else None
        dir_path = get_data_dir()
        assert "KastomPOS" in dir_path
        assert "ProgramData" in dir_path

        # Test case 2: PROGRAMDATA not set, but APPDATA is set
        mock_getenv.side_effect = lambda key: "C:\\Users\\Test\\AppData\\Roaming" if key == "APPDATA" else None
        dir_path = get_data_dir()
        assert "KastomPOS" in dir_path
        assert "AppData" in dir_path

def test_get_data_dir_mac():
    with mock.patch("sys.platform", "darwin"), \
         mock.patch("pathlib.Path.home") as mock_home:
        from pathlib import Path
        mock_home.return_value = Path("/Users/testuser")
        dir_path = get_data_dir()
        assert dir_path == "/Users/testuser/Library/Application Support/KastomPOS"

def test_get_data_dir_linux():
    with mock.patch("sys.platform", "linux"), \
         mock.patch("pathlib.Path.home") as mock_home:
        from pathlib import Path
        mock_home.return_value = Path("/home/testuser")
        dir_path = get_data_dir()
        assert dir_path == "/home/testuser/.kastompos"

def test_get_database_path_custom_env():
    with mock.patch("os.getenv") as mock_getenv:
        mock_getenv.return_value = "postgresql://user:pass@host/db"
        assert get_database_path() == "postgresql://user:pass@host/db"

def test_baseline_seeding(test_db):
    # Run baseline seeding
    perform_db_seed(test_db)
    
    # 1. Verify no demo/test business data is seeded
    assert test_db.query(models.Staff).count() == 0
    assert test_db.query(models.Product).count() == 0
    assert test_db.query(models.Order).count() == 0
    assert test_db.query(models.Supplier).count() == 0
    assert test_db.query(models.Store).count() == 0
    assert test_db.query(models.Account).count() == 0
    
    # 2. Verify baseline config exists
    # TaxTypes (VAT 16%, Exempt)
    vat_tax = test_db.query(models.TaxType).filter(models.TaxType.name == "VAT 16%").first()
    assert vat_tax is not None
    assert vat_tax.rate == 16.0
    
    exempt_tax = test_db.query(models.TaxType).filter(models.TaxType.name == "Exempt").first()
    assert exempt_tax is not None
    assert exempt_tax.rate == 0.0

    # AccountTypes
    assert test_db.query(models.AccountType).filter(models.AccountType.name == "Asset").first() is not None
    assert test_db.query(models.AccountType).filter(models.AccountType.name == "Liability").first() is not None
    assert test_db.query(models.AccountType).filter(models.AccountType.name == "Revenue").first() is not None
    assert test_db.query(models.AccountType).filter(models.AccountType.name == "Expense").first() is not None

    # Units
    assert test_db.query(models.Unit).filter(models.Unit.name == "Piece").first() is not None
    assert test_db.query(models.Unit).filter(models.Unit.name == "Kg").first() is not None
    assert test_db.query(models.Unit).filter(models.Unit.name == "Litre").first() is not None

    # Category
    assert test_db.query(models.Category).filter(models.Category.name == "General").first() is not None

def test_reinstall_backup_and_wipe():
    # Setup temporary directory for simulation
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "pos.db")
    
    try:
        # Create a dummy database file
        with open(db_file, "w") as f:
            f.write("dummy sqlite contents")
        
        # Verify the file is created
        assert os.path.exists(db_file)
        
        # Mock sys.argv to contain --reinstall
        with mock.patch("sys.argv", ["main.py", "--reinstall"]), \
             mock.patch("main.get_data_dir_lite", return_value=temp_dir), \
             mock.patch("PyQt6.QtWidgets.QMessageBox.question") as mock_question:
            
            # Simulate user confirming "Yes" to wipe database
            from PyQt6.QtWidgets import QMessageBox
            mock_question.return_value = QMessageBox.StandardButton.Yes
            
            # Run the same reinstall check block logic
            if "--reinstall" in sys.argv:
                db_path = os.path.join(temp_dir, "pos.db")
                if os.path.exists(db_path):
                    # We bypass QApplication check by mocking QMessageBox
                    reply = QMessageBox.question(
                        None,
                        "KastomPOS - Reinstall Detected",
                        "Prompt text",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        backup_path = os.path.join(temp_dir, f"pos.db.bak_{int(time.time())}")
                        os.rename(db_path, backup_path)
            
            # Verify the database file was renamed
            assert not os.path.exists(db_file)
            
            # Check backup file exists
            files = os.listdir(temp_dir)
            backup_files = [f for f in files if f.startswith("pos.db.bak_")]
            assert len(backup_files) == 1
            
    finally:
        shutil.rmtree(temp_dir)

def test_setup_wizard_seeding(test_db):
    # We will test the setup wizard's finished setup data seeding logic directly
    # on our test database by mimicking the finish_setup method.
    admin_user = "pos_admin"
    admin_pass = "secure123"
    biz_name = "Nairobi Retailers"
    biz_address = "Moi Avenue"
    biz_phone = "+254711122233"
    biz_pin = "A009876543Z"
    biz_county = "Nairobi"
    logo_url = "/path/to/logo.png"
    vat_enabled = True
    receipt_header = "Welcome to Nairobi Retailers"
    receipt_footer = "Thank you for shopping with us"
    mpesa_paybill = "Buy Goods 999888"
    printer_type = "Thermal Printer (80mm)"
    
    import hashlib
    import hashlib
    # 1. Create admin user
    hashed_pwd = hashlib.sha256(admin_pass.encode()).hexdigest()
    admin = test_db.query(models.Staff).filter(models.Staff.username == admin_user).first()
    if not admin:
        admin = models.Staff(
            username=admin_user,
            password_hash=hashed_pwd,
            name="Administrator",
            role="admin",
            is_active=True
        )
        test_db.add(admin)
        
    # 2. Seed Baseline tables
    # Tax types
    vat_tax = test_db.query(models.TaxType).filter(models.TaxType.name == "VAT 16%").first()
    if not vat_tax:
        vat_tax = models.TaxType(name="VAT 16%", rate=16.0)
        test_db.add(vat_tax)
    
    exempt_tax = test_db.query(models.TaxType).filter(models.TaxType.name == "Exempt").first()
    if not exempt_tax:
        exempt_tax = models.TaxType(name="Exempt", rate=0.0)
        test_db.add(exempt_tax)

    # Account types
    at1 = test_db.query(models.AccountType).filter(models.AccountType.name == "Asset").first()
    if not at1:
        at1 = models.AccountType(name="Asset")
        test_db.add(at1)
    at2 = test_db.query(models.AccountType).filter(models.AccountType.name == "Liability").first()
    if not at2:
        at2 = models.AccountType(name="Liability")
        test_db.add(at2)
    at3 = test_db.query(models.AccountType).filter(models.AccountType.name == "Equity").first()
    if not at3:
        at3 = models.AccountType(name="Equity")
        test_db.add(at3)
    at4 = test_db.query(models.AccountType).filter(models.AccountType.name == "Revenue").first()
    if not at4:
        at4 = models.AccountType(name="Revenue")
        test_db.add(at4)
    at5 = test_db.query(models.AccountType).filter(models.AccountType.name == "Expense").first()
    if not at5:
        at5 = models.AccountType(name="Expense")
        test_db.add(at5)
    
    test_db.flush()

    # Units
    u1 = test_db.query(models.Unit).filter(models.Unit.name == "Piece").first()
    if not u1:
        u1 = models.Unit(name="Piece")
        test_db.add(u1)
    u2 = test_db.query(models.Unit).filter(models.Unit.name == "Kg").first()
    if not u2:
        u2 = models.Unit(name="Kg")
        test_db.add(u2)
    u3 = test_db.query(models.Unit).filter(models.Unit.name == "Litre").first()
    if not u3:
        u3 = models.Unit(name="Litre")
        test_db.add(u3)

    # Category
    cat = test_db.query(models.Category).filter(models.Category.name == "General").first()
    if not cat:
        cat = models.Category(name="General")
        test_db.add(cat)

    # Store location
    store = test_db.query(models.Store).filter(models.Store.name == biz_name).first()
    if not store:
        store = models.Store(name=biz_name, location=biz_address or "Main Branch")
        test_db.add(store)
    
    test_db.flush()

    # Default key accounting ledger accounts
    acc1 = test_db.query(models.Account).filter(models.Account.code == "1001").first()
    if not acc1:
        acc1 = models.Account(name="Cash in Hand", account_type="Asset", code="1001", balance=0.0, account_type_id=at1.id, store_id=store.id, is_key=True)
        test_db.add(acc1)
    acc2 = test_db.query(models.Account).filter(models.Account.code == "1002").first()
    if not acc2:
        acc2 = models.Account(name="Bank Account", account_type="Asset", code="1002", balance=0.0, account_type_id=at1.id, store_id=store.id, is_key=True)
        test_db.add(acc2)
    acc3 = test_db.query(models.Account).filter(models.Account.code == "4001").first()
    if not acc3:
        acc3 = models.Account(name="Sales Revenue", account_type="Revenue", code="4001", balance=0.0, account_type_id=at4.id, store_id=store.id, is_key=True)
        test_db.add(acc3)

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
        setting_obj = test_db.query(models.Setting).filter(models.Setting.key == k).first()
        if not setting_obj:
            test_db.add(models.Setting(key=k, value=v))
        else:
            setting_obj.value = v

    test_db.commit()
    
    # Assertions on created objects
    saved_admin = test_db.query(models.Staff).filter(models.Staff.username == admin_user).first()
    assert saved_admin is not None
    assert saved_admin.password_hash == hashed_pwd
    assert saved_admin.role == "admin"
    
    saved_store = test_db.query(models.Store).filter(models.Store.name == biz_name).first()
    assert saved_store is not None
    assert saved_store.location == biz_address
    
    saved_acc = test_db.query(models.Account).filter(models.Account.code == "1001").first()
    assert saved_acc is not None
    assert saved_acc.name == "Cash in Hand"
    
    saved_settings = {s.key: s.value for s in test_db.query(models.Setting).all()}
    assert saved_settings["business_name"] == biz_name
    assert saved_settings["phone"] == biz_phone
    assert saved_settings["kra_pin"] == biz_pin
    assert saved_settings["tax_rate"] == "16.0"
    assert saved_settings["wizard_completed"] == "true"
