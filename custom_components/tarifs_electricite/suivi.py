"""Suivi de consommation : coûts par période, mensualité estimée, solde.

Fonctions pures (sans Home Assistant) : elles reçoivent la consommation
heure par heure (lue dans les statistiques du compteur) et le prix de chaque
heure, et produisent les montants affichés.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable, Optional

JOURS_AN = 365.0

FIABILITE_INSUFFISANTE = "insuffisante"  # moins de 14 jours de données
FIABILITE_FAIBLE = "faible"  # moins de 3 mois : saisons non couvertes
FIABILITE_MOYENNE = "moyenne"  # 3 à 11 mois
FIABILITE_BONNE = "bonne"  # une année (presque) complète


@dataclass
class Heure:
    """Une heure de consommation."""

    debut: datetime
    kwh: float
    prix: Optional[float]  # €/kWh ; None si inconnu

    @property
    def cout(self) -> Optional[float]:
        return None if self.prix is None else self.kwh * self.prix


def prix_moyen_heure(calcul: Callable[[datetime], Optional[float]], debut: datetime) -> Optional[float]:
    """Prix moyen sur une heure (4 points : les changements à la demi-heure comptent)."""
    prix = [calcul(debut + timedelta(minutes=m)) for m in (7, 22, 37, 52)]
    connus = [p for p in prix if p is not None]
    return sum(connus) / len(connus) if connus else None


def completer_prix(heures: list[Heure]) -> list[Heure]:
    """Heures au prix inconnu : prix moyen pondéré des heures connues."""
    connues = [h for h in heures if h.prix is not None and h.kwh > 0]
    kwh = sum(h.kwh for h in connues)
    if not kwh:
        return heures
    moyen = sum(h.kwh * h.prix for h in connues) / kwh
    return [h if h.prix is not None else Heure(h.debut, h.kwh, moyen) for h in heures]


def debuts_de_periode(maintenant: datetime) -> dict[str, datetime]:
    jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        "aujourdhui": jour,
        "semaine": jour - timedelta(days=jour.weekday()),
        "mois": jour.replace(day=1),
        "annee": jour.replace(month=1, day=1),
    }


def resume(
    heures: list[Heure],
    debut: datetime,
    fin: datetime,
    abonnement_mensuel: Optional[float],
    partiel_kwh: float = 0.0,
    partiel_prix: Optional[float] = None,
) -> dict:
    """Consommation et coût entre `debut` et `fin` (abonnement au prorata)."""
    dans = [h for h in heures if debut <= h.debut < fin]
    kwh = sum(h.kwh for h in dans) + partiel_kwh
    cout_energie = sum(h.cout or 0.0 for h in dans)
    if partiel_kwh and partiel_prix is not None:
        cout_energie += partiel_kwh * partiel_prix
    jours = max(0.0, (fin - debut).total_seconds() / 86400)
    cout_abo = (abonnement_mensuel or 0.0) * 12 / JOURS_AN * jours
    return {
        "kwh": round(kwh, 3),
        "cout_energie": round(cout_energie, 2),
        "cout_abonnement": round(cout_abo, 2),
        "total": round(cout_energie + cout_abo, 2),
        "prix_moyen_kwh": round(cout_energie / kwh, 4) if kwh > 0 else None,
    }


def fiabilite(jours: float) -> str:
    if jours < 14:
        return FIABILITE_INSUFFISANTE
    if jours < 90:
        return FIABILITE_FAIBLE
    if jours < 330:
        return FIABILITE_MOYENNE
    return FIABILITE_BONNE


def estimation_annuelle(
    heures: list[Heure],
    abonnement_mensuel: Optional[float],
    prelevements_par_an: int = 12,
    mensualite_fournisseur: Optional[float] = None,
    repartition: Optional[Callable[[Heure], str]] = None,
) -> dict:
    """Coût sur un an, d'après la consommation passée (12 derniers mois au plus).

    S'il y a moins d'un an de données, la consommation est extrapolée : plus
    la période est courte, moins l'estimation tient compte des saisons
    (chauffage en hiver, climatisation en été…).
    """
    heures = [h for h in heures if h.kwh >= 0]
    if not heures:
        return {"fiabilite": FIABILITE_INSUFFISANTE, "jours_de_donnees": 0}
    premiere = min(h.debut for h in heures)
    derniere = max(h.debut for h in heures) + timedelta(hours=1)
    jours = (derniere - premiere).total_seconds() / 86400
    fiab = fiabilite(jours)
    res: dict = {"fiabilite": fiab, "jours_de_donnees": round(jours), "depuis": premiere.date().isoformat()}
    if fiab == FIABILITE_INSUFFISANTE:
        return res

    heures = completer_prix(heures)
    # Pas d'extrapolation pour une année (presque) complète
    facteur = JOURS_AN / jours if jours < 360 else 1.0
    kwh = sum(h.kwh for h in heures) * facteur
    energie = sum(h.cout or 0.0 for h in heures) * facteur
    abo = (abonnement_mensuel or 0.0) * 12
    annuel = energie + abo
    mensualite = annuel / prelevements_par_an
    res.update({
        "consommation_annuelle_kwh": round(kwh),
        "cout_energie_annuel": round(energie, 2),
        "cout_abonnement_annuel": round(abo, 2),
        "cout_annuel_estime": round(annuel, 2),
        "prix_moyen_kwh": round(energie / kwh, 4) if kwh else None,
        "prelevements_par_an": prelevements_par_an,
        "mensualite_estimee": round(mensualite, 2),
        "extrapole": facteur > 1.0,
    })
    if repartition:
        par_periode: dict[str, float] = {}
        for h in heures:
            cle = repartition(h)
            par_periode[cle] = par_periode.get(cle, 0.0) + h.kwh
        total = sum(par_periode.values()) or 1.0
        res["repartition_pct"] = {k: round(v / total * 100, 1) for k, v in sorted(par_periode.items())}
    if mensualite_fournisseur:
        ecart = mensualite - mensualite_fournisseur
        res.update({
            "mensualite_fournisseur": mensualite_fournisseur,
            "ecart_mensuel": round(ecart, 2),
            "ecart_pct": round(ecart / mensualite_fournisseur * 100, 1),
            "regularisation_annuelle_estimee": round(ecart * prelevements_par_an, 2),
            "conseil": conseil_mensualite(ecart, mensualite_fournisseur, fiab),
            # Code stable (la carte rédige le conseil dans la langue de l'utilisateur)
            "conseil_code": ("ok" if abs(ecart / mensualite_fournisseur * 100) <= 5
                             else "trop_basse" if ecart > 0 else "trop_haute"),
        })
    return res


def conseil_mensualite(ecart: float, fournisseur: float, fiab: str) -> str:
    pct = ecart / fournisseur * 100 if fournisseur else 0
    prudence = "" if fiab == FIABILITE_BONNE else " (estimation encore peu fiable : moins d'un an de données)"
    if abs(pct) <= 5:
        return "Votre mensualité correspond à votre consommation." + prudence
    if ecart > 0:
        return (f"Votre mensualité semble trop basse d'environ {ecart:.0f} €/mois : "
                f"attendez-vous à une facture de régularisation, ou demandez à l'augmenter.{prudence}")
    return (f"Votre mensualité semble trop élevée d'environ {-ecart:.0f} €/mois : "
            f"vous pouvez demander à votre fournisseur de la baisser.{prudence}")


def solde_periode(
    heures: list[Heure],
    debut: datetime,
    maintenant: datetime,
    abonnement_mensuel: Optional[float],
    mensualite_fournisseur: float,
    prelevements_par_an: int = 12,
    partiel_kwh: float = 0.0,
    partiel_prix: Optional[float] = None,
) -> dict:
    """Payé (mensualités au prorata) moins consommé depuis le début de la période de facturation.

    Positif : vous avez payé d'avance (remboursement probable). Négatif :
    régularisation à prévoir.
    """
    conso = resume(heures, debut, maintenant, abonnement_mensuel, partiel_kwh, partiel_prix)
    jours = (maintenant - debut).total_seconds() / 86400
    paye = mensualite_fournisseur * prelevements_par_an / JOURS_AN * jours
    donnees_depuis = min((h.debut for h in heures if h.debut >= debut), default=None)
    return {
        "depuis": debut.date().isoformat(),
        "paye_estime": round(paye, 2),
        "consomme": conso["total"],
        "kwh": conso["kwh"],
        "solde": round(paye - conso["total"], 2),
        "donnees_completes": donnees_depuis is not None and donnees_depuis - debut < timedelta(days=2),
    }


def kwh_depuis_unite(valeur: float, unite: Optional[str]) -> float:
    u = (unite or "kWh").strip()
    if u == "Wh":
        return valeur / 1000
    if u == "MWh":
        return valeur * 1000
    return valeur


# ---------------------------------------------------------------- relevés du compteur
def plafond_horaire(puissance_kva: Optional[float]) -> float:
    """kWh maximum plausibles en une heure : puissance souscrite + 25 % (36 kVA par défaut)."""
    return float(puissance_kva or 36) * 1.25


def nettoyer_releves(
    lignes: list[tuple[datetime, Optional[float], Optional[float]]], plafond: float
) -> tuple[list[tuple[datetime, float]], list[str]]:
    """Consommation horaire fiable à partir des statistiques (début, variation, index).

    Un compteur qui repasse un instant à 0 (redémarrage de la passerelle, perte
    de communication) fait croire à Home Assistant à une remise à zéro : toute
    la valeur de l'index est alors comptée comme consommée en une heure. Ces
    heures aberrantes sont corrigées avec l'écart d'index, ou ignorées.
    """
    propres, anomalies = [], []
    etat_prec: Optional[float] = None
    for debut, variation, etat in lignes:
        if variation is None:
            etat_prec = etat if etat is not None else etat_prec
            continue
        ecart_index = etat - etat_prec if etat is not None and etat_prec is not None else None
        if 0 <= variation <= plafond:
            kwh = variation
        elif ecart_index is not None and 0 <= ecart_index <= plafond:
            kwh = ecart_index
            anomalies.append(debut.isoformat())
        else:
            kwh = 0.0
            anomalies.append(debut.isoformat())
        propres.append((debut, kwh))
        if etat is not None:
            etat_prec = etat
    return propres, anomalies


# ---------------------------------------------------------------- facturation
PAIEMENT_MENSUALITES = "mensualites"  # prélèvements fixes + régularisation
PAIEMENT_REEL = "conso_reelle"  # facture de la consommation réelle à chaque échéance


def ajouter_mois(d: date, n: int) -> date:
    mois = d.month - 1 + n
    annee = d.year + mois // 12
    mois = mois % 12 + 1
    jours = [31, 29 if annee % 4 == 0 and (annee % 100 or annee % 400 == 0) else 28,
             31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mois - 1]
    return date(annee, mois, min(d.day, jours))


def periode_facturation(ancre: date, frequence_mois: int, aujourdhui: date) -> tuple[date, date]:
    """Période de facturation contenant `aujourdhui`, calée sur la date d'une facture."""
    n = 0
    if aujourdhui >= ancre:
        while ajouter_mois(ancre, (n + 1) * frequence_mois) <= aujourdhui:
            n += 1
    else:
        while ajouter_mois(ancre, n * frequence_mois) > aujourdhui:
            n -= 1
    return ajouter_mois(ancre, n * frequence_mois), ajouter_mois(ancre, (n + 1) * frequence_mois)


