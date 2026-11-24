# Plan de réalisation : rapport annuel PLSOC généré (dossier `plsoc`)

Version du 21/10/2026. Sources : analyse des rapports 2014-2024, audit du schéma `pr_oedic` (`audit_pr_oedic.md`),
schéma `pr_oedic_news` installé (`sql/pr_oedic_news.sql`), projet QGIS de coordination et de validation.

## Objectif

Produire pour le **rapport 2026** (rédigé début 2027) un **brouillon complet** du rapport annuel. Le générateur fournit :
- les chiffres, tableaux, graphiques et cartes ;
- les fiches des mesures compensatoires.

L'équipe rédige ensuite les parties d'expertise dans les blocs prévus à cet effet (surlignés en jaune), comme pour les
autres dossiers du générateur.

| Restera manuel | Sera généré |
|---|---|
| météo, temps passé, observations remarquables, projets impactants et adhérents, photos, préconisations, commentaires et conclusions | bilan, communes, milieux, 7 secteurs (série + tableau par couple), protection, phénologie, succès et Mayfield, causes d'échec, rassemblements, baguage, habitats menacés, mesures compensatoires, carrières, cartes |

## Acquis

- `pr_oedic_news` est installé. Ses vues `v_rap_*` reproduisent à l'identique les chiffres 2015-2024 : bilan, succès,
  Mayfield, milieux, protection.
- La validation experte des nids 2026 se fait dans le projet QGIS (`t_validation_nid`). Elle prime sur les valeurs calculées.
- L'architecture du générateur (dossiers, briques, template, cartes QGIS avec atlas) est en place et éprouvée sur
  les dossiers générique, éolien et Natura 2000.

## Phases

### 0. Cadrage (2-3 j, novembre)

- Rédiger `src/reportgenerator/dossiers/plsoc/METHODO.md`. Il reprend le sommaire du rapport 2024 et précise, pour
  chaque élément :
  - sa source (vue `v_rap_*`) ;
  - ses règles de calcul ;
  - s'il est automatique, semi-automatique ou manuel.
- Faire trancher par l'équipe les décisions listées en fin de document : définitions, secteurs, causes, référentiels.
- **Livrable** : fiche validée. Aucune ligne de code tant qu'elle n'est pas validée.

### 1. Données (4-6 j, novembre-décembre)

Scripts SQL de complément pour `pr_oedic_news`, lancés par l'administrateur, testés au préalable en tables
temporaires.

- **Référentiels**
  - Compléter `ref_mesure_compensatoire` : arrêtés, porteurs, surfaces, structure de suivi, mesures récentes.
  - Créer `ref_carriere` : exploitant, arrêté, surfaces, structure de suivi.
  - Créer les sites de rassemblement.
  - Importer les PENAP/ZAP.
  - Reprendre les **parcelles du NAS** avec leur millésime.
- **Données hors base** : rapatrier les rassemblements 2020 et 2022-2025, les parcelles menacées et les nids APIE
  (fichiers du projet `pr_oedic4`).
- **Vues de rapport manquantes**
  - Passages par mesure : observations Mergin dans la mesure et suivis de mesure.
  - Historique de chaque mesure.
  - Liste des bagues de l'année (département, commune, lieu-dit, date, âge, habitat).
  - Rassemblements Mergin.
  - Causes d'échec regroupées comme dans le rapport (prédation, activité humaine, inconnue).
  - Carrières.
  - Habitats menacés avec les surfaces des parcelles.
- **Contrôle** : les tableaux 2024 recalculés doivent correspondre au rapport 2024 (secteurs, communes, protection,
  mesures, baguage). Les écarts sont expliqués dans la fiche.

### 2. Socle du dossier dans le générateur (3-4 j, décembre)

- **Mode annuel** : `run --dossier plsoc --annee N`. Il fonctionne sans demande et ne met pas à jour
  `date_reportgenerate`. Ce rapport n'est pas lancé par la file horaire, et la vue des demandes n'est pas modifiée.
- **Dossier `dossiers/plsoc/`** : `dossier.toml` (année, seuils, ordre des secteurs), lecture de `pr_oedic_news`
  (pas de VM de la synthèse), tests sans base.

### 3. Briques chiffres, tableaux et graphiques (5-7 j, décembre-janvier)

Une brique par partie du rapport. Le SQL est dans `analysis/plsoc/queries.py` ; les calculs et les textes sont des
fonctions pures testées.

