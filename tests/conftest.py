import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
for sub in ("compliance/tools", "scripts", "dashboard"):
    p = str(REPO / sub)
    if p not in sys.path:
        sys.path.insert(0, p)
