"""RoomOS — local-first room activity recognition pipeline.

This package contains the offline pipeline (video → perception → temporal
fusion → XGBoost classifier) and the live inference / action layer. The
FastAPI app in ``app/`` is a thin transport wrapper around it.
"""

from __future__ import annotations

__version__ = "0.1.0"
