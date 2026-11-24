# Analyse : diagnostic agro-écologique « Espèces PNA et IAE » (futur dossier `diag_iae`)

Version du 22/10/2026. Sources : le modèle `DIAG_PNA_IAE_modele.docx` et 6 diagnostics rendus en 2026 (Champ libre,
Charlotte Pantos, EARL du Coucou, Ferme du May, ferme Brunel, ferme de Priroda), la fiche terrain
`fiche_terrain_LPO.xlsx` (documents gardés hors du dépôt), les tables `src_gestion.agri_*` et les mares
(`src_gestion.v_mares_enrichies`). Les flux IGN cités ci-dessous ont été interrogés le 22/10/2026.

Objectif : produire à partir d'une zone dessinée (le périmètre de la ferme) un **brouillon du diagnostic**. Le chargé
de mission y ajoute ensuite la visite, les pratiques et les préconisations. Le rapport est remis à l'agriculteur :
il s'agit d'un **destinataire externe**, ce qui impose un floutage (voir §6).

---

## 1. Ce que contiennent les rapports actuels

### 1.1 Trame (identique dans les 7 documents)

| § | Contenu | Rédaction aujourd'hui |
|---|---|---|
| Page de garde | nom de la ferme, commune, photo, référent LPO (nom, tél., courriel), crédits | manuelle |
| 1. Présentation de la ferme | historique, productions, SAU, commune, altitude, labels | manuelle |
| 2.1 Périmètre d'action et espèces PNA | **texte fixe par secteur du programme** (« Allier - Bocage Bourbonnais », « Rhône - Coteaux du Lyonnais », « Haute-Loire - Loire Amont », « Zone Voironnais »…) : espèces PNA concernées, actions envisagées, partenaires ; puis contexte local | copier-coller + manuel |
| 2.2 Pratiques de la ferme | échanges avec l'agriculteur, photos, parfois sol (texture, pH) | manuelle |
| 2.3 Aménagements favorables | IAE existantes, préconisations, **carte de l'existant et des préconisations** | manuelle (carte QGIS faite à la main) |
| 3. Hiérarchisation des enjeux | tableau priorité / espèces PNA / préconisation / projet retenu / période / matériel ; tableau des conseils de gestion ; « à faire par la ferme » | manuelle |
| 4. Mise en œuvre | fiches techniques (haie, mare : coupes, paliers), photos du chantier | manuelle |
| Annexes | charte d'engagement 2025-2027 (adresse, n° de parcelle, type d'aménagement, espèces ciblées) | texte fixe, champs à remplir |

Constats :
- La partie « Hiérarchisation » du modèle contient un **exemple** (ferme du Potiron) recopié tel quel dans 3 rapports
  sur 6 (Ferme du May, Priroda, Charlotte Pantos) : pré-remplir ce tableau à partir des données éviterait ces oublis.
- Les en-têtes de secteur ne sont pas homogènes (styles Titre5, Titre6, Titre8, numérotation manuelle « 2.1. »).

### 1.2 Cartes produites à la main

| Carte | Rapports | Couches |
|---|---|---|
| Localisation de la ferme et observations d'espèces PNA (cercle de ~1 km, 2020-2025) | Ferme du May | point de la ferme, données VisioNature par espèce PNA, liste d'« autres espèces PNA potentielles » |
| Parcellaire + nidification | EARL du Coucou | parcellaire, prairies permanentes (RPG 2024), **données Pies-grièches / Milan royal / Vipère étiquetées possible / probable / certain**, propositions de plantation |
| Existant (occupation du sol) | Brunel, Champ libre, Pantos, Ferme du May | parcelles par type (prairie permanente / temporaire / de fauche, maraîchage, bosquet), haies (typologie : peu dense, dense, avec arbres à cavités, alignements), arbres et arbustes isolés, cours d'eau, mares, murets, clôtures, cadastre |
| Préconisations | toutes | arbres isolés, haies (plantation, spontanée, sèche), bosquets, mares (dont « mares SVJ »), hibernaculum, gîtes à chiroptères, nichoirs, gestion des surfaces (fauche tardive…) |

Fonds : orthophoto (CRAIG 2022, Google, Bing selon les auteurs), carton de localisation départemental, charte LPO AuRA
(bandeau bleu).

### 1.3 Fiche terrain

