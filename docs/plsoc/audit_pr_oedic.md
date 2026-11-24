# Audit du schéma `pr_oedic` (base gnlpoaura)

Audit réalisé le 20/10/2026, en lecture seule (catalogue, définitions des vues, comptages ; aucune donnée nominative
consultée). Objectif : trier ce qui relève de l'ancienne base et ce qui vient de Mergin, repérer les défauts, et
préparer la réorganisation des vues pour le suivi, l'analyse et le rapport annuel du PLSOC.

---

## 1. Synthèse

1. **Deux mondes coexistent sans se parler.**
   - L'historique 2015-2025 est dans des tables plates (`couple`, `nid`…), lues par les vues `v_info_*`.
   - Mergin (2026 et après) est lu par les vues `v_couples`, `v_nids`…
   - **Aucune vue ne couvre plusieurs années** en mêlant les deux.
   - Les vues `partage.lpo69_*_annee_en_cours` renvoient **0 ligne** depuis janvier 2026.
2. **Les vues Mergin sont de bonne qualité** : statut et succès calculés à partir des événements, dates clés, protection, œufs, contrôle d'anomalies. Ce sont le bon socle pour la suite. Leurs définitions s'écartent toutefois de celles de l'historique et du rapport (§ 4.3).
3. **L'historique est exploitable, mais fragile.**
   - Le trigger `maj_nid` renumérote `id_nid` avec l'année courante à chaque déplacement d'un nid. Les nids 2015-2019 ont été renumérotés en 2020, 23 nids de 2024 portent un identifiant « 2025 » et un nid de 2025 a été renommé en 2026.
   - Ces triggers sont **toujours actifs**.
4. **Trois vues historiques donnent des chiffres faux** :
   - `v_info_phenology` s'arrête en 2023 ;
   - `v_info_par_limite_administrative` perd les couples sans nid (17 sur 93 en 2024) ;
   - `v_nid_info_2025` filtre sur l'identifiant, qui n'est pas fiable.
5. **Une partie des données du rapport n'est pas en base** : rassemblements 2020 et 2022-2025, nids APIE, parcelles menacées, suivis des mesures après 2021, baguage 2019-2025. Elles vivent dans des fichiers chargés par le projet QGIS `pr_oedic4`.
6. **Le ménage est simple à faire** :
   - 12 tables distantes sont importées deux fois dans `from_mergin` ;
   - 6 tables « mares » d'un autre projet sont dans le même schéma ;
   - des noms contiennent des espaces, des accents ou des majuscules ;
   - des vues par année (`v_nid_info_2024`, `v_nid_info_2025`).
7. **Données personnelles** : des noms, téléphones et mails d'exploitants et de propriétaires sont exposés dans `pr_oedic` **et dans le schéma `partage`** (§ 4.7).

---

## 2. Flux actuels

```text
SAISIE 2026 →  Mergin (base « mergin », schéma oedic = DDL)
                    │  postgres_fdw (serveur « mergin », correspondance d'utilisateur de dbadmin)
                    ▼
               from_mergin.t_oedic_* / cor_oedic_*   (tables distantes)
                    │
                    ▼
               pr_oedic.v_couples_ref → v_nids → v_couples → v_observations → v_controle_anomalies
                    │                                          (+ vues de détail JSON, v_suivi_global)
                    ▼
               projet QGIS de coordination (non stocké dans pr_oedic.qgis_projects)

HISTORIQUE  →  QField 2022-2025 → qf_obs_jour (2 419 passages)  ┐
2015-2025      saisie QGIS directe + triggers crea_* / maj_*     ├→ couple / nid / oeufs / regroupement / mesurecomp…
                                                                 ┘        │
                                                                          ▼
                                       v_info_* , v_nid_info_20xx , partage.lpo69_* , vm_parcelles_*
                                                                          │
                                                                          ▼
                       projets QGIS pr_oedic2, pr_oedic3, pr_oedic4 (fév. 2026), « pr_oedic ac Atlas »
                       + nombreux fichiers locaux → rapport annuel
```

À noter : **aucun des 4 projets QGIS stockés dans `pr_oedic.qgis_projects` n'utilise les vues Mergin**. Le projet de
coordination 2026 est donc ailleurs (fichier). Il faudra l'inventorier avant tout renommage.

---

## 3. Inventaire classé

