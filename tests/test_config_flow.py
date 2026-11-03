"""Manual setup and discovery config flow tests."""

from __future__ import annotations

from collections.abc import Iterator
from ipaddress import ip_address
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.weatherxm_gateway.api import GatewayApi
from custom_components.weatherxm_gateway.const import DOMAIN


@pytest.fixture(autouse=True)
def no_network_client_session(mock_zeroconf: MagicMock) -> Iterator[None]:
    """Avoid opening a real aiohttp connector in mocked config flows."""
    # Resolving a config flow may initialize Zeroconf; the fixture keeps it mocked.
    with (
        patch(
            "custom_components.weatherxm_gateway.config_flow.async_get_clientsession",
            return_value=object(),
        ),
        patch.object(
            GatewayApi,
            "async_get_observations",
            return_value={"has_weather": False, "timestamp": None},
        ),
        patch.object(GatewayApi, "async_get_status", return_value={}),
    ):
        yield


INFO = {
    "gateway_id": "WXM-12345678",
    "model": "WXM-WG1200",
    "device_name": "Test Gateway",
    "station": {"paired_id": 19},
}


async def _info(_: GatewayApi) -> dict:
    return INFO


async def test_manual_setup_creates_entry(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Manual host setup validates and stores gateway details."""
    with patch.object(GatewayApi, "async_get_info", _info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={"host": "192.168.1.20", "port": 80},
        )
    assert result["type"] == "create_entry"
    assert result["title"] == "Test Gateway"
    assert result["data"] == {"host": "192.168.1.20", "port": 80}
    assert result["result"].unique_id == "WXM-12345678"


async def test_multiple_gateways_have_independent_entries(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Different stable gateway identities can be added at once."""

    async def get_info(_: GatewayApi) -> dict:
        return {**INFO, "gateway_id": f"WXM-{_.host}"}

    with patch.object(GatewayApi, "async_get_info", get_info):
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={"host": "gateway-one.local"}
        )
        second = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data={"host": "gateway-two.local"}
        )
    assert first["type"] == second["type"] == "create_entry"
    assert first["result"].unique_id != second["result"].unique_id


async def test_zeroconf_setup_and_ip_change_updates_existing_entry(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Discovery verifies identity and refreshes an existing gateway address."""

    def service(ip: str) -> ZeroconfServiceInfo:
        return ZeroconfServiceInfo(
            ip_address=ip_address(ip),
            ip_addresses=[ip_address(ip)],
            port=80,
            hostname="weatherxm.local.",
            type="_weatherxm._tcp.local.",
            name="WeatherXM",
            properties={"model": "WXM-WG1200", "id": "WXM-12345678"},
        )

    with patch.object(GatewayApi, "async_get_info", _info):
        first = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "zeroconf"}, data=service("192.168.1.20")
        )
        duplicate = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "zeroconf"}, data=service("192.168.1.21")
        )
    assert first["type"] == "create_entry"
    assert duplicate["type"] == "abort"
    assert duplicate["reason"] == "already_configured"
    assert (
        hass.config_entries.async_get_entry(first["result"].entry_id).data["host"]
        == "192.168.1.21"
    )


async def test_unsupported_model_aborts_zeroconf(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """A service name alone cannot create an entry for another device."""
    info = {**INFO, "model": "OTHER"}
    with patch.object(GatewayApi, "async_get_info", return_value=info):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "zeroconf"},
            data=ZeroconfServiceInfo(
                ip_address=ip_address("192.168.1.22"),
                ip_addresses=[ip_address("192.168.1.22")],
                port=80,
                hostname="other.local.",
                type="_weatherxm._tcp.local.",
                name="Other",
                properties={"model": "WXM-WG1200"},
            ),
        )
    assert result["type"] == "abort"
    assert result["reason"] == "unsupported_device"


async def test_options_flow_sets_polling_intervals(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Weather and diagnostics update intervals can be configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="WXM-OPTIONS",
        data={"host": "gateway.local", "port": 80},
    )
    entry.add_to_hass(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        user_input={"scan_interval": 30, "diagnostic_interval": 120},
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {"scan_interval": 30, "diagnostic_interval": 120}
