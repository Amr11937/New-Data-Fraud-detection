import os
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Example: postgresql+psycopg2://USER:PASSWORD@HOST:5432/DBNAME
DATABASE_URL = os.environ["DATABASE_URL"]

# Unlike the old Lambda deployment (pool_size=2, one small pool per
# short-lived execution environment), this process is long-running and
# handles all request concurrency itself, so the pool can be sized like
# a normal web service. Tune pool_size to your ECS/EC2 instance count
# and RDS max_connections, not per-request traffic.
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=1800,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
