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

The integration ships its own `brand/icon.png` and `brand/icon@2x.png`. Home Assistant 2026.3 and newer use these local files after installation. Some HACS repository views may still show a generic icon for a custom repository; this does not mean the local branding is missing. Home Assistant's Marketplace, available with 2026.11, includes the custom-integration branding display fix.

### Manual installation

Copy `custom_components/weatherxm_gateway` into `<config>/custom_components/weatherxm_gateway` and restart Home Assistant.

## Setup

After restart, Home Assistant can discover gateways advertising `_weatherxm._tcp.local.`. Discovery is verified against `/api/v1/info` and the gateway model and stable ID before an entry is created. If discovery is unavailable, add **WeatherXM Gateway Local** from **Settings → Devices & services → Add integration**, and enter the gateway hostname or IP address and HTTP port (default 80).

Use a reachable address from the Home Assistant host. Multiple gateway entries are supported; gateway IDs keep their device and entity IDs stable if their IP addresses change.

## Entities

Weather sensors include temperature, feels-like temperature, humidity, pressure, wind speed and gust, wind direction, rainfall rate, daily rainfall, rolling 24-hour rainfall, lifetime rainfall, UV index, and solar irradiance. Daily and rolling rainfall use measurement state semantics because their values can reset or decrease. Only lifetime rainfall uses `total_increasing`.

Diagnostic entities are created when their source fields are available: packet reception, Wi-Fi signal and state, gateway firmware and API versions, paired station type, firmware and ID, station radio RSSI/SNR, latest observation time, and Wi-Fi/station connectivity.

The gateway device page includes the gateway's model, firmware, validated MAC address and serial identifier where the API supplies valid values. Its **Visit** link opens the local gateway web interface using the configured host and port (including VPN hostnames and IPv6); the reported Wi-Fi IP is only a fallback. If Zeroconf updates the configured address, the link is refreshed while the existing device and entity identities remain stable. Home Assistant's user-customized device name is preserved.

Additional diagnostics include MQTT, LoRa, pairing and uplink connectivity; SD-card present, mounted and unusable states; SD capacity and filesystem; and paired-station radio signal. The gateway uptime, packet and MQTT counters, station packet age, activity state, receive frequency, pairing state, ownership state, SD status reason, and **Latest observation** are disabled by default because they are advanced or change frequently. To use one, open **Settings → Devices & services → Entities**, select the integration's disabled entities, and enable it. Uptime remains in seconds and is also included in downloadable diagnostics without enabling its entity. Home Assistant Activity and Recorder are separate: disabling frequent entities by default avoids their routine state updates in Activity and avoids default Recorder writes for those entities; enabling them opts into normal history behavior.

From the integration's device or config-entry page, use **Download diagnostics** to export a JSON snapshot of coordinator health, available/missing fields, observation freshness, and allowlisted gateway, station, radio and SD information. IDs, MAC addresses, IPs, hostnames, SSIDs, friendly names, coordinates and URLs are redacted or omitted. Diagnostics use the already-polled API data and do not make additional gateway requests. Treat downloads as potentially public and review them before sharing.

Gateway web access depends on Home Assistant being able to route to the configured address. A VPN address or manually configured hostname is preferred over the gateway's reported Wi-Fi address; ensure it remains reachable from the Home Assistant host. Diagnostics are limited to fields currently returned by the firmware, and the integration does not infer unavailable radio, station, or SD values.

**Latest observation** is disabled by default because its timestamp changes on every weather poll and would otherwise add a routine entry to Home Assistant Activity. Existing installations that already have this entity enabled must disable it once from its entity settings; the default applies when Home Assistant first creates the entity. It keeps its existing unique ID and remains available to enable again when needed. Weather polling, freshness checks, other diagnostics, and weather history are unaffected. Once enabled, its timestamp is recorded like other enabled entities.

The native weather entity exposes measured temperature, apparent temperature, humidity, pressure, wind speed, gust and bearing. It has no forecast. Its condition is **Unknown** by default because the gateway does not report cloud cover or an authoritative condition. To opt in, open the integration's **Options** and enable **Estimate weather condition from station readings**. The estimator reports `rainy` or `pouring` from rainfall rate, `windy` above 40 km/h, and `sunny` when irradiance is strong (at least 500 W/m², or at least 300 W/m² with UV index 6 or higher). Rain takes priority over wind, and wind takes priority over sun. UV only supports an irradiance reading; UV alone does not mean sunny. If none of those rules match, the condition remains Unknown. It never guesses `partlycloudy` or `clear-night`, since cloud cover is unavailable. These are local estimates, not conditions reported by WeatherXM, and the option does not change sensor readings or polling.

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
