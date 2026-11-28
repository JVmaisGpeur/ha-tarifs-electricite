"""Comparaison d'offres et puissance conseillée, côté Home Assistant (v1.3.0).

Les offres à comparer sont des sous-entrées de l'entrée du contrat (type « offre ») :
elles ne créent aucune entité de prix. La consommation vient du suivi (statistiques
horaires du compteur) ; la puissance, de la statistique horaire « max » du ou des
capteurs « Puissance au compteur ».
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_time_change
from homeassistant.util import dt as dt_util

from .comparaison import TOLERANCE_DEFAUT, Offre, comparer, depassements
from .const import SIGNAL_MAJ, SOUS_ENTREE_OFFRE
from .tariff import OFFRE_DYN, OFFRE_TEMPO, Contexte, Tarif, facteur_unite

if TYPE_CHECKING:
    from . import GestionnaireTarif

_LOGGER = logging.getLogger(__name__)


def _debut(valeur) -> datetime:
    if isinstance(valeur, (int, float)):
        return dt_util.as_local(dt_util.utc_from_timestamp(valeur))
    return dt_util.as_local(valeur)


def abonnements_de(data: dict) -> dict[int, float]:
    """Abonnements saisis pour chaque puissance : clés abo_3, abo_6… (€/mois)."""
    out = {}
    for cle, v in data.items():
        if cle.startswith("abo_") and v not in (None, ""):
            try:
                out[int(cle[4:])] = float(v)
            except ValueError:
                continue
    return out


class Comparateur:
    def __init__(self, g: "GestionnaireTarif") -> None:
        self.g = g
        self.hass = g.hass
        entry = g.entry
        self.offres_cfg: list[tuple[str, str, dict]] = [
            (sid, s.title, dict(s.data))
            for sid, s in (getattr(entry, "subentries", None) or {}).items()
            if s.subentry_type == SOUS_ENTREE_OFFRE
        ]
        reglages = g.suivi_reglages
        capteurs = reglages.get("puissance_compteur") or []
        self.capteurs_puissance: list[str] = [capteurs] if isinstance(capteurs, str) else list(capteurs)
        self.triphase = bool(reglages.get("triphase", False))
        self.tolerance = int(reglages.get("depassements_toleres", TOLERANCE_DEFAUT) or 0)
        self._annuler: list = []
        self._couleurs_offres: dict[str, str] = {}
        self._essais = 0
        # Derniers résultats, recopiés dans l'état du contrat à chaque recalcul
        self.comparatif: Optional[dict[str, Any]] = None
        self.puissance: Optional[dict[str, Any]] = None

    def etat(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.comparatif is not None:
            out["comparatif"] = self.comparatif
        if self.puissance is not None:
            out["puissance"] = self.puissance
        return out

    @property
    def a_offres(self) -> bool:
        return bool(self.offres_cfg)

    @property
    def a_puissance(self) -> bool:
        return bool(self.capteurs_puissance)

    async def async_demarrer(self) -> None:
        if not (self.a_offres or self.a_puissance):
            return
        self._annuler.append(async_track_time_change(self.hass, self._maj, hour=3, minute=40, second=0))
        # Premier calcul une fois le suivi chargé
        self._annuler.append(async_call_later(self.hass, 90, self._maj))

    def arreter(self) -> None:
        for a in self._annuler:
            a()
        self._annuler.clear()

    async def _maj(self, _now=None) -> None:
        try:
            await self.async_maj()
        except Exception as err:  # noqa: BLE001 - la comparaison ne doit jamais bloquer les tarifs
            _LOGGER.warning("Comparaison des offres : %s", err)

    # ------------------------------------------------------------ calcul
    def _offres(self) -> list[Offre]:
        g = self.g
        actuelle = Offre(
            f"{g.tarif.fournisseur} {g.tarif.offre}".strip(), g.tarif, {}, True, g.puissance_kva
        )
        autres = [Offre(titre, Tarif(cfg), abonnements_de(cfg)) for _sid, titre, cfg in self.offres_cfg]
        return [actuelle, *autres]

    async def _contextes(self, offres: list[Offre], debut: datetime, fin: datetime):
        """Contexte de chaque offre : couleurs Tempo passées, moyennes horaires d'un prix dynamique."""
        passe = self.g.contexte_passe()
        tempo = dict(self.g.journal.get("tempo", {}))
        if any(o.tarif.type_offre == OFFRE_TEMPO for o in offres) and not tempo:
            if not self._couleurs_offres:
                from .tempo import TempoClient

                self._couleurs_offres = await TempoClient(async_get_clientsession(self.hass)).async_historique()
            tempo = self._couleurs_offres
        couleur = (lambda j: tempo.get(j.isoformat())) if tempo else passe.couleur_de
        dyn: dict[int, dict[datetime, float]] = {}
        for o in offres:
            if o.tarif.type_offre == OFFRE_DYN and not o.actuelle:
                dyn[id(o)] = await self._moyennes(o.tarif.cfg.get("dyn_source"), debut, fin)
        actuel_dyn = await self.g._prix_dynamiques(debut, fin) if self.g.tarif.type_offre == OFFRE_DYN else {}

        def ctx_de(o: Offre) -> Contexte:
            serie = actuel_dyn if o.actuelle else dyn.get(id(o), {})
            # Le « Prix actuel » enregistré comprend déjà la majoration, que le calcul rajoute
            deja = o.tarif.majoration if o.actuelle else 0.0

            def prix_dyn(dt: datetime) -> Optional[float]:
                v = serie.get(dt.replace(minute=0, second=0, microsecond=0))
                return None if v is None else v - deja

            return Contexte(couleur_de=couleur, special_de=passe.special_de if o.actuelle else None,
                            prix_dyn_de=prix_dyn if serie else None)

        return ctx_de

    async def _moyennes(self, entite: Optional[str], debut: datetime, fin: datetime) -> dict[datetime, float]:
        if not entite:
            return {}
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        res = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, debut, fin, {entite}, "hour", None, {"mean"}
        )
        st = self.hass.states.get(entite)
        facteur = facteur_unite(st.attributes.get("unit_of_measurement")) if st else 1.0
        return {_debut(l["start"]): float(l["mean"]) * facteur for l in res.get(entite, []) if l.get("mean") is not None}

    def _heures(self, debut: datetime, fin: datetime) -> list[tuple[datetime, float]]:
        suivi = self.g.suivi
        if suivi is None:
            return []
        return [(h.debut, h.kwh) for h in suivi.heures_reelles if debut <= h.debut < fin]

    async def async_comparer(self, debut: datetime, fin: datetime, annuel: bool) -> dict[str, Any]:
        heures = self._heures(debut, fin)
        if not heures:
            return {"etat": "pas_de_donnees", "lignes": []}
        offres = self._offres()
        ctx_de = await self._contextes(offres, debut, fin)
        jours = (max(h for h, _ in heures) + timedelta(hours=1) - min(h for h, _ in heures)).total_seconds() / 86400
        res = await self.hass.async_add_executor_job(comparer, offres, heures, ctx_de, jours, annuel)
        res["etat"] = "ok"
        res["debut"], res["fin"] = debut.isoformat(), fin.isoformat()
        return res

    async def async_puissance(self, debut: datetime, fin: datetime) -> Optional[dict[str, Any]]:
        if not self.capteurs_puissance:
            return None
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        res = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, debut, fin, set(self.capteurs_puissance), "hour",
            {"power": "W"}, {"max"},
        )
        maxima = {c: [(_debut(l["start"]), l["max"]) for l in res.get(c, []) if l.get("max") is not None]
                  for c in self.capteurs_puissance}
        return depassements(maxima, self.triphase, self.g.puissance_kva, self.tolerance)

    async def async_maj(self) -> None:
        fin = dt_util.now().replace(minute=0, second=0, microsecond=0)
        debut = fin - timedelta(days=365)
        if self.a_offres:
            self.comparatif = await self.async_comparer(debut, fin, annuel=True)
            # Suivi pas encore chargé (démarrage) : nouvel essai dans 5 minutes
            if self.comparatif.get("etat") == "pas_de_donnees" and self._essais < 6:
                self._essais += 1
                self._annuler.append(async_call_later(self.hass, 300, self._maj))
        if self.a_puissance:
            self.puissance = await self.async_puissance(debut, fin)
        self.g.etat.update(self.etat())
        async_dispatcher_send(self.hass, SIGNAL_MAJ.format(self.g.entry.entry_id))
