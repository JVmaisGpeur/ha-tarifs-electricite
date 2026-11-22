"""Traductions : français et anglais complets, mêmes clés, mêmes paramètres."""

import json
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tarifs_electricite"


def _plat(o, chemin=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _plat(v, f"{chemin}/{k}")
    else:
        yield chemin, o


def _charger(nom):
    return dict(_plat(json.load(open(BASE / "translations" / nom, encoding="utf-8"))))


def test_memes_cles_et_parametres():
    fr, en = _charger("fr.json"), _charger("en.json")
    assert set(fr) == set(en), set(fr) ^ set(en)
    for cle in fr:
        assert fr[cle].strip() and en[cle].strip(), cle
        assert set(re.findall(r"\{\w+\}", fr[cle])) == set(re.findall(r"\{\w+\}", en[cle])), cle


def test_strings_json_est_l_anglais():
    # strings.json sert de référence : identique à en.json
    assert json.load(open(BASE / "strings.json")) == json.load(open(BASE / "translations" / "en.json"))


def test_anglais_sans_texte_francais_oublie():
    # Noms d'offres et de jours spéciaux (propres aux fournisseurs) mis à part
    propres = re.compile(r"Jours? Éclair|Jour Sérénité|Sobriété|Éclair|Sérénité|Énergie|Électricité|Flexibilité|Nuit|Heures Creuses|"
                         r"Heures Eco|Charge'Heures|Beaux Jours|Week-End|calendrier-tempo")
    mots_fr = re.compile(r"\b(les|des|une|pour|avec|heures|jour|prix|semaine|mois|année|facture|"
                         r"abonnement|creuses|pleines|votre|vous)\b", re.I)
    for cle, texte in _charger("en.json").items():
        reste = propres.sub("", texte)
        assert not mots_fr.search(reste), (cle, texte)


def test_carte_bilingue():
    carte = (BASE / "www" / "tarifs-electricite-card.js").read_text(encoding="utf-8")
    debut_fr, debut_en = carte.index("  fr: {"), carte.index("  en: {")
    fin = carte.index("function langue(")
    cles = lambda bloc: set(re.findall(r"^    (\w+):", bloc, re.M))
    fr, en = cles(carte[debut_fr:debut_en]), cles(carte[debut_en:fin])
    assert fr == en and len(fr) > 50, fr ^ en


if __name__ == "__main__":
    for nom, fn in list(globals().items()):
        if nom.startswith("test_"):
            fn()
            print("ok", nom)
