"""Contrat d'interface (version 1) : ce que les autres intégrations peuvent utiliser.

Si un de ces tests échoue, c'est qu'un changement casse le contrat : il faut
alors une version majeure et `version_interface` + 1 (voir README).
"""

import asyncio
import importlib.util
import json
import pathlib
import re
import sys
import types
from datetime import date, datetime, timedelta, timezone

TZ = timezone(timedelta(hours=1))
HORLOGE = [datetime(2026, 11, 24, 10, 0, tzinfo=TZ)]  # mardi
RACINE = pathlib.Path(__file__).resolve().parents[1]
BASE = RACINE / "custom_components" / "tarifs_electricite"


# ------------------------------------------------------------------ Home Assistant simulé
def mod(nom, **attrs):
    m = types.ModuleType(nom)
    m.__dict__.update(attrs)
    sys.modules[nom] = m
    return m


class Rien:
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return self

    def __getattr__(self, n):
        return Rien()


class Base:
    """Remplace SensorEntity, BinarySensorEntity, SelectEntity, RestoreEntity, Entity."""

    def async_on_remove(self, f):
        pass


mod("voluptuous", Schema=Rien, Optional=Rien, Required=Rien, All=Rien, Coerce=Rien, Range=Rien)
mod("aiohttp", ClientSession=object, ClientError=Exception, ClientTimeout=Rien)
for n in ("homeassistant", "homeassistant.helpers", "homeassistant.util", "homeassistant.components"):
    mod(n)
mod("homeassistant.config_entries", ConfigEntry=object)
mod("homeassistant.const", STATE_UNAVAILABLE="unavailable", STATE_UNKNOWN="unknown",
    Platform=types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor", SELECT="select"))
mod("homeassistant.core", HomeAssistant=object, ServiceCall=object, ServiceResponse=dict,
    SupportsResponse=types.SimpleNamespace(ONLY="only"), callback=lambda f: f)
mod("homeassistant.exceptions", ServiceValidationError=Exception)
mod("homeassistant.helpers.config_validation", config_entry_only_config_schema=lambda d: None, string=str,
    datetime=lambda v: v)
mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda h: None)
mod("homeassistant.helpers.dispatcher", async_dispatcher_send=lambda h, s: None,
    async_dispatcher_connect=lambda *a: (lambda: None))
mod("homeassistant.helpers.event", async_track_point_in_time=lambda *a: (lambda: None),
    async_track_state_change_event=lambda *a: (lambda: None),
    async_track_time_interval=lambda *a: (lambda: None),
    async_call_later=lambda *a: (lambda: None), async_track_time_change=lambda *a, **k: (lambda: None))


class _Store:
    def __init__(self, *a):
        pass

    async def async_load(self):
        return None

    def async_delay_save(self, f, d):
        pass


mod("homeassistant.helpers.storage", Store=_Store)
mod("homeassistant.helpers.typing", ConfigType=dict)
mod("homeassistant.helpers.device_registry", DeviceInfo=dict, DeviceEntryType=types.SimpleNamespace(SERVICE="service"))
mod("homeassistant.helpers.entity", Entity=Base)
mod("homeassistant.helpers.entity_platform", AddEntitiesCallback=object)
mod("homeassistant.helpers.restore_state", RestoreEntity=type("RestoreEntity", (), {}))
classes = types.SimpleNamespace(ENUM="enum", TIMESTAMP="timestamp", MONETARY="monetary", DATE="date")
mod("homeassistant.components.sensor", SensorEntity=type("SensorEntity", (), {}), SensorDeviceClass=classes,
    SensorStateClass=types.SimpleNamespace(MEASUREMENT="measurement"))
mod("homeassistant.components.binary_sensor", BinarySensorEntity=type("BinarySensorEntity", (), {}))
mod("homeassistant.components.select", SelectEntity=type("SelectEntity", (), {}))
mod("homeassistant.util.dt", now=lambda: HORLOGE[0], as_local=lambda d: d,
    utc_from_timestamp=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
    utcnow=lambda: HORLOGE[0].astimezone(timezone.utc))
sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]

spec = importlib.util.spec_from_file_location("te", BASE / "__init__.py", submodule_search_locations=[str(BASE)])
te = importlib.util.module_from_spec(spec)
sys.modules["te"] = te
spec.loader.exec_module(te)
import te.binary_sensor as plat_binary  # noqa: E402
import te.select as plat_select  # noqa: E402
import te.sensor as plat_sensor  # noqa: E402


class States(dict):
    def get(self, k):
        return dict.get(self, k)


def gestionnaire(cfg, options=None, entry_id="e1"):
    hass = types.SimpleNamespace(states=States(), data={te.DOMAIN: {}})
    entry = types.SimpleNamespace(data=cfg, options=options or {}, entry_id=entry_id, title="Contrat")
    g = te.GestionnaireTarif(hass, entry)
    g._recalculer()
    hass.data[te.DOMAIN][entry_id] = g
    return g


def entites(g):
    """translation_key des entités créées par les trois plateformes."""
    trouvees = []
    for plat in (plat_sensor, plat_binary, plat_select):
        asyncio.run(plat.async_setup_entry(g.hass, g.entry, lambda e: trouvees.extend(e)))
    return {e._attr_translation_key: e for e in trouvees}


HPHC = {"fournisseur": "Enercoop", "offre": "Flexibilité Nuit & Week-end", "type_offre": "hphc",
        "plages_hc": "23:00-06:00", "prix_hp": 0.30638, "prix_hc": 0.1729,
        "weekend": "heures_creuses", "feries": "heures_creuses", "puissance_kva": 6.0}
TEMPO = {"fournisseur": "EDF", "offre": "Tempo", "type_offre": "tempo", "plages_hc": "22:00-06:00",
         **{f"prix_{c}_{p}": v for c, (hp, hc) in {"bleu": (0.16, 0.13), "blanc": (0.19, 0.15),
                                                    "rouge": (0.70, 0.16)}.items()
            for p, v in (("hp", hp), ("hc", hc))}}
CHAMPS_SEGMENT = {"debut", "fin", "periode", "libelle", "prix", "couleur", "saison", "jour_special",
                  "jour_special_confirme", "heures_creuses"}
TOUJOURS = {"puissance_souscrite", "offre", "prix_actuel", "periode", "prochain_changement",
            "prochain_prix", "prix_bas"}


# ------------------------------------------------------------------ service previsions
def test_reponse_et_segments_contigus_sur_72_h():
    g = gestionnaire(HPHC)
    r = g.reponse_previsions(72, duree=3)
    assert r["version_interface"] == 1
    assert (r["fournisseur"], r["offre"], r["type_offre"], r["puissance_kva"]) == (
        "Enercoop", "Flexibilité Nuit & Week-end", "hphc", 6)
    segs = r["segments"]
    assert datetime.fromisoformat(segs[0]["debut"]) == HORLOGE[0]
    assert datetime.fromisoformat(segs[-1]["fin"]) == HORLOGE[0] + timedelta(hours=72)
    for a, b in zip(segs, segs[1:]):
        assert a["fin"] == b["debut"], (a, b)  # ni trou ni chevauchement
    for s in segs:
        assert set(s) == CHAMPS_SEGMENT, set(s) ^ CHAMPS_SEGMENT
        assert datetime.fromisoformat(s["debut"]).tzinfo is not None
        assert s["periode"] in {"hp", "hc", "hsc", "perso", "we", "we_hc", "base", "dyn"}
    assert {"moins_cher", "plus_cher", "meilleur_creneau"} <= set(r)


def _creuses(cfg, quand):
    g = gestionnaire(cfg)
    return {s["periode"]: s["heures_creuses"] for s in g.reponse_previsions(72)["segments"]
            if datetime.fromisoformat(s["debut"]) <= quand < datetime.fromisoformat(s["fin"])}


