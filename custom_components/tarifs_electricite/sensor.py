"""Capteurs : prix, période, prochain changement, abonnement, Tempo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import EntiteTarif
from .tariff import COULEURS, PERIODES

UNITE_PRIX = "EUR/kWh"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    g = hass.data[DOMAIN][entry.entry_id]
    entites: list[SensorEntity] = [
        CapteurPrixActuel(g),
        CapteurPeriode(g),
        CapteurProchainChangement(g),
        CapteurProchainPrix(g),
    ]
    if any(t.abonnement is not None for _d, t in g.tarifs.versions):
        entites.append(CapteurAbonnement(g))
    if g.suivi:
        entites += [CapteurCout(g, p) for p in ("aujourdhui", "semaine", "mois", "annee")]
        entites.append(CapteurCoutAnnuel(g))
        if g.suivi.mode == "mensualites":
            entites.append(CapteurMensualite(g))
            if g.suivi.mensualite:
                entites.append(CapteurEcart(g))
                if g.suivi.debut_facturation:
                    entites.append(CapteurSolde(g))
        elif g.suivi.debut_facturation:
            entites += [CapteurFacture(g, "facture_en_cours", "montant_actuel"),
                        CapteurFacture(g, "facture_estimee", "montant_estime"),
                        CapteurProchaineFacture(g)]
    if g.tempo:
        entites += [
            CapteurCouleurTempo(g, "tempo_aujourdhui"),
            CapteurCouleurTempo(g, "tempo_demain"),
            CapteurPrevisionsTempo(g),
        ]
    async_add_entities(entites)


class CapteurPrixActuel(EntiteTarif, SensorEntity):
    """Prix du kWh en ce moment. C'est le capteur à donner au tableau Énergie."""

    _attr_native_unit_of_measurement = UNITE_PRIX
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4
    _attr_icon = "mdi:cash-clock"
    _unrecorded_attributes = frozenset({"previsions", "grille", "historique_prix"})

    def __init__(self, g) -> None:
        super().__init__(g, "prix_actuel", "sensor")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Le suivi de consommation lit l'historique de ce capteur
        self.g.entite_prix = self.entity_id

    @property
    def native_value(self):
        return self.g.etat.get("prix")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        e = self.g.etat
        attrs = {
            "fournisseur": e.get("fournisseur"),
            "offre": e.get("offre"),
            "type_offre": e.get("type_offre"),
            "periode": e.get("periode"),
            "periode_libelle": e.get("periode_libelle"),
            "heures_creuses": e.get("heures_creuses"),
            "prix_bas": e.get("prix_bas"),
            "jour_special": e.get("jour_special"),
            "saison": e.get("saison"),
            "couleur_tempo": e.get("couleur_tempo"),
            "prochain_changement": (
                e["prochain_changement"].isoformat() if e.get("prochain_changement") else None
            ),
            "prochaine_periode": e.get("prochaine_periode"),
            "prochaine_periode_libelle": e.get("prochaine_periode_libelle"),
            "prochain_prix": e.get("prochain_prix"),
            "prix_min_24h": e.get("prix_min_24h"),
            "prix_max_24h": e.get("prix_max_24h"),
            "abonnement_mensuel": e.get("abonnement_mensuel"),
            "puissance_kva": e.get("puissance_kva"),
            "grille": e.get("grille"),
            "previsions": e.get("previsions"),
        }
        for cle in ("jours_speciaux", "source_prix", "previsions_disponibles",
                    "historique_prix", "evolution_prevue", "suivi"):
            if cle in e:
                attrs[cle] = e[cle]
        if "tempo_aujourdhui" in e:
            attrs["tempo_aujourdhui"] = e.get("tempo_aujourdhui")
            attrs["tempo_demain"] = e.get("tempo_demain")
            attrs["tempo_previsions"] = e.get("tempo_previsions")
        return attrs


