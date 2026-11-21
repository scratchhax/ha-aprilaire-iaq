"""Cloud client for AprilAire Healthy Air. Talks to device.aprilaire.io + socket.aprilaire.io."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import aiohttp

from . import cognito
from .const import API_BASE, WS_URL, WS_TIMEOUT
from .parser import parse_batch

_LOGGER = logging.getLogger(__name__)


class AprilAireAuthError(Exception):
    """Credentials were rejected."""


class AprilAireUnavailable(Exception):
    """Cloud or device could not be reached."""


def iter_locations(hierarchy: Any):
    """Yield (location_id, [device ids]) from whatever shape /hierarchy returns."""
    locs = hierarchy.get("locations") if isinstance(hierarchy, dict) else hierarchy
    if isinstance(locs, dict):
        items: list[Any] = [dict(v, locationId=v.get("locationId", k)) if isinstance(v, dict) else k
                            for k, v in locs.items()]
    elif isinstance(locs, list):
        items = locs
    else:
        items = []
    for loc in items:
        if not isinstance(loc, dict):
            continue
        lid = loc.get("locationId") or loc.get("id")
        if not lid:
            continue
        devices = loc.get("devices") or loc.get("deviceIds") or []
        ids = [d.get("deviceId") if isinstance(d, dict) else d for d in devices]
        yield lid, [i for i in ids if i]


class AprilAireCloud:
    """One-shot client: authenticate, then pull a snapshot of every device in the account."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._id_token: str | None = None
        self._refresh_token: str | None = None
        self._expires = 0.0

    # ---------- auth ----------
    async def _login(self) -> None:
        try:
            tokens = await asyncio.to_thread(cognito.authenticate, self._email, self._password)
        except Exception as err:  # noqa: BLE001
            text = str(err)
            if "NotAuthorized" in text or "Incorrect username" in text:
                raise AprilAireAuthError(text) from err
            raise AprilAireUnavailable(text) from err
        self._apply(tokens)

    async def _refresh(self) -> bool:
        if not self._refresh_token:
            return False
        try:
            tokens = await asyncio.to_thread(cognito.refresh, self._refresh_token)
        except Exception:  # noqa: BLE001
            return False
        self._apply(tokens)
        return True

    def _apply(self, tokens: dict) -> None:
        self._id_token = tokens["IdToken"]
        if tokens.get("RefreshToken"):
            self._refresh_token = tokens["RefreshToken"]
        self._expires = time.time() + int(tokens.get("ExpiresIn") or 3600) - 120

    async def _token(self, force: bool = False) -> str:
        if not force and self._id_token and time.time() < self._expires:
            return self._id_token
        if not force and self._id_token and await self._refresh():
            return self._id_token  # type: ignore[return-value]
        await self._login()
        return self._id_token  # type: ignore[return-value]

    @property
    def account_id(self) -> str | None:
        """The Cognito sub claim - a stable id for this account."""
        if not self._id_token:
            return None
        import base64

        part = self._id_token.split(".")[1]
        try:
            payload = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        except Exception:  # noqa: BLE001
            return None
        return payload.get("sub")

    # ---------- calls ----------
    async def _get(self, path: str, token: str) -> Any:
        try:
            async with self._session.get(
                f"{API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=25),
            ) as resp:
                if resp.status == 401:
                    raise AprilAireAuthError(f"401 on {path}")
                if resp.status == 403:
                    return None
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise AprilAireUnavailable(f"{path}: {err}") from err

    async def async_snapshot(self, timeout: int = WS_TIMEOUT) -> dict[str, dict]:
        """Return {device_id: parsed_data} for every device that reports in."""
        token = await self._token()
        try:
            hierarchy = await self._get("/hierarchy", token)
        except AprilAireAuthError:
            token = await self._token(force=True)
            hierarchy = await self._get("/hierarchy", token)
        if not hierarchy:
            raise AprilAireUnavailable("empty hierarchy")

        out: dict[str, dict] = {}
        for location_id, _ in iter_locations(hierarchy):
            try:
                batch = await self._ws_snapshot(token, location_id, timeout)
            except AprilAireUnavailable as err:
                _LOGGER.warning("location %s failed: %s", location_id, err)
                continue
            out.update(parse_batch(batch))
        if not out:
            raise AprilAireUnavailable("no data received over websocket")
        return out

    async def _ws_snapshot(self, token: str, location_id: str, timeout: int) -> list:
        """Open the socket, subscribe, keep every message that parses to a list."""
        frames: list = []
        try:
            async with self._session.ws_connect(
                WS_URL, timeout=20, heartbeat=None, receive_timeout=timeout
            ) as ws:
                await ws.send_str(json.dumps(
                    {"action": "subscribe", "message": {"token": token, "locationId": location_id}}
                ))
                deadline = time.time() + timeout
                while time.time() < deadline:
                    msg = await ws.receive(timeout=max(1.0, deadline - time.time()))
                    if msg.type is aiohttp.WSMsgType.CLOSED:
                        break
                    if msg.type is not aiohttp.WSMsgType.TEXT:
                        continue
                    if "SUBSCRIBED" in (msg.data or ""):
                        continue
                    try:
                        data = json.loads(msg.data)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    if isinstance(data, list):
                        frames.extend(data)
                        if any(isinstance(m, dict) and m.get("_type") == "SensorHubStatus" for m in data):
                            break
                    elif isinstance(data, dict) and data.get("messages"):
                        frames.extend(data["messages"])
        except aiohttp.ClientError as err:
            raise AprilAireUnavailable(f"websocket: {err}") from err
        except asyncio.TimeoutError:
            _LOGGER.debug("websocket snapshot timed out for %s", location_id)
        return frames
