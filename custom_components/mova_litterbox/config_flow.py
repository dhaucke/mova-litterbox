"""Config flow for MOVA Litter Box (local)."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_PORT, CONF_UPSTREAM, DEFAULT_PORT, DOMAIN


class MovaLitterBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MOVA Litter Box (local).

    Device details (did/uid/mac/model) all come from the device's own
    first messages once it connects. The one thing that can't be
    auto-discovered up front is the real MOVA broker address to proxy
    to - see the README for where to find it (your device's own
    /pair/ handshake, e.g. "20000.mt.eu.iot.mova-tech.com:19974").
    """

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            if ":" not in user_input[CONF_UPSTREAM]:
                errors["base"] = "upstream_format"
            else:
                return self.async_create_entry(title="MOVA Litter Box", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_UPSTREAM): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
