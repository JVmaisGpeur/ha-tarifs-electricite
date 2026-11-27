"""Suivi de consommation côté Home Assistant.

La consommation vient des statistiques long terme du compteur choisi (celles
du tableau Énergie), heure par heure. Le prix de chaque heure passée vient
des statistiques du capteur « Prix actuel » de cette intégration ; avant son
installation, il est recalculé à partir des grilles saisies.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .const import SIGNAL_MAJ
from .suivi import (
    PAIEMENT_MENSUALITES,
    PAIEMENT_REEL,
    Heure,
    facture_en_cours,
    nettoyer_releves,
    periode_facturation,
    plafond_horaire,
    debuts_de_periode,
    estimation_annuelle,
    kwh_depuis_unite,
    prix_moyen_heure,
    resume,
    solde_periode,
)
from .tariff import OFFRE_DYN, Contexte

if TYPE_CHECKING:
    from . import GestionnaireTarif

_LOGGER = logging.getLogger(__name__)

SUIVI_CLES = ("compteur", "mode_paiement", "frequence_mois", "mensualite_fournisseur",
              "prelevements_par_an", "date_debut_facturation")


def lire_reglages_suivi(data: dict, options: dict) -> dict:
    if "suivi" in options:
        return dict(options["suivi"])
    return {k: data[k] for k in SUIVI_CLES if data.get(k) not in (None, "")}


def _debut_ligne(valeur) -> datetime:
    if isinstance(valeur, (int, float)):
        return dt_util.as_local(dt_util.utc_from_timestamp(valeur))
    return dt_util.as_local(valeur)


class SuiviConsommation:
    def __init__(self, g: "GestionnaireTarif", reglages: dict) -> None:
        self.g = g
        self.hass = g.hass
        self.compteur: str = reglages["compteur"]
        # Ancien réglage sans mode : mensualités si une mensualité était indiquée
        self.mode: str = reglages.get("mode_paiement") or (
            PAIEMENT_MENSUALITES if reglages.get("mensualite_fournisseur") else PAIEMENT_REEL
        )
        self.frequence: int = int(reglages.get("frequence_mois") or 2)
        if self.mode == PAIEMENT_MENSUALITES:
            self.mensualite: Optional[float] = reglages.get("mensualite_fournisseur") or None
            self.prelevements: int = int(reglages.get("prelevements_par_an") or 12)
        else:
            self.mensualite = None
            self.prelevements = max(1, 12 // self.frequence)  # nombre de factures par an
        self.anomalies: list[str] = []
        debut = reglages.get("date_debut_facturation")
        self.debut_facturation: Optional[date] = date.fromisoformat(debut) if debut else None
        self.heures_reelles: list[Heure] = []
        self.heures_estimation: list[Heure] = []
        self._fin_stats: Optional[datetime] = None
        self._etat_fin_stats: Optional[float] = None
        self._dernier_live = 0.0
        self._annuler: list = []
        self.resultat: dict[str, Any] = {"etat": "en_attente"}

    # ------------------------------------------------------------ cycle de vie
    async def async_demarrer(self) -> None:
        self._annuler.append(
            async_track_state_change_event(self.hass, [self.compteur], self._compteur_change)
        )
        # Les statistiques horaires sont compilées un peu après chaque heure
        self._annuler.append(
            async_track_time_change(self.hass, self._maj_horaire, minute=15, second=0)
        )
        # Premier calcul une fois l'enregistreur prêt
        self._annuler.append(async_call_later(self.hass, 30, self._maj_horaire))

    @callback
    def arreter(self) -> None:
        for a in self._annuler:
            a()
        self._annuler.clear()

    async def _maj_horaire(self, _now=None) -> None:
        try:
            await self.async_maj()
        except Exception as err:  # noqa: BLE001 - le suivi ne doit jamais bloquer les tarifs
            _LOGGER.warning("Suivi de consommation : %s", err)
            self.resultat = {"etat": "erreur", "message": str(err)}
            self._publier()

    # ------------------------------------------------------------ statistiques
    async def _stats(self, stat_id: str, debut: datetime, fin: datetime, types: set, unites=None):
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.statistics import statistics_during_period

        res = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period, self.hass, debut, fin, {stat_id}, "hour", unites, types
        )
        return res.get(stat_id, [])

    async def async_maj(self) -> None:
        maintenant = dt_util.now()
        # 12 derniers mois (estimation) ; ils couvrent aussi l'année civile en cours
        debut = maintenant - timedelta(days=366)
        if self.debut_facturation:
            debut_fact = datetime.combine(self.debut_facturation, datetime.min.time(), maintenant.tzinfo)
            debut = min(debut, max(debut_fact, maintenant - timedelta(days=730)))

        energie = await self._stats(self.compteur, debut, maintenant, {"change", "state"}, {"energy": "kWh"})
        if not energie:
            self.resultat = {
                "etat": "pas_de_donnees",
                "message": "Aucune statistique pour ce compteur (il doit avoir une classe d'état total/total_increasing et un historique d'au moins une heure).",
            }
            self._publier()
            return
        prix_stats = {}
        if self.g.entite_prix:
            for ligne in await self._stats(self.g.entite_prix, debut, maintenant, {"mean"}):
                if ligne.get("mean") is not None:
                    prix_stats[_debut_ligne(ligne["start"])] = ligne["mean"]

        lignes = [
            (_debut_ligne(l["start"]), l.get("change"), l.get("state"))
            for l in energie
        ]
        self.heures_reelles, self.heures_estimation = await self.hass.async_add_executor_job(
            self._calculer_heures, lignes, prix_stats, maintenant
        )
        derniere = lignes[-1]
        self._fin_stats = derniere[0] + timedelta(hours=1)
        self._etat_fin_stats = derniere[2]
        self._publier()

    def _contexte_passe(self) -> Contexte:
        return self.g.contexte_passe()

    def _calculer_heures(self, lignes, prix_stats, maintenant) -> tuple[list[Heure], list[Heure]]:
        ctx = self._contexte_passe()
        tarifs = self.g.tarifs
        derniere = tarifs.derniere
        dynamique = derniere.type_offre == OFFRE_DYN
        il_y_a_un_an = maintenant - timedelta(days=365)
        reelles, estimation = [], []
        propres, self.anomalies = nettoyer_releves(lignes, self._plafond())
        for debut, kwh in propres:
            prix = prix_stats.get(debut)
            if prix is None:
                prix = prix_moyen_heure(lambda dt: tarifs.calcul(dt, ctx).prix, debut)
            reelles.append(Heure(debut, kwh, prix))
            if debut >= il_y_a_un_an:
                # Estimation : la consommation passée, aux prix de la grille la plus récente
                p = prix if dynamique else prix_moyen_heure(lambda dt: derniere.calcul(dt, ctx).prix, debut)
                estimation.append(Heure(debut, kwh, p))
        return reelles, estimation

    def _plafond(self) -> float:
        kva = None
        for _d, t in self.g.tarifs.versions:
            kva = t.cfg.get("puissance_kva") or kva
        return plafond_horaire(kva)

    # ------------------------------------------------------------ temps réel
    def _partiel(self) -> float:
        """kWh consommés depuis la dernière heure présente dans les statistiques."""
        st = self.hass.states.get(self.compteur)
        if st is None or st.state in (STATE_UNKNOWN, STATE_UNAVAILABLE) or self._etat_fin_stats is None:
            return 0.0
        try:
            actuel = kwh_depuis_unite(float(st.state), st.attributes.get("unit_of_measurement"))
        except ValueError:
            return 0.0
        delta = actuel - self._etat_fin_stats
        if delta < 0:  # compteur remis à zéro
            delta = actuel
        # Saut aberrant (passerelle qui redémarre…) : ignoré jusqu'aux prochaines statistiques
        return delta if delta <= self._plafond() * 2 else 0.0

    @callback
    def _compteur_change(self, _event) -> None:
        horodatage = dt_util.utcnow().timestamp()
        if horodatage - self._dernier_live < 60:
            return
        self._dernier_live = horodatage
        if self._fin_stats is not None:
            self._publier()

    @callback
    def _publier(self) -> None:
        if self._fin_stats is not None:
            self.resultat = self._resultats()
        self.g.etat["suivi"] = self.resultat
        async_dispatcher_send(self.hass, SIGNAL_MAJ.format(self.g.entry.entry_id))

    def _resultats(self) -> dict:
        maintenant = dt_util.now()
        abo = self.g.tarif.abonnement
        partiel = self._partiel()
        prix = self.g.etat.get("prix")
        res: dict[str, Any] = {"etat": "ok", "compteur": self.compteur, "mode_paiement": self.mode,
                               "frequence_mois": self.frequence,
                               "donnees_jusqua": self._fin_stats.isoformat(),
                               "heures_corrigees": len(self.anomalies),
                               "dernieres_anomalies": self.anomalies[-5:]}
        for nom, debut in debuts_de_periode(maintenant).items():
            res[nom] = resume(self.heures_reelles, debut, maintenant, abo, partiel, prix)
        tarifs = self.g.tarifs

        def periode(h: Heure) -> str:
            return tarifs.derniere.calcul(h.debut + timedelta(minutes=30)).libelle.split(" · ")[0]

        res["estimation"] = estimation_annuelle(
            self.heures_estimation, tarifs.derniere.abonnement, self.prelevements,
            self.mensualite, repartition=periode,
        )
        if self.mode == PAIEMENT_REEL and "mensualite_estimee" in res["estimation"]:
            # Pas de mensualité : montant moyen d'une facture, selon la fréquence choisie
            est = res["estimation"]
            est["facture_moyenne_estimee"] = est.pop("mensualite_estimee")
            est["factures_par_an"] = est.pop("prelevements_par_an")
        tz = maintenant.tzinfo
        if self.mode == PAIEMENT_MENSUALITES:
            if self.debut_facturation and self.mensualite:
                debut = datetime.combine(self.debut_facturation, datetime.min.time(), tz)
                res["solde"] = solde_periode(
                    self.heures_reelles, debut, maintenant, abo, self.mensualite,
                    self.prelevements, partiel, prix,
                )
        elif self.debut_facturation:
            d, f = periode_facturation(self.debut_facturation, self.frequence, maintenant.date())
            res["facture"] = facture_en_cours(
                self.heures_reelles,
                datetime.combine(d, datetime.min.time(), tz),
                datetime.combine(f, datetime.min.time(), tz),
                maintenant, abo, partiel, prix,
            )
        return res
