"""Config flow for MOVA Litter Box (local)."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_PORT, DEFAULT_PORT, DOMAIN


class MovaLitterBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MOVA Litter Box (local).

    No device details needed up front - did/uid/mac/model all come
    from the device's own first messages once it connects (see the
    README for the one-time DNS rewrite this depends on).
    """

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="MOVA Litter Box", data=user_input)

        schema = vol.Schema(
            {vol.Required(CONF_PORT, default=DEFAULT_PORT): int}
        )
        return self.async_show_form(step_id="user", data_schema=schema)
