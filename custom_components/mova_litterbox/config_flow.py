"""Config flow for MOVA Litter Box (local)."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import CONF_DID, CONF_MAC, CONF_MODEL, CONF_PORT, CONF_UID, DEFAULT_PORT, DOMAIN


class MovaLitterBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MOVA Litter Box (local).

    did/uid/mac come from your own device's /pair/ handshake (visible
    in the integration's debug log on first connection attempt, or by
    inspecting the MITM capture as described in the README) - there
    are no sane shared defaults since these identify your specific
    unit and account.
    """

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_DID])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="MOVA Litter Box", data=user_input
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_DID): str,
                vol.Required(CONF_UID): str,
                vol.Required(CONF_MODEL, default="mova.litterbox.q2504w"): str,
                vol.Required(CONF_MAC): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
