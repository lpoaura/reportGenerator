# Indicateurs de biodiversité : fiche méthodologique

Version de travail du 17/11/2026, première version. Elle sera amendée selon les retours des coordinateurs.

Références : conception `docs/indicateurs/conception.md`, plan `docs/indicateurs/plan.md`, rapports d'exécution
2023-2025 (Word, hors dépôt).

## 1. Process

| Étape | Qui | Comment |
|---|---|---|
| Saisie | observateurs | Faune-France (STOC, SHOC), GeoNature monitoring (STOM, STERF, POP Reptile, POP Amphibien) |
| Demande de rapport | coordination | formulaire QGIS : zone (région, département ou emprise dessinée), `list_analyse` = `indicateurs` |
| Génération | serveur | `generate` (file horaire) : ce dossier, puis la demande est marquée comme traitée |
| Rédaction | coordinateurs | passages surlignés en jaune (animation, perspectives, tendances MNHN, conclusion), page de garde |
| Envoi | coordination | suppression de l'annexe « Contrôle des saisies » |

- **Déclenchement** (`list_analyse`) : `indicateurs` = tous les protocoles ; `indicateurs, stoc, sterf` = ces
  protocoles seulement (jetons `stoc`, `shoc`, `stom`, `sterf`, `pop_reptile`, `pop_amphibien`) ; `annee_2024` force
  l'année du rapport. Aucune colonne n'est ajoutée à la vue des demandes.
- **Année** : paramètre `annee` (0 = dernière saison terminée : l'année en cours à partir du 1er octobre, sinon
  l'année précédente). Les données saisies après la saison du rapport (année suivante) sont ignorées.
- **Date d'extraction** : indiquée en page de garde. Les chiffres évoluent avec les saisies tardives (STOC 2023 : 284
  carrés dans le rapport, 299 en base en novembre 2026).
- **Lecture seule** : aucune vue ni table créée ; chaque requête ouvre une connexion `read_only`. Le schéma `grafana`
  n'est pas lu par le générateur (recoupement seulement).

## 2. Modèle commun

Tous les protocoles sont ramenés au même modèle (`analysis/indicateurs/modele.py`) :
aire (carré STOC/SHOC, site STOM/STERF, aire POP) > unité (point d'écoute, transect, mare) > passage (relevé d'une
unité à une date) > observateurs (catégorie) et observations (espèce, effectif).

