"""Constantes de l'intégration Tarifs Électricité."""

DOMAIN = "tarifs_electricite"
VERSION = "1.2.0"
# Version du contrat d'interface (entités + service previsions) : voir README
VERSION_INTERFACE = 1

SIGNAL_MAJ = f"{DOMAIN}_maj_{{}}"  # formaté avec l'entry_id

URL_CARTE = "/tarifs_electricite/tarifs-electricite-card.js"

TEMPO_API = "https://www.calendrier-tempo.fr/api"
TEMPO_INTERVALLE_MIN = 30

HORIZON_PREVISIONS_H = 48
SERVICE_PREVISIONS = "previsions"
SERVICE_PRIX_PASSES = "prix_passes"
NORMAL = "Normal"  # jour sans particularité (sélecteurs jours spéciaux)
