"""Tarifs Électricité : votre contrat d'électricité, quel que soit le fournisseur.

Expose le prix du kWh en cours, la période (HP/HC/HSC), la couleur Tempo et
les prévisions de prix, pour les cartes, automatisations et autres intégrations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    HORIZON_PREVISIONS_H,
    NORMAL,
    SERVICE_COMPARER,
    SERVICE_PREVISIONS,
    SERVICE_PRIX_PASSES,
    SIGNAL_MAJ,
    TEMPO_INTERVALLE_MIN,
    URL_CARTE,
    VERSION,
    VERSION_INTERFACE,
)
from .tariff import (
    OFFRE_DYN,
    OFFRE_TEMPO,
    Contexte,
    Tarif,
    TarifVersionne,
    facteur_unite,
    lire_serie_prix,
    meilleur_creneau,
    simplifier,
    trier_versions,
    versions_depuis,
)
from .prix_passes import (
    MAX_JOURS,
    derniere_modification,
    heures_passees,
    prix_revente_de,
    signatures,
)
from .comparaison_ha import Comparateur
from .suivi_ha import SuiviConsommation, lire_reglages_suivi
from .tempo import TempoClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SELECT]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SCHEMA_PREVISIONS = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Optional("heures", default=24): vol.All(vol.Coerce(int), vol.Range(min=1, max=72)),
        vol.Optional("duree"): vol.All(vol.Coerce(float), vol.Range(min=0.25, max=48)),
    }
)

SCHEMA_COMPARER = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Required("debut"): cv.datetime,
        vol.Required("fin"): cv.datetime,
    }
)

SCHEMA_PRIX_PASSES = vol.Schema(
    {
        vol.Optional("config_entry_id"): cv.string,
        vol.Required("debut"): cv.datetime,
        vol.Required("fin"): cv.datetime,
    }
)


class GestionnaireTarif:
    """Calcule l'état du contrat et prévient les entités à chaque changement."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        versions = trier_versions(versions_depuis(entry.data, entry.options))
        # Toutes les grilles du contrat, chacune avec sa date d'effet
        self.tarifs = TarifVersionne(versions)
        # Réglages non tarifaires (sources…) : ceux de la grille la plus récente
        self.cfg = versions[-1]["config"]
        self.tempo: Optional[TempoClient] = (
            TempoClient(async_get_clientsession(hass))
            if OFFRE_TEMPO in self.tarifs.types_offre
            else None
        )
        self.etat: dict[str, Any] = {}
        self._annuler: list = []
        self._annuler_prochain = None
        # Jours spéciaux : choix manuel (sélecteurs) et jour auquel il s'applique
        self.noms_speciaux: list[str] = self.tarifs.noms_speciaux
        self.js_jour = None
        self.js_manuel = {"aujourdhui": NORMAL, "demain": NORMAL}
        # Journal des jours passés (couleurs Tempo, jours spéciaux), pour chiffrer
        # la consommation passée
        self.store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.journal: dict[str, dict] = {"tempo": {}, "speciaux": {}}
        self.entite_prix: Optional[str] = None  # renseigné par le capteur « Prix actuel »
        reglages = lire_reglages_suivi(entry.data, entry.options)
        self.suivi: Optional[SuiviConsommation] = (
            SuiviConsommation(self, reglages) if reglages.get("compteur") else None
        )
        # v1.3.0 : offres à comparer et puissance conseillée
        self.suivi_reglages = reglages
        self.comparateur = Comparateur(self)
        # Prix dynamique
        self._serie_dyn: list = []
        self._dyn_etat: Optional[float] = None

    @property
    def tarif(self) -> Tarif:
        """Grille en vigueur aujourd'hui."""
        return self.tarifs.actif(dt_util.now().date())

    # ------------------------------------------------------------------ sources
    def _sources_speciales(self, demain: bool) -> list[tuple[str, str, str]]:
        """(nom du jour, entité source, valeur attendue) configurés."""
        res = []
        for n in (1, 2):
            nom = (self.cfg.get(f"js{n}_nom") or "").strip()
            ent = self.cfg.get(f"js{n}_source_demain" if demain else f"js{n}_source")
            if nom in self.noms_speciaux and ent:
                res.append((nom, ent, self.cfg.get(f"js{n}_valeur") or "on"))
        return res

    def _special_auto(self, demain: bool) -> tuple[bool, Optional[str]]:
        """(source disponible ?, nom du jour spécial ou None)."""
        disponible = False
        for nom, ent, valeur in self._sources_speciales(demain):
            st = self.hass.states.get(ent)
            if st is None or st.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                continue
            disponible = True
            if simplifier(st.state) == simplifier(valeur):
                return True, nom
        return disponible, None

    def jour_special(self, quand: str) -> str:
        """Jour spécial effectif pour 'aujourdhui' ou 'demain' (NORMAL sinon)."""
        auto, nom = self._special_auto(quand == "demain")
        if auto:
            return nom or NORMAL
        return self.js_manuel[quand]

    def est_auto(self, quand: str) -> bool:
        return self._special_auto(quand == "demain")[0]

    @callback
    def choisir_jour_special(self, quand: str, valeur: str) -> None:
        self.js_manuel[quand] = valeur if valeur in self.noms_speciaux else NORMAL
        self._recalculer()

    @callback
    def restaurer_jour_special(self, quand: str, valeur: str, jour_iso: Optional[str]) -> None:
        """Reprend le choix manuel après un redémarrage, s'il est encore valable."""
        if valeur not in self.noms_speciaux or not jour_iso:
            return
        jd = self.tarif.jour_special_de(dt_util.now())
        if quand == "aujourdhui" and jour_iso == jd.isoformat():
            self.js_manuel["aujourdhui"] = valeur
        elif quand == "demain":
            if jour_iso == (jd + timedelta(days=1)).isoformat():
                self.js_manuel["demain"] = valeur
            elif jour_iso == jd.isoformat():
                self.js_manuel["aujourdhui"] = valeur

    def _special_confirme(self, jour) -> bool:
        """Le type de ce jour est-il connu ? Aujourd'hui oui ; demain s'il a été
        annoncé (source automatique ou choix « jour spécial ») ; au-delà, non."""
        if self.js_jour is None:
            return False
        if jour <= self.js_jour:
            return True
        if jour == self.js_jour + timedelta(days=1):
            return self.est_auto("demain") or self.js_manuel["demain"] != NORMAL
        return False

    def _special_de(self, jour):
        if self.js_jour is None:
            return None
        if jour == self.js_jour:
            v = self.jour_special("aujourdhui")
        elif jour == self.js_jour + timedelta(days=1):
            v = self.jour_special("demain")
        else:
            return None
        return None if v == NORMAL else v

    def _lire_dynamique(self) -> None:
        ent = self.cfg.get("dyn_source")
        st = self.hass.states.get(ent) if ent else None
        self._serie_dyn = []
        self._dyn_etat = None
        if st is None:
            return
        facteur = facteur_unite(st.attributes.get("unit_of_measurement"))
        self._serie_dyn = lire_serie_prix(dict(st.attributes), facteur)
        try:
            self._dyn_etat = float(st.state) * facteur
        except (TypeError, ValueError):
            self._dyn_etat = None

    def _prix_dyn_de(self, dt: datetime) -> Optional[float]:
        for debut, fin, prix in self._serie_dyn:
            if debut <= dt < fin:
                return prix
        # Sans prévisions : le prix affiché vaut pour l'heure en cours
        maintenant = dt_util.now()
        heure = maintenant.replace(minute=0, second=0, microsecond=0)
        if self._dyn_etat is not None and heure <= dt < heure + timedelta(hours=1):
            return self._dyn_etat
        return None

    def contexte(self) -> Contexte:
        return Contexte(
            couleur_de=self.tempo.couleur if self.tempo else None,
            special_de=self._special_de if self.noms_speciaux else None,
            special_confirme_de=self._special_confirme if self.noms_speciaux else None,
            prix_dyn_de=self._prix_dyn_de if OFFRE_DYN in self.tarifs.types_offre else None,
        )

    # ------------------------------------------------------------------ cycle de vie
    async def async_demarrer(self) -> None:
        journal = await self.store.async_load()
        if isinstance(journal, dict):
            self.journal.update(journal)
        # Dernière modification des grilles (pour savoir quand des prix passés ont changé)
        grilles = derniere_modification(
            self.journal.get("grilles"),
            signatures(versions_depuis(self.entry.data, self.entry.options)),
            dt_util.now(),
        )
        if grilles != self.journal.get("grilles"):
            self.journal["grilles"] = grilles
            self._sauver_journal()
        if self.tempo and self.suivi:
            hist = await self.tempo.async_historique()
            if hist:
                self.journal["tempo"].update(hist)
                self._sauver_journal()
        if self.tempo:
            await self.tempo.async_rafraichir(dt_util.now().date(), historique=True)
            self._annuler.append(
                async_track_time_interval(
                    self.hass, self._tempo_periodique, timedelta(minutes=TEMPO_INTERVALLE_MIN)
                )
            )
        a_suivre = [e for _n, e, _v in self._sources_speciales(False) + self._sources_speciales(True)]
        if self.cfg.get("dyn_source"):
            a_suivre.append(self.cfg["dyn_source"])
        if a_suivre:
            self._annuler.append(
                async_track_state_change_event(self.hass, list(set(a_suivre)), self._source_changee)
            )
        self._recalculer()
        if self.suivi:
            await self.suivi.async_demarrer()
        await self.comparateur.async_demarrer()

    def _sauver_journal(self) -> None:
        # On ne garde que deux ans
        limite = (dt_util.now().date() - timedelta(days=731)).isoformat()
        for cle in ("tempo", "speciaux"):
            self.journal[cle] = {j: v for j, v in self.journal[cle].items() if j >= limite}
        self.store.async_delay_save(lambda: self.journal, 30)

    @callback
    def _source_changee(self, _event) -> None:
        self._recalculer()

    async def _tempo_periodique(self, _now: datetime) -> None:
        await self.tempo.async_rafraichir(dt_util.now().date())
        self._recalculer()

    @callback
    def arreter(self) -> None:
        if self.suivi:
            self.suivi.arreter()
        self.comparateur.arreter()
        for annuler in self._annuler:
            annuler()
        self._annuler.clear()
        if self._annuler_prochain:
            self._annuler_prochain()
            self._annuler_prochain = None

    # ------------------------------------------------------------------ calcul
    @property
    def puissance_kva(self) -> Optional[int]:
        """Puissance souscrite (kVA) de la grille en vigueur, ou None."""
        valeur = self.tarif.cfg.get("puissance_kva")
        try:
            return int(round(float(valeur))) if valeur not in (None, "") else None
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------ revente, prix passés
    @property
    def a_revente(self) -> bool:
        """Une grille au moins a un prix de revente : le capteur prix_revente existe."""
        return any(t.cfg.get("prix_revente") not in (None, "") for _d, t in self.tarifs.versions)

    @property
    def prix_revente(self) -> Optional[float]:
        return prix_revente_de(self.tarifs, dt_util.now().date())

    def contexte_passe(self) -> Contexte:
        """Couleurs Tempo et jours spéciaux tels qu'ils ont été (journal tenu par l'intégration)."""
        tempo = self.journal.get("tempo", {})
        speciaux = self.journal.get("speciaux", {})
        return Contexte(
            couleur_de=lambda j: tempo.get(j.isoformat()) or (self.tempo.couleur(j) if self.tempo else None),
            special_de=lambda j: speciaux.get(j.isoformat()),
        )

    async def _prix_dynamiques(self, debut: datetime, fin: datetime) -> dict[datetime, float]:
        """Moyennes horaires enregistrées du capteur « Prix actuel » (offres à prix dynamique)."""
        if OFFRE_DYN not in self.tarifs.types_offre or not self.entite_prix:
            return {}
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        res = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, debut, fin, {self.entite_prix}, "hour", None, {"mean"}
        )
        out: dict[datetime, float] = {}
        for ligne in res.get(self.entite_prix, []):
            if ligne.get("mean") is None:
                continue
            debut_l = ligne["start"]
            debut_l = (dt_util.utc_from_timestamp(debut_l) if isinstance(debut_l, (int, float)) else debut_l)
            out[dt_util.as_local(debut_l)] = float(ligne["mean"])
        return out

    async def async_prix_passes(self, debut: datetime, fin: datetime) -> dict[str, Any]:
        """Réponse du service `prix_passes` (contrat d'interface, version VERSION_INTERFACE)."""
        prix_dyn = await self._prix_dynamiques(debut, fin)
        heures = await self.hass.async_add_executor_job(
            heures_passees, self.tarifs, self.contexte_passe(), debut, fin, prix_dyn
        )
        grilles = self.journal.get("grilles") or {}
        return {
            "version_interface": VERSION_INTERFACE,
            "heures": heures,
            "derniere_modification": {"quand": grilles.get("quand"), "depuis": grilles.get("depuis")},
        }

    def reponse_previsions(self, heures: int, duree: Optional[float] = None) -> dict[str, Any]:
        """Réponse du service `previsions` (contrat d'interface, version VERSION_INTERFACE)."""
        segments = []
        for s in self.previsions(heures):
            seg = dict(s)
            seg["periode"] = s["periode"].lower()
            segments.append(seg)
        reponse: dict[str, Any] = {
            "version_interface": VERSION_INTERFACE,
            "fournisseur": self.tarif.fournisseur,
            "offre": self.tarif.offre,  # nom commercial
            "type_offre": self.tarif.type_offre,
            "puissance_kva": self.puissance_kva,
            "segments": segments,
        }
        connus = [s for s in segments if s["prix"] is not None]
        if connus:
            reponse["moins_cher"] = min(connus, key=lambda s: s["prix"])
            reponse["plus_cher"] = max(connus, key=lambda s: s["prix"])
        if duree:
            reponse["meilleur_creneau"] = meilleur_creneau(segments, duree)
        return reponse

    def previsions(self, heures: int) -> list[dict]:
        if OFFRE_DYN in self.tarifs.types_offre:
            self._lire_dynamique()
        return self.tarifs.segments(dt_util.now(), heures, self.contexte())

    def _bascule_jour_special(self, maintenant: datetime) -> None:
        jd = self.tarif.jour_special_de(maintenant)
        if self.js_jour is not None:
            # Journal : le jour en cours est-il spécial ?
            valeur = self.jour_special("aujourdhui")
            cle = self.js_jour.isoformat()
            ancien = self.journal["speciaux"].get(cle)
            if valeur != NORMAL and ancien != valeur:
                self.journal["speciaux"][cle] = valeur
                self._sauver_journal()
            elif valeur == NORMAL and ancien is not None:
                self.journal["speciaux"].pop(cle)
                self._sauver_journal()
        if self.js_jour == jd:
            return
        if self.js_jour is not None and jd == self.js_jour + timedelta(days=1):
            self.js_manuel = {"aujourdhui": self.js_manuel["demain"], "demain": NORMAL}
        elif self.js_jour is not None:
            self.js_manuel = {"aujourdhui": NORMAL, "demain": NORMAL}
        self.js_jour = jd

    @callback
    def _recalculer(self, _now: Optional[datetime] = None) -> None:
        maintenant = dt_util.now()
        t = self.tarifs.actif(maintenant.date())
        if self.noms_speciaux:
            self._bascule_jour_special(maintenant)
        if OFFRE_DYN in self.tarifs.types_offre:
            self._lire_dynamique()
        ctx = self.contexte()
        instant = self.tarifs.calcul(maintenant, ctx)
        quand, ensuite = self.tarifs.prochain_changement(maintenant, ctx)
        segments = self.tarifs.segments(maintenant, HORIZON_PREVISIONS_H, ctx)
        historique = self.tarifs.historique(maintenant.date())
        limite = maintenant + timedelta(hours=24)
        prix_24h = [
            s["prix"] for s in segments
            if s["prix"] is not None and datetime.fromisoformat(s["debut"]) < limite
        ]
        pmin = min(prix_24h) if prix_24h else None
        pmax = max(prix_24h) if prix_24h else None
        prix_bas = (
            instant.prix is not None and pmin is not None and pmax is not None and pmax > pmin
            and instant.prix <= pmin + (pmax - pmin) / 3
        )

        etat: dict[str, Any] = {
            "fournisseur": t.fournisseur,
            "offre": t.offre,
            "type_offre": t.type_offre,
            "abonnement_mensuel": t.abonnement,
            "puissance_kva": self.puissance_kva,
            "prix_revente": self.prix_revente,
            "prix": instant.prix,
            "periode": instant.periode,
            "periode_libelle": instant.libelle,
            "heures_creuses": instant.creuse,
            "heures_super_creuses": instant.periode == "HSC",
            "prix_bas": prix_bas,
            "saison": instant.saison,
            "couleur_tempo": instant.couleur,
            "jour_special": instant.jour_special,
            "prochain_changement": quand,
            "prochaine_periode": ensuite.periode if ensuite else None,
            "prochaine_periode_libelle": ensuite.libelle if ensuite else None,
            "prochain_prix": ensuite.prix if ensuite else None,
            "prix_min_24h": pmin,
            "prix_max_24h": pmax,
            "previsions": segments,
            "grille": t.grille(),
            "historique_prix": historique,
            "evolution_prevue": next((h for h in historique if h["statut"] == "prevue"), None),
        }
        if self.noms_speciaux:
            etat["jours_speciaux"] = {
                "options": [NORMAL, *self.noms_speciaux],
                "aujourdhui": self.jour_special("aujourdhui"),
                "demain": self.jour_special("demain"),
                "auto_aujourdhui": self.est_auto("aujourdhui"),
                "auto_demain": self.est_auto("demain"),
                "debut_h": t.debut_jour_special,
            }
        if t.type_offre == OFFRE_DYN:
            etat["source_prix"] = self.cfg.get("dyn_source")
            etat["previsions_disponibles"] = bool(self._serie_dyn)
        if self.suivi:
            etat["suivi"] = self.suivi.resultat
        etat.update(self.comparateur.etat())
        if self.tempo:
            for j, c in self.tempo.confirmees.items():
                if j <= maintenant.date() and self.journal["tempo"].get(j.isoformat()) != c:
                    self.journal["tempo"][j.isoformat()] = c
                    self._sauver_journal()
            aujourdhui = t.jour_tempo(maintenant)
            etat["tempo_aujourdhui"] = self.tempo.couleur(aujourdhui)
            etat["tempo_demain"] = self.tempo.couleur(aujourdhui + timedelta(days=1))
            etat["tempo_previsions"] = self.tempo.liste_previsions(maintenant.date())
            etat["tempo_disponible"] = self.tempo.disponible
        self.etat = etat
        async_dispatcher_send(self.hass, SIGNAL_MAJ.format(self.entry.entry_id))

        # Prochain recalcul : au changement de période, au plus tard dans 15 min
        if self._annuler_prochain:
            self._annuler_prochain()
        cible = maintenant + timedelta(minutes=15)
        if quand is not None:
            cible = min(cible, quand + timedelta(seconds=1))
        self._annuler_prochain = async_track_point_in_time(self.hass, self._recalculer, cible)


