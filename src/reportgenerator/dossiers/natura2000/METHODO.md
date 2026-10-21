# Rapport Natura 2000 : process et contenu

> **Première version complète** (données, tableaux, cartes, atlas, template), testée sur Combe de Savoie (section 10).

**Rapport produit** : « Synthèse de données sur la zone Natura 2000 « {{AREA_NAME}} » ». C'est un document de base : le
générateur remplit les chiffres, les tableaux et les cartes, puis le chargé d'études rédige les textes par espèce, la
discussion et ajoute les photos.

**Déclenchement** : la valeur `n2000` dans le champ `list_analyse` du formulaire QGIS. Aucune analyse optionnelle.

**Zone d'étude** : le périmètre du site saisi dans le formulaire (un ou plusieurs polygones : chaque polygone est un
secteur). Le nom saisi est repris tel quel dans le titre et les textes.

**Destinataire** : client (gestionnaire du site). Pas de floutage.

**Modèle** : le rapport « Synthèse faune Combe de Savoie 2025 » (site FR8201773), sans la partie « Résultats par
secteur » (p. 64 à 76), mise de côté pour l'instant.

**Origine** : les scripts R `traitement_dossier.R` et `SQL_script/*.sql` produisaient les tableaux, les données et le
projet QGIS, mais pas le rapport. Leurs règles sont reprises et corrigées (section 9).

---

## 1. Process de génération

```text
Formulaire QGIS (list_analyse = n2000)
  │
  ▼
socle_data            VM commune : toute la faune, 10 dernières années, jusqu'à 20 km,
                      anneaux 0 (site) / 1 km / 10 km / 20 km
  │
  ▼
n2000_perimetre       surface, nombre de secteurs, période, rayons appliqués
n2000_synthese        chiffres clés du site, tableau des espèces N2000
n2000_especes         statut biologique (nicheur / migrateur / hivernant), listes par groupe (annexes)
n2000_chiropteres     tableau des chiroptères N2000, couches gîtes et colonies
zonages               zonages environnementaux (carte de localisation)
couches_qgis_n2000    couches GPKG pour le projet QGIS
  │
  ▼
cartography           cartes + atlas par espèce (une image par espèce N2000)
  │
  ▼
Rendu Word            template.docx rempli → outputs/<zone>/<zone>.docx (+ copies Excel des tableaux)
```

## 2. Données prises en compte

| Critère | Valeur | Paramètre (`dossier.toml`) |
|---|---|---|
| Taxons | **toute la faune** (règne Animalia), rang espèce. Sous-espèces rattachées à l'espèce. Genres et complexes gardés quand ils sont « N2000 » (voir 3.2) | `groupes_taxo = "faune"` |
| Période | depuis le 1er janvier de (année en cours − 10) : 2015-2025 pour un rapport de 2025 | `annees` |
| Validation | statuts 0, 1 et 2 (comme tous les dossiers) | `statuts_validation` |
| Emprise | site + 20 km (rayon maximal) | `anneaux_km = [1, 10, 20]` |
| Doublons entre sources | même taxon, même jour, même cellule de 100 m : une seule source gardée | `sources_prioritaires` |
| Effectifs | effectif vide ou 0 → 1 ; **effectif ≥ 9999 → non renseigné** (valeur de saisie « inconnu », exclue des maximums ; vaut pour tous les dossiers) | — |
| Liste rouge régionale | `lr_aura` | `lr_regionale` |

### Rayon de prise en compte selon le taxon

Une donnée n'est retenue que si elle est à moins du rayon de son taxon. Le filtre est fait **dans la VM**
(paramètres `rayon_defaut_km` et `[params.rayons_km]`) : elle ne contient que les données utiles, ce qui la rend
beaucoup plus rapide (66 s au lieu de 9 min 30 sur Combe de Savoie). Le site et les rayons sont des **zones
disjointes** (une donnée n'est comptée qu'une fois), mais les tableaux ne sont **pas** découpés par anneau : ils
indiquent seulement si l'espèce est connue **dans le site** ou **à proximité**.

