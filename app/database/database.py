from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Jika menggunakan SQLite:
# SQLALCHEMY_DATABASE_URL = "sqlite:///./podflow.db"

# Jika menggunakan MySQL (ubah sesuai username & password Anda):
SQLALCHEMY_DATABASE_URL = "postgresql://neondb_owner:npg_98SWgRubHFYX@ep-holy-brook-az38gr1q-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()