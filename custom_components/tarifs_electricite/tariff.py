"""Moteur de calcul des tarifs d'électricité.

Ce module ne dépend pas de Home Assistant : il peut être testé seul.
Il répond à une seule question : « à tel instant, quelle période tarifaire,
quel type de jour, et quel prix ? »
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Optional

# ---------------------------------------------------------------- périodes
BASE = "BASE"
HP = "HP"
HC = "HC"
HSC = "HSC"  # heures super creuses
PERSO = "PERSO"  # période nommée par l'utilisateur (ex. « Heures solaires »)
WE = "WE"  # prix week-end
WE_HC = "WE_HC"  # prix week-end en heures creuses
DYN = "DYN"  # prix dynamique (marché)
PERIODES = [HP, HC, HSC, PERSO, WE, WE_HC, BASE, DYN]
# Périodes toujours creuses ; la période nommée (PERSO) l'est si le contrat le dit
PERIODES_CREUSES = {HC, HSC, WE_HC}

LIBELLES = {
    HP: "Heures pleines",
    HC: "Heures creuses",
    HSC: "Heures super creuses",
    PERSO: "Période spéciale",
    WE: "Week-end",
    WE_HC: "Week-end heures creuses",
    BASE: "Base",
    DYN: "Prix dynamique",
}

# ---------------------------------------------------------------- offres
OFFRE_BASE = "base"
OFFRE_HPHC = "hphc"
OFFRE_TEMPO = "tempo"
OFFRE_DYN = "dynamique"
OFFRES = [OFFRE_BASE, OFFRE_HPHC, OFFRE_TEMPO, OFFRE_DYN]

# Couleurs Tempo
BLEU = "bleu"
BLANC = "blanc"
ROUGE = "rouge"
COULEURS = (BLEU, BLANC, ROUGE)

# Week-ends / jours fériés
JOUR_IDENTIQUE = "identique"  # mêmes règles qu'en semaine
JOUR_HC = "heures_creuses"  # heures creuses toute la journée
JOUR_PRIX_WE = "prix_weekend"  # prix week-end (ex. -30 %)
JOUR_COMME_WE = "comme_weekend"  # (fériés) mêmes règles que le week-end

SAISON_HIVER = "hiver"
SAISON_ETE = "ete"
SAISON_UNIQUE = "annee"
NOMS_SAISON = {SAISON_HIVER: "Hiver", SAISON_ETE: "Été", SAISON_UNIQUE: "Toute l'année"}

MOIS_HIVER_DEFAUT = ["11", "12", "1", "2", "3"]
NORMAL = "normal"  # jour sans particularité

_RANGE_RE = re.compile(
    r"^\s*(\d{1,2})\s*[:hH]?\s*(\d{2})?\s*[-–à]\s*(\d{1,2})\s*[:hH]?\s*(\d{2})?\s*$"
)


class PlageInvalide(ValueError):
    """Plage horaire impossible à lire."""


def parse_plages(texte: Optional[str]) -> list[tuple[int, int]]:
    """Lit « 23:00-06:00, 12h-14h » et renvoie des plages en minutes."""
    if not texte or not str(texte).strip():
        return []
    plages: list[tuple[int, int]] = []
    for morceau in re.split(r"[,;/]|\bet\b", str(texte)):
        if not morceau.strip():
            continue
        m = _RANGE_RE.match(morceau)
        if not m:
            raise PlageInvalide(morceau.strip())
        h1, m1, h2, m2 = (int(m.group(i) or 0) for i in range(1, 5))
        if h1 > 24 or h2 > 24 or m1 > 59 or m2 > 59:
            raise PlageInvalide(morceau.strip())
        debut = (h1 * 60 + m1) % 1440
        fin = h2 * 60 + m2
        if fin == 0 or fin > 1440:
            fin = 1440
        if debut == fin:
            raise PlageInvalide(morceau.strip())
        if fin > debut:
            plages.append((debut, fin))
        else:  # passe minuit
            plages.append((debut, 1440))
            if fin > 0:
                plages.append((0, fin))
    return plages


def _dans(plages: list[tuple[int, int]], minute: int) -> bool:
    return any(d <= minute < f for d, f in plages)


def simplifier(texte) -> str:
    """Minuscules sans accents ni espaces superflus (pour comparer des états)."""
    t = unicodedata.normalize("NFKD", str(texte)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", t).strip().lower()


def paques(annee: int) -> date:
    """Date de Pâques (algorithme de Meeus/Jones/Butcher)."""
    a = annee % 19
    b, c = divmod(annee, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mois = (h + l - 7 * m + 114) // 31
    jour = ((h + l - 7 * m + 114) % 31) + 1
    return date(annee, mois, jour)


def jours_feries(annee: int, alsace_moselle: bool = False) -> set[date]:
    """Jours fériés en France métropolitaine."""
    p = paques(annee)
    feries = {
        date(annee, 1, 1),
        p + timedelta(days=1),
        date(annee, 5, 1),
        date(annee, 5, 8),
        p + timedelta(days=39),
        p + timedelta(days=50),
        date(annee, 7, 14),
        date(annee, 8, 15),
        date(annee, 11, 1),
        date(annee, 11, 11),
        date(annee, 12, 25),
    }
    if alsace_moselle:
        feries.add(p - timedelta(days=2))
        feries.add(date(annee, 12, 26))
    return feries


def _float(v) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


@dataclass
class ReglesSaison:
    plages_hc: list[tuple[int, int]] = field(default_factory=list)
    plages_hsc: list[tuple[int, int]] = field(default_factory=list)
    plages_perso: list[tuple[int, int]] = field(default_factory=list)
    prix: dict[str, Optional[float]] = field(default_factory=dict)


@dataclass
class JourSpecial:
    nom: str
    prix: dict[str, Optional[float]]  # BASE, ou HP/HC


@dataclass
class Contexte:
    """Informations venues de l'extérieur du contrat."""

    couleur_de: Optional[Callable[[date], Optional[str]]] = None  # Tempo
    special_de: Optional[Callable[[date], Optional[str]]] = None  # jour spécial
    # Le type du jour est-il connu (annoncé, ou saisi) ? Faux pour un jour à venir
    # dont le fournisseur n'a encore rien annoncé.
    special_confirme_de: Optional[Callable[[date], bool]] = None
    prix_dyn_de: Optional[Callable[[datetime], Optional[float]]] = None  # marché


