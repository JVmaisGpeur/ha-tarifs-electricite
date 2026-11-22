"""Parcours complet des écrans de configuration, avec un Home Assistant simulé.

Vérifie l'enchaînement des étapes et les données enregistrées, sans installer
Home Assistant.
"""

import asyncio
import importlib.util
import pathlib
import sys
import types
from datetime import datetime, timedelta, timezone

TZ = timezone(timedelta(hours=1))


def mod(nom, **attrs):
    m = types.ModuleType(nom)
    m.__dict__.update(attrs)
    sys.modules[nom] = m
    return m


class Champ:
    """vol.Required / vol.Optional simulés : gardent la clé, le défaut et la suggestion."""

    def __init__(self, cle, default=None, description=None):
        self.cle, self.defaut, self.description = cle, default, description or {}
        self.requis = isinstance(self, Requis)

    def __hash__(self):
        return hash(self.cle)


class Requis(Champ):
    pass


class Schema:
    def __init__(self, champs):
        self.champs = champs


class Rien:
    def __init__(self, *a, **k):
        self.args, self.kwargs = a, k

    def __call__(self, *a, **k):
        return self


mod("voluptuous", Schema=Schema, Optional=Champ, Required=Requis, All=Rien, Coerce=Rien, Range=Rien)
mod("aiohttp", ClientSession=object, ClientError=Exception, ClientTimeout=Rien)
mod("homeassistant")
mod("homeassistant.helpers")
mod("homeassistant.util")


class FlowHandler:
    def async_show_form(self, step_id, data_schema=None, errors=None, description_placeholders=None):
        return {"type": "form", "step_id": step_id, "schema": data_schema, "errors": errors or {}}

    def async_show_menu(self, step_id, menu_options):
        return {"type": "menu", "step_id": step_id, "menu_options": menu_options}

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}


class ConfigFlow(FlowHandler):
    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.DOMAIN = domain


class OptionsFlow(FlowHandler):
    pass


mod("homeassistant.config_entries", ConfigEntry=object, ConfigFlow=ConfigFlow,
    ConfigFlowResult=dict, OptionsFlow=OptionsFlow)
mod("homeassistant.const", STATE_UNAVAILABLE="unavailable", STATE_UNKNOWN="unknown",
    Platform=types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor", SELECT="select"))
mod("homeassistant.core", HomeAssistant=object, ServiceCall=object, ServiceResponse=dict,
    SupportsResponse=types.SimpleNamespace(ONLY="only"), callback=lambda f: f)
mod("homeassistant.exceptions", ServiceValidationError=Exception)
mod("homeassistant.helpers.config_validation", config_entry_only_config_schema=lambda d: None, string=str)
mod("homeassistant.helpers.aiohttp_client", async_get_clientsession=lambda h: None)
mod("homeassistant.helpers.dispatcher", async_dispatcher_send=lambda h, s: None)
mod("homeassistant.helpers.event", async_track_point_in_time=lambda *a: (lambda: None),
    async_track_state_change_event=lambda *a: (lambda: None),
    async_track_time_interval=lambda *a: (lambda: None),
    async_call_later=lambda *a: (lambda: None), async_track_time_change=lambda *a, **k: (lambda: None))
mod("homeassistant.helpers.storage", Store=Rien)
mod("homeassistant.helpers.typing", ConfigType=dict)
mod("homeassistant.helpers.selector", **{n: Rien for n in (
    "BooleanSelector", "DateSelector", "EntitySelector", "EntitySelectorConfig", "NumberSelector",
    "NumberSelectorConfig", "SelectSelector", "SelectSelectorConfig", "TextSelector")},
    NumberSelectorMode=types.SimpleNamespace(BOX="box"),
    SelectSelectorMode=types.SimpleNamespace(LIST="list", DROPDOWN="dropdown"),
    SelectOptionDict=dict)
mod("homeassistant.util.dt", now=lambda: datetime(2026, 11, 22, 17, 0, tzinfo=TZ),
    as_local=lambda d: d, utc_from_timestamp=lambda ts: datetime.fromtimestamp(ts, timezone.utc),
    utcnow=lambda: datetime(2026, 11, 22, 16, 0, tzinfo=timezone.utc))
sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]

base = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tarifs_electricite"
spec = importlib.util.spec_from_file_location("te", base / "__init__.py", submodule_search_locations=[str(base)])
te = importlib.util.module_from_spec(spec)
sys.modules["te"] = te
spec.loader.exec_module(te)
import te.config_flow as cf  # noqa: E402


def lancer(coro):
    return asyncio.run(coro)


def champs(res):
    return {c.cle: c for c in res["schema"].champs}


