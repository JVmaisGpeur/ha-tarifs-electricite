# Journal des modifications

## 1.0.0 – Première version publique

### Contrat
- Tous fournisseurs : fournisseur et offre en saisie libre, abonnement et puissance.
- Modèles d'offres qui pré-remplissent la structure : EDF (Tempo, Zen Week-End, Zen Week-End Heures Creuses, Zen Week-End Plus, Zen Flex), Enercoop Flexibilité Nuit & Week-end, TotalEnergies (Charge'Heures, Heures Eco+), Octopus Go, OHM Énergie (Week-End, Modulo, Beaux Jours), Sobry, Frank Énergie.
- Base, heures pleines / creuses (plusieurs plages), heures super creuses, période nommée (ex. heures solaires), prix week-end, jours de semaine au tarif week-end, jours fériés calculés (Alsace-Moselle en option), saisons hiver / été.
- Jours spéciaux (Sobriété, Jour Éclair, Jour Sérénité…) : d'un appui sur la carte ou suivis depuis une autre entité, avec heure de début de journée.
- Tempo : couleurs du jour, du lendemain et prévisions sur 15 jours, sans compte RTE.
- Prix dynamique lu sur une autre entité (€/MWh et c€/kWh convertis), majoration facultative.
- Évolutions tarifaires datées : nouveaux prix saisis à l'avance, bascule automatique à minuit, historique des grilles avec variations en %.

### Suivi de consommation
- Coût du jour, de la semaine, du mois et de l'année (abonnement compris, au prorata), d'après les statistiques du compteur.
- Coût annuel estimé avec indice de fiabilité.
- Paiement par mensualités : mensualité conseillée, écart avec celle du fournisseur, solde depuis la dernière régularisation.
- Paiement à la consommation réelle (tous les 1, 2, 3, 6 ou 12 mois) : facture en cours, montant estimé et date de la prochaine facture.
- Sauts aberrants du compteur détectés et corrigés.

### Entités, service et carte
- Prix actuel, période, prochain changement, prochain prix, heures creuses, prix bas, jour spécial, coûts, factures.
- Service `tarifs_electricite.previsions` : tranches de prix à venir et créneau le moins cher pour une durée donnée.
- Carte Lovelace incluse, installée automatiquement, avec éditeur visuel ; sections masquées par défaut.
