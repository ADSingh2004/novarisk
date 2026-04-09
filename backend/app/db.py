from sqlalchemy import create_engine, Column, Integer, Float, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
import os
import logging
import math

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
    
    # Store coordinates for easier indexing and checking
    latitude = Column(Float, index=True, nullable=False)
    longitude = Column(Float, index=True, nullable=False)
    radius_km = Column(Float, nullable=False)
    
    # Explicit tabular columns for the core metrics
    deforestation_risk = Column(Float, nullable=True)
    deforestation_confidence = Column(Float, nullable=True)
    water_stress_proxy = Column(Float, nullable=True)
    heat_island_index = Column(Float, nullable=True)
    
    # Generic payload storage for extra details like visual_layers if needed
    data = Column(JSON, nullable=True)


def init_db():
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

def is_invalid(val):
    if val is None:
        return True
    try:
        if math.isnan(val):
            return True
        if val == 0.0:
            return True
    except TypeError:
        pass
    return False

def get_cache_db(cache_key: str):
    session = SessionLocal()
    try:
        record = session.query(CalculationCache).filter_by(cache_key=cache_key).first()
        if not record:
            return None
            
        # If this is the main ESG metrics payload, check the 3 required fields
        if cache_key.startswith("esg_metrics:"):
            if (is_invalid(record.deforestation_risk) and
                is_invalid(record.water_stress_proxy) and
                is_invalid(record.heat_island_index)):
                logger.info(f"Cache entry {cache_key} has NaN/0.0 values, triggering recalculation.")
                return None
                
            # Serve the tabular columns instead of generic JSON to fulfill "tabular" usage
            return {
                "deforestation_risk": record.deforestation_risk,
                "deforestation_confidence": record.deforestation_confidence,
                "water_stress_proxy": record.water_stress_proxy,
                "heat_island_index": record.heat_island_index
            }
            
        # For non-esg_metrics (e.g. detailed deforestation), just return the JSON data
        return record.data

    except Exception as e:
        logger.error(f"Postgres cache read error: {e}")
        return None
    finally:
        session.close()

def set_cache_db(cache_key: str, latitude: float, longitude: float, radius_km: float, data: dict):
    # Notice we don't accept ttl_seconds anymore because cache is persistent
    session = SessionLocal()
    try:
        record = session.query(CalculationCache).filter_by(cache_key=cache_key).first()
        
        # Extract the key metrics if they exist
        dr = data.get("deforestation_risk")
        dc = data.get("deforestation_confidence", data.get("confidence_score"))
        ws = data.get("water_stress_proxy")
        hi = data.get("heat_island_index")
        
        if record:
            record.latitude = latitude
            record.longitude = longitude
            record.radius_km = radius_km
            record.deforestation_risk = dr
            record.deforestation_confidence = dc
            record.water_stress_proxy = ws
            record.heat_island_index = hi
            record.data = data
        else:
            new_record = CalculationCache(
                cache_key=cache_key,
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
                deforestation_risk=dr,
                deforestation_confidence=dc,
                water_stress_proxy=ws,
                heat_island_index=hi,
                data=data
            )
            session.add(new_record)
        session.commit()
    except Exception as e:
        logger.error(f"Postgres cache write error: {e}")
        session.rollback()
    finally:
        session.close()

# Auto-initialize on import so tables exist
init_db()
