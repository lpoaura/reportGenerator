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
vulnerabilite_eolien   indice de vulnérabilité (MEDDE 2015) : tableau, annexe 3, histogramme
nidification           rapaces et grands voiliers nicheurs
passereaux             passereaux nicheurs au-dessus du seuil de vulnérabilité
autres_nicheurs        autres espèces nicheuses à enjeux (ni rapace, ni grand voilier, ni passereau)
cartes_nidification    plan des cartes de nidification par groupe d'espèces (§5 bis)
dortoirs               dortoirs de rapaces et grands voiliers
cartes_dortoirs        plan des cartes de dortoirs par groupe, zones de dortoir fusionnées (§6)
migration              données de migration
cartes_migration       une carte de migration par espèce (Milan royal, vulnérabilité >= 4) (§7)
couverture_cartes      contrôle : espèces de vulnérabilité >= 3 absentes des cartes thématiques
  │                    → textes et tableaux du Word, copies Excel dans tables/
  ▼
couches_qgis_eolien    12 couches GPKG vm_eolienne_* dans data/ (noms et champs du workflow R + hors_region)
chiropteres           (optionnel) connaissance, vulnérabilité, gîtes, 5 couches *chiro* (section 10)
  │
  ▼
couches_cartes         couleurs par espèce (communes aux trois thèmes), couches des cartes, liste des cartes pour le rendu
cartography            toujours en dernier : copie du projet QGIS, re-lien des couches,
                       export de toutes les mises en page en PNG (Cartes_nidification, Cartes_dortoirs,
                       Cartes_migration : une image par carte du plan)
cartes_word            cartes par groupe ou par espèce insérées dans le Word
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
├── dataviz/                         eolien_histogramme_vulnerabilite.png
└── tables/                          2_oiseaux_especes_enjeux.xlsx, 2_oiseaux_especes_autres.xlsx,
                                     2b_oiseaux_vulnerabilite.xlsx (toutes les espèces),
                                     3_nidif_rapaces.xlsx, 4_nidif_ardeides.xlsx, 4b_nidif_passereaux.xlsx,
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
| Hivernant | donnée du 1er décembre au 31 janvier (même règle que le dossier Natura 2000) : indice de vulnérabilité |
| Nicheur (sens large) | statut `Possible`, `Probable` ou `Certain` : phrase de l'indice de vulnérabilité, passereaux |

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

### §3 bis État des connaissances par maille de 1 km (ajouté le 20/10/2026)

Partie de niveau 1 après « Connaissance des oiseaux », en **complément** des cartes 2 et 3 (conservées). Même
méthode que le dossier Natura 2000 (briques communes `connaissance`, `couches_qgis_connaissance`,
`connaissance_atlas` ; méthode détaillée dans `dossiers/natura2000/METHODO.md`, §3.1.1).

| Élément | Contenu |
|---|---|
| Groupes | **Oiseaux** ; **Chauves-souris** seulement si l'analyse optionnelle `chiropteres` est activée (`connaissance_groupes`, `[params.connaissance_groupes_analyse]`) |
| Emprise | mailles de 1 km de la zone d'étude **et des 6 km autour** (`connaissance_rayon_km = 6`, anneau intermédiaire) : à 20 km, les mailles seraient trop petites sur la carte pour lire les chiffres des espèces à enjeux |
| Référence (« espèces locales ») | espèces du groupe connues sur toute l'aire d'étude, 20 km (`pool_local_km = 20`), sur la période du rapport (10 ans) |
| Cartes d'effort | `{{Connaissance_effort_donnees}}`, `{{Connaissance_effort_jours}}` (groupes étudiés) |
| Tableau | `{{TABLE_CONNAISSANCE_GROUPES}}` (copie `tables/connaissance_groupes.xlsx`), puis `{{TEXTE_GROUPES_CARTOGRAPHIES}}` |
| Atlas | `{{ATLAS_CONNAISSANCE_GROUPES}}` : par groupe ayant au moins 4 espèces dans la zone d'étude (titre de niveau 2), « Part des espèces locales » et « Richesse et prospection » ; avertissement si la médiane des jours d'observation par maille est < 2 |
| Textes fixes | démarche et lecture des cartes, paragraphe jaune pour le commentaire |

Espèces à enjeux des cartes (chiffre rouge) : définition commune à tous les dossiers (Natura 2000 ou liste rouge
CR à NT, oiseaux nicheurs seulement), différente de celle du §4 (CR/EN/VU ou sensibilité éolienne > 2).
Projet QGIS : 4 mises en page clonées de `Carte17_sensibilite`. Dans l'ordre de rendu, les couches de ces cartes
passent **sous** les contours (`LEGENDE_ZONE_ETUDE`, `LEGENDE_LIMITE`) pour que la zone et les anneaux restent
visibles sur les mailles.

