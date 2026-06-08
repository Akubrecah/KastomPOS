from database import SessionLocal
import models

def seed_accounts():
    db = SessionLocal()
    
    # Expense Accounts
    expense_accounts = [
        {"name": "Maintenance & Repairs", "account_type": "Expense", "code": "EXP-001"},
        {"name": "Office Requisition", "account_type": "Expense", "code": "EXP-002"},
        {"name": "Cleaning & Toiletries", "account_type": "Expense", "code": "EXP-003"},
        {"name": "Electricity & Water", "account_type": "Expense", "code": "EXP-004"},
        {"name": "Internet & Communication", "account_type": "Expense", "code": "EXP-005"},
        {"name": "Wages & Salaries", "account_type": "Expense", "code": "EXP-006"},
        {"name": "Marketing & Ads", "account_type": "Expense", "code": "EXP-007"},
    ]
    
    # Liability Accounts
    liability_accounts = [
        {"name": "Accounts Payable", "account_type": "Liability", "code": "LIA-001"},
        {"name": "Accrued Expenses", "account_type": "Liability", "code": "LIA-002"},
        {"name": "Bank Loan", "account_type": "Liability", "code": "LIA-003"},
    ]
    
    for acc_data in expense_accounts + liability_accounts:
        existing = db.query(models.Account).filter(models.Account.name == acc_data["name"]).first()
        if not existing:
            acc = models.Account(**acc_data)
            db.add(acc)
    
    db.commit()
    db.close()
    print("Accounts seeded successfully.")

if __name__ == "__main__":
    seed_accounts()
