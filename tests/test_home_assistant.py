"""Chargement réel dans Home Assistant : assistant, entités, services, options.

Ignoré si Home Assistant et pytest-homeassistant-custom-component ne sont pas installés
(lancé par le job CI « home-assistant », sous Linux).
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

import voluptuous_serialize  # noqa: E402
from homeassistant import config_entries  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from homeassistant.helpers import config_validation as cv  # noqa: E402
from homeassistant.helpers import entity_registry as er  # noqa: E402
from homeassistant.setup import async_setup_component  # noqa: E402

DOMAIN = "tarifs_electricite"
REPO_COMPONENTS = str(Path(__file__).resolve().parent.parent / "custom_components")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(caplog, recorder_mock, enable_custom_integrations, hass):
    """L'historique (recorder) doit être prêt avant Home Assistant.

    L'outil de test charge son propre paquet custom_components : on y ajoute le nôtre.
    """
    import custom_components
    from homeassistant import loader

    if REPO_COMPONENTS not in list(custom_components.__path__):
        custom_components.__path__.append(REPO_COMPONENTS)
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS, None)
    yield
    _aucune_erreur(caplog)

def _aucune_erreur(caplog) -> None:
    """Une erreur consignée (même attrapée) fait échouer le test."""
    erreurs = [f"{r.name}: {r.getMessage()}" for r in caplog.get_records("call") if r.levelno >= logging.ERROR]
    assert not erreurs, erreurs



def _ecran(r, step_id: str | None = None):
    """Vérifie l'écran affiché et sérialise son formulaire comme le fait l'interface."""
    if step_id is not None:
        assert r.get("step_id") == step_id, (r.get("step_id"), r.get("errors"), r.get("reason"))
    if r["type"] is FlowResultType.FORM:
        assert not r.get("errors"), r["errors"]
        if r.get("data_schema") is not None:
            voluptuous_serialize.convert(r["data_schema"], custom_serializer=cv.custom_serializer)
    return r


async def _compteur_fictif(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.compteur_test", "1234.5", {
        "device_class": "energy", "state_class": "total_increasing", "unit_of_measurement": "kWh"})


async def _assistant_hphc(hass: HomeAssistant):
    flow = hass.config_entries.flow
    r = _ecran(await flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER}), "user")
    r = _ecran(await flow.async_configure(r["flow_id"], {"modele": "personnalise"}), "contrat")
    r = _ecran(await flow.async_configure(r["flow_id"], {
        "fournisseur": "Fournisseur", "offre": "Offre test", "type_offre": "hphc",
        "abonnement_mensuel": 15.5, "puissance_kva": 9, "prix_revente": 0.04}), "plages")
    r = _ecran(await flow.async_configure(r["flow_id"], {
        "plages_hc": "22:00-06:00", "prix_hp": 0.2516, "prix_hc": 0.19872, "perso_creuse": True}), "calendrier")
    r = _ecran(await flow.async_configure(r["flow_id"], {
        "weekend": "prix_weekend", "feries": "identique", "alsace_moselle": False,
        "saisons": True, "jours_speciaux": True}), "weekend")
    r = _ecran(await flow.async_configure(r["flow_id"], {"prix_weekend": 0.18, "prix_weekend_hc": 0.15}), "ete")
    r = _ecran(await flow.async_configure(r["flow_id"], {
        "mois_hiver": ["11", "12", "1", "2", "3"], "plages_hc_ete": "02:00-07:00, 13:00-16:00",
        "prix_hp_ete": 0.24, "prix_hc_ete": 0.18}), "jours_speciaux")
    r = _ecran(await flow.async_configure(r["flow_id"], {
        "js_debut_h": 6, "js1_nom": "Pointe", "js1_prix_hp": 0.70, "js1_prix_hc": 0.20}), "suivi")
    r = _ecran(await flow.async_configure(r["flow_id"], {
        "compteur": "sensor.compteur_test", "mode_paiement": "mensualites"}), "paiement_mensualites")
    r = await flow.async_configure(r["flow_id"], {
        "mensualite_fournisseur": 80, "prelevements_par_an": "12", "date_debut_facturation": "2026-01-01"})
    assert r["type"] is FlowResultType.CREATE_ENTRY, r
    return r["result"]


def _entites(hass: HomeAssistant, entry) -> dict[str, str]:
    """unique_id → entity_id des entités de l'entrée."""
    reg = er.async_get(hass)
    return {e.unique_id: e.entity_id for e in er.async_entries_for_config_entry(reg, entry.entry_id)}