Corrections du projet et du template faites à cette occasion (20/10/2026) :
- `LEGENDE_ZONE_ETUDE` lit `zone_etude.gpkg`, qui contient aussi le tampon de la demande et les 50 km autour : filtre
  `"secteur" = 'Zone d''étude'` ajouté (le tampon et les 50 km étaient tracés en rouge comme la zone d'étude) ;
- numérotation : les titres de niveau 2 suivent leur propre liste, dont le chiffre du chapitre avance grâce à des
  paragraphes vides masqués placés avant chaque chapitre à sous-titres. Avec la nouvelle partie (chapitre 4), 3 de
  ces « compteurs » ont été ajoutés après son titre (« 4.1 Oiseaux ») et 2 retirés avant « Nidification » : les
  sous-titres suivants restent justes (6.1, 9.1, 10.1). **À savoir si on ajoute ou déplace un chapitre.**
- 21/10/2026 (indice de vulnérabilité, script `outils/word/section_vulnerabilite.py`) : le chapitre 5 « Espèces à
  enjeux » a maintenant des sous-titres (5.1, 5.2) : 1 compteur ajouté après son titre, 1 retiré avant « Nidification ».

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

Le 2e paragraphe du §4 du template décrit cette règle. Dans le template, ce texte et le tableau forment le
sous-titre « Espèces à enjeux de conservation » ; le sous-titre suivant présente l'indice de vulnérabilité.

### §4 bis Indice de vulnérabilité à l'éolien (ajouté le 21/10/2026)

**Origine** : note de modification d'un rédacteur et rapport de référence « Rapport_Eolien_VF » (Le Cellier-du-Luc,
2026), qui reprend la matrice du Protocole de suivi environnemental des parcs éoliens terrestres (MEDDE 2015). Les
deux méthodes sont gardées (décision) : la liste « à enjeux » (§4) signale les très forts enjeux, l'indice affine et
fait ressortir des espèces écartées par la liste.

**Calcul** (`analysis/eolien/vulnerabilite.py`, fonctions pures testées sans base) :

> vulnérabilité = (note d'enjeu de conservation + note de sensibilité éolienne) / 2

| Élément | Règle |
|---|---|
| Sensibilité | note 0 à 4 de `partage.sensibilite_oiseaux` ; **inconnue = 0** (comme le rapport de référence : Bruant ortolan EN → 2,5) |
| Enjeu de conservation | CR, EN (et RE) = 5 ; VU = 4 ; NT = 3 ; LC = 2 ; DD, NA ou sans statut = 1 |
| Listes prises en compte | la **plus forte** de : LR régionale (`lr_regionale`) et LR France des nicheurs, toujours ; LR France des **migrateurs** seulement si l'espèce a au moins une donnée de **migration** (sélection Migration) ; LR France des **hivernants** seulement si elle a au moins une donnée d'**hivernage** (1er décembre - 31 janvier). Décision : une liste qui ne correspond à aucun statut observé sur l'aire d'étude ne compte pas |
| Espèces non protégées | la ligne « espèce non protégée = 0,5 » de la matrice **n'est pas appliquée** (décision : elle ferait disparaître des espèces chassables menacées, ex. Bécassine des marais CR = 3) |

L'indice est calculé une seule fois par espèce, sur **toutes** les données d'oiseaux de l'aire d'étude (20 km) : les
statuts migrateur et hivernant ne dépendent pas de la sélection d'un tableau (ex. nicheurs seuls).

Contrôle : le test `test_reproduit_le_rapport_de_reference` retrouve les notes de 11 espèces du tableau 2 du rapport
de référence (Aigle royal, Milan royal, Goéland cendré, Grue cendrée, Bécassine des marais, Bruant ortolan…). Écart
connu : le rapport de référence prenait toujours les LR migrateurs et hivernants ; ici seulement si le statut est
observé. Le Monticole bleu y vaut 2,5 avec LR AuRA « VU » (le statut actuel est EN, ce qui donne bien 2,5).

| Élément du template | Placeholder | Contenu |
|---|---|---|
| Matrice de calcul | 🤖 `{{TABLE_MATRICE_VULNERABILITE}}` | générée depuis les notes du code (pas d'image figée) |
| Phrase | 🤖 `{{TEXTE_VULNERABILITE}}` | « Au total, N espèces … supérieur à 2,5, dont M nicheuses (nicheur possible, probable ou certain), parmi les Z espèces observées » |
| Seuil | 🤖 `{{SEUIL_VULNERABILITE}}` | « supérieur à 2,5 » (légende du tableau) ; aussi `{{NB_ESPECE_VULNERABLE}}` |
| Tableau principal | 🤖 `{{TABLE_VULNERABILITE}}` | espèces dont l'indice dépasse le seuil, par indice décroissant puis nombre de données ; **sans les anneaux** (décision : vu le rayon d'action des oiseaux, la priorisation ne dépend pas de la distance) |
| Histogramme | 🤖 `{{CHART_VULNERABILITE}}` | nombre d'espèces par valeur d'indice (0,5 à 4,5), mêmes couleurs que les tableaux |
| Espèces les plus vulnérables | 🤖 `{{LISTE_ESPECES_TRES_VULNERABLES}}` (+ `{{VULNERABILITE_PHRASES_MIN}}`) | une phrase préremplie par espèce d'indice ≥ `vulnerabilite_phrases_min` (4) : statuts sur l'aire d'étude, nombre de données, dont zone d'étude et premier anneau, distance de la donnée la plus proche **de la zone d'étude** (0 = dedans), site de nidification **probable ou certain** le plus proche (statut, année). À relire et compléter |
| Contrôle des cartes | 🤖 `{{TEXTE_COUVERTURE_CARTES}}` (paragraphe jaune, à supprimer) | espèces d'indice ≥ `vulnerabilite_carte_min` (3) absentes de **toutes** les couches thématiques : rapaces et grands voiliers nicheurs (probable, certain), dortoirs, migration à enjeux, passereaux retenus (brique `couverture_cartes`). Contrôle sur les couches : les filtres du projet QGIS (ex. `nb_annee > 2` des rapaces nocturnes) peuvent encore masquer un point |
| Commentaire | ✍️ | paragraphe jaune |
| Annexe 3 | 🤖 `{{TABLE_VULNERABILITE_ANNEXE}}` | toutes les espèces, par ordre alphabétique |

Décision (21/10/2026) : pas de carte supplémentaire pour les espèces ≥ 3 non cartographiées pour l'instant (le
contrôle les liste) ; la représentation des nidifications répétées d'espèces proches au même endroit est à revoir
ensemble.

