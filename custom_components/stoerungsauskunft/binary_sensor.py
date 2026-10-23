"""Binärsensor je Sektor: an bei offizieller Störung oder auffälliger Meldungs-Häufung."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StoerungsConfigEntry
from .entity import StoerungsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StoerungsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(ProblemSensor(coordinator, s, "problem") for s in coordinator.sectors)


class ProblemSensor(StoerungsEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return self.state_data.problem

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self.state_data
        return {
            "official": bool(st.outages),
            "suspected": st.suspected,
            "official_postal_codes": sorted({o["postal_code"] for o in st.outages}),
            "suspected_postal_codes": sorted({a["postal_code"] for a in st.areas if a["suspected"]}),
        }
