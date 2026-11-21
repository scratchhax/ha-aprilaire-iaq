"""Data update coordinator for AprilAire Healthy Air."""
from __future__ import annotations

import inspect
import logging
from datetime import timedelta

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import AprilAireAuthError, AprilAireCloud, AprilAireUnavailable
from .const import CONF_EMAIL, CONF_PASSWORD, DEFAULT_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class AprilAireCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Pulls one snapshot per interval from the AprilAire cloud."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        # HA 2025.2+ takes (hass, config_entry, logger); older builds take
        # (hass, logger, config_entry=...). Pick whichever this build speaks.
        new_style = list(inspect.signature(DataUpdateCoordinator.__init__).parameters)[2] == "config_entry"
        args = (hass, entry, _LOGGER) if new_style else (hass, _LOGGER)
        super().__init__(
            *args,
            **({} if new_style else {"config_entry": entry}),
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_INTERVAL),
        )
        # trust_env=False: never let HTTP(S)_PROXY silently hijack the websocket.
        self.session = aiohttp.ClientSession(trust_env=False)
        self.cloud = AprilAireCloud(
            self.session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD]
        )

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            return await self.cloud.async_snapshot()
        except AprilAireAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AprilAireUnavailable as err:
            raise UpdateFailed(str(err)) from err

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        await self.session.close()
