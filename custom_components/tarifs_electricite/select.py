"""Sélecteurs « Jour spécial aujourd'hui / demain ».

Sans entité source, c'est ici (ou dans la carte, d'un appui) qu'on indique
qu'aujourd'hui ou demain est un jour Sobriété, Éclair, Sérénité… Avec une
entité source configurée, les sélecteurs suivent cette source.
"""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import NORMAL
from .const import DOMAIN
from .entity import EntiteTarif


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    g = hass.data[DOMAIN][entry.entry_id]
    if not g.noms_speciaux:
        return
    async_add_entities([SelectJourSpecial(g, "aujourdhui"), SelectJourSpecial(g, "demain")])


class SelectJourSpecial(EntiteTarif, SelectEntity, RestoreEntity):
    _attr_icon = "mdi:calendar-star"

    def __init__(self, g, quand: str) -> None:
        super().__init__(g, f"jour_special_{quand}", "select")
        self._quand = quand
        self._attr_options = [NORMAL, *g.noms_speciaux]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        precedent = await self.async_get_last_state()
        if precedent is not None:
            self.g.restaurer_jour_special(
                self._quand, precedent.state, precedent.attributes.get("jour")
            )
            self.g._recalculer()

    @property
    def current_option(self):
        return self.g.jour_special(self._quand)

    @property
    def extra_state_attributes(self):
        jour = self.g.js_jour
        if jour is not None and self._quand == "demain":
            from datetime import timedelta

            jour = jour + timedelta(days=1)
        return {
            "jour": jour.isoformat() if jour else None,
            "pilote_par_source": self.g.est_auto(self._quand),
            "debut_journee_h": self.g.tarif.debut_jour_special,
        }

    async def async_select_option(self, option: str) -> None:
        self.g.choisir_jour_special(self._quand, option)
