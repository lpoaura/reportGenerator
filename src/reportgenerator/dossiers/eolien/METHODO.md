# Rapport éolien : process et contenu

**Rapport produit** : « Synthèse des données d'oiseaux et de chiroptères dans le cadre d'un projet éolien » (titre `{{TITRE_RAPPORT}}`, « … d'oiseaux … » seul si la partie chiroptères n'est pas demandée), avec une partie chiroptères (section 10). C'est un document de base : le générateur remplit les chiffres, les tableaux et les cartes, puis le collègue rédige l'analyse.

**Déclenchement** : la valeur `analyse_eolien` dans le champ `list_analyse` du formulaire QGIS. Elle active aussi l'analyse optionnelle `chiropteres` (bloc `[declencheurs]` du `dossier.toml`).

**Fichiers du dossier** :
- `dossier.toml` : briques et paramètres ;
- `template.docx` : modèle Word ;
- `qgis/projet_eolien.qgs` : projet QGIS modèle, avec ses pièces jointes `projet_eolien_attachments.zip` ;
- `ref_chiropteres.csv` : référentiel de vulnérabilité des chiroptères (section 10) ;
- `METHODO.md` : ce document.

**Origine** : la méthode reprend l'ancien workflow R (`traitement_generale_v2.R`, `script_sql/*.sql`, `lancement_carte_qgis.py`), avec ses bugs corrigés (voir la section 9).

---

## 1. Process de génération

```text
Formulaire QGIS (list_analyse = analyse_eolien)
  │
  ▼
socle_data             VM lpoaura_afo.vm_reportgenerator_data_<date>_<code> (une par génération) :
                       oiseaux et chiroptères, 10 dernières années, jusqu'à 20 km,
                       mailles 1 km, note de sensibilité éolienne et anneau de chaque observation
  │
  ▼
projet_info            période, rayons, localisation
perimetres_anneaux     répartition par anneau + texte de connaissance
especes_enjeux_eolien  espèces à enjeux / autres espèces
nidification           rapaces et grands voiliers nicheurs
dortoirs               dortoirs de rapaces et grands voiliers
migration              données de migration
  │                    → textes et tableaux du Word, copies Excel dans tables/
  ▼
couches_qgis_eolien    12 couches GPKG vm_eolienne_* dans data/ (noms et champs du workflow R + hors_region)
chiropteres           (optionnel) connaissance, vulnérabilité, gîtes, 5 couches *chiro* (section 10)
  │
  ▼
cartography            toujours en dernier : copie du projet QGIS, re-lien des couches,
                       export de toutes les mises en page en PNG
  │
  ▼
Rendu Word             template.docx rempli → outputs/<zone>/<zone>.docx
```

La VM est supprimée à la fin, même en cas d'erreur. La date de génération n'est mise à jour en base qu'en cas de succès : une demande en échec reste en attente et sera retentée.

### Fichiers produits

```text
outputs/<zone>/
├── <zone>.docx                      rapport à compléter
├── projet_<zone>.qgs                projet QGIS de la zone (+ _attachments.zip, .render.json)
├── data/                            couches GPKG : vm_eolienne_* + donnees_brutes, zone_etude…
├── maps/                            Carte1_….png … Carte18_….png
└── tables/                          2_oiseaux_especes_enjeux.xlsx, 2_oiseaux_especes_autres.xlsx,
                                     3_nidif_rapaces.xlsx, 4_nidif_ardeides.xlsx,
                                     5_dortoirs.xlsx, 6_migration.xlsx
```

⚠️ **`data/` contient des données d'espèces sensibles**, en particulier des sites de nidification localisés au point. Ce dossier sert à travailler dans QGIS ; il ne doit pas être transmis tel quel au commanditaire.

---

## 2. Données prises en compte

| Critère | Valeur | Paramètre (`dossier.toml`) |
|---|---|---|
| Taxons | oiseaux et chauves-souris, rang espèce ; les sous-espèces sont rattachées à leur espèce. Pour les chiroptères seulement, les genres et complexes sont gardés (section 10) | `groupes_taxo`, `chiro_rangs_non_especes` |
| Période | depuis le 1er janvier de (année en cours − 10) | `annees` |
| Validation | statuts 0 (en attente), 1 et 2 | `statuts_validation` |
| Emprise | zone d'étude + 20 km | dernier élément de `anneaux_km` |
| Géométries | points uniquement (multipoints et polygones exclus : ~0,3 % des données) | — |
| Grille | mailles de 1 km (`M1`), **calculées spatialement** (voir ci-dessous) | `grille` |
| Doublons entre sources | même taxon, même jour, même cellule de 100 m : seule la source la mieux classée est gardée | `sources_prioritaires` |
| Liste rouge régionale | `lr_aura` | `lr_regionale` |
| Sensibilité éolienne | note 0-4 de `partage.sensibilite_oiseaux` | `sensibilite_eolien` |

Le champ **buffer** du formulaire **n'est pas utilisé** : l'emprise est fixée par les anneaux.

### Contrôles de qualité des données (audit sur la zone de test)

Un audit a comparé la synthèse brute et la VM sur la zone « TEST EOLIEN » (20 km, 10 ans). Corrections apportées dans la VM (elles valent aussi pour le rapport générique) :