Remarque sur la règle des listes : la LR France des nicheurs compte toujours, même si l'espèce ne niche pas sur
l'aire d'étude (décision : maximum entre LR AuRA et LR France). Exemple à Barbières : Pygargue à queue blanche, 2
données sans statut, CR France nicheur + sensibilité 4 → 4,5.

Mise en page (22/10/2026, script `outils/word/tableaux_paysage.py`) : le tableau principal est sur une page A4
**paysage** (la suite du chapitre repasse en portrait), comme le tableau de vulnérabilité des chiroptères (§10.3).

Colonnes des deux tableaux : nom vernaculaire, nom scientifique, LR France (nicheurs), LR France hivernants, LR France
migrateurs, LR AuRA, **Vulnérabilité**, Sensibilité éolien, « Statut sur l'aire d'étude » (nicheur possible, probable
ou certain, migrateur, hivernant : les statuts qui déterminent les listes prises en compte), nombre de données.

**Seuil** : `vulnerabilite_seuil = 2.5` et `vulnerabilite_seuil_inclus = false` (indice **strictement** supérieur à
2,5, comme la note de modification ; le rapport de référence prenait ≥ 2,5). Pour revenir à ≥ 2,5 :
`vulnerabilite_seuil_inclus = true`. Le même seuil sert à la phrase et à la sélection des passereaux.

**Couleurs** : cellules « Vulnérabilité » sur fond orange dégradé à partir de 2,5 (2,5 très clair → 4,5 foncé), comme
la matrice du rapport de référence (`COULEURS` dans `vulnerabilite.py`).

### §5 Nidification

| Élément | Placeholder | Contenu |
|---|---|---|
| Rapaces nicheurs | 🤖 `{{NB_RAPACE_NICHEUSE}}` | rapaces nicheurs probables ou certains, jusqu'à 20 km |
| … dont à enjeux forts | 🤖 `{{NB_RAPACE_NICHEUSE_ENJEUX}}` | les mêmes, classés CR, EN, VU ou NT sur `lr_aura` |
| Tableau rapaces | 🤖 `{{TABLE_RAPACES_NICHEURS}}` | tableau par anneau + colonne « Statut nidif. » (meilleur statut observé) |
| Cartes des rapaces | 🤖 `{{CARTES_NIDIF_RAPACES}}` | cartes par groupe (§5 bis) : nocturnes (ou hiboux / chouettes), buses et faucons, milans et busards, vautours, autres diurnes |
| Grands voiliers nicheurs | 🤖 `{{NB_ARDEIDES_NICHEUSE}}` | ardéidés, cigognes, laridés et grues nicheurs probables ou certains |
| Tableau grands voiliers | 🤖 `{{TABLE_ARDEIDES_NICHEURS}}` | tableau par anneau + statut de nidification |
| Cartes des grands voiliers | 🤖 `{{CARTES_NIDIF_GRANDS_VOILIERS}}` | mouettes, goélands et sternes ; cigognes et grues (Cigogne noire floutée à la maille de 5 km) ; hérons |
| Description des enjeux | ✍️ | — |

Les anciennes cartes 6 à 11.2 (listes de noms vernaculaires figées dans les styles QGIS) sont remplacées depuis le
21/10/2026 par les cartes par groupe (§5 bis) : à Barbières, elles perdaient 8 espèces nicheuses (Aigle royal, vautours,
Petit-duc scops, Chouette de Tengmalm, Chevêchette, Blongios nain, Bihoreau gris), absentes des listes ou renommées.

**Passereaux** (sous-partie ajoutée le 21/10/2026, brique `passereaux`, script `outils/word/section_passereaux.py`) :

| Élément | Placeholder | Contenu |
|---|---|---|
| Texte fixe | — | enjeu habitat (défrichement, pistes, dérangement) plutôt que collision, faible détectabilité lors des suivis de mortalité |
| Chiffres | 🤖 `{{NB_PASSEREAUX_VULNERABLES}}`, `{{NB_PASSEREAUX_NICHEURS}}` | passereaux retenus / tous les passereaux nicheurs (possible, probable ou certain) jusqu'à 20 km |
| Tableau | 🤖 `{{TABLE_PASSEREAUX_NICHEURS}}` | ordre Passeriformes, nicheur **possible, probable ou certain**, indice de vulnérabilité au-dessus du seuil (§4 bis, même seuil que le tableau principal) ; tableau par anneau + statut de nidification ; les nombres de données ne comptent que les données avec un statut de nidification |
| Cartes | 🤖 `{{CARTES_NIDIF_PASSEREAUX}}` | cartes par groupe (§5 bis), données possibles, probables ou certaines ; au-delà de 6 espèces, découpage par familles (pies-grièches, bruants, alouettes et pipits, fauvettes, traquets et gobemouches, fringilles, corvidés) |
| Description | ✍️ | paragraphe jaune |

