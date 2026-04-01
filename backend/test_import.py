#!/usr/bin/env python
import sys
import traceback

try:
    from app.main import app
    print("✅ SUCCESS: App imported")
    sys.exit(0)
except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)
