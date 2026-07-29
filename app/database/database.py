import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    # fallback ke variabel individual (untuk MySQL)
    db_host = os.getenv("MYSQLHOST") or os.getenv("DB_HOST")
    if db_host:
        db_user = os.getenv("MYSQLUSER", os.getenv("DB_USER"))
        db_password = os.getenv("MYSQLPASSWORD", os.getenv("DB_PASSWORD", ""))
        db_port = os.getenv("MYSQLPORT", os.getenv("DB_PORT", "3306"))
        db_name = os.getenv("MYSQLDATABASE", os.getenv("DB_NAME"))
        if not all([db_user, db_name]):
            raise ValueError("MYSQLUSER dan MYSQLDATABASE wajib diisi jika DATABASE_URL tidak ada.")
        SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        raise ValueError("DATABASE_URL atau variabel database environment wajib diisi!")

# Jika URL diawali dengan postgresql://, gunakan driver psycopg2
if SQLALCHEMY_DATABASE_URL.startswith("postgresql://"):
    # Pastikan tidak ada "postgresql+psycopg2" ganda
    if not SQLALCHEMY_DATABASE_URL.startswith("postgresql+psycopg2://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
elif SQLALCHEMY_DATABASE_URL.startswith("mysql://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

# Buat engine dengan pengaturan pool (baik untuk PostgreSQL)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()