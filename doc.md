# Documentation du générateur de rapports

## 1. Objectif

Le projet produit automatiquement des rapports Word à partir des données naturalistes de la base GeoNature LPO (PostgreSQL/PostGIS) : textes chiffrés, tableaux, graphiques et cartes QGIS.

Le rapport généré est **une base de travail**. Il ne remplace pas l'expertise : les collègues y ajoutent leur avis, le contexte local et les points de vigilance, dans les blocs prévus à cet effet (surlignés en jaune dans les templates).

Plusieurs **types de rapport** coexistent. Chacun a son modèle Word, son projet QGIS et ses analyses.

| Type | Déclenchement (`list_analyse`) | Description |
|---|---|---|
| `generique` | par défaut ; `atlas_nicheur` ajoute l'atlas | état des connaissances, tous taxons ([fiche](src/reportgenerator/dossiers/generique/METHODO.md)) |
| `eolien` | `analyse_eolien` | synthèse oiseaux + chiroptères pour un projet éolien ([fiche](src/reportgenerator/dossiers/eolien/METHODO.md)) |

---

## 2. Installation et utilisation

```bash
poetry install

# tous les rapports en attente (lecture de src_gestion.v_reportgenerator_areas_lpo)
poetry run reportgenerator generate --service gnlpoaura --limit 100
poetry run reportgenerator generate --service gnlpoaura --dry-run      # liste sans générer

# un rapport précis
poetry run reportgenerator run --service gnlpoaura --id_area 2337034 --area_name "TEST EOLIEN" \
    --referee "Nom" --buffer 5 --list_analyse "analyse_eolien" --output "TEST EOLIEN.docx"

# outils (sans base ni QGIS)
poetry run reportgenerator dossiers                    # types de rapport et leurs analyses
poetry run reportgenerator check --dossier eolien      # vérifie le template Word et les briques
poetry run pytest                                      # tests
```

⚠️ `run` et `generate` **marquent la demande comme traitée** (`date_reportgenerate`) dès qu'un rapport est produit sans erreur. Pour tester sans clôturer de vraies demandes, utiliser une zone de test dédiée.

### Dossier de sortie

Les rapports sont écrits dans `<sortie>/<nom de la zone>/`. Le dossier de sortie est choisi dans cet ordre :
1. l'option `--output_dir` ;
2. la variable d'environnement `OUTPUT_DIR` (utilisée par Docker) ;
3. `src/reportgenerator/outputs/`, ignoré par git.

**Le dossier de la zone est vidé à chaque génération.**

### QGIS

Les cartes sont produites par l'interpréteur Python de QGIS 3.40, dans un processus séparé. Il est détecté automatiquement ; sinon, définir `REPORTGENERATOR_QGIS_PYTHON` et `REPORTGENERATOR_QGIS_PREFIX` (voir le README).

---

## 3. Fonctionnement

```text
Formulaire QGIS ──► src_gestion.v_reportgenerator_areas_lpo (id_area, list_analyse, buffer…)
                          │
                          ▼
   type de rapport = dossier dont un "declencheur" figure dans list_analyse, sinon generique
                          │
                          ▼
   dossier.toml : briques obligatoires + optionnelles demandées, paramètres
                          │
                          ▼
   pipeline : briques exécutées dans l'ordre (dépendances "requires" ajoutées automatiquement)
     socle_data (VM) → analyses (textes, tableaux, graphiques) → couches GPKG → cartes QGIS
                          │
                          ▼
   renderer : template.docx rempli → <zone>.docx ; VM supprimée ; date mise à jour si succès
```

### Organisation du code

