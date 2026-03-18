"""
Pytest configuration — adds src/ to sys.path so that
`from aiplatform.skills...` and `from ventures.etsy...` work in tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
