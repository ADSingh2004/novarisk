# NovaRisk ESG API - Quick Reference Guide

## Core Analysis Endpoint

### `/api/v1/facility/analyze` (GET)
**Analyzes a facility and returns ESG risk metrics**

```
GET /api/v1/facility/analyze
  ?latitude={float}
  &longitude={float}
  &radius_km={float, default=5.0}
  &recalculate={bool, default=false}
```

**Response** (ESGMetricsResponse):
```json
{
  "deforestation_risk": 25.4,
  "water_stress_proxy": 18.9,
  "heat_island_index": 3.2,
  "sar_water_area": 0.12,
  "sar_water_change": -0.05,
  "forest_percentage": 65.2,
  "water_percentage": 8.4,
  "urban_percentage": 12.1,
  "agriculture_percentage": 10.8,
  "barren_percentage": 3.5
}
```

**Performance**:
- First request (cache miss): 45-60 seconds
- Subsequent requests: ~45ms (cached)
- Parallel computation of all 4 metrics

**Caching**:
- Results cached for 24 hours in Redis
- Set `recalculate=true` to force recomputation

---

## Reporting Endpoints

### `/api/v1/facility/report/pdf` (GET)
**Returns PDF report with ESG metrics**

```
GET /api/v1/facility/report/pdf
  ?latitude={float}
  &longitude={float}
  &radius_km={float, default=5.0}
```

**Returns**: PDF file  
**Filename**: `NovaRisk_ESG_Report_{latitude}_{longitude}.pdf`

**Content**:
- Facility location coordinates
- ESG risk scores table
- Risk level assessment (Good/Medium/High)
- Methodology explanation

---

### `/api/v1/facility/report/csv` (GET)
**Returns CSV report with ESG metrics**

```
GET /api/v1/facility/report/csv
  ?latitude={float}
  &longitude={float}
  &radius_km={float, default=5.0}
```

**Returns**: CSV file  
**Filename**: `NovaRisk_ESG_Report_{latitude}_{longitude}.csv`

**Content**:
- Facility coordinates
- Generated timestamp
- Metric scores and status levels

---

### `/api/v1/facility/report/ai-land-features-pdf` (GET) ⭐ NEW
**Returns detailed PDF report for AI-predicted land cover features**

```
GET /api/v1/facility/report/ai-land-features-pdf
  ?latitude={float}
  &longitude={float}
  &radius_km={float, default=5.0}
```

**Returns**: PDF file  
**Filename**: `NovaRisk_AI_LandCover_{latitude}_{longitude}.pdf`

**Content**:
- Land cover classification results (5 classes)
  - Forest percentage
  - Surface Water percentage
  - Urban/Built-up percentage
  - Agriculture percentage
  - Barren/Sparse percentage
- Detailed class descriptions
- AI methodology (U-Net with ResNet18)
- Key insights and coverage analysis
- Ground-truth validation disclaimer

**Features**:
- Color-coded tables for easy reading
- Methodology section explaining the AI model
- Class-by-class interpretation guide
- Dominant land cover identification

**Note**: Requires `/facility/analyze` to have been called first. If no cached data exists, automatically triggers analysis.

---

## Explainability Endpoint

### `/api/v1/facility/explain` (GET)
**Returns detailed explainability data for metrics**

```
GET /api/v1/facility/explain
  ?latitude={float}
  &longitude={float}
  &radius_km={float, default=5.0}
```

**Response** (ExplainResponse):
```json
{
  "formulas_used": [
    "NDVI = (NIR - Red) / (NIR + Red)",
    "NDWI = (Green - NIR) / (Green + NIR)",
    "AI Land Cover = U-Net Segmentation with MobileNetV3 Encoder"
  ],
  "input_band_values": {
    "mean_ndvi": 0.45,
    "mean_ndwi": 0.12,
    "ndvi_array": [[0.4, 0.41, ...], ...],
    "ndwi_array": [[0.1, 0.11, ...], ...]
  },
  "step_by_step_calculations": [
    "1. Fetched Sentinel-2 STAC items for the bounding box.",
    "2. Computed median composite over the time dimension to remove clouds.",
    ...
  ],
  "interpretation_logic": "The raw NDVI/NDWI arrays...",
  "classification_map": [[0, 1, 2, ...], [0, 1, 2, ...], ...]
}
```

**Required**: Must call `/facility/analyze` first to populate cache

---

## Facility Registration (Legacy)

### `/api/v1/facility/register` (POST)
**Registers a facility before analysis**

```
POST /api/v1/facility/register
Content-Type: application/json

{
  "name": "Tesla Gigafactory",
  "latitude": 35.6762,
  "longitude": 139.6503
}
```

**Response**:
```json
{
  "facility_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Facility 'Tesla Gigafactory' registered successfully."
}
```

**Note**: Currently returns mock UUID. Database integration TODO.

---

## History Endpoint

### `/api/v1/facility/history` (GET)
**Returns historical satellite metrics for a facility**

```
GET /api/v1/facility/history
  ?latitude={float}
  &longitude={float}
```

**Response**:
```json
{
  "history": [
    {"year": 2021, "deforestation": 1.2, "water_stress": 3.4, "uhi": 1.1},
    {"year": 2022, "deforestation": 2.5, "water_stress": 4.1, "uhi": 1.5},
    {"year": 2023, "deforestation": 3.8, "water_stress": 4.8, "uhi": 2.0}
  ]
}
```

