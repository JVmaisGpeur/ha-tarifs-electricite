"""Capteurs binaires : heures creuses, super creuses, prix bas, jour spécial."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EntiteTarif


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    g = hass.data[DOMAIN][entry.entry_id]
    t = g.tarifs
    entites = [BinaireTarif(g, "prix_bas", "mdi:piggy-bank-outline")]
    if t.a_heures_creuses:
        entites.append(BinaireTarif(g, "heures_creuses", "mdi:weather-night"))
    if t.a_hsc:
        entites.append(BinaireTarif(g, "heures_super_creuses", "mdi:weather-night-partly-cloudy"))
    if g.noms_speciaux:
        entites.append(BinaireJourSpecial(g))
    async_add_entities(entites)


class BinaireTarif(EntiteTarif, BinarySensorEntity):
    def __init__(self, g, cle: str, icone: str) -> None:
        super().__init__(g, cle, "binary_sensor")
        self._attr_icon = icone

    @property
    def is_on(self):
        return bool(self.g.etat.get(self._cle))

    @property
    def extra_state_attributes(self):
        e = self.g.etat
        return {
            "periode": e.get("periode_libelle"),
            "prix": e.get("prix"),
            "prochain_changement": (
                e["prochain_changement"].isoformat() if e.get("prochain_changement") else None
            ),
        }


class BinaireJourSpecial(EntiteTarif, BinarySensorEntity):
    """`on` quand le prix du moment est celui d'un jour spécial (Sobriété…)."""

    _attr_icon = "mdi:calendar-alert"

    def __init__(self, g) -> None:
        super().__init__(g, "jour_special", "binary_sensor")

    @property
    def is_on(self):
        return bool(self.g.etat.get("jour_special"))

    @property
    def extra_state_attributes(self):
        js = self.g.etat.get("jours_speciaux") or {}
        return {
            "jour_special": self.g.etat.get("jour_special"),
            "aujourdhui": js.get("aujourdhui"),
            "demain": js.get("demain"),
        }