Légende de l'état : ✅ sain · ⚠️ à corriger · 🗄️ à archiver · 🗑️ à supprimer (après vérification des usages)

### A. Données historiques 2015-2025 (à figer)

| Objet | Lignes | Contenu | État |
|---|---|---|---|
| `couple` | 1 049 | 1 ligne par couple et par année (2015-2025). Champs : milieu (`vocation_p`), culture (`vegetation`), lieu-dit, parcelle, bagues adultes depuis 2020 | ✅ identifiants uniques, toutes les géométries valides. 18 couples hors des 7 secteurs, 10 sans lieu-dit. Triggers actifs ⚠️ |
| `nid` | 874 | 1 ligne par nid : statut, succès, dates clés (couvaison, éclosion, échec, protection, poussins), Mayfield, bagues poussins | ⚠️ `id_nid` renumérotés (§ 4.2), 30 `stat_repro` = noms de colonnes en 2022, `oui`/`Oui`, `''` et NULL mélangés |
| `oeufs` | 143 | biométrie des œufs (2020, 2023-2025) | ✅ (+ `v_oeufs_auto` : âge et date de ponte estimés) |
| `qf_obs_jour` | 2 419 | **passages de terrain QField 2022-2025** (statut, nombre d'adultes/poussins/œufs, hauteur de végétation, protection, bagues), dont **331 passages sans oiseau** | ✅ précieux : c'est le seul historique « par passage ». Lien à `nid` cassé pour 2025 (4 liens sur 687) |
| `t_verif_2024`, `t_verif_2025` | 486 / 139 | contrôles de distance observation-couple (tous « OK ») | 🗑️ outil ponctuel, sans clé primaire |
| `regroupement` | 48 | rassemblements postnuptiaux 2015-2019 et 2021 (effectif max, dates) | 🗄️ 2020 et 2022-2025 absents (fichiers) |
| `regroupement_annuel` | 0 | table prévue (effectifs par quinzaine), jamais remplie | 🗑️ |
| `mesurecomp` | 29 | parcelles compensatoires (22 projets) : polygone, porteur, arrêté (12/29), surfaces (14/29), année de mise en place | ⚠️ référentiel à compléter et à garder |
| `etatmescomp` | 17 | état annuel des mesures 2018, 2019, 2021 | 🗄️ remplacé par `t_suivis_mesure` (Mergin) |
| `Baguage` | 7 | baguage 2018 avec biométrie | 🗄️ le baguage 2019-2025 n'est que dans les champs `BaguPULL_*` / `BaguAD_*` |
| `donnees brutes` | 3 624 | ancien import de données d'observateurs (dates en texte non exploitables, noms) | 🗑️ remplacé par `vm_donneesbrutes` |
| `parcelles agricoles` | 8 126 | îlots avec relevé de culture 2021-2022 (645 relevés) | 🗄️ |

### B. Référentiels et couches de contexte (à garder et renommer)

| Objet | Contenu | État |
|---|---|---|
| `secteur` | les 7 secteurs du rapport | ✅ |
| `Zone_d_etude`, `Contour zone etude` | périmètre du plan (3 entités / 1 contour) | ⚠️ doublon à fusionner, noms à revoir |
| `zones_prospection`, `chemins`, `routes` | zones et itinéraires de prospection (≈ 110 km chacun) | ✅ à documenter (année ?) |
| `commune` | communes (1 246), utilisées par les triggers | 🗑️ doublon de `ref_geo.l_areas` (type 25) |
| `plu` | zonage PLU simplifié (U, AU, A, N), sans millésime | ⚠️ dater la source |
| `parcelle` | cadastre (230 484), attributs de gestion (compensation, exploitant, propriétaire, zonage), sans millésime | ⚠️ 89 Mo, attributs à dater |
| `ref_statut_evenement` | nomenclature des événements de nid (Mergin) | ✅ |
| `qgis_projects` | 4 projets QGIS (2021-2026) | ⚠️ inventaire des couches : § 2 |

### C. Données personnelles (à isoler)

| Objet | Contenu |
|---|---|
| `t_annuaire_exploitant` (78), `t_annuaire_proprio` (43), `t_annuaire_structure` (6) | noms, téléphones, mails, adresses |
| `parcelle_avec_exploitant` (vue) | parcelle + coordonnées de l'exploitant |
| `partage.lpo69_parcelle_exploit`, `partage.lpo69_parcelle_proprietaires` | idem, **dans le schéma `partage`** |
| `from_mergin.t_oedic_exploitants` (+ doublon `t_exploitants`) | exploitants saisis sur Mergin |

### D. Vues d'analyse historiques (`v_info_*`, lisent `couple` et `nid`)

| Vue | Contenu | État |
|---|---|---|
| `v_info_generale` | bilan par année (couples, nicheurs, nids, succès, poussins, envols) | ✅ reproduit exactement le rapport 2024 |
| `v_info_par_milieu` | idem par milieu (culture si agricole) | ✅ |
| `v_info_par_type_protection` | idem par type de protection | ✅ |
| `v_info_par_limite_administrative` | idem par EPCI et commune | ⚠️ commune prise sur la géométrie **du nid** : les couples sans nid tombent en « NULL » (17/93 en 2024) |
| `v_info_phenology` | couples présents par jour | ⚠️ série de dates **codée en dur 2015-2023** : 2024 et 2025 absents |
| `v_info_couple_par_nb_nid` | couples par nombre de nids | ✅ |
| `v_nid_info_2024`, `v_nid_info_2025` | nids + couple de l'année | ⚠️ filtre `id_nid LIKE '%2025%'`, faux à cause des renumérotations. Une vue par année : 🗑️ |
| `v_oeufs_auto` | âge des œufs, dates de ponte/éclosion estimées | ✅ à reprendre sur Mergin |

### E. Vues Mergin (2026 →, lisent `from_mergin`)

| Vue | Rôle | Commentaire |
|---|---|---|
| `v_couples_ref` | socle couple : année, commune (ref_geo), `code_couple` | même format de code que l'historique (année + INSEE + n° + C) ✅ |
| `v_nids` | **cœur métier** : agrège les événements → dates clés, état du nid, succès calculé, protection, Mayfield, œufs, bagues | ✅ très complet. Définitions à aligner (§ 4.3) |
| `v_couples` | couple + statut de nidification + synthèse des nids | ✅ |
| `v_observations` | journal unifié observations + événements | ✅ 130 observations non rattachées à un couple en 2026 |
| `v_controle_anomalies` | contrôles (doublons, liens vides/orphelins, géométrie, statuts non reconnus, mesures hors plage) | ✅ très utile : 24 « DOUBLON_VUE » et 13 « LIEN_ORPHELIN » bloquants en 2026 |
| `v_suivi_global` | fil chronologique tous types | ✅ coordination |
| `v_couples_detail`, `v_nids_detail`, `v_couple_individus`, `v_couple_observations`, `v_nid_evenements`, `v_nid_oeufs`, `v_evenement_poussins`, `v_oeufs_detail` | détails en JSON pour les formulaires / infobulles QGIS | ✅ usage coordination |
| `v_observations_isolees` | observations sans couple | ✅ contrôle |

**Pas encore exposés** : `t_oedic_parcelles`, `t_oedic_suivis_parcelle`, `t_oedic_suivis_mesure`, `t_oedic_regroupement`, `t_oedic_exploitants`.

### F. Vues matérialisées

| Objet | Contenu | État |
|---|---|---|
| `vm_donneesbrutes` | données Œdicnème de la synthèse GeoNature dans la zone d'étude (19 877, de 1961 à 2026), rafraîchie régulièrement | ✅ utile (phénologie, rassemblements, hors suivi) |
| `vm_parcelle` | cadastre + commune (doublon de `parcelle`, 90 Mo) | ⚠️ |
| `vm_parcelles_hab_oedic` | parcelles ayant accueilli un couple (toutes années) | ⚠️ ne lit que l'historique |
| `vm_parcelles_regroupement` | parcelles de rassemblement | ⚠️ historique seulement |

### G. Dépendants hors schéma

8 vues `partage.lpo69_*` lisent les tables historiques. Les 3 vues « année en cours »
(`coupleetnidparsecteursanneeencours`, `nombre_nids_par_milieu_annee_en_cours`, …) sont **vides en 2026**. Il faut savoir
qui les consomme (Lizmap ? partenaires ?) avant de les rebrancher ou de les supprimer.

### H. Schéma `from_mergin`

- **12 tables Mergin importées deux fois** (même table distante) : `t_couples` / `t_oedic_couples`, `t_nids` /
  `t_oedic_nids`, `t_evenement_nids` / `t_oedic_evenement_nids`, `t_observation`, `t_oeufs`, `t_parcelles`,
  `t_regroupement`, `t_suivis_mesure`, `t_suivis_parcelle`, `t_exploitants`, `cor_poussin_individus`,
  `oedic_cor_couple_individus`. Les vues n'utilisent que les versions `t_oedic_*` / `cor_oedic_*` → les autres sont
  🗑️ (après vérification du projet QGIS de coordination).
- 6 tables `mares_*` + `v_synthese_projet_annee` (autre projet) : à ranger dans un schéma à part (`from_mergin_mares` ?).
- Droits : `from_mergin` est accessible à `dbadmin` et `dt`. Les vues de `pr_oedic` appartiennent à `dbadmin` et passent par sa correspondance d'utilisateur FDW. C'est un bon principe : **les lecteurs passent par les vues**. Le compte `lpoaura_afo` n'a pas de correspondance et ne lit `from_mergin` qu'à travers elles.

---

## 4. Constats détaillés

### 4.1 Aucune vue pluriannuelle

Pour le rapport comme pour l'analyse, il faut des séries 2015 → N. Aujourd'hui :
- `v_info_*` couvre 2015-2025 et ne verra jamais 2026 ;
- `v_couples` et `v_nids` couvrent 2026 seulement.

C'est le chantier n° 1 (§ 5).

### 4.2 Identifiants historiques renumérotés par les triggers

`maj_nid` (BEFORE INSERT **OR UPDATE OF geom**) recalcule `id_nid = année courante + INSEE + gid + 'N'` :

| Année du nid | Préfixe de l'identifiant | Nids |
|---|---|---|
| 2015 à 2019 | 2020 | 347 (tous) |
| 2017 | 2023 | 1 |
| 2020 | 2021 | 4 |
| 2022 | 2023 | 2 |
| 2024 | 2025 | 23 |
| 2025 | **2026** | 1 (modifié cette année) |

Conséquences :
- **l'identifiant n'est pas un indicateur d'année** : la vérité est la colonne `annee` ;
- 51 passages QField 2024 ne retrouvent plus leur nid ;
- tout déplacement d'un nid historique dans QGIS change son identifiant (et échoue s'il a des œufs, à cause de la clé étrangère).

