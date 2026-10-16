# Demande de modification d'un dossier existant

> Copier ce modèle, remplir ce qui est connu, laisser « ? » sinon : je poserai les questions.
> Une demande = un ou plusieurs points numérotés. Pour plusieurs points, répéter la partie « Point n ».

**Dossier** : eolien / generique / …
**Demandé par** : (collègue, pour savoir à qui renvoyer les questions métier)
**Urgence** : bloquant pour un rapport en cours ? date ?

---

## Point 1 : <titre court>

**Type** (cocher) :
- [ ] texte du Word (formulation, paragraphe fixe)
- [ ] chiffre ou texte calculé (`{{...}}`)
- [ ] tableau (colonnes, tri, sélection d'espèces)
- [ ] carte (nouvelle carte, filtre, couche, style)
- [ ] règle métier (sélection, seuil, calcul, période, statuts…)
- [ ] paramètre (`dossier.toml`)
- [ ] bug / résultat qui semble faux

**Où dans le rapport** : § / titre de la section, placeholder si connu (ex. `{{TABLE_DORTOIRS}}`, Carte 12).

**Aujourd'hui** : ce que le rapport produit (copier la phrase, joindre une capture ou le Word généré).

**Attendu** : ce qu'il devrait produire. Le plus utile : **un exemple concret**
(« sur TEST EOLIEN, le Milan royal devrait apparaître avec 12 données », ou la phrase finale exacte avec les
valeurs à remplir entre `{{ }}`).

**Règle** (si règle métier, tableau ou carte) :
| Question | Réponse |
|---|---|
| Quelles données ? (groupe, espèces, période, statuts de validation, rangs) | |
| Quel filtre ? (nidification, comportement, liste rouge, sensibilité…) | |
| Quel calcul ? (comptage de données / d'observations / d'espèces, max, seuils) | |
| Par zone ? (anneaux, maille, toute la zone) | |
| Cas limites ? (aucune donnée, espèce sans statut, données au lieu-dit, cachées) | |

**Pour une carte** : nom de la mise en page, couche(s), filtre, symbologie, emprise.
Préciser qui fait la mise en page QGIS (toi / moi : je fournis alors la couche et un filtre suggéré).

**Ce qui ne doit PAS changer** : (ex. « ne pas toucher au rapport générique », « garder les noms de champs du projet
QGIS »).

**Comment valider** : zone de test (id_area), valeur attendue, ou rapport de référence à comparer.

**Pièces jointes** : chemin local des fichiers (Word annoté, capture, extrait de méthode). Les garder hors du dépôt.

---

## Déjà décidé / contexte utile
(décisions prises avec le collègue, contraintes, choses déjà essayées)

## Ce que je fais de mon côté
1. Je relis le `METHODO.md` du dossier et le code concerné, puis je reformule et je liste les questions ou les
   effets de bord (autres sections, autre dossier, cartes).
2. Après validation : modification, tests, contrôle sur la vraie base (lecture seule), rendu Word, mise à jour du
   `METHODO.md` et du texte du template.
3. Je signale ce que tu dois faire toi-même (QGIS, commit, déploiement serveur).