def test_heures_creuses_par_type_offre():
    mardi_midi = datetime(2026, 11, 24, 12, 0, tzinfo=TZ)
    mardi_nuit = datetime(2026, 11, 25, 2, 0, tzinfo=TZ)
    assert _creuses({"type_offre": "base", "prix_base": 0.2}, mardi_midi) == {"base": False}
    assert _creuses(HPHC, mardi_midi) == {"hp": False}
    assert _creuses(HPHC, mardi_nuit) == {"hc": True}
    # Week-end entièrement en heures creuses
    HORLOGE[0] = datetime(2026, 11, 27, 10, 0, tzinfo=TZ)
    assert _creuses(HPHC, datetime(2026, 11, 28, 15, 0, tzinfo=TZ)) == {"hc": True}
    # Jour férié (11 novembre)
    HORLOGE[0] = datetime(2026, 11, 10, 10, 0, tzinfo=TZ)
    assert _creuses(HPHC, datetime(2026, 11, 11, 15, 0, tzinfo=TZ)) == {"hc": True}
    # Prix week-end dédié : HP du week-end pas creuses, HC du week-end creuses
    we = dict(HPHC, weekend="prix_weekend", prix_weekend=0.2, prix_weekend_hc=0.12)
    HORLOGE[0] = datetime(2026, 11, 27, 10, 0, tzinfo=TZ)
    assert _creuses(we, datetime(2026, 11, 28, 15, 0, tzinfo=TZ)) == {"we": False}
    assert _creuses(we, datetime(2026, 11, 28, 23, 30, tzinfo=TZ)) == {"we_hc": True}
    # Période nommée : creuse par défaut, ou non si le contrat le dit
    perso = dict(HPHC, perso_nom="Heures solaires", plages_perso="12:00-14:00", prix_perso=0.1)
    HORLOGE[0] = datetime(2026, 11, 24, 10, 0, tzinfo=TZ)
    assert _creuses(perso, mardi_midi) == {"perso": True}
    assert _creuses(dict(perso, perso_creuse=False), mardi_midi) == {"perso": False}
    # Super creuses
    hsc = dict(HPHC, plages_hsc="02:00-05:00", prix_hsc=0.1)
    assert _creuses(hsc, datetime(2026, 11, 25, 3, 0, tzinfo=TZ)) == {"hsc": True}
    # Tempo : HC creuses ; prix dynamique : jamais
    assert _creuses(TEMPO, datetime(2026, 11, 24, 23, 0, tzinfo=TZ)) == {"hc": True}


def test_tempo_prix_inconnu_explicite():
    HORLOGE[0] = datetime(2026, 11, 24, 10, 0, tzinfo=TZ)
    g = gestionnaire(TEMPO)
    g.tempo.confirmees = {date(2026, 11, 24): "bleu"}  # demain pas encore annoncé
    g._recalculer()
    segs = g.reponse_previsions(48)["segments"]
    for s in segs:
        debut = datetime.fromisoformat(s["debut"])
        if debut < datetime(2026, 11, 25, 6, 0, tzinfo=TZ):
            assert s["couleur"] == "bleu" and s["prix"] is not None
        else:
            assert s["couleur"] is None and s["prix"] is None, s
    # Le prix inconnu n'est jamais choisi comme le moins cher
    r = g.reponse_previsions(48)
    assert r["moins_cher"]["prix"] is not None