Groupes PNA suivis : **Chauves-souris, Vipères, Sonneur, Milan royal, Pies-grièches, Messicoles, Odonates,
Papillons**. Aménagements proposés : haie, haie spontanée, arbres isolés, bosquet (par 10 arbres), mare, pierres
sèches, hibernaculum / zone de ponte, semis de messicoles, gîtes à chiroptères.

---

## 2. Données disponibles en base

### 2.1 Observations (VM de synthèse)

La VM commune (`socle_data`) contient déjà ce qu'il faut pour les cartes d'espèces :
- `oiso_status_nidif` (Possible / Probable / Certain) et `oiso_code_nidif` (code atlas) pour les oiseaux. Exemple :
  la Pie-grièche écorcheur compte 11 000 à 14 000 données par an dans la synthèse depuis 2020, dont 1 100 à 1 500
  « certain » et 2 200 à 3 400 « probable » ;
- `bat_breed_colo` et `bat_is_gite` pour les colonies et les gîtes de chiroptères ;
- `date_max`, `precision_geo`, `donnee_cachee`, `pna_en_cours`, `pna_ex`.

Manque pour les autres groupes : le **stade de vie** (`id_nomenclature_life_stage` : ponte, larve, juvénile, exuvie).
Il n'est pas dans la VM. Il permettrait une notion de reproduction pour le Sonneur (pontes, têtards), les odonates
(exuvies, émergences), les vipères (juvéniles) et les papillons (chenilles, nids communautaires du Damier). Pour une
v1, ces groupes seraient cartographiés en **présence** avec la notion de récence.

**Liste des espèces PNA** : le statut `PNA` de la BDC TaxRef (`taxonomie.bdc_statut_text`) ne convient pas. Les
Pies-grièches, le Sonneur et les vipères n'y figurent qu'en « PNA terminé » (`exPNA`), et il compte de nombreux taxons
ultramarins. La liste doit donc être **maîtrisée dans le `dossier.toml`** : groupe PNA, `cd_ref`, sensibilité et
rayon de territoire. Taxons repérés dans les rapports :

| Groupe PNA | Espèces (cd_ref) |
|---|---|
| Pies-grièches | écorcheur 3807, grise 3814, à tête rousse 4460, méridionale 199409, à poitrine rose 3811 |
| Milan royal | 2844 |
| Vipères | aspic 78130, péliade 78141 |
| Sonneur | Sonneur à ventre jaune 212 |
| Chauves-souris | ordre Chiroptera (Grand rhinolophe 60295…) |
| Odonates | Agrion de Mercure 65133 + liste PNA libellules à fixer |
| Papillons | Damier de la Succise 53865 + liste PNA papillons de jour à fixer |
| Messicoles | flore : hors base faune, à traiter à part (CBN) |
| Hors PNA mais cités | Chevêche 3511, Effraie 3482, Huppe 3590, Bruant proyer 4686 (`especes_vises` des IAE) |

### 2.2 Infrastructures agro-écologiques (`src_gestion.agri_*`)

