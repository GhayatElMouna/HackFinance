"""
Point d'entree Streamlit (racine du projet).
Purge les modules `src.*` avant import pour eviter le cache Pydantic.
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Purger tout module projet deja charge (hot-reload Streamlit)
for name in list(sys.modules):
    if name == "src" or name.startswith("src."):
        del sys.modules[name]

runpy.run_path(str(ROOT / "src" / "dashboard" / "app.py"), run_name="__main__")
