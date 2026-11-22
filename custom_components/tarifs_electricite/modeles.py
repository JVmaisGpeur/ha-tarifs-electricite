"""Modèles d'offres : ils pré-remplissent la structure, jamais les prix.

Les prix changent souvent : l'utilisateur les recopie depuis sa facture ou
la grille de son fournisseur. Les plages horaires fixées par Enedis (heures
creuses « classiques ») varient selon le logement : elles restent à saisir.
"""

MODELES: dict[str, dict] = {
    "personnalise": {},
    "edf_tempo": {
        "fournisseur": "EDF", "offre": "Tempo", "type_offre": "tempo",
        "plages_hc": "22:00-06:00",
    },
    "edf_zen_week_end": {
        "fournisseur": "EDF", "offre": "Zen Week-End", "type_offre": "base",
        "weekend": "prix_weekend", "feries": "comme_weekend",
    },
    "edf_zen_week_end_hc": {
        "fournisseur": "EDF", "offre": "Zen Week-End Heures Creuses", "type_offre": "hphc",
        "weekend": "prix_weekend", "feries": "comme_weekend",
    },
    "edf_zen_week_end_plus": {
        "fournisseur": "EDF", "offre": "Zen Week-End Plus", "type_offre": "base",
        "weekend": "prix_weekend", "feries": "comme_weekend", "jours_extra": ["2"],
    },
    "edf_zen_flex": {
        "fournisseur": "EDF", "offre": "Zen Week-End option Flex", "type_offre": "hphc",
        "plages_hc": "13:00-18:00, 20:00-08:00",
        "jours_speciaux": True, "js_debut_h": 8, "js1_nom": "Sobriété",
    },
    "enercoop_nuit_weekend": {
        "fournisseur": "Enercoop", "offre": "Flexibilité Nuit & Week-end", "type_offre": "hphc",
        "plages_hc": "23:00-06:00", "weekend": "heures_creuses", "feries": "heures_creuses",
    },
    "total_charge_heures": {
        "fournisseur": "TotalEnergies", "offre": "Charge'Heures", "type_offre": "hphc",
    },
    "total_heures_eco_plus": {
        "fournisseur": "TotalEnergies", "offre": "Heures Eco+", "type_offre": "hphc",
        "jours_speciaux": True, "js1_nom": "Jour Éclair",
    },
    "octopus_go": {
        "fournisseur": "Octopus Energy", "offre": "Octopus Go", "type_offre": "hphc",
    },
    "ohm_week_end": {
        "fournisseur": "OHM Énergie", "offre": "Week-End", "type_offre": "hphc",
        "weekend": "heures_creuses", "feries": "identique",
    },
    "ohm_modulo": {
        "fournisseur": "OHM Énergie", "offre": "Modulo", "type_offre": "hphc",
        "perso_nom": "Heures solaires", "saisons": True,
        "jours_speciaux": True, "js1_nom": "Jour Sérénité",
    },
    "ohm_beaux_jours": {
        "fournisseur": "OHM Énergie", "offre": "Beaux Jours", "type_offre": "base",
        "saisons": True, "mois_hiver": ["11", "12", "1", "2", "3"],
    },
    "sobry": {"fournisseur": "Sobry", "offre": "Contrat intelligent", "type_offre": "dynamique"},
    "frank": {"fournisseur": "Frank Énergie", "offre": "Contrat dynamique", "type_offre": "dynamique"},
}
