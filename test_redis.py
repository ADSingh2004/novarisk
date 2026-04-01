#!/usr/bin/env python3
"""
Quick Redis connection diagnostics script.
Run this to test if Redis is accessible from your backend.
"""
import redis
import os
import sys

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

print("=" * 60)
print("🔍 NovaRisk ESG - Redis Diagnostics")
print("=" * 60)
print()

print(f"REDIS_URL: {REDIS_URL}")
print()

# Test 1: Connection
print("Test 1: Testing Redis connection...")
try:
    client = redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=5)
    print("  ✅ Client created successfully")
except Exception as e:
    print(f"  ❌ Failed to create client: {e}")
    sys.exit(1)

# Test 2: Ping
print("\nTest 2: Testing PING command...")
try:
    response = client.ping()
    print(f"  ✅ PING successful: {response}")
except Exception as e:
    print(f"  ❌ PING failed: {e}")
    sys.exit(1)

# Test 3: Set/Get
print("\nTest 3: Testing SET and GET...")
try:
    client.set("test_key", "test_value")
    value = client.get("test_key")
    if value == "test_value":
        print(f"  ✅ SET/GET successful")
    else:
        print(f"  ❌ SET/GET returned wrong value: {value}")
except Exception as e:
    print(f"  ❌ SET/GET failed: {e}")
    sys.exit(1)

# Test 4: JSON
print("\nTest 4: Testing JSON storage...")
try:
    import json
    test_data = {"deforestation_risk": 25.4, "water_stress": 18.9}
    json_str = json.dumps(test_data)
    client.setex("test_json", 3600, json_str)
    
    stored = client.get("test_json")
    decoded = json.loads(stored)
    
    if decoded == test_data:
        print(f"  ✅ JSON storage successful")
    else:
        print(f"  ❌ JSON storage failed: {decoded}")
except Exception as e:
    print(f"  ❌ JSON storage failed: {e}")
    sys.exit(1)

# Test 5: TTL
print("\nTest 5: Testing TTL/expiration...")
try:
    client.setex("temp_key", 10, "value")
    ttl = client.ttl("temp_key")
    if ttl > 0:
        print(f"  ✅ TTL is set: {ttl} seconds")
    else:
        print(f"  ❌ TTL not working properly: {ttl}")
except Exception as e:
    print(f"  ❌ TTL test failed: {e}")
    sys.exit(1)

print()
print("=" * 60)
print("✅ All Redis tests passed!")
print("=" * 60)
print()
print("Your Redis connection is working correctly.")
print("You can now use the backend API endpoints.")
