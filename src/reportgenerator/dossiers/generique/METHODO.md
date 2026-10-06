# Rapport générique : process et contenu

**Rapport produit** : état des connaissances naturalistes d'une zone d'étude et de ses alentours.

**Déclenchement** : rapport par défaut. Il est produit pour toute valeur de `list_analyse` qui ne déclenche pas un autre dossier. La valeur `atlas_nicheur` ajoute l'atlas des nicheurs.

**Fichiers du dossier** :
- `dossier.toml` ;
- `template.docx` ;
- le projet QGIS `templates/projet_modele.qgs`, partagé avec `templates/data/`.

---

## 1. Process de génération

```text
socle_data          VM lpoaura_afo.vm_reportgenerator_data_<date>_<code> (une par génération) : zone d'étude + buffer du formulaire
knowledge_status    graphiques (évolution, groupes taxonomiques, taux de connaissance, disparitions)
synthese_generale   chiffres clés, tableaux taxons / espèces, export Excel
zonages             zonages environnementaux (textes + tableau des surfaces)
cartography         6 cartes QGIS (projet_modele.qgs)
atlas_nicheur       (option) une planche PNG par espèce dans atlas/, non insérée dans le Word
→ template.docx rempli → outputs/<zone>/<zone>.docx
```

## 2. Données prises en compte

| Critère | Valeur |
|---|---|
| Emprise | zone d'étude + **buffer** du formulaire (km) |
| Période | **toutes les années**. Le texte « {{DATE_REPORT}} » affiche pourtant les 10 dernières années (voir la section 4) |
| Validation | statuts 0 (en attente), 1 et 2 |
| Taxons | Amphibiens, Chauves-souris, Mammifères, Odonates, Oiseaux, Papillons de jour, Poissons, Reptiles |
| Géométries | points uniquement |
| Grille | choisie automatiquement selon la surface (de 200 m à 5 km), maille **calculée spatialement** |
| Doublons entre sources | même taxon, même jour, même cellule de 100 m : seule la source la mieux classée de `sources_prioritaires` est gardée |

Ces deux derniers points corrigent des défauts relevés par l'audit du dossier éolien (détails dans `dossiers/eolien/METHODO.md`, section 2) :
- `cor_area_synthese` ne relie pas les données récentes à leur maille : elles étaient **exclues de la VM** (7 % des données d'oiseaux sur la zone de test) ;
- des données faune-france sont aussi importées par un partenaire (gn2pg_cen_auv) et étaient comptées deux fois.

Les chiffres d'un rapport générique produit après cette correction peuvent donc différer de ceux d'un rapport plus ancien sur la même zone.

## 3. Contenu du rapport

| Placeholder | Contenu |
|---|---|
| `{{AREA_NAME}}`, `{{REFEREE}}`, `{{BUFFER}}` | champs du formulaire |
| `{{DATE_REPORT}}` | « (année − 10 - année) » |
| `{{NB_OBS_ZONE}}`, `{{NB_SPECIES_ZONE}}`, `{{LAST_OBS_ZONE}}` | observations, espèces et dernière observation dans la zone d'étude |
| `{{…_BUFFER}}` | idem, dans le buffer seul (hors zone d'étude) |
| `{{…_GLOBAL}}` | idem, sur l'ensemble zone + buffer |
| `{{TABLE_TAXO}}` | par groupe taxonomique : nombre de données, d'espèces, d'espèces nicheuses, protégées et en danger |
| `{{TABLE_ESP}}` | toutes les espèces : statuts, nombre d'années, nombre de données, dernière observation (copie dans `tables/tableau_especes.xlsx`) |
| `{{TABLE_ESP_LR}}` | les espèces CR, EN, VU ou NT sur `lr_aura` ou sur une liste rouge France (nicheur, hivernant, migrateur) |
| `{{TEXTE_CONNAISSANCE}}` | texte fixe sur l'interprétation du taux de connaissance |
| `{{chart_evolution.png}}` | nombre de données et d'espèces par an, depuis 2000 |
| `{{chart_species_by_group.png}}`, `{{chart_data_by_group.png}}` | espèces et données par groupe taxonomique |
| `{{chart_knowledge_rate.png}}` | espèces observées / pool régional de référence (`src_gestion.vm_reportgenerator_refere_taxo`) |
| `{{chart_disparition.png}}` | espèces vues au moins 2 années, non revues depuis 5 ans (« en régression ») ou 10 ans (« disparue ») |
| `{{TABLE_ZONAGES}}` | surface de chaque type de zonage dans la zone d'étude, le buffer et les 10 km au-delà |
| `{{ZONAGE_PRESENTATION}}` | présentation des zonages présents dans la zone d'étude ou le buffer |
| `{{observations_brutes.png}}`, `{{mortalite.png}}`, `{{statut_connaissance.png}}`, `{{absence_connaissance.png}}`, `{{statut_protection.png}}`, `{{zones_protegees.png}}` | cartes QGIS (une mise en page = un groupe de couches = une image) |

Ces sorties sont disponibles mais pas utilisées dans le template : `{{NB_DATA}}`, `{{ZONAGE_TEXTE}}`, `{{chart_species_vs_pool.png}}`.

## 4. Points de vigilance

- `{{DATE_REPORT}}` annonce les 10 dernières années, alors que la VM ne filtre pas les dates. Le paramètre `annees` du `dossier.toml` permet de filtrer, comme pour l'éolien.
- Sans aucune espèce en régression, `chart_disparition` n'est pas produit et son placeholder reste visible dans le Word. Il est signalé dans le journal.
- L'atlas nicheur est produit dans `atlas/` mais n'est pas inséré dans le Word.
- Les années de l'atlas sont codées en dur, de 2009 à 2026 (`get_atlas_species_grid`). **Il faudra les mettre à jour avant janvier 2027.**
