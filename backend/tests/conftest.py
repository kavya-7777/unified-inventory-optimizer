import sys, os

# Ensure /app (the backend root) is on the path so `from app.xxx import yyy` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