def test_jour_special_confirme():
    zen = dict(HPHC, plages_hc="13:00-18:00, 20:00-08:00", jours_speciaux=True, js_debut_h=8,
               js1_nom="Sobriété", js1_prix_hp=0.75, js1_prix_hc=0.21)
    HORLOGE[0] = datetime(2026, 12, 15, 10, 0, tzinfo=TZ)
    g = gestionnaire(zen)

    def confirme(jour):
        return {s["jour_special_confirme"] for s in g.reponse_previsions(72)["segments"]
                if g.tarif.jour_special_de(datetime.fromisoformat(s["debut"])) == jour}

    assert confirme(date(2026, 12, 15)) == {True}
    assert confirme(date(2026, 12, 16)) == {False}  # rien d'annoncé pour demain
    g.choisir_jour_special("demain", "Sobriété")
    assert confirme(date(2026, 12, 16)) == {True}
    assert confirme(date(2026, 12, 17)) == {False}
    # Offre sans jours spéciaux : toujours connu
    g2 = gestionnaire(HPHC)
    assert {s["jour_special_confirme"] for s in g2.reponse_previsions(72)["segments"]} == {True}


def test_dynamique_jamais_heures_creuses():
    g = gestionnaire({"fournisseur": "Sobry", "offre": "x", "type_offre": "dynamique",
                      "dyn_source": "sensor.absent"})
    r = g.reponse_previsions(24)
    assert r["type_offre"] == "dynamique" and r["puissance_kva"] is None
    assert all(s["heures_creuses"] is False and s["periode"] == "dyn" for s in r["segments"])
    assert all(s["prix"] is None for s in r["segments"])  # source absente : prix inconnu


# ------------------------------------------------------------------ entités
def test_translation_keys_du_contrat():
    hphc = entites(gestionnaire(dict(HPHC, plages_hsc="02:00-05:00", prix_hsc=0.1)))
    assert TOUJOURS | {"heures_creuses", "heures_super_creuses"} <= set(hphc), set(hphc)
    tempo = entites(gestionnaire(TEMPO))
    assert TOUJOURS | {"heures_creuses", "tempo_aujourdhui", "tempo_demain", "tempo_previsions"} <= set(tempo)
    base = entites(gestionnaire({"type_offre": "base", "prix_base": 0.2}))
    assert TOUJOURS <= set(base) and "heures_creuses" not in base
    # Chaque clé du contrat a son nom traduit
    textes = json.load(open(BASE / "strings.json"))["entity"]
    for cle in TOUJOURS | {"tempo_aujourdhui", "tempo_demain", "tempo_previsions"}:
        assert cle in textes["sensor"] or cle in textes["binary_sensor"], cle
    for cle in ("heures_creuses", "heures_super_creuses", "prix_bas"):
        assert cle in textes["binary_sensor"], cle


def test_puissance_et_offre():
    e = entites(gestionnaire(HPHC))
    assert e["puissance_souscrite"].native_value == 6
    assert e["puissance_souscrite"]._attr_native_unit_of_measurement == "kVA"
    assert e["offre"].native_value == "hphc"
    assert e["offre"].extra_state_attributes == {"fournisseur": "Enercoop",
                                                 "nom_offre": "Flexibilité Nuit & Week-end"}
    assert set(e["offre"]._attr_options) == {"base", "hphc", "tempo", "dynamique"}
    assert e["periode"].native_value in e["periode"]._attr_options


def test_mise_a_jour_depuis_1_0_0():
    # Contrat 1.0.0 : sans puissance, options d'origine
    ancien = {k: v for k, v in HPHC.items() if k != "puissance_kva"}
    g = gestionnaire(ancien, options={}, entry_id="ancien")
    e = entites(g)
    assert e["puissance_souscrite"].native_value is None  # état unknown
    assert e["prix_actuel"]._attr_unique_id == "ancien_prix_actuel"
    assert e["prix_actuel"].entity_id == "sensor.tarif_electricite_prix_actuel"
    assert e["periode"].entity_id == "sensor.tarif_electricite_periode"


