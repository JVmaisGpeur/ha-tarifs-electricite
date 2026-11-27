"""Carte : chaque section a son bouton « i », avec un texte en français et en anglais (v1.2.0)."""

import pathlib
import re

CARTE = pathlib.Path(__file__).resolve().parents[1] / "custom_components" / "tarifs_electricite" / "www" / "tarifs-electricite-card.js"


def _bloc_aide(js: str, langue: str) -> str:
    debut = js.index("aide: {", js.index(f"  {langue}: {{"))
    niveau = 0
    for i in range(debut + len("aide: "), len(js)):
        if js[i] == "{":
            niveau += 1
        elif js[i] == "}":
            niveau -= 1
            if niveau == 0:
                return js[debut:i + 1]
    raise AssertionError(langue)


def test_chaque_section_a_son_aide_dans_les_deux_langues():
    js = CARTE.read_text(encoding="utf-8")
    cles = re.findall(r'"(\w+)"', re.search(r"const AIDE_CLES = \[([^\]]*)\]", js).group(1))
    assert len(cles) >= 8
    for langue in ("fr", "en"):
        trouvees = set(re.findall(r"^\s*(\w+):\s*\"", _bloc_aide(js, langue), re.M))
        assert trouvees == set(cles), (langue, set(cles) ^ trouvees)
    utilisees = set(re.findall(r'o\.ib\("(\w+)"\)', js))
    assert utilisees == set(cles), set(cles) ^ utilisees