| Brique | Contenu (numérotation du rapport 2024) |
|---|---|
| `plsoc_bilan` | résultats généraux, tableau par collectivité et commune, évolution de la population (fig. 17) |
| `plsoc_milieux` | part agricole / non agricole, milieux et cultures (fig. 6 à 9) |
| `plsoc_secteurs` | pour chaque secteur : série 2015-N, tableau par couple (statut, succès, menace), phrases chiffrées |
| `plsoc_protection` | nids protégés en milieu agricole et non agricole (tableaux 11-12) |
| `plsoc_phenologie` | tableau des dates, figure des couples présents par décade (fig. 10) |
| `plsoc_succes` | grille d'interprétation, répartition, Mayfield, causes, historique (fig. 11-12) |
| `plsoc_rassemblements` | effectifs maximums et historique par site, courbes (fig. 13-15) |
| `plsoc_baguage` | liste des bagues posées et lues |
| `plsoc_urbanisme` | habitats détruits et menacés (tableau 16) |
| `plsoc_carrieres` | fiches des carrières |

### 4. Template Word (2-3 j, janvier)

- Template construit par script (`outils/word/`) à partir du rapport 2024, gardé hors du dépôt :
  - textes fixes repris (présentation du plan, méthodologie) ;
  - placeholders ;
  - blocs jaunes à rédiger ;
  - sections conditionnelles.
- Contrôle : ouverture dans Word, aucun placeholder restant, `check --dossier plsoc`.

### 5. Cartes (3-5 j, janvier)

- Projet modèle `dossiers/plsoc/qgis/`, dans la même charte que le projet de coordination. Il contient :
  - une carte générale de répartition ;
  - un **atlas des 7 secteurs** ;
  - les rassemblements ;
  - les habitats menacés ;
  - un **atlas des mesures compensatoires**.
- Les couches sont exportées dans `outputs/<rapport>/data/`. Ce sont des données sensibles, jamais commitées.

### 6. Fiches des mesures compensatoires (4-6 j, janvier-février)

- **Contenu d'une fiche** : tableau de synthèse, carte, tableau des passages de l'année, historique depuis la mise en
  place, bloc « préconisations » à rédiger.
- **Extension du générateur** : un bloc de template répété autant de fois qu'il y a de mesures. La même extension
  servira aux fiches par espèce du dossier Natura 2000.
- **Option** : une fiche par mesure, à envoyer à son porteur de projet ou à la DREAL.

### 7. Validation et livraison (2-3 j, février)

- **2024** : génération à blanc, comparée au rapport 2024 publié, écarts expliqués.
- **2025** : génération à blanc.
- **2026** : génération réelle, une fois la validation de l'équipe terminée et les analyses rafraîchies.
- Mise à jour de `METHODO.md` et de `doc.md` (nouveau type de rapport, mode annuel).

**Total estimé : 25 à 37 jours**, soit environ 6 semaines réparties de novembre à février.

## Version minimale si le temps manque

Les phases 0 à 4, avec la carte générale et l'atlas des secteurs, donnent un brouillon des chapitres « Résultats ». Les
mesures compensatoires se réduisent alors à leur tableau de synthèse et à leur carte ; le reste reste fait à la main
comme aujourd'hui. Les fiches complètes et les carrières passent au rapport 2027.

## Décisions à prendre avec l'équipe (phase 0)

1. **Succès probable / échec probable** : reprendre la grille des rapports ou la règle Mergin. Elles diffèrent pour
   « couvaison puis oiseaux invisibles à cause de la végétation ».
2. **Mayfield** : période d'exposition (incubation seule ou ponte → envol), définition des « nids en échec » (échecs
   certains seuls, ou certains + probables), durée de 64 jours.
3. **Secteurs** : corriger les polygones pour retrouver l'affectation des rapports (en 2024 : Genas-Pusignan 40 dans
   le rapport, 37 par les polygones), ou saisir le secteur dans les compléments des couples.
4. **Causes d'échec** : nomenclature et regroupements du rapport (prédation, activité humaine, inconnue).
5. **Référentiels** : qui tient à jour les mesures compensatoires, les carrières, les sites de rassemblement et les
   parcelles.
6. **Rapport commun LPO / APIE** : la partie Nord-Isère est-elle générée comme les autres secteurs (ses données
   sont-elles toutes dans Mergin) ?
7. **Calendrier** : date de remise du brouillon 2026, pour caler la fin de la validation des nids.

## Risques

- Validation 2026 incomplète au moment de la génération : chiffres provisoires (succès calculé). Le contrôle
  « validation manquante » le signale.
- Données encore hors base (NAS, fichiers des projets QGIS) : les habitats menacés et les rassemblements historiques
  en dépendent.
- Fiches de mesures : seule extension réelle du générateur, et poste le plus incertain du chiffrage.
