# AprilAire Healthy Air Monitor — Home Assistant integration

Cloud-only custom integration for the AprilAire **Healthy Air Monitor**
(model `ZAWTHCPV`, made by Computime, firmware `1.9.0-prod` at time of writing).

## Why cloud and not local

The monitor is an ESP32, but it exposes **nothing** locally: every TCP port on the
device is closed and it keeps a single outbound MQTT/WebSocket session to
`mqtt.aprilairestat.com` (AWS IoT). Readings only reach AprilAire's cloud, which
pushes them to clients over `wss://socket.aprilaire.io/`. Auth is AWS Cognito SRP
(pool `us-west-2_skfkpmVv6`, client `3aiakr6qdoqtajv7qgtapecerg`).

The stock `aprilaire` integration only supports the E100/8920W thermostats; it has
no profile for this sensor hub, hence this one.

## Install

1. Copy `custom_components/aprilaire_iaq` into `<config>/custom_components/`.
2. Restart Home Assistant.
3. Settings → Devices & Services → Add Integration → **AprilAire Healthy Air Monitor**.
4. Enter the same email/password as the AprilAire app. One entry per account;
   every device in that account's locations is added automatically.

Requires Home Assistant 2024.6 or newer. No PyPI dependencies — `aiohttp` ships
with HA, and the Cognito SRP math is implemented with the standard library only.

## Entities (per device, all read-only)

| Entity | Notes |
| --- | --- |
| Temperature, Humidity | units follow whatever the device is configured for (°C/°F, ug/m3) |
| PM2.5, PM10 | µg/m³ |
| Carbon dioxide | ppm |
| TVOC, Nitrogen oxides | raw index, no unit published by AprilAire |
| Proximity | presence channel, 0/1 — semantics not documented by AprilAire |
| Air quality | `Good` / `Fair` / `Concerning` / `Unhealthy`, matches the ring light |
| Wi-Fi signal | dBm, disabled by default |

Each reading carries `air_quality`, `air_quality_code` and `sensor_status`
attributes; the air-quality sensor carries `reported_at` and `diagnostic_codes`.

The device reports roughly every 1–5 minutes, so the default poll interval is
**300 seconds**: each poll opens a fresh subscription socket, reads the snapshot
the cloud sends immediately after `subscribe`, then hangs up. Change it under
the integration's **Configure** dialog (30–3600 s) — it takes effect immediately,
no restart. Set it low only if you are debugging; there is no faster data to get. Expiry of the Cognito token is
handled by refresh; a rejected password raises a re-auth flow in the UI.

## Limits

- Read-only. Night light, LED mode and the alert thresholds are visible in the
  snapshot but no entities are built for them yet.
- Devices paired after setup need a config-entry reload to appear.
- Only the `PASSWORD_VERIFIER` SRP flow is implemented — an MFA-enabled account
  will fail. AprilAire's own app account is the one to use.
- It is an undocumented API; AprilAire can break it whenever they feel like it.

## Debug

```
python3 cli.py you@example.com 'yourpassword'
```

prints the same payload the integration sees, no Home Assistant involved.

Verbose logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.aprilaire_iaq: debug
```