```text
src/reportgenerator/
├── cli.py                 commandes run / generate / dossiers / check
├── run_single.py          génération d'un rapport
├── run_queue.py           demandes en attente (batch)
├── queries.py             VM principale (paramétrable) et requêtes communes
├── core/
│   ├── dossier.py         lecture des dossier.toml, choix du type de rapport
│   ├── registry.py        déclaration des briques (@register_brick)
│   ├── context.py         ReportContext transmis aux briques
│   ├── pipeline.py        ordre d'exécution, commande check
│   └── renderer.py        remplissage du Word
├── bricks/                lien entre le métier et les placeholders (common, generique, eolien)
├── analysis/              code métier : requêtes, calculs, graphiques, tableaux, cartographie
│   ├── eolien/            sélections, requêtes, couches QGIS, mises en forme du rapport éolien
│   ├── cartography/       export GPKG, lancement et script de rendu QGIS
│   └── common/tables/     insertion des tableaux Word (espèces, zonages, tableaux par anneau)
├── dossiers/<type>/       dossier.toml, template.docx, METHODO.md, (qgis/)
├── templates/             projet QGIS du rapport générique, atlas, polices
└── outputs/               rapports générés (non versionné)
```

### La VM principale

Toutes les analyses lisent une seule vue matérialisée, `lpoaura_afo.vm_reportgenerator_data_<date>_<code>`, créée par la brique `socle_data`. Son nom est **unique pour chaque génération** : plusieurs générations peuvent tourner en même temps (deux terminaux, le serveur et un test local) sans se gêner. Elle est supprimée à la fin ; une vue restée après un arrêt brutal est supprimée par une génération suivante au bout d'un jour. Ses paramètres viennent du `dossier.toml` :

| Paramètre | Effet | Générique | Éolien |
|---|---|---|---|
| `anneaux_km` | rayons des anneaux ; le plus grand fixe l'emprise ; colonne `anneau_ordre` | `[buffer]` | `[1, 6, 20]` |
| `annees` | ne garde que les N dernières années | toutes | 10 |
| `groupes_taxo` | groupes taxonomiques conservés | 8 groupes | Oiseaux |
| `grille` | grille des mailles (`geom_maille`) | automatique | M1 |
| `statuts_validation` | statuts de validation conservés | 0, 1, 2 | 0, 1, 2 |
| `sensibilite_eolien` | ajoute `sensibilite_eolien` (`partage.sensibilite_oiseaux`) | non | oui |

La VM porte un **nom unique** : deux rapports ne peuvent pas être générés en même temps. Elle est supprimée en fin de génération, même en cas d'échec.

---

## 4. Templates Word

Les valeurs à insérer sont des **placeholders** : `{{NOM}}`.

| Type | Exemple | Règles |
|---|---|---|
| Texte | `Parmi les {{NB_ESPECE_TOTAL}} espèces…` | peut se trouver au milieu d'une phrase, dans un tableau, une zone de texte (page de garde), un en-tête ou un pied de page |
| Tableau | `{{TABLE_DORTOIRS}}` | **seul dans son paragraphe**, dans le corps du document (pas dans une cellule ni une zone de texte) ; le tableau est inséré juste après |
| Image (graphique, carte) | `{{Carte1_zone_localisation}}` ou `{{chart_evolution.png}}` | **seul dans son paragraphe** ; le nom est celui du fichier PNG, sans extension, ou de la mise en page QGIS |

### Règles pour les modèles

- **Mise en forme** : la valeur reprend la mise en forme du **premier caractère** du placeholder (police, couleur, gras). Taper le placeholder dans le Word, dans le style du texte voulu.
- **Copier-coller** : ne jamais coller un placeholder depuis un chat ou un navigateur, car la mise en forme collée (Consolas, fond gris) se retrouve dans le rapport. Utiliser « Coller en texte seul ».
- **Images** : leur taille dépend du réglage `map_layout` du dossier.
  - `normal` : largeur de 6 pouces dans le paragraphe.
  - `A4` / `A3` : pleine page, avec ajout d'un nouveau paragraphe et d'un saut de page.
  - `page` : dans le paragraphe du placeholder, réduite pour tenir sur la page. C'est le bon choix quand le template prévoit déjà une page par carte.