| Table / vue | Contenu au 22/10/2026 |
|---|---|
| `agri_infrastructures` | 98 IAE (point ou ligne, L93) : `type_infra` (contrainte : Haie, Arbre, Perchoir, Hibernaculum, Muret, Bande_enherbee), `date_creation`, `nom_agri`, `tel_agri`, `programme_financement`, `type_chantier`, `especes_vises`, `remarque` |
| `agri_details_infra` | 94 lignes (1-1 avec l'IAE) : nb de rangs, de plants, d'espèces végétales, typologie de haie, essences, hauteurs, longueur, Végétal local, protection gibier |
| `agri_suivi_visites` | **vide** |
| `v_agri_haies`, `_arbres`, `_perchoirs`, `_hibernaculums`, `_murets`, `_bandes_enherbees` | une vue par type (jointure infra + détails) |

Bilan : 39 haies (5,5 km, 3 724 plants, 25 agriculteurs, 2021-2026), 27 perchoirs, 23 arbres, 8 hibernaculums,
1 muret, 0 bande enherbée. Répartition : Ain, Allier, Ardèche, Drôme, Loire, Puy-de-Dôme, Rhône, et 3 haies en
Vaucluse (limite de la Drôme, à vérifier).

S'y ajoutent les **mares** créées ou restaurées par la LPO (`v_mares_enrichies`, 1 792 mares). Cadres agricoles :
« Agri Mare » 24, « Fond vert IAE espèces PNA » 15, « Accompagnement agriculteurs » 11, sans compter les CVB et les
mesures compensatoires.

Limites pour le diagnostic :
1. **Pas de notion de ferme ni de diagnostic** : seul `nom_agri` (texte libre) relie les IAE. Les IAE d'une ferme ne
   se retrouvent que par intersection spatiale avec le périmètre dessiné.
2. **Pas de statut** : on ne distingue pas un élément *existant relevé*, *préconisé*, *retenu* ou *réalisé*. Or c'est
   la légende de toutes les cartes des diagnostics.
3. **Types manquants** : mare (gérée à part), gîte à chiroptères, nichoir, bosquet, verger ou pré-verger, haie
   spontanée ou sèche, pierrier, semis de messicoles. Les surfaces (bosquet, bande) n'ont pas de géométrie polygone.
4. **Champs libres non normalisés** :
   - `especes_vises` : « PGTR », « Pieègrièche grise », « bruant broyer » / « Bruant Proyer » ;
   - `programme_financement` : 4 graphies de « Pacte haie » ;
   - `typologie_haie` : « YTrois strate », « 3 strates », « trois strates ».
5. **Données personnelles** (`nom_agri`, `tel_agri`) dans la même table que la géométrie : elles ne doivent sortir ni
   dans les GPKG ni dans les cartes de bilan.

### 2.3 Autres couches en base

- `lpoaura_afo."RPGPARCELLES_GRAPHIQUES_2015..2024"` : **extrait de la Loire seulement** (6 468 parcelles en 2024),
  inutilisable à l'échelle régionale. Préférer le flux IGN (§3).
- `lpoaura_afo.bdd_ign_hydro` (BD TOPAGE / cours d'eau), CLC 2000-2018, `ref_geo.clc18_fr`.
- `ref_geo.l_areas` : communes, départements, EPCI, ZNIEFF, Natura 2000, ENS, PNR, APB, zones LPO (brique `zonages`
  réutilisable telle quelle).

---

## 3. Flux externes utiles (vérifiés le 22/10/2026)

Test dans un carré de 2 × 2 km autour d'une haie LPO du Puy-de-Dôme : 256 haies DSB, 19 arbres isolés, 180 haies,
48 bosquets, 32 alignements d'arbres, 19 broussailles et 1 mare (RPG surfaces non agricoles 2025), 132 parcelles RPG.

| Besoin du diagnostic | Source | Couche / service | Accès |
|---|---|---|---|
| Assolement, prairies permanentes / temporaires, bio | IGN - RPG 2025 | `LANDUSE.AGRICULTURE2025:parcelles_graphiques` (champs `code_group`, `code_cultu`, `pp`, `bio`, `iae`) ; `IGNF_RPG_PRAIRIES-PERMANENTES_2025:prairies_permanentes` ; `PRAIRIES.SENSIBLES.BCAE:prairies_sensibles` | WFS `data.geopf.fr/wfs` |
| **Arbres isolés, haies, bosquets, alignements, mares, murets** (l'« existant ») | IGN - RPG surfaces non agricoles 2025 (éléments déclarés à la PAC) | `IGNF_RPG_SURFACES-NON-AGRICOLES_2025:surfaces_non_agricoles_vegetation_ponctuelle` (arbres), `…_vegetation_surfacique` (haie, bosquet, arbres alignés, broussailles), `…_autres_elements` (mare, surface en eau), `…_element_artificialise` ; champs `type`, `nb_arbres`, `mur_tradi` | WFS |
| Haies (linéaire national, toutes surfaces) | IGN / OFB - Dispositif de suivi des bocages | `HAIES.BOCAGES:haie` (= `BDTOPO_V3:haie`) ; WMTS `IGNF_BD-HAIE-V1_2020` | WFS / WMTS |
| N° de parcelle (cartes, charte) | IGN - Parcellaire Express (PCI) | `CADASTRALPARCELS.PARCELLAIRE_EXPRESS:parcelle` | WFS / WMTS |
| Cours d'eau, plans d'eau, bâtiments | IGN - BD TOPO | `BDTOPO_V3:cours_d_eau`, `troncon_hydrographique`, `surface_hydrographique`, `plan_d_eau`, `batiment` | WFS |
| Fond de carte | IGN / CRAIG | `ORTHOIMAGERY.ORTHOPHOTOS` (IGN) ; CRAIG `tiles.craig.fr/ortho/service`, couches `ortho_2013` à `ortho_2025` (meilleure résolution en AuRA) | WMTS / WMS |
| **Évolution du bocage** (comparaison avant / après) | IGN - orthophotos historiques | `ORTHOIMAGERY.ORTHOPHOTOS.1950-1965`, `.1965-1980`, `.1980-1995` | WMTS |
| Hauteur de végétation (vieux arbres, haies hautes) | IGN - LiDAR HD | `IGNF_LIDAR-HD_MNH_…` (MNH) | WMTS |
| Altitude, pente | IGN | `ELEVATION.ELEVATIONGRIDCOVERAGE`, `ELEVATION.SLOPES` | WMTS / API altimétrie |
| Contexte bocager de l'EPCI | ADEME / IGN | `ADEME_EPCI_lineaire-haie-total` | WMTS |
| Continuités écologiques | Région / DREAL - SRADDET AuRA | réservoirs et corridors de la trame verte et bleue | DataARA / GéoIDE (URL à vérifier) |
| Zones humides, pelouses sèches | DREAL / CEN AuRA / départements | inventaires départementaux | à rapatrier (URL à vérifier) |
| Sols (faisabilité d'une mare, texture) | Gis Sol - Référentiel régional pédologique | unités cartographiques de sol | WMS Gis Sol (à vérifier) |

Choix technique :
- **Fonds** (ortho, ortho historique, cadastre) : couches WMS/WMTS directement dans le projet QGIS, sans code.
- **Données à compter** (linéaire de haies par hectare, nombre d'arbres isolés, part de prairies permanentes) : une
  brique qui télécharge le WFS sur l'emprise et l'écrit en GPKG `data/<couche>.gpkg`. Les cartes suivent alors la
  règle actuelle (couches GPKG redirigées) et le rapport reste reproductible.
- Le RPG est anonyme : les parcelles de la ferme sont celles qui intersectent le **périmètre dessiné** (seuil de
  recouvrement à fixer, ex. 50 %).

---

## 4. Ce qui est automatisable

Légende : **A** = automatique, **S** = semi-automatique (pré-rempli à compléter), **M** = reste manuel.

| § du rapport | Contenu généré | Données | Niveau |
|---|---|---|---|
| Page de garde | nom de la ferme (`area_name`), référent (`referee`), date, commune(s) et département | demande, `ref_geo` | A |
| 1. Présentation | « La ferme s'étend sur X ha (périmètre dessiné), commune(s) de …, altitude moyenne … m. » ; tableau d'assolement RPG (surfaces par grand type, part de prairies permanentes, parcelles bio) ; carte 1 de localisation (carton départemental + ortho) | demande, RPG WFS, altimétrie | S (texte de présentation M) |
| 2.1 Périmètre et espèces PNA | texte du **secteur du programme** choisi par intersection (si les secteurs existent en polygones, §5) ; zonages (brique `zonages`) ; **tableau des espèces PNA** dans le rayon : groupe, espèce, nombre de données, dernière année, statut de nidification maximal, distance au périmètre, présence sur la ferme | VM, liste PNA du `dossier.toml` | A |
| 2.1 Cartes espèces | carte 2 de **synthèse PNA** autour de la ferme (type Ferme du May) ; cartes 3.x, **une par espèce PNA présente** (§4.1) | VM | A |
| 2.2 Pratiques | — | — | M |
| 2.3 Aménagements | carte 4 de **l'existant** : parcelles RPG par type, haies DSB, éléments PAC (arbres isolés, bosquets, alignements, mares), cours d'eau, mares LPO, IAE LPO déjà réalisées ; indicateurs (m de haie/ha, arbres isolés/ha, part de prairies permanentes) | WFS IGN, `agri_*`, mares | A |
| 2.3 Préconisations | carte 5 des préconisations : le **projet QGIS de la ferme** (copié dans la sortie, `projet_<zone>.qgs`) contient une couche vide « préconisations » à dessiner, puis la carte est réexportée | saisie | S, A une fois le modèle `agri_` enrichi (§5) |
| 3. Hiérarchisation | tableau **pré-rempli** : une ligne par groupe PNA présent, triée par enjeu (nicheur certain sur la ferme > nicheur dans le rayon > présence), avec la préconisation type du groupe (table du `dossier.toml` : Pies-grièches → haie épineuse, arbres isolés, perchoirs ; Milan royal → arbres, bosquets ; Chauves-souris → gîte, haie, mare ; Sonneur → mares, ornières ; Vipères → hibernaculum, muret, lisière ; Odonates → mare, gestion des fossés ; Papillons → fauche tardive) ; colonnes « projet retenu, période, matériel » surlignées en jaune | VM, `dossier.toml` | S |
| 4. Mise en œuvre | tableau et carte des **IAE réalisées sur la ferme** (type, date, longueur, plants, essences, programme) et des mares créées ou restaurées | `agri_*`, mares | A (fiches techniques M) |
| 5. (option) Bilan territorial | IAE et mares réalisées par la LPO dans le rayon ou le secteur : chiffres par type et par année, carte (§4.2) | `agri_*`, mares | A |
| Annexe charte | texte fixe ; n° de parcelle des aménagements pré-rempli depuis le cadastre | PCI WFS | S |

### 4.1 Cartes par espèce PNA : nidification et zones de nidification

Une image par espèce : le mécanisme `pages` existe déjà (cartes de migration et de nidification éoliennes, une
image par espèce ou par groupe). Contenu proposé :

- **Points** colorés par statut : nicheur certain / probable / possible / observation sans indice de nidification
  (oiseaux) ; colonie, gîte, autre contact (chiroptères) ; présence (autres groupes, en attendant le stade de vie).
- **Zones de nidification** : regroupement des données probable + certain d'une espèce par `ST_ClusterDBSCAN`, avec un
  rayon de territoire propre à l'espèce dans le `dossier.toml` (ex. 150 m Pie-grièche écorcheur, 300 m PG grise,
  500 m Milan royal). Le contour est une zone tampon de ce rayon. Pour chaque zone : années distinctes de nidification,
  dernière année, statut maximal. Classes :

  | Classe | Règle (seuils dans le `dossier.toml`) |
  |---|---|
  | Régulière et récente | ≥ 3 années distinctes sur la période et dernière nidification ≥ N-2 |
  | Récente | dernière nidification ≥ N-2 (N = année en cours ou dernière saison terminée) |
  | Régulière, non revue | ≥ 3 années distinctes, dernière < N-2 |
  | Ancienne | autres |

- Période : 10 ans par défaut (paramètre `annees` de la VM).
- Rayon : `buffer` de la demande (1 à 5 km ; le rapport de la Ferme du May montre 1 km et les données sur 2 km).
- Le texte associé est pré-rédigé : « La Pie-grièche écorcheur niche de façon régulière à 350 m de la ferme (6 années
  depuis 2017, dernière nidification certaine en 2026). »

### 4.2 Bilan des IAE réalisées

Réalisable dès maintenant avec `agri_*` + `v_mares_enrichies` :
- carte des IAE par type (haie en ligne, arbre / perchoir / hibernaculum en point, mare), avec étiquette de l'année ;
- chiffres : linéaire de haies, nombre de plants, part en Végétal local, nombre d'arbres, de perchoirs, d'hibernaculums
  et de mares, par programme et par année ;
- dans le diagnostic : IAE de la ferme et des fermes voisines (rayon) ;
- en dossier à part (`bilan_iae`, déclenché sur n'importe quelle zone : département, EPCI, secteur) : bilan d'un
  programme pour les financeurs (Fonds vert IAE PNA, FEADER, Pacte haie).

Les noms et téléphones des agriculteurs n'entrent pas dans les GPKG ; seule la ferme diagnostiquée est nommée.

---

## 5. Données à avoir en base (recommandations)

Par ordre d'intérêt pour le rapport :

1. **Statut des IAE** dans `agri_infrastructures` : `existant` (relevé au diagnostic) / `préconisé` / `retenu` /
   `réalisé` / `abandonné`, avec `date_proposition` et `date_realisation`. Ce champ conditionne les cartes
   « existant / préconisations » et le bilan.
2. **Ferme et diagnostic** : table `agri_fermes` (nom, périmètre, référent, date de visite, secteur, consentement de
   diffusion) et clé `id_ferme` dans `agri_infrastructures`. Les coordonnées personnelles quittent la table
   géographique.
3. **Types manquants** : mare (lien vers `src_gestion.mare` par uuid, plutôt qu'un doublon), gîte à chiroptères,
   nichoir, bosquet, verger / pré-verger, haie spontanée, haie sèche, pierrier, semis de messicoles ; géométrie
   polygone admise pour les surfaces.
4. **Nomenclatures** à la place du texte libre :
   - espèces visées : liste multiple reliée aux groupes PNA ;
   - programme de financement ;
   - typologie de haie (1, 2 ou 3 strates ; dense / peu dense ; avec arbres à cavités) ;
   - protection.
5. **Saisie terrain** : un projet Mergin « diagnostic IAE », comme pour les mares (`from_mergin`), avec périmètre,
   éléments existants et préconisations. Il alimente directement les tables ci-dessus et remplace les couches
   dessinées dans chaque projet QGIS personnel.
6. **Secteurs du programme** en polygones, avec leur texte (espèces PNA, actions, partenaires) : table dans
   `src_gestion`, ou type de zone LPO dans `ref_geo`. Le §2.1 devient alors automatique.
7. `agri_suivi_visites` (vide) : à utiliser pour la reprise des plantations, ce qui permettrait un taux de survie
   dans le bilan.
8. Côté VM : ajouter le stade de vie (`id_nomenclature_life_stage`) pour la reproduction des non-oiseaux.
9. Rapatriements utiles (copie locale, sans dépendre d'un flux) : RPG régional complet (le RPG en base ne couvre que la
   Loire), trame verte et bleue du SRADDET, inventaires de zones humides.

Rappel : rien de cela ne touche la vue des demandes. Le type de rapport passe par `list_analyse` (ex. `diag_iae`).

---

## 6. Points de vigilance

- **Destinataire externe** : le diagnostic est remis à l'agriculteur, et parfois aux partenaires (ComCom, Paysans de
  Nature). Il faut exclure `donnee_cachee` et représenter les espèces sensibles (Milan royal, Pie-grièche grise…)
  par zone ou par maille, jamais par point de nid. La liste et la règle sont à fixer avec le référent PNA.
- **Périmètre** : les fermes ont souvent des parcelles éclatées (Brunel : Maurines + Deux-Verges). La zone de demande
  doit accepter un multipolygone. Le rayon de contexte se calcule autour de l'ensemble.
- **Échelle des cartes** : la ferme fait de 1,7 ha (Champ libre) à 154 ha (fiche terrain). L'emprise se règle sur le
  périmètre (`extent_layer`), avec une marge. Les cartes d'espèces suivent le rayon de contexte.
- **RPG** : déclaratif, millésime N-1, anonyme. L'« existant » PAC ne couvre que les surfaces déclarées. La couche
  DSB complète pour les haies, et le relevé terrain reste la référence.
- **Messicoles** : flore, absente de la base faune. Section manuelle, ou données du CBN si une convention existe.
- **Zone de test** : aucune demande `LPO_REPORT_STUDY` ne correspond à une ferme. Il en faudra une (périmètre d'une
  ferme déjà diagnostiquée, ex. EARL du Coucou) pour comparer avec le rapport fait à la main.

---

## 7. Proposition de phasage

| Phase | Contenu | Données |
|---|---|---|
| **v1** | dossier `diag_iae` : template repris du modèle (page de garde, trame, charte) ; localisation ; zonages ; tableau et cartes PNA par espèce (nidification + zones régulières / récentes) ; carte de synthèse ; IAE et mares LPO réalisées dans le rayon ; tableau de hiérarchisation pré-rempli ; projet QGIS de la ferme prêt à dessiner | base actuelle |
| **v2** | carte de l'existant (RPG SNA, haies DSB, cadastre, BD TOPO) et indicateurs paysagers ; tableau d'assolement ; ortho historique en option ; dossier `bilan_iae` | flux IGN (brique de téléchargement WFS → GPKG) |
| **v3** | carte des préconisations et chapitre « mise en œuvre » automatiques ; suivi des plantations | modèle `agri_` enrichi (§5), saisie Mergin |

## 8. Questions à trancher avant de coder

1. Liste définitive des espèces PNA par groupe, avec les espèces sensibles et leur mode de représentation.
2. Rayon de contexte par défaut (1, 2 ou 5 km).
3. Définitions : « nidification régulière » (≥ 3 années sur 10 ?), « récente » (N à N-2 ?), statuts retenus (probable +
   certain, ou aussi possible ?), rayon de territoire par espèce.
4. Les secteurs du programme existent-ils en polygones ? Qui maintient leurs textes ?
5. Évolution du modèle `agri_*` (statut, ferme, types) et saisie Mergin : qui porte le chantier en base ?
6. Charte graphique des cartes : bandeau LPO bleu des diagnostics récents (Brunel, Priroda, Ferme du May) ou charte
   du projet éolien / Natura 2000 ?
7. Une ferme de test et son rapport de référence pour le dry-run.
