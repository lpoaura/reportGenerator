# Rapport Indicateurs : partie « Bénévoles » (design court)

Statut : validé le 18/11/2026.

## Intention

Montrer aux coordinateurs et aux financeurs (DREAL, Région) la place du bénévolat dans chaque protocole : combien de
bénévoles, quel travail, quel renouvellement. Le rapport est transmis : **uniquement des chiffres agrégés**, aucun nom,
aucun email, aucune liste nominative (le suivi nominatif des bénévoles relève d'un autre outil).

Un futur rapport « participants » (bénévoles, organismes tiers, salariés) pourra réutiliser les calculs et graphiques :
ils sont donc **paramétrés par catégorie d'observateurs** (approche B retenue), ce rapport les appelant avec
« Bénévole ».

## Approches envisagées

- A. Calculs dédiés aux bénévoles : le plus court, mais à réécrire pour le futur rapport participants.
- **B. Calculs paramétrés par catégorie (retenue)** : même rendu, réutilisables pour les organismes tiers et salariés.
- C. Analyse activable dans `list_analyse` : écartée, rien à masquer puisque la partie ne contient que des agrégats.

## Définitions (règles métier)

- **Bénévole** : compte de catégorie « Bénévole » (règle commune du rapport : aucun organisme). Les observateurs
  « Non renseigné » (sans compte GeoNature) sont affichés à part, jamais comptés comme bénévoles.
- **Statut d'un bénévole en N** (par protocole, d'après les saisons où il a fait au moins un relevé) :
  nouveau (première saison = N), fidèle (présent en N et N-1), revenant (présent en N, absent en N-1, présent avant),
  parti (présent en N-1, absent en N).
- **Département d'un bénévole** : départements des aires où il a fait un relevé dans la saison (un bénévole peut
  compter dans plusieurs départements ; le total régional n'est pas la somme).
- **Ancienneté** : nombre de saisons distinctes de participation au protocole jusqu'à N, en tranches 1, 2-4, 5-9,
  10 et plus.
- **Engagement** : nombre d'aires suivies dans la saison par bénévole : 1, 2, 3 et plus.
- **Travail réalisé** : aires (catégorie de l'aire), relevés et données (catégorie du relevé), heures (mêmes règles
  que la répartition par catégorie) ; part du protocole = aires des bénévoles / aires suivies.
- **Valorisation** : heures × `taux_horaire_benevolat` (`dossier.toml`, 0 par défaut = non affichée).
- **Aires créées jamais visitées** (modules GeoNature : STOM, STERF, POP) : aires de la zone sans aucune visite depuis
  leur création, par catégorie du créateur du site (`id_inventor`) et année de création. Proxy des engagements non
  concrétisés : les comptes inscrits sans saisie ne sont pas mesurables (droits des modules dans `gn_permissions`,
  inaccessible ; inscriptions STOC/SHOC chez Vigie-Nature).
- **Multi-protocoles** : comptes GeoNature bénévoles actifs dans au moins deux protocoles à leur saison N
  (correspondance par compte, comme l'indicateur existant).

## Contenu

**Dans chaque protocole, nouvelle sous-partie « Bénévoles »** (après « Espèces », avant les analyses propres) :

1. Texte et tuiles : bénévoles en N et écart à N-1, part des observateurs, part des aires, données, heures
   (et valorisation si le taux est renseigné).
2. Graphique du renouvellement par saison depuis le début du suivi des observateurs : nouveaux, fidèles, revenants
   (barres empilées au-dessus de l'axe), partis (sous l'axe).
3. Graphique par département (si plusieurs) : bénévoles nouveaux / fidèles / revenants, partis.
4. Graphique ancienneté (tranches) et engagement (aires par bénévole).
5. Modules GeoNature : nombre d'aires créées jamais visitées (texte, détail par catégorie du créateur en annexe).
6. Tableaux de chaque graphique en annexe paysage (comme le reste du rapport).

**Nouvelle partie « Le réseau bénévole »** (avant la conclusion, tous protocoles du rapport) :

1. Bénévoles distincts tous protocoles, écart à N-1, heures cumulées (et valorisation).
2. Évolution des bénévoles distincts par année.
3. Bénévoles sur 2 protocoles ou plus et combinaisons les plus fréquentes (STOC + SHOC…) en barres.
4. Bénévoles distincts par département.

Couleurs : statuts en palette catégorielle validée (ordre fixe) ; bénévoles en vert d'eau comme dans le reste du
rapport ; mêmes règles de lisibilité (tuiles, texte jamais en couleur de série).

## Contraintes

- Lecture seule ; une seule requête nouvelle (aires jamais visitées et créateur), vérifiée par `EXPLAIN`.
- Aucun nom ni email dans le Word, les tableaux d'annexe ni les couches QGIS.
- Règle métier écrite une fois (fonctions pures testées sans base), reportée dans le `METHODO.md` et le template.
- Validation habituelle : tests, lint, `check`, dry-run régional 2026, ouverture dans Word.

## Laissé au constructeur

Disposition exacte des graphiques, libellés, seuils d'affichage (ex. masquer le graphique par département pour une
zone d'un seul département, comme la couverture).
