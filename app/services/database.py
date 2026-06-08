import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

def get_database_path():
    # If running as a PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # On Windows, os.getenv('APPDATA') usually points to C:\Users\Name\AppData\Roaming
        app_data = os.getenv('APPDATA')
        if app_data:
            base_dir = os.path.join(app_data, 'KastomPOS')
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
            return f"sqlite:///{os.path.join(base_dir, 'pos.db')}"
    
    # Default to local SQLite if no DATABASE_URL is provided
    return os.getenv("DATABASE_URL", "sqlite:///./pos.db")

SQLALCHEMY_DATABASE_URL = get_database_path()

# SQLite needs 'check_same_thread: False'
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
