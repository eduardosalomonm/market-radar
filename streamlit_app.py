"""Public guest portfolios and an explicitly synthetic market showcase."""

import os
import runpy
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).parent / "market_radar"


def drop_stale_project_modules(package=PACKAGE, modules=sys.modules):
    """Streamlit Cloud reruns this script after a push without restarting Python.

    Modules imported before the update would otherwise stay in memory and clash
    with the new code, so they are discarded whenever the package changed.
    """
    stamp = max(path.stat().st_mtime_ns for path in package.rglob("*.py"))
    loaded = modules.get(package.name)
    if loaded is not None and getattr(loaded, "_code_stamp", None) != stamp:
        for name in [name for name in modules if name == package.name or name.startswith(package.name + ".")]:
            del modules[name]
    return stamp

os.environ.setdefault("MARKET_RADAR_PUBLIC_DEMO", "1")
os.environ.setdefault("MARKET_RADAR_DATABASE", str(Path(tempfile.gettempdir()) / "market-radar-public-demo.db"))

stamp = drop_stale_project_modules()
import market_radar  # noqa: E402

market_radar._code_stamp = stamp
runpy.run_path(str(Path(__file__).parent / "market_radar" / "dashboard.py"), run_name="__main__")