@dataclass
class Instant:
    periode: str
    prix: Optional[float]
    libelle: str = ""
    saison: Optional[str] = None
    couleur: Optional[str] = None
    jour_special: Optional[str] = None
    creuse: bool = False  # heures creuses (HC, HSC, week-end HC, période nommée creuse)
    confirme: bool = True  # type de jour connu (offres à jours spéciaux)

    def cle(self) -> tuple:
        return (self.periode, self.prix, self.saison, self.couleur, self.jour_special,
                self.creuse, self.confirme)


class Tarif:
    """Contrat d'électricité décrit par l'utilisateur."""

    def __init__(self, cfg: dict) -> None:
        self.cfg = dict(cfg)
        g = cfg.get
        self.type_offre: str = g("type_offre", OFFRE_HPHC)
        self.fournisseur: str = g("fournisseur", "")
        self.offre: str = g("offre", "")
        self.abonnement = _float(g("abonnement_mensuel"))
        self.est_hphc = self.type_offre == OFFRE_HPHC
        calendrier = self.type_offre in (OFFRE_BASE, OFFRE_HPHC)

        self.weekend: str = g("weekend", JOUR_IDENTIQUE) if calendrier else JOUR_IDENTIQUE
        if self.weekend == JOUR_HC and not self.est_hphc:
            self.weekend = JOUR_IDENTIQUE
        self.feries: str = g("feries", JOUR_IDENTIQUE) if calendrier else JOUR_IDENTIQUE
        self.jours_extra: set[int] = {int(j) for j in (g("jours_extra") or [])}
        self.alsace_moselle = bool(g("alsace_moselle", False))
        self.saisons = bool(g("saisons", False)) and calendrier
        self.mois_hiver = {int(m) for m in (g("mois_hiver") or MOIS_HIVER_DEFAUT)}
        self.prix_weekend = _float(g("prix_weekend"))
        self.prix_weekend_hc = _float(g("prix_weekend_hc")) if self.est_hphc else None
        self.nom_perso: str = (g("perso_nom") or LIBELLES[PERSO]).strip()
        self.perso_creuse: bool = bool(g("perso_creuse", True))
        self._feries_cache: dict[int, set[date]] = {}

        # Jours spéciaux (Sobriété, Jour Éclair, Jour Sérénité…)
        self.jours_speciaux: dict[str, JourSpecial] = {}
        self.debut_jour_special = int(_float(g("js_debut_h")) or 0)
        if calendrier and g("jours_speciaux"):
            for n in (1, 2):
                nom = (g(f"js{n}_nom") or "").strip()
                if not nom:
                    continue
                if self.est_hphc:
                    prix = {HP: _float(g(f"js{n}_prix_hp")), HC: _float(g(f"js{n}_prix_hc"))}
                else:
                    prix = {BASE: _float(g(f"js{n}_prix"))}
                self.jours_speciaux[nom] = JourSpecial(nom, prix)

        # Dynamique
        self.majoration = _float(g("dyn_majoration")) or 0.0

        # Tempo
        if self.type_offre == OFFRE_TEMPO:
            self.plages_hc_tempo = parse_plages(g("plages_hc") or "22:00-06:00")
            self.prix_tempo = {
                (c, p): _float(g(f"prix_{c}_{p.lower()}")) for c in COULEURS for p in (HP, HC)
            }

        # Règles par saison
        self.regles: dict[str, ReglesSaison] = {}
        if self.type_offre == OFFRE_BASE:
            self.regles[SAISON_HIVER if self.saisons else SAISON_UNIQUE] = ReglesSaison(
                prix={BASE: _float(g("prix_base"))}
            )
            if self.saisons:
                self.regles[SAISON_ETE] = ReglesSaison(prix={BASE: _float(g("prix_base_ete"))})
        elif self.est_hphc:
            self.regles[SAISON_HIVER if self.saisons else SAISON_UNIQUE] = self._regles_hphc("")
            if self.saisons:
                self.regles[SAISON_ETE] = self._regles_hphc("_ete")

    def _regles_hphc(self, suffixe: str) -> ReglesSaison:
        g = self.cfg.get
        return ReglesSaison(
            plages_hc=parse_plages(g(f"plages_hc{suffixe}")),
            plages_hsc=parse_plages(g(f"plages_hsc{suffixe}")),
            plages_perso=parse_plages(g(f"plages_perso{suffixe}")),
            prix={
                HP: _float(g(f"prix_hp{suffixe}")),
                HC: _float(g(f"prix_hc{suffixe}")),
                HSC: _float(g(f"prix_hsc{suffixe}")),
                PERSO: _float(g(f"prix_perso{suffixe}")),
            },
        )

    # ------------------------------------------------------------------ infos
    @property
    def a_hsc(self) -> bool:
        return any(r.plages_hsc for r in self.regles.values())

    @property
    def a_perso(self) -> bool:
        return any(r.plages_perso for r in self.regles.values())

    @property
    def a_heures_creuses(self) -> bool:
        return self.type_offre in (OFFRE_HPHC, OFFRE_TEMPO)

    def est_creuse(self, periode: str) -> bool:
        return periode in PERIODES_CREUSES or (periode == PERSO and self.perso_creuse)

    def libelle(self, periode: str) -> str:
        return self.nom_perso if periode == PERSO else LIBELLES.get(periode, periode)

    def est_ferie(self, jour: date) -> bool:
        if jour.year not in self._feries_cache:
            self._feries_cache[jour.year] = jours_feries(jour.year, self.alsace_moselle)
        return jour in self._feries_cache[jour.year]

    def est_jour_weekend(self, jour: date) -> bool:
        """Samedi, dimanche, jours choisis en plus, et fériés « comme le week-end »."""
        if jour.weekday() >= 5 or jour.weekday() in self.jours_extra:
            return True
        return self.feries == JOUR_COMME_WE and self.est_ferie(jour)

    def saison(self, jour: date) -> str:
        if not self.saisons:
            return SAISON_UNIQUE
        return SAISON_HIVER if jour.month in self.mois_hiver else SAISON_ETE

    @staticmethod
    def jour_tempo(dt: datetime) -> date:
        """Le jour Tempo va de 6 h à 6 h le lendemain."""
        return (dt - timedelta(hours=6)).date()

    def jour_special_de(self, dt: datetime) -> date:
        """Jour « spécial » auquel appartient l'instant (ex. 8 h → 8 h pour Zen Flex)."""
        return (dt - timedelta(hours=self.debut_jour_special)).date()

    # ------------------------------------------------------------------ calcul
    def calcul(self, dt: datetime, ctx: Optional[Contexte] = None) -> Instant:
        ctx = ctx or Contexte()
        instant = self._calcul(dt, ctx)
        instant.creuse = self.est_creuse(instant.periode)
        if self.jours_speciaux and ctx.special_confirme_de:
            instant.confirme = bool(ctx.special_confirme_de(self.jour_special_de(dt)))
        return instant

    def _calcul(self, dt: datetime, ctx: Contexte) -> Instant:
        minute = dt.hour * 60 + dt.minute
        jour = dt.date()

        if self.type_offre == OFFRE_DYN:
            prix = ctx.prix_dyn_de(dt) if ctx.prix_dyn_de else None
            if prix is not None:
                prix = round(prix + self.majoration, 5)
            return Instant(DYN, prix, LIBELLES[DYN])

        if self.type_offre == OFFRE_TEMPO:
            couleur = ctx.couleur_de(self.jour_tempo(dt)) if ctx.couleur_de else None
            periode = HC if _dans(self.plages_hc_tempo, minute) else HP
            prix = self.prix_tempo.get((couleur, periode)) if couleur else None
            return Instant(periode, prix, LIBELLES[periode], couleur=couleur)

        saison = self.saison(jour)
        r = self.regles[saison]
        saison_aff = saison if self.saisons else None

        # Période selon l'heure
        if not self.est_hphc:
            periode = BASE
        elif _dans(r.plages_hsc, minute):
            periode = HSC
        elif _dans(r.plages_perso, minute):
            periode = PERSO
        elif _dans(r.plages_hc, minute):
            periode = HC
        else:
            periode = HP

        # Jour spécial (prioritaire)
        if self.jours_speciaux and ctx.special_de:
            nom = ctx.special_de(self.jour_special_de(dt))
            js = self.jours_speciaux.get(nom) if nom else None
            if js:
                if not self.est_hphc:
                    p, prix = BASE, js.prix.get(BASE)
                elif periode == HP:
                    p, prix = HP, js.prix.get(HP)
                else:
                    p, prix = HC, js.prix.get(HC)
                return Instant(p, prix, f"{self.libelle(p)} · {js.nom}", saison_aff, jour_special=js.nom)

        we = self.est_jour_weekend(jour)
        ferie = self.est_ferie(jour)
        if (we and self.weekend == JOUR_HC) or (ferie and self.feries == JOUR_HC):
            if periode not in (HSC, PERSO):
                periode = HC
        elif we and self.weekend == JOUR_PRIX_WE:
            if self.est_hphc and self.prix_weekend_hc is not None and periode != HP:
                return Instant(WE_HC, self.prix_weekend_hc, LIBELLES[WE_HC], saison_aff)
            return Instant(WE, self.prix_weekend, LIBELLES[WE], saison_aff)

        return Instant(periode, r.prix.get(periode), self.libelle(periode), saison_aff)

    def segments(
        self, debut: datetime, heures: int = 48, ctx: Optional[Contexte] = None
    ) -> list[dict]:
        """Découpe les `heures` à venir en tranches de même période/prix."""
        debut = debut.replace(second=0, microsecond=0)
        fin = debut + timedelta(hours=heures)
        resultats: list[dict] = []
        courant = self.calcul(debut, ctx)
        t0 = t = debut
        while t < fin:
            t = t + timedelta(minutes=1)
            suivant = self.calcul(t, ctx) if t < fin else None
            if suivant is None or suivant.cle() != courant.cle():
                resultats.append(
                    {
                        "debut": t0.isoformat(),
                        "fin": t.isoformat(),
                        "periode": courant.periode,
                        "libelle": courant.libelle,
                        "prix": courant.prix,
                        "couleur": courant.couleur,
                        "saison": courant.saison,
                        "jour_special": courant.jour_special,
                        "jour_special_confirme": courant.confirme,
                        "heures_creuses": courant.creuse,
                    }
                )
                if suivant is None:
                    break
                courant, t0 = suivant, t
        return resultats

    def prochain_changement(
        self, dt: datetime, ctx: Optional[Contexte] = None, horizon_h: int = 72
    ) -> tuple[Optional[datetime], Optional[Instant]]:
        dt = dt.replace(second=0, microsecond=0)
        actuel = self.calcul(dt, ctx)
        t = dt
        limite = dt + timedelta(hours=horizon_h)
        while t < limite:
            t += timedelta(minutes=1)
            suivant = self.calcul(t, ctx)
            if suivant.cle() != actuel.cle():
                return t, suivant
        return None, None

    # ------------------------------------------------------------------ affichage
    def grille(self) -> dict:
        """Grille des prix : colonnes + lignes, pour la carte."""
        lignes: list[dict] = []
        if self.type_offre == OFFRE_TEMPO:
            for c in COULEURS:
                lignes.append({"libelle": c, "code": c, "prix": {HP: self.prix_tempo[(c, HP)],
                                                                 HC: self.prix_tempo[(c, HC)]}})
        elif self.type_offre in (OFFRE_BASE, OFFRE_HPHC):
            for saison, r in self.regles.items():
                lignes.append({"libelle": NOMS_SAISON[saison], "code": saison,
                               "prix": {k: v for k, v in r.prix.items() if v is not None}})
            if self.weekend == JOUR_PRIX_WE and self.prix_weekend is not None:
                if self.est_hphc:
                    hc = self.prix_weekend_hc if self.prix_weekend_hc is not None else self.prix_weekend
                    lignes.append({"libelle": "Week-end", "code": "weekend",
                                   "prix": {HP: self.prix_weekend, HC: hc}})
                else:
                    lignes.append({"libelle": "Week-end", "code": "weekend",
                                   "prix": {BASE: self.prix_weekend}})
            for js in self.jours_speciaux.values():
                lignes.append({"libelle": js.nom, "code": "special",
                               "prix": {k: v for k, v in js.prix.items() if v is not None},
                               "special": True})
        cles = [p for p in (HP, HC, HSC, PERSO, BASE) if any(p in l["prix"] for l in lignes)]
        colonnes = [{"cle": p, "nom": self.nom_perso if p == PERSO else p} for p in cles]
        return {"colonnes": colonnes, "lignes": lignes}


