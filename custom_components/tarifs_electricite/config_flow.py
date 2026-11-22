"""Configuration guidée du contrat.

Création : modèle d'offre → contrat → prix/plages → calendrier → (week-end)
→ (été) → (jours spéciaux). Seules les étapes utiles à l'offre choisie sont
montrées. Le bouton « Configurer » reprend les mêmes étapes, pré-remplies.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import DOMAIN
from .modeles import MODELES
from .suivi_ha import lire_reglages_suivi
from .tariff import (
    COULEURS,
    JOUR_COMME_WE,
    JOUR_HC,
    JOUR_IDENTIQUE,
    JOUR_PRIX_WE,
    MOIS_HIVER_DEFAUT,
    OFFRE_BASE,
    OFFRE_DYN,
    OFFRE_HPHC,
    OFFRE_TEMPO,
    OFFRES,
    PlageInvalide,
    parse_plages,
    trier_versions,
    versions_depuis,
)
from homeassistant.util import dt as dt_util


def _nombre(mini, maxi, pas, unite):
    return NumberSelector(NumberSelectorConfig(
        min=mini, max=maxi, step=pas, mode=NumberSelectorMode.BOX, unit_of_measurement=unite))


# Home Assistant refuse un pas inférieur à 0,001 : « any » accepte toutes les décimales
# (les prix au kWh en ont souvent 4 ou 5)
PRIX = _nombre(0, 10, "any", "€/kWh")
MAJORATION = _nombre(-1, 1, "any", "€/kWh")
EUROS = _nombre(0, 1000, 0.01, "€/mois")
KVA = _nombre(1, 36, 1, "kVA")
HEURE = _nombre(0, 23, 1, "h")
TEXTE = TextSelector()
OUI_NON = BooleanSelector()
ENTITE = EntitySelector()
# Filtres au format « filter » (les clés domain/device_class à la racine sont l'ancien format)
ENTITE_PRIX = EntitySelector(EntitySelectorConfig(filter=[{"domain": ["sensor", "input_number"]}]))
ENTITE_COMPTEUR = EntitySelector(
    EntitySelectorConfig(filter=[{"domain": "sensor", "device_class": "energy"}])
)


def _liste(options: list[str], cle_trad: str, multiple: bool = False, liste: bool = False):
    return SelectSelector(SelectSelectorConfig(
        options=options, translation_key=cle_trad, multiple=multiple,
        mode=SelectSelectorMode.LIST if liste else SelectSelectorMode.DROPDOWN))


MODELE = _liste(list(MODELES), "modele")
TYPES = _liste(OFFRES, "type_offre", liste=True)
JOURS_SEMAINE = _liste(["0", "1", "2", "3", "4"], "jour_semaine", multiple=True)
# Libellés traduits par Home Assistant (strings.json → selector)
MOIS = _liste([str(m) for m in range(1, 13)], "mois", multiple=True)
PRELEVEMENTS = _liste(["12", "11", "10"], "prelevements")

# (clé, sélecteur, obligatoire, valeur par défaut)
Champ = tuple[str, Any, bool, Any]


def _plages_ok(saisie: dict, cles: list[str]) -> dict[str, str]:
    erreurs = {}
    for cle in cles:
        try:
            parse_plages(saisie.get(cle))
        except PlageInvalide:
            erreurs[cle] = "plages_invalides"
    return erreurs


def _verif_plages(suffixe: str = "") -> Callable[[dict], dict]:
    def verifier(s: dict) -> dict:
        e = _plages_ok(s, [f"plages_hc{suffixe}", f"plages_hsc{suffixe}", f"plages_perso{suffixe}"])
        if s.get(f"plages_hsc{suffixe}") and s.get(f"prix_hsc{suffixe}") is None:
            e[f"prix_hsc{suffixe}"] = "prix_manquant"
        if s.get(f"plages_perso{suffixe}") and s.get(f"prix_perso{suffixe}") is None:
            e[f"prix_perso{suffixe}"] = "prix_manquant"
        return e
    return verifier


MODE_PAIEMENT = _liste(["mensualites", "conso_reelle"], "mode_paiement", liste=True)
FREQUENCE = _liste(["1", "2", "3", "6", "12"], "frequence")


def _champs_suivi() -> list:
    return [
        ("compteur", ENTITE_COMPTEUR, False, None),
        ("mode_paiement", MODE_PAIEMENT, True, "mensualites"),
    ]


def _champs_paiement(mode: str) -> list:
    if mode == "conso_reelle":
        return [
            ("frequence_mois", FREQUENCE, True, "2"),
            ("date_debut_facturation", DateSelector(), False, None),
        ]
    return [
        ("mensualite_fournisseur", EUROS, False, None),
        ("prelevements_par_an", PRELEVEMENTS, False, "12"),
        ("date_debut_facturation", DateSelector(), False, None),
    ]


def _etape_paiement(mode: str) -> str:
    return "paiement_reel" if mode == "conso_reelle" else "paiement_mensualites"


class _Etapes:
    """Étapes communes à la création et à la modification."""

    valeurs: dict[str, Any]
    AVEC_SUIVI = False  # l'étape « suivi » termine la création ; en modification, elle a son menu

    async def _terminer(self) -> ConfigFlowResult:  # pragma: no cover - surchargé
        raise NotImplementedError

    # ------------------------------------------------------------ mécanique
    def _sequence(self) -> list[str]:
        v = self.valeurs
        t = v.get("type_offre")
        if t == OFFRE_TEMPO:
            seq = ["contrat", "tempo"]
        elif t == OFFRE_DYN:
            seq = ["contrat", "dynamique"]
        else:
            seq = ["contrat", "prix_base" if t == OFFRE_BASE else "plages", "calendrier"]
            if v.get("weekend") == JOUR_PRIX_WE:
                seq.append("weekend")
            if v.get("saisons"):
                seq.append("ete")
            if v.get("jours_speciaux"):
                seq.append("jours_speciaux")
        if self.AVEC_SUIVI:
            seq.append("suivi")
            if v.get("compteur"):
                seq.append(_etape_paiement(v.get("mode_paiement", "mensualites")))
        return seq

    async def _suivant(self, etape: str) -> ConfigFlowResult:
        seq = self._sequence()
        i = seq.index(etape)
        if i + 1 < len(seq):
            return await getattr(self, f"async_step_{seq[i + 1]}")()
        return await self._terminer()

    async def _etape(
        self,
        etape: str,
        champs: list[Champ],
        saisie: Optional[dict],
        verifier: Optional[Callable[[dict], dict]] = None,
    ) -> ConfigFlowResult:
        erreurs: dict[str, str] = {}
        if saisie is not None:
            erreurs = verifier(saisie) if verifier else {}
            if not erreurs:
                for cle, _sel, requis, _def in champs:
                    if not requis and cle not in saisie:
                        self.valeurs.pop(cle, None)
                self.valeurs.update(saisie)
                return await self._suivant(etape)
        v = {**self.valeurs, **(saisie or {})}
        schema: dict = {}
        for cle, sel, requis, defaut in champs:
            val = v.get(cle, defaut)
            desc = {"suggested_value": val} if val is not None else None
            schema[(vol.Required if requis else vol.Optional)(cle, description=desc)] = sel
        return self.async_show_form(
            step_id=etape,
            data_schema=vol.Schema(schema),
            errors=erreurs,
            description_placeholders={
                "fournisseur": v.get("fournisseur", ""),
                "offre": v.get("offre", ""),
            },
        )

    # ------------------------------------------------------------ étapes
    async def async_step_contrat(self, saisie=None) -> ConfigFlowResult:
        return await self._etape("contrat", [
            ("fournisseur", TEXTE, True, None),
            ("offre", TEXTE, True, None),
            ("type_offre", TYPES, True, OFFRE_HPHC),
            ("abonnement_mensuel", EUROS, False, None),
            ("puissance_kva", KVA, False, None),
        ], saisie)

    async def async_step_prix_base(self, saisie=None) -> ConfigFlowResult:
        return await self._etape("prix_base", [("prix_base", PRIX, True, None)], saisie)

    async def async_step_plages(self, saisie=None) -> ConfigFlowResult:
        return await self._etape("plages", [
            ("plages_hc", TEXTE, True, None),
            ("prix_hp", PRIX, True, None),
            ("prix_hc", PRIX, True, None),
            ("plages_hsc", TEXTE, False, None),
            ("prix_hsc", PRIX, False, None),
            ("perso_nom", TEXTE, False, None),
            ("plages_perso", TEXTE, False, None),
            ("prix_perso", PRIX, False, None),
            ("perso_creuse", OUI_NON, True, True),
        ], saisie, _verif_plages())

    async def async_step_calendrier(self, saisie=None) -> ConfigFlowResult:
        hphc = self.valeurs.get("type_offre") == OFFRE_HPHC
        we = [JOUR_IDENTIQUE, JOUR_HC, JOUR_PRIX_WE] if hphc else [JOUR_IDENTIQUE, JOUR_PRIX_WE]
        fe = [JOUR_IDENTIQUE, JOUR_HC, JOUR_COMME_WE] if hphc else [JOUR_IDENTIQUE, JOUR_COMME_WE]
        return await self._etape("calendrier", [
            ("weekend", _liste(we, "jour"), True, JOUR_IDENTIQUE),
            ("feries", _liste(fe, "jour"), True, JOUR_IDENTIQUE),
            ("jours_extra", JOURS_SEMAINE, False, None),
            ("alsace_moselle", OUI_NON, True, False),
            ("saisons", OUI_NON, True, False),
            ("jours_speciaux", OUI_NON, True, False),
        ], saisie)

    async def async_step_weekend(self, saisie=None) -> ConfigFlowResult:
        champs: list[Champ] = [("prix_weekend", PRIX, True, None)]
        if self.valeurs.get("type_offre") == OFFRE_HPHC:
            champs.append(("prix_weekend_hc", PRIX, False, None))
        return await self._etape("weekend", champs, saisie)

    async def async_step_ete(self, saisie=None) -> ConfigFlowResult:
        mois_defaut = [str(m) for m in self.valeurs.get("mois_hiver", MOIS_HIVER_DEFAUT)]
        champs: list[Champ] = [("mois_hiver", MOIS, True, mois_defaut)]
        if self.valeurs.get("type_offre") == OFFRE_BASE:
            champs.append(("prix_base_ete", PRIX, True, None))
            verif = None
        else:
            v = self.valeurs
            champs += [
                ("plages_hc_ete", TEXTE, True, v.get("plages_hc")),
                ("prix_hp_ete", PRIX, True, None),
                ("prix_hc_ete", PRIX, True, None),
                ("plages_hsc_ete", TEXTE, False, v.get("plages_hsc")),
                ("prix_hsc_ete", PRIX, False, None),
                ("plages_perso_ete", TEXTE, False, v.get("plages_perso")),
                ("prix_perso_ete", PRIX, False, None),
            ]
            verif = _verif_plages("_ete")

        def verifier(s: dict) -> dict:
            e = verif(s) if verif else {}
            if not s.get("mois_hiver"):
                e["mois_hiver"] = "mois_manquants"
            return e

        return await self._etape("ete", champs, saisie, verifier)

    async def async_step_jours_speciaux(self, saisie=None) -> ConfigFlowResult:
        hphc = self.valeurs.get("type_offre") == OFFRE_HPHC
        champs: list[Champ] = [("js_debut_h", HEURE, True, 0)]
        for n in (1, 2):
            requis = n == 1
            champs.append((f"js{n}_nom", TEXTE, requis, None))
            if hphc:
                champs += [(f"js{n}_prix_hp", PRIX, requis, None), (f"js{n}_prix_hc", PRIX, requis, None)]
            else:
                champs.append((f"js{n}_prix", PRIX, requis, None))
            champs += [
                (f"js{n}_source", ENTITE, False, None),
                (f"js{n}_valeur", TEXTE, False, None),
                (f"js{n}_source_demain", ENTITE, False, None),
            ]

        def verifier(s: dict) -> dict:
            e = {}
            if s.get("js2_nom"):
                cles = ["js2_prix_hp", "js2_prix_hc"] if hphc else ["js2_prix"]
                for c in cles:
                    if s.get(c) is None:
                        e[c] = "prix_manquant"
                if s["js2_nom"].strip().lower() == str(s.get("js1_nom", "")).strip().lower():
                    e["js2_nom"] = "nom_identique"
            return e

        return await self._etape("jours_speciaux", champs, saisie, verifier)

    async def async_step_tempo(self, saisie=None) -> ConfigFlowResult:
        champs: list[Champ] = [("plages_hc", TEXTE, True, "22:00-06:00")]
        for c in COULEURS:
            champs += [(f"prix_{c}_hp", PRIX, True, None), (f"prix_{c}_hc", PRIX, True, None)]
        return await self._etape(
            "tempo", champs, saisie, lambda s: _plages_ok(s, ["plages_hc"])
        )

    async def async_step_dynamique(self, saisie=None) -> ConfigFlowResult:
        return await self._etape("dynamique", [
            ("dyn_source", ENTITE_PRIX, True, None),
            ("dyn_majoration", MAJORATION, False, None),
        ], saisie)


class TarifsElectriciteConfigFlow(_Etapes, ConfigFlow, domain=DOMAIN):
    VERSION = 1
    AVEC_SUIVI = True

    async def async_step_suivi(self, saisie=None) -> ConfigFlowResult:
        return await self._etape("suivi", _champs_suivi(), saisie)

    async def async_step_paiement_mensualites(self, saisie=None) -> ConfigFlowResult:
        return await self._etape("paiement_mensualites", _champs_paiement("mensualites"), saisie)

    async def async_step_paiement_reel(self, saisie=None) -> ConfigFlowResult:
        return await self._etape("paiement_reel", _champs_paiement("conso_reelle"), saisie)

    def __init__(self) -> None:
        self.valeurs = {}

    async def async_step_user(self, saisie=None) -> ConfigFlowResult:
        """Première étape : partir d'un modèle d'offre (ou de zéro)."""
        if saisie is not None:
            self.valeurs = dict(MODELES.get(saisie["modele"], {}))
            return await self.async_step_contrat()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("modele", default="personnalise"): MODELE}),
        )

    async def _terminer(self) -> ConfigFlowResult:
        titre = f"{self.valeurs['fournisseur']} – {self.valeurs['offre']}"
        return self.async_create_entry(title=titre, data=self.valeurs)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TarifsElectriciteOptionsFlow()


MODE_MODIF = _liste(["evolution", "correction"], "mode_modif", liste=True)


def _nom_version(v: dict) -> str:
    """Libellé neutre (sans langue) : date d'effet, ou « … » pour la grille d'origine."""
    d = v.get("date_effet")
    quand = f"{d[8:10]}/{d[5:7]}/{d[:4]}" if d else "…"
    cfg = v["config"]
    return f"{quand} – {cfg.get('fournisseur', '')} {cfg.get('offre', '')}".strip()


class TarifsElectriciteOptionsFlow(_Etapes, OptionsFlow):
    """Nouvelle grille (avec date d'effet), correction, ou suppression d'une grille."""

    versions: list[dict]

    async def async_step_init(self, saisie=None) -> ConfigFlowResult:
        self.versions = trier_versions(
            versions_depuis(self.config_entry.data, self.config_entry.options)
        )
        menu = ["nouveaux_prix", "puissance", "suivi"]
        if len(self.versions) > 1:
            menu.append("supprimer_version")
        return self.async_show_menu(step_id="init", menu_options=menu)

    async def async_step_puissance(self, saisie=None) -> ConfigFlowResult:
        """Puissance souscrite seule, sans repasser par tout le contrat.

        Elle s'applique à la grille en cours et aux grilles à venir ; les
        grilles passées gardent la leur dans l'historique.
        """
        aujourdhui = dt_util.now().date().isoformat()
        actif = 0
        for i, v in enumerate(self.versions):
            if not v.get("date_effet") or v["date_effet"] <= aujourdhui:
                actif = i
        if saisie is not None:
            for v in self.versions[actif:]:
                cfg = dict(v["config"])
                if saisie.get("puissance_kva"):
                    cfg["puissance_kva"] = saisie["puissance_kva"]
                else:
                    cfg.pop("puissance_kva", None)
                v["config"] = cfg
            return self._enregistrer()
        valeur = self.versions[actif]["config"].get("puissance_kva")
        schema = vol.Schema({
            vol.Optional("puissance_kva", description={"suggested_value": valeur} if valeur else None): KVA
        })
        return self.async_show_form(step_id="puissance", data_schema=schema)

    async def async_step_nouveaux_prix(self, saisie=None) -> ConfigFlowResult:
        # On part de la grille la plus récente (éventuellement une évolution prévue)
        self.valeurs = dict(self.versions[-1]["config"])
        return await self.async_step_contrat()

    def _formulaire_suivi(self, etape: str, champs: list, valeurs: dict) -> ConfigFlowResult:
        schema = {}
        for cle, sel, requis, defaut in champs:
            val = valeurs.get(cle, defaut)
            desc = {"suggested_value": val} if val is not None else None
            schema[(vol.Required if requis else vol.Optional)(cle, description=desc)] = sel
        return self.async_show_form(step_id=etape, data_schema=vol.Schema(schema))

    async def async_step_suivi(self, saisie=None) -> ConfigFlowResult:
        actuel = lire_reglages_suivi(self.config_entry.data, self.config_entry.options)
        if saisie is not None:
            if not saisie.get("compteur"):
                return self._enregistrer({})  # suivi désactivé
            self.suivi_saisie = {**actuel, **saisie}
            return await getattr(self, f"async_step_{_etape_paiement(saisie['mode_paiement'])}")()
        if actuel.get("compteur") and not actuel.get("mode_paiement"):
            actuel["mode_paiement"] = "mensualites" if actuel.get("mensualite_fournisseur") else "conso_reelle"
        return self._formulaire_suivi("suivi", _champs_suivi(), actuel)

    async def _paiement(self, mode: str, saisie) -> ConfigFlowResult:
        champs = _champs_paiement(mode)
        if saisie is not None:
            garder = ["compteur", "mode_paiement"] + [c[0] for c in champs]
            final = {k: v for k, v in {**self.suivi_saisie, **saisie}.items()
                     if k in garder and v not in (None, "")}
            for cle, _sel, requis, _d in champs:  # champ vidé par l'utilisateur
                if not requis and cle not in saisie:
                    final.pop(cle, None)
            return self._enregistrer(final)
        return self._formulaire_suivi(_etape_paiement(mode), champs, self.suivi_saisie)

    async def async_step_paiement_mensualites(self, saisie=None) -> ConfigFlowResult:
        return await self._paiement("mensualites", saisie)

    async def async_step_paiement_reel(self, saisie=None) -> ConfigFlowResult:
        return await self._paiement("conso_reelle", saisie)

    async def _terminer(self) -> ConfigFlowResult:
        return await self.async_step_date_effet()

    async def async_step_date_effet(self, saisie=None) -> ConfigFlowResult:
        aujourdhui = dt_util.now().date().isoformat()
        if saisie is not None:
            if saisie["mode"] == "correction":
                self.versions[-1] = {**self.versions[-1], "config": self.valeurs}
            else:
                d = saisie.get("date_effet") or aujourdhui
                self.versions = [v for v in self.versions if v.get("date_effet") != d]
                self.versions.append({"date_effet": d, "config": self.valeurs})
            return self._enregistrer()
        schema = vol.Schema({
            vol.Required("mode", default="evolution"): MODE_MODIF,
            vol.Optional("date_effet", description={"suggested_value": aujourdhui}): DateSelector(),
        })
        return self.async_show_form(
            step_id="date_effet",
            data_schema=schema,
            description_placeholders={"grille": _nom_version(self.versions[-1])},
        )

    async def async_step_supprimer_version(self, saisie=None) -> ConfigFlowResult:
        if saisie is not None:
            del self.versions[int(saisie["version"])]
            return self._enregistrer()
        choix = SelectSelector(SelectSelectorConfig(
            options=[SelectOptionDict(value=str(i), label=_nom_version(v))
                     for i, v in enumerate(self.versions)],
            mode=SelectSelectorMode.LIST,
        ))
        return self.async_show_form(
            step_id="supprimer_version",
            data_schema=vol.Schema({vol.Required("version", default=str(len(self.versions) - 1)): choix}),
        )

    def _enregistrer(self, suivi: Optional[dict] = None) -> ConfigFlowResult:
        self.versions = trier_versions(self.versions)
        cfg = self.versions[-1]["config"]
        titre = f"{cfg['fournisseur']} – {cfg['offre']}"
        if titre != self.config_entry.title:
            self.hass.config_entries.async_update_entry(self.config_entry, title=titre)
        if suivi is None:
            suivi = lire_reglages_suivi(self.config_entry.data, self.config_entry.options)
        return self.async_create_entry(title="", data={"versions": self.versions, "suivi": suivi})
