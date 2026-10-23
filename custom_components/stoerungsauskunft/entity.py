"""Gemeinsame Basisklasse."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SECTORS, SITE
from .coordinator import StoerungsCoordinator
from .model import SectorState


class StoerungsEntity(CoordinatorEntity[StoerungsCoordinator]):
    _attr_has_entity_name = True
    _attr_attribution = "Daten: störungsauskunft.de"

    def __init__(self, coordinator: StoerungsCoordinator, sector: int, kind: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self.sector = sector
        key = SECTORS[sector]["key"]
        self._attr_unique_id = f"{entry.entry_id}_{key}_{kind}"
        self._attr_translation_key = kind
        self._attr_translation_placeholders = {"sector": SECTORS[sector]["name"]}
        self._attr_icon = SECTORS[sector]["icon"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Störungsauskunft {entry.title}",
            manufacturer="störungsauskunft.de",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=SITE,
        )

    @property
    def state_data(self) -> SectorState:
        return self.coordinator.data.get(self.sector, SectorState())
