"""Tests du gestionnaire avec un Home Assistant simulé (aucune dépendance à installer)."""

import sys, types, importlib.util, pathlib
from datetime import datetime, timedelta, timezone, date
TZ = timezone(timedelta(hours=1))
HORLOGE = [datetime(2026, 12, 15, 9, 0, tzinfo=TZ)]

def mod(nom, **attrs):
    m = types.ModuleType(nom); m.__dict__.update(attrs); sys.modules[nom] = m; return m
class Any_:
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return self
    def __getattr__(self, n): return Any_()
vol = mod("voluptuous", Schema=Any_, Optional=Any_, Required=Any_, All=Any_, Coerce=Any_, Range=Any_)
mod("aiohttp", ClientSession=object, ClientError=Exception, ClientTimeout=Any_)
mod("homeassistant"); mod("homeassistant.helpers"); mod("homeassistant.util")
mod("homeassistant.config_entries", ConfigEntry=object)
mod("homeassistant.const", STATE_UNAVAILABLE="unavailable", STATE_UNKNOWN="unknown",
    Platform=types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor", SELECT="select"))
mod("homeassistant.core", HomeAssistant=object, ServiceCall=object, ServiceResponse=dict,
    SupportsResponse=types.SimpleNamespace(ONLY="only"), callback=lambda f: f)
mod("homeassistant.exceptions", ServiceValidationError=Exception)
mod("homeassistant.helpers.config_validation", config_entry_only_config_schema=lambda d: None, string=str)
mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda h: None)
ENVOIS = []
mod("homeassistant.helpers.dispatcher", async_dispatcher_send=lambda h, s: ENVOIS.append(s))
PROG = []
mod("homeassistant.helpers.event", async_track_point_in_time=lambda h, f, t: (PROG.append(t), (lambda: None))[1],
    async_track_state_change_event=lambda h, e, f: (lambda: None), async_track_time_interval=lambda h, f, i: (lambda: None),
    async_call_later=lambda h, d, f: (lambda: None), async_track_time_change=lambda h, f, **k: (lambda: None))
class _Store:
    def __init__(self, *a): self.sauve = None
    async def async_load(self): return None
    def async_delay_save(self, f, d): self.sauve = f()
mod("homeassistant.helpers.storage", Store=_Store)
mod("homeassistant.helpers.typing", ConfigType=dict)
mod("homeassistant.util.dt", now=lambda: HORLOGE[0], as_local=lambda d: d.astimezone(TZ),
    utc_from_timestamp=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
    utcnow=lambda: HORLOGE[0].astimezone(timezone.utc))
sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]

base = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tarifs_electricite"
pkg = types.ModuleType("te"); pkg.__path__ = [str(base)]; sys.modules["te"] = pkg
spec = importlib.util.spec_from_file_location("te", base / "__init__.py", submodule_search_locations=[str(base)])
te = importlib.util.module_from_spec(spec); sys.modules["te"] = te; spec.loader.exec_module(te)

class Etat:
    def __init__(s, state, attributes=None): s.state = state; s.attributes = attributes or {}
class States(dict):
    def get(s, k): return dict.get(s, k)
hass = types.SimpleNamespace(states=States())
def entree(cfg): return types.SimpleNamespace(data=cfg, options={}, entry_id="e1")

# 1) Zen Flex en manuel : choix pour demain, bascule à 8 h
cfg = {"fournisseur": "EDF", "offre": "Zen Flex", "type_offre": "hphc", "plages_hc": "13:00-18:00, 20:00-08:00",
       "prix_hp": 0.2142, "prix_hc": 0.1595, "jours_speciaux": True, "js_debut_h": 8, "js1_nom": "Sobriété",
       "js1_prix_hp": 0.7467, "js1_prix_hc": 0.2142}
g = te.GestionnaireTarif(hass, entree(cfg))
g._recalculer()
assert g.etat["prix"] == 0.2142 and g.etat["jour_special"] is None
g.choisir_jour_special("demain", "Sobriété")
segs = g.etat["previsions"]
assert any(s["jour_special"] == "Sobriété" for s in segs)
HORLOGE[0] = datetime(2026, 12, 16, 7, 59, tzinfo=TZ); g._recalculer()
assert g.etat["jour_special"] is None, g.etat["jour_special"]      # pas encore 8 h
HORLOGE[0] = datetime(2026, 12, 16, 8, 0, tzinfo=TZ); g._recalculer()
assert g.etat["jour_special"] == "Sobriété" and g.etat["prix"] == 0.7467
assert g.etat["jours_speciaux"]["demain"] == "Normal"
HORLOGE[0] = datetime(2026, 12, 17, 8, 0, tzinfo=TZ); g._recalculer()
assert g.etat["jour_special"] is None and g.etat["prix"] == 0.2142
print("manuel + bascule ok")

