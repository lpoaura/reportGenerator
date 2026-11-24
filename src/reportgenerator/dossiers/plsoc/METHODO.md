# Rapport annuel PLSOC Œdicnème : fiche méthodologique

Version de travail du 21/10/2026, première version test. Elle sera amendée selon les retours de l'équipe et les choix
méthodologiques à venir.

Références : `docs/plsoc/audit_pr_oedic.md`, `docs/plsoc/plan_rapport.md`, `docs/plsoc/sql/pr_oedic_news.sql`, et les
rapports annuels 2018-2024 (Word, hors dépôt).

## 1. Process

| Étape | Qui | Comment |
|---|---|---|
| Saisie terrain | observateurs | Mergin (couples, nids, événements, observations, bagues, parcelles, suivis, regroupements) |
| Contrôle, validation, compléments | équipe | projet QGIS de coordination (anomalies ; succès, jours Mayfield et causes validés ; milieu, lieu-dit, menace) |
| Rafraîchissement des analyses | administrateur | `SELECT pr_oedic_news.f_rafraichir_analyses();` **avant** la génération |
| Demande de rapport | équipe | formulaire QGIS : dessin de l'**emprise**, `list_analyse` = `plsoc` |
| Génération | serveur | `generate` (file horaire) : ce dossier, puis la demande est marquée comme traitée |
| Rédaction | équipe | passages surlignés en jaune, photos, météo, projets ; suppression de la section « État des données » |

- **Emprise** : la zone dessinée dans la demande (`ref_geo.l_areas`). **Toutes** les données du suivi qui
  l'intersectent sont prises en compte, quel que soit le département. Chaque territoire (Rhône, Isère, Ain, Allier,
  Cantal…) dessine ainsi l'emprise de son rapport, sans reprendre les données de toute la région. Le paramètre
  `emprise = "zone_etude:<id>"` prend à la place une zone de `pr_oedic_news.ref_zone_etude` (essais).
- **Saison** : paramètre `annee`. Par défaut (0), c'est la dernière saison terminée : l'année en cours après le 1er
  octobre (paramètre `fin_saison` du schéma), sinon l'année précédente. Les séries commencent en 2015, ou à la première
  année présente dans l'emprise.
- **Données** : schéma `pr_oedic_news`, en lecture seule. Le rapport n'utilise pas la VM de la synthèse.

## 2. Règles retenues (validées le 21/10/2026)

- **Succès de reproduction** : celui **validé à dire d'expert** (`t_validation_nid`). À défaut, le succès calculé
  depuis les événements Mergin est utilisé et signalé comme **provisoire** dans le texte. Pour l'historique
  2015-2025, ce sont les valeurs validées à l'époque.
- **Mayfield** (méthode des rapports) : survie journalière = 1 − échecs certains / total des jours d'exposition ;
  probabilité de succès = survie ^ 64 jours. Les jours d'exposition sont ceux **validés par les experts**, sinon ceux
  calculés (incubation seule : sous-estimation signalée).
- **Secteurs, communes, collectivités, mesures compensatoires, zonage PLU** : rattachement **par polygone** (position du
  couple ou du nid). Les couples hors des secteurs forment un bloc « Couples hors des secteurs ». Les communes du
  couple et du nid peuvent différer à une limite communale.
