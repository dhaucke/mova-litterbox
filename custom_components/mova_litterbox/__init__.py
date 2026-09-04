"""The MOVA Litter Box (local) integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .broker import MovaLocalBroker, ensure_self_signed_cert
from .const import CONF_DID, CONF_PORT, DEFAULT_PORT, DOMAIN, SIGNAL_UPDATE

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


class MovaLitterBoxData:
    """Shared state for one litter box: last-known property values."""

    def __init__(self) -> None:
        self.properties: dict[str, dict] = {}

    def handle_message(self, hass: HomeAssistant, message: dict) -> None:
        data = message.get("data", {})
        method = data.get("method")
        if method == "properties_changed":
            for prop in data.get("params", []):
                key = f"{prop.get('siid')}.{prop.get('piid')}"
                self.properties[key] = prop
        else:
            return
        async_dispatcher_send(hass, SIGNAL_UPDATE)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MOVA Litter Box from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    box_data = MovaLitterBoxData()

    storage_dir = Path(hass.config.path("mova_litterbox"))
    storage_dir.mkdir(exist_ok=True)
    cert_path = storage_dir / "cert.pem"
    key_path = storage_dir / f"{entry.data[CONF_DID]}_key.pem"
    ensure_self_signed_cert(cert_path, key_path, "eu.iot.mova-tech.com")

    def _on_message(message: dict) -> None:
        box_data.handle_message(hass, message)

    broker = MovaLocalBroker(
        cert_path,
        key_path,
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        _on_message,
    )
    await broker.start()

    hass.data[DOMAIN][entry.entry_id] = {"broker": broker, "data": box_data}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        stored = hass.data[DOMAIN].pop(entry.entry_id)
        await stored["broker"].stop()
    return unload_ok
