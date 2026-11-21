"""Config flow for AprilAire Healthy Air Monitor."""
from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import AprilAireAuthError, AprilAireCloud, AprilAireUnavailable
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_INTERVAL,
    DOMAIN,
    MAX_INTERVAL,
    MIN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

try:  # HA 2024.6+
    from homeassistant.config_entries import ConfigFlowResult
except ImportError:  # pragma: no cover
    ConfigFlowResult = FlowResult

try:  # HA 2024.4+
    from homeassistant.config_entries import OptionsFlowWithConfigEntry as _OptionsBase
except ImportError:  # pragma: no cover
    from homeassistant.config_entries import OptionsFlow as _OptionsBase

INTERVAL_SELECTOR = vol.All(vol.Coerce(int), vol.Range(min=MIN_INTERVAL, max=MAX_INTERVAL))

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL): INTERVAL_SELECTOR,
    }
)


class AprilAireConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect credentials and prove they work before creating the entry."""

    VERSION = 1

    async def _try_login(self, email: str, password: str) -> tuple[str | None, int]:
        """Return (account id, device count) or raise the API errors."""
        session = aiohttp.ClientSession(trust_env=False)
        try:
            cloud = AprilAireCloud(session, email, password)
            data = await cloud.async_snapshot()
            return cloud.account_id or email.lower(), len(data)
        finally:
            await session.close()

    async def async_step_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            try:
                account_id, devices = await self._try_login(email, password)
            except AprilAireAuthError:
                errors["base"] = "auth_failed"
            except (AprilAireUnavailable, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                if not devices:
                    errors["base"] = "no_devices"
                else:
                    await self.async_set_unique_id(account_id)
                    self._abort_if_unique_id_configured(
                        updates={CONF_EMAIL: email, CONF_PASSWORD: password}
                    )
                    return self.async_create_entry(
                        title=f"AprilAire ({email})",
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_INTERVAL),
                        },
                    )
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "AprilAireOptionsFlow":
        return AprilAireOptionsFlow(config_entry)

    async def async_step_reauth(self, entry_data: dict) -> ConfigFlowResult:
        return await self.async_step_reauth_user()

    async def async_step_reauth_user(self, user_input: dict | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        description_placeholders = {"email": entry.data.get(CONF_EMAIL, "")}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            try:
                await self._try_login(email, password)
            except AprilAireAuthError:
                errors["base"] = "auth_failed"
            except (AprilAireUnavailable, aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_EMAIL: email, CONF_PASSWORD: password}
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=entry.data.get(CONF_EMAIL)): str,
                vol.Required(CONF_PASSWORD, default=""): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_user",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )


class AprilAireOptionsFlow(_OptionsBase):
    """Let the poll interval be changed without re-entering credentials."""

    async def async_step_init(self, user_input: dict | None = None) -> ConfigFlowResult:
        entry = getattr(self, "config_entry", None) or self.handler
        current = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_INTERVAL)
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(title="", data=dict(user_input))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Optional(CONF_SCAN_INTERVAL, default=current): INTERVAL_SELECTOR}
            ),
            errors=errors,
        )
