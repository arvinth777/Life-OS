import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
URL = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost:5432/life_os")
if URL.startswith("postgres://"):
    URL = URL.replace("postgres://", "postgresql+psycopg://", 1)
elif URL.startswith("postgresql://"):
    URL = URL.replace("postgresql://", "postgresql+psycopg://", 1)
if not URL.startswith("postgresql+psycopg://"):
    raise RuntimeError("Life OS requires PostgreSQL")
engine = create_engine(URL, pool_pre_ping=True, pool_size=5, max_overflow=2)
