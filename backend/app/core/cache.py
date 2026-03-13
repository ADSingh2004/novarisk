import os
import redis
import json

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Initialize Redis client
# Set decode_responses=True so we get strings instead of bytes
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

def get_cache(key: str) -> dict:
    """Retrieves a cached JSON response if it exists."""
    try:
        val = redis_client.get(key)
        if val:
            return json.loads(val)
    except Exception as e:
        print(f"Redis cache Read Error: {e}")
    return None

def set_cache(key: str, data: dict, expire_seconds: int = 86400):
    """Stores data in Redis cache with an expiration (default 24h)."""
    try:
        redis_client.setex(key, expire_seconds, json.dumps(data))
    except Exception as e:
        print(f"Redis cache Write Error: {e}")
