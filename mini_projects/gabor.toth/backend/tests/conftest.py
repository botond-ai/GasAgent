"""Global Pytest Configuration - Sets up Python path for imports."""

import sys
import os

# Add backend directory to Python path so relative imports work
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