async def test_assistant_hphc_et_chargement(hass: HomeAssistant) -> None:
    await _compteur_fictif(hass)
    entry = await _assistant_hphc(hass)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.title == "Fournisseur – Offre test"

    ents = _entites(hass, entry)
    for cle in ("prix_actuel", "periode", "offre", "prix_revente", "cout_aujourdhui", "mensualite"):
        uid = f"{entry.entry_id}_{cle}"
        assert any(u.startswith(uid) for u in ents), (cle, sorted(ents))
    prix = hass.states.get(next(e for u, e in ents.items() if u == f"{entry.entry_id}_prix_actuel"))
    assert prix is not None and prix.state not in ("unavailable", "unknown"), prix
    assert float(prix.state) > 0

    assert hass.services.has_service(DOMAIN, "previsions")
    rep = await hass.services.async_call(DOMAIN, "previsions", {"heures": 12}, blocking=True, return_response=True)
    assert rep


async def test_options_menu(hass: HomeAssistant) -> None:
    await _compteur_fictif(hass)
    entry = await _assistant_hphc(hass)
    await hass.async_block_till_done()
    opts = hass.config_entries.options

    r = await opts.async_init(entry.entry_id)
    assert r["type"] is FlowResultType.MENU
    assert set(r["menu_options"]) >= {"nouveaux_prix", "puissance", "revente", "suivi"}

    # Chaque écran du menu s'ouvre et se sérialise
    for etape in ("puissance", "revente", "suivi"):
        r = await opts.async_init(entry.entry_id)
        _ecran(await opts.async_configure(r["flow_id"], {"next_step_id": etape}), etape)

    # Puissance souscrite seule
    r = await opts.async_init(entry.entry_id)
    r = await opts.async_configure(r["flow_id"], {"next_step_id": "puissance"})
    r = await opts.async_configure(r["flow_id"], {"puissance_kva": 12})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.options["versions"][-1]["config"]["puissance_kva"] == 12
    assert entry.state is config_entries.ConfigEntryState.LOADED

    # Nouvelle grille : reprend les étapes pré-remplies, puis la date d'effet
    r = await opts.async_init(entry.entry_id)
    r = _ecran(await opts.async_configure(r["flow_id"], {"next_step_id": "nouveaux_prix"}), "contrat")
    r = _ecran(await opts.async_configure(r["flow_id"], {
        "fournisseur": "Fournisseur", "offre": "Offre test", "type_offre": "base"}), "prix_base")
    r = _ecran(await opts.async_configure(r["flow_id"], {"prix_base": 0.2276}), "calendrier")
    r = _ecran(await opts.async_configure(r["flow_id"], {
        "weekend": "identique", "feries": "identique", "alsace_moselle": False,
        "saisons": False, "jours_speciaux": False}), "date_effet")
    r = await opts.async_configure(r["flow_id"], {"mode": "evolution", "date_effet": "2030-01-01"})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert len(entry.options["versions"]) == 2
    assert entry.state is config_entries.ConfigEntryState.LOADED

    r = await opts.async_init(entry.entry_id)
    assert "supprimer_version" in r["menu_options"]
    _ecran(await opts.async_configure(r["flow_id"], {"next_step_id": "supprimer_version"}), "supprimer_version")


