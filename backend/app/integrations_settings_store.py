"""Device integration settings — UI connections (smart plug, lights, thermostat)."""



from __future__ import annotations



from datetime import datetime, timezone

from pathlib import Path

from typing import Any





def integrations_store_path() -> Path:

    from roomos.config import load_config



    from .core.config import settings



    cfg = load_config(settings.roomos_config)

    return cfg.resolve_path("data/integrations.json")





def default_integrations_document() -> dict[str, Any]:

    now = datetime.now(timezone.utc).isoformat()

    return {

        "schemaVersion": 1,

        "updatedAt": now,

        "devices": {

            "smartPlug": {

                "enabled": False,

                "connected": False,

                "brand": "tplink_kasa",

                "host": "",

                "label": "Fan plug",

            },

            "lights": {

                "enabled": False,

                "connected": False,

                "brand": "none",

                "notes": "",

            },

            "thermostat": {

                "enabled": False,

                "connected": False,

                "brand": "none",

                "notes": "",

            },

        },

    }


