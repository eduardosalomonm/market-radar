"""Safe public entry point for Streamlit Community Cloud."""

import os
import runpy
import tempfile
from pathlib import Path

os.environ.setdefault("MARKET_RADAR_PUBLIC_DEMO", "1")
os.environ.setdefault("MARKET_RADAR_DATABASE", str(Path(tempfile.gettempdir()) / "market-radar-public-demo.db"))

runpy.run_path(str(Path(__file__).parent / "market_radar" / "dashboard.py"), run_name="__main__")
