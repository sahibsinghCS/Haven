"""Multi-room camera registry, previews, and presence orchestration."""

from .models import OrchestratorMode, RoomCamera, RoomDocument, RoomRecord
from .store import RoomsStore
from .orchestrator import PresenceOrchestrator
from .preview_manager import RoomPreviewManager

__all__ = [
    "OrchestratorMode",
    "PresenceOrchestrator",
    "RoomCamera",
    "RoomDocument",
    "RoomPreviewManager",
    "RoomRecord",
    "RoomsStore",
]
