"""Base commune des entités."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_MAJ, VERSION


class EntiteTarif(Entity):
    """Entité liée à un contrat ; identifiants identiques sur toutes les installations."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, gestionnaire, cle: str, plateforme: str) -> None:
        self.g = gestionnaire
        self._cle = cle
        entry = gestionnaire.entry
        self._attr_unique_id = f"{entry.entry_id}_{cle}"
        self._attr_translation_key = cle
        # entity_id en français, quelle que soit la langue de Home Assistant
        self.entity_id = f"{plateforme}.tarif_electricite_{cle}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=gestionnaire.tarif.fournisseur or "Fournisseur",
            model=gestionnaire.tarif.offre or None,
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
            # Home Assistant n'accepte que http(s):// ou homeassistant:// (lien interne)
            configuration_url=f"homeassistant://config/integrations/integration/{DOMAIN}",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_MAJ.format(self.g.entry.entry_id), self._maj
            )
        )

    @callback
    def _maj(self) -> None:
        self.async_write_ha_state()
