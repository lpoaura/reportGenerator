# Rapport éolien : process et contenu

**Rapport produit** : « Synthèse des données d'oiseaux dans le cadre d'un projet éolien ». C'est un document de base : le générateur remplit les chiffres, les tableaux et les cartes, puis le collègue rédige l'analyse.

**Déclenchement** : la valeur `analyse_eolien` dans le champ `list_analyse` du formulaire QGIS.

**Fichiers du dossier** :
- `dossier.toml` : briques et paramètres ;
- `template.docx` : modèle Word ;
- `qgis/projet_eolien.qgs` : projet QGIS modèle, avec ses pièces jointes `projet_eolien_attachments.zip` ;
- `METHODO.md` : ce document.

**Origine** : la méthode reprend l'ancien workflow R (`traitement_generale_v2.R`, `script_sql/*.sql`, `lancement_carte_qgis.py`), avec ses bugs corrigés (voir la section 9).

---

## 1. Process de génération

```text
Formulaire QGIS (list_analyse = analyse_eolien)
  │
  ▼
socle_data             VM lpoaura_afo.vm_reportgenerator_data :
                       oiseaux, 10 dernières années, jusqu'à 20 km, mailles 1 km,
                       note de sensibilité éolienne et anneau de chaque observation
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
couches_qgis_eolien    11 couches GPKG vm_eolienne_* dans data/ (noms et champs du workflow R)
  │
  ▼
cartography            copie du projet QGIS, re-lien des couches, export des 21 mises en page en PNG
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
| Taxons | oiseaux (`tx_group2_inpn_v2 = 'Oiseaux'`), rang espèce ; les sous-espèces sont rattachées à leur espèce | `groupes_taxo` |
| Période | depuis le 1er janvier de (année en cours − 10) | `annees` |
| Validation | statuts 0 (en attente), 1 et 2 | `statuts_validation` |
| Emprise | zone d'étude + 20 km | dernier élément de `anneaux_km` |
| Géométries | points uniquement | — |
| Grille | mailles de 1 km (`M1`) | `grille` |
| Liste rouge régionale | `lr_aura` | `lr_regionale` |
| Sensibilité éolienne | note 0-4 de `partage.sensibilite_oiseaux` | `sensibilite_eolien` |

Le champ **buffer** du formulaire **n'est pas utilisé** : l'emprise est fixée par les anneaux.

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
| Dortoir | « dorto » dans le comportement **ou** dans la remarque de l'observateur |
| Migration | « migr » dans le comportement **ou** dans la remarque de l'observateur |

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
| Texte de synthèse | 🤖 `{{CONNAISSANCE_OISEAUX}}` | nombre de données et d'espèces sur toute la zone, puis par anneau, du plus éloigné à la zone d'étude |
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
| vm_eolienne | point | id, datetime, cd_nom, count_max, oiso_code_nidif, oiso_status_nidif, behaviour, comment_description, nom_vern, classe, ordre, famille |
| vm_eolienne_etat_connaissance | maille 1 km | id, id_area, sum_nb_data, sum_nb_esp |
| vm_eolienne_nidif | point | id, nom_vern, cd_nom, famille, ordre, nb_data, derniere_obs, nb_annee, oiso_status_nidif (`Nicheur certain` / `Nicheur probable`) |
| vm_eolienne_nidif_cn | maille 5 km | idem nidif, Cigogne noire uniquement |
| vm_eolienne_nidif_tampon | polygone | lb_nom, nom_vern, distance_km, nb_data |
| vm_eolienne_dortoirs | point | id, nom_vern, cd_nom, famille, ordre, derniere_obs, nb_data |
| vm_eolienne_migration_all | point | id, nom_vern, cd_nom, famille, ordre, nb_ind_max, derniere_obs, esp_enjeux (`enjeux` / `autres`) |
| vm_eolienne_sensi_oiseau | maille 1 km | id, id_area, max_sensi, max_sensi_n/d/m, tot_max_sensi (les sum_* et tot_sensi reprennent les mêmes valeurs) |

`nom_vern` est le nom vernaculaire **complet**, par exemple « Héron garde-boeufs, Pique bœufs ». Les filtres du projet en dépendent.

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
- **Dortoirs et migration** : la recherche de « dorto » et « migr » dans les remarques est bruitée (« pas de dortoir », « migrateur ? »…). Relire les tableaux.
- **Couches vides** : sans aucune donnée (par exemple, aucun nid de Cigogne noire), la couche n'est pas exportée. La carte correspondante est vide ; ce n'est pas une erreur.
- **Mailles sans donnée** : elles ne sont pas exportées. Elles apparaissent en blanc, sans valeur « 0 ».
- **Statut de validation 0** : les données en attente de validation sont incluses.
- **Liste rouge AuRA** : une espèce sans statut `lr_aura` a une case vide (pas de repli sur la liste rouge France).
- **Délai de génération** : il faut compter quelques minutes, dont environ 1 minute de rendu QGIS pour les 21 cartes.

## 8. Points encore ouverts

1. Tampons : faut-il ajouter les espèces du SQL R (Aigle royal, vautours, Busard cendré) ? Le texte du §8.2 serait à compléter.
2. Espèces « ajoutées à dire d'expert » (§4, 1er paragraphe, par exemple les petites chouettes de montagne) : rien n'est codé. Faut-il retirer la phrase, ou ajouter une liste dans `dossier.toml` ?
3. Dortoirs et migration : faut-il ne garder que la nomenclature de comportement ?
4. Données partenaires (`lpoaura_afo.t_eolienne`) : faut-il les réintégrer ?
5. Chiroptères : les anciens scripts R existent (dbchiro, gîtes, sensibilité). Ce serait une brique optionnelle à créer.

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
