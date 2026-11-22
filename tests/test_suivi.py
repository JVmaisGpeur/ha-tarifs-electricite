"""Tests du suivi de consommation (sans Home Assistant)."""

import importlib.util
import pathlib
import sys
from datetime import datetime, timedelta

_base = pathlib.Path(__file__).parents[1] / "custom_components/tarifs_electricite"
for nom in ("tariff", "suivi"):
    spec = importlib.util.spec_from_file_location(nom, _base / f"{nom}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nom] = mod
    spec.loader.exec_module(mod)
tariff, suivi = sys.modules["tariff"], sys.modules["suivi"]

NUIT_WEEKEND = {"type_offre": "hphc", "plages_hc": "23:00-06:00", "prix_hp": 0.30, "prix_hc": 0.17,
          "weekend": "heures_creuses", "feries": "heures_creuses", "abonnement_mensuel": 15.0}


def annee(kwh_par_heure=1.0, jours=365, fin=datetime(2026, 11, 22)):
    t = tariff.Tarif(NUIT_WEEKEND)
    debut = fin - timedelta(days=jours)
    heures = []
    h = debut
    while h < fin:
        prix = suivi.prix_moyen_heure(lambda dt: t.calcul(dt).prix, h)
        heures.append(suivi.Heure(h, kwh_par_heure, prix))
        h += timedelta(hours=1)
    return t, heures


def test_prix_moyen_heure_demi_heure():
    t = tariff.Tarif({"type_offre": "hphc", "plages_hc": "22:30-06:30", "prix_hp": 0.30, "prix_hc": 0.20})
    p = suivi.prix_moyen_heure(lambda dt: t.calcul(dt).prix, datetime(2026, 11, 24, 22, 0))
    assert abs(p - 0.25) < 1e-9


def test_periodes_et_abonnement():
    t, heures = annee(jours=40)
    maintenant = datetime(2026, 11, 22, 12, 0)  # dimanche midi ; données jusqu'à minuit
    debuts = suivi.debuts_de_periode(maintenant)
    assert debuts["semaine"] == datetime(2026, 11, 16)
    r = suivi.resume(heures, debuts["mois"], datetime(2026, 11, 22), 15.0)
    assert r["kwh"] == 21 * 24
    assert abs(r["cout_abonnement"] - 15 * 12 / 365 * 21) < 0.01
    # partie en cours (heure non encore dans les statistiques)
    r2 = suivi.resume(heures, debuts["mois"], datetime(2026, 11, 22), 15.0, 2.0, 0.17)
    assert abs(r2["cout_energie"] - r["cout_energie"] - 0.34) < 0.011


def test_estimation_annee_complete():
    t, heures = annee()
    est = suivi.estimation_annuelle(heures, 15.0, 12, mensualite_fournisseur=180,
                                    repartition=lambda h: t.calcul(h.debut + timedelta(minutes=30)).periode)
    assert est["fiabilite"] == "bonne" and not est["extrapole"]
    assert est["consommation_annuelle_kwh"] == 8760
    # 1 kWh/h : HC ≈ 52 % des heures (nuits + week-ends + fériés)
    assert 48 < est["repartition_pct"]["HC"] < 56
    attendu = (est["cout_energie_annuel"] + 180) / 12
    assert abs(est["mensualite_estimee"] - attendu) < 0.01
    assert abs(est["ecart_mensuel"] - (est["mensualite_estimee"] - 180)) < 0.01
    assert "trop" in est["conseil"] or "correspond" in est["conseil"]


def test_estimation_extrapolee_et_insuffisante():
    _t, heures = annee(jours=60)
    est = suivi.estimation_annuelle(heures, 15.0, 11)
    assert est["fiabilite"] == "faible" and est["extrapole"]
    assert est["consommation_annuelle_kwh"] == 8760
    assert abs(est["mensualite_estimee"] - est["cout_annuel_estime"] / 11) < 0.01
    _t, heures = annee(jours=5)
    assert suivi.estimation_annuelle(heures, 15.0)["fiabilite"] == "insuffisante"


def test_prix_inconnus_completes():
    hs = [suivi.Heure(datetime(2026, 1, 1) + timedelta(hours=i), 1.0, 0.2 if i % 2 else None) for i in range(24 * 20)]
    est = suivi.estimation_annuelle(hs, None)
    assert abs(est["prix_moyen_kwh"] - 0.2) < 1e-9


def test_solde():
    _t, heures = annee(jours=100)
    debut = datetime(2026, 9, 1)
    s = suivi.solde_periode(heures, debut, datetime(2026, 11, 22), 15.0, 200.0, 12)
    jours = (datetime(2026, 11, 22) - debut).days
    assert abs(s["paye_estime"] - 200 * 12 / 365 * jours) < 0.01
    assert abs(s["solde"] - (s["paye_estime"] - s["consomme"])) < 0.01
    assert s["donnees_completes"]


def test_unites():
    assert suivi.kwh_depuis_unite(1500, "Wh") == 1.5
    assert suivi.kwh_depuis_unite(2, "MWh") == 2000


def test_saut_du_compteur_ignore():
    # Index en kWh ; la passerelle repasse à 0 un instant le 4 novembre
    h0 = datetime(2026, 11, 4, 10)
    lignes = [(h0, 0.8, 1856.2), (h0 + timedelta(hours=1), 1857.0, 1857.0),
              (h0 + timedelta(hours=2), 0.5, 1857.5), (h0 + timedelta(hours=3), 4000.0, None)]
    propres, anomalies = suivi.nettoyer_releves(lignes, suivi.plafond_horaire(9))
    assert [round(k, 3) for _d, k in propres] == [0.8, 0.8, 0.5, 0.0]
    assert len(anomalies) == 2
    assert suivi.plafond_horaire(None) == 45.0


def test_periode_facturation():
    from datetime import date
    # Facture tous les 2 mois, dernière connue le 15 septembre
    assert suivi.periode_facturation(date(2026, 9, 15), 2, date(2026, 11, 22)) == (date(2026, 11, 15), date(2027, 1, 15))
    assert suivi.periode_facturation(date(2026, 9, 15), 2, date(2026, 11, 14)) == (date(2026, 9, 15), date(2026, 11, 15))
    # Date de calage dans le futur : on remonte
    assert suivi.periode_facturation(date(2027, 3, 31), 1, date(2026, 11, 22)) == (date(2026, 10, 31), date(2026, 11, 30))
    assert suivi.ajouter_mois(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_facture_en_cours():
    _t, heures = annee(jours=30)
    debut, fin = datetime(2026, 11, 15), datetime(2027, 1, 15)
    f = suivi.facture_en_cours(heures, debut, fin, datetime(2026, 11, 22), 15.0)
    assert f["prochaine_facture"] == "2027-01-15" and f["jours_ecoules"] == 7.0
    assert f["kwh"] == 7 * 24
    # Projection : 7 jours connus prolongés sur 61 jours, abonnement de toute la période
    attendu = f["cout_moyen_par_jour"] * 61 + 15 * 12 / 365 * 61
    assert abs(f["montant_estime"] - attendu) < 0.5, (f, attendu)  # coût par jour arrondi
    assert f["montant_actuel"] < f["montant_estime"]


if __name__ == "__main__":
    for nom, f in list(globals().items()):
        if nom.startswith("test_"):
            f()
            print("ok", nom)
