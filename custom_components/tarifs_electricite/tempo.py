"""Couleurs Tempo : officielles (aujourd'hui, demain) et prévisions.

Source : calendrier-tempo.fr, API publique gratuite et sans clé.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Optional

import aiohttp

from .const import TEMPO_API
from .tariff import BLANC, BLEU, ROUGE

_LOGGER = logging.getLogger(__name__)

_CODES = {1: BLEU, 2: BLANC, 3: ROUGE}
_NOMS = {
    "bleu": BLEU, "blue": BLEU, "tempo_bleu": BLEU,
    "blanc": BLANC, "white": BLANC, "tempo_blanc": BLANC,
    "rouge": ROUGE, "red": ROUGE, "tempo_rouge": ROUGE,
}


def normaliser_couleur(valeur: Any) -> Optional[str]:
    """Accepte « BLEU », « bleu », « blue », 1/2/3… et renvoie bleu/blanc/rouge."""
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)) and not isinstance(valeur, bool):
        return _CODES.get(int(valeur))
    texte = str(valeur).strip().lower()
    if texte.isdigit():
        return _CODES.get(int(texte))
    return _NOMS.get(texte)


def _date(valeur: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(valeur)[:10])
    except (TypeError, ValueError):
        return None


class TempoClient:
    """Garde en mémoire les couleurs connues (confirmées) et les prévisions."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self.confirmees: dict[date, str] = {}
        self.previsions: list[dict] = []
        self.disponible = False

    async def _get(self, chemin: str) -> Optional[dict]:
        try:
            async with self._session.get(
                f"{TEMPO_API}/{chemin}", timeout=aiohttp.ClientTimeout(total=20)
            ) as rep:
                if rep.status != 200:
                    _LOGGER.debug("Tempo %s : HTTP %s", chemin, rep.status)
                    return None
                return await rep.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Tempo %s : %s", chemin, err)
            return None

    def _lire_jour(self, donnees: Optional[dict], defaut: date) -> None:
        if not donnees or str(donnees.get("status", "ok")).lower() not in ("ok", "success"):
            return
        couleur = normaliser_couleur(
            donnees.get("couleur") or donnees.get("color") or donnees.get("code")
            or donnees.get("codeJour")
        )
        if couleur:
            jour = _date(donnees.get("date") or donnees.get("dateJour")) or defaut
            self.confirmees[jour] = couleur

    async def async_rafraichir(self, aujourdhui: date, historique: bool = False) -> None:
        ok = False
        if historique:
            hist = await self._get("history?days=3")
            for ligne in (hist or {}).get("history", []) or []:
                c = normaliser_couleur(ligne.get("couleur_reelle") or ligne.get("couleur"))
                j = _date(ligne.get("date"))
                if c and j:
                    self.confirmees[j] = c

        today = await self._get("today")
        self._lire_jour(today, aujourdhui)
        ok |= today is not None
        self._lire_jour(await self._get("tomorrow"), aujourdhui + timedelta(days=1))

        pred = await self._get("predictions")
        if pred and isinstance(pred.get("predictions"), list):
            ok = True
            self.previsions = []
            for p in pred["predictions"]:
                j = _date(p.get("date"))
                c = normaliser_couleur(p.get("couleur_predite") or p.get("couleur"))
                if not j:
                    continue
                confirme = bool(p.get("confirmed"))
                if confirme and c:
                    self.confirmees.setdefault(j, c)
                self.previsions.append(
                    {"date": j.isoformat(), "couleur": c, "confirmee": confirme}
                )

        # On ne garde que les jours utiles
        limite = aujourdhui - timedelta(days=3)
        self.confirmees = {j: c for j, c in self.confirmees.items() if j >= limite}
        self.disponible = ok

    async def async_historique(self, jours: int = 366) -> dict[str, str]:
        """Couleurs passées {date iso: couleur}, pour chiffrer la consommation passée."""
        hist = await self._get(f"history?days={jours}")
        resultat = {}
        for ligne in (hist or {}).get("history", []) or []:
            c = normaliser_couleur(ligne.get("couleur_reelle") or ligne.get("couleur"))
            j = _date(ligne.get("date"))
            if c and j:
                resultat[j.isoformat()] = c
        return resultat

    def couleur(self, jour: date) -> Optional[str]:
        return self.confirmees.get(jour)

    def liste_previsions(self, aujourdhui: date, jours: int = 15) -> list[dict]:
        """Prévisions à partir d'aujourd'hui, les couleurs officielles prenant le dessus."""
        par_date = {p["date"]: dict(p) for p in self.previsions}
        resultat = []
        for i in range(jours):
            j = aujourdhui + timedelta(days=i)
            cle = j.isoformat()
            if j in self.confirmees:
                resultat.append({"date": cle, "couleur": self.confirmees[j], "confirmee": True})
            elif cle in par_date:
                resultat.append(par_date[cle])
        return resultat
