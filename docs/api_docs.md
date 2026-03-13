# NovaRisk ESG API Documentation

This directory contains the API documentation and architecture diagrams for the NovaRisk ESG Backend.

## Endpoints Overview

The API is built with FastAPI and runs on `http://127.0.0.1:8000/api/v1` by default.

### 1. Register Facility (POST)
Registers a new facility location into the system (Mock DB implementation).

**Endpoint:** `POST /facility/register`
**Body:**
```json
{
  "name": "Tokyo Industrial Plant",
  "latitude": 35.6762,
  "longitude": 139.6503
}
```

**cURL Example:**
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/facility/register" \
     -H "Content-Type: application/json" \
     -d '{"name": "Tokyo Industrial Plant", "latitude": 35.6762, "longitude": 139.6503}'
```

### 2. Analyze Facility (GET)
Returns the live ESG metrics (Deforestation, Water Stress, UHI Intensity) for a coordinate. Uses Redis caching for sub-100ms response times on repeated reads.

**Endpoint:** `GET /facility/analyze?latitude=<lat>&longitude=<lon>&radius_km=<radius>`

**cURL Example:**
```bash
curl -X GET "http://127.0.0.1:8000/api/v1/facility/analyze?latitude=35.6762&longitude=139.6503&radius_km=5.0"
```

### 3. Export PDF Report (GET)
Generates and downloads a compliance-ready PDF report containing ESG metrics, risk categories, and methodology notes.

**Endpoint:** `GET /facility/report/pdf?latitude=<lat>&longitude=<lon>`

**cURL Example:**
```bash
curl -sSJ -O "http://127.0.0.1:8000/api/v1/facility/report/pdf?latitude=35.6762&longitude=139.6503"
# The -sSJ -O flags tell curl to save the binary output to a file using the server-provided filename.
```

### 4. Export CSV Report (GET)
Generates a raw data CSV containing the ESG metrics.

**Endpoint:** `GET /facility/report/csv?latitude=<lat>&longitude=<lon>`

**cURL Example:**
```bash
curl -sSJ -O "http://127.0.0.1:8000/api/v1/facility/report/csv?latitude=35.6762&longitude=139.6503"
```

## Performance Metrics
- **Cached Read p50 Latency:** ~20-50ms (measured via `load_test.py`)
- **Cold Read Latency:** ~2-10 seconds depending on Microsoft Planetary Computer upstream response times and raster sizes.
