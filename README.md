# WeatherXM Gateway Local

WeatherXM Gateway Local is a Home Assistant custom integration for local, read-only access to a WeatherXM WG1200 gateway. It polls the gateway's local HTTP API; normal operation requires no WeatherXM cloud account, token, or Internet connection. It supports multiple gateways, manual host/IP configuration, and native `_weatherxm._tcp.local.` discovery.

This is an independent community project. It is not an official WeatherXM integration and is not maintained, supported, or endorsed by WeatherXM.

## Supported hardware and firmware

- WeatherXM WG1200 gateway running firmware with `/api/v1/info`, `/api/v1/observations`, and `/status` endpoints.
- The API field variants in firmware 0.8.34 and the inspected 0.8.39 source are handled, including both `station.packet_reception` and the older `station.reception` spelling.
- Firmware 0.8.34 is known to report an incorrect wind direction in some cases. The integration passes through the gateway's reported direction and cannot repair incorrect firmware readings. Accurate direction requires an upstream firmware fix. Valid 0° North values are retained.

## Installation

### HACS custom repository

1. In Home Assistant, open **HACS → Integrations → ⋮ → Custom repositories**.
2. Add [this repository](https://github.com/andrevza/weatherxm_hacs) and select **Integration**.
3. Install **WeatherXM Gateway Local**, then restart Home Assistant.

The repository is configured for direct HACS custom-repository installation. Inclusion in HACS's default catalog is separate and requires Home Assistant Brands registration and the applicable HACS publishing checks ([HACS publishing requirements](https://www.hacs.dev/docs/publish/integration/)).

### Manual installation

Copy `custom_components/weatherxm_gateway` into `<config>/custom_components/weatherxm_gateway` and restart Home Assistant.

## Setup

After restart, Home Assistant can discover gateways advertising `_weatherxm._tcp.local.`. Discovery is verified against `/api/v1/info` and the gateway model and stable ID before an entry is created. If discovery is unavailable, add **WeatherXM Gateway Local** from **Settings → Devices & services → Add integration**, and enter the gateway hostname or IP address and HTTP port (default 80).

Use a reachable address from the Home Assistant host. Multiple gateway entries are supported; gateway IDs keep their device and entity IDs stable if their IP addresses change.

## Entities

Weather sensors include temperature, feels-like temperature, humidity, pressure, wind speed and gust, wind direction, rainfall rate, daily rainfall, rolling 24-hour rainfall, lifetime rainfall, UV index, and solar irradiance. Daily and rolling rainfall use measurement state semantics because their values can reset or decrease. Only lifetime rainfall uses `total_increasing`.

Diagnostic entities are created when their source fields are available: packet reception, Wi-Fi signal and state, gateway firmware and API versions, paired station type, firmware and ID, station radio RSSI/SNR, latest observation time, and Wi-Fi/station connectivity.

The native weather entity exposes measured temperature, apparent temperature, humidity, pressure, wind speed, gust and bearing. It has no forecast and does not infer a sky condition from irradiance, humidity, or rainfall.

The integration converts recognized API units to canonical native units (°C, m/s, hPa and mm), which Home Assistant then converts to the user's configured unit system. Unknown or malformed units produce unavailable measurements instead of mislabeled values. Missing, null, invalid, stale, or explicitly absent observations are unavailable. The client does not expose station battery fields because the standard REST API has not confirmed them.

## Options

Default intervals are 20 seconds for weather observations and 60 seconds for gateway diagnostics. Both can be changed in the integration's options. Weather updates accept 10–3600 seconds; diagnostics accept 30–3600 seconds.

## Privacy and local operation

The integration issues only GET requests to `/api/v1/info`, `/api/v1/observations`, and `/status`. It does not modify gateway settings, follow HTTP redirects, expose Wi-Fi credentials, scrape the web interface, or make cloud requests. API responses are size-limited and requests have an 8-second timeout.

## Troubleshooting

- **No discovery:** ensure Home Assistant's Zeroconf integration is enabled and multicast DNS can cross the network segment. Otherwise use manual setup.
- **Cannot connect:** verify the gateway address, port, and that Home Assistant can reach the gateway's local HTTP service.
- **No weather values:** check that the station is paired and that `/api/v1/observations` reports `has_weather: true` with a recent timestamp.
- **Wind direction seems wrong:** firmware 0.8.34 has a known decoding/reporting issue. The integration does not substitute its own value; check for an upstream firmware correction.
- **Units show unavailable:** check the gateway's `units` fields for valid supported units.

## Reporting issues

Include Home Assistant version, integration version, gateway firmware version, relevant endpoint names and redacted example responses. Do not include Wi-Fi credentials or public network details. [Report integration issues here](https://github.com/andrevza/weatherxm_hacs/issues).

## Development

See [docs/architecture.md](docs/architecture.md). The test suite uses mocked responses and does not require a gateway. Run `pytest`, `ruff check .`, and `ruff format --check .` in the project’s Python 3.14 development environment.

### Validate captured endpoint responses offline

Save the raw JSON from `/api/v1/info`, `/api/v1/observations`, and `/status` into separate files, then run:

```sh
python scripts/validate_captures.py \
  --info /path/to/info.json \
  --observations /path/to/observations.json \
  --status /path/to/status.json
```

The validator uses the integration’s parser, unit conversions, sensor descriptions, diagnostic extraction, and freshness policy. It makes no network requests. The bundled files in `tests/fixtures/` are firmware-shaped examples, not captures from a physical gateway.