# ------------------------------------------------------------------ v1.2.0 : prix de revente
def test_prix_revente_absent_puis_saisi():
    assert "prix_revente" not in entites(gestionnaire(HPHC))
    g = gestionnaire(dict(HPHC, prix_revente=0.13))
    e = entites(g)
    assert e["prix_revente"].native_value == 0.13
    assert e["prix_revente"]._attr_native_unit_of_measurement == "EUR/kWh"
    assert e["prix_actuel"].extra_state_attributes["prix_revente"] == 0.13


def test_prix_revente_par_grille():
    HORLOGE[0] = datetime(2026, 11, 24, 10, 0, tzinfo=TZ)
    versions = [
        {"date_effet": None, "config": dict(HPHC, prix_revente=0.10)},
        {"date_effet": "2026-06-01", "config": dict(HPHC)},  # champ vidé ensuite
        {"date_effet": "2027-02-01", "config": dict(HPHC, prix_revente=0.04)},
    ]
    g = gestionnaire(HPHC, options={"versions": versions})
    e = entites(g)
    assert "prix_revente" in e and e["prix_revente"].native_value is None  # unknown : la grille en cours n'en a pas
    lignes = asyncio.run(_prix_passes(g, datetime(2026, 5, 31, 23, 0, tzinfo=TZ), datetime(2026, 6, 1, 1, 0, tzinfo=TZ)))
    assert [l["prix_revente"] for l in lignes["heures"]] == [0.10, None]


# ------------------------------------------------------------------ v1.2.0 : service prix_passes
async def _prix_passes(g, debut, fin):
    async def executeur(fn, *args):
        return fn(*args)

    g.hass.async_add_executor_job = executeur
    return await g.async_prix_passes(debut, fin)


def test_prix_passes_heures_contigues_et_champs():
    HORLOGE[0] = datetime(2026, 11, 24, 10, 0, tzinfo=TZ)
    g = gestionnaire(dict(HPHC, prix_revente=0.13))
    r = asyncio.run(_prix_passes(g, datetime(2026, 11, 23, 21, 30, tzinfo=TZ), datetime(2026, 11, 24, 2, 0, tzinfo=TZ)))
    assert r["version_interface"] == 1
    assert set(r["derniere_modification"]) == {"quand", "depuis"}
    h = r["heures"]
    assert [datetime.fromisoformat(x["debut"]).hour for x in h] == [21, 22, 23, 0, 1]  # début arrondi à l'heure
    for a, b in zip(h, h[1:]):
        assert datetime.fromisoformat(b["debut"]) - datetime.fromisoformat(a["debut"]) == timedelta(hours=1)
    for x in h:
        assert set(x) == {"debut", "prix", "prix_revente", "periode", "couleur", "jour_special"}
        assert x["prix_revente"] == 0.13
    assert (h[0]["periode"], h[0]["prix"]) == ("hp", 0.30638)
    assert (h[3]["periode"], h[3]["prix"]) == ("hc", 0.1729)


def test_prix_passes_demi_heure_et_tempo():
    HORLOGE[0] = datetime(2026, 11, 24, 10, 0, tzinfo=TZ)
    g = gestionnaire(dict(HPHC, plages_hc="23:30-06:00"))
    h = asyncio.run(_prix_passes(g, datetime(2026, 11, 23, 23, 0, tzinfo=TZ), datetime(2026, 11, 24, 0, 0, tzinfo=TZ)))["heures"]
    assert abs(h[0]["prix"] - (0.30638 + 0.1729) / 2) < 1e-5, h  # 23:00 → 00:00 : moitié HP, moitié HC
    # Tempo : chaque heure au prix de sa couleur, d'après le journal tenu par l'intégration
    g = gestionnaire(TEMPO)
    g.journal["tempo"] = {"2026-11-20": "rouge", "2026-11-21": "bleu"}
    h = asyncio.run(_prix_passes(g, datetime(2026, 11, 20, 12, 0, tzinfo=TZ), datetime(2026, 11, 21, 12, 0, tzinfo=TZ)))["heures"]
    midi_rouge = next(x for x in h if datetime.fromisoformat(x["debut"]).hour == 12)
    assert (midi_rouge["couleur"], midi_rouge["prix"]) == ("rouge", 0.70)
    nuit = next(x for x in h if datetime.fromisoformat(x["debut"]).hour == 23)
    assert nuit["couleur"] == "rouge" and nuit["prix"] == 0.16  # la journée Tempo va de 6 h à 6 h
    matin = next(x for x in h if datetime.fromisoformat(x["debut"]).hour == 7)
    assert (matin["couleur"], matin["prix"]) == ("bleu", 0.16)


