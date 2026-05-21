"""Common path bootstrap for CLI scripts so ``python scripts/foo.py`` works
without `pip install -e .`."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_BACKEND_ROOT = _HERE.parent.parent  # backend/
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))