Décisions : pas de découpage par milieux (forestiers, xériques, agricoles) comme dans le rapport de référence ; aucune
espèce écartée pour l'instant.

**Autres espèces nicheuses à enjeux** (sous-partie ajoutée le 21/10/2026, brique `autres_nicheurs`, script
`outils/word/cartes_groupes.py`) : nicheurs probables ou certains qui ne sont ni rapaces, ni grands voiliers, ni
passereaux, menacés (CR, EN, VU sur la LR régionale ou France des nicheurs) ou d'indice de vulnérabilité au-dessus du
seuil. `{{NB_AUTRES_NICHEURS}}`, `{{TABLE_AUTRES_NICHEURS}}` (tableau par anneau, copie `tables/4c_nidif_autres.xlsx`),
`{{CARTES_NIDIF_AUTRES}}` (canards, grèbes et cormorans ; limicoles ; râles ; carte « autres espèces »). À Barbières :
13 espèces (Martin-pêcheur, Petit Gravelot, Courlis cendré, Tourterelle des bois, Nette rousse, fuligules…), qui
n'apparaissaient sur aucune carte ni dans aucun tableau.

### §5 bis Cartes de nidification par groupe d'espèces (ajouté le 21/10/2026)

**Objectif** : chaque espèce des tableaux de nidification (rapaces, grands voiliers, passereaux, autres) apparaît sur une
carte, quelle que soit la zone, sans nom d'espèce écrit dans le projet QGIS, et aucune carte n'a plus de 6 espèces.

**Plan des cartes** (`analysis/eolien/cartes.py`, fonctions pures testées) :

| Règle | Détail | Paramètre |
|---|---|---|
| Groupes | définis par des **règles** (ordres, familles, genres, noms scientifiques), dans l'ordre de priorité : une espèce va dans le premier groupe qui la reconnaît. Jamais par le nom vernaculaire (il change : « Hibou petit-duc, Petit-duc scops » → « Petit-duc scops ») | `[[params.groupes_cartes]]` (fin du `dossier.toml`) |
| Ordre des groupes | nocturnes ; buses et faucons (Buteo, Falco) ; milans et busards (Milvus, Circus) ; vautours ; autres diurnes ; mouettes, goélands et sternes ; cigognes et grues ; hérons ; canards, grèbes et cormorans ; limicoles ; râles ; passereaux | idem |
| Maximum par carte | 6 espèces (lisibilité de la carte et de la légende) | `cartes_max_especes` |
| Découpage | un groupe trop grand est découpé selon ses sous-groupes s'il en a (nocturnes : hiboux = Bubo, Asio, Otus / chouettes = Strix, Athene, Glaucidium, Aegolius, Tyto ; autres diurnes : aigles / autour, épervier, bondrée, élanion ; passereaux : familles), sinon en cartes équilibrées gardant les genres ensemble (7 espèces → 4 + 3) | `[[params.groupes_cartes.decoupage]]` |
| Carte « Autres » | les espèces qu'aucun groupe ne reconnaît : rien n'est oublié ; un groupe s'ajoute quand des espèces y reviennent souvent | — |
| Groupe absent | pas de carte (plus de carte vide) | — |
| Section | chaque groupe dit dans quelle sous-partie ses cartes sont insérées (rapaces, grands voiliers, passereaux, autres) | `section` |

À Barbières (21/10/2026) : 13 cartes ; les nocturnes (8 espèces) sont découpés en hiboux (3) et chouettes (5).

**Données** (brique `cartes_nidification`, couche `vm_eolienne_nidif_cartes`) :

