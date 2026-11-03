# Changelog

Notable changes to WeatherXM Gateway Local are recorded here. This project is independently maintained and is not an official WeatherXM project.

## [0.2.0] - 2026-11-03

### Added

- Optional estimated weather conditions from local station readings. The default condition remains Unknown; cloud-dependent conditions are not inferred.
- Gateway Visit link and expanded device metadata.
- Downloadable, privacy-redacted diagnostics and additional gateway, station, and SD-card diagnostics.
- Independent integration branding.

### Changed

- Frequently changing diagnostic entities, including Latest observation, uptime, counters, and packet age, are disabled by default to reduce Activity and Recorder noise.
- Documented the WeatherXM WG1200 firmware update path and compatibility caution.

## [0.1.0]

### Added

- Initial local WG1200 integration with manual and Zeroconf setup, weather measurements, native weather entity, and gateway diagnostics.