def test_prix_passes_dynamique_sans_historique():
    g = gestionnaire({"fournisseur": "Sobry", "offre": "x", "type_offre": "dynamique", "dyn_source": "sensor.absent"})
    h = asyncio.run(_prix_passes(g, datetime(2026, 11, 23, 0, 0, tzinfo=TZ), datetime(2026, 11, 23, 3, 0, tzinfo=TZ)))["heures"]
    assert [x["prix"] for x in h] == [None, None, None]  # jamais de prix deviné


def test_derniere_modification_des_grilles():
    from te.prix_passes import derniere_modification, signatures

    maintenant = datetime(2026, 11, 24, 10, 0, tzinfo=TZ)
    v1 = [{"date_effet": None, "config": dict(HPHC)}]
    etat = derniere_modification(None, signatures(v1), maintenant)
    assert (etat["quand"], etat["depuis"]) == (None, None)  # première installation : rien de modifié
    # Nouvelle grille au 01/02/2027
    v2 = v1 + [{"date_effet": "2027-02-01", "config": dict(HPHC, prix_hp=0.315)}]
    etat = derniere_modification(etat, signatures(v2), maintenant)
    assert (etat["quand"], etat["depuis"]) == (maintenant.isoformat(), "2027-02-01")
    # Correction d'une grille passée, datée du 01/08/2026
    v3 = [v1[0], {"date_effet": "2026-08-01", "config": dict(HPHC, prix_hc=0.18)}, v2[1]]
    plus_tard = maintenant + timedelta(days=1)
    etat = derniere_modification(etat, signatures(v3), plus_tard)
    assert (etat["quand"], etat["depuis"]) == (plus_tard.isoformat(), "2026-08-01")
    # Suivi de consommation modifié seul : pas une modification de grille
    v4 = [dict(v, config=dict(v["config"], compteur="sensor.autre")) for v in v3]
    assert derniere_modification(etat, signatures(v4), plus_tard + timedelta(days=1))["quand"] == plus_tard.isoformat()


# ------------------------------------------------------------------ indépendance
def test_aucune_reference_aux_autres_projets():
    interdits = re.compile(r"zendure|batterie|battery|chef d.orchestre|orchestre|solarflow", re.I)
    fichiers = [p for p in BASE.rglob("*") if p.suffix in {".py", ".json", ".js", ".yaml"}]
    for p in fichiers:
        assert not interdits.search(p.read_text(encoding="utf-8")), p
    manifest = json.load(open(BASE / "manifest.json"))
    deps = manifest.get("dependencies", []) + manifest.get("after_dependencies", [])
    assert set(deps) <= {"http", "frontend", "recorder"}, deps


def test_changelog_annonce_les_changements_d_interface():
    """La rubrique « Interface » de la 1.1.0 annonce le passage des périodes en minuscules."""
    texte = (RACINE / "CHANGELOG.md").read_text(encoding="utf-8")
    version = texte.split("## 1.1.0", 1)[1].split("\n## ", 1)[0]
    interface = version.split("### Interface", 1)[1].split("\n### ", 1)[0]
    assert "minuscules" in interface and "`previsions`" in interface and "`HP`" in interface, interface


if __name__ == "__main__":
    for nom, fn in list(globals().items()):
        if nom.startswith("test_"):
            fn()
            print("ok", nom)