- **Texte à compléter** : les parties que le générateur ne remplit pas (commanditaire, analyses) restent du texte normal, surligné en jaune.
- **Sections conditionnelles** : `{{#nom}}` … `{{/nom}}`, chaque balise seule dans son paragraphe du corps du document. Si la brique `nom` a été exécutée, seules les balises sont retirées ; sinon, toute la section disparaît. Exemple : la partie chiroptères du rapport éolien.
- **Ajouter une partie à un template** : le plus sûr est de copier des paragraphes existants (titres, corps, légendes, pages de carte) pour garder la mise en page. Deux pièges :
  - un titre copié emporte son signet de sommaire : il faut retirer les signets en double, sinon Word signale un fichier endommagé ;
  - dans le template éolien, la numérotation des sous-titres (x.1, x.2) est portée par des paragraphes de liste **cachés**, placés avant le premier sous-titre de chaque chapitre : il en faut un de plus par chapitre ajouté.
- **Contrôle** : vérifier le rendu en ouvrant le rapport dans **Word**. LibreOffice est plus tolérant et peut afficher un fichier que Word refuse.
- **Vérification** : `reportgenerator check --dossier <type>` liste les placeholders sans source, les sorties non utilisées, et signale un template sans aucun placeholder.

---

## 5. Projets QGIS

- **Une carte = une mise en page.** Pour chaque mise en page, le rendu n'affiche que le groupe de couches **du même nom**, plus les groupes indiqués dans `visible_groups`. L'image est enregistrée sous `maps/<mise en page>.png` et remplace le placeholder `{{<mise en page>}}`.
- **Toutes les mises en page sont exportées** : il n'y a pas de liste à maintenir.
- **Couches** : leurs sources doivent être des GeoPackage nommés `<couche>.gpkg|layername=<couche>`. Au rendu, elles sont redirigées vers `outputs/<zone>/data/<couche>.gpkg`, en conservant les filtres (`subset`). Une couche absente de `data/` devient invalide, et sa carte sort vide.
- **Réglages du rendu**, dans le bloc `[params.qgis_render]` du `dossier.toml` :
  - `visible_groups` : groupes toujours affichés ;
  - `extent_layer` : couche qui fixe l'emprise ;
  - `extent_margin_ratio` : marge autour de l'emprise ;
  - `extent_offset_y_ratio` : décalage vertical ;
  - `layout_buffers_m` : élargissement de l'emprise par mise en page ;
  - `dpi`.
- **Pièces jointes** : le fichier `<projet>_attachments.zip`, placé à côté du `.qgs`, est copié avec lui.
- **Projet de la zone** : le projet est copié dans le dossier de sortie, sous le nom `projet_<zone>.qgs`. Il peut ensuite être ouvert pour retoucher une carte à la main.

---

## 6. Ajouter un type de rapport ou une analyse

### Process avec les collègues

1. **Le besoin** : le collègue transmet, via le formulaire de besoin :
   - un rapport type (Word) ;
   - la méthode de chaque élément : données, filtres, calculs, rendu attendu.
2. **La fiche** : décrire chaque élément du rapport dans `dossiers/<type>/METHODO.md` (process, contenu, règles), en s'inspirant de la fiche éolien. Lister les questions ouvertes et les trancher avec le collègue **avant** de coder.
3. **Le dossier** : créer `dossiers/<type>/dossier.toml` avec un déclencheur, `declencheurs = ["analyse_xxx"]`, et ajouter `analyse_xxx` à la liste du formulaire QGIS.
4. **Les briques** : réutiliser les briques existantes (`socle_data`, `cartography`, `zonages`…), et écrire les nouvelles (section suivante).
5. **Le template** : déposer le Word en `template.docx` et y placer les placeholders (section 4).
6. **Les cartes** : déposer le projet QGIS dans `dossiers/<type>/qgis/` (section 5).
7. **Les vérifications** :
   - `check --dossier <type>` jusqu'à obtenir « Dossier prêt » ;
   - `pytest` ;
   - un rendu avec de fausses données (voir `tests/test_eolien.py`) ;
   - une génération réelle sur une zone de test, à comparer avec un rapport fait à la main.