def meilleur_creneau(segments: list[dict], duree_h: float, pas_min: int = 15) -> Optional[dict]:
    """Créneau continu de `duree_h` heures le moins cher (prix inconnus exclus)."""
    if not segments or duree_h <= 0:
        return None
    tranches = [
        (datetime.fromisoformat(s["debut"]), datetime.fromisoformat(s["fin"]), s["prix"])
        for s in segments
    ]
    debut_total, fin_total = tranches[0][0], tranches[-1][1]
    duree = timedelta(hours=duree_h)
    meilleur = None
    t = debut_total
    while t + duree <= fin_total:
        fin = t + duree
        cout, complet = 0.0, True
        for d, f, prix in tranches:
            recouvre = (min(f, fin) - max(d, t)).total_seconds()
            if recouvre <= 0:
                continue
            if prix is None:
                complet = False
                break
            cout += prix * recouvre
        if complet:
            moyenne = cout / duree.total_seconds()
            if meilleur is None or moyenne < meilleur["prix_moyen"] - 1e-9:
                meilleur = {"debut": t.isoformat(), "fin": fin.isoformat(),
                            "prix_moyen": round(moyenne, 5)}
        t += timedelta(minutes=pas_min)
    return meilleur


# ---------------------------------------------------------------- prix dynamiques
_CLES_DEBUT = ("start_time", "start", "startsAt", "starts_at", "from", "begin", "datetime",
               "date_time", "time", "hour", "date")
