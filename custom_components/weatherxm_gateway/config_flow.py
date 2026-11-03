"""Config flow for WeatherXM Gateway Local."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    GatewayApi,
    GatewayConnectionError,
    GatewayError,
    gateway_id,
    info_model,
    supported_model,
    validate_host,
)
from .const import (
    CONF_DIAGNOSTIC_INTERVAL,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DIAGNOSTIC_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_DIAGNOSTIC_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_DIAGNOSTIC_INTERVAL,
    MIN_SCAN_INTERVAL,
)


class WeatherXMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle manual and Zeroconf setup."""

    VERSION = 1

    async def _async_validate(
        self, host: str, port: int
    ) -> tuple[GatewayApi, dict[str, Any]]:
        """Connect and validate supported gateway identity."""
        api = GatewayApi(host, port, async_get_clientsession(self.hass))
        info = await api.async_get_info()
        if not supported_model(info_model(info)):
            raise ValueError("unsupported_device")
        if not gateway_id(info):
            raise ValueError("missing_id")
        return api, info

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input:
            try:
                host = validate_host(user_input[CONF_HOST])
                port = user_input.get(CONF_PORT, DEFAULT_PORT)
                _, info = await self._async_validate(host, port)
            except ValueError as err:
                errors["base"] = (
                    str(err)
                    if str(err) in ("unsupported_device", "missing_id")
                    else "invalid_host"
                )
            except GatewayConnectionError:
                errors["base"] = "cannot_connect"
            except GatewayError:
                errors["base"] = "invalid_response"
            else:
                unique = gateway_id(info)
                assert unique
                await self.async_set_unique_id(unique)
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )
                return self.async_create_entry(
                    title=str(info.get("device_name") or unique),
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    int, vol.Range(min=1, max=65535)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Verify discovered gateway against its API before creating the entry."""
        properties = discovery_info.properties
        if not supported_model(str(properties.get("model", "")).upper()):
            return self.async_abort(reason="unsupported_device")
        host = discovery_info.host
        try:
            api, info = await self._async_validate(
                host, discovery_info.port or DEFAULT_PORT
            )
        except ValueError as err:
            reason = (
                str(err)
                if str(err) in ("unsupported_device", "missing_id")
                else "cannot_connect"
            )
            return self.async_abort(reason=reason)
        except GatewayError:
            return self.async_abort(reason="cannot_connect")
        stable_id = gateway_id(info)
        advertised_id = properties.get("gateway_id") or properties.get("id")
        if not stable_id or (advertised_id and advertised_id != stable_id):
            return self.async_abort(reason="invalid_device")
        await self.async_set_unique_id(stable_id)
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: api.host, CONF_PORT: api.port}
        )
        self.context["title_placeholders"] = {
            "name": str(info.get("device_name") or stable_id)
        }
        return self.async_create_entry(
            title=str(info.get("device_name") or stable_id),
            data={CONF_HOST: api.host, CONF_PORT: api.port},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WeatherXMOptionsFlow:
        """Create options flow."""
        return WeatherXMOptionsFlow()


class WeatherXMOptionsFlow(config_entries.OptionsFlow):
    """Configure polling intervals."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set polling intervals."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(
                    int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                ),
                vol.Required(
                    CONF_DIAGNOSTIC_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_DIAGNOSTIC_INTERVAL, DEFAULT_DIAGNOSTIC_INTERVAL
                    ),
                ): vol.All(
                    int,
                    vol.Range(min=MIN_DIAGNOSTIC_INTERVAL, max=MAX_DIAGNOSTIC_INTERVAL),
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