def etape(flux, res, saisie):
    """Envoie `saisie` à l'étape affichée, en vérifiant que les champs existent."""
    assert res["type"] == "form", res
    connus = champs(res)
    for cle in saisie:
        assert cle in connus, f"{cle} absent de l'étape {res['step_id']} ({list(connus)})"
    return lancer(getattr(flux, f"async_step_{res['step_id']}")(saisie))


def test_creation_enercoop_conso_reelle():
    f = cf.TarifsElectriciteConfigFlow()
    r = lancer(f.async_step_user())
    assert r["step_id"] == "user"
    r = lancer(f.async_step_user({"modele": "enercoop_nuit_weekend"}))
    assert r["step_id"] == "contrat"
    assert champs(r)["fournisseur"].description["suggested_value"] == "Enercoop"
    r = etape(f, r, {"fournisseur": "Enercoop", "offre": "Flexibilité Nuit & Week-end", "type_offre": "hphc",
                     "abonnement_mensuel": 13.41, "puissance_kva": 6})
    assert r["step_id"] == "plages"
    assert champs(r)["plages_hc"].description["suggested_value"] == "23:00-06:00"
    r = etape(f, r, {"plages_hc": "23:00-06:00", "prix_hp": 0.30638, "prix_hc": 0.1729})
    assert r["step_id"] == "calendrier"
    r = etape(f, r, {"weekend": "heures_creuses", "feries": "heures_creuses", "alsace_moselle": False,
                     "saisons": False, "jours_speciaux": False})
    assert r["step_id"] == "suivi"
    r = etape(f, r, {"compteur": "sensor.envoy_conso", "mode_paiement": "conso_reelle"})
    assert r["step_id"] == "paiement_reel"
    r = etape(f, r, {"frequence_mois": "2", "date_debut_facturation": "2026-09-15"})
    assert r["type"] == "create_entry" and r["title"] == "Enercoop – Flexibilité Nuit & Week-end"
    d = r["data"]
    assert d["compteur"] == "sensor.envoy_conso" and d["frequence_mois"] == "2"
    assert "prelevements_par_an" not in d
    return d


def test_erreur_de_plage():
    f = cf.TarifsElectriciteConfigFlow()
    lancer(f.async_step_user({"modele": "personnalise"}))
    f.valeurs.update({"fournisseur": "X", "offre": "Y", "type_offre": "hphc"})
    r = lancer(f.async_step_plages({"plages_hc": "n'importe quoi", "prix_hp": 0.3, "prix_hc": 0.2}))
    assert r["step_id"] == "plages" and r["errors"] == {"plages_hc": "plages_invalides"}
    r = lancer(f.async_step_plages({"plages_hc": "22h-6h", "prix_hp": 0.3, "prix_hc": 0.2,
                                    "plages_hsc": "02:00-05:00"}))
    assert r["errors"] == {"prix_hsc": "prix_manquant"}


def test_creation_zen_flex_toutes_etapes():
    f = cf.TarifsElectriciteConfigFlow()
    r = lancer(f.async_step_user({"modele": "edf_zen_flex"}))
    r = etape(f, r, {"fournisseur": "EDF", "offre": "Zen Flex", "type_offre": "hphc"})
    r = etape(f, r, {"plages_hc": "13:00-18:00, 20:00-08:00", "prix_hp": 0.2142, "prix_hc": 0.1595})
    assert champs(r)["jours_speciaux"].description["suggested_value"] is True
    r = etape(f, r, {"weekend": "prix_weekend", "feries": "comme_weekend", "alsace_moselle": False,
                     "saisons": True, "jours_speciaux": True})
    assert r["step_id"] == "weekend"
    r = etape(f, r, {"prix_weekend": 0.15})
    assert r["step_id"] == "ete"
    r = etape(f, r, {"mois_hiver": ["11", "12", "1", "2", "3"], "plages_hc_ete": "13:00-18:00",
                     "prix_hp_ete": 0.2, "prix_hc_ete": 0.15})
    assert r["step_id"] == "jours_speciaux"
    assert champs(r)["js_debut_h"].description["suggested_value"] == 8
    r = etape(f, r, {"js_debut_h": 8, "js1_nom": "Sobriété", "js1_prix_hp": 0.7467, "js1_prix_hc": 0.2142})
    assert r["step_id"] == "suivi"
    r = etape(f, r, {"mode_paiement": "mensualites"})  # pas de compteur : fin
    assert r["type"] == "create_entry"


