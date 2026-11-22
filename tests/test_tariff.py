"""Tests du moteur de tarifs (sans Home Assistant).

Lancer : python3 -m pytest tests  (ou python3 tests/test_tariff.py)
"""

import importlib.util
import pathlib
import sys
from datetime import date, datetime

_chemin = pathlib.Path(__file__).parents[1] / "custom_components/tarifs_electricite/tariff.py"
_spec = importlib.util.spec_from_file_location("tariff", _chemin)
tariff = importlib.util.module_from_spec(_spec)
sys.modules["tariff"] = tariff
_spec.loader.exec_module(tariff)

# Offre type « nuit & week-end » : HC 23h-6h en semaine, tout le week-end et les jours fériés
NUIT_WEEKEND = {
    "fournisseur": "Enercoop",
    "offre": "Flexibilité Nuit & Week-end",
    "type_offre": "hphc",
    "plages_hc": "23:00-06:00",
    "prix_hp": 0.30638,
    "prix_hc": 0.1729,
    "weekend": "heures_creuses",
    "feries": "heures_creuses",
}


def test_parse_plages():
    assert tariff.parse_plages("23:00-06:00") == [(1380, 1440), (0, 360)]
    assert tariff.parse_plages("23h-6h, 12h30-14h") == [(1380, 1440), (0, 360), (750, 840)]
    assert tariff.parse_plages("") == []
    try:
        tariff.parse_plages("n'importe quoi")
    except tariff.PlageInvalide:
        pass
    else:
        raise AssertionError("plage invalide acceptée")


def test_paques_et_feries():
    assert tariff.paques(2026) == date(2026, 4, 5)
    assert tariff.paques(2027) == date(2027, 3, 28)
    f = tariff.jours_feries(2026)
    assert date(2026, 4, 6) in f  # lundi de Pâques
    assert date(2026, 5, 14) in f  # Ascension
    assert date(2026, 5, 25) in f  # Pentecôte
    assert date(2026, 12, 26) not in f
    assert date(2026, 12, 26) in tariff.jours_feries(2026, alsace_moselle=True)


def test_contrat_nuit_weekend():
    t = tariff.Tarif(NUIT_WEEKEND)
    # Mardi 24 nov. 2026
    assert t.calcul(datetime(2026, 11, 24, 10, 0)).periode == "HP"
    assert t.calcul(datetime(2026, 11, 24, 10, 0)).prix == 0.30638
    assert t.calcul(datetime(2026, 11, 24, 23, 0)).periode == "HC"
    assert t.calcul(datetime(2026, 11, 24, 5, 59)).periode == "HC"
    assert t.calcul(datetime(2026, 11, 24, 6, 0)).periode == "HP"
    assert t.calcul(datetime(2026, 11, 24, 22, 59)).periode == "HP"
    # Samedi et dimanche toute la journée
    assert t.calcul(datetime(2026, 11, 28, 14, 0)).periode == "HC"
    assert t.calcul(datetime(2026, 11, 29, 20, 0)).periode == "HC"
    # Lundi 30 nov. avant 6 h : encore HC, 6 h : HP
    assert t.calcul(datetime(2026, 11, 30, 5, 0)).periode == "HC"
    assert t.calcul(datetime(2026, 11, 30, 6, 0)).periode == "HP"
    # Férié (11 novembre 2026, mercredi)
    assert t.calcul(datetime(2026, 11, 11, 15, 0)).periode == "HC"


def test_prochain_changement_et_segments():
    t = tariff.Tarif(NUIT_WEEKEND)
    quand, ensuite = t.prochain_changement(datetime(2026, 11, 27, 12, 0))  # vendredi
    assert quand == datetime(2026, 11, 27, 23, 0)
    assert ensuite.periode == "HC"
    # Du vendredi 23 h au lundi 6 h : une seule tranche HC
    segs = t.segments(datetime(2026, 11, 27, 23, 0), heures=60)
    assert segs[0]["periode"] == "HC"
    assert segs[0]["fin"] == datetime(2026, 11, 30, 6, 0).isoformat()


def test_hsc_et_saisons():
    t = tariff.Tarif(
        {
            "type_offre": "hphc",
            "saisons": True,
            "plages_hc": "00:00-07:00, 13:00-16:00",
            "plages_hc_ete": "11:00-17:00",
            "plages_hsc_ete": "02:00-05:00",
            "prix_hp": 0.30, "prix_hc": 0.20,
            "prix_hp_ete": 0.25, "prix_hc_ete": 0.15, "prix_hsc_ete": 0.10,
            "weekend": "heures_creuses",
        }
    )
    hiver = t.calcul(datetime(2026, 12, 1, 14, 0))
    assert (hiver.periode, hiver.prix, hiver.saison) == ("HC", 0.20, "hiver")
    ete = t.calcul(datetime(2026, 6, 2, 12, 0))
    assert (ete.periode, ete.prix, ete.saison) == ("HC", 0.15, "ete")
    assert t.calcul(datetime(2026, 6, 2, 3, 0)).periode == "HSC"
    assert t.calcul(datetime(2026, 6, 2, 9, 0)).prix == 0.25


