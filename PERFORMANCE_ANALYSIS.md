# NovaRisk ESG Performance Analysis & Optimization Plan

## Current Performance Issue
**Problem**: Metric calculations take 20-30 minutes, causing API timeouts (returning 0 values)  
**Goal**: Reduce calculation time to <1 minute  

## Root Cause Analysis

### 1. STAC API Query Redundancy (PRIMARY BOTTLENECK)
Each `/facility/analyze` request makes **9-10 STAC catalog searches**:

```
Deforestation Risk:
  ├─ search_sentinel2(days_back=30, max_items=5) → ~5-10s
  └─ search_sentinel2(days_back=365, max_items=10) → ~10-15s

Water Stress Fusion:
  ├─ search_sentinel2(days_back=30, max_items=5) → ~5-10s (DUPLICATE!)
  ├─ search_sentinel2(days_back=365, max_items=10) → ~10-15s (DUPLICATE!)
  ├─ search_sentinel1(days_back=30, max_items=5) → ~10-15s
  └─ search_sentinel1(days_back=365, max_items=10) → ~10-15s

Urban Heat Island:
  └─ search_landsat(days_back=60, max_items=10) → ~10-15s

Land Cover + Explain:
  └─ search_sentinel2(days_back=30, max_items=5) → ~5-10s (DUPLICATE!)

Total: 6-10 STAC API calls that are BLOCKING
Estimated time: 60-150 seconds just waiting for STAC API
```

### 2. Rasterio/Stackstac Inefficiency (SECONDARY BOTTLENECK)
```
- Each metric independently computes median composites (~5-10s each)
- NDVI computed 3 times: deforestation, water, explainability
- NDWI computed 2 times: water stress, explainability  
- Each windowed read re-downloads the same satellite tiles
- No intermediate result caching between metrics

Estimated time: 30-60 seconds for redundant raster ops
```

### 3. Sequential Metric Execution (PARTIALLY ADDRESSED)
Current code has ThreadPoolExecutor with 4 workers, but:
- STAC searches within each metric are still SEQUENTIAL
- Each thread blocks waiting for STAC API before raster processing
- Could benefit from async/await for I/O operations

### 4. AI Model Inference (TERTIARY)
```
Land cover classification on CPU:
- ResNet18 U-Net inference: ~2-5s
- Model loading happens once (cached as singleton)
- Resolution limited to 256x256 for performance
- Reasonable performance, not a major bottleneck

Estimated time: 2-5 seconds
```

### 5. SAR Processing
- Water stress SAR results ARE being cached locally
- But Sentinel-1 searches still block (`search_sentinel1` calls)

## Performance Bottleneck Priority Matrix

| Issue | Impact | Effort | Priority |
|-------|--------|--------|----------|
| Duplicate STAC searches | 60-150s | LOW | **CRITICAL** |
| Sequential raster ops | 30-60s | MEDIUM | **HIGH** |
| No composite caching | 20-40s | LOW | **HIGH** |
| Sequential index calc | 10-20s | MEDIUM | **MEDIUM** |
| Non-async STAC calls | 5-10s | MEDIUM | **MEDIUM** |
| AI inference | 2-5s | LOW | LOW |

## Proposed Optimizations (Est. Total Speedup: 10-15x)

### 1. **Centralized STAC Search Cache** (Est: -60-100s)
```
Create a shared search function that caches results:
- search_cached_sentinel2_recent() → cache key by bbox + date_range
- search_cached_sentinel2_historical() → cache key by bbox + date_range  
- search_cached_sentinel1_recent() → cache key by bbox + date_range
- search_cached_landsat() → cache key by bbox + date_range

Benefits:
- Deforestation: reuses Water's S2 recent search
- Water: reuses Deforestation's S2 searches
- Land Cover: reuses existing S2 recent search
- Explainability: uses cached searches

Estimated Savings: 60-100 seconds (eliminates 6 of 10 STAC searches)
```