_CLES_FIN = ("end_time", "end", "endsAt", "ends_at", "till", "to", "until")
_CLES_PRIX = ("price_per_kwh", "price_eur_per_kwh", "price_ct_per_kwh", "price_eur_per_mwh",
              "price", "value", "total", "prix", "price_kwh")


def facteur_unite(unite: Optional[str]) -> float:
    """Convertit vers €/kWh : €/MWh → /1000, ct/kWh → /100."""
    u = simplifier(unite or "")
    if "mwh" in u:
        return 0.001
    if u.startswith(("c", "ct")) and "kwh" in u:
        return 0.01
    return 1.0


def _facteur_cle(cle: str, defaut: float) -> float:
    c = cle.lower()
    if "mwh" in c:
        return 0.001
    if "ct" in c or "cent" in c:
        return 0.01
    if "kwh" in c:
        return 1.0
    return defaut


def _dt(v) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def lire_serie_prix(attributs: dict, facteur_etat: float = 1.0) -> list[tuple[datetime, datetime, float]]:
    """Trouve une liste de prix horaires dans les attributs d'une entité.

    Compatible avec les formats les plus courants (EPEX Spot, Nord Pool,
    intégrations de fournisseurs) : liste de dicts avec un début, une fin
    facultative et un prix.
    """
    meilleure: list[tuple[datetime, datetime, float]] = []
    for valeur in attributs.values():
        if not isinstance(valeur, list) or not valeur or not isinstance(valeur[0], dict):
            continue
        cle_d = next((k for k in _CLES_DEBUT if k in valeur[0]), None)
        cle_p = next((k for k in _CLES_PRIX if k in valeur[0]), None)
        if not cle_d or not cle_p:
            continue
        cle_f = next((k for k in _CLES_FIN if k in valeur[0]), None)
        f = _facteur_cle(cle_p, facteur_etat)
        points = []
        for item in valeur:
            d = _dt(item.get(cle_d))
            p = _float(item.get(cle_p))
            if d is None or p is None:
                continue
            fin = _dt(item.get(cle_f)) if cle_f else None
            points.append([d, fin, p * f])
        points.sort(key=lambda x: x[0])
        for i, pt in enumerate(points):
            if pt[1] is None:
                pt[1] = points[i + 1][0] if i + 1 < len(points) else pt[0] + timedelta(hours=1)
        serie = [(d, fin, p) for d, fin, p in points if fin > d]
        if len(serie) > len(meilleure):
            meilleure = serie
    return meilleure


