# Dossier « Indicateurs de biodiversité » : document de conception

Version du 17/11/2026, avant planification. Rien n'est codé.

Références :
- rapports d'exécution 2023, 2024, 2025 (Word, hors dépôt) : `C:\Users\afourneyron\Desktop\projet enquête protocoler` ;
- architecture du générateur : `doc.md`, et le dossier `plsoc`, le plus proche (pas de VM de synthèse, année de
  saison, emprise dessinée).

## 1. Intention

Chaque année, la LPO AuRA rend à la DREAL et à la Région un rapport d'exécution « Indicateurs de biodiversité en
Auvergne-Rhône-Alpes » : STOC (EPS et sites), SHOC, STOM, STERF, POP Reptiles et POP Amphibiens. Aujourd'hui, le
rapport est réécrit à la main tous les ans :
- le plan change d'une année sur l'autre ;
- les chiffres sont recopiés depuis Faune-France, GeoNature ou des tableurs ;
- les tableaux sont tapés à la main (tableau STERF par département, liste des sites STOM avec observateurs, rangs
  STOC-sites / STOC-EPS) ;
- il y a des erreurs de recopie (« moyenne de 2111 carrés », tableau POP Amphibiens légendé « aires POP Reptile »,
  total STERF incohérent).

Objectifs :
1. **Produire le rapport de l'année plus facilement** : une trame Word où tous les chiffres, tableaux, graphiques et
   cartes sont générés. La partie rédigée (animation, formations, communication, perspectives) reste aux
   coordinateurs, dans des blocs surlignés en jaune.
2. **Montrer la progression** : chaque chiffre de l'année est accompagné de son historique (série depuis le début du
   protocole) et de l'écart avec l'année précédente.
3. **Valoriser le travail** : chiffres clés de participation (observateurs, bénévoles / salariés / organismes tiers,
   temps passé, données produites).
4. **Harmoniser les pratiques entre protocoles** : même modèle de données, mêmes analyses, même plan pour chaque
   protocole.

Public : les coordinateurs de chaque protocole (naturalistes, outils bureautiques), qui complètent le Word, puis la
DREAL et la Région. Le tableau de bord Grafana existant n'est pas concerné.

## 2. Objectifs, non-objectifs, anti-objectifs

**Objectifs**
- Un nouveau type de dossier `indicateurs`, déclenché par `list_analyse`.
- La **zone** de la demande fixe le périmètre : une région donne une analyse régionale, un département se concentre
  sur le département, toute autre emprise dessinée fonctionne aussi.
- L'**année du rapport** est la dernière saison terminée, avec un historique complet.
- Un **modèle commun** à tous les protocoles, et des **analyses communes** écrites une seule fois.
- Des sections par protocole **optionnelles** : rapport complet ou un seul protocole.

**Non-objectifs (version 1)**
- Recalculer les tendances STOC : elles sont produites par le MNHN. Le rapport garde une section « Tendances MNHN » à
  compléter (figures fournies par le MNHN). L'import automatique d'un fichier MNHN est une évolution possible.
- Calculer des tendances statistiques pour SHOC, STOM, STERF ou POP : les échantillons sont jugés trop faibles dans les
  rapports eux-mêmes. On se limite à des indicateurs **descriptifs**, présentés comme tels.
- Remplacer ou alimenter le tableau de bord Grafana.
- Modifier la base (aucune vue ni table permanente créée).

