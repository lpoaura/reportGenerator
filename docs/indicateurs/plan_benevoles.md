# Partie « Bénévoles » du rapport Indicateurs : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** une sous-partie « Bénévoles » dans chaque protocole et une partie « Le réseau bénévole » avant la conclusion,
chiffres agrégés seulement.

**Architecture:** calculs purs paramétrés par catégorie dans `analysis/indicateurs/participants.py` (réutilisables
pour un futur rapport participants), graphiques dans `figures.py`, une requête en lecture seule (créateurs des aires des
modules), câblage dans `bricks/indicateurs.py`, template par `outils/word/template_indicateurs.py`.

**Tech Stack:** Python 3.14, pandas, matplotlib, psycopg (lecture seule), python-docx, pytest.

**Spec:** `docs/indicateurs/benevoles.md` (validé le 18/11/2026).

## Global Constraints

- Aucun nom, aucun email dans le Word, les annexes ou les couches : comptes agrégés uniquement.
- « Bénévole » = catégorie « Bénévole » de la règle commune ; « Non renseigné » jamais compté comme bénévole.
- Correspondance entre protocoles : comptes `role:` uniquement (comme `observateurs_multi_protocoles`).
- Statuts en N : nouveau (première saison = N), fidèle (N et N-1), revenant (N, pas N-1, avant), parti (N-1, pas N).
- Ancienneté : saisons distinctes de participation jusqu'à N, tranches 1 / 2-4 / 5-9 / 10 et plus.
- Engagement : aires suivies en N par participant, 1 / 2 / 3 et plus.
- Valorisation : heures × `taux_horaire_benevolat` (0 par défaut = non affichée).
- Base en lecture seule ; `EXPLAIN` de la nouvelle requête ; tests sans base ; lint 120 ; textes en français.
- Statuts : palette validée, ordre fixe fidèle `BLEU`, revenant `VERT_EAU`, nouveau `ORANGE`, parti `GRIS`.

## Review Focus

1. Protocole sans aucun bénévole en N : phrase « aucun bénévole », graphiques « Aucune donnée », pas d'erreur.
2. Première saison de la série (pas de N-1) : tous nouveaux, aucun parti, aucun fidèle.
3. Observateurs « Non renseigné » ou sans compte `role:` : exclus des bénévoles et du réseau.
4. Aire de module sans créateur (`id_inventor` nul) : catégorie « Non renseigné » ; protocoles Faune-France : pas de
   requête, pas de bloc.
5. SHOC (saison d'hiver) dans le réseau : participation comptée à la saison de chaque protocole (année = numéro de
   saison), documenté dans le METHODO.

---

### Task 1: calculs par protocole (`participants.py`)

**Files:** Create `src/reportgenerator/analysis/indicateurs/participants.py` ; Test `tests/test_indicateurs.py`

**Interfaces — Produces:**
- `STATUTS = ("fidèle", "revenant", "nouveau", "parti")`, `TRANCHES_ANCIENNETE`, `TRANCHES_ENGAGEMENT = ("1", "2", "3+")`
- `participants(jeu, saison, categorie) -> set[str]`
- `statuts(jeu, saison, categorie) -> dict[str, str]` (participants N et partis)
- `serie_statuts(jeu, debut, saison, categorie) -> list[dict]` : `{"saison", "fidèle", "revenant", "nouveau", "parti"}`
- `statuts_par_departement(jeu, saison, categorie) -> list[dict]` : `{"departement", *STATUTS, "total"}` (total = présents N),
  tri total décroissant puis nom
- `anciennete(jeu, saison, categorie) -> dict[str, int]` ; `engagement(jeu, saison, categorie) -> dict[str, int]`
- `travail(jeu, saison, categorie, temps) -> dict` : participants, part_observateurs, aires, part_aires, releves,
  donnees, heures, heures_estimees (aires = catégorie de l'aire, relevés/données = catégorie du relevé, heures =
  `temps_heures(...)["par_categorie"]`)

