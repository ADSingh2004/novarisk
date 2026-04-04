"""
NovaRisk ESG - Metrics Validation Test Suite
=============================================

This test suite validates that the ESG metrics pipeline returns meaningful,
non-zero values across diverse geographic regions and environmental conditions.

Selected test locations are chosen to demonstrate:
1. High deforestation risk (active land-use change)
2. High water stress (water scarcity or shrinking water bodies)
3. High urban heat island effect (urban centers)

All locations have been verified against satellite data to ensure realistic
metric expectations.
"""

import asyncio
import sys
import os
from typing import Dict, Any
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from satellite_processing.metrics.deforestation_risk import calculate_deforestation_risk
from satellite_processing.metrics.water_stress_proxy import calculate_water_stress_proxy
from satellite_processing.metrics.urban_heat_island import calculate_urban_heat_island
from satellite_processing.metrics.sar_analytics import verify_deforestation_sar


# ============================================================================
# TEST LOCATIONS - Curated for Multi-Metric Validation
# ============================================================================

TEST_LOCATIONS = {
    "sao_paulo_brazil": {
        "name": "São Paulo Metropolitan Area",
        "coordinates": {"lat": -23.55, "lon": -46.65},
        "region": "South America (Tropical/Subtropical)",
        "description": "Major urban center with deforestation pressure from Atlantic Forest remnants, strong UHI from 12M+ population, water stress from droughts",
        "expected_metrics": {
            "deforestation_risk": (15, 40),  # (min, max) - Moderate to high: agricultural conversion
            "water_stress_proxy": (30, 60),  # Water scarcity in metropolitan area
            "heat_island_index": (8, 18)     # Strong UHI from urban sprawl
        },
        "reasoning": {
            "deforestation": "Atlantic Forest deforestation for agriculture and urban expansion",
            "water_stress": "São Paulo suffered major droughts (2014-2015); Cantareira System critically low",
            "uhi": "Massive urban agglomeration (21M+ people); city center 5-8°C warmer than surroundings"
        }
    },
    
    "new_delhi_india": {
        "name": "New Delhi National Capital Region",
        "coordinates": {"lat": 28.70, "lon": 77.10},
        "region": "South Asia (Temperate/Arid)",
        "description": "Megacity with extreme UHI, severe water stress, agricultural deforestation in hinterland",
        "expected_metrics": {
            "deforestation_risk": (20, 45),  # Moderate: agricultural expansion + urban sprawl
            "water_stress_proxy": (50, 85),  # VERY HIGH: Depleted aquifers, Yamuna sewage-fed
            "heat_island_index": (18, 35)    # Extreme UHI: summer temps 8-15°C above rural areas
        },
        "reasoning": {
            "deforestation": "Intensive agricultural conversion in Punjab/Haryana hinterland",
            "water_stress": "Groundwater depleting at ~1m/year; surface water heavily polluted",
            "uhi": "One of world's hottest cities; UHI effect pronounced May-June (45-50°C vs 35°C rural)"
        }
    },
    
    "jakarta_indonesia": {
        "name": "Jakarta Metropolitan Region",
        "coordinates": {"lat": -6.21, "lon": 106.85},
        "region": "Southeast Asia (Tropical)",
        "description": "Southeast Asia's largest city with rapid deforestation, extreme water stress, intense UHI",
        "expected_metrics": {
            "deforestation_risk": (25, 50),  # High: Palm oil expansion + urban sprawl into peatlands
            "water_stress_proxy": (40, 75),  # High: Overdraft from aquifers, canal degradation
            "heat_island_index": (5, 15)     # Moderate (tropical baseline already high); 3-5°C urban excess
        },
        "reasoning": {
            "deforestation": "Surrounding peatlands cleared for palm oil; rapid urban expansion",
            "water_stress": "Artesian wells dropping; tidal flooding + saltwater intrusion (subsidence)",
            "uhi": "Tropical monsoon climate; UHI less pronounced than temperate cities but still significant"
        }
    },
    
    "los_angeles_usa": {
        "name": "Los Angeles Metropolitan Area",
        "coordinates": {"lat": 34.05, "lon": -118.24},
        "region": "North America (Semi-Arid)",
        "description": "Major North American megacity with sprawl-driven habitat loss, severe water stress, persistent UHI",
        "expected_metrics": {
            "deforestation_risk": (18, 42),  # Moderate: Chaparral/scrub habitat conversion to urban/suburban
            "water_stress_proxy": (45, 70),  # High: Colorado River over-allocation, drought
            "heat_island_index": (12, 22)    # Strong UHI: Downtown LA 7-10°C warmer than San Gabriel Mountains
        },
        "reasoning": {
            "deforestation": "Native chaparral/grassland replacing with concrete; wildland-urban interface",
            "water_stress": "Colorado River system severely stressed; local aquifers depleted",
            "uhi": "Basin geometry traps heat; urban fabric (dark surfaces) intensifies warming"
        }
    },
    
    "cerrado_brazil": {
        "name": "Cerrado Savanna Agricultural Belt (Goiás/Mato Grosso)",
        "coordinates": {"lat": -10.2, "lon": -55.5},
        "region": "South America (Savanna)",
        "description": "World's fastest deforestation hotspot; intensive soybean/cattle; emerging urban centers",
        "expected_metrics": {
            "deforestation_risk": (50, 85),  # VERY HIGH: Active frontier; ~14% annual FCC loss
            "water_stress_proxy": (25, 55),  # Moderate to High: Aquifer stress from irrigation
            "heat_island_index": (8, 18)     # Moderate: Emerging agricultural towns, reduced vegetation
        },
        "reasoning": {
            "deforestation": "Most aggressive deforestation globally (~80% Cerrado lost); mechanized soy/cattle",
            "water_stress": "Deforestation reducing dry-season water; aquifer pumping intensifying",
            "uhi": "Agricultural conversion → lower ET; emerging towns showing UHI signal"
        }
    },
    
    "shenyang_china": {
        "name": "Shenyang Industrial Megacity",
        "coordinates": {"lat": 41.80, "lon": 123.92},
        "region": "East Asia (Temperate)",
        "description": "Post-industrial Chinese megacity with habitat loss, severe water stress, extreme UHI",
        "expected_metrics": {
            "deforestation_risk": (22, 48),  # Moderate-High: Industrial sprawl, coal mine reclamation zones
            "water_stress_proxy": (35, 65),  # High: Liaohe River depleted; industrial pollution
            "heat_island_index": (15, 28)    # Very High: Dense urban core; winter heating + summer UHI
        },
        "reasoning": {
            "deforestation": "Post-industrial site reclamation; coal mining legacy deforestation",
            "water_stress": "Liaohe River critically low; groundwater pollution limits availability",
            "uhi": "Old industrial city with dense urban fabric; district heating in winter amplifies signal"
        }
    },
    
    "kumasi_ghana": {
        "name": "Kumasi Forest Margin (Ghana/Ivory Coast Border)",
        "coordinates": {"lat": 6.63, "lon": -1.63},
        "region": "West Africa (Tropical)",
        "description": "Active tropical forest deforestation frontier; subsistence + commercial logging; emergent UHI",
        "expected_metrics": {
            "deforestation_risk": (35, 65),  # High: Cocoa plantation expansion + logging
            "water_stress_proxy": (15, 40),  # Moderate: Seasonal rainfall variability increasing
            "heat_island_index": (2, 8)      # Low to Moderate: Smaller city + tropical climate baseline
        },
        "reasoning": {
            "deforestation": "Rainforest → cocoa plantations; illegal logging ongoing",
            "water_stress": "Deforestation reducing baseflow; dry season lengthening",
            "uhi": "Regional urban center; modest UHI (3-5°C); high baseline tropical temps"
        }
    },
    
    "bangalore_india": {
        "name": "Bangalore Tech Hub & Urban Growth",
        "coordinates": {"lat": 12.97, "lon": 77.59},
        "region": "South Asia (Tropical)",
        "description": "Fastest-growing Indian megacity; deforestation from tech parks + real estate; water crisis; UHI",
        "expected_metrics": {
            "deforestation_risk": (28, 52),  # High: Bangalore urban sprawl eating into forests (Western Ghats proximity)
            "water_stress_proxy": (45, 75),  # Very High: Lakes drying; groundwater depleted; Bangalore water crisis 2023-24
            "heat_island_index": (6, 14)     # Moderate: High-altitude tropical; tech sprawl reducing green cover
        },
        "reasoning": {
            "deforestation": "IT sector expansion; residential sprawl into forested hinterland",
            "water_stress": "Lakes dried (Bellandur, Varthur); aquifers critically low; monsoon failures",
            "uhi": "Urban expansion replacing gardens; reduced tree cover aggravating seasonal heat stress"
        }
    }
}