**Anti-objectifs** (le projet échoue s'il fait ceci, même techniquement juste)
- Des chiffres qui contredisent le rapport sans explication : chaque écart avec les chiffres publiés doit pouvoir
  s'expliquer (saisie tardive, règle de rattachement documentée).
- Des indicateurs descriptifs présentés comme des tendances.
- Une règle métier (catégorie d'observateur, passage valide, aire complète) écrite à plusieurs endroits avec des
  variantes (c'est déjà le cas en base : voir §5.3).
- Un rapport illisible pour une petite zone : un département sans STOM ne doit pas afficher une section STOM vide.

## 3. Contraintes

- Règles du dépôt (`CLAUDE.md`) : base en lecture seule, tables temporaires de session uniquement, pas de `generate`
  sur les demandes réelles, pas de colonne ajoutée à `src_gestion.v_reportgenerator_areas_lpo`, règles métier écrites
  une fois (`selections.py` et `dossier.toml`), template modifié par script, `METHODO.md` à jour.
- Le serveur Docker lance `generate` toutes les heures (code de `main`) : le déclencheur `indicateurs` n'est actif en
  production qu'après fusion dans `main`.
- Le générateur **ne dépend pas du schéma `grafana`** : le droit `USAGE` sur le schéma manque (vérifié le 17/11/2026
  malgré l'ouverture des droits sur les VM), et le compte du serveur Docker devrait l'avoir aussi (voir §5.4).
- Sortie Word uniquement (pas de PDF) : le document est une base de travail complétée par les coordinateurs.
- Données personnelles : le rapport cite déjà nommément les observateurs STOM (liste des sites). Les noms
  n'apparaissent que là où le rapport actuel les montre. Jamais d'email dans le rapport.

## 4. Approches envisagées

| Approche | Principe | Pour | Contre |
|---|---|---|---|
| **A. Traduction dans le générateur** (retenue) | un adaptateur SQL par protocole lit sa source et range les données dans un modèle commun (tables temporaires) ; analyses communes en Python | lecture seule ; tout est dans le dépôt et testable sans base ; ajouter un protocole = écrire un adaptateur | quelques règles déjà présentes en base sont relues ou réécrites |
| B. Vues harmonisées en base | un schéma `pr_indicateurs` avec des vues communes, lues par le générateur et Grafana | une seule source pour tableau de bord et rapport | modification de base hors des règles du projet, déploiement plus lent, règles réparties entre base et dépôt |
| C. Un dossier par protocole | un template par protocole, bibliothèque commune | rapports courts par coordinateur | rapport d'exécution à assembler à la main ; les plans divergent (contraire de l'harmonisation) |

**Choix de l'utilisateur : A** (17/11/2026). Les sections optionnelles de A couvrent l'intérêt de C. La sortie des
adaptateurs est pensée pour pouvoir devenir les vues de B plus tard.

## 5. Conception

### 5.1 Modèle commun

Tous les protocoles se ramènent à cette structure :

```
Aire (carré STOC/SHOC, site STOM/STERF, aire POP)
 └─ Unité (point d'écoute, transect, mare)
     └─ Passage (date, numéro, attendu ou non)
         ├─ Observateurs → organisme → catégorie
         └─ Observations (espèce, effectif)
```

Chaque adaptateur produit quatre tables temporaires de session (`pg_temp`), pour **toutes les années** et pour les
seules aires de la zone :

| Table | Colonnes (minimum) |
|---|---|
| `ind_aires` | protocole, id_aire, nom_aire, departement, geom (union ou enveloppe des unités), premiere_annee |
| `ind_unites` | protocole, id_unite, id_aire, nom_unite, geom |
| `ind_passages` | protocole, id_passage, id_aire, id_unite (null si le passage concerne toute l'aire), date, saison, num_passage, dans_periode (bool), duree_min (null si inconnue), duree_estimee (bool) |
| `ind_passage_observateurs` | protocole, id_passage, id_observateur, organisme, categorie |
| `ind_observations` | protocole, id_passage, cd_ref, nom (français), effectif |

Le nom des tables, leur forme exacte (une table par protocole ou une table commune avec la colonne `protocole`) et le
passage par pandas sont laissés au constructeur. La contrainte : les analyses communes ne lisent que ces tables.

### 5.2 Les adaptateurs

| Protocole | Source | Aire | Unité | Passage | Effectif | Début de série |
|---|---|---|---|---|---|---|
| STOC-EPS | `pr_vigienature.t_releve` / `t_observation`, `nom_protocole = 'STOC_EPS'` | carré (`carre_numnat`, géométrie `l_carre_suivi`) | point (`point_num`) | relevé d'un point (`passage_mnhn`) | `nombre` | 2001 |
| STOC-sites | idem, `STOC_SITES`, `STOC_ONF`, `STOC_SITES_RNF` | site (`site_name`) | point | idem | `nombre` | selon le site |
| SHOC | idem, `nom_protocole = 'SHOC'` (transects) | carré | transect | relevé d'un transect | `nombre` | hiver 2014-15 |
| STOM | `gn_monitoring`, module `stom` | groupe de sites (`t_sites_groups`) | site = point d'écoute | visite | `nb_0_5 + nb_5_10 + nb_10_15` (hors `nb_hors_proto`) | 2019 en base (2014 au niveau national) |
| STERF | `gn_monitoring`, module `sterf_ebms` (le module `sterf` est vide) | groupe de sites | transect | visite | `effectif` | 2024 en base |
| POP Reptile | `gn_monitoring`, module `POPReptile` | groupe de sites (aire) | transect | visite | `count_max` | 2022 |
| POP Amphibien | `gn_monitoring`, module `POPAmphibien` | groupe de sites (aire) | site (mare) | visite | `count_max` | 2022 |

Points de vigilance relevés pendant l'étude :
- `pr_vigienature` contient des carrés **hors AuRA** (environ 1 500 carrés en 2026). Le filtre se fait toujours sur
  la géométrie de la zone, jamais sur un attribut.
- Le champ `observateur` de `pr_vigienature` (identifiant Faune-France) n'est fiable qu'à partir de 2015 (1 à
  48 observateurs par an avant, pour 200 carrés). Les séries « observateurs » STOC démarrent en 2015, avec une note.
- POP Amphibien : 11 sites sur 112 n'ont pas d'aire. Ils sont comptés comme une aire « sans aire » et listés dans
  l'annexe de contrôle.
- Monitoring : les aires sans passage dans la zone ne sont pas des aires suivies. Elles servent au calcul des aires
  existantes non suivies (POP : « transects existants / visités »).
- Les durées viennent de `gn_monitoring.v_suivi_passage.duree_retenue_min` (POP : heures de début et de fin, sinon
  moyenne du site ou du module). Pour le STERF, la vue ne lit pas les heures, alors que `t_visit_complements` contient
  `start_hour` et `end_hour` : l'adaptateur STERF les lit lui-même.

- STOC : `passage_mnhn` vaut 1 à 3 (quelques valeurs de 0 et de 4 à 13 depuis 2024, à traiter comme anomalies). Le
  passage de mars se reconnaît à sa date (mois de mars), pas à son numéro.

**Saison** : année civile, sauf SHOC (hiver de décembre N-1 à janvier N, rattaché à **N-1** pour coller aux rapports :
« saison 2024-2025 » = hiver 2024 dans le rapport 2025).

### 5.3 Catégorie des observateurs

La règle est écrite **une seule fois** (`analysis/indicateurs/selections.py`) et appliquée à tous les protocoles :
- **Salarié LPO** : organisme dont le nom commence par « LPO », ou adresse email contenant « lpo ». Certains salariés
  n'ont pas d'adresse LPO mais sont bien rattachés à l'organisme LPO Auvergne-Rhône-Alpes.
- **Organisme tiers** : tout autre organisme renseigné, en gardant son nom. L'OFB est aussi reconnu par une adresse
  `@ofb.gouv.fr`, car le rapport STOC le distingue.
- **Bénévole** : aucun organisme, ou « - ».

Sources :
- monitoring : `cor_visit_observer` → `utilisateurs.t_roles` → `bib_organismes` ;
- STOC/SHOC : identifiant Faune-France → email (`src_vn_json.observers_json`) → `t_roles`. Test sur le STOC 2025 :
  216 observateurs sur 216 retrouvés, 33 de l'organisme LPO (30 dans le rapport), 39 adresses OFB (39 dans le
  rapport).

**Historique des statuts** (validé le 17/11/2026) : l'organisme n'est pas daté en base, mais quand un utilisateur
change de statut (bénévole devenu salarié, salarié parti dans une structure tiers), un **nouveau compte** est créé
avec le nouvel organisme. Pour les modules monitoring, le compte qui a saisi le passage porte donc le bon statut à la
date du passage. Deux conséquences :
- une personne qui a changé de statut compte pour deux observateurs dans les séries ; les indicateurs de fidélisation
  comptent des comptes, pas des personnes (note dans `METHODO.md`) ;
- STOC et SHOC passent par l'identifiant Faune-France puis par l'email actuel. Le rattachement retrouve donc le compte
  qui porte l'email actuel, et donc le **statut actuel**, appliqué à toutes les années. Une note l'indique sous les
  séries STOC et SHOC par catégorie.

C'est la règle de `gn_monitoring.v_suivi_passage_observateur`. La VM `grafana.vm_synthese_par_observateur` en applique
une autre (sans le critère d'organisme). Le générateur ne réutilise pas la colonne `categorie` des vues : il applique
sa propre règle partout, et `METHODO.md` signale l'écart avec Grafana.

### 5.4 Ce qui est réutilisé de la base

- **Lu directement** : `gn_monitoring.v_suivi_passage` (passages, durées), `v_popreptiles_aire_annee`,
  `v_popamphibien_aire_annee` (état de l'aire, passages attendus, règles POP déjà validées), `v_*_anomalies` (annexe
  de contrôle), `t_*` du monitoring.
- **Repris comme définitions, sans être lu** : les VM `grafana.vm_synthese_*` et `vm_comparaison_annees`. Même avec
  l'accès, elles ne couvrent pas le STOC et le SHOC, elles dépendent de leur rafraîchissement, elles ne filtrent pas par
  zone et elles classent les observateurs sur l'email seul. Leurs indicateurs sont repris dans les analyses communes :
  fréquence de présence (passages avec l'espèce / passages du site), première et dernière année, « autres protocoles »
  d'un observateur, et d'une année sur l'autre (`vm_comparaison_annees`) : observateurs gagnés et perdus, aires
  nouvelles et abandonnées, espèces nouvelles et non revues. Elles servent de recoupement pendant la validation
  quand l'accès est ouvert.

### 5.5 Zone et rattachement

- **Emprise** : la géométrie de la demande (`id_area`), comme pour le PLSOC.
- **Aire dans la zone** : au moins une de ses unités intersecte la zone. L'aire est alors comptée entière, y compris
  ses unités hors zone, pour ne pas couper un carré STOC à une limite départementale.
- **Département d'une aire** : celui qui contient le centroïde de ses unités.
- **Niveau de détail** : un cran en dessous de la zone. Si l'emprise touche au moins deux départements, les tableaux
  sont détaillés par département. Sinon, ils listent les aires (nom, commune, passages, observateurs selon le
  protocole).

### 5.6 Année du rapport

Paramètre `annee` du `dossier.toml`, sur le modèle du PLSOC : `0` = dernière saison terminée, au 1er octobre pour
les protocoles de printemps et d'été. Un jeton `annee_AAAA` dans `list_analyse` (ex. `indicateurs, annee_2024`) force
une année pour refaire un rapport passé. Il ne demande aucune colonne nouvelle : `parse_list_analyse` découpe déjà les
valeurs.

Chaque rapport indique sa **date d'extraction**. Les chiffres en base évoluent avec les saisies tardives : STOC 2023 =
284 carrés dans le rapport, 299 aujourd'hui.

### 5.7 Analyses communes

Calculées pour chaque protocole, dans des fonctions pures testées sans base :

| Bloc | Indicateurs (année N, avec série et écart N-1) |
|---|---|
| **Participation** | aires suivies ; unités suivies ; passages ; observateurs ; données ; espèces ; temps total (mesuré ou estimé, voir paramètres) ; répartition par catégorie (aires, observateurs, données, temps) |
| **Couverture** | aires suivies par département (ou liste des aires) ; aires nouvelles (première année = N) ; aires non reconduites (suivies en N-1, pas en N) ; aires complètes ou incomplètes (passages réalisés / attendus, passages dans la période) ; cumul depuis le début (aires suivies au moins une fois, observateurs au moins une fois) |
| **Historique** | graphique des aires suivies par an depuis le début ; graphique des observateurs par catégorie ; tableau des chiffres clés N-4 à N |
| **Fidélisation** | ancienneté des aires (nombre d'années suivies, aire la plus ancienne) ; taux de reconduction des aires et des observateurs ; par rapport à l'année précédente : observateurs gagnés et perdus, aires nouvelles et abandonnées (nombres, jamais de noms de personnes) ; observateurs actifs sur plusieurs protocoles |
| **Espèces** | espèces les plus fréquentes (part des aires et des unités où l'espèce est notée) et les plus abondantes (somme des effectifs) en N ; évolution de la fréquence des 10 premières espèces sur les dernières années, signalée comme **descriptive** |
| **Carte** | aires de la zone par statut en N : suivie, nouvelle, non suivie (QGIS) |

Les chiffres clés de la première page reprennent pour chaque protocole : aires, observateurs, données, temps, écart
avec N-1.

### 5.8 Analyses propres à un protocole

| Protocole | Analyse | Source de la règle |
|---|---|---|
| STOC | temps estimé = carrés × 10,5 h (paramètre) ; carrés par nombre de passages (1, 2, 3, avec ou sans mars) ; part OFB | rapports 2023-2025 |
| STOC | **STOC-sites Natura 2000** : sites LPO créés en 2021 sur 7 ZPS, reconnus par leur nom (`site_name ILIKE 'STOC N2000%'` : exactement les 25 sites de la liste du rapport en 2025) ; données cumulées, taxons, rang des espèces sur les STOC-sites comparé au rang en STOC-EPS (tableau des 40 premières espèces) | rapport 2023 (tableau fait à la main) |
| STOC | section « Tendances MNHN » : blocs à compléter (figures cortèges, annexes court et long terme) | MNHN |
| SHOC | carrés par saison, part des carrés aussi suivis en STOC | — |
| STOM | liste des sites suivis en N : date, site, département, observateurs (comme dans le rapport) ; répartition par massif | rapport 2025 |
| STERF | « STERF vrai » (au moins 5 transects et suivi annuel) ou « site type STERF » ; tableau par département (observateurs, STERF vrais, sites type STERF, transects, données) ; transects non suivis en N | rapport 2025 |
| POP | état des aires (vues POP) ; tableau par département (aires, transects ou sites, suivis complets, nouveaux) ; avancement vers les objectifs (50 mailles Reptile, 500 mares Amphibien, en paramètres) | rapport 2025 |
| STERF | avancement vers l'objectif de 100 sites (150 idéalement) | rapport 2025 |

### 5.9 Plan du Word

1. Page de garde, référence, chiffres clés de l'année (tous protocoles), date d'extraction.
2. Contexte (texte fixe, repris du rapport 2025, à relire par les coordinateurs).
3. **Une section par protocole**, toujours dans le même ordre (STOC, SHOC, STOM, STERF, POP Reptile, POP Amphibien),
   avec le même plan :
   1. Protocole (texte fixe) ;
   2. Participation et chiffres clés ;
   3. Couverture (tableau, carte) ;
   4. Historique et fidélisation ;
   5. Espèces ;
   6. Analyses propres au protocole ;
   7. Animation et perspectives (bloc jaune à rédiger).
4. Conclusion (bloc jaune, avec le récapitulatif chiffré pré-rédigé).
5. Annexes : tableaux complets d'espèces, anomalies de saisie (à supprimer avant envoi).

Chaque section protocole est un bloc `{{#protocole}} … {{/protocole}}`, masqué si le protocole n'est pas demandé ou
s'il n'a aucune aire dans la zone (`sans_section`). Les noms de placeholders sont préfixés par protocole
(`{{STOC_NB_AIRES}}`…) : le template est plus long, mais chaque section se lit seule et se modifie sans casser les
autres.

### 5.10 Déclenchement et paramètres

- `list_analyse` : `indicateurs` déclenche le dossier. Les jetons `stoc`, `shoc`, `stom`, `sterf`, `pop_reptile`,
  `pop_amphibien` limitent le rapport à ces protocoles. Sans jeton de protocole, tous les protocoles sont traités.
- `dossier.toml` : année, début de série par protocole, passages attendus par protocole, seuil STERF vrai
  (5 transects), objectifs de couverture, nombre d'espèces affichées, règle de reconnaissance des STOC-sites
  Natura 2000.
- **Temps de travail** (demande du 17/11/2026) : tous les temps sont des paramètres par protocole, que les
  coordinateurs pourront ajuster selon leur vision du terrain. Le temps d'un protocole se compose :
  - d'un **temps de terrain** : mesuré (heures de début et de fin du passage) quand il existe, sinon forfaitaire ;
  - d'un **temps complémentaire** forfaitaire par passage ou par aire : préparation, trajet, saisie. Il vaut 0 pour
    l'instant, et pourra être relevé pour mieux valoriser le travail réel.

  Le rapport précise toujours si un temps est mesuré ou estimé. Valeurs de départ :

  | Protocole | Terrain | Complément | Origine |
  |---|---|---|---|
  | STOC-EPS | 10,5 h par carré, saisie comprise | 0 | rapports 2023-2025 |
  | SHOC | 2 h par passage (protocole : 1 h 30 à 2 h) | 1 h de saisie par carré, soit 5 h par carré | proposition |
  | STOM | 5 h par site (protocole) | 1 h de saisie par site, soit 6 h par site | proposition |
  | STERF | mesuré (heures de début et de fin) | 0 | module |
  | POP Reptile, POP Amphibien | mesuré (`v_suivi_passage.duree_retenue_min`) | 0 | module |

### 5.11 Arbitrages pris après relecture (proposés, à corriger si besoin)

- **Plusieurs observateurs sur un passage** : les observateurs sont comptés une fois chacun, dans leur catégorie. Une
  aire est attribuée à **une seule** catégorie : celle de l'observateur qui a fait le plus de passages, et en cas
  d'égalité Salarié LPO > Organisme tiers > Bénévole. La somme par catégorie redonne donc le total, comme dans le
  rapport (90 + 45 + 163 = 298 carrés STOC). Les données et le temps d'un passage suivent la même priorité. Le temps
  est compté **par passage**, pas en heures-personnes.
- **Observateur Faune-France sans compte `t_roles`** : catégorie « Non renseigné ». Elle n'apparaît que si elle est
  non vide, et ces observateurs sont listés dans l'annexe de contrôle.
- **Passages attendus et périodes** (paramètres du `dossier.toml`, tirés des protocoles cités dans les rapports) :
  - STOC-EPS : 2 passages attendus, du 1er avril au 8 mai et du 9 mai au 15 juin ; passage de mars (1er au 31 mars)
    optionnel, compté à part ;
  - SHOC : 2 passages, en décembre et en janvier ;
  - STOM : 1 passage, du 10 mai au 15 juillet ;
  - POP : règles des vues `v_pop*_aire_annee` ;
  - STERF : 4 passages par transect, de mai à août (protocole national, valeur à confirmer avec le coordinateur
    STERF, en paramètre).
- **STERF vrai** (validé le 17/11/2026) : un site **composé d'au moins 5 transects** et **suivi l'année du rapport**.
  Les autres sites suivis en N sont des « sites type STERF ».
- **Périmètre POP** (validé le 17/11/2026) : POP Reptile suit la même démarche que POP Amphibien, qui concorde avec le
  rapport : aires et transects des vues `v_pop*_aire_annee`. Les chiffres POP Reptile du rapport 2025 ne servent pas
  de référence (import de données ultérieur, valeurs possiblement fausses).
- **STOC** : une seule section, avec le bloc commun sur les STOC-EPS. Une sous-partie « STOC-sites » détaille les 25
  STOC-sites Natura 2000 LPO et résume en une phrase les autres STOC-sites (`STOC_SITES` hors N2000, `STOC_ONF`,
  `STOC_SITES_RNF`), comme le rapport 2025 (« 26 STOC-sites effectués sur d'autres sites »). Un seul jeton `stoc`. Les
  chiffres de recoupement du §6 portent sur les seuls STOC-EPS.
- **STOM** : l'aire est le groupe de sites. Le module ne contient que des sites LPO (31 sites, tous dans le jeu
  `STOM_Pub`) : pas de filtre. Les sites des autres structures (PN Écrins, PN Vanoise, CREA, Asters) restent dans le
  texte fixe. Le **massif** n'est pas disponible : `v_export_stom_sites.secteur` est vide et le type `MAS` de `ref_geo`
  ne contient aucune zone. La version 1 détaille le STOM par département ; le détail par massif viendra si une couche
  de massifs est chargée.
- **STERF** : les objectifs par zone biogéographique utilisent `ref_geo` type `ZBIOG` (4 zones).

## 6. Validation

En plus des étapes de `CLAUDE.md` :
- **Recoupement avec le rapport 2025** (dry-run, zone = région AuRA, année 2025) : écarts attendus seulement à cause
  des saisies tardives.

  | Indicateur | Rapport 2025 | Base au 16/11/2026 |
  |---|---|---|
  | carrés STOC-EPS | 298 | 304 |
  | observateurs STOC-EPS | 208 | 216 |
  | carrés STOC depuis 2001 | 680 | 680 |
  | carrés SHOC 2024-25 | 130 | 130 |
  | STERF : transects / observateurs / données | 248 / 22 / 5 462 | 248 / 21 / 5 469 |
  | STOM : sites LPO | 29 | 30 groupes de sites suivis (298 points) |
  | STERF : STERF vrais + sites type STERF | 21 + 25 = 46 | 49 groupes de sites suivis |
  | POP Reptile : aires (transects) enregistrées | 41 (125) | 85 (235) : la référence est la vue, pas le rapport (§5.11) |
  | POP Reptile : transects suivis | 29 (6 passages) | 118 transects visités, 36 aires (référence : la vue) |
  | POP Amphibien : aires (sites) enregistrées | 23 (120) | 24 (118) |
  | POP Amphibien : sites suivis | 42 (3 passages) | 50 sites visités, 8 aires |

- **Dry-run sur un département** (Savoie : 25 carrés STOC, 6 SHOC en 2025 d'après le rapport) pour vérifier le
  détail par aire et le masquage des sections vides.
- Tests unitaires des analyses communes avec un jeu factice construit à la main.

## 7. Laissé au constructeur

- La forme des tables temporaires et le découpage en briques (une brique par protocole et des briques communes, ou
  une brique par bloc d'analyse).
- Les graphiques (bibliothèque déjà utilisée dans le dépôt).
- L'ordre de livraison. Proposition : socle commun + STOC, puis les modules monitoring, puis les analyses propres à
  chaque protocole.
- Le projet QGIS (une mise en page par protocole, ou une mise en page commune filtrée).

## 8. Questions ouvertes

Les questions de la relecture ont reçu une réponse le 17/11/2026 (§5.3, §5.10, §5.11). Reste à confirmer pendant la
construction, sans bloquer le plan :
- le nombre de passages STERF attendus par transect (paramètre, 4 par défaut), avec le coordinateur STERF ;
- les temps forfaitaires SHOC et STOM (paramètres), avec les coordinateurs.
