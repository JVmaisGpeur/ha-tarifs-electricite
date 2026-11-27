"""T2 (v1.2.0) : prix d'une période passée, heure par heure.

Tels que le contrat les définit aujourd'hui, corrections comprises : les grilles
datées, le journal des couleurs Tempo et des jours spéciaux, et pour un prix
dynamique les moyennes horaires enregistrées du capteur « Prix actuel ».
Jamais de prix deviné : `prix` vaut None quand rien n'est connu.

Module pur (sans Home Assistant), utilisé par le service `prix_passes`.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Optional

from .tariff import OFFRE_DYN, Contexte, TarifVersionne

MINUTES = (7, 22, 37, 52)  # 4 points par heure, comme le suivi de consommation
MAX_JOURS = 366
# Réglages qui ne sont pas des prix : leur changement n'est pas une modification de grille
CLES_HORS_GRILLE = {
    "suivi", "compteur", "mode_paiement", "frequence_mois", "mensualite_fournisseur",
    "prelevements_par_an", "date_debut_facturation",
}


def _f(valeur: Any) -> Optional[float]:
    try:
        return None if valeur in (None, "") else float(valeur)
    except (TypeError, ValueError):
        return None


def prix_revente_de(tarifs: TarifVersionne, jour) -> Optional[float]:
    """Prix de revente du surplus de la grille en vigueur ce jour-là (None si aucun)."""
    return _f(tarifs.actif(jour).cfg.get("prix_revente"))


def heures_passees(
    tarifs: TarifVersionne,
    ctx: Contexte,
    debut: datetime,
    fin: datetime,
    prix_dyn: Optional[dict[datetime, float]] = None,
) -> list[dict[str, Any]]:
    """Une ligne par heure entre debut (arrondi à l'heure) et fin.

    prix_dyn : moyennes horaires enregistrées du prix (heure locale de début → €/kWh),
    utilisées pour les heures où la grille en vigueur est un prix dynamique.
    """
    tz = debut.tzinfo
    h = debut.replace(minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    fin_utc = fin.astimezone(timezone.utc)
    prix_dyn = prix_dyn or {}
    lignes: list[dict[str, Any]] = []
    while h < fin_utc:
        local = h.astimezone(tz)
        grille = tarifs.actif(local.date())
        instants = [tarifs.calcul(local + timedelta(minutes=m), ctx) for m in MINUTES]
        if grille.type_offre == OFFRE_DYN:
            prix = prix_dyn.get(local)
        else:
            connus = [i.prix for i in instants if i.prix is not None]
            prix = sum(connus) / len(connus) if connus else None
        periode = Counter(i.periode for i in instants).most_common(1)[0][0]
        lignes.append({
            "debut": local.isoformat(),
            "prix": None if prix is None else round(prix, 5),
            "prix_revente": prix_revente_de(tarifs, local.date()),
            "periode": periode.lower() if periode else None,
            "couleur": next((i.couleur for i in instants if i.couleur), None),
            "jour_special": next((i.jour_special for i in instants if i.jour_special), None),
        })
        h += timedelta(hours=1)
    return lignes


# ------------------------------------------------------------------ dernière modification
def signatures(versions: list[dict]) -> dict[str, str]:
    """Empreinte de chaque grille, par date d'effet (« origine » pour la première sans date)."""
    out = {}
    for v in versions:
        cfg = {k: val for k, val in (v.get("config") or {}).items() if k not in CLES_HORS_GRILLE}
        texte = json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
        out[v.get("date_effet") or "origine"] = hashlib.sha256(texte.encode()).hexdigest()[:16]
    return out


def derniere_modification(
    ancien: Optional[dict], nouvelles: dict[str, str], maintenant: datetime
) -> dict[str, Any]:
    """Nouvel état « grilles » du journal.

    Retourne {"versions", "quand", "depuis"} : `quand` = date de la dernière
    modification des grilles, `depuis` = date d'effet la plus ancienne qu'elle
    touche (None = dès l'origine du contrat). Premier passage : aucune modification.
    """
    if not isinstance(ancien, dict) or "versions" not in ancien:
        return {"versions": nouvelles, "quand": None, "depuis": None}
    avant = ancien.get("versions") or {}
    if avant == nouvelles:
        return {"versions": nouvelles, "quand": ancien.get("quand"), "depuis": ancien.get("depuis")}
    touchees = [k for k in set(avant) | set(nouvelles) if avant.get(k) != nouvelles.get(k)]
    depuis = None if "origine" in touchees else min(touchees)
    return {"versions": nouvelles, "quand": maintenant.isoformat(), "depuis": depuis}
