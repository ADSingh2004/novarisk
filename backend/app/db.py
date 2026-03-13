from sqlalchemy import create_engine, Column, Integer, Float, String, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@localhost:5432/novarisk")

# Use a generic thread-local session maker
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class CalculationCache(Base):
    __tablename__ = "calculation_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, unique=True, index=True, nullable=False)
    data = Column(JSON, nullable=False)
    expires_at = Column(DateTime, nullable=False)

def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

def get_cache_db(cache_key: str):
    session = SessionLocal()
    try:
        record = session.query(CalculationCache).filter_by(cache_key=cache_key).first()
        if record:
            if datetime.utcnow() > record.expires_at:
                session.delete(record)
                session.commit()
                return None
            return record.data
        return None
    except Exception as e:
        logger.error(f"Postgres cache read error: {e}")
        return None
    finally:
        session.close()

def set_cache_db(cache_key: str, data: dict, ttl_seconds: int = 86400):
    session = SessionLocal()
    try:
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        record = session.query(CalculationCache).filter_by(cache_key=cache_key).first()
        if record:
            record.data = data
            record.expires_at = expires_at
        else:
            new_record = CalculationCache(cache_key=cache_key, data=data, expires_at=expires_at)
            session.add(new_record)
        session.commit()
    except Exception as e:
        logger.error(f"Postgres cache write error: {e}")
        session.rollback()
    finally:
        session.close()

# Auto-initialize on import so tables exist
init_db()
