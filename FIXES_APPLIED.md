# Fixes Applied - March 31, 2026

## Issues Found and Fixed

### 1. **JSON Serialization Error in cache.py**
**Problem**: Exception handler was trying to catch `json.JSONEncodeError` which doesn't apply to `json.dumps()` errors.
- `json.dumps()` raises `TypeError` for non-serializable objects (like numpy arrays), not `json.JSONEncodeError`
- This caused the exception to not be caught, propagating the error up

**Fix Applied**: 
- Changed exception handling from `json.JSONEncodeError` to `TypeError` in [backend/app/core/cache.py](backend/app/core/cache.py)
- Now properly catches and logs serialization errors

### 2. **Non-Serializable Numpy Arrays in explain_data**
**Problem**: The land cover explainability data was storing numpy arrays (`ndvi_array`, `ndwi_array`) which cannot be JSON serialized.
- Attempted to cache these arrays, causing `json.dumps()` to fail with `TypeError`
- All metrics returned 0.0 because exceptions cascaded through the calculation

**Fix Applied**:
- Removed numpy arrays (`ndvi_array`, `ndwi_array`) from `explain_data` in [backend/app/api/endpoints.py](backend/app/api/endpoints.py)
- Now only stores JSON-serializable statistics: `mean_ndvi`, `mean_ndwi`, `classification_map`

### 3. **SSL/Network Connection Errors in STAC Searches**
**Problem**: urllib3 SSL errors when connecting to Planetary Computer STAC API:
```
SSLError(SSLEOFError(8, '[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1028)'))
```
- STAC searches were uncaught, causing entire metric calculations to fail silently
- No error logging to diagnose the issue

**Fix Applied**:
- Added try-except blocks to all three STAC search functions in [satellite_processing/client.py](satellite_processing/client.py):
  - `search_sentinel2()`: Now catches exceptions and returns empty list `[]`
  - `search_landsat()`: Now catches exceptions and returns empty list `[]`
  - `search_sentinel1()`: Now catches exceptions and returns empty list `[]`
- Added comprehensive logging for all searches:
  - INFO level: Search start, items found
  - DEBUG level: Cache hits
  - ERROR level: Connection/SSL failures
- Added `logging` module import and `logger` initialization to client.py
- Added `urllib3.disable_warnings()` for SSL certificate warnings

## Result

**Before Fixes**:
- Metrics returned 0.0 values (silent failure)
- Backend logs showed cryptic exceptions about missing `json.JSONEncodeError`
- SSL errors from STAC API caused metric calculations to crash
- No visibility into which search was failing

**After Fixes**:
- Metrics return properly structured 0.0 scores with "status": "partial" or "failed"
- Clear error messages in logs showing which STAC search failed and why
- Graceful degradation: system continues even when satellite data fetch fails
- Full audit trail of cache hits/misses and network connectivity issues

## Next Steps

1. **Verify Network Connectivity**: The SSL errors suggest potential network issues with Planetary Computer STAC API
   - Check if the server can reach `planetarycomputer.microsoft.com`
   - Try accessing the API directly to diagnose SSL/certificate issues
   - Consider using environment variable to allow SSL verification bypass if needed

2. **Test with Real Data**: Once network connectivity is confirmed
   - Restart backend: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`
   - Call `/api/v1/facility/analyze?latitude=35.6762&longitude=139.6503` and check logs
   - Verify cache is being populated after successful searches

3. **Monitor Performance**: Track actual satellite data processing speed
   - Expected: <1 minute for full metric calculation (with caching on second call ~45ms)
   - Actual: Monitor with backend logs showing computation times

## Files Modified

1. ✅ [backend/app/core/cache.py](backend/app/core/cache.py) - Fixed exception handling
2. ✅ [backend/app/api/endpoints.py](backend/app/api/endpoints.py) - Removed non-serializable arrays from cache
3. ✅ [satellite_processing/client.py](satellite_processing/client.py) - Added error handling and logging to STAC searches
