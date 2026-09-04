"""Sensor platform for MOVA Litter Box (local)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_DID, CONF_MAC, CONF_MODEL, DOMAIN, KNOWN_PROPERTIES, SIGNAL_UPDATE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    stored = hass.data[DOMAIN][entry.entry_id]
    box_data = stored["data"]
    entities = [
        MovaPropertySensor(entry, box_data, key, name)
        for key, name in KNOWN_PROPERTIES.items()
    ]
    async_add_entities(entities)


class MovaPropertySensor(SensorEntity):
    """A single siid.piid property, exposed as a raw-value sensor.

    Property meanings are provisional (see const.py) - this exposes
    the raw value so it's usable/graphable in HA now, to be refined
    into proper typed entities (binary_sensor, etc.) once semantics
    are confirmed against real litter box behavior.
    """

    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, box_data, prop_key: str, name: str) -> None:
        self._box_data = box_data
        self._prop_key = prop_key
        did = entry.data[CONF_DID]
        self._attr_unique_id = f"{did}_{prop_key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, did)},
            name="MOVA Litter Box",
            model=entry.data[CONF_MODEL],
            manufacturer="MOVA",
            connections={("mac", entry.data[CONF_MAC])},
        )

    @property
    def native_value(self):
        prop = self._box_data.properties.get(self._prop_key)
        return prop.get("value") if prop else None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update)
        )

    def _handle_update(self) -> None:
        self.async_write_ha_state()