### 2. **Composite Caching Layer** (Est: -20-40s)
```
Cache computed median composites in Redis:
- Cache Key: f"composite:sentinel2:recent:{bbox}:{date_range}"
- Cache Key: f"composite:landsat:{bbox}:{date_range}"

Benefits:
- NDVI computation reuses median composite
- NDWI computation reuses median composite
- Land cover uses same composite
- No re-downloading of tiles

Estimated Savings: 20-40 seconds
```

### 3. **Parallel STAC Searches Within Metrics** (Est: -10-20s)
```
Instead of:
  items_recent = search(days=30)      # 10s
  items_historical = search(days=365) # 15s  # BLOCKED on above
  # Total: 25s

Use asyncio:
  items_recent, items_historical = await asyncio.gather(
      async_search(days=30),      # 10s
      async_search(days=365)      # 15s (parallel)
  )
  # Total: 15s (fastest of the two)

Estimated Savings: 10-20 seconds
```

### 4. **Reuse STAC Items for Index Calculations** (Est: -10-15s)
```
Currently:
  items = search_sentinel2(max_items=5)
  ndvi = calculate_ndvi_from_stac_items(items)  # Downloads tiles
  ndwi = calculate_ndwi_from_stac_items(items)  # Re-downloads same tiles!

Optimized:
  items = search_sentinel2(max_items=5)
  # Stack once, extract multiple indices
  stacked_cube = stackstac.stack(items, assets=['B02','B03','B04','B08'])
  ndvi = compute_ndvi(stacked_cube)   # Already in memory
  ndwi = compute_ndwi(stacked_cube)   # Already in memory

Estimated Savings: 10-15 seconds
```

### 5. **Async/Await for I/O** (Est: -5-10s)
```
Replace ThreadPoolExecutor blocking calls with asyncio native tasks:
- Parallel metric downloads via async libraries
- Non-blocking STAC API calls
- Better utilization of event loop

Estimated Savings: 5-10 seconds
```

### 6. **Reduce Data Volume** (Est: -5-10s)
```
Current:
  - 40m resolution composites for 10km bbox: ~250x250 pixels
  - Land cover inference on full resolution: 256x256
  
Optimized for faster inference:
  - Option: Coarsen initial composite to 60m for metrics: ~170x170
  - Option: Batch SAR processing (reuse across multiple queries)

Estimated Savings: 5-10 seconds
```

## Implementation Strategy

### Phase 1 (Target: 80% of optimization)
1. ✅ Create centralized STAC search cache
2. ✅ Implement composite caching
3. ✅ Fix redundant index calculations
4. ✅ Add profiling/timing instrumentation

**Expected Result: 20-30 minutes → 3-5 minutes**

### Phase 2 (Target: 90% of optimization)
1. ✅ Implement async/await for STAC calls
2. ✅ Parallel STAC searches within metrics
3. ✅ Batch operation optimization

**Expected Result: 3-5 minutes → 30-60 seconds**

### Phase 3 (Target: 100% + Features)
1. ✅ Add land feature AI prediction PDF export
2. ✅ Fine-tune resolution/precision tradeoffs  
3. ✅ Implement request-level caching for identical queries

**Expected Result: 30-60 seconds → 15-30 seconds**

## Monitoring & Profiling

Add timing instrumentation at each step:
```python
@timer("stac_search_sentinel2_recent")
def search_sentinel2(...)  # Logs execution time

@timer("ndvi_calculation")
def calculate_ndvi_from_stac_items(...)  # Logs execution time
```

## File Changes Required
1. `satellite_processing/client.py` → Add caching for STAC searches
2. `satellite_processing/indices/*.py` → Optimize raster operations
3. `backend/app/api/endpoints.py` → Refactor metric pipeline
4. `backend/app/core/cache.py` → Extend for composites
5. `reporting/generator.py` → Add PDF export for AI land features
6. `satellite_processing/ai/land_cover_classifier.py` → Optimize inference

## Expected Results Post-Optimization

| Metric | Before | After | Speedup |
|--------|--------|-------|---------|
| Cold HTTP Request | 20-30 min | 30-60s | **20-30x** |
| Cached Request | 45ms | 45ms | N/A |
| Total API Calls | 10 | 4 | **2.5x** |
| Raster Ops Time | 60s | 15s | **4x** |
| STAC Query Time | 90s | 20s | **4.5x** |
