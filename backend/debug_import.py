#!/usr/bin/env python
import sys
import traceback

print("Python path:", sys.path[:3])
print("Current dir:", sys.argv[0])

try:
    print("Importing app.main...")
    from app.main import app
    print("SUCCESS: App imported")
except ImportError as e:
    print(f"ImportError: {e}")
    traceback.print_exc()
    print("\nTrying to import sub-modules directly...")
    try:
        from app.api import endpoints
        print("app.api imports OK")
    except Exception as e2:
        print(f"app.api failed: {e2}")
        traceback.print_exc()
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
