"""Event platform for MOVA Litter Box (local).

Exposes momentary app commands (see const.MOMENTARY_PROPERTIES) as `event`
entities - the box has no persistent "on" state for these, so a single
"activated" firing whenever the app sends value=1 is the correct shape,
not a sensor/binary_sensor.
"""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, MOMENTARY_PROPERTIES, SIGNAL_NEW_DEVICE, SIGNAL_UPDATE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    stored = hass.data[DOMAIN][entry.entry_id]
    box_data = stored["data"]
    created_event_entities: set[tuple[str, str]] = set()

    def _add_event_entities(did: str) -> None:
        device = box_data.devices.get(did)
        if not device:
            return
        new_entities = []
        for key, name in MOMENTARY_PROPERTIES.items():
            entity_key = (did, key)
            if entity_key in created_event_entities or key not in device["properties"]:
                continue
            created_event_entities.add(entity_key)
            new_entities.append(MovaCommandEvent(box_data, did, key, name))
        if new_entities:
            async_add_entities(new_entities)

    def _handle_new_device(did: str) -> None:
        _add_event_entities(did)

    def _handle_update(did: str) -> None:
        _add_event_entities(did)

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_DEVICE, _handle_new_device)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_UPDATE, _handle_update)
    )

    for did in list(box_data.devices):
        _handle_new_device(did)


class MovaCommandEvent(EventEntity):
    """Fires "activated" whenever the app sends this command's value=1.

    The value=0 that always follows shortly after is the app's own reset,
    not a second command - only the 1 is a real "the button was tapped".
    """

    _attr_should_poll = False
    _attr_event_types = ["activated"]

    def __init__(self, box_data, did: str, prop_key: str, name: str) -> None:
        self._box_data = box_data
        self._did = did
        self._prop_key = prop_key
        self._attr_unique_id = f"{did}_{prop_key}_event"
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        device = self._box_data.devices.get(self._did, {})
        return DeviceInfo(
            identifiers={(DOMAIN, self._did)},
            name="MOVA Litter Box",
            model=device.get("model"),
            manufacturer="MOVA",
            connections={("mac", device["mac"])} if device.get("mac") else set(),
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update)
        )

    def _handle_update(self, did: str) -> None:
        if did != self._did:
            return
        device = self._box_data.devices.get(self._did)
        prop = device["properties"].get(self._prop_key) if device else None
        if prop and prop.get("value") == 1:
            self._trigger_event("activated")
            # schedule_update_ha_state (not async_write_ha_state) - safe
            # from any thread, unlike the async_ variant.
            self.schedule_update_ha_state()