| Protocole | Source | Aire | Unité | Effectif | Début de série |
|---|---|---|---|---|---|
| STOC-EPS | `pr_vigienature.t_releve` (`STOC_EPS`) | carré (`carre_numnat`) | point (`point_num`) | `nombre` | 2001 |
| STOC-sites | idem (`STOC_SITES`, `STOC_ONF`, `STOC_SITES_RNF`) | site (`site_name`) | point | `nombre` | 2001 |
| SHOC | idem (`SHOC`) | carré | transect (`point_num`) | `nombre` | hiver 2014-2015 |
| STOM | `gn_monitoring`, module `stom` | groupe de sites | site (point d'écoute) | `nb_0_5 + nb_5_10 + nb_10_15` | 2019 |
| STERF | module `sterf_ebms` | groupe de sites | transect | `effectif` (sinon `count_max`) | 2024 |
| POP Reptile | module `POPReptile` | aire (groupe) | transect | `count_max` | 2022 |
| POP Amphibien | module `POPAmphibien` | aire (groupe) | site (mare) | `count_max` | 2022 |

- `pr_vigienature` contient des carrés de toute la France : le filtre se fait toujours sur la géométrie de la zone.
- Monitoring : un site appartient au module s'il y est rattaché (`cor_site_module`) **ou** s'il a une visite du module
  (9 transects POP Reptile visités en 2025 n'étaient pas rattachés). Un site sans groupe forme l'aire « Sans aire »
  (POP Amphibien), sans contour sur la carte, listé dans l'annexe de contrôle.
- Espèce : `taxonomie.taxref` (STOC/SHOC par `cor_taxon_referentiels`), premier nom vernaculaire sans l'article final.

## 3. Règles retenues (validées le 17/11/2026)

- **Zone** : une aire est dans la zone si l'une de ses unités l'intersecte (toutes années) ; elle est alors comptée
  entière. Département, commune et zone biogéographique (`ref_geo.mv_aura_zb`) : ceux du centre de l'aire (département
  et zone les plus proches si le centre sort de la région).
- **Niveau de détail** : tableaux par département si l'emprise touche au moins deux départements, sinon liste des
  aires ; tableau par zone biogéographique si l'emprise touche au moins deux zones.
- **Saison** : année civile, sauf SHOC : décembre N-1 et janvier N forment la saison N, affichée « N-1-N » (le rapport
  2025 montre l'hiver 2024-2025).
- **Catégorie des observateurs** (règle unique, `selections.categorie_observateur`) : salarié LPO si l'organisme commence
  par « LPO » ou si l'adresse contient « lpo » ; OFB (organisme tiers) si l'adresse est `@ofb.gouv.fr` ou l'organisme
  l'OFB ; organisme tiers pour tout autre organisme ; bénévole sans organisme (ou « - »). Observateur Faune-France sans
  compte GeoNature : « Non renseigné », listé dans l'annexe de contrôle. **Écart avec Grafana** :
  `grafana.vm_synthese_par_observateur` ne regarde que l'adresse ; la colonne `categorie` des vues monitoring n'est
  pas reprise.
- **Comptes et statuts** : un changement de statut (bénévole devenu salarié, salarié parti dans une structure tiers)
  crée un nouveau compte. Monitoring : le statut est juste à la date du passage. STOC et SHOC : le rattachement passe
  par l'adresse Faune-France actuelle, donc le statut actuel est appliqué à toutes les années (note sous les tableaux).
  Les indicateurs de fidélisation comptent des comptes, pas des personnes.
- **Plusieurs observateurs** : une aire est attribuée à la catégorie de l'observateur qui y a fait le plus de relevés
  (égalité : salarié LPO > organisme tiers > bénévole) ; un relevé prend la catégorie la plus prioritaire de ses
  observateurs. Les sommes par catégorie redonnent les totaux.
- **Observateurs STOC** : comptés à partir de 2015 (champ `observateur` peu fiable avant).
- **Passages attendus** (aire « complète ») : STOC-EPS : une visite du 1er avril au 8 mai et une du 9 mai au 15 juin
  (mars, du 1er au 31, optionnel, compté à part ; `passage_mnhn` hors de 1 à 3 signalé en annexe) ; SHOC : décembre et
  janvier ; STOM : une visite du 10 mai au 15 juillet ; STERF : 4 passages par transect de mai à août (à confirmer) ;
  POP : état de l'aire des vues `v_popreptiles_aire_annee` et `v_popamphibien_aire_annee`.
- **STERF vrai** : site d'au moins 5 transects, suivi l'année du rapport ; les autres sites suivis sont des « sites
  type STERF ». Objectif 100 sites (150 idéalement) ; objectifs par zone biogéographique à renseigner
  (`objectifs_zbiog`).
- **POP** : objectifs 50 mailles (aires) POP Reptile, 500 mares POP Amphibien (unités des aires suivies).
- **STOC-sites Natura 2000** : sites dont le nom commence par « STOC N2000 » (25 sites suivis en 2025, comme le
  rapport), depuis 2021 ; rang des espèces (effectif cumulé) comparé au rang en STOC-EPS sur les mêmes saisons. Les
  autres STOC-sites sont résumés en une phrase.
- **Indicateurs descriptifs** : fréquences (part des aires et des unités où l'espèce est notée) et effectifs, jamais
  présentés comme des tendances. Les tendances STOC sont celles du MNHN (bloc à compléter).

## 4. Temps de travail (paramètres du `dossier.toml`, à ajuster par les coordinateurs)

Temps = terrain (mesuré ou forfaitaire) + complément forfaitaire (préparation, trajet, saisie). Le rapport précise
toujours s'il est mesuré ou estimé. Une durée manquante prend la moyenne de la saison (POP : règle des vues) ou la
valeur par défaut du protocole.

| Protocole | Terrain | Complément | Origine |
|---|---|---|---|
| STOC-EPS | 10,5 h par carré, saisie comprise | 0 | rapports 2023-2025 |
| SHOC | 2 h par visite (carré × date) | 1 h de saisie par carré | proposition, à confirmer |
| STOM | 5 h par site | 1 h de saisie par site | proposition, à confirmer |
| STERF | mesuré (heures de début et de fin de la visite) ; 1 h par transect sans heures | 0 | module, défaut à confirmer |
| POP Reptile, POP Amphibien | mesuré (`v_suivi_passage.duree_retenue_min`) | 0 | module |

## 5. Contenu du rapport

Page de garde et chiffres clés (tous protocoles) ; contexte ; une section par protocole, toujours dans le même ordre et
avec le même plan (protocole, participation et chiffres clés, couverture et carte, historique et fidélisation, espèces,
analyses propres, animation à rédiger) ; conclusion ; annexes (espèces par protocole, contrôle des saisies). Une
section est masquée si le protocole n'est pas demandé ou s'il n'a aucune aire dans la zone.

Cartes : projet QGIS `qgis/projet_indicateurs.qgs` (une mise en page par protocole), construit par
`outils/qgis/build_projet_indicateurs.py` et modifiable directement dans QGIS (symbologie, mise en page). Template :
`outils/word/template_indicateurs.py` (textes fixes repris du rapport 2025, à relire).

## 6. Recoupements (dry-run région, saison 2025, base au 17/11/2026)

| Indicateur | Rapport 2025 | Générateur | Écart |
|---|---|---|---|
| carrés STOC-EPS / observateurs | 298 / 208 | 304 / 216 | saisies tardives |
| carrés STOC-EPS 2001-2025 | 680 | 654 | à vérifier : la base compte 680 carrés en incluant 2026 (26 nouveaux) |
| catégories STOC (carrés) | 90 / 45 / 163 | 93 / 48 / 163 | saisies tardives, règle de l'organisme |
| observateurs OFB (STOC) | 39 | 39 | — |
| carrés SHOC 2024-2025 | 130 | 130 | — |
| STOC-sites Natura 2000 | 25 | 25 | — |
| STOM : sites | 29 | 30 | saisie tardive |
| STERF : transects / observateurs / données | 248 / 22 / 5 462 | 248 / 21 / 5 469 | — |
| STERF : STERF vrais + sites type | 21 + 25 = 46 | 28 + 21 = 49 | à confirmer : le générateur compte les transects existants du site (≥ 5) ; le rapport comptait peut-être les transects parcourus |
| POP Reptile : aires / transects suivis | 29 transects | 36 / 118 | la référence est la vue (= vue) |
| POP Amphibien : aires / sites suivis | 42 sites | 8 / 50 | la référence est la vue (= vue) |
| Savoie : carrés STOC / SHOC | 25 / 6 | 25 / 6 | — |

Modules monitoring 2025 recoupés avec les VM `grafana.vm_synthese_par_annee` et `vm_synthese_monitoring_base` (toute
la base) : aires, relevés, données et observateurs identiques (STOM 30 / 299 / 1 686 / 22 ; STERF 49 / 973 / 5 469 /
21 ; POP Reptile 36 / 597 / 934 / 22 ; POP Amphibien 8 / 148 / 259 / 6).
