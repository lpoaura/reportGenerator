# Outils de développement

Scripts pour tester un dossier sans toucher à la base, et pour modifier les projets QGIS et les templates Word **par
script** (pas à la main). Ils ne font pas partie du générateur : rien ici n'est lancé par `generate`.

Précautions (voir aussi `CLAUDE.md`) :
- les dossiers de sortie (rapports, `data/` avec des nids localisés) se créent **hors du dépôt** ;
- la base n'est lue qu'en lecture seule : la VM est une table temporaire, la session passe ensuite en lecture seule ;
- avant de modifier un template ou un projet, garder une copie de l'original hors du dépôt.

Prérequis : `poetry` (scripts Python), le Python de QGIS (`C:\Program Files\QGIS\3_40\bin\python-qgis-ltr.bat`, ou
`QGIS_PREFIX_PATH` pour une autre installation) pour `qgis/`, Word pour `verif/word_update.ps1`, et
[pymupdf](https://pypi.org/project/PyMuPDF/) pour les scripts de `verif/` qui lisent un PDF (non installé par
poetry : `pip install --target <dossier> pymupdf`, puis `PYTHONPATH=<dossier>`).

## 1. Dry-run complet d'un rapport (`dryrun/`)

```powershell
poetry run python outils/dryrun/dryrun_dossier.py <list_analyse|-> <id_area> <buffer> <nom> <dossier_sortie>
# ex. générique : poetry run python outils/dryrun/dryrun_dossier.py - 2337024 2 MontSaxonnex C:\temp\essai
# ex. éolien    : ... analyse_eolien 2337018 2 Barbieres C:\temp\essai_eolien
```

Comme `run_single.py` (toutes les briques, cartes QGIS, Word), mais la VM est une table temporaire et la date de la
demande n'est pas modifiée. `id_area` : une zone de demande (type `LPO_REPORT_STUDY`). La VM est gardée en cache
(dossier temporaire du système, ou `DRYRUN_CACHE`) : les essais suivants la rechargent en quelques secondes. Supprimer
le cache si le SQL de la VM change. Pour tester un projet QGIS ou un template modifié sans les installer :
`DRYRUN_QGIS=<projet.qgs>` et `DRYRUN_TEMPLATE=<template.docx>`. Pour remplacer des paramètres du `dossier.toml` :
`DRYRUN_PARAMS` en JSON. Exemple PLSOC sur la zone d'étude du plan, sans demande (`id_area` inutilisé) :
`$env:DRYRUN_PARAMS='{"annee": 2024, "emprise": "zone_etude:1"}'` puis `... dryrun_dossier.py plsoc 0 0 PLSOC_2024 C:\temp\plsoc`.

## 2. Cartes de l'état des connaissances dans un projet QGIS (`qgis/`)

`connaissance_qgis.py` ajoute à un projet, dans sa charte, les couches `connaissance_*` et les mises en page
`Connaissance_effort_donnees`, `Connaissance_effort_jours`, `Atlas_connaissance_groupes`, `Atlas_connaissance_croisee`
(idempotent : les existantes sont remplacées). Profils : `eolien` (modèle `Carte17_sensibilite`, aussi pour Natura
2000) et `generique` (modèle `statut_connaissance`).

```powershell
# 1. couches connaissance_* : dry-run du dossier (étape 1), dossier <sortie>\data
# 2. ajout au projet (écrit une copie hors du dépôt)
& "C:\Program Files\QGIS\3_40\bin\python-qgis-ltr.bat" outils/qgis/ajout_connaissance.py `
    src/reportgenerator/dossiers/eolien/qgis/projet_eolien.qgs <sortie>\data eolien C:\temp\projet_eolien\projet_eolien.qgs
# 3. essai : DRYRUN_QGIS=C:\temp\projet_eolien\projet_eolien.qgs + dry-run, contrôle des cartes (verif/)
# 4. installation dans le dépôt (chemins ./data/, refuse s'il reste un chemin vers le dossier de construction)
poetry run python outils/qgis/integrer_projet.py C:\temp\projet_eolien\projet_eolien.qgs `
    src/reportgenerator/dossiers/eolien/qgis/projet_eolien.qgs
```

Projet Natura 2000 : reconstruit en entier depuis le projet éolien (même charte) par `build_projet_n2000.py`
(`<projet_eolien.qgs> <dossier de travail contenant data/ d'un dry-run n2000>`), qui appelle `connaissance_qgis.py`,
puis installé avec `integrer_projet.py`.