# ---------------------------------------------------------------- versions datées
def comparer_grilles(avant: dict, apres: dict) -> list[dict]:
    """Prix qui ont changé entre deux grilles (même libellé, même colonne)."""
    anciennes = {l["libelle"]: l["prix"] for l in avant.get("lignes", [])}
    changements = []
    for ligne in apres.get("lignes", []):
        ancien = anciennes.get(ligne["libelle"])
        if not ancien:
            continue
        for cle, nouveau in ligne["prix"].items():
            vieux = ancien.get(cle)
            if vieux is None or nouveau is None or abs(vieux - nouveau) < 1e-9:
                continue
            changements.append({
                "libelle": ligne["libelle"], "code": ligne.get("code"), "cle": cle,
                "avant": vieux, "apres": nouveau,
                "variation_pct": round((nouveau - vieux) / vieux * 100, 1) if vieux else None,
            })
    return changements


class TarifVersionne:
    """Plusieurs grilles successives d'un même contrat, chacune avec sa date d'effet.

    La grille d'une date s'applique à partir de minuit ce jour-là. La première
    version peut ne pas avoir de date (« depuis l'installation »).
    """

    def __init__(self, versions: list[dict]) -> None:
        brutes = []
        for v in versions:
            d = v.get("date_effet")
            brutes.append((date.fromisoformat(d) if d else None, Tarif(v["config"])))
        brutes.sort(key=lambda x: x[0] or date.min)
        self.versions: list[tuple[Optional[date], Tarif]] = brutes

    def actif(self, jour: date) -> Tarif:
        choisi = self.versions[0][1]
        for d, t in self.versions:
            if d is None or d <= jour:
                choisi = t
        return choisi

    @property
    def derniere(self) -> Tarif:
        return self.versions[-1][1]

    def calcul(self, dt: datetime, ctx: Optional[Contexte] = None) -> Instant:
        return self.actif(dt.date()).calcul(dt, ctx)

    # Mêmes algorithmes que Tarif : ils ne s'appuient que sur calcul()
    segments = Tarif.segments
    prochain_changement = Tarif.prochain_changement

    # Ce qui détermine les entités à créer : toutes versions confondues
    @property
    def types_offre(self) -> set[str]:
        return {t.type_offre for _d, t in self.versions}

    @property
    def a_hsc(self) -> bool:
        return any(t.a_hsc for _d, t in self.versions)

    @property
    def a_heures_creuses(self) -> bool:
        return any(t.a_heures_creuses for _d, t in self.versions)

    @property
    def noms_speciaux(self) -> list[str]:
        noms: list[str] = []
        for _d, t in self.versions:
            noms += [n for n in t.jours_speciaux if n not in noms]
        return noms

    def historique(self, aujourdhui: date) -> list[dict]:
        actif = self.actif(aujourdhui)
        resultat, precedente, abo_prec = [], None, None
        for d, t in self.versions:
            grille = t.grille()
            variations = comparer_grilles(precedente, grille) if precedente else []
            if abo_prec and t.abonnement is not None and abs(abo_prec - t.abonnement) > 1e-9:
                variations.append({
                    "libelle": "Abonnement", "code": "abonnement", "cle": "€/mois", "avant": abo_prec,
                    "apres": t.abonnement,
                    "variation_pct": round((t.abonnement - abo_prec) / abo_prec * 100, 1),
                })
            pcts = [v["variation_pct"] for v in variations
                    if v["variation_pct"] is not None and v["libelle"] != "Abonnement"]
            if t is actif:
                statut = "en_cours"
            elif d is not None and d > aujourdhui:
                statut = "prevue"
            else:
                statut = "passee"
            resultat.append({
                "date_effet": d.isoformat() if d else None,
                "statut": statut,
                "fournisseur": t.fournisseur,
                "offre": t.offre,
                "abonnement_mensuel": t.abonnement,
                "grille": grille,
                "variations": variations,
                "variation_moyenne_pct": round(sum(pcts) / len(pcts), 1) if pcts else None,
            })
            precedente, abo_prec = grille, t.abonnement
        return resultat


def versions_depuis(data: dict, options: dict) -> list[dict]:
    """Versions enregistrées, ou une version unique si le contrat n'a encore jamais été modifié."""
    if options.get("versions"):
        return [dict(v) for v in options["versions"]]
    cfg = {**data, **{k: v for k, v in options.items() if k != "versions"}}
    return [{"date_effet": None, "config": cfg}]


def trier_versions(versions: list[dict]) -> list[dict]:
    return sorted(versions, key=lambda v: v.get("date_effet") or "")