### Écrire une brique

```python
# bricks/<fichier>.py
@register_brick("dortoirs", requires=["socle_data"], provides=["TABLE_DORTOIRS"])
def dortoirs(ctx):
    """Dortoirs des rapaces et grands voiliers."""
    rows = ...  # requête sur la VM (ctx.queries / analysis/<module>/queries.py)
    return AnalysisResult(tables={"TABLE_DORTOIRS": TableBlock(rows, insert_ring_table, {...})})
```

- `texts` / `tables` / `images` : clé = nom du placeholder. Deux briques ne peuvent pas fournir la même clé.
- `requires` : briques à exécuter avant, ajoutées automatiquement au plan.
- `last=True` : brique exécutée après toutes les autres. C'est le cas de `cartography`, qui a besoin des couches produites par les autres briques.
- **Regrouper une option** : une brique vide qui `requires` les briques d'une partie (ex. `chiropteres`) sert d'interrupteur. On la met dans `optional`, un déclencheur l'active (`[declencheurs] analyse_x = ["chiropteres"]`), et elle délimite la section `{{#chiropteres}}` du template.
- `provides` : clés fournies, utilisées seulement par `check`. Pour `cartography`, elles sont lues dans le projet QGIS.
- `ctx.params` : paramètres du `dossier.toml`. `ctx.cached(clé, fonction)` évite de relancer une même requête dans plusieurs briques.
- Pour qu'elle soit chargée, une nouvelle brique doit être importée dans `bricks/__init__.py`.
- Garder le SQL dans `analysis/<module>/` et la mise en forme pure (calculs, textes) dans des fonctions testables sans base.

---

## 7. Dépannage

| Symptôme | Cause et solution |
|---|---|
| `Command '['C:\\Program Files (x86)\\wapt\\python.EXE', '-Ic', …]' returned non-zero exit status 2` | Poetry trouve le Python de wapt dans le `PATH`. Lancer `poetry config virtualenvs.use-poetry-python true`. |
| `check` : « Aucun placeholder {{...}} dans le template » | Le Word contient encore les anciennes variables : les convertir en `{{NOM}}`. |
| `[AVERTISSEMENT] Placeholder sans valeur : {{X}}` | Aucune brique ne fournit X, ou une image n'a pas été produite. Le placeholder reste visible dans le Word. |
| Cartes vides (fond de carte seul), `Couche invalide pour l'emprise` | Les couches du projet QGIS ne correspondent à aucun `data/<couche>.gpkg`. Vérifier les noms `layername`. |
| QGIS s'arrête avec le code `3221226505` (0xC0000409) | Plantage de QGIS lui-même. Relancer le rendu seul pour lire sa sortie (commande affichée dans l'erreur) ; vérifier d'abord la validité des couches. |
| `cannot dump lists of mixed types` | Une liste Python mêlant entiers et décimaux a été envoyée en paramètre SQL. Convertir les valeurs (ex. `float(x)`). |
| Texte d'un placeholder en Consolas, sur fond gris | Mise en forme collée dans le template : retaper le placeholder (section 4). |
| Une brique échoue | Le journal affiche « ✗ Brique … ÉCHEC ». La demande reste en attente, et la VM est supprimée. |
| Word : « le fichier semble endommagé » | Identifiants en double dans le XML. Les dessins sont corrigés automatiquement au rendu (`dedupe_drawing_ids`). Pour un template, valider avec le script `validate.py` de la compétence docx : il signale notamment les signets en double. |
| Un paramètre du `dossier.toml` est ignoré, ou lu comme une espèce | Il est placé **après** une sous-table `[params.xxx]` : en TOML, tout ce qui suit une sous-table lui appartient. Les sous-tables doivent rester en fin de fichier. |