`ajout_cartes_vulnerabilite.py <projet.qgs> <data_dir> <sortie.qgs>` (Python de QGIS) ajoute au projet éolien les
cartes `Carte11.2_nidif_passereaux` (couleurs par espèce construites au rendu) et `Carte17bis_vulnerabilite`
(couches `vm_eolienne_passereaux` et `vm_eolienne_vuln_oiseau` d'un dry-run) ; installation avec `integrer_projet.py`.

`ajout_cartes_groupes.py <projet.qgs> <data_dir> <sortie.qgs>` (Python de QGIS) remplace les cartes de nidification
6 à 11.2 du projet éolien par la mise en page modèle `Cartes_nidification` (couche `vm_eolienne_nidif_cartes` d'un
dry-run ; une image par groupe d'espèces au rendu, cf. METHODO éolien §5 bis) ; installation avec `integrer_projet.py`.

`ajout_cartes_dortoirs_migration.py <projet.qgs> <data_dir> <sortie.qgs>` (Python de QGIS) : mises en page modèles
`Cartes_dortoirs` (zones de dortoir par groupe, à la place des cartes 12.1 à 12.4 ; carte 12 de synthèse reprise sur
les zones, « style fixe ») et `Cartes_migration` (une image par espèce, à la place de la carte 16).

`inspect_layout.py <projet> <mise en page>` liste les éléments d'une mise en page (positions, légendes, textes).

`projet_oedic_coordination.py <projet_source.qgz> <projet_sortie.qgz>` (Python de QGIS) construit le projet de
coordination et de validation du suivi Œdicnème (PLSOC) sur le schéma `pr_oedic_news` (cf.
`docs/plsoc/sql/pr_oedic_news.sql`). Il reprend les fonds de carte du projet source, et ajoute :
- les couches de la saison suivie (filtre `annee = pr_oedic_news.f_annee_saison()`), l'historique et les tables de bilan ;
- les formulaires de saisie de `v_terrain_validation_nids` et `v_terrain_complement_couples` (seules couches
  modifiables) ;
- 4 thèmes de carte (coordination, validation, contrôle, historique).

Le projet source n'est pas modifié. Le lanceur `.bat` de QGIS ne supporte pas les chemins contenant des espaces : travailler
dans un dossier sans espace, puis copier le `.qgz`. La connexion passe par le service `gnlpoaura` : aucun identifiant n'est
enregistré dans le projet.

## 3. Templates Word (`word/`)

Le texte de la section « État des connaissances par maille » est écrit **une seule fois**, dans
`textes_connaissance.py` (les chiffres et seuils sont des placeholders fournis par les briques).

- `section_connaissance.py <generique|eolien> <template> <sortie>` : ajoute la section au template générique (fin de
  « État des connaissances ») ou éolien (chapitre après « Connaissance des oiseaux »), et ajuste les paragraphes
  masqués qui numérotent les sous-titres (voir les METHODO). Refuse un template qui a déjà la section : pour la
  regénérer après une modification du texte, repartir du template d'avant la section (historique git).
- `convert_template_n2000.py <Synthese_faune_Combe_Savoie_2025.docx> <sortie>` : construit tout le template Natura
  2000 à partir du rapport de référence (gardé hors du dépôt), section de connaissance comprise.
- `section_vulnerabilite.py <template.docx> <sortie>` : ajoute au template éolien l'indice de vulnérabilité des
  oiseaux (sous-titres du chapitre « Espèces à enjeux », phrases des espèces les plus vulnérables, contrôle des
  cartes, carte 17 bis, annexe 3, annexes chiroptères renumérotées 4 à 6, compteurs ajustés). Puis
  `section_passereaux.py <template.docx> <sortie>` : sous-partie « Les passereaux » du chapitre Nidification.
  Chacun refuse un template qui a déjà sa section.
- `cartes_groupes.py <template.docx> <sortie>` : cartes de nidification par groupe dans le template éolien (cartes
  6 à 11.2 remplacées par `{{CARTES_NIDIF_<SOUS-PARTIE>}}`, sous-partie « Autres espèces nicheuses à enjeux »,
  paragraphe de lecture des cartes).
- `cartes_dortoirs_migration.py <template.docx> <sortie>` : cartes 12.1 à 12.4 -> `{{CARTES_DORTOIRS}}` (par groupe),
  carte 16 -> `{{CARTES_MIGRATION_ESPECES}}` (par espèce), phrases de méthode.
- `tableaux_paysage.py <template.docx> <sortie> [PLACEHOLDER ...]` : tableaux larges sur une page A4 paysage, la suite
  repassant en portrait (par défaut `TABLE_VULNERABILITE` et `TABLE_CHIRO_VULNERABILITE`).
- `template_plsoc.py <template_natura2000.docx> <sortie.docx>` : construit le template du rapport annuel PLSOC
  (`dossiers/plsoc/template.docx`). Il reprend la page de garde et la charte du template Natura 2000, puis écrit la
  trame des rapports 2018-2024 : textes fixes, placeholders, passages à rédiger. Il se relance après toute
  modification de la trame.
- `plan_docx.py <docx>` : titres et placeholders d'un document (structure).

## 4. Vérifications (`verif/`)

| Script | Usage |
|---|---|
| `word_update.ps1 <rapport.docx>` | ouvre le rapport dans Word (sans l'afficher), met à jour les champs et le sommaire, exporte `<rapport>_maj.pdf` ; « fichier endommagé » = échec |
| `montage_png.py <maps> <sortie.png> <carte>...` | planche de cartes côte à côte |
| `crop_legendes.py <maps> <sortie.png> <carte>...` | bandeaux titre et légende (chevauchements) |
| `recadre.py <image> <sortie> x0 y0 x1 y1` | détail en pleine résolution (contours, étiquettes) |
| `montage_pages.py <pdf> <sortie.png> <de> <à> [dpi]` | planche de pages du PDF |
| `pages_mot.py <pdf> <texte>...` | pages contenant un texte |
| `titres_corps.py <pdf>` | numéros des titres dans le corps du rapport |