async def test_assistant_tempo(hass: HomeAssistant) -> None:
    """Offre Tempo : le service des couleurs est simulé (pas de réseau en test)."""
    from custom_components.tarifs_electricite.tempo import TempoClient

    with patch.object(TempoClient, "_get", AsyncMock(return_value=None)):
        flow = hass.config_entries.flow
        r = await flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        r = _ecran(await flow.async_configure(r["flow_id"], {"modele": "edf_tempo"}), "contrat")
        r = _ecran(await flow.async_configure(r["flow_id"], {
            "fournisseur": "EDF", "offre": "Tempo", "type_offre": "tempo"}), "tempo")
        prix = {f"prix_{c}_{p}": 0.1 + i / 100 for i, (c, p) in enumerate(
            (c, p) for c in ("bleu", "blanc", "rouge") for p in ("hp", "hc"))}
        r = _ecran(await flow.async_configure(r["flow_id"], {"plages_hc": "22:00-06:00", **prix}), "suivi")
        r = await flow.async_configure(r["flow_id"], {"mode_paiement": "mensualites"})
        assert r["type"] is FlowResultType.CREATE_ENTRY, r
        entry = r["result"]
        await hass.async_block_till_done()
        assert entry.state is config_entries.ConfigEntryState.LOADED
        ents = _entites(hass, entry)
        assert f"{entry.entry_id}_tempo_aujourdhui" in ents, sorted(ents)
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


async def test_offre_a_comparer_et_puissance(hass: HomeAssistant) -> None:
    """v1.3.0 : sous-entrée « offre », capteurs du comparatif, puissance au compteur, service."""
    await _compteur_fictif(hass)
    hass.states.async_set("sensor.puissance_test", "1500", {
        "device_class": "power", "state_class": "measurement", "unit_of_measurement": "W"})
    entry = await _assistant_hphc(hass)
    await hass.async_block_till_done()
    ents = _entites(hass, entry)
    assert not any(u.endswith(("_meilleure_offre", "_puissance_conseillee")) for u in ents)  # rien sans offre

    sub = hass.config_entries.subentries
    r = _ecran(await sub.async_init((entry.entry_id, "offre"), context={"source": config_entries.SOURCE_USER}), "user")
    r = _ecran(await sub.async_configure(r["flow_id"], {"modele": "personnalise"}), "contrat")
    r = _ecran(await sub.async_configure(r["flow_id"], {"fournisseur": "Autre", "offre": "Base", "type_offre": "base"}), "prix_base")
    r = _ecran(await sub.async_configure(r["flow_id"], {"prix_base": 0.2516}), "calendrier")
    r = _ecran(await sub.async_configure(r["flow_id"], {
        "weekend": "identique", "feries": "identique", "alsace_moselle": False,
        "saisons": False, "jours_speciaux": False}), "abonnements")
    r = await sub.async_configure(r["flow_id"], {"abo_3": 9.5, "abo_6": 12.4})
    assert r["type"] is FlowResultType.CREATE_ENTRY, r
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert len(entry.subentries) == 1 and entry.state is config_entries.ConfigEntryState.LOADED
    ents = _entites(hass, entry)
    assert f"{entry.entry_id}_meilleure_offre" in ents and f"{entry.entry_id}_economie_possible" in ents, sorted(ents)

    # Puissance au compteur : Configurer → Suivi
    opts = hass.config_entries.options
    r = await opts.async_init(entry.entry_id)
    r = _ecran(await opts.async_configure(r["flow_id"], {"next_step_id": "suivi"}), "suivi")
    r = _ecran(await opts.async_configure(r["flow_id"], {
        "compteur": "sensor.compteur_test", "mode_paiement": "mensualites",
        "puissance_compteur": ["sensor.puissance_test"], "triphase": False, "depassements_toleres": 10}),
        "paiement_mensualites")
    r = await opts.async_configure(r["flow_id"], {"mensualite_fournisseur": 80, "prelevements_par_an": "12"})
    assert r["type"] is FlowResultType.CREATE_ENTRY, r
    await hass.async_block_till_done()
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry.options["suivi"]["puissance_compteur"] == ["sensor.puissance_test"]
    assert f"{entry.entry_id}_puissance_conseillee" in _entites(hass, entry)

    rep = await hass.services.async_call(DOMAIN, "comparer_offres", {
        "debut": "2026-10-01 00:00:00", "fin": "2026-11-01 00:00:00"}, blocking=True, return_response=True)
    assert rep["version_interface"] == 1 and "lignes" in rep
