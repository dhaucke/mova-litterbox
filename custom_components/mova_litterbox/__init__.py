"""The MOVA Litter Box (local) integration."""
from __future__ import annotations

import logging
import ssl
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .broker import (
    MovaLocalBroker,
    build_server_ssl_context,
    ensure_self_signed_cert,
    resolve_public,
)
from .const import (
    CONF_PORT,
    CONF_UPSTREAM,
    DEFAULT_PORT,
    DOMAIN,
    PUBLIC_DNS_SERVERS,
    SIGNAL_NEW_DEVICE,
    SIGNAL_UPDATE,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


class MovaLitterBoxData:
    """Tracks every device seen on the broker, keyed by its did.

    Nothing about a device is known ahead of time - did/uid/mac/model
    all come from the device's own first messages, so entities are
    created dynamically as devices connect rather than configured
    up front.
    """

    def __init__(self) -> None:
        self.devices: dict[str, dict] = {}

    def handle_message(self, hass: HomeAssistant, message: dict) -> None:
        did = str(message.get("did", ""))
        if not did:
            return

        is_new = did not in self.devices
        device = self.devices.setdefault(
            did, {"uid": None, "mac": None, "model": None, "properties": {}}
        )

        data = message.get("data", {})
        method = data.get("method")
        if method == "dev_start":
            params = data.get("params", {})
            device["uid"] = params.get("uid")
            device["mac"] = params.get("mac")
            device["model"] = params.get("model")
        elif method == "properties_changed":
            for prop in data.get("params", []):
                key = f"{prop.get('siid')}.{prop.get('piid')}"
                device["properties"][key] = prop
        elif isinstance(data.get("result"), list):
            # Response to a get_properties/set_properties call - the app
            # issues these itself (we don't need to send our own query),
            # and we get to read the answer as it passes through. Same
            # {siid, piid, value} shape as properties_changed, plus a
            # "code" (0 = success) we don't currently need.
            for prop in data["result"]:
                if prop.get("code") == 0 and "value" in prop:
                    key = f"{prop.get('siid')}.{prop.get('piid')}"
                    device["properties"][key] = prop
        else:
            # Anything else - notably app-issued commands, whose method
            # name/shape we don't know yet - so it's visible instead of
            # silently dropped.
            _LOGGER.warning("Unhandled MOVA message: %s", message)

        # handle_message is called from the broker's own connection-handling
        # task, which HA doesn't guarantee runs on hass.loop - dispatching
        # directly here can construct a Task bound to the wrong loop
        # (RuntimeError: loop ... is not the running loop). call_soon_threadsafe
        # guarantees the dispatch itself always runs on hass.loop.
        if is_new:
            hass.loop.call_soon_threadsafe(
                async_dispatcher_send, hass, SIGNAL_NEW_DEVICE, did
            )
        hass.loop.call_soon_threadsafe(
            async_dispatcher_send, hass, SIGNAL_UPDATE, did
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up MOVA Litter Box from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    box_data = MovaLitterBoxData()

    storage_dir = Path(hass.config.path("mova_litterbox"))
    upstream_host, _, upstream_port_str = entry.data[CONF_UPSTREAM].partition(":")
    upstream_port = int(upstream_port_str) if upstream_port_str else DEFAULT_PORT

    def _prepare() -> tuple[ssl.SSLContext, str]:
        # File I/O, OpenSSL cert loading, and the DNS lookup below are all
        # blocking - must not run directly on the event loop.
        storage_dir.mkdir(exist_ok=True)
        cert_path = storage_dir / "cert.pem"
        key_path = storage_dir / "key.pem"
        ensure_self_signed_cert(cert_path, key_path, "eu.iot.mova-tech.com")
        ctx = build_server_ssl_context(cert_path, key_path)
        ip = resolve_public(upstream_host, PUBLIC_DNS_SERVERS)
        return ctx, ip

    ssl_context, upstream_ip = await hass.async_add_executor_job(_prepare)

    def _on_message(message: dict) -> None:
        box_data.handle_message(hass, message)

    broker = MovaLocalBroker(
        ssl_context,
        entry.data.get(CONF_PORT, DEFAULT_PORT),
        upstream_host,
        upstream_port,
        upstream_ip,
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