| Règle | Détail | Paramètre |
|---|---|---|
| Statuts | nidification probable ou certaine ; possible aussi pour les passereaux (comme leur tableau) | — |
| Regroupement | données d'une espèce regroupées par **maille de 100 m** : un point au centre des données de la maille. Maille plutôt que rayon : pas d'« effet de chaîne » (des chanteurs tous les 100 m le long d'une haie ne fusionnent pas) | `nidif_regroupement_m` |
| Site pluriannuel | maille occupée au moins 3 années différentes : point grossi et cerclé de noir (comme l'ancien cercle des rapaces nocturnes, mais pour toutes les espèces) | `nidif_annees_site` |
| Floutage | espèce sensible : point au **centre** d'une maille plus grande (Cigogne noire : 5 km), jamais au centre des données | `[params.nidif_floutage_m]` |
| Superposition | points de plusieurs espèces au même endroit (colonie, lieu-dit) écartés en cercle autour de leur position (style « déplacement de points » de QGIS), à moins de 1 mm sur la carte (environ 190 m) | `[params.qgis_render.deplacement_mm]` |

Champs : id, cle (carte), cd_ref, nom, lb_nom, couleur, ordre_legende, nb_data, nb_annee, derniere_obs, statut_nidif,
site_pluriannuel, donnee_cachee, precision_geo.

**Couleurs** (brique `couches_cartes`) : une couleur par espèce, **la même sur toutes les cartes du rapport**.
- Référentiel **`dossiers/eolien/couleurs_especes.csv`** (cd_ref ; couleur), initialisé le 21/10/2026 avec les couleurs
  des anciens styles QGIS (45 espèces ; couleur de nidification prioritaire sur celle des dortoirs). À compléter ou
  corriger directement.
- Espèce absente du référentiel : couleur automatique (palettes de P. Tol, lisibles par les daltoniens), réutilisée
  d'une carte à l'autre quand les espèces ne se côtoient pas.
- Deux espèces d'une même carte ont toujours des couleurs nettement différentes (écart perçu ΔE ≥ 20) : sinon, la
  seconde reçoit une couleur automatique pour tout le rapport (liste dans `data` de la brique, `remplacees`).

**Rendu** : une seule mise en page modèle `Cartes_nidification` dans le projet (clone de l'ancienne carte 8, script
`outils/qgis/ajout_cartes_groupes.py`). Pour chaque carte du plan (`[params.qgis_render]` → `pages`, fourni par la
brique), le rendu filtre la couche sur la clé de la carte, construit le style des espèces de la carte
(`categories_dynamiques` : nom, ordre de légende, couleur, champ d'accent `site_pluriannuel`), écarte les points
superposés, met le titre (« Données de nidification des … ») et exporte `maps/Cartes_nidification__<clé>.png`. La
légende ne montre que les espèces de la carte, plus le symbole « Site occupé au moins 3 années » (couche de légende
seule, jamais dessinée). La brique `cartes_word` insère les images dans les sous-parties.

### §6 Dortoirs

| Élément | Placeholder | Contenu |
|---|---|---|
| Tableau | 🤖 `{{TABLE_DORTOIRS}}` | rapaces et grands voiliers ayant au moins une donnée de dortoir |
| Carte 12 (synthèse) | 🤖 `{{Carte12_dortoir_toutes_donnees}}` | zones de dortoir de toutes les espèces, couleur unique |
| Cartes par groupe | 🤖 `{{CARTES_DORTOIRS}}` | une carte par groupe d'espèces (§5 bis : mêmes groupes, 6 espèces au plus, carte « Autres »), titre « Données de dortoirs des … » |
| Rayon | 🤖 `{{DORTOIRS_RAYON}}` | « 750 m » (phrase de méthode du 1er paragraphe) |
| Description | ✍️ | — |

Depuis le 22/10/2026 (brique `cartes_dortoirs`, couche `vm_eolienne_dortoirs_cartes`, scripts
`outils/word/cartes_dortoirs_migration.py` et `outils/qgis/ajout_cartes_dortoirs_migration.py`) :
- **zones de dortoir** : tampon de `dortoirs_rayon_m` (750 m) autour de chaque donnée de dortoir d'une espèce,
  fusionnés quand ils se touchent ; une zone par ligne (nb_data, nb_sites, derniere_obs, nb_annee, donnee_cachee).
  750 m correspond à l'ancien rond de 8 mm des cartes 12 à l'échelle du rapport (1 mm ≈ 190 m) : ce n'était pas un
  tampon en mètres, seulement la taille du symbole ;
- **cartes** : les anciennes cartes 12.1 à 12.4 (listes de noms figées : 26 espèces non dessinées à Barbières, dont
  Milan noir, Héron garde-bœufs, Vautour fauve) sont remplacées par la mise en page modèle `Cartes_dortoirs` (une
  image par groupe, zones semi-transparentes à la couleur de l'espèce, même référentiel de couleurs que la
  nidification). La carte 12 garde la vue d'ensemble (toutes les espèces, couleur unique : couche « style fixe »,
  ni restylée ni filtrée au rendu). À Barbières : 37 espèces sur 11 cartes.

### §7 Migration

| Élément | Placeholder | Contenu |
|---|---|---|
| Espèces en migration | 🤖 `{{NB_MIGRATION_TOTAL}}` | toutes les espèces ayant au moins une donnée de migration |
| … dont à enjeux | 🤖 `{{NB_MIGRATION_ENJEUX}}` | rapaces et grands voiliers parmi elles |
| Tableau | 🤖 `{{TABLE_MIGRATION}}` | espèces à enjeux ; tableau par anneau + « Max ind. » (effectif maximal) |
| Cartes 13 à 15 | 🤖 | couche `vm_eolienne_migration_all` (nombre de données, espèces à enjeux, effectifs) |
| Cartes par espèce | 🤖 `{{CARTES_MIGRATION_ESPECES}}` | une carte par espèce : Milan royal (`migration_cartes_especes`), puis les espèces migratrices d'indice de vulnérabilité ≥ `migration_cartes_vulnerabilite_min` (4), par indice décroissant ; titre « Données de migration : … » |
| Seuil | 🤖 `{{MIGRATION_CARTES_SEUIL}}` | « 4 » (phrase du 1er paragraphe) |
| Description | ✍️ | — |

Depuis le 22/10/2026 (brique `cartes_migration`, couche `vm_eolienne_migration_especes`) : la carte 16 (Milan
royal, filtre par nom) est remplacée par la mise en page modèle `Cartes_migration`, clone de la carte 16 (rond creux,
taille selon l'effectif maximal `nb_ind_max`, légende des effectifs gardée) : une image par espèce, couleur de
l'espèce au contour (référentiel commun). Une espèce « migratrice » a au moins une donnée de migration (sélection
Migration). Utile hors de la région habituelle : les espèces emblématiques suivies changent. À Barbières : Milan
royal, Aigle royal, Balbuzard pêcheur, Vautour fauve, Vautour percnoptère, Busard cendré.

### §8 Sensibilité éolienne

| Élément | Placeholder | Contenu |
|---|---|---|
| Carte 17 : indice par maille | 🤖 `{{Carte17_sensibilite}}` | voir le calcul ci-dessous |
| Carte 17 bis : indice par maille à partir de la vulnérabilité | 🤖 `{{Carte17bis_vulnerabilite}}` | voir ci-dessous |
| Carte 18 : tampons de nidification | 🤖 `{{Carte18_sensibilite_tampon}}` | tampons autour des sites de nidification **certains**, fusionnés par espèce |

Calcul de l'indice, par maille de 1 km (couche `vm_eolienne_sensi_oiseau`, champ `tot_max_sensi`, de 0 à 7) :
- point de départ : la note de sensibilité maximale (0 à 4) parmi les espèces observées dans la maille ;
- +1 si un rapace ou un grand voilier y est nicheur probable ou certain ;
- +1 s'il y a un dortoir de rapace ou de grand voilier ;
- +1 s'il y a une donnée de migration de rapace ou de grand voilier.

**Carte 17 bis** (`{{Carte17bis_vulnerabilite}}`, ajoutée le 21/10/2026, couche `vm_eolienne_vuln_oiseau`) : même
calcul, en partant de l'**indice de vulnérabilité** le plus élevé des espèces de la maille (0,5 à 4,5, §4 bis ; 0 si
aucune espèce notée) au lieu de leur sensibilité, avec les mêmes bonus : champ `vulnerabilite`, de 0 à 7,5. Mêmes
classes et couleurs que la carte 17 (mailles de 3 et plus ; dernière classe 6 - 7,5). Décision : les deux cartes sont
proposées aux rédacteurs pour comparaison, avant de choisir une méthode. Sur Barbières (21/10/2026), 92 % des
mailles (1 504 / 1 636) sont dans la même classe sur les deux cartes : la plupart des mailles comptent une espèce de
sensibilité 3-4 dont la vulnérabilité est voisine ; les écarts touchent surtout la limite d'affichage (3). Champs de la couche : id, id_area,
vuln_especes, bonus_nidif, bonus_dortoir, bonus_migration, vulnerabilite, nb_data.

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
| Annexe 3 | 🤖 `{{TABLE_VULNERABILITE_ANNEXE}}` | indice de vulnérabilité de toutes les espèces (§4 bis) |

Les annexes chiroptères sont les annexes 4 à 6 (section 10.3).

---

## 4. Tableaux par anneau

Colonnes fixes :
- Nom vernaculaire ;
- Nom scientifique (en italique) ;
- Protection nationale ;
- LR France (nicheurs) ;
- LR France hivernants (tableau des dortoirs) ou LR France migrateurs (tableau de migration) ;
- LR AuRA ;
- **Vulnérabilité** (indice du §4 bis, juste après la LR régionale à la demande des rédacteurs, fond coloré à partir de 2,5) ;
- Sensibilité éolien ;
- Statut nidif. (tableaux de nidification seulement).

Puis, pour « Ensemble des zones » et pour chaque zone, deux colonnes : « Nb données » et « Dernière obs. ». Le tableau de migration en ajoute une troisième, « Max ind. ». Une case vide signifie qu'il n'y a aucune donnée dans cette zone. **Une zone où aucune espèce du tableau n'a de donnée n'est pas affichée** (gain de largeur ; « Ensemble des zones » est toujours affiché). Cela vaut pour les tableaux d'oiseaux, pas encore pour ceux des chiroptères.

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
| vm_eolienne_nidif | point | id, nom_vern, cd_nom, famille, ordre, nb_data, derniere_obs, nb_annee, oiso_status_nidif (`Nicheur certain` / `Nicheur probable`), donnee_cachee, precision_geo. **Sans la Cigogne noire**. Plus utilisée par les cartes du rapport (groupe de vérification du projet seulement) ; `vm_eolienne_nidif_cn` est supprimée (floutage dans `vm_eolienne_nidif_cartes`) |
| vm_eolienne_nidif_cartes | point | cartes de nidification par groupe (§5 bis) |
| vm_eolienne_nidif_tampon | polygone | lb_nom, nom_vern, distance_km, nb_data |
| vm_eolienne_dortoirs | point | id, nom_vern, cd_nom, famille, ordre, derniere_obs, nb_data, donnee_cachee, precision_geo (plus utilisée par les cartes du rapport) |
| vm_eolienne_dortoirs_cartes | polygone | zones de dortoir fusionnées par espèce (§6) : cle, cd_ref, nom, lb_nom, couleur, ordre_legende, nb_data, nb_sites, derniere_obs, nb_annee, donnee_cachee |
| vm_eolienne_migration_especes | point | cartes de migration par espèce (§7) : cle, cd_ref, nom, lb_nom, couleur, ordre_legende, nb_data, nb_ind_max, derniere_obs, donnee_cachee, precision_geo |
| vm_eolienne_migration_all | point | id, nom_vern, cd_nom, famille, ordre, nb_ind_max, derniere_obs, esp_enjeux (`enjeux` / `autres`), donnee_cachee, precision_geo |
| vm_eolienne_sensi_oiseau | maille 1 km | id, id_area, max_sensi, max_sensi_n/d/m, tot_max_sensi (les sum_* et tot_sensi reprennent les mêmes valeurs), vuln_especes |
| vm_eolienne_vuln_oiseau | maille 1 km | id, id_area, vuln_especes, bonus_nidif, bonus_dortoir, bonus_migration, vulnerabilite (carte 17 bis, ajoutée le 21/10/2026) |
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
| changer le seuil de l'indice de vulnérabilité (tableau principal, phrase, passereaux) | `vulnerabilite_seuil`, `vulnerabilite_seuil_inclus` (`true` : ≥ au lieu de >) |
| changer les espèces décrites par une phrase préremplie / contrôlées sur les cartes | `vulnerabilite_phrases_min` (4), `vulnerabilite_carte_min` (3) |
| ajouter une espèce aux tampons | `[params.tampons_nidification_km]`, par **nom scientifique** |
| prendre aussi les nicheurs probables pour les tampons | `tampons_statuts_nidif = ["Certain", "Probable"]` |
| changer le rayon des zonages | `zonage_rayon_km` |

Toute modification d'une règle doit aussi être reportée dans le texte du template et dans ce document.

---

## 7. Points de vigilance

- **Le §5.2 du template** parle de « statut de nicheuse certaine », alors que le tableau et le chiffre comptent les nicheurs **probables ou certains**.
- **Le §8.1 du template** parle d'un « nid d'une espèce de rapace à fort enjeu », alors que le +1 s'applique à **tout** rapace ou grand voilier nicheur probable ou certain (règle du R).
- **Dortoirs et migration** : la recherche dans les remarques exclut les négations simples (« pas de dortoir »), mais reste approximative (« migrateur ? »…). Relire les tableaux.
- **Tampons de nidification** : le cercle est centré sur le nid. Pour la Cigogne noire (5 km), le tampon révèle donc l'emplacement du nid, même si les cartes de nidification la floutent à 5 km.
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

**Activation** : analyse optionnelle `chiropteres`, activée par défaut par `analyse_eolien`. Toute la partie est délimitée dans le template par `{{#chiropteres}}` … `{{/chiropteres}}`, à deux endroits : le chapitre avant la conclusion, et les annexes 4 à 6 (annexes 3 à 5 avant l'ajout de l'annexe 3 des oiseaux, le 21/10/2026). Si l'analyse n'est pas demandée, ces sections sont retirées et la numérotation se recale.

Pour proposer plus tard un rapport sans chiroptères, il suffit d'ajouter au `dossier.toml` une ligne `analyse_eolien_oiseaux = []` dans `[declencheurs]`, puis la valeur correspondante dans la liste du formulaire QGIS.

### 10.1 Données

- **Une seule source : la VM principale.** DBchiro est déjà importé dans `gn_synthese` (source `dbChiroGCRA`), comme VisioNature et les partenaires. On n'interroge donc pas `src_dbchirogcra`. Une même donnée peut toutefois arriver par deux sources (ex. faune-france et dbChiroGCRA) : le dédoublonnage `sources_prioritaires` (section 2) garde la première.
- **Données et observations** : les suivis acoustiques produisent des centaines de contacts pour un même taxon, un même jour, au même point (96 % de répétitions sur la zone de test : 13 005 données pour 976 observations). Le rapport annonce les deux chiffres, puis **compte en observations** (un taxon, un jour, un lieu) : par anneau, dans le tableau de vulnérabilité et dans les annexes.
- **Genres et complexes gardés** (`chiro_rangs_non_especes = ["GN", "RES"]`). Ils sont fréquents pour les gîtes et colonies, par exemple « Pipistrelle indéterminée » ou « Oreillard indéterminé ». Ils comptent dans les **données** et les **gîtes**, jamais dans le **nombre d'espèces**.
- **Pseudo-taxons d'absence exclus**, par leur nom (« Aucune chauve-souris ou trace », « Aucune capture filet », « Aucun contact acoustique », « No aves »…) : ce sont des visites sans observation. Les complexes d'espèces ont eux aussi des `cd_nom` négatifs (« Pipistrelle de Kuhl / Nathusius », « Murin de grande taille », « Sérotine / Noctule ») : ils sont gardés (filtre corrigé en octobre 2026 ; avant, ils étaient perdus).
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
| Méthode | texte fixe | NP, NE, NH et classes, renvoi à l'annexe 6 |
| Connaissance | 🤖 `{{CHIRO_CONNAISSANCE}}` | nombre de données brutes et d'observations, nombre d'espèces, puis par anneau (en observations), dont les observations non précisées à l'espèce, puis « Précautions de lecture » si besoin |
| | 🤖 `{{TABLE_CHIRO_PERIMETRES}}` | observations, espèces et dernière observation par zone |
| | ✍️ | description de la connaissance |
| | 🤖 cartes 19 et 20 | nombre d'espèces et nombre de données par maille de 1 km |
| Vulnérabilité | 🤖 `{{CHIRO_VULN_EOLIEN}}`, `{{CHIRO_VULN_HABITAT}}` | listes des espèces à vulnérabilité forte ou très forte |
| | 🤖 `{{TABLE_CHIRO_VULNERABILITE}}` | tableau 5 du document : nom, nombre d'observations, LR France, LR AuRA, NH et classe, NE et classe ; tri par vulnérabilité éolien décroissante ; page A4 paysage (22/10/2026) |
| | ✍️ ×2 | description de la vulnérabilité habitat et de la vulnérabilité éolienne |
| | 🤖 cartes 21, 22, 23 | pipistrelles, noctules, sérotines et vespère |
| Gîtes et colonies | 🤖 `{{CHIRO_TEXTE_GITES}}` | nombre de sites de colonies (par taxon, années) et de gîtes hors reproduction |
| | ✍️ | description des gîtes |
| | 🤖 cartes 24 et 25 | colonies de reproduction, gîtes hors reproduction |
| Sensibilité | texte fixe | méthode de l'indice et des tampons |
| | 🤖 cartes 26 et 27 | indice par maille, tampons autour des gîtes |

**Annexes** (en paysage) :
- annexe 4, `{{TABLE_CHIRO_ESPECES}}` : tous les taxons par anneau ;
- annexe 5, `{{TABLE_CHIRO_GITES}}` : gîtes et colonies par taxon et par anneau (nombre de sites, effectif maximal) ;
- annexe 6, `{{TABLE_CHIRO_REFERENTIEL}}` : NSE, NHab et rayon par espèce.

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

Couches exportées dans `data/`. Les cartes **19 à 27** sont dans `qgis/projet_eolien.qgs` : pour chacune, un groupe de couches et une mise en page portant **le même nom** que le placeholder, clonée d'une carte oiseaux (bandeau, légendes, sources, logo). Les classes des symbologies sont **fixes** (elles ne dépendent pas de la zone) et les légendes n'affichent que les catégories présentes sur la carte. Première version générée par script : la mise en forme fine reste à reprendre dans QGIS.

| Couche | Géométrie | Champs |
|---|---|---|
| vm_eolienne_chiro_data | point | id, cd_nom, nom_vern, lb_nom, id_rang, **groupe** (pipistrelles, noctules, serotines_vespere, murins, rhinolophes, oreillards, autres), periode, gite, colonie, count_max, datetime, annee, anneau_ordre, lr_aura, n2k, source, precision_geo, donnee_cachee, ne, ne_classe, nh, nh_classe |
| vm_eolienne_etat_connaissance_chiro | maille 1 km | id, id_area, sum_nb_data (données brutes), sum_nb_obs (observations), sum_nb_esp |
| vm_eolienne_chiro_gites | point (un par site, taxon et type) | id, cd_nom, nom_vern, lb_nom, **type_gite**, nb_data, effectif_max, premiere_obs, derniere_obs, periodes, donnee_cachee, precision_geo, groupe, ne, ne_classe |
| vm_eolienne_chiro_gite_tampon | polygone | cd_nom, nom_vern, lb_nom, distance_m, rayon_par_defaut, nb_sites |
| vm_eolienne_sensi_chiro | maille 1 km | id, id_area, sensi_especes, bonus_colonie, bonus_gite, bonus_transit, **sensibilite**, nb_data |

| Mise en page | Couche, filtre et symbologie |
|---|---|
| Carte19_chiro_nb_especes | `vm_eolienne_etat_connaissance_chiro`, classes sur `sum_nb_esp` : 0 (genres seuls), 1-2, 3-5, 6-10, 11-15, 16 et + |
| Carte20_chiro_nb_donnees | idem, classes sur `sum_nb_obs` (observations, comme le texte ; `sum_nb_data` est gonflé par les répétitions acoustiques) : 1, 2-5, 6-10, 11-25, 26-50, 51 et + |
| Carte21_chiro_pipistrelles | `vm_eolienne_chiro_data`, `"groupe" = 'pipistrelles'`, une couleur par espèce (`nom_vern`), gris pour les taxons non identifiés à l'espèce |
| Carte22_chiro_noctules | idem, `"groupe" = 'noctules'` |
| Carte23_chiro_serotines_vespere | idem, `"groupe" = 'serotines_vespere'` |
| Carte24_chiro_colonies | `vm_eolienne_chiro_gites`, `"type_gite" = 'Colonie de reproduction'`, une couleur par groupe d'espèces (`groupe`), identique sur la carte 25 |
| Carte25_chiro_gites | idem, `"type_gite" = 'Gîte'` (une seule carte, plutôt que deux pour cause de légende trop longue comme dans le document) |
| Carte26_chiro_sensibilite | `vm_eolienne_sensi_chiro`, catégories 0 à 6 et + sur `sensibilite` |
| Carte27_chiro_tampons_gites | `vm_eolienne_chiro_gite_tampon` (contours seuls, couleur selon `distance_m` : 1, 5, 10, 20 km) + `vm_eolienne_chiro_gites` (étoile = colonie) |

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
| Tableaux NSE et NHab avec puces de critères | Remplacés par le référentiel en annexe 6, généré depuis le fichier CSV (une seule source) |
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
