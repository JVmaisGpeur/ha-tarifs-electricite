"""T3 à T5 (v1.3.0) : comparaison d'offres et puissance conseillée, sans Home Assistant."""

import importlib
import pathlib
import sys
import types
from datetime import date, datetime, timedelta, timezone

BASE = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tarifs_electricite"
pkg = types.ModuleType("te_pkg")
pkg.__path__ = [str(BASE)]
sys.modules.setdefault("te_pkg", pkg)
tariff = importlib.import_module("te_pkg.tariff")
C = importlib.import_module("te_pkg.comparaison")

TZ = timezone(timedelta(hours=1))
FIN = datetime(2026, 11, 1, tzinfo=TZ)
HPHC = {"fournisseur": "F", "offre": "HP/HC", "type_offre": "hphc", "plages_hc": "22:00-06:00",
        "prix_hp": 0.27, "prix_hc": 0.20, "abonnement_mensuel": 15.0, "puissance_kva": 6}
BASE_OFFRE = {"fournisseur": "G", "offre": "Base", "type_offre": "base", "prix_base": 0.25}
TEMPO = {"fournisseur": "H", "offre": "Tempo", "type_offre": "tempo", "plages_hc": "22:00-06:00",
         **{f"prix_{c}_{p}": v for c, vals in {"bleu": (0.16, 0.13), "blanc": (0.19, 0.15), "rouge": (0.70, 0.16)}.items()
            for p, v in zip(("hp", "hc"), vals)}}


def heures(jours=365, kwh=0.1):
    return [(FIN - timedelta(hours=h), kwh) for h in range(1, jours * 24 + 1)]


def ctx(o=None):
    return tariff.Contexte()


def actuelle():
    return C.Offre("Contrat", tariff.Tarif(HPHC), {}, True, 6)


def test_sans_offre_seul_le_contrat():
    res = C.comparer([actuelle()], heures(), ctx, 365)
    assert len(res["lignes"]) == 1 and res["economie_possible"] == 0


def test_offre_identique_meme_total():
    copie = C.Offre("Copie", tariff.Tarif(HPHC), {6: 15.0})
    res = C.comparer([actuelle(), copie], heures(), ctx, 365)
    a, b = res["lignes"]
    assert a["total"] == b["total"] and {a["ecart"], b["ecart"]} == {0.0}


def test_base_deux_puissances():
    base = C.Offre("Base", tariff.Tarif(BASE_OFFRE), {3: 10.0, 6: 13.0})
    res = C.comparer([actuelle(), base], heures(), ctx, 365)
    lignes = [l for l in res["lignes"] if l["offre"] == "Base"]
    assert len(lignes) == 2 and lignes[0]["energie"] == lignes[1]["energie"]
    assert {l["abonnement"] for l in lignes} == {120.0, 156.0}
    assert abs(lignes[0]["energie"] - 876 * 0.25) < 0.01


def test_tempo_couleurs_connues_pas_estime():
    couleurs = lambda j: "bleu"
    t = C.Offre("Tempo", tariff.Tarif(TEMPO), {6: 16.0})
    res = C.comparer([actuelle(), t], heures(30), lambda o: tariff.Contexte(couleur_de=couleurs), 30, annuel=False)
    ligne = next(l for l in res["lignes"] if l["offre"] == "Tempo")
    assert not ligne["estime"]
    # couleur inconnue : prix probable, « estimé »
    res = C.comparer([actuelle(), t], heures(30), ctx, 30, annuel=False)
    assert next(l for l in res["lignes"] if l["offre"] == "Tempo")["estime"]


def test_dynamique_sans_historique_donnees_insuffisantes():
    dyn = C.Offre("Dyn", tariff.Tarif({"fournisseur": "D", "offre": "Dyn", "type_offre": "dynamique"}), {6: 12.0})
    res = C.comparer([actuelle(), dyn], heures(), ctx, 365)
    ligne = next(l for l in res["lignes"] if l["offre"] == "Dyn")
    assert ligne["donnees_insuffisantes"] and ligne["total"] is None
    assert res["meilleure"]["offre"] == "Contrat" and res["lignes"][-1]["offre"] == "Dyn"


def test_sept_mois_extrapoles():
    res = C.comparer([actuelle()], heures(213), ctx, 213)
    assert res["extrapole"]
    ligne = res["lignes"][0]
    assert abs(ligne["kwh"] - 876) <= 1
    assert ligne["abonnement"] == 180.0


def test_service_periode_un_mois():
    res = C.comparer([actuelle()], heures(30), ctx, 30, annuel=False)
    assert not res["extrapole"]
    assert abs(res["lignes"][0]["abonnement"] - 15.0 * 12 * 30 / 365) < 0.01


def _maxima(valeurs):
    return [(FIN - timedelta(hours=i + 1), w) for i, w in enumerate(valeurs)]


def test_pointe_4300_w():
    res = C.depassements({"sensor.p": _maxima([4300, 2000, 3500, 1000])}, False, 6)
    assert res["heures_depassement"]["3"] == 2 and res["heures_depassement"]["6"] == 0
    assert res["conseillee"] == 6 and res["pointe"]["w"] == 4300
    assert res["possible_avec_ecretage"] == 3  # 2 heures ≤ 10 tolérées


def test_tolerance_zero():
    res = C.depassements({"sensor.p": _maxima([4300, 2000])}, False, 6, tolerance=0)
    assert res["conseillee"] == 6 and res["possible_avec_ecretage"] is None


def test_triphase_trois_capteurs():
    phases = {"a": _maxima([3500]), "b": _maxima([1000]), "c": _maxima([500])}
    res = C.depassements(phases, True, 9)
    assert res["par_phase"] and res["heures_depassement"]["9"] == 1  # 3 500 W > 3 000 W par phase
    assert res["pointe"]["phase"] == "a"
    assert res["heures_depassement"]["12"] == 0


def test_triphase_un_seul_capteur_avertit():
    res = C.depassements({"total": _maxima([5000])}, True, 9)
    assert res["avertissement_phase"] and res["heures_depassement"]["9"] == 0