def test_tempo():
    cfg = {"type_offre": "tempo"}
    prix = {"bleu": (0.16, 0.13), "blanc": (0.19, 0.15), "rouge": (0.70, 0.16)}
    for c, (hp, hc) in prix.items():
        cfg[f"prix_{c}_hp"] = hp
        cfg[f"prix_{c}_hc"] = hc
    t = tariff.Tarif(cfg)
    couleurs = {date(2026, 11, 24): "rouge", date(2026, 11, 25): "bleu"}
    # 25 nov. à 3 h : encore le jour Tempo du 24 (rouge), en HC
    i = t.calcul(datetime(2026, 11, 25, 3, 0), tariff.Contexte(couleur_de=couleurs.get))
    assert (i.couleur, i.periode, i.prix) == ("rouge", "HC", 0.16)
    i = t.calcul(datetime(2026, 11, 25, 7, 0), tariff.Contexte(couleur_de=couleurs.get))
    assert (i.couleur, i.periode, i.prix) == ("bleu", "HP", 0.16)
    # Couleur inconnue : période connue, prix inconnu
    i = t.calcul(datetime(2026, 11, 27, 12, 0), tariff.Contexte(couleur_de=couleurs.get))
    assert (i.periode, i.prix) == ("HP", None)


def test_meilleur_creneau():
    t = tariff.Tarif(NUIT_WEEKEND)
    segs = t.segments(datetime(2026, 11, 24, 12, 0), heures=24)  # mardi midi
    c = tariff.meilleur_creneau(segs, 3)
    assert c["debut"] == datetime(2026, 11, 24, 23, 0).isoformat()
    assert c["prix_moyen"] == 0.1729
    # Créneau de 8 h : forcément 1 h de HP
    c = tariff.meilleur_creneau(segs, 8)
    assert c["prix_moyen"] > 0.1729


def test_base():
    t = tariff.Tarif({"type_offre": "base", "prix_base": "0,1952"})
    i = t.calcul(datetime(2026, 11, 24, 12, 0))
    assert (i.periode, i.prix) == ("BASE", 0.1952)
    assert t.prochain_changement(datetime(2026, 11, 24, 12, 0)) == (None, None)


def test_zen_week_end_plus():
    # Base, -30 % le week-end, les fériés et le mercredi
    t = tariff.Tarif({"type_offre": "base", "prix_base": 0.20, "weekend": "prix_weekend",
                      "prix_weekend": 0.14, "feries": "comme_weekend", "jours_extra": ["2"]})
    assert t.calcul(datetime(2026, 11, 24, 12, 0)).prix == 0.20  # mardi
    assert t.calcul(datetime(2026, 11, 25, 12, 0)).periode == "WE"  # mercredi choisi
    assert t.calcul(datetime(2026, 11, 28, 12, 0)).prix == 0.14  # samedi
    assert t.calcul(datetime(2026, 12, 25, 12, 0)).prix == 0.14  # Noël (vendredi)
    lignes = {l["libelle"]: l["prix"] for l in t.grille()["lignes"]}
    assert lignes["Week-end"] == {"BASE": 0.14}


def test_week_end_hphc_avec_hc():
    t = tariff.Tarif({"type_offre": "hphc", "plages_hc": "22:00-06:00", "prix_hp": 0.25,
                      "prix_hc": 0.18, "weekend": "prix_weekend", "prix_weekend": 0.17,
                      "prix_weekend_hc": 0.12})
    assert t.calcul(datetime(2026, 11, 28, 12, 0)).periode == "WE"
    i = t.calcul(datetime(2026, 11, 28, 23, 0))
    assert (i.periode, i.prix) == ("WE_HC", 0.12)
    assert t.calcul(datetime(2026, 11, 27, 23, 0)).prix == 0.18  # vendredi soir


def test_zen_flex_jour_special():
    t = tariff.Tarif({"type_offre": "hphc", "plages_hc": "13:00-18:00, 20:00-08:00",
                      "prix_hp": 0.2142, "prix_hc": 0.1595, "jours_speciaux": True,
                      "js_debut_h": 8, "js1_nom": "Sobriété", "js1_prix_hp": 0.7467,
                      "js1_prix_hc": 0.2142})
    sobriete = {date(2026, 12, 15)}
    ctx = tariff.Contexte(special_de=lambda j: "Sobriété" if j in sobriete else None)
    # Mardi 15 déc. 9 h : HP de jour Sobriété
    i = t.calcul(datetime(2026, 12, 15, 9, 0), ctx)
    assert (i.periode, i.prix, i.jour_special) == ("HP", 0.7467, "Sobriété")
    # 15 déc. 14 h : HC de jour Sobriété
    assert t.calcul(datetime(2026, 12, 15, 14, 0), ctx).prix == 0.2142
    # 16 déc. 7 h : encore le jour Sobriété (il va jusqu'à 8 h)
    assert t.calcul(datetime(2026, 12, 16, 7, 0), ctx).jour_special == "Sobriété"
    # 16 déc. 9 h : jour normal
    assert t.calcul(datetime(2026, 12, 16, 9, 0), ctx).prix == 0.2142
    assert t.calcul(datetime(2026, 12, 16, 9, 0), ctx).jour_special is None