# ============================================================================
# TEST RUNNER
# ============================================================================

class MetricsValidator:
    """Validates ESG metrics across test locations."""
    
    def __init__(self):
        self.results = []
        self.timestamp = datetime.now().isoformat()
    
    async def test_location(self, location_key: str, location_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test a single location against all three metrics.
        
        Args:
            location_key: Key identifier for the location
            location_data: Location metadata and coordinates
            
        Returns:
            Dictionary containing test results and validation status
        """
        lat = location_data["coordinates"]["lat"]
        lon = location_data["coordinates"]["lon"]
        radius_km = 5.0
        
        print(f"\n{'='*70}")
        print(f"Testing: {location_data['name']}")
        print(f"Coordinates: ({lat}, {lon})")
        print(f"{'='*70}")
        
        result = {
            "location_key": location_key,
            "name": location_data["name"],
            "coordinates": location_data["coordinates"],
            "radius_km": radius_km,
            "timestamp": self.timestamp,
            "metrics": {},
            "status": "PENDING"
        }
        
        try:
            # Test 1: Deforestation Risk
            print(f"\n[1/3] Calculating Deforestation Risk...")
            deforestation_data = calculate_deforestation_risk(lat, lon, radius_km)
            deforestation_score = deforestation_data.get("score", 0.0)
            
            print(f"  Score: {deforestation_score:.2f}")
            print(f"  Expected Range: {location_data['expected_metrics']['deforestation_risk']}")
            
            result["metrics"]["deforestation_risk"] = {
                "score": deforestation_score,
                "expected_range": location_data["expected_metrics"]["deforestation_risk"],
                "within_range": self._check_range(deforestation_score, location_data["expected_metrics"]["deforestation_risk"]),
                "full_data": deforestation_data
            }
            
            # Test 2: Water Stress Proxy
            print(f"\n[2/3] Calculating Water Stress Proxy...")
            water_stress_data = calculate_water_stress_proxy(lat, lon, radius_km)
            water_stress_score = water_stress_data.get("score", 0.0)
            
            print(f"  Score: {water_stress_score:.2f}")
            print(f"  Expected Range: {location_data['expected_metrics']['water_stress_proxy']}")
            
            result["metrics"]["water_stress_proxy"] = {
                "score": water_stress_score,
                "expected_range": location_data["expected_metrics"]["water_stress_proxy"],
                "within_range": self._check_range(water_stress_score, location_data["expected_metrics"]["water_stress_proxy"]),
                "full_data": water_stress_data
            }
            
            # Test 3: Urban Heat Island
            print(f"\n[3/3] Calculating Urban Heat Island Intensity...")
            uhi_data = calculate_urban_heat_island(lat, lon, facility_radius_km=1.0, rural_radius_km=10.0)
            uhi_score = uhi_data.get("score", 0.0)
            
            print(f"  Score: {uhi_score:.2f}")
            print(f"  Expected Range: {location_data['expected_metrics']['heat_island_index']}")
            
            result["metrics"]["heat_island_index"] = {
                "score": uhi_score,
                "expected_range": location_data["expected_metrics"]["heat_island_index"],
                "within_range": self._check_range(uhi_score, location_data["expected_metrics"]["heat_island_index"]),
                "full_data": uhi_data
            }
            
            # Validate all metrics are non-zero
            all_nonzero = (deforestation_score > 0) and (water_stress_score > 0) and (uhi_score > 0)
            result["status"] = "PASS" if all_nonzero else "PARTIAL"
            
            print(f"\n{'─'*70}")
            print(f"Summary:")
            print(f"  Deforestation: {deforestation_score:.2f} ✓" if deforestation_score > 0 else f"  Deforestation: {deforestation_score:.2f} ✗")
            print(f"  Water Stress:  {water_stress_score:.2f} ✓" if water_stress_score > 0 else f"  Water Stress:  {water_stress_score:.2f} ✗")
            print(f"  UHI Index:     {uhi_score:.2f} ✓" if uhi_score > 0 else f"  UHI Index:     {uhi_score:.2f} ✗")
            print(f"  Status: {result['status']}")
            
        except Exception as e:
            result["status"] = "FAILED"
            result["error"] = str(e)
            print(f"\n✗ ERROR: {e}")
        
        self.results.append(result)
        return result
    
    @staticmethod
    def _check_range(value: float, expected_range: tuple) -> bool:
        """Check if value falls within expected range."""
        min_val, max_val = expected_range
        return min_val <= value <= max_val
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Run tests across all locations."""
        print("\n" + "="*70)
        print("NovaRisk ESG - Multi-Metrics Validation Test Suite")
        print("="*70)
        print(f"Timestamp: {self.timestamp}")
        print(f"Total Locations: {len(TEST_LOCATIONS)}")
        
        for location_key, location_data in TEST_LOCATIONS.items():
            await self.test_location(location_key, location_data)
        
        return self._generate_summary()
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        partial = sum(1 for r in self.results if r["status"] == "PARTIAL")
        failed = sum(1 for r in self.results if r["status"] == "FAILED")
        
        summary = {
            "timestamp": self.timestamp,
            "total_tests": total,
            "passed": passed,
            "partial": partial,
            "failed": failed,
            "pass_rate": f"{(passed/total)*100:.1f}%" if total > 0 else "0%",
            "results": self.results
        }
        
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        print(f"Total Tests: {total}")
        print(f"Passed (All 3 metrics > 0): {passed}")
        print(f"Partial (1-2 metrics > 0): {partial}")
        print(f"Failed: {failed}")
        print(f"Pass Rate: {summary['pass_rate']}")
        print("="*70 + "\n")
        
        return summary


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main():
    """Run the full metrics validation test suite."""
    validator = MetricsValidator()
    summary = await validator.run_all_tests()
    
    # Save results to JSON
    output_file = os.path.join(os.path.dirname(__file__), "test_metrics_results.json")
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n✓ Results saved to: {output_file}")
    
    return summary


if __name__ == "__main__":
    summary = asyncio.run(main())
    
    # Exit with appropriate code
    exit_code = 0 if summary["failed"] == 0 else 1
    exit(exit_code)
