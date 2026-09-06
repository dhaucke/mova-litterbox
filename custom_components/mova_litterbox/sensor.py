"""Sensor platform for MOVA Litter Box (local)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, KNOWN_PROPERTIES, SIGNAL_NEW_DEVICE, SIGNAL_UPDATE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    stored = hass.data[DOMAIN][entry.entry_id]
    box_data = stored["data"]
    created_property_entities: set[tuple[str, str]] = set()

    def _add_property_entities(did: str) -> None:
        device = box_data.devices.get(did)
        if not device:
            return
        new_entities = []
        for key in device["properties"]:
            entity_key = (did, key)
            if entity_key in created_property_entities:
                continue
            created_property_entities.add(entity_key)
            name = KNOWN_PROPERTIES.get(key, f"Property {key}")
            new_entities.append(MovaPropertySensor(box_data, did, key, name))
        if new_entities:
            async_add_entities(new_entities)

    def _handle_new_device(did: str) -> None:
        async_add_entities([MovaSerialSensor(box_data, did)])
        _add_property_entities(did)

    def _handle_update(did: str) -> None:
        _add_property_entities(did)

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE, _handle_new_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_UPDATE, _handle_update)
    )

    # Catch up on any device(s) that connected before this platform finished
    # setting up.
    for did in list(box_data.devices):
        _handle_new_device(did)


def _device_info(did: str, device: dict) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, did)},
        name="MOVA Litter Box",
        model=device.get("model"),
        manufacturer="MOVA",
        connections={("mac", device["mac"])} if device.get("mac") else set(),
    )


class MovaPropertySensor(SensorEntity):
    """A single siid.piid property, exposed as a raw-value sensor.

    Property meanings are provisional (see const.py) - this exposes
    the raw value so it's usable/graphable in HA now, to be refined
    into proper typed entities (binary_sensor, etc.) once semantics
    are confirmed against real litter box behavior.
    """

    _attr_should_poll = False

    def __init__(self, box_data, did: str, prop_key: str, name: str) -> None:
        self._box_data = box_data
        self._did = did
        self._prop_key = prop_key
        self._attr_unique_id = f"{did}_{prop_key}"
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._did, self._box_data.devices.get(self._did, {}))

    @property
    def native_value(self):
        device = self._box_data.devices.get(self._did)
        if not device:
            return None
        prop = device["properties"].get(self._prop_key)
        return prop.get("value") if prop else None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update)
        )

    def _handle_update(self, did: str) -> None:
        if did == self._did:
            # schedule_update_ha_state (not async_write_ha_state) - it's
            # safe from any thread, unlike the async_ variant which
            # requires already being on the event loop.
            self.schedule_update_ha_state()


class MovaSerialSensor(SensorEntity):
    """The device's serial number, always available once it has connected
    (independent of which properties it happens to report)."""

    _attr_should_poll = False

    def __init__(self, box_data, did: str) -> None:
        self._box_data = box_data
        self._did = did
        self._attr_unique_id = f"{did}_uid"
        self._attr_name = "Account UID"

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._did, self._box_data.devices.get(self._did, {}))

    @property
    def native_value(self):
        device = self._box_data.devices.get(self._did)
        return device.get("uid") if device else None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update)
        )

    def _handle_update(self, did: str) -> None:
        if did == self._did:
            # schedule_update_ha_state (not async_write_ha_state) - it's
            # safe from any thread, unlike the async_ variant which
            # requires already being on the event loop.
            self.schedule_update_ha_state()
