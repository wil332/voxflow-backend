from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Jika menggunakan SQLite:
# SQLALCHEMY_DATABASE_URL = "sqlite:///./podflow.db"

# Jika menggunakan MySQL (ubah sesuai username & password Anda):
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:@localhost:3306/podflow_db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()