def facture_en_cours(
    heures: list[Heure],
    debut: datetime,
    fin: datetime,
    maintenant: datetime,
    abonnement_mensuel: Optional[float],
    partiel_kwh: float = 0.0,
    partiel_prix: Optional[float] = None,
    jours_reference: int = 14,
) -> dict:
    """Montant de la période en cours et projection jusqu'à la prochaine facture.

    La projection prolonge le coût moyen par jour des `jours_reference`
    derniers jours (la consommation récente reflète mieux la saison).
    """
    deja = resume(heures, debut, maintenant, abonnement_mensuel, partiel_kwh, partiel_prix)
    ref_debut = max(debut, maintenant - timedelta(days=jours_reference))
    recent = resume(heures, ref_debut, maintenant, None, partiel_kwh, partiel_prix)
    jours_ref = max((maintenant - ref_debut).total_seconds() / 86400, 1 / 24)
    par_jour = recent["cout_energie"] / jours_ref
    restant = max(0.0, (fin - maintenant).total_seconds() / 86400)
    total_jours = (fin - debut).total_seconds() / 86400
    abo_total = (abonnement_mensuel or 0.0) * 12 / JOURS_AN * total_jours
    projection = deja["cout_energie"] + par_jour * restant + abo_total
    return {
        "debut": debut.date().isoformat(),
        "prochaine_facture": fin.date().isoformat(),
        "jours_ecoules": round((maintenant - debut).total_seconds() / 86400, 1),
        "jours_restants": round(restant, 1),
        "kwh": deja["kwh"],
        "montant_actuel": deja["total"],
        "montant_estime": round(projection, 2),
        "abonnement_actuel": deja["cout_abonnement"],
        "abonnement_estime": round(abo_total, 2),
        "cout_moyen_par_jour": round(par_jour, 2),
    }
