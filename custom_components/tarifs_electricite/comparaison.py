"""T3 à T5 (v1.3.0) : comparer des offres et conseiller une puissance souscrite.

Module pur (sans Home Assistant). Il reçoit la consommation réelle heure par heure
(celle du suivi) et les grilles saisies par l'utilisateur, et rend ce qu'il aurait
payé avec chaque offre, abonnement compris. Jamais de prix deviné : une heure sans
prix (prix dynamique sans historique) est comptée comme inconnue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .tariff import BLANC, BLEU, OFFRE_DYN, OFFRE_TEMPO, ROUGE, Contexte, Tarif

PUISSANCES = [3, 6, 9, 12, 15, 18, 24, 30, 36]  # kVA du marché français
MINUTES = (7, 22, 37, 52)  # 4 points par heure, comme le suivi
JOURS_AN = 365.0
PART_INCONNUE_MAX = 0.10  # au-delà, « données insuffisantes »
TOLERANCE_DEFAUT = 10  # heures de dépassement par an acceptées avec un écrêtage


def chances_tempo(jour: date) -> dict[str, float]:
    """Couleur Tempo probable d'un jour dont la couleur n'est pas connue (« estimé »).

    Règles du calendrier Tempo : dimanche toujours bleu ; jours rouges en semaine de
    novembre à mars (22 par an) ; jours blancs surtout l'hiver, jamais le dimanche.
    """
    if jour.weekday() == 6:
        return {BLEU: 1.0}
    hiver = jour.month in (11, 12, 1, 2, 3)
    if hiver and jour.weekday() < 5:
        return {ROUGE: 0.2, BLANC: 0.3, BLEU: 0.5}
    if hiver:
        return {BLANC: 0.3, BLEU: 0.7}
    return {BLANC: 0.05, BLEU: 0.95}


@dataclass
class Offre:
    nom: str
    tarif: Tarif
    abonnements: dict[int, float] = field(default_factory=dict)  # kVA → €/mois
    actuelle: bool = False
    puissance_actuelle: Optional[int] = None


def prix_heure(tarif: Tarif, debut: datetime, ctx: Contexte) -> tuple[Optional[float], bool]:
    """(prix moyen de l'heure, estimé ?) ; None si un quart d'heure n'a pas de prix."""
    prix, estime = [], False
    for m in MINUTES:
        t = debut + timedelta(minutes=m)
        inst = tarif.calcul(t, ctx)
        p = inst.prix
        if p is None and tarif.type_offre == OFFRE_TEMPO:
            periode = inst.periode
            chances = chances_tempo(tarif.jour_tempo(t))
            connus = [(c, tarif.prix_tempo.get((c, periode))) for c in chances]
            if all(v is not None for _c, v in connus):
                p = sum(chances[c] * v for c, v in connus)
                estime = True
        if p is None:
            return None, estime
        prix.append(p)
    if tarif.jours_speciaux:
        estime = True  # jours spéciaux de cette offre inconnus pour le passé
    return sum(prix) / len(prix), estime


def energie_offre(tarif: Tarif, heures: list[tuple[datetime, float]], ctx: Contexte) -> dict[str, float]:
    """Coût de l'énergie sur les heures données, et parts estimée et inconnue."""
    cout = kwh = kwh_estime = kwh_inconnu = 0.0
    for debut, e in heures:
        if e <= 0:
            continue
        p, est = prix_heure(tarif, debut, ctx)
        kwh += e
        if p is None:
            kwh_inconnu += e
            continue
        cout += e * p
        if est:
            kwh_estime += e
    connu = kwh - kwh_inconnu
    if kwh_inconnu and connu > 0:
        cout *= kwh / connu  # les heures sans prix au prix moyen des autres
    return {
        "energie": cout,
        "kwh": kwh,
        "part_estimee": kwh_estime / kwh if kwh else 0.0,
        "part_inconnue": kwh_inconnu / kwh if kwh else 0.0,
    }


def comparer(
    offres: list[Offre],
    heures: list[tuple[datetime, float]],
    ctx_de: Any,
    jours: float,
    annuel: bool = True,
) -> dict[str, Any]:
    """Comparatif : une ligne par offre et par puissance, de la moins chère à la plus chère.

    `ctx_de(offre)` rend le contexte (couleurs Tempo, prix dynamiques) de l'offre.
    `annuel` : total ramené à 12 mois (capteurs) ; sinon la période telle quelle (service).
    """
    extrapole = annuel and 0 < jours < 360
    facteur = JOURS_AN / jours if extrapole else 1.0
    duree_mois = 12.0 if annuel else jours * 12 / JOURS_AN
    lignes: list[dict[str, Any]] = []
    for o in offres:
        e = energie_offre(o.tarif, heures, ctx_de(o))
        insuffisant = e["kwh"] > 0 and e["part_inconnue"] > PART_INCONNUE_MAX
        abos = dict(o.abonnements)
        if o.actuelle and not abos:
            abos = {o.puissance_actuelle or 0: o.tarif.abonnement or 0.0}
        for kva, abo in sorted(abos.items()):
            energie = e["energie"] * facteur
            abonnement = (abo or 0.0) * duree_mois
            lignes.append({
                "offre": o.nom,
                "fournisseur": o.tarif.fournisseur,
                "type_offre": o.tarif.type_offre,
                "kva": kva or None,
                "energie": None if insuffisant else round(energie, 2),
                "abonnement": round(abonnement, 2),
                "total": None if insuffisant else round(energie + abonnement, 2),
                "kwh": round(e["kwh"] * facteur),
                "estime": e["part_estimee"] > 0.01,
                "part_estimee_pct": round(e["part_estimee"] * 100, 1),
                "donnees_insuffisantes": insuffisant,
                "actuel": o.actuelle and (kva == o.puissance_actuelle or len(abos) == 1),
            })
    ref = next((l for l in lignes if l["actuel"] and l["total"] is not None), None)
    for l in lignes:
        if ref and l["total"] is not None:
            l["ecart"] = round(l["total"] - ref["total"], 2)
            l["ecart_pct"] = round((l["total"] - ref["total"]) / ref["total"] * 100, 1) if ref["total"] else None
        else:
            l["ecart"] = l["ecart_pct"] = None
    classees = sorted(lignes, key=lambda l: (l["total"] is None, l["total"] or 0.0))
    meilleure = next((l for l in classees if l["total"] is not None), None)
    economie = None
    if meilleure and ref:
        economie = round(max(0.0, ref["total"] - meilleure["total"]), 2)
    return {
        "lignes": classees,
        "meilleure": meilleure,
        "economie_possible": economie,
        "jours_de_donnees": round(jours),
        "extrapole": extrapole,
        "estime": any(l["estime"] for l in classees),
    }


# ------------------------------------------------------------------ puissance souscrite
def depassements(
    maxima: dict[str, list[tuple[datetime, float]]],
    triphase: bool,
    actuelle: Optional[int] = None,
    tolerance: int = TOLERANCE_DEFAUT,
    puissances: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Heures où la puissance tirée du réseau a dépassé chaque puissance souscrite.

    `maxima` : {capteur: [(début d'heure, maximum en W)]}. En triphasé avec trois
    capteurs, chaque phase est comparée à la puissance ÷ 3 ; avec un seul capteur,
    le total est comparé à la puissance entière (et une phase peut dépasser seule).
    """
    puissances = sorted(set((puissances or PUISSANCES) + ([actuelle] if actuelle else [])))
    par_phase = triphase and len(maxima) >= 3
    heures: dict[datetime, dict[str, float]] = {}
    for capteur, serie in maxima.items():
        for debut, w in serie:
            if w is None:
                continue
            heures.setdefault(debut, {})[capteur] = float(w)
    resultat: dict[int, int] = {}
    for p in puissances:
        limite = p * 1000 / 3 if par_phase else p * 1000
        n = 0
        for valeurs in heures.values():
            if par_phase:
                if any(v > limite for v in valeurs.values()):
                    n += 1
            elif sum(valeurs.values()) > limite:
                n += 1
        resultat[p] = n
    pointe = None
    for debut, valeurs in heures.items():
        if par_phase:
            capteur, v = max(valeurs.items(), key=lambda kv: kv[1])
        else:
            capteur, v = None, sum(valeurs.values())
        if pointe is None or v > pointe["w"]:
            pointe = {"w": round(v), "date": debut.isoformat(), "phase": capteur}
    sans = [p for p in puissances if resultat[p] == 0]
    conseillee = min(sans) if sans else None
    possibles = [p for p in puissances if 0 < resultat[p] <= tolerance and (conseillee is None or p < conseillee)]
    return {
        "heures_depassement": {str(p): resultat[p] for p in puissances},
        "conseillee": conseillee,
        "possible_avec_ecretage": min(possibles) if possibles else None,
        "pointe": pointe,
        "par_phase": par_phase,
        "avertissement_phase": triphase and not par_phase,
        "tolerance": tolerance,
        "heures_mesurees": len(heures),
    }
