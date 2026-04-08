import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

_host = os.getenv("POS_DB_HOST")
_port = os.getenv("POS_DB_PORT", "3306")
_name = os.getenv("POS_DB_NAME")
_user = os.getenv("POS_DB_USER")
_pass = os.getenv("POS_DB_PASSWORD")

if not all([_host, _name, _user, _pass]):
    raise RuntimeError("POS_DB_* variables not found in .env")

POS_DATABASE_URL = f"mysql+pymysql://{_user}:{_pass}@{_host}:{_port}/{_name}"

pos_engine = create_engine(
    POS_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=0,
)

PosSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=pos_engine,
)


def get_pos_db():
    db = PosSessionLocal()
    try:
        yield db
    finally:
        db.close()
