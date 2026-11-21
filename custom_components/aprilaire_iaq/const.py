"""Constants for the AprilAire Healthy Air Monitor integration."""
DOMAIN = "aprilaire_iaq"
BRAND = "AprilAire"
MANUFACTURER = "Computime"

API_BASE = "https://device.aprilaire.io"
WS_URL = "wss://socket.aprilaire.io/"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"

DEFAULT_INTERVAL = 60
WS_TIMEOUT = 40

# measurement id -> (key, device_class hint, unit)
MEASUREMENTS = {
    0: ("temperature", "temperature", "°C"),
    1: ("humidity", "humidity", "%"),
    2: ("pm25", "pm25", "µg/m³"),
    3: ("pm10", "pm10", "µg/m³"),
    4: ("tvoc", "tvoc", None),
    5: ("co2", "co2", "ppm"),
    6: ("nox", "nox", None),
    7: ("proximity", "proximity", None),
}

# IAQMonitorStatus.currentState / measurement currentState -> label
IAQ_STATES = {
    "-1": "Unknown",
    "0": "Good",
    "1": "Fair",
    "2": "Concerning",
    "3": "Unhealthy",
    "4": "Unhealthy",
    "5": "Night Light",
}
