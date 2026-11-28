"""Constantes de l'intégration Tarifs Électricité."""

DOMAIN = "tarifs_electricite"
VERSION = "1.3.0"
# Version du contrat d'interface (entités + service previsions) : voir README
VERSION_INTERFACE = 1

SIGNAL_MAJ = f"{DOMAIN}_maj_{{}}"  # formaté avec l'entry_id

URL_CARTE = "/tarifs_electricite/tarifs-electricite-card.js"

TEMPO_API = "https://www.calendrier-tempo.fr/api"
TEMPO_INTERVALLE_MIN = 30

HORIZON_PREVISIONS_H = 48
SERVICE_PREVISIONS = "previsions"
SERVICE_PRIX_PASSES = "prix_passes"
SERVICE_COMPARER = "comparer_offres"  # v1.3.0
SOUS_ENTREE_OFFRE = "offre"  # offres à comparer (sous-entrées du contrat)
NORMAL = "Normal"  # jour sans particularité (sélecteurs jours spéciaux)
