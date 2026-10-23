"""Sensoren: Anzahl offizieller Störungen und Anzahl Bürgermeldungen je Sektor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import StoerungsConfigEntry
from .entity import StoerungsEntity

MAX_ITEMS = 50  # Attribute klein halten


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StoerungsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for sector in coordinator.sectors:
        entities += [OutageSensor(coordinator, sector, "outages"),
                     ReportSensor(coordinator, sector, "reports")]
    async_add_entities(entities)


class OutageSensor(StoerungsEntity, SensorEntity):
    """Aktive offizielle Störungen der Netzbetreiber im Gebiet."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "Störungen"
    _unrecorded_attributes = frozenset({"outages", "planned"})

    @property
    def native_value(self) -> int:
        return len(self.state_data.outages)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self.state_data
        return {
            "outages": st.outages[:MAX_ITEMS],
            "planned": st.planned[:MAX_ITEMS],
            "postal_codes": sorted({o["postal_code"] for o in st.outages}),
        }


class ReportSensor(StoerungsEntity, SensorEntity):
    """Bürgermeldungen in laufenden Häufungen (ohne Adressen)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "Meldungen"
    _unrecorded_attributes = frozenset({"areas"})

    @property
    def native_value(self) -> int:
        return self.state_data.report_count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        st = self.state_data
        return {
            "areas": st.areas[:MAX_ITEMS],
            "suspected_postal_codes": sorted({a["postal_code"] for a in st.areas if a["suspected"]}),
        }