- [ ] Tests (jeu factice, catégorie « Bénévole » et une autre catégorie) : `test_statuts_participants`
  (O1 bénévole 2023-2025 → fidèle ; première saison → nouveau ; absent N-1 présent avant → revenant ; N-1 seul →
  parti), `test_statuts_premiere_saison` (Review 2), `test_participants_hors_categorie` (Review 3 : Non renseigné et
  autre catégorie exclus), `test_anciennete_engagement_travail` (sommes = participants N).
- [ ] RED, implémentation, GREEN ; commit « Indicateurs : calculs des participants par catégorie ».

### Task 2: aires des modules jamais visitées

**Files:** Modify `queries.py` (méthode `createurs_aires_monitoring(module) -> list[dict]` : id_aire, annee_creation,
organisme, email, connu, d'après le site le plus ancien de l'aire, `t_base_sites.id_inventor`) ; `participants.py`
(`aires_jamais_visitees(aires_ids: set, createurs: list[dict]) -> list[dict]` : `{"categorie", "annee_creation",
"aires"}` trié par année puis catégorie, catégorie via `categorie_observateur`) ; `outils/verif/explain_indicateurs.py`.

- [ ] Test `test_aires_jamais_visitees` : aire sans passage, créateur sans organisme → Bénévole ; créateur inconnu →
  Non renseigné (Review 4) ; aire visitée ignorée.
- [ ] RED, implémentation, GREEN ; `EXPLAIN` en lecture seule ; commit.

### Task 3: réseau multi-protocoles

**Files:** `participants.py`

**Interfaces — Produces:**
- `reseau(jeux: dict, saisons: dict, categorie) -> dict` : `{"participants", "multi", "combinaisons": [(codes, n)]}`
  (comptes `role:`, combinaisons triées n décroissant)
- `serie_reseau(jeux, debut, saison, categorie) -> list[dict]` : `{"saison", "participants"}` (chaque protocole à la
  même saison numérotée)
- `reseau_par_departement(jeux, saisons, categorie) -> list[dict]` : `{"departement", "participants"}`

- [ ] Test `test_reseau_benevoles` : un compte sur deux protocoles → multi 1, combinaison (stom, sterf) ; compte
  non `role:` ignoré.
- [ ] RED, implémentation, GREEN ; commit.

### Task 4: graphiques

**Files:** `figures.py` : `chart_renouvellement(serie, path, lib_saison)` (barres empilées fidèle/revenant/nouveau,
partis sous l'axe), `chart_statuts_departements(lignes, path)` (barres horizontales empilées, partis en étiquette),
`chart_anciennete_engagement(anciennete, engagement, path, aire)` (deux panneaux), `chart_combinaisons(combinaisons,
path, labels)`, `chart_reseau(serie, path, lib_saison)`. Tous : « Aucune donnée » si vide.

- [ ] Étendre `test_figures` (cas remplis et vides) ; RED, implémentation, GREEN ; contrôle visuel ; commit.

### Task 5: câblage des briques, template, documentation

**Files:** `bricks/indicateurs.py` (CLES += `TEXTE_BENEVOLES`, `BLOCS_BENEVOLES` ; `ind_synthese` provides
`TEXTE_RESEAU_BENEVOLE`, `BLOCS_RESEAU_BENEVOLE`) ; `textes.py` (`texte_benevoles`, `texte_reseau`) ; `dossier.toml`
(`taux_horaire_benevolat = 0`) ; template (H2 « Bénévoles » après « Espèces » ; H1 « Le réseau bénévole » avant la
conclusion) ; `METHODO.md`.

- [ ] Tests : `test_section_benevoles` (blocs image/légende, annexes « Bénévoles : … »), `test_section_sans_benevole`
  (Review 1 : phrase, pas d'erreur), `test_reseau_synthese`, valorisation affichée seulement si taux > 0.
- [ ] RED, implémentation, GREEN ; template reconstruit ; suite complète, lint, `check` ; commit.
- [ ] Dry-run régional 2026 (tous protocoles), ouverture Word (COM), placeholders, contrôle des graphiques.
