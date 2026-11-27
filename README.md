# Tarifs Électricité pour Home Assistant

🇫🇷 Français · [🇬🇧 English](README.en.md)

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![Version](https://img.shields.io/github/v/release/JVmaisGpeur/ha-tarifs-electricite)](https://github.com/JVmaisGpeur/ha-tarifs-electricite/releases)
[![Validation](https://github.com/JVmaisGpeur/ha-tarifs-electricite/actions/workflows/validate.yml/badge.svg)](https://github.com/JVmaisGpeur/ha-tarifs-electricite/actions/workflows/validate.yml)
[![Licence MIT](https://img.shields.io/badge/licence-MIT-green.svg)](LICENSE)

<img src="https://raw.githubusercontent.com/JVmaisGpeur/ha-tarifs-electricite/main/images/icon.png" alt="Icône Tarifs Électricité" width="96" align="right">

Votre contrat d'électricité dans Home Assistant, **quel que soit le fournisseur**. Choisissez votre offre dans la liste (ou décrivez-la), recopiez les prix de votre facture : l'intégration calcule en continu le **prix du kWh en cours**, la **période** (heures pleines, creuses, super creuses, week-end…), les **jours spéciaux** (Tempo, Sobriété, Jour Éclair…) et les **prévisions de prix**. Tout est disponible en capteurs pour le tableau Énergie, les automatisations, les cartes et d'autres intégrations (voir [Interface pour les autres intégrations](#interface-pour-les-autres-intégrations)).

Une carte Lovelace est incluse : elle s'installe toute seule avec l'intégration. Intégration et carte sont en **français et en anglais** : elles suivent la langue de Home Assistant.

![Aperçu de la carte](https://raw.githubusercontent.com/JVmaisGpeur/ha-tarifs-electricite/main/images/apercu-carte.png)

## Installation

Home Assistant 2025.1 ou plus récent (2026.3 ou plus pour voir l'icône de l'intégration).

[![Ouvrir dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=JVmaisGpeur&repository=ha-tarifs-electricite&category=integration)

1. Cliquez sur le bouton ci-dessus, ou : HACS → ⋮ → **Dépôts personnalisés** → `https://github.com/JVmaisGpeur/ha-tarifs-electricite`, type **Intégration**.
2. Télécharger **Tarifs Électricité**, puis redémarrer Home Assistant.
3. Paramètres → Appareils et services → **Ajouter une intégration** → *Tarifs Électricité* (ou [![Ajouter l'intégration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=tarifs_electricite)).
4. Choisissez votre offre dans la liste, vérifiez la structure pré-remplie et saisissez vos prix.
5. Ajoutez la carte *Tarifs Électricité* à un tableau de bord.

Pour changer de prix ou d'offre plus tard : bouton **Configurer** de l'intégration, ou la roue dentée de la carte (voir ci-dessous). La puissance souscrite se modifie seule via **Configurer → Puissance souscrite**, et le prix de revente du surplus via **Configurer → Revente du surplus**.

### Installation manuelle

Copiez le dossier `custom_components/tarifs_electricite` dans le dossier `custom_components` de votre configuration, puis redémarrez Home Assistant.

## Ma consommation : coûts, mensualité, solde

Facultatif, à la fin de la configuration (ou plus tard : **Configurer → Suivi de consommation et mensualité**). Choisissez le **compteur d'énergie soutirée du réseau** — celui du tableau Énergie (Linky via TIC, Shelly EM, Enphase « consommation d'énergie nette cumulée »…). L'historique déjà enregistré par Home Assistant est utilisé immédiatement.

Puis indiquez comment vous payez :

- **Mensualités** (prélèvement fixe + régularisation) : montant de la mensualité, nombre de prélèvements par an, date de la dernière régularisation → mensualité conseillée, écart, solde.
- **Consommation réelle** (facture tous les 1, 2, 3, 6 ou 12 mois, sans mensualité) : fréquence et date d'une de vos factures pour caler les périodes → **facture en cours**, **montant estimé de la prochaine facture** et sa date (`sensor.tarif_electricite_facture_en_cours`, `_facture_estimee`, `_prochaine_facture`).

Dans les deux cas : `sensor.tarif_electricite_cout_annuel_estime`. Les **sauts aberrants du compteur** (passerelle qui redémarre et repasse un instant à 0, ce que Home Assistant prend pour des milliers de kWh consommés) sont détectés et corrigés : une heure ne peut dépasser la puissance souscrite + 25 %.

| Ce que vous obtenez | Comment c'est calculé |
|---|---|
| **Coût aujourd'hui, cette semaine, ce mois-ci, cette année** (`sensor.tarif_electricite_cout_*`) | consommation heure par heure × prix de cette heure-là (HP/HC, week-end, Tempo, jours spéciaux…), + la part d'abonnement. Attributs : kWh, coût énergie, coût abonnement, prix moyen payé |
| **Mensualité estimée** (`sensor.tarif_electricite_mensualite_estimee`) | votre consommation des 12 derniers mois, aux prix de votre grille la plus récente (évolution prévue comprise), + 12 mois d'abonnement, divisé par le nombre de prélèvements (10, 11 ou 12). Attributs : consommation annuelle, coût annuel, répartition HP/HC en %, **fiabilité** |
| **Écart avec la mensualité du fournisseur** (`sensor.tarif_electricite_ecart_mensualite`) | estimée − prélevée. Positif : régularisation à prévoir ; négatif : vous payez trop. Un conseil en clair est fourni (« vous pouvez demander à baisser votre mensualité d'environ 25 €/mois ») |
| **Solde depuis la dernière facture** (`sensor.tarif_electricite_solde_estime`) | mensualités payées (au prorata) − coût réellement consommé depuis la date de début de période. Positif : remboursement probable |

**Fiabilité de l'estimation** : *bonne* avec une année complète de données ; *moyenne* entre 3 et 11 mois, *faible* sous 3 mois (la consommation est extrapolée sur un an, sans tenir compte des saisons : chauffage, climatisation…) ; aucune estimation sous 14 jours.

Le prix des heures passées vient de l'historique du capteur *Prix actuel* (donc exactement ce qui était affiché, y compris prix dynamique et jours spéciaux). Pour les heures d'avant l'installation de l'intégration, il est recalculé avec les grilles saisies, l'historique des couleurs Tempo et le journal des jours spéciaux.

## Évolutions tarifaires et historique des prix

Quand votre fournisseur annonce de nouveaux prix (en général un mois avant), ouvrez **Configurer**, saisissez les nouveaux prix, puis choisissez :

- **Évolution tarifaire** + la date d'effet annoncée : l'intégration continue d'appliquer les prix actuels, puis **bascule toute seule à minuit le jour J**. La carte affiche « Nouveaux prix le 1er février 2027 · +2,8 % en moyenne » en attendant.
- **Correction** : pour rectifier une erreur de saisie, sans créer d'historique.

Chaque grille est conservée avec sa date d'effet. La carte montre l'historique (prix avant → après, en %, abonnement compris), et l'attribut `historique_prix` de `sensor.tarif_electricite_prix_actuel` le rend disponible pour vos propres cartes ou automatisations. Une évolution annulée ou saisie en double se retire avec **Configurer → Supprimer une grille**.

Les prévisions et le service `previsions` tiennent compte d'une évolution prévue : le créneau le moins cher calculé la veille d'une hausse utilise déjà les bons prix.

## Offres prêtes à l'emploi

Le modèle pré-remplit la **structure** de l'offre (plages connues, week-end, jours spéciaux, saisons). Les **prix ne sont jamais pré-remplis** : ils changent souvent, recopiez ceux de votre facture ou de la grille tarifaire du fournisseur. Vérifiez toujours la structure proposée.

| Modèle | Ce qui est pré-rempli |
|---|---|
| EDF Tempo | type Tempo, HC 22 h–6 h, couleurs automatiques |
| EDF Zen Week-End / Zen Week-End Plus | prix week-end et fériés (+ jour au choix en semaine pour Plus) |
| EDF Zen Week-End Heures Creuses | HP/HC + prix week-end |
| EDF Zen Week-End option Flex | HC 13 h–18 h et 20 h–8 h, jours **Sobriété** (journée de 8 h à 8 h) |
| Enercoop Flexibilité Nuit & Week-end | HC 23 h–6 h, week-end et fériés en HC |
| TotalEnergies Charge'Heures | HP/HC + heures super creuses à saisir |
| TotalEnergies Heures Eco+ | HP/HC + **Jours Éclair** |
| Octopus Go | HP/HC (heures creuses de nuit à saisir) |
| OHM Énergie Week-End / Modulo / Beaux Jours | week-end en HC / heures solaires + saisons + Jours Sérénité / Base avec prix d'été |
| Sobry, Frank Énergie | prix dynamique lu sur une autre entité |
| **Autre offre** | vous décrivez tout vous-même |

## Tout ce qu'on peut décrire

| Besoin | Où |
|---|---|
| Prix unique | type **Base** |
| Heures pleines / creuses, plusieurs plages (`02:00-07:00, 13:00-16:00`) | type **HP/HC** |
| Heures super creuses | HP/HC, champs facultatifs |
| Une période nommée en plus (« Heures solaires »…), creuse ou non | HP/HC, champs facultatifs |
| Week-end : comme en semaine, tout en HC, ou **prix week-end dédié** (avec ou sans prix HC week-end) | étape *Calendrier* |
| Jours fériés : comme en semaine, tout en HC, ou comme le week-end (calcul automatique, Alsace-Moselle en option) | étape *Calendrier* |
| Jours de semaine au tarif week-end (lundi, mercredi…) | étape *Calendrier* |
| Prix (et plages) différents hiver / été, mois au choix | étape *Calendrier* → *Été* |
| 1 ou 2 types de **jours spéciaux** (Sobriété, Éclair, Sérénité…), avec heure de début de journée | étape *Calendrier* → *Jours spéciaux* |
| Tempo | type **Tempo** : couleurs et prévisions sur 15 jours récupérées automatiquement ([calendrier-tempo.fr](https://www.calendrier-tempo.fr/domotique), sans compte) |
| Prix qui change chaque heure | type **Prix dynamique** : choisissez l'entité qui donne le prix (intégration Sobry, EPEX Spot, Nord Pool…). €/MWh et c€/kWh convertis automatiquement, majoration (taxes, acheminement) en option. Si l'entité publie les prix à venir, ils servent aux prévisions |

### Jours spéciaux : comment l'intégration sait que c'est un jour spécial ?

Les fournisseurs annoncent ces jours la veille (par mail, SMS ou dans leur appli), sans API publique. Deux façons de faire :

- **D'un appui** : sur la carte, touchez *Aujourd'hui* ou *Demain* pour passer de « Normal » à « Sobriété ». Ce sont aussi des entités `select.tarif_electricite_jour_special_aujourdhui` / `_demain`, réglables par une automatisation. À l'heure de début de journée, « demain » devient « aujourd'hui ».
- **Automatiquement** : si une autre intégration annonce déjà ces jours (ex. l'intégration EDF Zen Flex), choisissez son entité comme source et indiquez l'état qui signifie « jour spécial » (ex. `Sobriété` ; majuscules et accents ignorés). La carte affiche alors 🔗.

## Entités créées

Identifiants identiques sur toutes les installations :

| Entité | Contenu |
|---|---|
| `sensor.tarif_electricite_offre` | type d'offre : `base`, `hphc`, `tempo` ou `dynamique`. Attributs : `fournisseur`, `nom_offre` |
| `sensor.tarif_electricite_puissance_souscrite` | puissance souscrite en kVA (`unknown` si non renseignée) |
| `sensor.tarif_electricite_prix_actuel` | Prix du kWh en ce moment (EUR/kWh). Attributs : période, libellé, jour spécial, prochain changement, min/max sur 24 h, grille, `previsions` (tranches des 48 h à venir) |
| `sensor.tarif_electricite_periode` | `hp`, `hc`, `hsc` (super creuses), `perso` (période nommée), `we`, `we_hc` (week-end), `base` ou `dyn` (prix dynamique) |
| `sensor.tarif_electricite_prochain_changement` / `_prochain_prix` | quand le prix change, et le prix suivant (`unknown` si le prix ne change jamais, ex. Base sans option) |
| `binary_sensor.tarif_electricite_heures_creuses` | `on` en heures creuses, super creuses, week-end creuses, et période nommée si elle est déclarée creuse |
| `binary_sensor.tarif_electricite_heures_super_creuses` | si l'offre en a |
| `binary_sensor.tarif_electricite_prix_bas` | `on` quand le prix est dans le tiers le moins cher des 24 h à venir — **marche avec toutes les offres**, y compris le prix dynamique |
| `binary_sensor.tarif_electricite_jour_special` | `on` pendant un jour spécial |
| `select.tarif_electricite_jour_special_aujourdhui` / `_demain` | type de jour (offres à jours spéciaux) |
| `sensor.tarif_electricite_abonnement_mensuel` | si renseigné |
| `sensor.tarif_electricite_prix_revente` | prix de revente du surplus (EUR/kWh), si renseigné ; `unknown` si la grille en vigueur n'en a pas |
| `sensor.tarif_electricite_tempo_aujourdhui` / `_demain` / `_previsions` | offres Tempo |

**Tableau Énergie** : Paramètres → Tableaux de bord → Énergie → consommation réseau → *Utiliser une entité avec le prix actuel* → `sensor.tarif_electricite_prix_actuel`. Pour le retour au réseau : *Utiliser une entité avec le prix actuel* → `sensor.tarif_electricite_prix_revente`.

## Service `tarifs_electricite.previsions`

Renvoie les tranches de prix à venir, la moins chère, la plus chère et, si `duree` est donnée, **le créneau continu le moins cher** de cette durée.

```yaml
action: tarifs_electricite.previsions
data:
  heures: 24
  duree: 3
response_variable: tarifs
# tarifs.meilleur_creneau → {debut, fin, prix_moyen}
```

## Service `tarifs_electricite.prix_passes`

Renvoie les prix d'une période passée (au plus 366 jours), **heure par heure**, tels que le contrat les définit aujourd'hui : une grille corrigée après coup donne les nouveaux prix. Utile pour valoriser une consommation ou une production passée.

```yaml
action: tarifs_electricite.prix_passes
data:
  debut: "2026-10-01 00:00:00"
  fin: "2026-11-01 00:00:00"
response_variable: passe
# passe.heures → [{debut, prix, prix_revente, periode, couleur, jour_special}, …]
```

## Exemples d'automatisations

Lancer le chauffe-eau quand le prix est bas (toutes offres) :

```yaml
alias: Chauffe-eau – marche quand le prix est bas
triggers:
  - trigger: state
    entity_id: binary_sensor.tarif_electricite_prix_bas
    to: "on"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.chauffe_eau   # adaptez à votre entité
```

Planifier une recharge de 3 h au moment le moins cher des 24 prochaines heures :

```yaml
alias: Recharge – planifier au moins cher
triggers:
  - trigger: time
    at: "18:00:00"
actions:
  - action: tarifs_electricite.previsions
    data: { heures: 24, duree: 3 }
    response_variable: tarifs
  - action: input_datetime.set_datetime
    target: { entity_id: input_datetime.debut_recharge }
    data:
      datetime: "{{ tarifs.meilleur_creneau.debut }}"
```

Être prévenu d'un jour spécial demain :

```yaml
triggers:
  - trigger: state
    entity_id: select.tarif_electricite_jour_special_demain
condition: "{{ trigger.to_state.state != 'Normal' }}"
actions:
  - action: notify.notify
    data:
      message: "Demain : {{ trigger.to_state.state }}. Pensez à décaler vos consommations."
```

## Interface pour les autres intégrations

> 🇬🇧 English version below.

D'autres intégrations peuvent s'appuyer sur Tarifs Électricité, par exemple pour piloter des batteries de stockage ou une recharge selon les prix à venir. Elles passent **uniquement** par les entités et le service décrits ici : jamais par le code interne.

**Version d'interface : 1** (depuis la 1.1.0). Elle figure dans la réponse du service (`version_interface`).

### Retrouver les entités

Par le registre des entités de Home Assistant, avec l'`entry_id` du contrat et la `translation_key` ci-dessous — **pas** par l'`entity_id`, que l'utilisateur peut renommer. L'`unique_id` vaut `<entry_id>_<translation_key>`.

| translation_key | Plateforme | État / unité | Présente |
|---|---|---|---|
| `puissance_souscrite` | sensor | kVA (entier) ou `unknown` | toujours |
| `offre` | sensor (enum) | `base`, `hphc`, `tempo`, `dynamique` | toujours |
| `prix_actuel` | sensor | EUR/kWh | toujours |
| `periode` | sensor (enum) | `hp`, `hc`, `hsc`, `perso`, `we`, `we_hc`, `base`, `dyn` | toujours |
| `prochain_changement` | sensor (timestamp) | date-heure du prochain changement de prix ; `unknown` si le prix ne change jamais | toujours |
| `prochain_prix` | sensor | EUR/kWh ; `unknown` si le prix ne change jamais | toujours |
| `heures_creuses` | binary_sensor | `on` en heures creuses (week-ends et fériés compris selon le contrat) | offres HP/HC et Tempo |
| `heures_super_creuses` | binary_sensor | `on` en heures super creuses | si l'offre en a |
| `prix_bas` | binary_sensor | `on` si le prix est dans le tiers bas des 24 h à venir | toujours |
| `tempo_aujourdhui`, `tempo_demain` | sensor (enum) | `bleu`, `blanc`, `rouge` | offres Tempo |
| `tempo_previsions` | sensor (enum) | couleur d'après-demain ; attribut `previsions` | offres Tempo |
| `prix_revente` | sensor | EUR/kWh, ou `unknown` si la grille en vigueur n'en a pas | si un prix de revente est saisi (depuis la 1.2.0) |

Les **attributs** des entités (grille, historique, suivi…) ne font **pas** partie du contrat : ils peuvent changer librement.

### Service `tarifs_electricite.previsions` (réponse uniquement)

Entrées : `config_entry_id` (facultatif, sinon le premier contrat), `heures` (1 à 72, défaut 24), `duree` (facultatif, en heures).

Réponse :

| Champ | Contenu |
|---|---|
| `version_interface` | `1` |
| `fournisseur`, `offre` | fournisseur et **nom commercial** de l'offre, tels que saisis |
| `type_offre` | `base`, `hphc`, `tempo` ou `dynamique` |
| `puissance_kva` | entier, ou `null` |
| `segments` | tranches successives, du moment de l'appel jusqu'à l'horizon demandé, sans trou ni chevauchement |
| `moins_cher`, `plus_cher` | segment au prix connu le plus bas / le plus haut (absents si aucun prix connu) |
| `meilleur_creneau` | si `duree` est donnée : `{debut, fin, prix_moyen}` du créneau continu le moins cher, ou `null` |

Attention au mot « offre » : l'état du **capteur** `offre` est le type d'offre (`base`, `hphc`, `tempo`, `dynamique`), comme le champ `type_offre` du service ; le **champ** `offre` du service est le nom commercial saisi, comme l'attribut `nom_offre` du capteur.

Chaque segment :

| Champ | Contenu |
|---|---|
| `debut`, `fin` | ISO 8601 avec fuseau horaire |
| `periode` | mêmes valeurs que le capteur `periode` (minuscules) |
| `libelle` | texte lisible (ex. « Heures creuses · Sobriété ») |
| `prix` | EUR/kWh, ou **`null` si inconnu** : couleur Tempo pas encore annoncée, prix dynamique pas publié. Jamais de prix deviné |
| `couleur` | `bleu`, `blanc`, `rouge`, ou `null` (offre non Tempo, ou couleur inconnue) |
| `saison` | `hiver`, `ete`, ou `null` (offre sans saisons) |
| `jour_special` | nom du jour spécial (ex. `Sobriété`), ou `null` |
| `jour_special_confirme` | `false` si le type de ce jour n'est pas encore connu (demain non annoncé, après-demain) : le prix affiché est celui d'un jour normal. Toujours `true` pour une offre sans jours spéciaux |
| `heures_creuses` | `true` en HC, HSC, week-end HC, et période nommée déclarée creuse. Toujours `false` en Base et en prix dynamique (utilisez `prix`, ou `prix_bas`) |

Pour se protéger au pire cas : traiter un `prix: null` comme le prix le plus élevé possible, et un `jour_special_confirme: false` comme un jour spécial possible ; recalculer quand `tempo_demain` ou le sélecteur de jour spécial de demain change.

### Service `tarifs_electricite.prix_passes` (réponse uniquement, depuis la 1.2.0)

Entrées : `config_entry_id` (facultatif), `debut`, `fin` (dates-heures ; au plus 366 jours ; sans fuseau = heure locale de Home Assistant). Le début est arrondi à l'heure.

| Champ | Contenu |
|---|---|
| `version_interface` | `1` |
| `heures` | une ligne par heure, contiguës : `debut` (ISO 8601 avec fuseau), `prix` (EUR/kWh, moyenne pondérée par le temps dans l'heure ; **`null` si inconnu**), `prix_revente` (ou `null`), `periode` dominante (minuscules), `couleur` Tempo et `jour_special` (ou `null`) |
| `derniere_modification` | `{quand, depuis}` : date de la dernière modification des grilles, et date d'effet la plus ancienne qu'elle touche (`depuis: null` = dès l'origine du contrat). `{null, null}` tant qu'aucune grille n'a été modifiée depuis la 1.2.0 |

Calcul : grilles datées, journal des couleurs Tempo et des jours spéciaux tenu par l'intégration ; pour un prix dynamique, moyennes horaires enregistrées du capteur `prix_actuel`. Une heure 23:00 → 00:00 avec heures creuses à 23:30 vaut la moyenne des deux prix. Un pilote qui a déjà valorisé une période recalcule quand `derniere_modification.quand` change.

### Règles de version

| Changement | Version |
|---|---|
| Renommer ou supprimer une entité, une `translation_key`, une valeur d'enum, un champ du service | majeure (2.0.0) et `version_interface` + 1 |
| Changer une unité ou le sens d'une valeur | majeure (2.0.0) et `version_interface` + 1 |
| Ajouter une entité, une valeur d'enum, un champ du service | mineure (1.x.0) |
| Correction sans effet sur le contrat | correctif (1.1.x) |

- Un élément appelé à disparaître est d'abord annoncé obsolète dans le CHANGELOG et ce README pendant au moins une version mineure.
- Une nouvelle valeur d'enum est annoncée dans le CHANGELOG : un consommateur doit traiter une valeur inconnue comme « non gérée », sans planter.
- Le CHANGELOG a une rubrique « Interface » à chaque version qui la touche.
- Les tests `tests/test_interface.py` vérifient ce contrat à chaque modification.

### 🇬🇧 Interface for other integrations

Other integrations may rely on Tarifs Électricité, for example to drive storage batteries or EV charging from upcoming prices. They must use **only** the entities and the service below, never the internal code.

**Interface version: 1** (since 1.1.0), returned by the service as `version_interface`.

**Finding entities** — through Home Assistant's entity registry, using the contract's `entry_id` and the `translation_key` (not the `entity_id`, which users may rename). `unique_id` is `<entry_id>_<translation_key>`.

| translation_key | Platform | State / unit | Present |
|---|---|---|---|
| `puissance_souscrite` | sensor | subscribed power, kVA (integer) or `unknown` | always |
| `offre` | sensor (enum) | offer type: `base`, `hphc`, `tempo`, `dynamique` | always |
| `prix_actuel` | sensor | current price, EUR/kWh | always |
| `periode` | sensor (enum) | `hp` peak, `hc` off-peak, `hsc` super off-peak, `perso` named period, `we`/`we_hc` weekend, `base`, `dyn` dynamic | always |
| `prochain_changement` | sensor (timestamp) | next price change; `unknown` if the price never changes | always |
| `prochain_prix` | sensor | next price, EUR/kWh; `unknown` if the price never changes | always |
| `heures_creuses` | binary_sensor | `on` during off-peak hours (weekends and bank holidays included per contract) | peak/off-peak and Tempo offers |
| `heures_super_creuses` | binary_sensor | `on` during super off-peak hours | if the offer has them |
| `prix_bas` | binary_sensor | `on` when the price is in the cheapest third of the next 24 h | always |
| `tempo_aujourdhui`, `tempo_demain` | sensor (enum) | Tempo colour today / tomorrow: `bleu` blue, `blanc` white, `rouge` red | Tempo offers |
| `tempo_previsions` | sensor (enum) | colour for the day after tomorrow; `previsions` attribute | Tempo offers |
| `prix_revente` | sensor | surplus resale price, EUR/kWh, or `unknown` if the current grid has none | when a resale price is entered (since 1.2.0) |

Entity **attributes** (price grid, history, consumption…) are **not** part of the contract.

**Service `tarifs_electricite.previsions`** (response only). Inputs: `config_entry_id` (optional, defaults to the first contract), `heures` (hours ahead, 1–72, default 24), `duree` (optional slot length in hours). Response: `version_interface`, `fournisseur` (supplier), `offre` (commercial offer name), `type_offre`, `puissance_kva` (integer or `null`), `segments`, and when applicable `moins_cher` / `plus_cher` (cheapest / most expensive segment with a known price) and `meilleur_creneau` (`{debut, fin, prix_moyen}`: cheapest continuous slot of `duree` hours).

Note on “offre”: the `offre` **sensor** state is the offer type (same as the service's `type_offre`); the service's `offre` **field** is the commercial name (same as the sensor's `nom_offre` attribute).

Segments are contiguous, from the call time to the requested horizon. Each has: `debut`/`fin` (ISO 8601 with offset), `periode` (lowercase, as above), `libelle` (label), `prix` (EUR/kWh, or **`null` when unknown**: Tempo colour not yet announced, dynamic price not yet published — never a guessed price), `couleur` (Tempo colour or `null`), `saison` (`hiver` winter, `ete` summer, or `null`), `jour_special` (special day name or `null`), `jour_special_confirme` (`false` when that day's type is not known yet; the normal-day price is shown; always `true` for offers without special days), `heures_creuses` (`true` for off-peak, super off-peak, weekend off-peak and named periods declared off-peak; always `false` for flat and dynamic offers).

Worst-case strategy: treat `prix: null` as the highest possible price and `jour_special_confirme: false` as a possible special day; recompute when `tempo_demain` or tomorrow's special-day selector changes.

**Service `tarifs_electricite.prix_passes`** (response only, since 1.2.0). Inputs: `config_entry_id` (optional), `debut`, `fin` (start and end date-times, at most 366 days; without offset = Home Assistant local time; start rounded down to the hour). Response: `version_interface`; `heures`, one contiguous line per hour with `debut` (ISO 8601 with offset), `prix` (EUR/kWh, time-weighted mean over the hour, **`null` when unknown**), `prix_revente` (or `null`), dominant `periode` (lowercase), Tempo `couleur` and `jour_special` (or `null`); `derniere_modification` `{quand, depuis}`: when the grids were last changed and the earliest effective date affected (`depuis: null` = from the start of the contract; both `null` until a grid is changed after 1.2.0). Computed from the dated grids and the Tempo / special-day log kept by the integration; dynamic prices come from the recorded hourly means of `prix_actuel`.

**Versioning** — renaming/removing an entity, `translation_key`, enum value or service field, or changing a unit or meaning: major version (2.0.0) and `version_interface` + 1. Adding an entity, enum value or service field: minor (1.x.0). Fixes without contract impact: patch (1.1.x). Anything to be removed is first announced as deprecated in the CHANGELOG and README for at least one minor version. Consumers must treat unknown enum values as "unsupported" without failing. The CHANGELOG has an "Interface" section for every version that touches it.

## Carte

```yaml
type: custom:tarifs-electricite-card
entity: sensor.tarif_electricite_prix_actuel
heures: 24            # 12, 24 ou 48
# Sections facultatives, masquées par défaut : activez celles que vous voulez
afficher_frise: true
afficher_tempo: true
afficher_grille: true
afficher_historique: true
afficher_suivi: true
# titre: Mon contrat
```

Toutes les sections sont masquées par défaut : la carte n'affiche que le prix, la période et le prochain changement tant que vous n'activez rien (éditeur visuel de la carte).

Prix en cours, période, badge « Prix bas », prochain changement, frise colorée des prochaines heures (dégradé vert → rouge pour le prix dynamique, hachures pour les jours spéciaux), jours spéciaux d'aujourd'hui et de demain (modifiables d'un appui), couleurs Tempo, grille de prix. Un appui sur le prix ouvre l'historique ; la roue dentée ouvre la configuration.

## Tests

Aucune dépendance à installer :

```bash
python3 tests/test_tariff.py        # moteur de calcul
python3 tests/test_suivi.py         # coûts, mensualité, solde
python3 tests/test_gestionnaire.py  # jours spéciaux, sources, prix dynamique, évolutions datées, suivi (HA simulé)
python3 tests/test_config_flow.py   # tous les écrans de configuration (HA simulé)
python3 tests/test_interface.py     # contrat d'interface (entités, service previsions)
python3 tests/test_traductions.py   # français et anglais complets
```

## Contribuer

Bugs, idées, offres de fournisseurs à ajouter aux modèles : [ouvrez une issue](https://github.com/JVmaisGpeur/ha-tarifs-electricite/issues). Pour une offre, indiquez le fournisseur, le nom de l'offre et un lien vers sa grille tarifaire.

Cette intégration n'est affiliée à aucun fournisseur d'électricité. Les noms d'offres ne servent qu'à pré-remplir la structure ; vérifiez toujours les plages et les prix sur votre contrat.

## Licence

MIT – JVmaisGpeur
