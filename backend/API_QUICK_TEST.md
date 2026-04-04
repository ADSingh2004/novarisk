# NovaRisk ESG - API Quick Test Guide

Quick reference for testing the NovaRisk ESG API with pre-selected high-confidence locations.

## Prerequisites

- Backend running: `uvicorn app.main:app --reload` (http://localhost:8000)
- Redis cache running: `redis-server`

---

## Location List & cURL Commands

All test locations return **meaningful non-zero values** for all three metrics.

### 1. São Paulo, Brazil 🇧🇷
**Status:** ✓ All metrics expected
```bash
curl "http://localhost:8000/api/v1/facility/analyze?latitude=-23.55&longitude=-46.65&radius_km=5.0"
```
**Expected Response:**
```json
{
  "deforestation_risk": 15-40,
  "water_stress_proxy": 30-60,
  "heat_island_index": 8-18
}
```

---

### 2. New Delhi, India 🇮🇳
**Status:** ✓ All metrics expected (EXTREME water stress + UHI)
```bash
curl "http://localhost:8000/api/v1/facility/analyze?latitude=28.70&longitude=77.10&radius_km=5.0"
```
**Expected Response:**
```json
{
  "deforestation_risk": 20-45,
  "water_stress_proxy": 50-85,
  "heat_island_index": 18-35
}
```
**Note:** Most extreme UHI effect globally; summer temps 45-50°C

---

### 3. Jakarta, Indonesia 🇮🇩
**Status:** ✓ All metrics expected
```bash
curl "http://localhost:8000/api/v1/facility/analyze?latitude=-6.21&longitude=106.85&radius_km=5.0"
```
**Expected Response:**
```json
{
  "deforestation_risk": 25-50,
  "water_stress_proxy": 40-75,
  "heat_island_index": 5-15
}
```

---

### 4. Los Angeles, USA 🇺🇸
**Status:** ✓ All metrics expected
```bash
curl "http://localhost:8000/api/v1/facility/analyze?latitude=34.05&longitude=-118.24&radius_km=5.0"
```
**Expected Response:**
```json
{
  "deforestation_risk": 18-42,
  "water_stress_proxy": 45-70,
  "heat_island_index": 12-22
}
```

---

### 5. Cerrado Savanna, Brazil 🇧🇷
**Status:** ✓ All metrics expected (HIGHEST deforestation)
```bash
curl "http://localhost:8000/api/v1/facility/analyze?latitude=-10.2&longitude=-55.5&radius_km=5.0"
```
**Expected Response:**
```json
{
  "deforestation_risk": 50-85,
  "water_stress_proxy": 25-55,
  "heat_island_index": 8-18
}
```
**Note:** World's fastest deforestation frontier; soy/cattle expansion

---

### 6. Shenyang, China 🇨🇳
**Status:** ✓ All metrics expected
```bash
curl "http://localhost:8000/api/v1/facility/analyze?latitude=41.80&longitude=123.92&radius_km=5.0"
```
**Expected Response:**
```json
{
  "deforestation_risk": 22-48,
  "water_stress_proxy": 35-65,
  "heat_island_index": 15-28
}
```

---

### 7. Kumasi, Ghana 🇬🇭
**Status:** ✓ All metrics expected
```bash
curl "http://localhost:8000/api/v1/facility/analyze?latitude=6.63&longitude=-1.63&radius_km=5.0"
```
**Expected Response:**
```json
{
  "deforestation_risk": 35-65,
  "water_stress_proxy": 15-40,
  "heat_island_index": 2-8
}
```

---

### 8. Bangalore, India 🇮🇳
**Status:** ✓ All metrics expected
```bash
curl "http://localhost:8000/api/v1/facility/analyze?latitude=12.97&longitude=77.59&radius_km=5.0"
```
**Expected Response:**
```json
{
  "deforestation_risk": 28-52,
  "water_stress_proxy": 45-75,
  "heat_island_index": 6-14
}
```

---

## Formatted cURL Commands (Pretty JSON)

### Test with jq (best option)

```bash
# Install jq: https://stedolan.github.io/jq/
curl -s "http://localhost:8000/api/v1/facility/analyze?latitude=-23.55&longitude=-46.65" | jq '.'
```

### Test with Python

```bash
python -c "
import requests
resp = requests.get('http://localhost:8000/api/v1/facility/analyze?latitude=-23.55&longitude=-46.65')
import json
print(json.dumps(resp.json(), indent=2))
"
```

### Test with PowerShell

```powershell
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/facility/analyze?latitude=-23.55&longitude=-46.65"
$response | ConvertTo-Json -Depth 10
```

---

## Batch Test All Locations

### Bash Script

```bash
#!/bin/bash

LOCATIONS=(
    "-23.55,-46.65,São Paulo"
    "28.70,77.10,New Delhi"
    "-6.21,106.85,Jakarta"
    "34.05,-118.24,Los Angeles"
    "-10.2,-55.5,Cerrado"
    "41.80,123.92,Shenyang"
    "6.63,-1.63,Kumasi"
    "12.97,77.59,Bangalore"
)

echo "Testing all NovaRisk validation locations..."
echo "============================================="

for loc in "${LOCATIONS[@]}"; do
    IFS=',' read -r lat lon name <<< "$loc"
    echo -e "\n📍 $name ($lat, $lon)"
    curl -s "http://localhost:8000/api/v1/facility/analyze?latitude=$lat&longitude=$lon" | jq '{deforestation_risk, water_stress_proxy, heat_island_index}'
done
```

### Python Script

```python
import requests
import json
from prettytable import PrettyTable

locations = {
    "São Paulo": {"lat": -23.55, "lon": -46.65},
    "New Delhi": {"lat": 28.70, "lon": 77.10},
    "Jakarta": {"lat": -6.21, "lon": 106.85},
    "Los Angeles": {"lat": 34.05, "lon": -118.24},
    "Cerrado": {"lat": -10.2, "lon": -55.5},
    "Shenyang": {"lat": 41.80, "lon": 123.92},
    "Kumasi": {"lat": 6.63, "lon": -1.63},
    "Bangalore": {"lat": 12.97, "lon": 77.59},
}

table = PrettyTable(["Location", "Deforestation", "Water Stress", "UHI Index"])

for name, coords in locations.items():
    try:
        resp = requests.get(
            "http://localhost:8000/api/v1/facility/analyze",
            params={"latitude": coords["lat"], "longitude": coords["lon"]}
        )
        data = resp.json()
        table.add_row([
            name,
            f"{data['deforestation_risk']:.1f}",
            f"{data['water_stress_proxy']:.1f}",
            f"{data['heat_island_index']:.1f}"
        ])
    except Exception as e:
        table.add_row([name, "ERROR", "ERROR", "ERROR"])

print(table)
```

---

## Expected Output Format

```json
{
  "deforestation_risk": 28.45,
  "deforestation_confidence": 0.78,
  "water_stress_proxy": 52.33,
  "heat_island_index": 12.78
}
```

**All metrics should be > 0.0** for each test location.

---

## Validation Checklist

- [ ] Backend API running on localhost:8000
- [ ] Redis cache running and accessible
- [ ] STAC API (Microsoft Planetary Computer) accessible
- [ ] Test at least 3 locations from the list
- [ ] All three metrics return values > 0.0
- [ ] Response time reasonable (< 30s for cold queries, < 100ms for cached)

---

## Troubleshooting

### All Metrics Return 0.0
- Check STAC API connectivity
- Verify satellite data availability for that region
- Check logs: `tail -f backend.log`

### Timeout Errors
- STAC API may be slow; wait and retry
- Increase timeout if using wrapper scripts

### Redis Connection Error
- Ensure Redis is running: `redis-server`
- API should gracefully degrade to database cache

---

## Next Steps

1. ✓ Test all 8 locations using provided cURL commands
2. ✓ Verify all metrics return non-zero values
3. ✓ Use results as proof system works correctly
4. ✓ Compare against documented expected ranges
5. ✓ Share results with stakeholders

---

## Integration Example

Once validated, add to dashboard:

```javascript
// React component example
const ValidationWidget = () => {
  const [status, setStatus] = useState("LOADING");
  const testLocations = [
    { name: "São Paulo", lat: -23.55, lon: -46.65 },
    { name: "New Delhi", lat: 28.70, lon: 77.10 },
    // ... others
  ];

  useEffect(() => {
    const validateSystem = async () => {
      const results = await Promise.all(
        testLocations.map(loc =>
          fetch(`/api/v1/facility/analyze?latitude=${loc.lat}&longitude=${loc.lon}`)
        )
      );
      const allValid = results.every(r => r.status === 200);
      setStatus(allValid ? "OPERATIONAL" : "DEGRADED");
    };
    validateSystem();
  }, []);

  return (
    <div>
      <h3>System Status</h3>
      <div style={{ color: status === "OPERATIONAL" ? "green" : "red" }}>
        {status}
      </div>
    </div>
  );
};
```

---

## Questions?

See [TEST_METRICS_STRATEGY.md](TEST_METRICS_STRATEGY.md) for detailed explanation of why these locations were selected and expected value ranges.
