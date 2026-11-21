"""Turn the raw websocket batch into a plain dict of devices. No HA imports."""
from __future__ import annotations

from .const import IAQ_STATES, MEASUREMENTS


def _blank(device_id: str) -> dict:
    return {
        "device_id": device_id,
        "model": None,
        "name": None,
        "firmware": None,
        "hardware": None,
        "rssi": None,
        "diag": [],
        "settings": {},
        "measurements": {},   # key -> {value, unit, label, status, state}
        "iaq_state": None,
        "iaq_state_code": None,
        "as_of": None,
    }


def parse_batch(batch: list) -> dict[str, dict]:
    """`batch` is the JSON array AprilAire pushes right after subscribe."""
    devices: dict[str, dict] = {}

    def dev(did):
        return devices.setdefault(did or "", _blank(did or ""))

    for msg in batch or []:
        if not isinstance(msg, dict):
            continue
        mtype = msg.get("_type")
        did = msg.get("deviceId")
        if not did:
            continue
        d = dev(did)
        if msg.get("asOf"):
            d["as_of"] = msg["asOf"]

        if mtype == "DeviceSetup":
            hub = msg.get("sensorHub") or {}
            for sensor in hub.get("sensors") or []:
                info = sensor.get("sensorInfo") or {}
                d["model"] = info.get("model") or d["model"]
                d["firmware"] = info.get("fwVersion") or d["firmware"]
                for m in sensor.get("measurements") or []:
                    mid = m.get("id")
                    key, _, unit = MEASUREMENTS.get(mid, (f"measurement_{mid}", None, None))
                    entry = d["measurements"].setdefault(key, {})
                    entry["label"] = (m.get("type") or key).upper()
                    entry["unit"] = m.get("unit") or unit
        elif mtype == "DeviceStatus":
            d["model"] = msg.get("model") or d["model"]
            d["firmware"] = msg.get("firmwareRev") or d["firmware"]
            d["hardware"] = msg.get("hardwareRev")
        elif mtype == "DeviceSettings":
            iaq = msg.get("iaqMonitor") or {}
            d["settings"] = {k: iaq.get(k) for k in ("dispName", "lightMode", "nightLight") if k in iaq}
            d["name"] = iaq.get("dispName") or d["name"]
        elif mtype == "SensorHubStatus":
            for sensor in msg.get("sensors") or []:
                for m in sensor.get("measurements") or []:
                    mid = m.get("id")
                    key = MEASUREMENTS.get(mid, (f"measurement_{mid}",))[0]
                    entry = d["measurements"].setdefault(key, {})
                    entry["value"] = m.get("reading")
                    entry["status"] = m.get("status")
                    if m.get("currentState") is not None:
                        entry["state_code"] = m["currentState"]
                        entry["state"] = IAQ_STATES.get(str(m["currentState"]), "Unknown")
        elif mtype == "IaqMonitorStatus":
            code = msg.get("currentState")
            d["iaq_state_code"] = code
            d["iaq_state"] = IAQ_STATES.get(str(code), "Unknown")
            d["rssi"] = msg.get("wifiRSSI")
            d["diag"] = msg.get("diagCodes") or []
            for sensor in msg.get("sensors") or []:
                for m in sensor.get("measurements") or []:
                    mid = m.get("id")
                    key = MEASUREMENTS.get(mid, (f"measurement_{mid}",))[0]
                    st = m.get("currentState")
                    if st is not None:
                        d["measurements"].setdefault(key, {})["state_code"] = st
                        d["measurements"][key]["state"] = IAQ_STATES.get(str(st), "Unknown")
        # DeviceWifiStatus / CalibrationData etc. are ignored on purpose

    for d in devices.values():
        for key, m in d["measurements"].items():
            m.setdefault("state", None)
            m.setdefault("unit", None)
            m.setdefault("label", key)
            m["available"] = m.get("status") in (None, "reporting")
        d["readings"] = {
            k: m["value"] for k, m in d["measurements"].items() if m.get("value") is not None
        }
    return devices