| Taxons | Rayon | Comment le modifier |
|---|---|---|
| tous (défaut) | 1 km | `rayon_defaut_km` |
| rapaces (Accipitriformes, Falconiformes, Strigiformes) | 10 km | `[params.rayons_km]`, par ordre |
| chiroptères | 10 km | idem, par ordre |
| Loup gris, Lynx boréal | 20 km | idem, par espèce (nom scientifique, sous-espèces comprises) |

Ajouter une espèce à grand rayon (ex. vautours, Loutre d'Europe) = **une ligne** dans `[params.rayons_km]`, puis la
phrase des méthodes du rapport se met à jour seule.

## 3. Espèces Natura 2000

### 3.1 Définition

Une espèce est « Natura 2000 » si :
- **oiseau** : inscrite à l'**annexe I de la directive Oiseaux** ;
- **autre groupe** : inscrite à l'**annexe II de la directive Habitats-Faune-Flore**.

Source : colonne `n2k` de `taxonomie.mv_c_statut`, lue **selon le groupe**. Pour les oiseaux, les annexes II/1, II/2 et
III de la colonne sont celles de la directive Oiseaux (espèces chassables) : elles ne rendent pas une espèce N2000
(sinon le Vanneau, le Cygne tuberculé ou l'Étourneau le seraient).

### 3.2 Genres et complexes d'espèces

Certaines données ne sont pas identifiées à l'espèce, mais concernent forcément une espèce N2000 : « Chabots » (*Cottus*,
sans statut dans la table alors que le Chabot commun est en annexe II), « Grand Murin / Petit Murin ». Ce sont des
enjeux : ces taxons sont **gardés et affichés** (tableaux, atlas), marqués « (complexe) », et **ne comptent pas dans le
nombre d'espèces**.

Règle :
- **genres** : N2000 si **toutes leurs espèces** (de la faune de France, dans `mv_c_statut`) le sont : détection
  automatique (ex. *Cottus*, *Rhinolophus*) ;
- **complexes** « A / B » (ex. « Myotis myotis / M. blythii », Murin de grande taille) : TAXREF ne les rattache pas
  à leurs espèces (leur parent est le genre), la détection automatique est impossible : **liste du dossier**
  `n2000_taxons_complexes`.

### 3.2 bis Taxons écartés

`n2000_taxons_exclus` (nom scientifique) retire un taxon de la liste N2000 :
- **statut erroné** dans `mv_c_statut` : *Salmo trutta* (truite commune et truite de mer, même cd_ref) y est en
  annexe II, ce qui ferait de toute donnée de truite une donnée N2000 (l'annexe II concerne le Saumon atlantique) ;
- les **données ponctuelles douteuses** (ex. animal échappé : une Tortue grecque en 2023 à Combe de Savoie) ne sont
  **pas** exclues automatiquement : le chargé d'études les retire du rapport s'il les juge non pertinentes (décision).

### 3.3 Statut biologique (oiseaux)

Dans le tableau récapitulatif, chaque oiseau N2000 reçoit un ou plusieurs statuts (ex. « Nicheur, hivernant ») :

| Statut | Règle (validée) |
|---|---|
| Nicheur (possible / probable / certain) | au moins une donnée avec ce statut de nidification ; le plus fort est affiché |
| Hivernant | au moins une donnée entre le 1er décembre et le 31 janvier |
| Migrateur | au moins une donnée avec un comportement de migration, ou « migr » dans la remarque de l'observateur (hors négation), comme pour l'éolien |
| (vide) | aucun des trois : rien ne précise le statut, la cellule reste vide (à compléter par le chargé d'études si besoin) |



### 3.4 Cortèges (classement d'expert)

Le classement des oiseaux en cortèges (zones humides, forestiers, rupestres, milieux ouverts) reste **manuel** pour
l'instant. Prévu : un fichier `ref_corteges.csv` (cd_ref ; cortège), vide au départ, complété au fil des rapports.
Quand une espèce y figure, le tableau récapitulatif affiche son cortège et les cartes peuvent être rangées par cortège.

## 4. Contenu du rapport, section par section

Légende : 🤖 automatique · ✍️ à rédiger (surligné en jaune dans le template).

### Couverture, page 2

| Élément | Contenu |
|---|---|
| Titre | 🤖 « Synthèse de données sur la zone Natura 2000 « {{AREA_NAME}} » » |
| Historique des versions, rédaction et validation | ✍️ |

### §1 Contexte et objectifs

| Élément | Placeholder | Contenu |
|---|---|---|
| Surface et nombre de secteurs | 🤖 `{{SURFACE_HA}}`, `{{NB_SECTEURS}}` | surface du site (ha) et nombre de polygones |
| Commanditaire, objectifs | ✍️ | — |
| Carte de localisation | 🤖 | site, contours, zonages environnementaux |

### §2 Matériels et méthodes

| Élément | Contenu |
|---|---|
| Présentation de la base, points importants | texte fixe |
| Période | 🤖 `{{PERIODE_ETUDE}}` |
| Rayons de prise en compte | 🤖 `{{TEXTE_RAYONS}}` (généré depuis `[params.rayons_km]`) |
| Carte de pression d'observation | 🤖 points + carte de chaleur |

### §3.1 Ensemble du site

| Élément | Contenu |
|---|---|
| Chiffres clés | 🤖 `{{TEXTE_CHIFFRES_SITE}}` : « Sur la période 2015-2025, X données pour Y espèces ont été recensées au sein du site Natura 2000 (Z données pour W espèces en comptant le kilomètre autour du site). Dans le site, le groupe le plus largement connu… » |
| Complexes | 🤖 `{{TEXTE_COMPLEXES}}` : taxons non identifiés à l'espèce présentés comme complexes |
| Graphiques par groupe | 🤖 `{{CHART_ESPECES_GROUPES}}`, `{{CHART_DONNEES_GROUPES}}` : nombre d'espèces et de données par groupe taxonomique **dans le site** (mêmes graphiques que le rapport générique, barres horizontales) ; au-delà de 15 groupes, les plus petits sont regroupés en « Autres groupes (n) ». Remplacent les graphiques Word du rapport de Combe de Savoie, dont les chiffres étaient figés |
| Niveau de connaissance par groupe | ✍️ |
| Phrase de lecture des tableaux | texte fixe : site / à proximité, rayon selon le taxon |
| **Tableau des espèces N2000** | 🤖 `{{TABLE_ESPECES_N2000}}` : groupe, nom vernaculaire, nom scientifique, **présence** (dans le site / à proximité), **statut biologique** (oiseaux), nombre de données, dernière année, (cortège si renseigné). Copie Excel |
| Espèces à grand rayon | 🤖 `{{LISTE_ESPECES_GRAND_RAYON}}` : espèces N2000 à rayon étendu connues seulement à proximité (ex. Loup gris, Lynx boréal) |

### §3.1.1 État des connaissances par groupe taxonomique (porter à connaissance)

Briques **communes** aux dossiers (`connaissance`, `couches_qgis_connaissance`, `connaissance_atlas`, cf. `doc.md`) :
la même section existe dans les dossiers générique et éolien (20/10/2026). Les paramètres propres à Natura 2000
sont dans le `dossier.toml` (emprise 1 km, vocabulaire « le site », titres de niveau 4).

Section destinée au porter à connaissance : le chargé d'études la supprime s'il ne la transmet pas (décision). Elle ne
mesure pas la biodiversité mais **ce que les données permettent d'en dire**, et répond à trois questions : où a-t-on
prospecté ? connaît-on bien chaque groupe à cet endroit ? où sont les espèces à enjeux ? Le Word explique la démarche
et la lecture de chaque carte (décision : « expliquer au maximum la démarche et l'interprétation »).

**Grille** : mailles de **1 km** (`grille = "M1"`) couvrant le site et le kilomètre autour, **même grille sur toutes les
cartes** (décision : éviter les erreurs de lecture). Les mailles sans donnée sont affichées en blanc (couche
`connaissance_grille`) pour distinguer « aucune donnée » de « hors zone ». Données : celles du rapport (période, validation
0/1/2, absences et 9999 exclus, genres et complexes compris pour l'effort), au rayon de 1 km quel que soit le taxon.
La maille est calculée spatialement sur la grille `grille_connaissance` (M1).

**Indicateurs par maille et par groupe** (+ « Tous groupes »), requête `connaissance_mailles` :
- `nb_donnees` ; `nb_jours` = nombre de dates différentes avec au moins une donnée (mesure de l'effort, moins sensible
  aux inventaires intensifs et aux comptages qu'un nombre de données) ;
- `nb_especes` et `pct_pool_local` = espèces de la maille / **espèces du groupe connues à `pool_local_km` (10 km)** du
  site (décision : référence locale réaliste ; une référence régionale pénalise les groupes riches en espèces
  localisées, ex. reptiles 9 / 42 en région contre 9 / 12 à 10 km) ;
- `peu_donnees` = moins de `connaissance_seuil_donnees` (2) données du groupe : maille hachurée, « lecture prudente »
  (décision : < 2 données = mauvaise connaissance) ;
- `nb_enjeux` = espèces à enjeux de la maille : **N2000** (définition 3.1) **ou liste rouge régionale CR/EN/VU/NT** (à
  défaut nationale) ; oiseaux : nicheurs seulement (possible/probable/certain, `enjeux_oiseaux_nicheurs_seulement`).
  Sélection SQL `enjeu_sql` (`analysis/connaissance/selections.py`, commune aux dossiers) ;
- `classe_croisee` = effort × richesse, 3 niveaux chacun (constantes `SEUILS_EFFORT_JOURS` = 3 / 10 jours et
  `SEUILS_RICHESSE_PCT` = 25 / 50 % dans `analysis/n2000/tables.py`).

**Groupes cartographiés** (décision du 19/10/2026) : au moins `connaissance_min_especes_site` (4) espèces **dans le
site** ; en dessous, l'atlas des espèces et le tableau suffisent. L'effort de prospection ne bloque plus la carte :
une campagne d'inventaire d'une journée menée par un spécialiste peut être plus complète que plusieurs passages
opportunistes, et la carte reste utile pour voir si les espèces sont regroupées ou réparties. Si la médiane des
jours d'observation du groupe par maille est inférieure à `connaissance_alerte_jours_median` (2), les cartes du
groupe sont précédées d'un **avertissement** court (italique, sous le titre du groupe : il doit tenir sur la page
de la carte) et le texte sous le tableau explique la limite (passages ponctuels, ligne « 1 - 2 j » de la carte
croisée). Sur Combe de Savoie : 21 groupes cartographiés, dont 12 avec avertissement.
(Ancienne règle, jusqu'au 19/10/2026 : au moins 10 mailles et une médiane d'au moins 2 jours, soit 8 groupes.)

Limites connues : pour les groupes à très grand pool local (coléoptères : 592 espèces à 10 km), presque toutes les
mailles sont sous 10 % : la carte montre surtout où le groupe a été noté et les espèces à enjeux. Le groupe
« Autres » (hétérogène) est cartographié s'il atteint le seuil.

| Élément | Contenu |
|---|---|
| Introduction | texte fixe (démarche, limites) + 🤖 période |
| Où a-t-on prospecté ? | texte fixe + 🤖 cartes `Connaissance_effort_donnees` (nombre de données par maille) et `Connaissance_effort_jours` (jours d'observation), toutes espèces ; maille grise = 1 donnée / 1 jour |
| Connaît-on bien chaque groupe ? | texte fixe + 🤖 `{{POOL_LOCAL_KM}}`, `{{TABLE_CONNAISSANCE_GROUPES}}` (groupe, espèces dans le site, espèces site + 1 km, espèces à 10 km, part locale, espèces en région pour mémoire, mailles avec données, dont < 2 données, médiane de jours par maille, carte oui/non ; copie Excel `3_connaissance_groupes`), `{{TEXTE_GROUPES_CARTOGRAPHIES}}` (critère, liste des groupes, groupes avec avertissement et limite de l'exercice, depuis les paramètres) |
| Comment lire les cartes ? | texte fixe + 🤖 `{{SEUIL_PEU_DONNEES}}`, `{{TEXTE_LECTURE_CROISEE}}` (classes, depuis les constantes) : part des espèces locales, hachures, chiffre rouge = espèces à enjeux, quatre coins de la carte croisée (gris clair : peu prospecté ; bleu : prospecté, peu d'espèces ; rouge : riche malgré peu de prospection ; brun foncé : riche et bien connu) |
| Atlas | 🤖 `{{ATLAS_CONNAISSANCE_GROUPES}}` : par groupe cartographié, un titre de niveau 4, l'avertissement éventuel, puis deux cartes « Part des espèces locales – groupe » et « Richesse et prospection – groupe » |
| Commentaire | ✍️ groupes et secteurs les moins connus, prospections à prévoir |

Les seuils du `dossier.toml` alimentent les textes du Word ; **les légendes des cartes QGIS (classes « 1 donnée »,
« moins de 2 données », matrice 3 × 3) sont écrites dans le projet** : à reprendre dans QGIS si un seuil change.

### §3.1.1 à 3.1.6 Oiseaux nicheurs, amphibiens, odonates, papillons, poissons, mammifères, autres groupes

Par groupe :
- 🤖 un chiffre (ex. « 14 espèces d'oiseaux nicheuses inscrites à l'annexe I ») ;
- 🤖 **une carte par espèce N2000** (atlas en points : nicheur certain / probable / possible / autres données), avec sa
  légende « Répartition de … ». Oiseaux : **nicheurs seulement** pour l'instant (`atlas_oiseaux_non_nicheurs = false`),
  les autres sont cités dans le tableau récapitulatif ;
- ✍️ après chaque carte : photo et texte de l'espèce.

Les groupes sans espèce N2000 n'ont pas de section (ex. reptiles sur Combe de Savoie).

### §3.1.7 Chiroptères (rayon 10 km)

| Élément | Contenu |
|---|---|
| Chiffre | 🤖 nombre d'espèces N2000 connues dans le site et à proximité |
| **Tableau** | 🤖 `{{TABLE_CHIRO_N2000}}` : nom vernaculaire, nom scientifique, nb de données, LR France, LR AuRA, N2000, protection nationale, effectif max, statut (colonie de reproduction / gîte sans reproduction / contact). Copie Excel |
| Carte 1 | 🤖 présence des chiroptères N2000, une couleur par espèce |
| Carte 2 | 🤖 gîtes et colonies, **toutes espèces**, taille selon l'effectif (1-3, 3-10, 10-30, 30-100, 100-300, > 300), couleur selon reproduction / sans reproduction |
| Carte 3 | 🤖 colonies de reproduction par espèce, **toutes espèces** (plusieurs espèces d'un même gîte disposées en cercle) |
| Carte 4 | 🤖 gîtes sans reproduction des espèces N2000 |
| Atlas | 🤖 une carte par espèce (et complexe) N2000 : gîtes et colonies, taille selon l'effectif |
| Interprétation | ✍️ |

### §3.2 Résultats par secteur

Mis de côté pour l'instant.

### §4 Discussions et propositions d'actions

✍️

### Annexes : listes par groupe

🤖 Une annexe par groupe présent (oiseaux, mammifères, amphibiens, reptiles, poissons, invertébrés…), espèces **dans
le site et à proximité** (rayon du taxon), avec la colonne « présence ». Colonnes : nom vernaculaire, (nom scientifique),
protection nationale, Natura 2000, LR France, LR AuRA, nombre de données, dernière année, statut de nidification
(oiseaux), effectif max. Copie Excel de chaque annexe.

## 4 bis. Template Word (`template.docx`)

Construit à partir du rapport « Synthèse faune Combe de Savoie 2025 » (même mise en page, styles, couverture, pieds
de page), par script :
- chiffres, tableaux, cartes et atlas remplacés par des placeholders (liste en section 4) ;
- textes d'expert propres au site **surlignés en jaune** (à réécrire ou supprimer) : présentation du site,
  commanditaire, niveau de connaissance des groupes, commentaires des chiroptères, discussion ;
- photos et textes par espèce supprimés : l'atlas insère pour chaque espèce sa carte, sa légende numérotée et un
  paragraphe jaune « [Photo et texte de l'espèce à rédiger] » ;
- nouvelle section **3.1.1 État des connaissances par groupe taxonomique** (porter à connaissance, à supprimer si elle
  n'est pas transmise) ; les espèces passent en **3.1.2 Espèces Natura 2000**, suivies de l'atlas (un titre par
  groupe : Oiseaux nicheurs, Mammifères…) ;
- partie « Résultats par secteur » retirée ; section des cartes chiroptères passée d'A3 paysage à A4 portrait ;
  annexes en paysage, un tableau par groupe ;
- **sommaire et numéros de figures mis à jour par Word à l'ouverture** (Word demande « Mettre à jour les champs ? » :
  répondre Oui ; sinon F9 après Ctrl+A).

## 5. Cartes

Projet QGIS : `qgis/projet_n2000.qgs`, construit à partir du projet éolien (**même charte** : format portrait, bandeaux
bleus en haut et dans la légende, bloc LPO, fond OpenStreetMap, contours 1 / 10 / 20 km). Comme pour les autres dossiers,
chaque carte = un groupe de couches et une mise en page du même nom ; les couches pointent vers `./data/<couche>.gpkg`.
Le texte « Sources » des cartes est calculé à partir des sources réellement présentes dans les données (au moins 1 %
des données, puis « et autres partenaires ») et passé au projet (variable `@sources`) ; il est aussi disponible pour le
Word (`{{SOURCES_DONNEES}}`). Libellés des sources : `analysis/n2000/tables.py` et `[params.sources_libelles]`.

### Cartes simples

| Mise en page | Contenu | Emprise |
|---|---|---|
| Carte01_localisation | site, contours, zonages environnementaux (50 km) | site + 30 km |
| Carte02_pression_observation | données du site et du kilomètre autour + carte de chaleur | contour 1 km + 1 maille |
| Connaissance_effort_donnees | nombre de données par maille de 1 km, toutes espèces (site + 1 km) ; 1 donnée en gris | contour 1 km + 1 maille |
| Connaissance_effort_jours | nombre de jours d'observation par maille de 1 km, toutes espèces ; 1 jour en gris | contour 1 km + 1 maille |
| Carte04_chiro_presence_n2000 | observations des chiroptères N2000, une couleur par espèce | contour 10 km + marge |
| Carte05_chiro_gites_colonies | gîtes et colonies, toutes espèces : taille = effectif maximal (1-3, 3-10, 10-30, 30-100, 100-300, > 300), bleu = reproduction, orange = sans reproduction | contour 10 km + marge |
| Carte06_chiro_colonies_especes | colonies de reproduction, toutes espèces (décision) : une couleur par espèce, espèces d'un même gîte disposées en cercle | contour 10 km + marge |
| Carte07_chiro_gites_n2000 | gîtes sans reproduction des espèces N2000, taille = effectif | contour 10 km + marge |

### Atlas (une image par page, `<mise en page>__<clé>.png`)

| Mise en page | Une page par | Couverture |
|---|---|---|
| Atlas_especes_n2000 | taxon N2000 (hors chiroptères ; oiseaux nicheurs seulement), points par type de donnée (nicheur certain / probable / possible / autres) | `n2000_atlas_especes` |
| Atlas_chiro_gites | taxon N2000 de chiroptère ayant un gîte ou une colonie (complexes compris) | `n2000_atlas_chiro` |
| Atlas_connaissance_groupes | groupe cartographié (§3.1.1) : part des espèces locales par maille (< 10 / 10-25 / 25-50 / 50-75 / > 75 %, viridis), hachures si < 2 données, nombre d'espèces à enjeux dans un rond rouge | `connaissance_atlas_groupes` |
| Atlas_connaissance_croisee | même groupe : classe effort × richesse, palette bivariée 3 × 3 (légende en matrice dessinée dans la mise en page) | `connaissance_atlas_groupes` |

Les deux atlas de la connaissance ont une **emprise fixe**, la même que les cartes d'effort 03a/03b (contour 1 km + une
maille, pour tous les groupes : les cartes se comparent d'un groupe à l'autre). Variables de projet passées par le
générateur : `@sources`, `@pool_local_km`. Couvertures : un attribut `rayon_km` par taxon (atlas des espèces et des
gîtes).

### Emprises (décision du 19/10/2026)

Toutes les emprises sont calculées par la brique `couches_qgis_n2000` à partir du **rectangle englobant le site**, et
non plus à partir des données ni de la couche `zone_etude` (qui contient aussi le tampon de la demande et les 50 km
autour : les cartes s'étendaient jusqu'à 20 km) :
- **cartes d'espèces** (atlas des espèces, atlas des gîtes, cartes 04 à 07 des chiroptères) : **contour du rayon de
  prise en compte du taxon** (1, 10 ou 20 km, même règle que la vue, `[params.rayons_km]`) + une marge (10 % du rayon,
  au moins 500 m : `emprise_marge_ratio`, `emprise_marge_min_km`). Toutes les espèces d'un même rayon ont donc **le
  même cadrage** (ex. tous les rapaces et chiroptères sur le contour 10 km), et toutes leurs données sont visibles
  puisqu'elles sont dans ce rayon ;
- **cartes par maille et pression d'observation** (02, 03a, 03b, atlas de la connaissance) : contour 1 km + une maille
  de marge (`emprise_marge_mailles_km`), pour que toutes les mailles soient entières ;
- carte de localisation : site + 30 km (`layout_buffers_m`).

Passage au rendu QGIS : `extent_bbox` (rectangle du site, emprise commune) et `layout_extents` (rectangle par mise en
page) dans la configuration `qgis_render` ; couvertures des atlas = ces rectangles.

**Dans le Word** : `{{ATLAS_ESPECES_N2000}}`, `{{ATLAS_CHIRO_GITES}}`, `{{ATLAS_CONNAISSANCE_GROUPES}}` insèrent toutes
les cartes de l'atlas, chacune suivie de sa légende numérotée (« Figure n : Répartition – … », numéro mis à jour avec
F9) et d'un paragraphe surligné à rédiger (photo et texte de l'espèce). L'atlas des espèces est découpé par groupe
(titre de niveau 3 : « Oiseaux nicheurs », « Mammifères »…). La carte, sa légende et son texte tiennent sur une page.
L'atlas « état des connaissances » est destiné au porter à connaissance : le chargé d'études supprime la section s'il
ne veut pas la transmettre (décision).

Les données sont affichées **au point précis**, données cachées par les observateurs comprises (décision : les clients
sont des gestionnaires qui protègent les sites).

Couches produites (brique `couches_qgis_n2000`) : `n2000_limit`, `n2000_donnees`, `n2000_chiro_donnees`,
`n2000_chiro_gites`, et les couvertures `n2000_atlas_especes`, `n2000_atlas_chiro` ; brique commune
`couches_qgis_connaissance` : `connaissance_mailles`, `connaissance_grille`, `connaissance_atlas_groupes`
(+ `zone_etude`, `zones_protegees` de la brique `cartography`).

Correction du 20/10/2026 : `LEGENDE_ZONE_ETUDE` (repris du projet éolien) traçait aussi le tampon de la demande et
les 50 km autour (`zone_etude.gpkg`) : filtre `"secteur" = 'Zone d''étude'`. Les couches des cartes de connaissance
sont dessinées sous les contours (zone d'étude, contours 1 / 10 / 20 km) : ils restent visibles sur les mailles
(ils étaient cachés par les mailles opaques).

## 6. Paramètres (`dossier.toml`)

À compléter pendant le développement : `anneaux_km`, `rayon_defaut_km`, `[params.rayons_km]`, `annees`,
`groupes_taxo`, `statuts_validation`, `n2000_taxons_complexes`, `periode_hivernage`, `periodes_migration`,
`atlas_oiseaux_non_nicheurs`, `zonage_rayon_km`.

État des connaissances (§3.1.1) : `grille` (M1), `pool_local_km` (10), `connaissance_seuil_donnees` (2),
`connaissance_min_especes_site` (4), `connaissance_alerte_jours_median` (2), `enjeux_oiseaux_nicheurs_seulement` (true).
Emprises : `emprise_marge_ratio` (0,1), `emprise_marge_min_km` (0,5), `emprise_marge_mailles_km` (1).

## 7. Points de vigilance

- Les données sont opportunistes : une absence ne prouve pas l'absence de l'espèce (ex. chiroptères dans le site).
- Les statuts biologiques sont déduits des dates et des comportements saisis : à relire par le chargé d'études.
- La colonne « présence » distingue le site des abords ; pour les espèces à grand rayon, « à proximité » peut vouloir
  dire jusqu'à 20 km.

## 8. Points ouverts

1. Cortèges : référentiel à constituer (3.4).
2. Cartes des oiseaux N2000 non nicheurs : prévues mais désactivées.
3. Résultats par secteur (p. 64-76 du modèle) : à traiter plus tard.
4. Symbologie des cartes : ajustements possibles dans QGIS.
5. État des connaissances : approche testée sur le rapport N2000 ; à étendre aux autres dossiers si elle est jugée
   parlante (décision).
6. Colonne « Espèces en région » du tableau de connaissance : vue `src_gestion.vm_reportgenerator_refere_taxo` (rang
   ES, regroupement un peu différent) ; les groupes résiduels peuvent y être sous-estimés (ex. « Hémiptères » : 5 en
   région, la plupart des espèces étant classées en Punaises ou Cigales). Donnée pour mémoire seulement.

## 9. Reprise des scripts R : corrections prévues

| Dans le script R | Correction |
|---|---|
| Zone d'étude et contour 1 km plein superposés : les données du site comptées deux fois | zones disjointes |
| Colonnes 10 et 20 km absentes des tableaux, alors que rapaces, chiroptères et grands prédateurs sont extraits jusque-là | colonne « présence », un seul comptage par espèce dans son rayon |
| Chiroptères : tampon « 1 km + rayon du gîte de l'espèce » (1 m si inconnu), données au-delà de 10 km perdues ; Murin de Bechstein classé « dans le site » à tort | rayon fixe de 10 km |
| Espèces N2000 repérées par motifs `ilike` sur le texte `n2k` | lecture exacte des annexes, selon le groupe |
| Taxons au genre exclus (rang espèce seulement) | genres et complexes N2000 gardés |
| Statuts de validation 1 et 2 | 0, 1 et 2 |
| Effectifs 9999 dans les maximums | exclus |
| Jointure directe sur `src_dbchirogcra` | champs gîte / colonie / période de la synthèse étendue |
| Grille codée en dur (`id_type = 73`) | paramètre `grille` |
| `lr_choix_reg = "lr_ra"` déclaré, `lr_aura` utilisé | `lr_aura` |
| Projet QGIS en chemins absolus, couche en base avec une géométrie en dur | chemins relatifs, couches produites par le générateur |

## 10. Test sur Combe de Savoie (FR8201773), données au 19/11/2025

Comparaison avec le rapport « Synthèse faune Combe de Savoie 2025 ».

| Élément | Rapport 2025 | Générateur | Explication |
|---|---|---|---|
| Données / espèces « au sein du site » | 41 699 / 448 | **14 509 / 906** dans le site ; 51 388 / 1 284 site + 1 km | le chiffre du rapport portait en fait sur **site + 1 km** (couche « Résultats plugin LPO » : polygone tampon), statuts 1-2 et groupes restreints ; le générateur donne les deux chiffres. Plus d'espèces : toute la faune est prise en compte |
| Oiseaux | 180 esp. / 36 013 données | 173 esp. / 9 842 données dans le site | idem (site seul) |
| Chiroptères N2000 | 8 espèces, aucune dans le site | 8 espèces, dont 5 dans le site | données acoustiques du CEN Savoie de juin-juillet 2025 (source `gn2pg_cen_savoie`), intégrées depuis |
| Oiseaux N2000 nicheurs | 14 | 17 | + Chevêchette d'Europe, Chouette de Tengmalm (rapaces nocturnes : rayon de 10 km, nids en montagne), Engoulevent (possible) |
| Liste N2000 | 48 taxons (sélection) | 80 espèces + 1 complexe | rapaces jusqu'à 10 km (vautours, Gypaète…), invertébrés (Lucane, Rosalie, Écaille chinée), poissons (Blageon, Bouvière) |
| Truite de mer | — | écartée | statut erroné dans `mv_c_statut` (3.2 bis) |

Les mêmes données sont retrouvées : les écarts viennent du périmètre compté, des rayons par taxon et des données
ajoutées depuis.
