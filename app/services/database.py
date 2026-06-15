import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

from pathlib import Path

def get_data_dir():
    appName = "KastomPOS"
    if sys.platform == "win32":
        base_dir = os.getenv("PROGRAMDATA")
        if not base_dir:
            base_dir = os.getenv("APPDATA")
        if not base_dir:
            base_dir = str(Path.home() / ".kastompos")
        else:
            base_dir = os.path.join(base_dir, appName)
    elif sys.platform == "darwin":
        base_dir = str(Path.home() / "Library" / "Application Support" / appName)
    else:
        base_dir = str(Path.home() / ".kastompos")
    
    try:
        os.makedirs(base_dir, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create data directory {base_dir}: {e}")
    return base_dir

def get_database_path():
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url
    return f"sqlite:///{os.path.join(get_data_dir(), 'pos.db')}"

SQLALCHEMY_DATABASE_URL = get_database_path()

# SQLite needs 'check_same_thread: False'
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

def run_migrations(db_engine):
    try:
        from sqlalchemy import text
        with db_engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(products)")).fetchall()
            columns = [r[1] for r in res]
            if columns and "expiry_date" not in columns:
                conn.execute(text("ALTER TABLE products ADD COLUMN expiry_date DATE"))
                conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
