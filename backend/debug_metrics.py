import sys
import os

sys.path.append(os.path.abspath(".."))

from satellite_processing.metrics.deforestation_risk import calculate_deforestation_risk
from satellite_processing.metrics.water_stress_fusion import calculate_fused_water_stress_proxy
from satellite_processing.metrics.urban_heat_island import calculate_urban_heat_island

lat, lon = 35.6762, 139.6503
print("=== DEFORESTATION ===")
try:
    print(calculate_deforestation_risk(lat, lon))
except Exception as e:
    print(f"Error: {e}")

print("=== WATER STRESS ===")
try:
    print(calculate_fused_water_stress_proxy(lat, lon))
except Exception as e:
    print(f"Error: {e}")

print("=== UHI ===")
try:
    print(calculate_urban_heat_island(lat, lon))
except Exception as e:
    print(f"Error: {e}")