# 2) Source automatique (capteur texte d'une autre intégration)
cfg2 = dict(cfg, js1_source="sensor.zen_flex_aujourdhui", js1_valeur="Sobriété", js1_source_demain="sensor.zen_flex_demain")
hass.states["sensor.zen_flex_aujourdhui"] = Etat("sobriete")
hass.states["sensor.zen_flex_demain"] = Etat("Éco")
HORLOGE[0] = datetime(2026, 12, 15, 9, 0, tzinfo=TZ)
g2 = te.GestionnaireTarif(hass, entree(cfg2)); g2._recalculer()
assert g2.etat["jour_special"] == "Sobriété" and g2.etat["jours_speciaux"]["auto_aujourdhui"]
assert g2.etat["jours_speciaux"]["demain"] == "Normal"
hass.states["sensor.zen_flex_aujourdhui"] = Etat("unavailable"); g2._recalculer()
assert g2.etat["jour_special"] is None and not g2.etat["jours_speciaux"]["auto_aujourdhui"]
print("source auto ok")

# 3) Restauration après redémarrage
g3 = te.GestionnaireTarif(hass, entree(cfg)); g3._recalculer()
g3.restaurer_jour_special("demain", "Sobriété", "2026-12-16"); g3._recalculer()
assert g3.etat["jours_speciaux"]["demain"] == "Sobriété"
g3.restaurer_jour_special("aujourdhui", "Sobriété", "2026-12-01")   # périmé
assert g3.etat["jours_speciaux"]["aujourdhui"] == "Normal"
print("restauration ok")

# 4) Dynamique, entité en €/MWh avec prévisions EPEX
attrs = {"unit_of_measurement": "EUR/MWh", "data": [
    {"start_time": (HORLOGE[0].replace(minute=0) + timedelta(hours=h)).isoformat(),
     "end_time": (HORLOGE[0].replace(minute=0) + timedelta(hours=h + 1)).isoformat(),
     "price_eur_per_mwh": 50 + 10 * h} for h in range(24)]}
hass.states["sensor.epex"] = Etat("50", attrs)
g4 = te.GestionnaireTarif(hass, entree({"fournisseur": "Sobry", "offre": "x", "type_offre": "dynamique",
                                        "dyn_source": "sensor.epex", "dyn_majoration": 0.12}))
g4._recalculer()
assert abs(g4.etat["prix"] - 0.17) < 1e-9, g4.etat["prix"]
assert g4.etat["prochain_changement"] == HORLOGE[0].replace(minute=0) + timedelta(hours=1)
assert g4.etat["prix_bas"] is True and g4.etat["previsions_disponibles"]
assert len(g4.etat["previsions"]) == 25  # 24 h connues + reste inconnu
# sans prévisions : seule l'heure en cours
hass.states["sensor.epex"] = Etat("8.5", {"unit_of_measurement": "c€/kWh"}); g4._recalculer()
assert abs(g4.etat["prix"] - 0.205) < 1e-9 and g4.etat["previsions_disponibles"] is False
print("dynamique ok")

# 5) Contrat Enercoop Nuit & Week-end
g5 = te.GestionnaireTarif(hass, entree({"fournisseur": "Enercoop", "offre": "NWE", "type_offre": "hphc",
     "plages_hc": "23:00-06:00", "prix_hp": 0.30638, "prix_hc": 0.1729, "weekend": "heures_creuses", "feries": "heures_creuses"}))
HORLOGE[0] = datetime(2026, 11, 28, 15, 0, tzinfo=TZ); g5._recalculer()
assert g5.etat["heures_creuses"] and g5.etat["prix"] == 0.1729
assert g5.etat["prochain_changement"] == datetime(2026, 11, 30, 6, 0, tzinfo=TZ)
print("contrat Enercoop ok")

# 6) Évolution tarifaire saisie à l'avance
cfg6 = {"fournisseur": "Enercoop", "offre": "NWE", "type_offre": "hphc", "plages_hc": "23:00-06:00",
        "prix_hp": 0.30638, "prix_hc": 0.1729, "weekend": "heures_creuses", "feries": "heures_creuses"}
e6 = types.SimpleNamespace(data=cfg6, entry_id="e6", options={"versions": [
    {"date_effet": None, "config": cfg6},
    {"date_effet": "2027-02-01", "config": dict(cfg6, prix_hp=0.3150, prix_hc=0.1780)}]})
g6 = te.GestionnaireTarif(hass, e6)
HORLOGE[0] = datetime(2027, 1, 31, 20, 0, tzinfo=TZ); g6._recalculer()
assert g6.etat["prix"] == 0.1729
assert g6.etat["prochain_changement"] == datetime(2027, 2, 1, 0, 0, tzinfo=TZ)
assert g6.etat["prochain_prix"] == 0.1780
assert g6.etat["evolution_prevue"]["date_effet"] == "2027-02-01"
HORLOGE[0] = datetime(2027, 2, 1, 10, 0, tzinfo=TZ); g6._recalculer()
assert g6.etat["prix"] == 0.3150 and g6.etat["evolution_prevue"] is None
assert [h["statut"] for h in g6.etat["historique_prix"]] == ["passee", "en_cours"]
# Ancienne installation (options à plat, sans versions) : toujours lisible
e7 = types.SimpleNamespace(data=cfg6, entry_id="e7", options={"prix_hp": 0.40})
g7 = te.GestionnaireTarif(hass, e7); g7._recalculer()
assert g7.tarif.regles["annee"].prix["HP"] == 0.40
print("évolutions datées ok")

