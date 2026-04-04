"""
NovaRisk ESG - Quick Metrics Verification Script
=================================================

Simple script to quickly test and verify metrics for any single location.
Useful for rapid validation without running full test suite.

Usage:
    python quick_test_metrics.py --location "säo_paulo_brazil"
    python quick_test_metrics.py --lat -23.55 --lon -46.65
"""

import argparse
import sys
import os
from datetime import datetime
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from satellite_processing.metrics.deforestation_risk import calculate_deforestation_risk
from satellite_processing.metrics.water_stress_proxy import calculate_water_stress_proxy
from satellite_processing.metrics.urban_heat_island import calculate_urban_heat_island

# Predefined locations (from test_metrics_validation.py)
QUICK_LOCATIONS = {
    "sao_paulo": {"lat": -23.55, "lon": -46.65, "name": "São Paulo, Brazil"},
    "new_delhi": {"lat": 28.70, "lon": 77.10, "name": "New Delhi, India"},
    "jakarta": {"lat": -6.21, "lon": 106.85, "name": "Jakarta, Indonesia"},
    "los_angeles": {"lat": 34.05, "lon": -118.24, "name": "Los Angeles, USA"},
    "cerrado": {"lat": -10.2, "lon": -55.5, "name": "Cerrado, Brazil"},
    "shenyang": {"lat": 41.80, "lon": 123.92, "name": "Shenyang, China"},
    "kumasi": {"lat": 6.63, "lon": -1.63, "name": "Kumasi, Ghana"},
    "bangalore": {"lat": 12.97, "lon": 77.59, "name": "Bangalore, India"},
}


def analyze_location(lat: float, lon: float, radius_km: float = 5.0) -> dict:
    """Analyze a single location for all three metrics."""
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "location": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "metrics": {}
    }
    
    print(f"\n{'='*60}")
    print(f"Analyzing: ({lat}, {lon})")
    print(f"{'='*60}")
    
    try:
        # Deforestation
        print("\n[1/3] Deforestation Risk...", end=" ", flush=True)
        defo = calculate_deforestation_risk(lat, lon, radius_km)
        defo_score = defo.get("score", 0.0)
        result["metrics"]["deforestation_risk"] = defo_score
        status = "✓" if defo_score > 0 else "✗"
        print(f"{status} {defo_score:.2f}")
        
        # Water Stress
        print("[2/3] Water Stress Proxy...", end=" ", flush=True)
        water = calculate_water_stress_proxy(lat, lon, radius_km)
        water_score = water.get("score", 0.0)
        result["metrics"]["water_stress_proxy"] = water_score
        status = "✓" if water_score > 0 else "✗"
        print(f"{status} {water_score:.2f}")
        
        # UHI
        print("[3/3] Urban Heat Island Index...", end=" ", flush=True)
        uhi = calculate_urban_heat_island(lat, lon, facility_radius_km=1.0, rural_radius_km=10.0)
        uhi_score = uhi.get("score", 0.0)
        result["metrics"]["heat_island_index"] = uhi_score
        status = "✓" if uhi_score > 0 else "✗"
        print(f"{status} {uhi_score:.2f}")
        
        # Summary
        print(f"\n{'─'*60}")
        print("Results:")
        print(f"  Deforestation:  {defo_score:6.2f}  {get_emoji(defo_score)}")
        print(f"  Water Stress:   {water_score:6.2f}  {get_emoji(water_score)}")
        print(f"  UHI Index:      {uhi_score:6.2f}  {get_emoji(uhi_score)}")
        print(f"{'─'*60}")
        
        all_positive = (defo_score > 0) and (water_score > 0) and (uhi_score > 0)
        status_emoji = "✓ PASS" if all_positive else "⚠ PARTIAL"
        print(f"Overall Status: {status_emoji}")
        result["status"] = "PASS" if all_positive else "PARTIAL"
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        result["status"] = "FAILED"
        result["error"] = str(e)
    
    return result