---

## 8. Points de vigilance et dette technique

À traiter en priorité :
- **Atlas** : les années de 2009 à 2026 sont codées en dur dans `get_atlas_species_grid`. Les données de 2027 seront ignorées.
- **Docker** : `Dockerfile` définit `OUTPUT_DIR=/app/output`, mais `compose.yml` monte le volume sur `/output`. Les rapports risquent de ne pas être conservés hors du conteneur.
- **Données sensibles dans git** : `templates/data/*.gpkg` (dont `donnees_brutes.gpkg`) et `symbology-style.db` sont versionnés. Vérifier qu'ils ne contiennent pas de vraies données.

À traiter ensuite :
- **CI** : le workflow ne tourne que sur `main` et n'installe pas le projet. Les tests `pytest` existent désormais : les activer.
- **Rapport générique** : `{{DATE_REPORT}}` annonce 10 ans, alors que les données ne sont pas filtrées (voir sa fiche).
- **Requêtes** : statut d'observation codé en dur (`id_nomenclature_observation_status = 89`) ; SQL construit par f-string (les valeurs sont converties, mais des requêtes paramétrées seraient plus sûres).
- **Couleurs de liste rouge** : elles sont définies à plusieurs endroits, avec des valeurs différentes (`styles.py`, `utils.py`, `excel_export.py`, SQL).
- **Tableaux** : les placeholders de tableaux ne sont cherchés que dans les paragraphes du corps du document.

Corrigé lors de l'ajout des chiroptères :
- sous-espèces dont le `cd_sup` est vide (leurs données tombaient sur un `cd_ref` nul) ;
- identifiants de dessin en double avec le pied de page (Word refusait d'ouvrir le rapport) ;
- `w:shd` sans attribut `w:val` dans les cellules colorées (non conforme au schéma).

Corrigé après l'audit des données (VM commune à tous les dossiers, détails dans la fiche éolien, section 2) :
- maille calculée spatialement : `cor_area_synthese` est incomplet pour les données récentes, qui étaient exclues ;
- dédoublonnage entre sources (paramètre `sources_prioritaires`) ;
- une seule ligne de statuts par taxon (`mv_c_statut` contient des doublons) ;
- nouveaux champs de la VM : `source`, `comportement` (comportement VisioNature), `precision_geo` (point / lieu-dit), `donnee_cachee` ;
- VM au nom unique par génération : avec le nom fixe, une génération lancée en parallèle supprimait et recréait la vue d'une autre (erreur « column s.donnee_cachee does not exist », ou pire, requêtes silencieuses sur la zone de l'autre génération).

Déjà corrigé lors de la mise en place du multi-dossiers :
- sous-espèces (`SESS` → `SSES`) ;
- rayon des zonages (`× 10 km`) ;
- couche vide qui faisait échouer le rapport ;
- `--output_dir` ignoré ;
- nom de zone non contrôlé avant de vider le dossier ;
- filtres QGIS perdus au re-lien ;
- pièces jointes QGIS non copiées ;
- VM non supprimée en cas d'échec.

---

## 9. Bonnes pratiques

À faire :
- garder chaque fichier simple, et séparer SQL, calculs, mise en forme et rapport ;
- écrire une règle métier **une seule fois** (sélections, `dossier.toml`) et la documenter dans la fiche du dossier ;
- utiliser des chemins basés sur `Path(__file__)` ;
- couvrir chaque calcul par un test sans base ;
- après toute modification d'un template, lancer `check`.

À éviter :
- coder une liste de cartes ou de colonnes en dur, alors qu'elle peut se déduire du projet QGIS ou du template ;
- ajouter des colonnes à la vue des demandes : passer par `list_analyse` et le `dossier.toml` ;
- mélanger le code QGIS (interpréteur QGIS) et le code Poetry ;
- générer un rapport de test sur une vraie demande (elle serait clôturée).
