import os
import redis
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Custom JSON encoder to handle datetime and other non-serializable objects
class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            # For objects with __dict__, try to serialize them
            return obj.__dict__
        return super().default(obj)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Test Redis connection on startup
def test_redis_connection():
    """Test if Redis is accessible at startup."""
    try:
        client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
        client.ping()
        logger.info(f"✅ Redis connected successfully: {REDIS_URL}")
        return True
    except redis.ConnectionError as e:
        logger.error(f"❌ Redis connection failed: {e}")
        logger.error(f"   REDIS_URL: {REDIS_URL}")
        return False
    except Exception as e:
        logger.error(f"❌ Redis error: {type(e).__name__}: {e}")
        return False

# Initialize Redis client
# Set decode_responses=True so we get strings instead of bytes
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
    logger.info(f"Redis client initialized with URL: {REDIS_URL}")
except Exception as e:
    logger.error(f"⚠️ Failed to initialize Redis client: {e}")
    redis_client = None

def get_cache(key: str) -> dict:
    """Retrieves a cached JSON response if it exists."""
    if redis_client is None:
        logger.warning("Redis client not available, skipping cache read")
        return None
    
    try:
        val = redis_client.get(key)
        if val:
            logger.debug(f"Cache HIT: {key}")
            return json.loads(val)
        else:
            logger.debug(f"Cache MISS: {key}")
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error during read: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Redis cache JSON decode error: {e}")
    except Exception as e:
        logger.error(f"Redis cache read error: {type(e).__name__}: {e}")
    return None

def set_cache(key: str, data: dict, expire_seconds: int = 86400):
    """Stores data in Redis cache with an expiration (default 24h)."""
    if redis_client is None:
        logger.warning("Redis client not available, skipping cache write")
        return
    
    try:
        # Use custom encoder to handle datetime and other non-serializable objects
        json_str = json.dumps(data, cls=EnhancedJSONEncoder)
        redis_client.setex(key, expire_seconds, json_str)
        logger.debug(f"Cache SET: {key} (expires in {expire_seconds}s)")
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error during write: {e}")
    except TypeError as e:
        logger.error(f"Redis cache JSON serialization error (non-serializable object): {e}")
        logger.debug(f"Failed to serialize data: {type(data)} with keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
    except Exception as e:
        logger.error(f"Redis cache write error: {type(e).__name__}: {e}")