# ----------------------------------------------------------------------
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Carte Lovelace servie par l'intégration + service de prévisions."""
    hass.data.setdefault(DOMAIN, {})

    chemin = Path(__file__).parent / "www" / "tarifs-electricite-card.js"
    try:
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_CARTE, str(chemin), False)]
        )
        add_extra_js_url(hass, f"{URL_CARTE}?v={VERSION}")
    except Exception as err:  # noqa: BLE001 - la carte ne doit jamais bloquer l'intégration
        _LOGGER.warning("Carte Tarifs Électricité non enregistrée : %s", err)

    async def _service_previsions(call: ServiceCall) -> ServiceResponse:
        gestionnaires: dict[str, GestionnaireTarif] = hass.data.get(DOMAIN, {})
        if not gestionnaires:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="aucun_contrat"
            )
        entry_id = call.data.get("config_entry_id")
        if entry_id:
            if entry_id not in gestionnaires:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="contrat_inconnu",
                    translation_placeholders={"entry_id": entry_id},
                )
            g = gestionnaires[entry_id]
        else:
            g = next(iter(gestionnaires.values()))
        return g.reponse_previsions(call.data["heures"], call.data.get("duree"))

    hass.services.async_register(
        DOMAIN,
        SERVICE_PREVISIONS,
        _service_previsions,
        schema=SCHEMA_PREVISIONS,
        supports_response=SupportsResponse.ONLY,
    )

    async def _service_prix_passes(call: ServiceCall) -> ServiceResponse:
        g = _gestionnaire(hass, call.data.get("config_entry_id"))
        debut, fin = _local(call.data["debut"]), _local(call.data["fin"])
        if fin <= debut or fin - debut > timedelta(days=MAX_JOURS):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="periode_invalide",
                translation_placeholders={"jours": str(MAX_JOURS)},
            )
        return await g.async_prix_passes(debut, fin)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PRIX_PASSES,
        _service_prix_passes,
        schema=SCHEMA_PRIX_PASSES,
        supports_response=SupportsResponse.ONLY,
    )

    async def _service_comparer(call: ServiceCall) -> ServiceResponse:
        """v1.3.0 : ce que chaque offre saisie aurait coûté sur la période donnée."""
        g = _gestionnaire(hass, call.data.get("config_entry_id"))
        debut, fin = _local(call.data["debut"]), _local(call.data["fin"])
        if fin <= debut or fin - debut > timedelta(days=MAX_JOURS):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="periode_invalide",
                translation_placeholders={"jours": str(MAX_JOURS)},
            )
        if g.suivi is None:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="suivi_requis")
        rep = await g.comparateur.async_comparer(debut, fin, annuel=False)
        rep["version_interface"] = VERSION_INTERFACE
        return rep

    hass.services.async_register(
        DOMAIN,
        SERVICE_COMPARER,
        _service_comparer,
        schema=SCHEMA_COMPARER,
        supports_response=SupportsResponse.ONLY,
    )
    return True


def _local(valeur: datetime) -> datetime:
    """Date-heure du service, dans le fuseau de Home Assistant (heure locale si sans fuseau)."""
    if valeur.tzinfo is None:
        return valeur.replace(tzinfo=dt_util.get_default_time_zone())
    return dt_util.as_local(valeur)


def _gestionnaire(hass: HomeAssistant, entry_id: Optional[str]) -> "GestionnaireTarif":
    gestionnaires: dict[str, GestionnaireTarif] = hass.data.get(DOMAIN, {})
    if not gestionnaires:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="aucun_contrat")
    if entry_id:
        if entry_id not in gestionnaires:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="contrat_inconnu",
                translation_placeholders={"entry_id": entry_id},
            )
        return gestionnaires[entry_id]
    return next(iter(gestionnaires.values()))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    gestionnaire = GestionnaireTarif(hass, entry)
    await gestionnaire.async_demarrer()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = gestionnaire
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_recharger))
    return True


async def _async_recharger(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        gestionnaire: GestionnaireTarif = hass.data[DOMAIN].pop(entry.entry_id)
        gestionnaire.arreter()
    return ok