| Constat | Effet avant correction | Correction |
|---|---|---|
| Le précalcul `cor_area_synthese` ne relie pas les données récentes à leur maille | **16 262 données d'oiseaux perdues** (7 %), surtout les plus récentes | Maille calculée spatialement (`ST_Intersects` avec la grille). Une donnée hors grille reste dans la VM, sans maille |
| Les mêmes données sont importées par plusieurs sources (faune-france et gn2pg_cen_auv) | ~5 900 données comptées deux fois | Dédoublonnage `sources_prioritaires` : pour un même taxon, un même jour et une même cellule de 100 m, seule la source la mieux classée est gardée. Deux données d'une même source ne sont jamais fusionnées |
| Le comportement saisi dans VisioNature (« Migration active », « Dortoir / reposoir ») est dans la synthèse étendue, pas dans la nomenclature | Dortoirs et migration sous-estimés | Le champ `comportement` est utilisé (voir Sélections) |
| `mv_c_statut` contient quelques taxons en double | Données dupliquées pour ces taxons | Une seule ligne de statuts par taxon |
| `partage.sensibilite_oiseaux` est indexée par `cd_nom` (parfois un synonyme) | Espèces sans note de sensibilité | Rattachement par TAXREF au `cd_ref` (+10 espèces) |

Ce qui reste à savoir pour bien lire les résultats (signalé dans le texte du rapport, « Précautions de lecture », quand c'est significatif) :
- **Aire d'étude hors région** : la base ne contient pas de données hors Auvergne-Rhône-Alpes (sur la zone de test, 37 % de l'aire). La phrase est ajoutée au-delà de 1 %, et la couche `vm_eolienne_hors_region` permet de griser ce secteur sur les cartes (`region_donnees`, `region_libelle`).
- **Données localisées au lieu-dit** (`precision_geo` = `place` ou `subplace`, 24 % des données d'oiseaux sur la zone de test) : elles sont placées au centroïde du lieu-dit. Un seul point peut regrouper plus de 20 000 données. La phrase est ajoutée au-delà de 5 %.
- **Données cachées par l'observateur** (`donnee_cachee`, 16 %) : ce sont surtout des nids d'espèces sensibles (Faucon pèlerin 291/291, Grand-duc 52/56, Circaète 40/41 sur la zone de test). Elles sont comptées et cartographiées au point précis, comme dans le R (voir 8. Points ouverts).
- **Sensibilité éolienne incomplète** : `partage.sensibilite_oiseaux` ne contient pas certaines espèces (Grande Aigrette, Chevêche d'Athéna, Aigle botté, Héron pourpré, Goéland leucophée, Busard des roseaux, Élanion blanc…). Elles ont une note vide, comptée 0 dans l'indice par maille.
- **Données en attente de validation** (statut 0) : environ 40 % des données, incluses (décision).

### Anneaux

Les zones sont **disjointes**, comme des donuts : chaque observation est comptée dans une seule zone.

| Libellé dans le rapport | Contenu |
|---|---|
| Zone d'étude | à l'intérieur du périmètre du projet |
| Contour 1 km | entre le périmètre et 1 km |
| Contour 6 km | entre 1 et 6 km |
| Contour 20 km | entre 6 et 20 km |
| Toute la zone / Ensemble des zones | somme des zones précédentes (0 à 20 km) |

Dans le R, « contour 1 km » incluait la zone d'étude.

### Sélections utilisées

Les règles sont définies dans `analysis/eolien/selections.py`.

| Sélection | Règle |
|---|---|
| Rapaces | ordres Accipitriformes, Falconiformes, Strigiformes |
| Grands voiliers | familles Ardeidae, Ciconiidae, Laridae, Gruidae |
| Nicheur | statut de reproduction `Probable` ou `Certain` |
| Dortoir | comportement VisioNature « Dortoir / reposoir », **ou** « dorto » dans la nomenclature de comportement, **ou** dans la remarque de l'observateur, sauf négation (« pas de dortoir », « aucun pré-dortoir »…) |
| Migration | comportement VisioNature « Migration… », **ou** « migr » dans la nomenclature de comportement, **ou** dans la remarque, sauf négation (« pas de migration »…) |

---

## 3. Contenu du rapport, section par section

Légende : 🤖 rempli automatiquement · ✍️ à rédiger ou compléter par le collègue (surligné en jaune dans le template).

### Page de garde, p. 2, contexte

| Élément | Placeholder | Contenu |
|---|---|---|
| Entreprise (couverture, p. 2, contexte) | ✍️ `[ENTREPRISE]` | à compléter |
| Adresse (p. 2) | ✍️ `[ADRESSE DE L'ENTREPRISE]` | à compléter |
| Localisation | 🤖 `{{LOCALISATION}}` | nom de la zone saisi dans le formulaire |
| Rayon d'étude | 🤖 `{{RAYON_MAX_KM}}` | `20` |
| Rayons des zones tampon | 🤖 `{{ANNEAUX_KM}}` | « 1 km, 6 km et 20 km » |

### §1 Matériel et méthodes

| Élément | Placeholder | Contenu |
|---|---|---|
| Période d'étude | 🤖 `{{PERIODE_ETUDE}}` | « (2016 à 2026) », année en cours − 10 → année en cours |

### §2 Localisation du projet

| Élément | Placeholder | Contenu |
|---|---|---|
| Description du territoire | ✍️ | — |
| Carte 1 | 🤖 `{{Carte1_zone_localisation}}` | zone d'étude, contours, et zonages (PNR, APB, ZNIEFF 1 et 2, RNR, RNN, Natura 2000) intersectant un rayon de 30 km ; emprise de la carte élargie de 30 km |

### §3 Connaissance des oiseaux

| Élément | Placeholder | Contenu |
|---|---|---|
| Texte de synthèse | 🤖 `{{CONNAISSANCE_OISEAUX}}` | nombre de données et d'espèces sur toute la zone, puis par anneau, du plus éloigné à la zone d'étude, puis « Précautions de lecture » si besoin (aire hors région, données au lieu-dit, voir 2.) |
| Tableau de répartition | 🤖 `{{TABLE_PERIMETRES}}` | une ligne par zone (anneaux + toute la zone), avec le nombre d'observations, le nombre d'espèces et la dernière année d'observation |
| Description de la prospection | ✍️ | — |
| Carte 2 | 🤖 `{{Carte2_Donnee_disponible}}` | observations brutes (couche `vm_eolienne`) |
| Carte 3 | 🤖 `{{Carte3_Etat_connaissance_globale}}` | nombre de données et d'espèces par maille de 1 km (`vm_eolienne_etat_connaissance`) |

### §4 Espèces à enjeux

| Élément | Placeholder | Contenu |
|---|---|---|
| Nombre d'espèces | 🤖 `{{NB_ESPECE_TOTAL}}` | espèces d'oiseaux observées **jusqu'à 20 km** |
| Nombre d'espèces à enjeux | 🤖 `{{NB_ESPECE_ENJEUX}}` | espèces répondant à **au moins un** des critères ci-dessous |
| Tableau | 🤖 `{{TABLE_ESPECES_ENJEUX}}` | tableau par anneau (section 4) |

Une espèce est « à enjeux » si elle remplit au moins un de ces critères :
- CR, EN ou VU sur la liste rouge régionale (`lr_aura`) ou sur la liste rouge France des nicheurs. Les codes migrateurs et hivernants (`VUm`, `ENw`…) ne comptent pas.
- Note de sensibilité éolienne supérieure à 2.
- Rapace ou grand voilier.

Le 2e paragraphe du §4 du template décrit cette règle.

### §5 Nidification

| Élément | Placeholder | Contenu |
|---|---|---|
| Rapaces nicheurs | 🤖 `{{NB_RAPACE_NICHEUSE}}` | rapaces nicheurs probables ou certains, jusqu'à 20 km |
| … dont à enjeux forts | 🤖 `{{NB_RAPACE_NICHEUSE_ENJEUX}}` | les mêmes, classés CR, EN, VU ou NT sur `lr_aura` |
| Tableau rapaces | 🤖 `{{TABLE_RAPACES_NICHEURS}}` | tableau par anneau + colonne « Statut nidif. » (meilleur statut observé) |
| Cartes 6 à 9 | 🤖 `{{Carte6_…}}` à `{{Carte9_…}}` | couche `vm_eolienne_nidif`, filtrée dans le projet QGIS (nocturnes, buse/faucons, milans/busards, autres diurnes) |
| Grands voiliers nicheurs | 🤖 `{{NB_ARDEIDES_NICHEUSE}}` | ardéidés, cigognes, laridés et grues nicheurs probables ou certains |
| Tableau grands voiliers | 🤖 `{{TABLE_ARDEIDES_NICHEURS}}` | tableau par anneau + statut de nidification |
| Cartes 10, 11, 11.1 | 🤖 | laridés, cigognes (Cigogne noire floutée à la maille de 5 km), hérons |
| Description des enjeux | ✍️ | — |

### §6 Dortoirs

| Élément | Placeholder | Contenu |
|---|---|---|
| Tableau | 🤖 `{{TABLE_DORTOIRS}}` | rapaces et grands voiliers ayant au moins une donnée de dortoir |
| Cartes 12 à 12.4 | 🤖 | couche `vm_eolienne_dortoirs` filtrée par groupe dans le projet QGIS |
| Description | ✍️ | — |

### §7 Migration

| Élément | Placeholder | Contenu |
|---|---|---|
| Espèces en migration | 🤖 `{{NB_MIGRATION_TOTAL}}` | toutes les espèces ayant au moins une donnée de migration |
| … dont à enjeux | 🤖 `{{NB_MIGRATION_ENJEUX}}` | rapaces et grands voiliers parmi elles |
| Tableau | 🤖 `{{TABLE_MIGRATION}}` | espèces à enjeux ; tableau par anneau + « Max ind. » (effectif maximal) |
| Cartes 13 à 16 | 🤖 | couche `vm_eolienne_migration_all` (champ `esp_enjeux`, effectifs, milans) |
| Description | ✍️ | — |

### §8 Sensibilité éolienne

| Élément | Placeholder | Contenu |
|---|---|---|
| Carte 17 : indice par maille | 🤖 `{{Carte17_sensibilite}}` | voir le calcul ci-dessous |
| Carte 18 : tampons de nidification | 🤖 `{{Carte18_sensibilite_tampon}}` | tampons autour des sites de nidification **certains**, fusionnés par espèce |

Calcul de l'indice, par maille de 1 km (couche `vm_eolienne_sensi_oiseau`, champ `tot_max_sensi`, de 0 à 7) :
- point de départ : la note de sensibilité maximale (0 à 4) parmi les espèces observées dans la maille ;
- +1 si un rapace ou un grand voilier y est nicheur probable ou certain ;
- +1 s'il y a un dortoir de rapace ou de grand voilier ;
- +1 s'il y a une donnée de migration de rapace ou de grand voilier.

Rayons des tampons, définis dans `[params.tampons_nidification_km]` :

| Espèce | Rayon |
|---|---|
| Milan royal, Cigogne noire | 5 km |
| Milan noir, Circaète Jean-le-Blanc, Faucon pèlerin, Grand-duc d'Europe, Busard Saint-Martin | 2,5 km |

### §9 Conclusion, annexes

| Élément | Placeholder | Contenu |
|---|---|---|
| Conclusion | ✍️ | — |
| Annexe 1 (statuts) | texte fixe | — |
| Annexe 2 | 🤖 `{{TABLE_AUTRES_ESPECES}}` | toutes les espèces qui ne sont pas à enjeux ; tableau par anneau |

---

## 4. Tableaux par anneau

Colonnes fixes :
- Nom vernaculaire ;
- Nom scientifique (en italique) ;
- Protection nationale ;
- LR France (nicheurs) ;
- LR AuRA ;
- Sensibilité éolien ;
- Statut nidif. (tableaux de nidification seulement).

Puis, pour « Ensemble des zones » et pour chaque zone, deux colonnes : « Nb données » et « Dernière obs. ». Le tableau de migration en ajoute une troisième, « Max ind. ». Une case vide signifie qu'il n'y a aucune donnée dans cette zone.

Les deux lignes d'en-tête sont répétées sur chaque page. Les statuts de liste rouge sont colorés selon les couleurs UICN. Quand une sélection est vide, le tableau affiche « Aucune espèce concernée. ».

---

## 5. Projet QGIS

Le projet modèle est l'ancien `Eolienne_QGIS.qgs`, utilisé tel quel. Ses couches pointent vers `<couche>.gpkg|layername=<couche>`. Au rendu, chaque source est redirigée vers `outputs/<zone>/data/<couche>.gpkg` en **conservant son filtre** (`subset`). **Les filtres de chaque carte sont donc définis dans le projet QGIS, pas dans le code.** Par exemple, la carte 6 filtre sur `"ordre" = 'Strigiformes' AND "nb_annee" > 2`.

| Couche | Géométrie | Champs |
|---|---|---|
| vm_eolienne_zone_etude | polygone | id, area_name, name_project |
| vm_eolienne_limit | polygone | id, area_name (`contour 1 km`, `contour 6 km`, `contour 20 km`, en polygones pleins) |
| vm_eolienne_zone_protection | polygone | id, type_code |
| vm_eolienne | point | id, datetime, cd_nom, count_max, oiso_code_nidif, oiso_status_nidif, behaviour, comment_description, nom_vern, classe, ordre, famille, comportement, source, precision_geo, donnee_cachee |
| vm_eolienne_etat_connaissance | maille 1 km | id, id_area, sum_nb_data, sum_nb_esp |
| vm_eolienne_nidif | point | id, nom_vern, cd_nom, famille, ordre, nb_data, derniere_obs, nb_annee, oiso_status_nidif (`Nicheur certain` / `Nicheur probable`), donnee_cachee, precision_geo. **Sans la Cigogne noire** (sinon visible au point précis via le filtre `Ciconiidae`) |
| vm_eolienne_nidif_cn | maille 5 km | idem nidif, Cigogne noire uniquement |
| vm_eolienne_nidif_tampon | polygone | lb_nom, nom_vern, distance_km, nb_data |
| vm_eolienne_dortoirs | point | id, nom_vern, cd_nom, famille, ordre, derniere_obs, nb_data, donnee_cachee, precision_geo |
| vm_eolienne_migration_all | point | id, nom_vern, cd_nom, famille, ordre, nb_ind_max, derniere_obs, esp_enjeux (`enjeux` / `autres`), donnee_cachee, precision_geo |
| vm_eolienne_sensi_oiseau | maille 1 km | id, id_area, max_sensi, max_sensi_n/d/m, tot_max_sensi (les sum_* et tot_sensi reprennent les mêmes valeurs) |
| vm_eolienne_hors_region | polygone | pct_hors_region : partie de l'aire d'étude hors de la région couverte par la base, **à ajouter au projet** (grisé « pas de données ») |

`nom_vern` est le nom vernaculaire **complet**, par exemple « Héron garde-boeufs, Pique bœufs ». Les filtres du projet en dépendent.

Les champs `precision_geo` et `donnee_cachee` permettent, dans le projet, de styler différemment les points au lieu-dit ou les données cachées, ou de les filtrer.

### Réglages du rendu

Ils sont dans le bloc `[params.qgis_render]` du `dossier.toml` :
- groupes « Zone_etude » et « FDC » toujours visibles ;
- emprise calée sur la couche `LEGENDE_LIMITE` (contour 20 km) ;
- décalage vertical de 5 % ;
- +30 km pour la Carte 1 ;
- 150 dpi.

**Toutes** les mises en page du projet sont exportées. Pour chacune, seul le groupe de couches qui porte son nom est affiché.

### Modifier une carte ou en ajouter une

1. Ouvrir `qgis/projet_eolien.qgs` dans QGIS. Pour avoir des données à l'écran, copier à côté du projet le dossier `data/` d'un rapport déjà généré. Il contient des données sensibles : ne pas le commiter.
2. Pour une nouvelle carte, créer un groupe de couches et une mise en page **du même nom**.
3. Ajouter `{{<nom de la mise en page>}}`, seul dans son paragraphe, sur une page dédiée du template Word.
4. Vérifier avec `reportgenerator check --dossier eolien`.

---

## 6. Modifier les règles sans toucher au code

| Pour… | Modifier dans `dossier.toml` |
|---|---|
| changer les anneaux | `anneaux_km` (ex. `[1, 5, 15]`) : tableaux, textes et emprise suivent |
| changer la période | `annees` |
| changer la liste rouge régionale | `lr_regionale` (`lr_aura`, `lr_auv`, `lr_ra`) |
| changer les critères « à enjeux » | `enjeux_lr_statuts`, `enjeux_sensibilite_min` |
| changer les « enjeux forts » des rapaces nicheurs | `nicheur_enjeux_lr_statuts` |
| ajouter une espèce aux tampons | `[params.tampons_nidification_km]`, par **nom scientifique** |
| prendre aussi les nicheurs probables pour les tampons | `tampons_statuts_nidif = ["Certain", "Probable"]` |
| changer le rayon des zonages | `zonage_rayon_km` |

Toute modification d'une règle doit aussi être reportée dans le texte du template et dans ce document.

---

## 7. Points de vigilance

- **Le §5.2 du template** parle de « statut de nicheuse certaine », alors que le tableau et le chiffre comptent les nicheurs **probables ou certains**.
- **Le §8.1 du template** parle d'un « nid d'une espèce de rapace à fort enjeu », alors que le +1 s'applique à **tout** rapace ou grand voilier nicheur probable ou certain (règle du R).
- **Dortoirs et migration** : la recherche dans les remarques exclut les négations simples (« pas de dortoir »), mais reste approximative (« migrateur ? »…). Relire les tableaux.
- **Tampons de nidification** : le cercle est centré sur le nid. Pour la Cigogne noire (5 km), le tampon révèle donc l'emplacement du nid, même si la couche `vm_eolienne_nidif_cn` est floutée.
- **Couches vides** : sans aucune donnée (par exemple, aucun nid de Cigogne noire), la couche n'est pas exportée. La carte correspondante est vide ; ce n'est pas une erreur.
- **Mailles sans donnée** : elles ne sont pas exportées. Elles apparaissent en blanc, sans valeur « 0 ».
- **Statut de validation 0** : les données en attente de validation sont incluses (environ 40 % des données).
- **Liste rouge AuRA** : une espèce sans statut `lr_aura` a une case vide (pas de repli sur la liste rouge France).
- **Délai de génération** : il faut compter quelques minutes, dont environ 1 minute de rendu QGIS pour les 21 cartes.

## 8. Points encore ouverts

1. Tampons : faut-il ajouter les espèces du SQL R (Aigle royal, vautours, Busard cendré) ? Le texte du §8.2 serait à compléter.
2. Espèces « ajoutées à dire d'expert » (§4, 1er paragraphe, par exemple les petites chouettes de montagne) : rien n'est codé. Faut-il retirer la phrase, ou ajouter une liste dans `dossier.toml` ?
3. Données partenaires (`lpoaura_afo.t_eolienne`) : faut-il les réintégrer ?
4. **Données cachées** (16 %, surtout des nids sensibles) : sur les cartes destinées au commanditaire, faut-il les flouter (maille 1 ou 5 km), les exclure, ou les garder au point ? Aujourd'hui, elles sont au point, comme dans le R.
5. **`partage.sensibilite_oiseaux`** : à compléter (espèces manquantes listées en 2.).

---

## 9. Reprise du workflow R : corrections apportées

| Problème dans le R | Correction |
|---|---|
| La liste rouge régionale n'était jamais appliquée au filtre « à enjeux » (la chaîne `"lr_aura"` était comparée aux codes) | Le critère est réellement appliqué |
| Donuts faux en v2 (6 km − zone d'étude, « contour 10 km » inexistant) : double comptage | Anneaux disjoints calculés dans la VM (`anneau_ordre`) |
| Le tampon de 10 km de la Cigogne noire n'était jamais produit (absent de l'`union`) | Tampons paramétrés, Cigogne noire à 5 km comme dans le template |
| `NB_RAPACE_NICHEUSE_ENJEUX` n'était jamais calculé | Calculé |
| Statuts joints par nom vernaculaire (doublons, espèces perdues) | Jointure par `cd_ref` |
| Les sommes de `17_vm_sensi` étaient faussées par les jointures | Max + bonus 0/1, sans produit cartésien |
| Script QGIS : imports manquants, 6 cartes oubliées dans la liste | Toutes les mises en page sont exportées automatiquement |
| VM secondaires à créer et supprimer à la main | Une seule VM, supprimée automatiquement |
| Mise en forme Excel, puis copier-coller dans le Word | Tableaux insérés directement dans le Word |
| Mailles via `cor_area_synthese` (incomplet), doublons entre sources, comportement VisioNature ignoré | Voir 2. « Contrôles de qualité des données » |

---

## 10. Partie chiroptères

**Origine** : le document « partie chiroptères » d'un collègue, avec la méthode du SRE (Le Bret et Letscher, 2010), repris et corrigé (voir 10.7). Les anciens scripts R chiroptères ne sont pas repris : ils interrogeaient dbchiro en direct, et leurs tampons de sensibilité et leurs donuts étaient faux.

**Activation** : analyse optionnelle `chiropteres`, activée par défaut par `analyse_eolien`. Toute la partie est délimitée dans le template par `{{#chiropteres}}` … `{{/chiropteres}}`, à deux endroits : le chapitre avant la conclusion, et les annexes 3 à 5. Si l'analyse n'est pas demandée, ces sections sont retirées et la numérotation se recale.

Pour proposer plus tard un rapport sans chiroptères, il suffit d'ajouter au `dossier.toml` une ligne `analyse_eolien_oiseaux = []` dans `[declencheurs]`, puis la valeur correspondante dans la liste du formulaire QGIS.

### 10.1 Données

- **Une seule source : la VM principale.** DBchiro est déjà importé dans `gn_synthese` (source `dbChiroGCRA`), comme VisioNature et les partenaires. On n'interroge donc pas `src_dbchirogcra`. Une même donnée peut toutefois arriver par deux sources (ex. faune-france et dbChiroGCRA) : le dédoublonnage `sources_prioritaires` (section 2) garde la première.
- **Données et observations** : les suivis acoustiques produisent des centaines de contacts pour un même taxon, un même jour, au même point (96 % de répétitions sur la zone de test : 13 005 données pour 976 observations). Le rapport annonce les deux chiffres, puis **compte en observations** (un taxon, un jour, un lieu) : par anneau, dans le tableau de vulnérabilité et dans les annexes.
- **Genres et complexes gardés** (`chiro_rangs_non_especes = ["GN", "RES"]`). Ils sont fréquents pour les gîtes et colonies, par exemple « Pipistrelle indéterminée » ou « Oreillard indéterminé ». Ils comptent dans les **données** et les **gîtes**, jamais dans le **nombre d'espèces**.
- **Pseudo-taxons d'absence exclus.** Les `cd_nom` négatifs de DBchiro (« Aucune chauve-souris ou trace », « Aucune capture filet », « Aucun contact acoustique ») correspondent à des visites sans chauve-souris.
- **Gîte et colonie** : ce sont les champs `bat_is_gite` et `bat_breed_colo` de la synthèse étendue. Une donnée de colonie de reproduction est classée « Colonie de reproduction », les autres gîtes « Gîte ».
- **Période** : champ `bat_period` (estivage, transit, hivernant). ⚠️ Il n'est presque jamais renseigné (6 données sur 12 823 sur la zone de test). **Il n'est pas pris en compte pour l'instant** (décision), ni dans le texte, ni dans l'indice de sensibilité.

### 10.2 Vulnérabilité des espèces (méthode du document)

| Note | Calcul |
|---|---|
| NP, note patrimoniale | note de la liste rouge **AuRA** (CR 6, EN 5, VU 4, DD 3, NT 2, LC/NA 1) + 4 si annexe II DHFF. **Calculée** à partir de `lr_aura` et `n2k` |
| NE, note éolien | arrondi de (2 × NSE + NP) / 3 → **vulnérabilité aux collisions et barotraumatismes** : très forte (10), forte (7-9), moyenne (5-6), faible (≤ 4) |
| NH, note habitat | arrondi de (2 × NHab + NP) / 3 → **vulnérabilité à la destruction d'habitat** : forte (≥ 8), moyenne (5-7), faible (≤ 4) |

NSE (sensibilité directe à l'éolien), NHab (sensibilité à la perte d'habitat) et le rayon d'action autour des gîtes sont dans **`ref_chiropteres.csv`**, une ligne par espèce, repérée par son `cd_ref`. Les seuils des classes sont dans le `dossier.toml` (`chiro_seuils_ne`, `chiro_seuils_nh`).

Contrôle : le calcul retrouve exactement les notes et classes des **24 espèces** du tableau final du document (test `test_vulnerabilite_reproduit_le_tableau_du_document`). La seule exception est documentée en 10.7.

### 10.3 Contenu du rapport

**Chapitre « Chiroptères »** (avant la conclusion) :

| Section | Placeholder | Contenu |
|---|---|---|
| Introduction | texte fixe | — |
| Méthode | texte fixe | NP, NE, NH et classes, renvoi à l'annexe 5 |
| Connaissance | 🤖 `{{CHIRO_CONNAISSANCE}}` | nombre de données brutes et d'observations, nombre d'espèces, puis par anneau (en observations), dont les observations non précisées à l'espèce, puis « Précautions de lecture » si besoin |
| | 🤖 `{{TABLE_CHIRO_PERIMETRES}}` | observations, espèces et dernière observation par zone |
| | ✍️ | description de la connaissance |
| | 🤖 cartes 19 et 20 | nombre d'espèces et nombre de données par maille de 1 km |
| Vulnérabilité | 🤖 `{{CHIRO_VULN_EOLIEN}}`, `{{CHIRO_VULN_HABITAT}}` | listes des espèces à vulnérabilité forte ou très forte |
| | 🤖 `{{TABLE_CHIRO_VULNERABILITE}}` | tableau 5 du document : nom, nombre d'observations, LR France, LR AuRA, NH et classe, NE et classe ; tri par vulnérabilité éolien décroissante |
| | ✍️ ×2 | description de la vulnérabilité habitat et de la vulnérabilité éolienne |
| | 🤖 cartes 21, 22, 23 | pipistrelles, noctules, sérotines et vespère |
| Gîtes et colonies | 🤖 `{{CHIRO_TEXTE_GITES}}` | nombre de sites de colonies (par taxon, années) et de gîtes hors reproduction |
| | ✍️ | description des gîtes |
| | 🤖 cartes 24 et 25 | colonies de reproduction, gîtes hors reproduction |
| Sensibilité | texte fixe | méthode de l'indice et des tampons |
| | 🤖 cartes 26 et 27 | indice par maille, tampons autour des gîtes |

**Annexes** (en paysage) :
- annexe 3, `{{TABLE_CHIRO_ESPECES}}` : tous les taxons par anneau ;
- annexe 4, `{{TABLE_CHIRO_GITES}}` : gîtes et colonies par taxon et par anneau (nombre de sites, effectif maximal) ;
- annexe 5, `{{TABLE_CHIRO_REFERENTIEL}}` : NSE, NHab et rayon par espèce.

Autres valeurs disponibles pour le texte : `{{NB_CHIRO_DONNEES}}` (données brutes), `{{NB_CHIRO_OBSERVATIONS}}`, `{{NB_CHIRO_ESPECES}}`, `{{NB_CHIRO_DONNEES_NON_ESPECE}}`, `{{NB_CHIRO_COLONIES}}`, `{{NB_CHIRO_GITES}}`.

Copies Excel : `tables/7_chiro_especes.xlsx`, `tables/8_chiro_gites.xlsx`.

### 10.4 Indice de sensibilité et tampons (même principe que les oiseaux)

Pour chaque maille de 1 km :
- point de départ : la classe de vulnérabilité éolien maximale des espèces contactées (faible 1, moyenne 2, forte 3, très forte 4) ;
- +1 si une colonie de reproduction y est connue ;
- +1 si un gîte hors reproduction y est connu ;
- (désactivé) +1 si une espèce de vulnérabilité éolien forte ou très forte y est notée **en transit**. Ce bonus dépend du champ période, non pris en compte pour l'instant (voir 10.1). Pour l'activer : `chiro_transit_classe_min = "Forte"` dans le `dossier.toml` (le champ `bonus_transit` de la couche vaut 0 sinon).

**Tampons** : autour de chaque gîte et colonie, selon le rayon de l'espèce (`dist_gite_m` du référentiel, de 5 à 20 km, repris de `lpoaura_jgc.cs_distance`), fusionnés par taxon. Les taxons sans rayon (genres et complexes, par exemple « Pipistrelle indéterminée ») ont un **rayon par défaut de 1 km** (`chiro_dist_gite_defaut_m`, champ `rayon_par_defaut` = vrai dans la couche).

**Floutage** : `chiro_floutage_m = 0` donne la position précise. Avec une valeur (ex. `1000`), gîtes, colonies et tampons sont placés au centre d'une maille de cette taille, dans les couches et donc sur les cartes.

### 10.5 Couches QGIS et cartes à créer

Couches exportées dans `data/`. Les cartes **19 à 27 restent à créer** dans `qgis/projet_eolien.qgs` : un groupe de couches et une mise en page portant **le même nom** que le placeholder. Tant qu'elles n'existent pas, `check` les signale et leurs placeholders restent visibles dans le Word.

| Couche | Géométrie | Champs |
|---|---|---|
| vm_eolienne_chiro_data | point | id, cd_nom, nom_vern, lb_nom, id_rang, **groupe** (pipistrelles, noctules, serotines_vespere, murins, rhinolophes, oreillards, autres), periode, gite, colonie, count_max, datetime, annee, anneau_ordre, lr_aura, n2k, source, precision_geo, donnee_cachee, ne, ne_classe, nh, nh_classe |
| vm_eolienne_etat_connaissance_chiro | maille 1 km | id, id_area, sum_nb_data (donnÃ©es brutes), sum_nb_obs (observations), sum_nb_esp |
| vm_eolienne_chiro_gites | point (un par site, taxon et type) | id, cd_nom, nom_vern, lb_nom, **type_gite**, nb_data, effectif_max, premiere_obs, derniere_obs, periodes, donnee_cachee, precision_geo, groupe, ne, ne_classe |
| vm_eolienne_chiro_gite_tampon | polygone | cd_nom, nom_vern, lb_nom, distance_m, rayon_par_defaut, nb_sites |
| vm_eolienne_sensi_chiro | maille 1 km | id, id_area, sensi_especes, bonus_colonie, bonus_gite, bonus_transit, **sensibilite**, nb_data |

| Mise en page à créer | Couche et filtre suggéré |
|---|---|
| Carte19_chiro_nb_especes | `vm_eolienne_etat_connaissance_chiro`, symbologie sur `sum_nb_esp` |
| Carte20_chiro_nb_donnees | idem, sur `sum_nb_obs` (observations, comme le texte ; `sum_nb_data` est gonflÃ© par les rÃ©pÃ©titions acoustiques) |
| Carte21_chiro_pipistrelles | `vm_eolienne_chiro_data`, `"groupe" = 'pipistrelles'`, catégories sur `nom_vern` |
| Carte22_chiro_noctules | idem, `"groupe" = 'noctules'` |
| Carte23_chiro_serotines_vespere | idem, `"groupe" = 'serotines_vespere'` |
| Carte24_chiro_colonies | `vm_eolienne_chiro_gites`, `"type_gite" = 'Colonie de reproduction'` |
| Carte25_chiro_gites | idem, `"type_gite" = 'Gîte'` (une seule carte, plutôt que deux pour cause de légende trop longue comme dans le document) |
| Carte26_chiro_sensibilite | `vm_eolienne_sensi_chiro`, sur `sensibilite` |
| Carte27_chiro_tampons_gites | `vm_eolienne_chiro_gite_tampon` + `vm_eolienne_chiro_gites` |

### 10.6 Paramètres (`dossier.toml`)

| Paramètre | Rôle |
|---|---|
| `chiro_rangs_non_especes` | rangs gardés en plus de l'espèce (genres, complexes) |
| `chiro_referentiel` | fichier du référentiel (NSE, NHab, rayon) |
| `chiro_seuils_ne`, `chiro_seuils_nh` | seuils des classes de vulnérabilité |
| `chiro_dist_gite_defaut_m` | rayon des tampons pour les taxons sans rayon (1 000 m) |
| `chiro_transit_classe_min` | (commenté = désactivé) classe minimale pour le bonus « transit » de l'indice |
| `chiro_floutage_m` | taille de la maille de floutage des gîtes (0 = précis) |

### 10.7 Écarts et corrections par rapport au document fourni

| Dans le document | Ce qui est fait |
|---|---|
| Tableau des notes patrimoniales saisi à la main : Grand Murin NP 8 et Petit Murin NP 5, alors que le tableau final utilise 5 et 8 (listes rouges inversées) ; Sérotine bicolore NP 2 au lieu de 3 (DD) | NP **calculée** à partir de la liste rouge AuRA et de l'annexe II : plus d'erreur de saisie, et mise à jour automatique avec les listes rouges |
| La méthode parle des notes « LR Rhône-Alpes », le tableau utilise la LR AuRA | LR AuRA partout |
| « La note finale est l'addition de NE et NH », mais le tableau ne présente pas cette somme | Pas de somme : deux vulnérabilités distinctes, éolien et habitat, comme dans le tableau |
| Seuils des classes non écrits, et différents entre NE (forte dès 7) et NH (forte dès 8) | Seuils explicites dans le `dossier.toml`, repris du tableau final |
| Grande Noctule : NSE 8 dans la méthode, mais NE = 8 dans le tableau final (ce qui correspond à NSE 10) | NSE 8 conservée, ce qui donne **NE 7, classe « Forte » inchangée**. À trancher : passer à 10 dans le référentiel si l'espèce doit être en tête de liste |
| Murin cryptique (*Myotis crypticus*) absent de la méthode | Ajouté au référentiel, **assimilé au Murin de Natterer** (NSE 2, NHab 10, 5 km), dont il a été séparé |
| Tableaux NSE et NHab avec puces de critères | Remplacés par le référentiel en annexe 5, généré depuis le fichier CSV (une seule source) |
| Deux cartes « gîtes hors reproduction » (légende trop longue) | Une seule carte, la légende étant à gérer dans la mise en page |
| Données « Aucune espèce » comptées par dbchiro | Exclues (pseudo-taxons d'absence) |
| Titre « … partie Ardéchoise » | Titres génériques |

Corrections faites au passage, qui concernent aussi les oiseaux :
- **sous-espèces** : leur `cd_sup` est souvent vide. Elles sont maintenant rattachées au `cd_ref` de leur parent, ou à leur propre `cd_ref` (déjà celui de l'espèce). Avant, leurs données tombaient sur un `cd_ref` nul (le Petit Rhinolophe apparaissait en double) ;
- **ouverture dans Word** : l'identifiant de dessin d'une carte pouvait reprendre celui du logo du pied de page, et Word signalait alors un fichier endommagé. Les identifiants sont maintenant rendus uniques (test `test_drawing_ids_unique_across_parts`).

### 10.8 Points ouverts

1. **Périodes** (transit, estivage, hivernage), non prises en compte pour l'instant : `bat_period` n'est presque jamais renseigné. Piste : déduire la période de la date (par exemple : hivernage de mi-novembre à mi-mars, transit printanier de mi-mars à mai, estivage de juin à mi-août, transit automnal de mi-août à mi-novembre), à valider avec le collègue. La brique `chiro_periodes` (tableau par période) existe déjà, mais elle n'est pas encore incluse.
2. **Floutage** : à fixer avant diffusion (`chiro_floutage_m`, par exemple 1 000 m).
3. **Tables de référence** : `ref_chiropteres.csv` remplace `lpoaura_afo."99_chiro_sensi_eol"` (classes 0-3, non utilisées) et `lpoaura_jgc.cs_distance` (copiée, dédoublonnée : chaque espèce y figurait deux fois). Les tables en base peuvent être archivées.
4. **Données cachées** : même question que pour les oiseaux (8. Points ouverts).

Décisions prises : Grande Noctule à NSE 8 ; rayon par défaut de 1 km pour les genres et complexes ; titre « … d'oiseaux et de chiroptères … » automatique (`{{TITRE_RAPPORT}}`, sommaire à mettre à jour dans Word avec F9).
