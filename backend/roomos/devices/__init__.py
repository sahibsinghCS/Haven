"""Direct device control (smart plugs, thermostats) without a home-automation hub."""

from .smart_plug import apply_smart_plug_state
from .thermostat import apply_thermostat_setpoints, list_thermostat_devices

__all__ = [
    "apply_smart_plug_state",
    "apply_thermostat_setpoints",
    "list_thermostat_devices",
]