**Note**: Currently returns mock data. Time-series database integration TODO.

---

## Usage Examples

### Example 1: Full Analysis + PDF Export

```bash
# 1. Analyze facility
curl -X GET "http://localhost:8000/api/v1/facility/analyze?latitude=35.6762&longitude=139.6503&radius_km=5.0" \
  -H "Accept: application/json"

# 2. Export comprehensive ESG report
curl -X GET "http://localhost:8000/api/v1/facility/report/pdf?latitude=35.6762&longitude=139.6503" \
  -H "Accept: application/pdf" \
  -o esg_report.pdf

# 3. Export AI land cover analysis
curl -X GET "http://localhost:8000/api/v1/facility/report/ai-land-features-pdf?latitude=35.6762&longitude=139.6503" \
  -H "Accept: application/pdf" \
  -o land_cover_report.pdf
```

### Example 2: Get Detailed Explainability

```bash
# Get explanation with pixel-level data
curl -X GET "http://localhost:8000/api/v1/facility/explain?latitude=35.6762&longitude=139.6503" \
  -H "Accept: application/json" \
  -o explanation.json
```

### Example 3: Force Recalculation (Bypass Cache)

```bash
# Force fresh analysis (ignores 24-hour Redis cache)
curl -X GET "http://localhost:8000/api/v1/facility/analyze?latitude=35.6762&longitude=139.6503&recalculate=true" \
  -H "Accept: application/json"
```

---

## Performance Notes

### Caching Strategy
- **Metrics Results**: Cached for 24 hours per location/radius
- **STAC Searches**: Cached for 24 hours per collection/location/date-range
- **Explainability Data**: Cached alongside metrics (piggybacked)
- **AI Inference**: Model cached in memory (singleton)

### Response Times
| Scenario | Latency | Reason |
|----------|---------|--------|
| Cold first request | 45-60s | STAC API searches + raster processing |
| Warm (STAC cached) | 20-40s | No STAC calls, direct raster ops |
| Hot (all cached) | ~45ms | Direct Redis lookup |

### Data Pipeline Parallelization
All metrics computed in parallel:
```
Request Start
    ├─ Deforestation Risk (parallel thread 1) → 25s
    ├─ Water Stress (parallel thread 2) → 30s ← SLOWEST
    ├─ UHI (parallel thread 3) → 15s
    └─ Land Cover (parallel thread 4) → 20s
Request End (after SLOWEST completes)
```

Total time ≈ 30s (not 90s sequential sum)

---

## Error Handling

### Common Error Responses

**No satellite data available**
```json
{
  "detail": "No Sentinel-2 data found for the specified location and date range"
}
```

**Cache miss on explainability (must analyze first)**
```json
{
  "detail": "Explainability data not found. Please call /facility/analyze first."
}
```

**Invalid coordinates**
```json
{
  "detail": "Invalid latitude/longitude values"
}
```

---

## Integration Tips

### For Dashboard Use
```javascript
// React example
const [metrics, setMetrics] = useState(null);

const analyzeLocation = async (lat, lon) => {
  const response = await fetch(
    `/api/v1/facility/analyze?latitude=${lat}&longitude=${lon}`
  );
  const data = await response.json();
  setMetrics(data);
};

const downloadPDF = (lat, lon, type = 'esg') => {
  const endpoint = type === 'esg' 
    ? `/api/v1/facility/report/pdf?latitude=${lat}&longitude=${lon}`
    : `/api/v1/facility/report/ai-land-features-pdf?latitude=${lat}&longitude=${lon}`;
  window.location.href = endpoint;
};
```

### For Backend Integration
```python
import requests

# Get metrics
response = requests.get(
    f'http://localhost:8000/api/v1/facility/analyze',
    params={'latitude': 35.6762, 'longitude': 139.6503}
)
metrics = response.json()

# Download PDF
response = requests.get(
    f'http://localhost:8000/api/v1/facility/report/ai-land-features-pdf',
    params={'latitude': 35.6762, 'longitude': 139.6503}
)
with open('report.pdf', 'wb') as f:
    f.write(response.content)
```

---

## Monitoring & Logs

### Enable Debug Logging
Set environment variable:
```bash
export PYTHONPATH=/path/to/backend
LOG_LEVEL=DEBUG python -m uvicorn app.main:app --reload
```

### Key Metrics to Monitor
```
[TIMER] STAC search complete: {duration}ms
[TIMER] NDVI calculation: {duration}ms
[TIMER] NDWI calculation: {duration}ms
[TIMER] UHI calculation: {duration}ms
All metrics computed in {duration:.2f}s (PARALLEL)
```

---

## Version History

### v1.0 (Current)
- 3 ESG metrics: Deforestation, Water Stress, UHI
- AI Land Cover classification (5 classes)
- PDF/CSV reporting
- 24-hour Redis caching
- Parallel metric computation
- **NEW**: AI Land Features PDF export

### Planned Features
- Historical time-series analysis
- Batch location analysis
- Custom alert thresholds
- Multi-facility portfolios
- Real-time satellite data streaming