def test_creation_tempo_et_dynamique():
    for modele, etape_prix, saisie in (
        ("edf_tempo", "tempo", {"plages_hc": "22:00-06:00", **{f"prix_{c}_{p}": 0.1 for c in ("bleu", "blanc", "rouge") for p in ("hp", "hc")}}),
        ("sobry", "dynamique", {"dyn_source": "sensor.sobry_prix"}),
    ):
        f = cf.TarifsElectriciteConfigFlow()
        r = lancer(f.async_step_user({"modele": modele}))
        r = etape(f, r, {"fournisseur": "F", "offre": "O", "type_offre": f.valeurs["type_offre"]})
        assert r["step_id"] == etape_prix
        r = etape(f, r, saisie)
        assert r["step_id"] == "suivi"
        r = etape(f, r, {"mode_paiement": "mensualites"})
        assert r["type"] == "create_entry"


def _options(data, options=None):
    o = cf.TarifsElectriciteOptionsFlow()
    o.config_entry = types.SimpleNamespace(data=data, options=options or {}, title="Enercoop – Flexibilité Nuit & Week-end")
    o.hass = types.SimpleNamespace(config_entries=types.SimpleNamespace(async_update_entry=lambda *a, **k: None))
    return o


def test_modification_evolution_puis_suivi_puis_suppression():
    data = test_creation_enercoop_conso_reelle()
    o = _options(data)
    r = lancer(o.async_step_init())
    assert r["type"] == "menu" and r["menu_options"] == ["nouveaux_prix", "suivi"]
    r = lancer(o.async_step_nouveaux_prix())
    assert r["step_id"] == "contrat"
    assert champs(r)["fournisseur"].description["suggested_value"] == "Enercoop"
    r = etape(o, r, {"fournisseur": "Enercoop", "offre": "Flexibilité Nuit & Week-end", "type_offre": "hphc",
                     "abonnement_mensuel": 13.8, "puissance_kva": 6})
    r = etape(o, r, {"plages_hc": "23:00-06:00", "prix_hp": 0.3150, "prix_hc": 0.1780})
    r = etape(o, r, {"weekend": "heures_creuses", "feries": "heures_creuses", "alsace_moselle": False,
                     "saisons": False, "jours_speciaux": False})
    assert r["step_id"] == "date_effet", r
    r = etape(o, r, {"mode": "evolution", "date_effet": "2027-02-01"})
    assert r["type"] == "create_entry"
    opts = r["data"]
    assert [v["date_effet"] for v in opts["versions"]] == [None, "2027-02-01"]
    assert opts["versions"][1]["config"]["prix_hp"] == 0.3150
    assert opts["suivi"]["compteur"] == "sensor.envoy_conso"

    # Suivi : passage en mensualités
    o = _options(data, opts)
    r = lancer(o.async_step_init())
    assert r["menu_options"] == ["nouveaux_prix", "suivi", "supprimer_version"]
    r = lancer(o.async_step_suivi())
    assert champs(r)["mode_paiement"].description["suggested_value"] == "conso_reelle"
    r = etape(o, r, {"compteur": "sensor.envoy_conso", "mode_paiement": "mensualites"})
    assert r["step_id"] == "paiement_mensualites"
    r = etape(o, r, {"mensualite_fournisseur": 80, "prelevements_par_an": "11"})
    suivi = r["data"]["suivi"]
    assert suivi == {"compteur": "sensor.envoy_conso", "mode_paiement": "mensualites",
                     "mensualite_fournisseur": 80, "prelevements_par_an": "11"}, suivi
    assert len(r["data"]["versions"]) == 2

    # Suppression de l'évolution prévue
    o = _options(data, r["data"])
    lancer(o.async_step_init())
    r = lancer(o.async_step_supprimer_version())
    assert champs(r)["version"].defaut == "1"
    r = lancer(o.async_step_supprimer_version({"version": "1"}))
    assert len(r["data"]["versions"]) == 1 and r["data"]["suivi"]["mensualite_fournisseur"] == 80

    # Correction de la grille sans historique
    o = _options(data, r["data"])
    lancer(o.async_step_init())
    r = lancer(o.async_step_nouveaux_prix())
    for s in ({"fournisseur": "Enercoop", "offre": "Flexibilité Nuit & Week-end", "type_offre": "hphc"},
              {"plages_hc": "23:00-06:00", "prix_hp": 0.31, "prix_hc": 0.17},
              {"weekend": "heures_creuses", "feries": "heures_creuses", "alsace_moselle": False,
               "saisons": False, "jours_speciaux": False}):
        r = etape(o, r, s)
    r = etape(o, r, {"mode": "correction"})
    assert len(r["data"]["versions"]) == 1 and r["data"]["versions"][0]["config"]["prix_hp"] == 0.31

    # Désactiver le suivi
    o = _options(data, r["data"])
    lancer(o.async_step_init())
    r = lancer(o.async_step_suivi({"mode_paiement": "mensualites"}))
    assert r["data"]["suivi"] == {}


if __name__ == "__main__":
    for nom, fn in list(globals().items()):
        if nom.startswith("test_"):
            fn()
            print("ok", nom)
