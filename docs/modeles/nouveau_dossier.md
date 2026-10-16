# Nouveau type de rapport

> Deux cas : un ancien workflow existe (scripts, requêtes) → parties 2 et suivantes ; il n'existe que des rapports
> finaux → compléter aussi la partie 2 bis.
> Remplir ce qui est connu, mettre « ? » ailleurs. Le plus important : **les fichiers sources (partie 2)** et
> **un rapport de référence avec sa zone (partie 9)**. Le reste, je peux le déduire puis te le faire valider.

## 1. Identité

| | |
|---|---|
| Nom court du dossier (minuscules, sans espace) | ex. `carriere` |
| Titre du rapport | |
| Valeur `list_analyse` qui le déclenche | ex. `analyse_carriere` |
| Analyses optionnelles (cases à cocher du formulaire) | ex. `chiropteres`, `atlas_nicheur`… ou aucune |
| Référent métier (qui valide la méthode) | |
| Destinataire du rapport | interne / client / public → impose le floutage des données sensibles |
| Volume attendu | quelques rapports par an / par mois |

## 2. Fichiers fournis

Déposer dans un dossier **hors du dépôt** et donner son chemin : `C:\...\<nom>_sources\`

- [ ] **Scripts** (R, Python, SQL) + **ordre d'exécution** (ou le script principal qui appelle les autres)
- [ ] **Requêtes SQL** / VM secondaires créées par le workflow
- [ ] **Rapport Word vierge** (le modèle) et **un rapport rempli** (résultat réel)
- [ ] **Projet QGIS** (+ `_attachments.zip`, styles, données de démo si besoin)
- [ ] **Méthodologie** (document du collègue, notes, PDF)
- [ ] **Tables de référence** : fichiers (CSV/Excel) ou tables en base (`schéma.table`, droits de lecture du service ?)
- [ ] Script de rendu des cartes (ex. `lancement_carte_qgis.py`)
- [ ] Ce qui était fait **à la main** après les scripts (copier-coller Excel, retouches de cartes, textes)

### 2 bis. Sans ancien workflow (seulement des rapports finaux)

Je reconstitue alors les règles **à partir du résultat** : pour chaque chiffre, tableau ou carte, je fais une hypothèse
(données, filtre, calcul), je la rejoue sur la base pour la même zone et je compare jusqu'à retrouver le résultat.
Pour que ce soit possible :

- [ ] **2 ou 3 rapports finaux sur des zones différentes** (un seul ne permet pas de distinguer le texte fixe du
      texte qui varie, ni de vérifier une règle)
- [ ] pour chacun : **la zone exacte** (id_area si saisie, sinon la géométrie : shapefile, GPKG, ou projet QGIS)
      et **la date de production** du rapport. Les données ajoutées depuis expliquent des écarts : je compare en
      filtrant à cette date
- [ ] **ce qui a servi à le produire**, même partiel : export de données (CSV/Excel), tableaux Excel intermédiaires,
      projet QGIS ou au moins les cartes en image, requêtes ou filtres faits dans QGIS
- [ ] **un Word annoté** (commentaires ou surlignage), même rapidement :
      - 🤖 « à automatiser » / ✍️ « rédigé à la main » / 🧠 « choix d'expert » (ex. espèces ajoutées « à dire d'expert ») ;
      - pour chaque chiffre ou tableau, d'où il vient si quelqu'un s'en souvient (« export Faune-France, nicheurs
        seulement », « liste rouge régionale »…)
- [ ] **la personne qui a fait le rapport**, joignable pour les questions (une courte liste de questions groupées,
      pas un aller-retour permanent)
- [ ] ce qui **peut changer** par rapport au rapport d'origine (c'est l'occasion de corriger ou simplifier)

Ce que je livre en plus dans ce cas : un **tableau de rétro-ingénierie** dans le `METHODO.md` (élément → règle
retrouvée → écart avec le rapport d'origine → explication), et la liste des éléments qui restent manuels.

## 3. Données

| Critère | Valeur | Comme l'éolien ? |
|---|---|---|
| Groupes taxonomiques | | |
| Période (N dernières années / toutes) | | |
| Statuts de validation | | 0, 1, 2 |
| Emprise : buffer du formulaire, ou anneaux fixes (km) ? | | |
| Grille (M1, M5, auto) | | |
| Rangs gardés (espèces seules, genres…) | | |
| Dédoublonnage entre sources | | faune-france, dbChiroGCRA |
| Données cachées / sensibles : précises, floutées, exclues ? | | |
| Autres sources (tables partenaires, hors synthèse) | | |

## 4. Contenu du rapport, section par section

Un tableau suffit, même partiel. Je le complète à partir du Word et des scripts.

| § / section | Élément (texte, chiffre, tableau, carte, graphique) | Auto ou à rédiger | Règle / source (script, requête) |
|---|---|---|---|
| | | | |

## 5. Tableaux

Pour chaque tableau : colonnes, sélection des lignes, tri, découpage par zone, copie Excel nécessaire ?

## 6. Cartes

| Nom de la carte | Couches | Filtre | Emprise / échelle | Existe dans le projet QGIS ? |
|---|---|---|---|---|
| | | | | |

Qui fait les mises en page QGIS : toi / moi (je fournis alors les couches et des filtres suggérés).

## 7. Reprise de l'ancien workflow

- Ce qui doit être **repris à l'identique** (noms de couches/champs du projet QGIS, formulations validées…) :
- Ce qui peut être **abandonné** :
- **Bugs ou doutes connus** dans les scripts :
- Ce qui a changé depuis (tables renommées, listes rouges, nouvelles sources) :

## 8. Décisions déjà prises
(ce qui a été tranché avec le collègue : seuils, listes d'espèces, textes…)

## 9. Validation

| | |
|---|---|
| Zone de test (nom + id_area si déjà saisie) | |
| Rapport de référence fait avec l'ancien workflow sur cette zone | chemin |
| Critère d'acceptation | ex. « mêmes espèces à enjeux, écarts de chiffres expliqués » |

---

## Ce que je fais ensuite (étapes avec validation de ta part)

1. **Analyse** des scripts, du Word et du projet QGIS : inventaire de chaque élément du rapport, de sa source et de
   sa règle ; liste des incohérences, des bugs et des questions. → **tu tranches**.
2. **Fiche `METHODO.md`** du dossier (process, données, contenu section par section, points ouverts). → **tu valides**
   (éventuellement avec le collègue).
3. **Code** : `dossier.toml`, briques (réutilisation de `socle_data`, `cartography`, `zonages`…), requêtes, tests sans
   base.
4. **Template** : conversion du Word en placeholders, couches QGIS sous les noms attendus par le projet.
5. **Contrôles** : requêtes vérifiées sur la vraie base (lecture seule), essai sur la zone de test comparé au rapport
   de référence, audit de qualité des données, rendu Word ouvert dans Word, `check`.
6. **Livraison** : récapitulatif des écarts avec l'ancien workflow, de ce qu'il te reste à faire (QGIS, formulaire,
   commit, déploiement serveur) et des points ouverts.