# 7) Suivi de consommation : statistiques simulées (1 kWh/h pendant 400 jours)
import asyncio
cfg8 = dict(cfg6, abonnement_mensuel=15.0, compteur="sensor.conso", mensualite_fournisseur=180,
            prelevements_par_an="12", date_debut_facturation="2026-09-01")
e8 = types.SimpleNamespace(data=cfg8, entry_id="e8", options={})
HORLOGE[0] = datetime(2026, 11, 22, 16, 40, tzinfo=TZ)
async def executeur(f, *a): return f(*a)
hass.async_add_executor_job = executeur
g8 = te.GestionnaireTarif(hass, e8)
assert g8.suivi and g8.suivi.mensualite == 180 and g8.suivi.prelevements == 12
g8.entite_prix = "sensor.tarif_electricite_prix_actuel"
fin_stats = datetime(2026, 11, 22, 15, 0, tzinfo=TZ)
async def fausses_stats(stat_id, debut, fin, types_, unites=None):
    lignes, h, etat = [], fin_stats - timedelta(days=400), 1000.0
    while h < fin_stats:
        etat += 1.0
        ligne = {"start": h.timestamp(), "change": 1.0, "state": etat}
        if stat_id == "sensor.tarif_electricite_prix_actuel":
            if h < fin_stats - timedelta(days=30):
                h += timedelta(hours=1); continue   # intégration installée il y a 30 jours
            ligne = {"start": h.timestamp(), "mean": 0.25}
        if h >= debut:
            lignes.append(ligne)
        h += timedelta(hours=1)
    return lignes
g8.suivi._stats = fausses_stats
g8._recalculer()
hass.states["sensor.conso"] = Etat(str(1000 + 400 * 24 + 1.5), {"unit_of_measurement": "kWh"})
asyncio.run(g8.suivi.async_maj())
r = g8.etat["suivi"]
assert r["etat"] == "ok", r
# Aujourd'hui : 00:00 → 15:00 dans les stats (15 kWh) + 1,5 kWh en cours
assert abs(r["aujourdhui"]["kwh"] - 16.5) < 1e-6, r["aujourdhui"]
# les 30 derniers jours au prix enregistré (0,25 €), le reste recalculé depuis la grille
assert abs(r["aujourdhui"]["cout_energie"] - (15 * 0.25 + 1.5 * g8.etat["prix"])) < 0.01, r["aujourdhui"]
assert r["semaine"]["kwh"] > r["aujourdhui"]["kwh"] and r["annee"]["kwh"] > r["mois"]["kwh"]
est = r["estimation"]
assert est["fiabilite"] == "bonne" and not est["extrapole"] and 8700 < est["consommation_annuelle_kwh"] <= 8760, est
assert est["mensualite_fournisseur"] == 180 and "conseil" in est
assert set(est["repartition_pct"]) == {"Heures pleines", "Heures creuses"}
solde = r["solde"]
assert solde["depuis"] == "2026-09-01" and solde["donnees_completes"]
assert abs(solde["solde"] - (solde["paye_estime"] - solde["consomme"])) < 0.01
print("suivi ok :", r["aujourdhui"]["total"], "€ aujourd'hui ·", est["mensualite_estimee"], "€/mois estimés ·", est["conseil"][:60])

# 8) Paiement à la consommation réelle, facture tous les 2 mois + saut du compteur
cfg9 = dict(cfg6, abonnement_mensuel=13.41, puissance_kva=6, compteur="sensor.conso",
            mode_paiement="conso_reelle", frequence_mois="2", date_debut_facturation="2026-09-15")
g9 = te.GestionnaireTarif(hass, types.SimpleNamespace(data=cfg9, entry_id="e9", options={}))
g9.entite_prix = None
async def stats_avec_saut(stat_id, debut, fin, types_, unites=None):
    lignes = await fausses_stats(stat_id, debut, fin, types_, unites)
    for l in lignes:  # le 4 novembre à 10 h, l'index repasse par 0
        if l["start"] == datetime(2026, 11, 4, 10, tzinfo=TZ).timestamp():
            l["change"] = l["state"]
    return lignes
g9.suivi._stats = stats_avec_saut
g9._recalculer()
asyncio.run(g9.suivi.async_maj())
r = g9.etat["suivi"]
assert r["heures_corrigees"] == 1, r["heures_corrigees"]
assert abs(r["mois"]["kwh"] - (21 * 24 + 15 + 1.5)) < 1e-6, r["mois"]["kwh"]  # 1 kWh/h, sans le saut
f = r["facture"]
assert f["debut"] == "2026-11-15" and f["prochaine_facture"] == "2027-01-15", f
assert f["montant_estime"] > f["montant_actuel"] > 0
est = r["estimation"]
assert est["factures_par_an"] == 6 and "facture_moyenne_estimee" in est and "mensualite_estimee" not in est
assert "ecart_mensuel" not in est and "solde" not in r
print("consommation réelle ok :", f["montant_actuel"], "€ →", f["montant_estime"], "€ le", f["prochaine_facture"])