class CapteurPeriode(EntiteTarif, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    # États en minuscules : hp, hc, hsc, perso, we, we_hc, base, dyn
    _attr_options = [p.lower() for p in PERIODES]
    _attr_icon = "mdi:clock-time-four-outline"

    def __init__(self, g) -> None:
        super().__init__(g, "periode", "sensor")

    @property
    def native_value(self):
        periode = self.g.etat.get("periode")
        return periode.lower() if periode else None

    @property
    def extra_state_attributes(self):
        return {"libelle": self.g.etat.get("periode_libelle")}


class CapteurProchainChangement(EntiteTarif, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:timer-sand"

    def __init__(self, g) -> None:
        super().__init__(g, "prochain_changement", "sensor")

    @property
    def native_value(self):
        return self.g.etat.get("prochain_changement")

    @property
    def extra_state_attributes(self):
        return {"prochaine_periode": self.g.etat.get("prochaine_periode")}


class CapteurProchainPrix(EntiteTarif, SensorEntity):
    _attr_native_unit_of_measurement = UNITE_PRIX
    _attr_suggested_display_precision = 4
    _attr_icon = "mdi:cash-fast"

    def __init__(self, g) -> None:
        super().__init__(g, "prochain_prix", "sensor")

    @property
    def native_value(self):
        return self.g.etat.get("prochain_prix")


class CapteurAbonnement(EntiteTarif, SensorEntity):
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:file-document-outline"

    def __init__(self, g) -> None:
        super().__init__(g, "abonnement_mensuel", "sensor")

    @property
    def native_value(self):
        return self.g.etat.get("abonnement_mensuel")


class CapteurCouleurTempo(EntiteTarif, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(COULEURS)
    _attr_icon = "mdi:palette"

    def __init__(self, g, cle: str) -> None:
        super().__init__(g, cle, "sensor")

    @property
    def native_value(self):
        return self.g.etat.get(self._cle)


class CapteurPrevisionsTempo(EntiteTarif, SensorEntity):
    """État : couleur prévue après-demain ; attribut `previsions` : jusqu'à 15 jours."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(COULEURS)
    _attr_icon = "mdi:calendar-range"
    _unrecorded_attributes = frozenset({"previsions"})

    def __init__(self, g) -> None:
        super().__init__(g, "tempo_previsions", "sensor")

    @property
    def native_value(self):
        prev = self.g.etat.get("tempo_previsions") or []
        return prev[2]["couleur"] if len(prev) > 2 else None

    @property
    def extra_state_attributes(self):
        prev = self.g.etat.get("tempo_previsions") or []
        return {
            "previsions": prev,
            "source": "calendrier-tempo.fr",
            "service_disponible": self.g.etat.get("tempo_disponible"),
        }


# ---------------------------------------------------------------- suivi de consommation
class _CapteurSuivi(EntiteTarif, SensorEntity):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 2

    def _suivi(self) -> dict:
        return self.g.etat.get("suivi") or {}

    @property
    def available(self) -> bool:
        return self._suivi().get("etat") == "ok"


class CapteurCout(_CapteurSuivi):
    """Coût de la période : énergie consommée + part d'abonnement."""

    _attr_icon = "mdi:cash-multiple"

    def __init__(self, g, periode: str) -> None:
        super().__init__(g, f"cout_{periode}", "sensor")
        self._periode = periode

    @property
    def native_value(self):
        return (self._suivi().get(self._periode) or {}).get("total")

    @property
    def extra_state_attributes(self):
        d = dict(self._suivi().get(self._periode) or {})
        d["donnees_jusqua"] = self._suivi().get("donnees_jusqua")
        return d


class CapteurMensualite(_CapteurSuivi):
    """Mensualité qui couvrirait la consommation des 12 derniers mois aux prix actuels."""

    _attr_icon = "mdi:calendar-month"
    _attr_native_unit_of_measurement = "EUR"

    def __init__(self, g) -> None:
        super().__init__(g, "mensualite_estimee", "sensor")

    @property
    def native_value(self):
        return (self._suivi().get("estimation") or {}).get("mensualite_estimee")

    @property
    def extra_state_attributes(self):
        return self._suivi().get("estimation") or {}


class CapteurEcart(_CapteurSuivi):
    """Mensualité estimée moins mensualité du fournisseur (positif : régularisation à prévoir)."""

    _attr_icon = "mdi:scale-unbalanced"

    def __init__(self, g) -> None:
        super().__init__(g, "ecart_mensualite", "sensor")

    @property
    def native_value(self):
        return (self._suivi().get("estimation") or {}).get("ecart_mensuel")

    @property
    def extra_state_attributes(self):
        e = self._suivi().get("estimation") or {}
        return {k: e.get(k) for k in ("ecart_pct", "mensualite_estimee", "mensualite_fournisseur",
                                      "regularisation_annuelle_estimee", "conseil", "fiabilite")}


class CapteurSolde(_CapteurSuivi):
    """Payé moins consommé depuis le début de la période de facturation."""

    _attr_icon = "mdi:piggy-bank"

    def __init__(self, g) -> None:
        super().__init__(g, "solde_estime", "sensor")

    @property
    def native_value(self):
        return (self._suivi().get("solde") or {}).get("solde")

    @property
    def extra_state_attributes(self):
        return self._suivi().get("solde") or {}


class CapteurCoutAnnuel(_CapteurSuivi):
    """Coût sur un an d'après la consommation des 12 derniers mois, aux prix actuels."""

    _attr_icon = "mdi:calendar-blank-multiple"

    def __init__(self, g) -> None:
        super().__init__(g, "cout_annuel_estime", "sensor")

    @property
    def native_value(self):
        return (self._suivi().get("estimation") or {}).get("cout_annuel_estime")

    @property
    def extra_state_attributes(self):
        return self._suivi().get("estimation") or {}


class CapteurFacture(_CapteurSuivi):
    """Facture de la période en cours (paiement à la consommation réelle)."""

    _attr_icon = "mdi:receipt-text-outline"

    def __init__(self, g, cle: str, champ: str) -> None:
        super().__init__(g, cle, "sensor")
        self._champ = champ

    @property
    def native_value(self):
        return (self._suivi().get("facture") or {}).get(self._champ)

    @property
    def extra_state_attributes(self):
        return self._suivi().get("facture") or {}


class CapteurProchaineFacture(_CapteurSuivi):
    _attr_device_class = SensorDeviceClass.DATE
    _attr_native_unit_of_measurement = None
    _attr_suggested_display_precision = None
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, g) -> None:
        super().__init__(g, "prochaine_facture", "sensor")

    @property
    def native_value(self):
        from datetime import date

        d = (self._suivi().get("facture") or {}).get("prochaine_facture")
        return date.fromisoformat(d) if d else None