def test_modulo_perso_saisons():
    t = tariff.Tarif({"type_offre": "hphc", "saisons": True, "mois_hiver": ["11", "12", "1", "2", "3"],
                      "perso_nom": "Heures solaires",
                      "plages_hc": "23:00-07:00", "prix_hp": 0.21, "prix_hc": 0.16,
                      "plages_hc_ete": "23:00-07:00", "plages_perso_ete": "11:00-16:00",
                      "prix_hp_ete": 0.20, "prix_hc_ete": 0.155, "prix_perso_ete": 0.10})
    i = t.calcul(datetime(2026, 6, 10, 12, 0))
    assert (i.periode, i.prix, i.libelle) == ("PERSO", 0.10, "Heures solaires")
    assert t.calcul(datetime(2026, 12, 10, 12, 0)).periode == "HP"
    g = t.grille()
    assert {"cle": "PERSO", "nom": "Heures solaires"} in g["colonnes"]


def test_base_saisons():
    t = tariff.Tarif({"type_offre": "base", "saisons": True, "prix_base": 0.20, "prix_base_ete": 0.14})
    assert t.calcul(datetime(2026, 7, 1, 12, 0)).prix == 0.14
    assert t.calcul(datetime(2026, 1, 1, 12, 0)).prix == 0.20


def test_dynamique():
    attrs = {"data": [
        {"start_time": "2026-11-22T16:00:00+01:00", "end_time": "2026-11-22T17:00:00+01:00", "price_eur_per_mwh": 80},
        {"start_time": "2026-11-22T17:00:00+01:00", "end_time": "2026-11-22T18:00:00+01:00", "price_eur_per_mwh": 120},
    ]}
    serie = tariff.lire_serie_prix(attrs)
    assert serie[1][2] == 0.12
    nordpool = {"raw_today": [{"start": "2026-11-22T16:00:00+01:00", "value": 9.5},
                              {"start": "2026-11-22T17:00:00+01:00", "value": 4.0}]}
    s2 = tariff.lire_serie_prix(nordpool, tariff.facteur_unite("c€/kWh"))
    assert abs(s2[0][2] - 0.095) < 1e-9 and s2[1][1].hour == 18
    t = tariff.Tarif({"type_offre": "dynamique", "dyn_majoration": 0.10})

    def prix(dt):
        for d, f, p in serie:
            if d <= dt < f:
                return p
        return None
    from datetime import timezone, timedelta as td
    tz = timezone(td(hours=1))
    ctx = tariff.Contexte(prix_dyn_de=prix)
    assert t.calcul(datetime(2026, 11, 22, 17, 30, tzinfo=tz), ctx).prix == 0.22
    segs = t.segments(datetime(2026, 11, 22, 16, 0, tzinfo=tz), 3, ctx)
    assert [s["prix"] for s in segs] == [0.18, 0.22, None]


def test_versions_datees():
    v1 = dict(NUIT_WEEKEND, abonnement_mensuel=15.0)
    v2 = dict(NUIT_WEEKEND, prix_hp=0.3150, prix_hc=0.1780, abonnement_mensuel=15.5)
    t = tariff.TarifVersionne([{"date_effet": None, "config": v1},
                               {"date_effet": "2027-02-01", "config": v2}])
    assert t.calcul(datetime(2027, 1, 29, 12, 0)).prix == 0.30638  # vendredi, HP
    assert t.calcul(datetime(2027, 2, 1, 12, 0)).prix == 0.3150   # lundi, nouveau HP
    # Changement de prix à minuit même si la période ne change pas (HC du week-end)
    quand, ensuite = t.prochain_changement(datetime(2027, 1, 31, 23, 30))
    assert quand == datetime(2027, 2, 1, 0, 0) and ensuite.prix == 0.1780
    h = t.historique(date(2026, 11, 22))
    assert [x["statut"] for x in h] == ["en_cours", "prevue"]
    assert h[1]["variation_moyenne_pct"] == 2.8
    assert {"libelle": "Abonnement", "cle": "€/mois", "avant": 15.0, "apres": 15.5,
            "variation_pct": 3.3} in h[1]["variations"]
    # Une fois la date passée
    h = t.historique(date(2027, 3, 1))
    assert [x["statut"] for x in h] == ["passee", "en_cours"]
    assert t.noms_speciaux == [] and t.a_heures_creuses


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
