# Contributor and coding-agent guide

## Project identity

- This is the independent **WeatherXM Gateway Local** Home Assistant integration.
- Integration domain: `weatherxm_gateway`; display name: `WeatherXM Gateway Local`.
- Repository: `https://github.com/andrevza/weatherxm_hacs`.
- It is not maintained, supported, or endorsed by WeatherXM. Keep upstream firmware links intact, but do not imply upstream ownership of this integration.
- Preserve the MIT license and existing copyright notices.

## Architecture and behavior

- The integration is read-only. Its REST client polls `/api/v1/info`, `/api/v1/observations`, and `/status`; do not add gateway writes, cloud requests, or extra polling without a demonstrated need.
- Weather observations and gateway diagnostics use separate coordinators. Options changes reload the config entry.
- Preserve the single gateway device and the existing config-entry identifier and entity unique IDs. Use the gateway ID, never the station's paired ID, for gateway identity.
- Preserve user-customized device names. Validate optional API metadata, and prefer the configured host and port for the device's Visit link.
- Preserve valid numeric zero values, especially 0° wind direction. Read packet reception from the verified `station.packet_reception` field (or `/status`'s `packet_reception` field).
- Weather condition is Unknown by default. Estimated conditions are opt-in; do not invent cloud cover, partly-cloudy, or clear-night conditions. See `README.md` for the estimator rules.
- Keep fast-changing timestamp, uptime, counter, and packet-age entities disabled by default. Counters can reset, so do not give them a monotonic state class without verified reset semantics.
- Keep diagnostics allowlisted and privacy-conscious. Never dump complete API
  payloads or commit real captures, gateway IDs, MAC addresses, hostnames, IP
  addresses, SSIDs, coordinates, or credentials. Use sanitized synthetic fixtures.

## Development and validation

- Read `README.md`, `docs/architecture.md`, and this file before changing integration behavior.
- Use the project's Python 3.14 development dependencies from
  `requirements-dev.txt`; do not install dependencies on a user's base machine.
  A disposable Docker environment is suitable.
- Run the CI checks before submitting changes:

  ```sh
  ruff check .
  ruff format --check .
  pytest -q
  ```

- Run Home Assistant hassfest as well. CI uses `home-assistant/actions/hassfest@master`.
  For a local Docker run, mount the repository at `/github/workspace` in the
  `ghcr.io/home-assistant/hassfest` image.
- Validate `manifest.json`, `hacs.json`, translations, entity descriptions, units, device classes, and unique IDs when changing integration metadata or entities.
- Tests must not contact a real gateway or Home Assistant production instance. Use mocked API responses and sanitized fixtures.

## Versioning and changelog

- For each user-facing release, bump `custom_components/weatherxm_gateway/manifest.json` using semantic versioning and add a matching entry to `CHANGELOG.md`.
- Keep the manifest version and changelog release version aligned. Documentation-only changes do not require a version bump unless they are part of a planned release.
- Do not amend or force-push published history. Use a new commit for follow-up changes.