- **Statut de nidification** : nicheur certain si au moins un nid ; sinon nicheur probable (historique) ou règle
  Mergin (probable si au moins 2 contacts à au moins 7 jours d'intervalle, sinon possible), sauf statut validé dans
  les compléments.
- **Degré de menace** : celui saisi dans les compléments, sinon déduit du PLU (U → « Zone U », AU → « Zone AU »,
  sinon « Non menacé »).

## 3. Déductions automatiques (en attente des compléments experts)

Chaque valeur déduite est comptée dans l'encadré « État des données ». Les lieux-dits déduits portent un astérisque
dans les tableaux.

| Information | Règle | Vérification sur 2024 (saisi) |
|---|---|---|
| Milieu | dans une mesure compensatoire → parcelle compensatoire ; dans une parcelle agricole Mergin → agricole ; sinon inconnu | 38 couples agricoles sur 38, 12 en mesure sur 12 ; 2 couples de carrière classés à tort « agricole » |
| Culture | type de végétation du relevé de parcelle Mergin de l'année le plus proche de l'installation du couple | non vérifiable (pas de relevé avant 2026) |
| Lieu-dit | lieu-dit Faune-France (`src_vn_json.places_json`) le plus proche, à moins de 1 000 m | 47 lieux-dits sur 93 identiques au lieu-dit saisi, les autres sont voisins |

## 4. Contenu du rapport

| Partie | Généré | Source | Reste à rédiger |
|---|---|---|---|
| État des données | validation, milieux et lieux-dits saisis ou déduits, causes, anomalies | toutes | section à supprimer en version finale |
| Présentation, méthodologie | textes fixes (rapports 2018-2024), carte de l'emprise, texte de la zone | — | historique local, surfaces agricoles, PENAP/ZAP, temps passé |
| Résultats généraux | texte chiffré, tableau collectivités / communes, carte, bilan annuel depuis 2015, graphique | `mv_ana_couple`, `mv_ana_nid` | météo |
| Milieux | texte, % agricole par an, cultures, milieux non agricoles | idem + déductions | commentaire |
| Secteurs | par secteur : texte chiffré, série, carte, tableau par couple | idem + `ref_secteur` | commentaire par secteur |
| Protection | tableaux agricole / non agricole, texte | `mv_ana_nid` | — |
| Phénologie | dates clés par an (1re et dernière observations : Faune-France / GeoNature ; « Hivernage » si janvier / décembre), couples par décade | `mv_synthese_oedicneme`, couples, nids, rassemblements | commentaire |
| Succès, Mayfield, causes | tableaux, textes, graphiques, historique | `mv_ana_nid` | commentaire |
| Rassemblements | effectif maximal par site, historique | `v_ana_rassemblement` | description des sites |
| Baguage | liste des bagues de l'année (poussins bagués, adultes identifiés) | `v_ana_bague` + bagues de poussins Mergin | — |
| Bilan | texte pré-rédigé | — | à compléter |
| Planification urbaine | couples en zone U / AU depuis 2015, parcelles | `ref_plu`, `hist_parcelle` | projets impactants, adhérents |
| Mesures compensatoires | synthèse ; une fiche par projet : synthèse, carte, observations de l'année, suivis d'état, historique | `ref_mesure_compensatoire`, couples, nids, `v_ana_evenement`, `v_mergin_suivis_mesure` | résultats, préconisations, bilan ; carrières |
| Annexe | anomalies de saisie de l'année | `v_ctrl_anomalies` | — |

Cartes (version 1) : dessinées par matplotlib, sans fond de carte (communes, secteurs, mesures, couples colorés par
statut). Le projet QGIS du rapport est prévu en version 2.

## 5. Données manquantes ou incomplètes (au 21/10/2026)

| Donnée | Effet sur le rapport | Remède |
|---|---|---|
| Validation des nids 2026 (0 sur 80) | succès et Mayfield provisoires (succès calculé : 60 %) | validation dans le projet QGIS, puis rafraîchissement |
| Causes d'échec 2026 (0 sur 30) | graphique des causes vide | validation |
| Milieu des couples 2026 (38 déduits, 50 inconnus) | milieux non agricoles absents | compléments dans le projet QGIS |
| Lieux-dits 2026 (déduits) | astérisques dans les tableaux | compléments |
| Rassemblements 2020, 2022-2025 | aucun historique récent | rapatrier les fichiers des projets QGIS dans la base |
| Bagues de poussins Mergin : `fk_uuid_evenement` contient l'uuid du **nid** | rattachées au nid par le rapport ; signalées « lien orphelin » par les contrôles | corriger le formulaire Mergin, ou adapter les vues |
| Parcelles cadastrales (un seul millésime, inconnu) | surfaces des habitats menacés incomplètes | reprise des parcelles du NAS |
| Référentiel des carrières | partie « carrières » entièrement à rédiger | créer `ref_carriere` |
| Secteurs hors Est lyonnais | aucun bloc par secteur ailleurs | dessiner les secteurs des autres départements (`ref_secteur`) |
| Polygones de secteurs ≠ affectation des anciens rapports | 2024 : Genas-Pusignan 37 contre 40 au rapport | ajuster les polygones si nécessaire |
| Météo, temps passé, projets, photos | — | rédaction |

## 6. Validation de la version test

- Dry-run 2024 sur la zone d'étude du plan (`emprise = "zone_etude:1"`) : 93 couples, 76 nicheurs, 88 nids, 29 / 16
  / 11 / 32 nids par issue, 33 jeunes à l'envol, 51 %, Mayfield 32 échecs / 1 866 j / 33,1 %, 14 poussins bagués,
  38 couples agricoles, 26 nids protégés : identiques au rapport 2024.
- Écarts connus :
  - communes en limite (Colombier-Saugnieu 21 au lieu de 20, Genas 15 au lieu de 16) ;
  - secteurs : affectation par polygone ;
  - mesures : 11 couples au lieu de 12 ;
  - phénologie : la dernière observation vient de Faune-France.
- Dry-run 2026 : rapport complet (114 pages), avertissements de l'état des données conformes.
- Tests sans base : `tests/test_plsoc.py`, dont un rendu complet sur données factices.

```powershell
$env:DRYRUN_PARAMS = '{"annee": 2024, "emprise": "zone_etude:1"}'
poetry run python outils/dryrun/dryrun_dossier.py plsoc 0 0 PLSOC_2024 <dossier de sortie hors dépôt>
```

## 7. Pistes pour la version 2

- Projet QGIS du rapport : atlas des secteurs et des mesures, fond orthophoto.
- Rassemblements : sites nommés, courbes par comptage.
- Carrières : référentiel et fiches.
- Fiches des mesures envoyables séparément aux porteurs de projets.
- Comparaison des chiffres avec la version précédente du rapport (contrôle de régression).
