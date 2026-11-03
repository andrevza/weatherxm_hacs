"""Constants for WeatherXM Gateway Local."""

from datetime import timedelta

DOMAIN = "weatherxm_gateway"
PLATFORMS = ("sensor", "binary_sensor", "weather")
DEFAULT_PORT = 80
DEFAULT_SCAN_INTERVAL = 20
DEFAULT_DIAGNOSTIC_INTERVAL = 60
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600
MIN_DIAGNOSTIC_INTERVAL = 30
MAX_DIAGNOSTIC_INTERVAL = 3600
REQUEST_TIMEOUT = 8
MAX_RESPONSE_BYTES = 256_000
CONF_PORT = "port"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_DIAGNOSTIC_INTERVAL = "diagnostic_interval"
SERVICE_TYPE = "_weatherxm._tcp.local."
MODEL = "WXM-WG1200"
PLATFORMS_INTERVALS = {"weather": timedelta(seconds=DEFAULT_SCAN_INTERVAL)}

KEY_INFO = "info"
KEY_OBSERVATIONS = "observations"
KEY_STATUS = "status"
