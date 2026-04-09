import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.db import engine, Base, CalculationCache

print("Dropping calculation_cache table...")
CalculationCache.__table__.drop(engine, checkfirst=True)
print("Table dropped. init_db() will recreate it on next import.")