Côté couples, 37 identifiants ont un préfixe d'année décalé : ce sont des couples saisis l'année suivante (`crea_couple` utilise `now()`).

→ **Désactiver les triggers `crea_*` / `maj_*` et passer les tables historiques en lecture seule.**

### 4.3 Définitions qui diffèrent entre l'historique, Mergin et le rapport

| Notion | Historique / rapport | Vues Mergin | Effet |
|---|---|---|---|
| Couple nicheur | nicheur certain = un nid existe ; « couple observé » = nicheur probable | certain = un nid ; probable = ≥ 2 contacts espacés de ≥ 7 j ; possible = sinon | séries comparables pour les « certains » ; « probable » à recaler |
| Succès probable / échec probable | grille du rapport : couvaison puis oiseaux invisibles (végétation) = **succès probable** (scénario 4) ; éclos puis adultes absents et végétation rase = échec probable (scénario 5) | couvaison sans éclosion en fin de saison = **échec probable** ; éclos sans envol = succès probable | ⚠️ en 2026, 38 nids en « succès probable » contre 10 certains. Le scénario 4 et le scénario 5 sont inversés ou absents |
| Mayfield | rapport : exposition depuis la 1re preuve de nidification, période de 64 j (ponte → envol) | `mayfield_jours_exposition` = **incubation seulement** (couvaison → éclosion/échec) | taux non comparables. Calculer incubation et élevage séparément, puis les combiner |
| Validation experte | `succ_repro` historique = valeur validée | succès **calculé** ; `t_nids.succes_repro` saisi (booléen) sert de contrôle | prévoir un champ « succès validé » à 4 classes (le « lavage » par dire d'expert) |
| Protection | piquetage / accès interdit / information | événements PROT_PIQUET, PROT_ACCES (+ DEPROT) | ✅ correspondance directe |
| Cause d'échec | liste historique mêlant causes et fins d'exposition (« envol jeune », « croissance culture ») | texte libre, vide en 2026 | nomenclature à définir |

### 4.4 Ce que l'historique contenait et que Mergin ne saisit pas (encore)

| Information | Historique | Mergin | Usage |
|---|---|---|---|
| Milieu (agricole, bassin, friche, carrière, entreprise, parking, aéroport, toiture…) | `couple.vocation_p` (100 %) | ❌ | rapport § 3.2, protection, toutes les analyses d'habitat |
| Culture / couvert | `couple.vegetation` | ❌ (déductible du RPG avec un an de retard : RPG 2015-2024 dans `lpoaura_afo`) | habitat agricole |
| Lieu-dit | `couple.lieu_dit` | ❌ | tous les tableaux du rapport |
| Hauteur de végétation au passage | `qf_obs_jour.hauteur_vegetation` (2022-2025) | ❌ | détectabilité, succès |
| Passage sans oiseau | `qf_obs_jour` « pas d'oiseaux » (331) | ❌ (pas de nombre 0 explicite) | effort, mesures compensatoires, phénologie |
| Parcelle compensatoire oui/non | `nid."Parcelle compensatoire"` | ❌ (déductible par `mesurecomp`) | suivi des mesures |
| Lien nid → exploitant | `nid.id_exploit` | ❌ (seulement `t_parcelles.numero_pacage`) | protection agricole |
| Bague lue lors d'une observation | — | ❌ (bagues seulement sur couple et poussin) | survie, fidélité |
| Territoire pluriannuel | ❌ | ❌ | fidélité au site, occupation, durée de vie des sites |

### 4.5 Données du rapport hors base

Le projet QGIS `pr_oedic4` (février 2026) charge des fichiers locaux :
- « Rasspostnup 2025 » (rassemblements) ;
- « Nids APIE » ;
- « Couples Mes Comp 2025 » ;
- « Parcelles menacées 2015 2025 » ;
- « Nouvelles parcelles menacées 2025 » ;
- les PENAP et la ZAP.

Ce sont autant de couches à rapatrier en base (référentiels) ou à recréer par requête.

### 4.6 Qualité de la saison 2026 (Mergin)

- 90 couples, 81 nids, 605 observations, 241 événements.
- 130 observations non rattachées à un couple. 3 nids sans couple. 2 statuts d'événement non reconnus.
- Distance observation-couple : médiane 18 m, 90 % sous 98 m, 99 % sous 517 m.
- `v_controle_anomalies` : 24 doublons bloquants, 24 liens orphelins bloquants, 131 liens vides importants.
- `cause_echec` vide pour tous les nids. Protection saisie sur 11 nids.

### 4.7 Hygiène du schéma

- **Noms** : espaces, accents, majuscules (`"donnees brutes"`, `"parcelles agricoles"`, `"Baguage"`, `"Contour zone etude"`, colonnes `"BaguREAL?"`, `"Parcelle compensatoire"`). Ils sont pénibles en SQL et cassent certains outils.
- **Types** : `couple.annee` en texte, `nid.annee` en numérique, `qf_obs_jour` mélange les codes.
- **Propriétaires** : `geonature`, `lpo69`, `lpoaura_afo`, `dbadmin`.
- **Doublons** : `commune` / `ref_geo` ; `parcelle` / `vm_parcelle` (180 Mo à eux deux).
- **Performance** : `v_couples` → `v_nids` → FDW, avec une recherche de commune par ligne. C'est acceptable pour 90 couples, mais à **matérialiser** pour l'analyse pluriannuelle et le rapport.
- **RGPD** : les annuaires et les vues « parcelle + exploitant / propriétaire » sont lisibles par plusieurs rôles, dont `lizmap` pour certaines tables. Il faut vérifier qui y accède réellement. La copie dans `partage` est à reconsidérer.

---

## 5. Historique dans Mergin, ou deux bases ?

**Recommandation : ne pas charger l'historique dans Mergin.** Mergin est une base de **saisie terrain** synchronisée sur les mobiles. Y mettre dix ans d'historique alourdit la synchronisation, expose l'historique validé à des modifications accidentelles et lie l'archive à l'évolution des formulaires d'une saison à l'autre.

À la place, construire **dans gnlpoaura un historique au format du modèle Mergin**, puis des vues d'analyse qui unissent les deux sources :

```text
pr_oedic_hist (figé)          from_mergin (vivant)
  h_couples, h_nids,             t_oedic_couples, t_oedic_nids,
  h_evenements, h_observations   t_oedic_evenement_nids, t_oedic_observation
  (migration unique, colonne source = 'shape' | 'qfield')
             └──────────────┬──────────────┘
                            ▼
        pr_oedic : vues d'analyse « toutes années » (mêmes règles de calcul pour toutes les sources)
```

Deux niveaux possibles :

| Option | Principe | Effort | Intérêt |
|---|---|---|---|
| **B : indicateurs** (court terme) | vues annuelles qui unissent les indicateurs historiques (valeurs validées de `couple`/`nid`) et les indicateurs Mergin (`v_couples`/`v_nids`) | faible | suffit au rapport 2026 (séries, tableaux) |
| **A : événements** (moyen terme) | migration de l'historique en événements : dates de `nid` → événements COUV/POUS/ECHEC/PROT pour 2015-2021 ; `qf_obs_jour` → **vrais passages** 2022-2025 (y compris les passages sans oiseau) | moyen | mêmes calculs pour toutes les années (phénologie, Mayfield, effort de suivi) |

Démarrer par B pour le rapport 2026, puis A pendant l'hiver. Pour l'historique, **garder les valeurs validées** (succès, statut) comme référence et ne pas les recalculer.

---

## 6. Organisation et nommage proposés

| Préfixe / schéma | Usage | Exemples |
|---|---|---|
| `pr_oedic_hist` (schéma) | tables historiques figées, triggers désactivés, lecture seule | `couple`, `nid`, `qf_obs_jour`… (renommées en `h_*` à la migration A) |
| `ref_*` | référentiels | `ref_secteur`, `ref_zone_etude`, `ref_mesure_compensatoire`, `ref_statut_evenement`, `ref_milieu`, `ref_cause_echec`, `ref_site_rassemblement`, `ref_carriere` |
| `v_terrain_*` | coordination, saison en cours | `v_terrain_couples`, `v_terrain_nids`, `v_terrain_a_visiter` (jours depuis le dernier passage, éclosion attendue), `v_terrain_protections` |
| `v_ctrl_*` | contrôle de la saisie | `v_ctrl_anomalies` (+ contrôles historiques) |
| `mv_ana_*` | analyse pluriannuelle harmonisée, matérialisée | `mv_ana_couple_annee`, `mv_ana_nid`, `mv_ana_evenement`, `mv_ana_passage_mesure`, `mv_ana_regroupement`, `mv_ana_individu` (bagues) |
| `v_rap_*` | agrégats du rapport | `v_rap_bilan`, `v_rap_commune`, `v_rap_secteur`, `v_rap_milieu`, `v_rap_protection`, `v_rap_phenologie_decade`, `v_rap_mayfield`, `v_rap_causes_echec`, `v_rap_mesures`, `v_rap_rassemblements`, `v_rap_baguage`, `v_rap_parcelles_menacees` |

Règles :
- noms en minuscules, sans espace ni accent ;
- une vue = une question ;
- jamais de vue « par année » : l'année est une colonne ;
- un commentaire SQL (`COMMENT ON`) par vue ;
- les anciens noms restent provisoirement en vues de compatibilité pour les projets QGIS, puis sont supprimés.

---

## 7. Questions → données → faisabilité

Légende : ✅ possible maintenant · 🟡 après harmonisation (§ 5) · 🟠 nouveau champ ou nomenclature · 🔴 donnée externe

| Thème | Questions | Données | Faisabilité |
|---|---|---|---|
| Effectifs | évolution 2015 → N, par secteur, commune, collectivité ; nicheurs certains/probables | couples | ✅ hist., 🟡 en série |
| Répartition | noyaux, déplacements (vers la périphérie, les milieux artificiels), densité | couples + secteurs | 🟡 |
| Habitat | milieux et cultures occupés, évolution, sols (fersialsols), lien avec la PAC | `vocation_p`, RPG 2015-2024, pédologie | ✅ hist. · 🟠 Mergin (milieu) · 🔴 pédologie |
| Phénologie | arrivée, cantonnement, ponte (rétro-calcul par la biométrie des œufs), éclosion, envol, hivernage ; tendance | événements, œufs, synthèse | 🟡 (✅ 2022+ avec `qf_obs_jour`) |
| Reproduction | succès par milieu, secteur, protection, rang de ponte ; taille de ponte ; pontes de remplacement ; productivité | nids, événements | ✅ / 🟡 |
| Mayfield | survie journalière incubation / élevage, par milieu et par protection | événements | 🟡 + alignement de méthode (§ 4.3) |
| Causes d'échec | prédation, travaux agricoles, dérangement, végétation | cause | 🟠 nomenclature |
| Protection | efficacité du piquetage (survie des nids protégés ou non en milieu agricole), délai découverte → protection | événements PROT | ✅ 2026, 🟡 hist. |
| Mesures compensatoires | taux d'occupation, délai de colonisation, succès sur mesure / hors mesure, effet de la gestion (recouvrement, hauteurs, clôture, fréquentation) | `mesurecomp` + `t_suivis_mesure` + couples | ✅ occupation · 🟠 passages négatifs · état : Mergin |
| Rassemblements | sites, effectifs max, phénologie automne/hiver, toitures | `t_oedic_regroupement` (cet hiver), synthèse | 🟠 effectif en entier, site de rassemblement · 🔴 2022-2025 en fichiers |
| Démographie / baguage | retour des poussins, âge de 1re reproduction, fidélité au site et au partenaire, dispersion natale, survie | bagues couples + poussins + **lectures de bagues** | 🟡 consolidation 2018-2026 · 🟠 lecture de bague sur une observation |
| Fidélité au territoire | réoccupation des sites d'une année sur l'autre | territoire pluriannuel | 🟠 (ou regroupement spatial automatique) |
| Menaces | parcelles U/AU occupées, surfaces détruites ou menacées, projets | PLU (à dater), couples | ✅ / 🟠 « projet identifié » |
| Effort de suivi | passages par couple, pression d'observation, détectabilité selon la hauteur de végétation | observations, `qf_obs_jour` | 🟡 · 🟠 hauteur de végétation |
| Météo | succès et phénologie selon pluie/froid | Météo-France | 🔴 |
| Données opportunistes | compléments hors suivi (Faune-France) | `vm_donneesbrutes` | ✅ |

---

## 8. Pistes pour préparer la saison 2027 (cet hiver)

**Formulaires Mergin**
- Milieu (liste), culture/couvert, lieu-dit (ou calcul automatique depuis une couche de toponymes).
- Hauteur de végétation à chaque passage.
- Événement ou observation « passage sans oiseau » (couple et mesure compensatoire).
- Cause d'échec (liste), succès **validé** à 4 classes + auteur/date de validation.
- Lecture de bague sur une observation (`cor_observation_individus`).
- Regroupement : effectif en **entier**, rattaché à un **site de rassemblement** plutôt qu'à une parcelle.

**Base**
- Désactiver les triggers historiques, figer `pr_oedic_hist`.
- Corriger ou supprimer `v_info_phenology`, `v_info_par_limite_administrative`, `v_nid_info_20xx`.
- Supprimer les doublons de `from_mergin`, déplacer les mares.
- Revoir les droits sur les données personnelles.
- Matérialiser les vues d'analyse (rafraîchissement nocturne).
- Rapatrier les couches « fichiers » (rassemblements, parcelles menacées, PENAP/ZAP, nids APIE).

**Outils**
- QGIS de coordination : liste « à visiter » (jours depuis le dernier passage, éclosion attendue), nids agricoles non protégés.
- Contrôles supplémentaires : succès calculé ≠ succès validé, couple sans passage depuis 15 jours.
- Rapport : générateur `plsoc` (cf. analyse des rapports Word), fiches par mesure compensatoire.

---

## 9. Étapes proposées

Script de création du nouveau schéma : [sql/pr_oedic_news.sql](sql/pr_oedic_news.sql).

| Étape | Contenu | Échéance indicative |
|---|---|---|
| 1. Valider l'audit | relire, compléter (projet QGIS de coordination, consommateurs des vues `partage`) | novembre |
| 2. Sécuriser | désactiver les triggers historiques, supprimer les doublons FDW, droits RGPD | novembre |
| 3. Harmoniser (option B) | référentiels `ref_*`, vues `v_rap_*` toutes années → chiffres du rapport 2026 depuis la base | novembre-décembre |
| 4. Définir les questions | atelier avec l'équipe sur le tableau § 7 : priorités, définitions (§ 4.3) | décembre |
| 5. Formulaires 2027 | champs § 8, nomenclatures | janvier-février |
| 6. Migration (option A) | `qf_obs_jour` 2022-2025 puis nids 2015-2021 en événements | hiver 2027 |
| 7. Analyses et rapport | vues `mv_ana_*`, générateur de rapport | 2027 |
