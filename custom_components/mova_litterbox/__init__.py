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

# Methods we've seen and recognize but don't parse (yet) - not anomalies.
KNOWN_UNHANDLED_METHODS = {"event_occured", "_otc.info", "local.query_tz_time"}


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
        elif method in ("properties_changed", "set_properties"):
            # properties_changed is the device reporting its own state;
            # set_properties is the app *commanding* a change - both carry
            # the same {did, siid, piid, value} shape, so both update our
            # cache immediately rather than waiting for a confirmation
            # message to come back through.
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
        elif method in KNOWN_UNHANDLED_METHODS or isinstance(data.get("result"), dict):
            # Recognized but not yet parsed: event log entries, device info
            # pings, timezone queries, and action-invoke acks (a dict
            # result with a siid/aiid/code, as opposed to the list-shaped
            # property results handled above) - expected traffic.
            _LOGGER.debug("Unhandled MOVA message: %s", message)
        else:
            # Anything else - notably app-issued commands, whose method
            # name/shape we don't know yet - so it's visible instead of
            # silently dropped.
            _LOGGER.warning("Unhandled MOVA message: %s", message)

        # handle_message runs as part of the broker's own asyncio relay
        # coroutine (see broker.py), which is scheduled on hass.loop itself
        # (asyncio.start_server was awaited from async_setup_entry) - never
        # a separate thread. So no thread-hop is needed to reach the event
        # loop here; call the (@callback, synchronous) dispatcher directly.
        if is_new:
            async_dispatcher_send(hass, SIGNAL_NEW_DEVICE, did)
        async_dispatcher_send(hass, SIGNAL_UPDATE, did)


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
