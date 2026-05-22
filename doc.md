# Documentation du générateur de rapports

## 1. Objectif du projet

Ce projet automatise la production de rapports à partir de données PostgreSQL/PostGIS.
Il n'est pas là pour remplacer l'expertise métier, mais simplement facilité la préparation de documents pour permettre de donner un avis plus facilement aux experts locals.

Il permet de :

* récupérer des données via SQL,
* produire des analyses métier,
* générer des tableaux Excel,
* générer des dataviz,
* exporter des données spatiales en GeoPackage,
* produire des cartes via QGIS,
* assembler le tout dans un rapport Word à partir d’un modèle.

L’objectif principal est de garder une architecture modulaire pour pouvoir ajouter de nouvelles analyses progressivement, sans refactor global.

---

## 2. Architecture générale

L’architecture suit une séparation stricte des responsabilités :

* **`queries`** : accès aux données SQL
* **`analysis`** : logique métier et orchestration d’un module d’analyse
* **`report`** : assemblage final du document Word
* **`templates`** : modèles Word et QGIS

### Chaîne de traitement

```text
CLI
  ↓
Queries SQL
  ↓
Analyse métier
  ↓
Exports (tables, images, gpkg)
  ↓
Cartographie QGIS
  ↓
Rapport Word
```

---

## 3. Rôle des fichiers principaux

### `cli.py`

Point d’entrée du projet.

* lit les arguments de ligne de commande,
* crée les dossiers de sortie,
* ouvre la connexion à la base,
* lance les analyses,
* lance la cartographie,
* appelle la génération du rapport final.

### `db_auth.py`

Contient la connexion à la base PostgreSQL/PostGIS.

### `queries.py`

Contient les requêtes SQL et les classes d’accès aux données.

### `analysis/<module>/analysis.py`

Orchestre une analyse spécifique.

Exemples :

* `knowledge_status/analysis.py`
* `cartography/analysis.py`

Ce fichier appelle les requêtes, les exports et prépare les éléments à insérer dans le rapport.

### `analysis/cartography/qgis_launcher.py`

Lance un script QGIS dans un environnement séparé.

### `analysis/cartography/qgis_render.py`

Script exécuté avec l’environnement QGIS. Il charge le projet QGIS et exporte les cartes.

### `report.py`

Charge le modèle Word, remplace les variables, insère les tableaux et images, puis enregistre le document final.

---

## 4. Organisation des sorties

Chaque exécution crée un dossier dédié à la zone étudiée.

Exemple :

```text
outputs/
└── MONPROJETTEST/
    ├── report.docx
    ├── projet.qgs
    ├── data/
    ├── dataviz/
    │   ├── chart_evolution.png
    │   └── ...
    └── maps/
        ├── carte_observations.png
        └── carte_mortalite.png
```

### Convention de nommage

* `data/` : géopackages et données intermédiaires
* `dataviz/` : graphiques et figures
* `maps/` : cartes exportées par QGIS
* `report.docx` : rapport final
* `projet.qgs` : copie du projet QGIS modèle

---


## 5. Principe de fonctionnement des templates Word

Le modèle Word contient des placeholders, par exemple :

```text
{{AREA_NAME}}
{{REFEREE}}
{{NB_DATA}}
{{chart_evolution.png}}
{{carte_observations.png}}
```

Le script de génération remplace les variables textuelles puis insère les images à partir des noms de fichiers ou des placeholders définis.

### Règle importante

Pour les placeholders :

* écrire le texte en un seul bloc dans Word,
* éviter de changer la mise en forme au milieu du placeholder.

---

## 6. Principe de fonctionnement du template QGIS

Le projet QGIS modèle sert de base à la cartographie.

Il contient :

* les couches,
* les styles,
* les groupes de couches,
* les mises en page,
* les exports cartographiques.

Le projet est copié dans le dossier de sortie avant exécution.
le script qgis_render.py, permet de lancer la génération de cartographie pour toutes les groupes de couches présents. 
Il coche un groupe de couche et décoche les autres et lance la mise en page de carte qui porte le même nom que la couche pour permettre la génération de la carte avec les bonne données.

---

## 7. Exemple de module d’analyse : `knowledge_status`

Cette analyse produit par exemple :

* un texte explicatif générique, (à venir)
* un texte basé sur les données, (à venir)
* un tableau des chiffres clés, 
* une figure temporelle,
* éventuellement d’autres exports. 

### Fichiers typiques

* `analysis.py` : orchestration du module
* `dataviz.py` : création des graphiques
* `export.py` : exports éventuels
* `report_context.py` : préparation des variables à injecter dans le rapport



## 8. Ajouter une nouvelle analyse : méthode recommandée (à faire)



## 9. Bonnes pratiques à respecter

### À faire

* garder chaque fichier simple,
* garder un nommage en anglais
* séparer SQL / analyse / export / rapport,
* utiliser des chemins basés sur `Path(__file__)`,
* retourner des objets ou dictionnaires clairs,
* tester chaque étape indépendamment.

### À éviter

* mélanger QGIS dans le code Poetry,
* mettre trop de logique dans `cli.py`,
* faire des fonctions avec trop d’arguments,
* utiliser des chemins relatifs fragiles,
* écrire des modules trop génériques trop tôt.

---

## 10. Prochaine évolution possible

Les prochaines évolution de code possibles sont :

* génération d'un atlas à partir du QGIS
* ajout d’un système de logs plus détaillé,
* analyses des temps de calcules des étapes/analyses

Les prochaines évolution d'analyses possibles sont :

* Analyses des nicheurs 
* Analyses des migrations
* Analyses de la mortalité
* 

---

## 11. Note de travail

Cette documentation est pensée pour servir de base évolutive. Elle peut être enrichie au fur et à mesure des nouvelles analyses et des nouveaux exports ajoutés au projet.
