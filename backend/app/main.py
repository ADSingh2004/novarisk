import os
import sys
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Add backend to path to make imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api import endpoints
from core.cache import test_redis_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NovaRisk ESG API",
    description="Satellite ESG Intelligence Dashboard API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:49671").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix="/api/v1")

@app.on_event("startup")
async def startup_event():
    """Test Redis connection on startup."""
    logger.info("🚀 Application starting up...")
    logger.info(f"ALLOWED_ORIGINS: {os.getenv('ALLOWED_ORIGINS', 'default')}")
    redis_ok = test_redis_connection()
    if redis_ok:
        logger.info("✅ All systems ready")
    else:
        logger.warning("⚠️ Redis connection failed - cache will not work")

@app.get("/")
def read_root():
    return {"message": "Welcome to NovaRisk ESG API"}

@app.get("/health")
def health_check():
    """Check system health including Redis."""
    redis_ok = test_redis_connection()
    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": {"connected": redis_ok},
        "version": "1.0.0"
    }

@app.get("/diagnostics")
def diagnostics():
    """Get system diagnostics."""
    import redis as redis_lib
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    redis_status = "unknown"
    redis_error = None
    try:
        test_client = redis_lib.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
        test_client.ping()
        redis_status = "✅ connected"
    except redis_lib.ConnectionError as e:
        redis_status = "❌ connection failed"
        redis_error = str(e)
    except Exception as e:
        redis_status = "❌ error"
        redis_error = f"{type(e).__name__}: {str(e)}"
    
    return {
        "status": "ok",
        "redis": {
            "url": redis_url,
            "status": redis_status,
            "error": redis_error
        },
        "environment": {
            "REDIS_URL": "set" if os.getenv("REDIS_URL") else "not set (using default)",
            "ALLOWED_ORIGINS": "set" if os.getenv("ALLOWED_ORIGINS") else "not set (using default)"
        }
    }