def get_emoji(score: float) -> str:
    """Return emoji representation of score."""
    if score == 0:
        return "✗ (Zero)"
    elif score < 25:
        return "⚠ (Low)"
    elif score < 50:
        return "🟡 (Moderate)"
    elif score < 75:
        return "🔴 (High)"
    else:
        return "🔴🔴 (Critical)"


def main():
    parser = argparse.ArgumentParser(
        description="QuickTest NovaRisk ESG metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python quick_test_metrics.py --location sao_paulo
  python quick_test_metrics.py --lat -23.55 --lon -46.65
  python quick_test_metrics.py --list
        """
    )
    
    parser.add_argument("--location", type=str, help="Predefined location key")
    parser.add_argument("--lat", type=float, help="Latitude")
    parser.add_argument("--lon", type=float, help="Longitude")
    parser.add_argument("--radius", type=float, default=5.0, help="Analysis radius in km (default: 5.0)")
    parser.add_argument("--list", action="store_true", help="List all predefined locations")
    parser.add_argument("--all", action="store_true", help="Test all predefined locations")
    parser.add_argument("--export", type=str, help="Export results to JSON file")
    
    args = parser.parse_args()
    
    # List locations
    if args.list:
        print("\nPredefined Test Locations:")
        print("─" * 60)
        for key, data in QUICK_LOCATIONS.items():
            print(f"  {key:15} → {data['name']:30} ({data['lat']:7.2f}, {data['lon']:7.2f})")
        print("─" * 60)
        print(f"\nUsage: python quick_test_metrics.py --location {list(QUICK_LOCATIONS.keys())[0]}")
        return
    
    results = []
    
    # Test all locations
    if args.all:
        print(f"\n{'='*60}")
        print("Testing ALL Predefined Locations")
        print(f"{'='*60}")
        for key, data in QUICK_LOCATIONS.items():
            result = analyze_location(data["lat"], data["lon"], args.radius)
            result["location_key"] = key
            result["location_name"] = data["name"]
            results.append(result)
        
        # Summary
        print(f"\n\n{'='*60}")
        print("BATCH SUMMARY")
        print(f"{'='*60}")
        passed = sum(1 for r in results if r["status"] == "PASS")
        partial = sum(1 for r in results if r["status"] == "PARTIAL")
        total = len(results)
        
        for r in results:
            name = r.get("location_name", f"({r['location']['lat']}, {r['location']['lon']})")
            status = r["status"]
            defo = r["metrics"].get("deforestation_risk", 0)
            water = r["metrics"].get("water_stress_proxy", 0)
            uhi = r["metrics"].get("heat_island_index", 0)
            print(f"  {name:35} {status:8} ({defo:5.1f}, {water:5.1f}, {uhi:5.1f})")
        
        print(f"{'─'*60}")
        print(f"Total: {total} | Passed: {passed} | Partial: {partial} | Pass Rate: {(passed/total)*100:.0f}%")
        
    # Test single predefined location
    elif args.location:
        if args.location.lower() not in QUICK_LOCATIONS:
            print(f"Unknown location: {args.location}")
            print(f"Available: {', '.join(QUICK_LOCATIONS.keys())}")
            return
        
        data = QUICK_LOCATIONS[args.location.lower()]
        print(f"\n📍 {data['name']}")
        result = analyze_location(data["lat"], data["lon"], args.radius)
        result["location_key"] = args.location
        result["location_name"] = data["name"]
        results.append(result)
    
    # Test custom coordinates
    elif args.lat is not None and args.lon is not None:
        print(f"\n📍 Custom Location")
        result = analyze_location(args.lat, args.lon, args.radius)
        results.append(result)
    
    else:
        parser.print_help()
        print("\nQuick start:")
        print("  python quick_test_metrics.py --list           # See available locations")
        print("  python quick_test_metrics.py --location sao_paulo  # Test São Paulo")
        print("  python quick_test_metrics.py --all            # Test all locations")
        return
    
    # Export if requested
    if args.export and results:
        with open(args.export, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n✓ Results exported to: {args.export}")


if __name__ == "__main__":
    main()
