# Dossier « Indicateurs de biodiversité » : plan de mise en œuvre

> **Pour les agents :** sous-skill requis : superpowers:subagent-driven-development (recommandé) ou
> superpowers:executing-plans, tâche par tâche. Les étapes sont des cases à cocher (`- [ ]`).

**Objectif :** un nouveau type de dossier `indicateurs` qui produit la trame Word du rapport d'exécution annuel
« Indicateurs de biodiversité en AuRA » (STOC, SHOC, STOM, STERF, POP Reptile, POP Amphibien) pour la zone et l'année
de la demande.

**Architecture :** un adaptateur par source (Faune-France via `pr_vigienature`, modules `gn_monitoring`) lit la base
en lecture seule et range les lignes dans un modèle commun (`Jeu` : aires, unités, passages, observateurs,
observations, en DataFrames pandas). Des analyses communes, en fonctions pures, calculent pour chaque protocole les
mêmes indicateurs. Une brique par protocole (`stoc`, `shoc`, …) remplit une section `{{#code}}…{{/code}}` du template,
avec les mêmes placeholders préfixés. Les analyses propres à un protocole sont des suites de blocs
(`inserer_blocs` du PLSOC).

**Stack :** Python 3.12, pandas (déjà présent avec geopandas), shapely, matplotlib, python-docx, psycopg 3. Pas de
nouvelle dépendance.

**Conception :** [docs/indicateurs/conception.md](conception.md), approuvée le 17/11/2026. Le plan s'appuie dessus.
Les exécutants lisent les deux.

## Contraintes globales

- Base en **lecture seule** : chaque requête ouvre une connexion `read_only = True` (modèle `PlsocQueries._fetch`).
  Aucun `CREATE`/`UPDATE`/`DROP`, aucune table temporaire non plus (les données passent en pandas).
- **Jamais de `generate`/`run`** sur les demandes réelles. Les essais passent par `outils/dryrun/dryrun_dossier.py`,
  avec un `id_area` de `ref_geo.l_areas` : région AuRA `2191961`, Savoie `2236653`.
- Branche `indicateurs` (créée depuis `eolien_vulnerabilite` : l'architecture multi-dossiers n'est pas dans `main`).
- Toujours `poetry run`. Les scripts d'essai vont dans le scratchpad, jamais `python -`.
- Ne pas lire le schéma `grafana` (pas de droit `USAGE`), ni `t_annuaire_*`, ni `parcelle_avec_exploitant`.
- **Jamais d'email dans le rapport.** Les noms d'observateurs n'apparaissent que dans la liste des sites STOM et dans
  l'annexe de contrôle.
- Toute règle métier est écrite une fois : `analysis/indicateurs/selections.py` (règles), `dossier.toml` (seuils,
  périodes, temps, objectifs ; sous-tables `[params.xxx]` en fin de fichier).
- Textes et documentation en français. Toute règle métier est reportée dans `METHODO.md` **et** dans le texte du
  template Word.
- Ordre des catégories et priorité : `Salarié LPO` > `Organisme tiers` > `Bénévole` > `Non renseigné`.
- Placeholders : préfixes `STOC`, `SHOC`, `STOM`, `STERF`, `POPR`, `POPA` ; tableau, image ou blocs seul dans son
  paragraphe ; `merge_results` refuse une clé fournie par deux briques.
- Lint : `poetry run flake8 --max-line-length 120 src/reportgenerator/analysis src/reportgenerator/bricks
  src/reportgenerator/core tests outils`.

## Points de vigilance pour la relecture

Cas que la conception implique sans qu'une tâche les teste naturellement. Chacun a son test, dans la tâche indiquée.

1. **Protocole absent de la zone** (département sans STOM) : section masquée, ligne absente des chiffres clés de la
   page de garde, aucune division par zéro. Test : `test_section_masquee_sans_aire` (tâche 8),
   `test_synthese_ignore_protocole_vide` (tâche 11).
2. **Aires dans l'historique mais aucune en N** (aire abandonnée) : section affichée, texte « aucune aire suivie en
   N », pas de `nan` dans le Word. Test : `test_annee_sans_passage_texte_explicite` (tâche 8).
3. **Passage sans observateur** (visite sans `cor_visit_observer`, relevé STOC sans `observateur`, avant 2015) : le
   passage est classé « Non renseigné » et la somme par catégorie redonne le total. Test :
   `test_categories_somme_egale_total` (tâche 5).
4. **Pas d'année N-1** (première année d'un protocole, STERF en 2024) : l'écart affiche « — », jamais `+100 %` ni
   `ZeroDivisionError`. Test : `test_ecart` (tâche 7).
5. **Limites de la saison SHOC** : un relevé du 20 novembre ou du 10 février tombe dans la même saison que décembre et
   janvier ; la saison 2025 s'affiche « 2024-2025 ». Test : `test_saison_hiver` (tâche 2).

---

### Tâche 1 : jetons de paramètres et protocoles par défaut dans `list_analyse`

Le dossier doit accepter `indicateurs` (tous les protocoles), `indicateurs, stoc, sterf` (deux protocoles) et
`indicateurs, annee_2024` (année forcée) sans colonne nouvelle.

**Fichiers :**
- Modifier : `src/reportgenerator/core/dossier.py` (`Dossier`, `select_analyses`, `load_dossier`)
- Modifier : `src/reportgenerator/run_single.py` (construction de `ReportContext.params`)
- Modifier : `outils/dryrun/dryrun_dossier.py` (même chose)
- Tests : `tests/test_core.py`

**Interfaces :**
- Produit : `Dossier.default_optional: tuple[str, ...]` (lu dans `[analyses] par_defaut`, vide par défaut) ;
  `Dossier.params_for(list_analyse: str | None) -> dict` ; `select_analyses` inchangé en signature.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
def _dossier(**kw):
    return Dossier(name="t", label="t", path=Path("."), template=Path("t.docx"), qgis_project=None,
                   required=("socle",), optional=("a", "b"), params={"annee": 0, "seuil": 5, "actif": True},
                   trigger_analyses={"declencheur": []}, **kw)


def test_jeton_remplace_un_parametre_entier():
    d = _dossier()
    assert d.params_for("declencheur, annee_2024")["annee"] == 2024
    assert d.params_for("declencheur")["annee"] == 0
    assert d.params_for("declencheur, actif_0")["actif"] is True      # booléen : pas de remplacement
    assert d.params_for("declencheur, inconnu_3") == d.params           # clé absente : ignoré


def test_jeton_de_parametre_non_signale_comme_ignore():
    enabled, ignored = _dossier().select_analyses("declencheur, annee_2024, a")
    assert enabled == ["socle", "a"] and ignored == []


def test_optionnelles_par_defaut_si_aucune_demandee():
    d = _dossier(default_optional=("a", "b"))
    assert d.select_analyses("declencheur")[0] == ["socle", "a", "b"]
    assert d.select_analyses("declencheur, b")[0] == ["socle", "b"]
    assert _dossier().select_analyses("declencheur")[0] == ["socle"]
```

- [ ] **Étape 2 : lancer les tests, ils échouent**

Commande : `poetry run pytest tests/test_core.py -q -k "jeton or par_defaut"`
Attendu : échec (`unexpected keyword argument 'default_optional'`, `no attribute 'params_for'`).

- [ ] **Étape 3 : implémenter dans `core/dossier.py`**

Jeton de paramètre : une valeur `^(?P<cle>[a-z_]+)_(?P<val>\d+)$` dont la clé existe dans `params` avec une valeur
`int` qui n'est pas un `bool`. `params_for` renvoie une copie de `params` avec ces remplacements.
`select_analyses` retire ces jetons de `ignored`. Si aucune optionnelle n'est activée, `enabled = default_optional`.
`load_dossier` lit `analyses.get("par_defaut", [])`.

- [ ] **Étape 4 : utiliser `params_for`**

Dans `run_single.py` et `outils/dryrun/dryrun_dossier.py`, remplacer `params=dict(dossier.params)` par
`params=dossier.params_for(list_analyse)`. Dans le dry-run, `DRYRUN_PARAMS` reste prioritaire : l'appliquer après.

- [ ] **Étape 5 : lancer toute la suite, elle passe**

Commande : `poetry run pytest -q`
Attendu : tout passe (les dossiers existants n'ont ni `par_defaut` ni jeton de paramètre).

- [ ] **Étape 6 : commit**

```bash
git add src/reportgenerator/core/dossier.py src/reportgenerator/run_single.py outils/dryrun/dryrun_dossier.py tests/test_core.py
git commit -m "Dossiers : jetons de paramètres (annee_AAAA) et analyses optionnelles par défaut"
```

---

### Tâche 2 : modèle commun et règles métier

**Fichiers :**
- Créer : `src/reportgenerator/analysis/indicateurs/__init__.py` (vide)
- Créer : `src/reportgenerator/analysis/indicateurs/modele.py`
- Créer : `src/reportgenerator/analysis/indicateurs/selections.py`
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Produit (`modele.py`) :
  ```python
  COLONNES = {
      "aires": ["id_aire", "nom_aire", "wkt", "x", "y", "nb_unites", "commune", "departement", "zbiog"],
      "unites": ["id_unite", "id_aire", "nom_unite"],
      "passages": ["id_passage", "id_aire", "id_unite", "date", "saison", "nb_donnees", "duree_min", "duree_estimee"],
      "observateurs": ["id_passage", "id_observateur", "nom", "organisme", "categorie"],
      "observations": ["id_passage", "cd_ref", "nom", "effectif"],
      "etats": ["id_aire", "saison", "etat"],
  }

  @dataclass
  class Jeu:
      code: str                                        # "stoc", "shoc", "stom", "sterf", "pop_reptile", ...
      aires: pd.DataFrame
      unites: pd.DataFrame
      passages: pd.DataFrame                           # date : datetime.date ; saison : int
      observateurs: pd.DataFrame
      observations: pd.DataFrame                       # seulement les saisons >= N - annees_especes + 1
      etats: pd.DataFrame | None = None                # état d'aire fourni par la base (POP)
      anomalies: list[dict] = field(default_factory=list)   # {code, libelle, aire, unite, date, nom}

  def jeu_vide(code: str) -> Jeu
  def verifier(jeu: Jeu) -> Jeu        # ValueError si une colonne de COLONNES manque ; renvoie le jeu
  ```
- Produit (`selections.py`) :
  ```python
  PROTOCOLES = ("stoc", "shoc", "stom", "sterf", "pop_reptile", "pop_amphibien")   # ordre du rapport
  PREFIXES = {"stoc": "STOC", "shoc": "SHOC", "stom": "STOM", "sterf": "STERF",
              "pop_reptile": "POPR", "pop_amphibien": "POPA"}
  CATEGORIES = ("Salarié LPO", "Organisme tiers", "Bénévole", "Non renseigné")    # ordre = priorité

  def categorie_observateur(organisme: str | None, email: str | None, connu: bool = True) -> tuple[str, str | None]
  def categorie_prioritaire(categories: Iterable[str]) -> str
  def saison(d: date, mode: str) -> int                  # mode "civile" ou "hiver"
  def libelle_saison(s: int, mode: str) -> str
  def annee_par_defaut(aujourdhui: date, fin_saison: str = "10-01") -> int
  def numero_periode(d: date, periodes: list[list[str]]) -> int | None    # 1 = première période ; "MM-JJ"
  def dans_periode(d: date, periode: list[str]) -> bool
  def est_stoc_site_n2000(nom_site: str | None, motif: str) -> bool        # motif façon ILIKE : "STOC N2000%"
  def completer_durees(passages: pd.DataFrame) -> pd.DataFrame
  ```

Règles à appliquer exactement :
- `categorie_observateur` : organisme qui commence par « LPO » (sans tenir compte de la casse ni des espaces) **ou**
  email qui contient « lpo » → `("Salarié LPO", organisme or "LPO")`. Sinon, email `@ofb.gouv.fr` ou organisme qui
  contient « OFB » ou « Office français de la biodiversité » → `("Organisme tiers", "OFB")`. Sinon, organisme
  renseigné et différent de « - » → `("Organisme tiers", organisme)`. Sinon `("Bénévole", None)`.
  `connu=False` (observateur Faune-France sans compte) → `("Non renseigné", None)`.
- `saison(d, "hiver")` : année de janvier, soit `d.year + 1` si `d.month >= 7`, sinon `d.year`. `libelle_saison(2025,
  "hiver")` → `"2024-2025"`. Note pour la conception : le rapport 2025 montre l'hiver 2024-2025, la saison 2025 du
  modèle. C'est le sens de « rattaché à N-1 » du §5.2 : corriger la phrase du §5.2 dans la même tâche.
- `completer_durees` : une durée manquante prend la moyenne des durées connues de la même saison et passe
  `duree_estimee = True`. Si aucune durée n'est connue dans la saison, elle reste vide.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
@pytest.mark.parametrize("organisme, email, attendu", [
    ("LPO Auvergne-Rhône-Alpes", "x@gmail.com", ("Salarié LPO", "LPO Auvergne-Rhône-Alpes")),
    (None, "prenom.nom@lpo.fr", ("Salarié LPO", "LPO")),
    (None, "a.b@ofb.gouv.fr", ("Organisme tiers", "OFB")),
    ("CEN Savoie", "a@cen.fr", ("Organisme tiers", "CEN Savoie")),
    ("-", None, ("Bénévole", None)),
    (None, None, ("Bénévole", None)),
])
def test_categorie_observateur(organisme, email, attendu):
    assert s.categorie_observateur(organisme, email) == attendu


def test_categorie_inconnue_et_priorite():
    assert s.categorie_observateur("LPO", "x@lpo.fr", connu=False) == ("Non renseigné", None)
    assert s.categorie_prioritaire(["Bénévole", "Organisme tiers"]) == "Organisme tiers"
    assert s.categorie_prioritaire([]) == "Non renseigné"


def test_saison_hiver():
    for d in (date(2024, 11, 20), date(2024, 12, 15), date(2025, 1, 20), date(2025, 2, 10)):
        assert s.saison(d, "hiver") == 2025
    assert s.saison(date(2025, 5, 2), "civile") == 2025
    assert s.libelle_saison(2025, "hiver") == "2024-2025" and s.libelle_saison(2025, "civile") == "2025"


def test_annee_par_defaut():
    assert s.annee_par_defaut(date(2026, 11, 17)) == 2026
    assert s.annee_par_defaut(date(2026, 9, 30)) == 2025


def test_periodes():
    p = [["04-01", "05-08"], ["05-09", "06-15"]]
    assert s.numero_periode(date(2025, 5, 8), p) == 1
    assert s.numero_periode(date(2025, 5, 9), p) == 2
    assert s.numero_periode(date(2025, 3, 20), p) is None
    assert s.dans_periode(date(2025, 3, 20), ["03-01", "03-31"])


def test_stoc_site_n2000():
    assert s.est_stoc_site_n2000("STOC N2000 Dombes 3", "STOC N2000%")
    assert not s.est_stoc_site_n2000("STOC ONF Chartreuse", "STOC N2000%")
    assert not s.est_stoc_site_n2000(None, "STOC N2000%")


def test_completer_durees():
    p = pd.DataFrame({"saison": [2025, 2025, 2025, 2024], "duree_min": [60, 30, None, None],
                      "duree_estimee": [False, False, False, False]})
    r = s.completer_durees(p)
    assert r["duree_min"].tolist()[:3] == [60, 30, 45] and r["duree_estimee"].tolist()[2] is True
    assert pd.isna(r["duree_min"].iloc[3])


def test_verifier_jeu():
    assert verifier(jeu_vide("stoc")).code == "stoc"
    with pytest.raises(ValueError):
        verifier(dataclasses.replace(jeu_vide("stoc"), aires=pd.DataFrame({"id_aire": []})))
```

- [ ] **Étape 2 : lancer les tests, ils échouent** : `poetry run pytest tests/test_indicateurs.py -q` → `ModuleNotFoundError`.
- [ ] **Étape 3 : implémenter `modele.py` et `selections.py`** avec les signatures ci-dessus.
- [ ] **Étape 4 : lancer les tests, ils passent** : `poetry run pytest tests/test_indicateurs.py -q`.
- [ ] **Étape 5 : corriger la phrase « Saison » du §5.2 de `docs/indicateurs/conception.md`** (saison SHOC = année de
  janvier).
- [ ] **Étape 6 : commit** : `git commit -m "Indicateurs : modèle commun et règles (catégories, saisons, périodes)"`.

---

### Tâche 3 : jeu factice partagé par les tests

Un seul jeu construit à la main, réutilisé par les tâches 5 à 12. Les valeurs attendues des tests en découlent.

**Fichiers :**
- Créer : `tests/indicateurs_factice.py`

**Interfaces :**
- Produit : `jeu_factice(code: str = "stom") -> Jeu` ; constantes `ZONE_WKT`, `DEPARTEMENTS` (liste de dicts
  `{code, nom, wkt}` : « 73 Savoie », « 38 Isère »).

Contenu exact (saison civile, `observations` présentes pour 2024 et 2025) :

| Aire | Département | Unités | Commune |
|---|---|---|---|
| A1 | Savoie | U1a, U1b | Chambéry |
| A2 | Savoie | U2a | Albertville |
| A3 | Isère | U3a | Grenoble |
| A4 | Isère | U4a, U4b, U4c, U4d, U4e | Vienne |

| Passage | Aire / unité | Date | Données | Durée (min) | Estimée | Observateurs |
|---|---|---|---|---|---|---|
| P1 | A1 / U1a | 2023-05-20 | 10 | 60 | non | O1 |
| P2 | A3 / U3a | 2023-06-01 | 5 | 30 | non | O2 |
| P3 | A1 / U1a | 2024-05-20 | 8 | 60 | non | O1 |
| P4 | A2 / U2a | 2024-06-10 | 4 | 45 | non | O3 |
| P5 | A3 / U3a | 2024-06-02 | 6 | 30 | non | O2 |
| P6 | A1 / U1a | 2025-05-21 | 12 | 60 | non | O1, O2 |
| P7 | A1 / U1b | 2025-05-21 | 3 | 30 | oui | O1 |
| P8 | A2 / U2a | 2025-06-11 | 7 | 45 | non | O3 |
| P9 | A4 / U4a | 2025-07-01 | 2 | vide | non | aucun |

`nom_aire` = identifiant (« A1 »…), `nb_unites` = nombre d'unités du tableau.
Observateurs : O1 Bénévole, O2 Salarié LPO, O3 Organisme tiers « CEN Savoie » ; `id_observateur` `role:1`,
`role:2`, `role:3` ; noms « Observateur 1 », « Observateur 2 », « Observateur 3 ». `id_passage` = « P1 »…
La durée de P9 reste vide dans le jeu : c'est `temps_heures` qui la complète (tâche 5).
Observations : P3 (1001 Merle noir, 2) ; P4 (1002 Pinson des arbres, 1) ; P6 (1001, 3), (1002, 2) ; P7 (1001, 1) ;
P8 (1002, 4), (1003 Rouge-gorge familier, 1) ; P9 (1001, 2). `wkt` des aires : petits carrés de 1 km dans
`ZONE_WKT` (Lambert 93), Savoie au nord, Isère au sud.

- [ ] **Étape 1 : écrire `tests/indicateurs_factice.py`**, qui passe `verifier()`.
- [ ] **Étape 2 : vérifier** : `poetry run pytest tests/test_indicateurs.py -q` passe toujours (le module est importé
  par un test `test_jeu_factice_valide` : `verifier(jeu_factice())`).
- [ ] **Étape 3 : commit** : `git commit -m "Indicateurs : jeu factice des tests"`.

---

### Tâche 4 : adaptateurs (lignes de la base → `Jeu`)

Fonctions pures : elles reçoivent les lignes des requêtes (listes de dicts) et rendent un `Jeu`. Le SQL vient à la
tâche 9.

**Fichiers :**
- Créer : `src/reportgenerator/analysis/indicateurs/adaptateurs.py`
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Consomme : `selections.categorie_observateur`, `saison`, `completer_durees`, `modele.verifier`.
- Produit :
  ```python
  def jeu_vigienature(code, aires, releves, observations, observateurs, localisation, regle) -> Jeu
  def jeu_monitoring(code, aires, unites, passages, observateurs, observations, localisation, regle,
                     etats=(), anomalies=()) -> Jeu
  ```
  Lignes reçues (clés exactes, fournies par la tâche 9) :
  - `aires` : `id_aire, nom_aire, wkt, x, y, nb_unites` ; `localisation` : `id_aire, commune, departement, zbiog` ;
  - vigienature : `releves` : `id_passage, id_aire, id_unite, nom_unite, date, observateur, nb_donnees,
    passage_mnhn` ; `observateurs` : `observateur, id_role, nom, email, organisme` (une ligne par identifiant
    Faune-France retrouvé ; `id_role` vide si l'email n'a pas de compte) ;
  - monitoring : `unites` : `id_unite, id_aire, nom_unite` ; `passages` : `id_passage, id_aire, id_unite, date,
    nb_donnees, duree_min, duree_estimee` ; `observateurs` : `id_passage, id_role, nom, email, organisme` ;
    `etats` : `id_aire, saison, etat` ; `anomalies` : `code, libelle, aire, unite, date` ;
  - `observations` (les deux) : `id_passage, cd_ref, nom, effectif`.
  - `regle` : la sous-table `[params.protocoles.<code>]` (tâche 8) ; utilisés ici : `saison`, `debut_serie`,
    `debut_observateurs` (vigienature).

Règles :
- les passages dont la saison est avant `debut_serie` sont retirés (et leurs observations et observateurs) ;
- vigienature : `id_observateur = f"role:{id_role}"` si le compte est retrouvé, sinon `f"ff:{observateur}"` en
  « Non renseigné », avec une anomalie `observateur_inconnu` (une par observateur, `nom` renseigné, sans email) ;
  aucun observateur avant `debut_observateurs` (2015) ; un `passage_mnhn` hors de 1 à 3 donne une anomalie
  `passage_mnhn` ; les unités sont les `(id_aire, id_unite, nom_unite)` distincts des relevés ;
- monitoring : `id_observateur = f"role:{id_role}"` ; les unités d'aire `sans_aire` donnent une anomalie
  `site_sans_aire` ; `completer_durees` est appliquée ;
- `nom` des observateurs gardé (liste STOM, annexe de contrôle) ; l'email ne sort jamais de l'adaptateur.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
REGLE_V = {"saison": "hiver", "debut_serie": 2015, "debut_observateurs": 2015}


def test_jeu_vigienature_saisons_categories_anomalies():
    aires = [{"id_aire": "C1", "nom_aire": "Carré 1", "wkt": "POINT(0 0)", "x": 0, "y": 0, "nb_unites": 2}]
    releves = [
        {"id_passage": 1, "id_aire": "C1", "id_unite": "C1/1", "nom_unite": "1", "date": date(2024, 12, 10),
         "observateur": "11", "nb_donnees": 5, "passage_mnhn": 1},
        {"id_passage": 2, "id_aire": "C1", "id_unite": "C1/2", "nom_unite": "2", "date": date(2025, 1, 12),
         "observateur": "99", "nb_donnees": 3, "passage_mnhn": 7},
        {"id_passage": 3, "id_aire": "C1", "id_unite": "C1/1", "nom_unite": "1", "date": date(2013, 12, 10),
         "observateur": "11", "nb_donnees": 1, "passage_mnhn": 1},
    ]
    obs = [{"observateur": "11", "id_role": 5, "nom": "A B", "email": "a@lpo.fr", "organisme": None}]
    loc = [{"id_aire": "C1", "commune": "X", "departement": "Savoie", "zbiog": "Alpes"}]
    j = jeu_vigienature("shoc", aires, releves, [], obs, loc, REGLE_V)
    assert j.passages["saison"].tolist() == [2025, 2025]                 # 2013 retiré (début de série)
    assert set(j.observateurs["categorie"]) == {"Salarié LPO", "Non renseigné"}
    assert {a["code"] for a in j.anomalies} == {"observateur_inconnu", "passage_mnhn"}
    assert "email" not in j.observateurs.columns
    assert j.aires.loc[0, "departement"] == "Savoie" and len(j.unites) == 2


def test_jeu_monitoring_durees_et_sans_aire():
    aires = [{"id_aire": "sans_aire", "nom_aire": "Sans aire", "wkt": None, "x": 0, "y": 0, "nb_unites": 1}]
    unites = [{"id_unite": "7", "id_aire": "sans_aire", "nom_unite": "Mare 7"}]
    passages = [
        {"id_passage": 1, "id_aire": "sans_aire", "id_unite": "7", "date": date(2025, 4, 1), "nb_donnees": 2,
         "duree_min": 40, "duree_estimee": False},
        {"id_passage": 2, "id_aire": "sans_aire", "id_unite": "7", "date": date(2025, 5, 1), "nb_donnees": 1,
         "duree_min": None, "duree_estimee": False},
    ]
    j = jeu_monitoring("pop_amphibien", aires, unites, passages, [], [], [], {"saison": "civile",
                       "debut_serie": 2022})
    assert j.passages["duree_min"].tolist() == [40, 40] and j.passages["duree_estimee"].tolist() == [False, True]
    assert [a["code"] for a in j.anomalies] == ["site_sans_aire"]
```

- [ ] **Étape 2 : lancer, échec attendu** (`ImportError`).
- [ ] **Étape 3 : implémenter `adaptateurs.py`.**
- [ ] **Étape 4 : lancer, les tests passent** : `poetry run pytest tests/test_indicateurs.py -q`.
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : adaptateurs Faune-France et monitoring vers le modèle commun"`.

---

### Tâche 5 : analyses communes (année N)

**Fichiers :**
- Créer : `src/reportgenerator/analysis/indicateurs/communes.py`
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Consomme : `Jeu`, `selections.CATEGORIES`, `categorie_prioritaire`, `numero_periode`, `dans_periode`.
- Produit :
  ```python
  def categorie_passages(jeu) -> dict[id_passage, str]           # priorité entre les observateurs du passage
  def categorie_aires(jeu, saison) -> dict[id_aire, str]         # observateur au plus grand nombre de passages
  def temps_heures(jeu, saison, temps: dict) -> dict             # {"heures", "estime", "par_categorie": {cat: h}}
  def chiffres(jeu, saison, temps: dict) -> dict                 # voir clés ci-dessous
  def par_categorie(jeu, saison, temps: dict) -> list[dict]      # {categorie, aires, observateurs, donnees, heures}
  def statut_aires(jeu, saison) -> dict[id_aire, str]            # "suivie" | "nouvelle" | "non suivie"
  def completude(jeu, saison, regle) -> dict[id_aire, str]       # "complète" | "incomplète"
  def couverture(jeu, saison, regle, par_departement: bool) -> list[dict]
  ```
  `chiffres` renvoie `aires, unites, visites, releves, observateurs, donnees, especes, heures, heures_estimees`.
  Une **visite** est un couple `(id_aire, date)` distinct ; un **relevé** est une ligne de `passages`. `especes` vaut
  `None` si la saison n'a pas d'observations chargées.
  `temps` = sous-table `[params.protocoles.<code>.temps]` : `terrain_h` (nombre ou `"mesure"`), `unite_terrain`
  (`"aire"` ou `"visite"`), `complement_h`, `unite_complement`. « mesure » = somme de `duree_min` / 60, après
  `completer_durees` (idempotente : le jeu factice garde une durée vide) ;
  `estime` vaut vrai dès qu'un forfait est utilisé ou qu'une durée est estimée. La part par catégorie suit la
  catégorie de l'aire (forfait par aire) ou du passage (forfait par visite : catégorie prioritaire des passages de
  la visite ; durée mesurée : catégorie du passage).
  `completude` : avec `regle["periodes"]`, l'aire est complète si chaque période contient au moins une visite ;
  avec `regle["passages_par_unite"]` et `regle["periode_unite"]`, chaque unité visitée en N doit avoir ce nombre de
  dates dans la période ; si `jeu.etats` est fourni, l'état de la base est repris tel quel.
  `couverture` : par département (`departement, aires, unites, visites, observateurs, donnees, nouvelles,
  completes`) avec une ligne `total=True`, ou par aire (`aire, commune, departement, unites, visites,
  observateurs, completude`).

- [ ] **Étape 1 : écrire les tests qui échouent** (jeu factice de la tâche 3)

```python
TEMPS_MESURE = {"terrain_h": "mesure", "unite_terrain": "visite", "complement_h": 0, "unite_complement": "aire"}


def test_chiffres_2025():
    c = communes.chiffres(jeu_factice(), 2025, TEMPS_MESURE)
    assert (c["aires"], c["unites"], c["visites"], c["releves"]) == (3, 4, 3, 4)
    assert (c["observateurs"], c["donnees"], c["especes"]) == (3, 24, 3)
    assert c["heures"] == 3.0 and c["heures_estimees"] is True       # P9 complété à 45 min, P7 estimé


def test_categories_somme_egale_total():
    j = jeu_factice()
    assert communes.categorie_aires(j, 2025) == {"A1": "Bénévole", "A2": "Organisme tiers", "A4": "Non renseigné"}
    assert communes.categorie_passages(j)["P6"] == "Salarié LPO"
    lignes = {r["categorie"]: r for r in communes.par_categorie(j, 2025, TEMPS_MESURE)}
    assert sum(r["aires"] for r in lignes.values()) == 3
    assert sum(r["donnees"] for r in lignes.values()) == 24
    assert lignes["Salarié LPO"]["donnees"] == 12 and lignes["Non renseigné"]["donnees"] == 2


def test_temps_forfaitaires():
    j = jeu_factice()
    par_aire = {"terrain_h": 5, "unite_terrain": "aire", "complement_h": 1, "unite_complement": "aire"}
    par_visite = {"terrain_h": 2, "unite_terrain": "visite", "complement_h": 0, "unite_complement": "aire"}
    assert communes.temps_heures(j, 2025, par_aire)["heures"] == 18
    assert communes.temps_heures(j, 2025, par_visite) == {"heures": 6, "estime": True,
        "par_categorie": {"Salarié LPO": 2, "Organisme tiers": 2, "Non renseigné": 2}}


def test_statut_completude_couverture():
    j = jeu_factice()
    assert communes.statut_aires(j, 2025) == {"A1": "suivie", "A2": "suivie", "A4": "nouvelle", "A3": "non suivie"}
    assert communes.completude(j, 2025, {"periodes": [["05-01", "06-30"]]}) == {
        "A1": "complète", "A2": "complète", "A4": "incomplète"}
    dep = communes.couverture(j, 2025, {"periodes": [["05-01", "06-30"]]}, par_departement=True)
    assert [(r["departement"], r["aires"]) for r in dep] == [("Isère", 1), ("Savoie", 2), ("Total", 3)]
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : implémenter `communes.py`.** Égalité dans `categorie_aires` : priorité `CATEGORIES`. Les
  départements sont triés par nom, le total en dernier.
- [ ] **Étape 4 : lancer, les tests passent.**
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : analyses communes de l'année (participation, catégories, temps, couverture)"`.

---

### Tâche 6 : historique, fidélisation et espèces

**Fichiers :**
- Modifier : `src/reportgenerator/analysis/indicateurs/communes.py`
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Produit :
  ```python
  def serie(jeu, debut: int, saison: int, temps: dict) -> list[dict]      # chiffres() pour chaque saison, + "saison"
  def series_categories(jeu, debut: int, saison: int) -> list[dict]       # {saison, <categorie>: nb observateurs}
  def fidelisation(jeu, saison) -> dict
  def especes(jeu, saison, n: int | None) -> list[dict]                   # {rang, nom, freq_aires, freq_unites, effectif}
  def evolution_especes(jeu, saison, n: int, annees: int) -> list[dict]   # {nom, <saison>: freq_aires, ...}
  def observateurs_multi_protocoles(jeux: dict[str, Jeu], saisons: dict[str, int]) -> int
  ```
  `fidelisation` renvoie : `aires_n1, reconduites, taux_reconduction_aires, nouvelles, abandonnees,
  observateurs_gagnes, observateurs_perdus, taux_reconduction_observateurs, cumul_aires, cumul_observateurs,
  anciennete_moyenne, plus_ancienne` (`{nom_aire, premiere, annees}`). Taux en pourcentage arrondi à l'entier,
  `None` si le dénominateur est nul. Les compteurs portent sur des comptes (`id_observateur`), jamais sur des noms.
  `serie` : `especes` vaut `None` pour une saison sans observations chargées (avant la fenêtre `annees_especes`).
  `series_categories` part de `regle.get("debut_observateurs", debut_serie)` (STOC : 2015, avec la note du §5.2).
  `especes` : fréquences en % (part des aires suivies, part des unités visitées où l'espèce est notée), tri par
  fréquence des aires décroissante, puis effectif décroissant, puis nom. `n=None` = toutes (annexe).
  `observateurs_multi_protocoles` : comptes `role:` présents dans au moins deux jeux à leur saison.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
def test_serie_et_categories():
    s = communes.serie(jeu_factice(), 2023, 2025, TEMPS_MESURE)
    assert [(r["saison"], r["aires"]) for r in s] == [(2023, 2), (2024, 3), (2025, 3)]
    assert s[0]["especes"] is None                                     # pas d'observations chargées en 2023
    cat = {r["saison"]: r for r in communes.series_categories(jeu_factice(), 2023, 2025)}
    assert cat[2025]["Bénévole"] == 1 and cat[2025]["Salarié LPO"] == 1 and cat[2025]["Organisme tiers"] == 1


def test_fidelisation():
    f = communes.fidelisation(jeu_factice(), 2025)
    assert (f["reconduites"], f["taux_reconduction_aires"], f["nouvelles"], f["abandonnees"]) == (2, 67, 1, 1)
    assert (f["observateurs_gagnes"], f["observateurs_perdus"], f["taux_reconduction_observateurs"]) == (0, 0, 100)
    assert (f["cumul_aires"], f["cumul_observateurs"], f["anciennete_moyenne"]) == (4, 3, 2.0)
    assert f["plus_ancienne"]["premiere"] == 2023 and f["plus_ancienne"]["annees"] == 3


def test_especes():
    e = communes.especes(jeu_factice(), 2025, n=None)
    assert [(r["nom"], r["freq_aires"], r["freq_unites"], r["effectif"]) for r in e] == [
        ("Merle noir", 67, 75, 6), ("Pinson des arbres", 67, 50, 6), ("Rouge-gorge familier", 33, 25, 1)]
    evo = communes.evolution_especes(jeu_factice(), 2025, n=2, annees=2)
    assert evo[0]["nom"] == "Merle noir" and evo[0][2024] == 33 and evo[0][2025] == 67


def test_observateurs_multi_protocoles():
    j = jeu_factice()
    assert communes.observateurs_multi_protocoles({"a": j, "b": j}, {"a": 2025, "b": 2025}) == 3
```

Les identifiants O1, O2, O3 du jeu factice sont `role:1`, `role:2`, `role:3`.

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : implémenter.**
- [ ] **Étape 4 : lancer, les tests passent.**
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : historique, fidélisation et espèces"`.

---

### Tâche 7 : textes, graphiques et carte

**Fichiers :**
- Créer : `src/reportgenerator/analysis/indicateurs/textes.py`
- Créer : `src/reportgenerator/analysis/indicateurs/figures.py`
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Produit (`textes.py`) :
  ```python
  def nombre(x) -> str                     # 81561 -> "81 561" (espace insécable fine U+202F) ; 10.5 -> "10,5"
  def ecart(n, n1) -> str                  # "+6 (+33 %)", "=", "−2 (−10 %)", "—" si n1 est None, "+5" si n1 == 0
  def texte_participation(label, aire, libelle, c: dict, c1: dict | None, temps_note: str) -> str
  def texte_couverture(label_aire, c: dict, fid: dict, par_departement: bool, nb_departements: int) -> str
  def texte_fidelisation(label_aire, fid: dict) -> str
  def texte_especes(c: dict, especes: list[dict]) -> str
  def note_temps(temps: dict, estime: bool) -> str     # « Temps mesuré… » ou « Temps estimé : 10,5 h par carré… »
  ```
  `aire` est `regle["aire"]` (« carré », « site », « aire ») et `libelle` le libellé de saison (`libelle_saison`).
  Si `c["aires"] == 0`, `texte_participation` renvoie « Aucun site suivi en 2025 dans la zone. » (« Aucune aire
  suivie » : « aire » est le seul libellé féminin) et les autres textes restent courts et sans chiffre vide.
- Produit (`figures.py`, matplotlib `Agg`, `apply_lpo_theme`, `_fin` repris du PLSOC) :
  ```python
  def chart_aires(serie: list[dict], path: Path, label_aire: str) -> Path              # barres par saison
  def chart_observateurs(series_cat: list[dict], path: Path) -> Path                   # barres empilées par catégorie
  def carte_aires(path: Path, zone_wkt: str, departements: list[dict], aires: pd.DataFrame,
                  statuts: dict[str, str]) -> Path                                     # suivie / nouvelle / non suivie
  ```
  Carte : contours des départements, emprise, aires colorées par statut, légende. Matplotlib et non QGIS : même choix
  que le PLSOC, sans projet QGIS à maintenir pour six protocoles (choix du constructeur, §7 de la conception).

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
def test_ecart():
    assert textes.ecart(24, 18) == "+6 (+33 %)"
    assert textes.ecart(3, 3) == "="
    assert textes.ecart(18, 20) == "−2 (−10 %)"
    assert textes.ecart(5, None) == "—"
    assert textes.ecart(5, 0) == "+5"


def test_nombre():
    assert textes.nombre(81561) == "81\u202f561" and textes.nombre(10.5) == "10,5"


def test_textes_sans_aire():
    vide = {"aires": 0, "observateurs": 0, "donnees": 0, "heures": 0, "heures_estimees": False}
    t = textes.texte_participation("STOM", "site", "2025", vide, None, "")
    assert t == "Aucun site suivi en 2025 dans la zone."
    assert textes.texte_participation("POP Reptile", "aire", "2025", vide, None, "").startswith("Aucune aire suivie")


def test_figures(tmp_path):
    j = jeu_factice()
    assert figures.chart_aires(communes.serie(j, 2023, 2025, TEMPS_MESURE), tmp_path / "a.png", "site").exists()
    assert figures.chart_observateurs(communes.series_categories(j, 2023, 2025), tmp_path / "o.png").exists()
    assert figures.carte_aires(tmp_path / "c.png", ZONE_WKT, DEPARTEMENTS, j.aires,
                               communes.statut_aires(j, 2025)).exists()
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : implémenter.** Formulations reprises des rapports (« En 2025, 304 carrés ont été suivis par 216
  observateurs… »), pas de mot « tendance » : les évolutions sont « descriptives ».
- [ ] **Étape 4 : lancer, les tests passent.**
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : textes, graphiques et carte"`.

---

### Tâche 8 : manifeste, brique socle et briques de protocole

**Fichiers :**
- Créer : `src/reportgenerator/dossiers/indicateurs/dossier.toml`
- Créer : `src/reportgenerator/bricks/indicateurs.py`
- Créer : `src/reportgenerator/analysis/indicateurs/chargement.py` (squelette ; le SQL arrive à la tâche 9)
- Modifier : `src/reportgenerator/bricks/__init__.py` (import `indicateurs`)
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Consomme : tout ce qui précède.
- Produit :
  ```python
  # chargement.py
  def charger(code: str, q, regle: dict, saison: int, annees_especes: int) -> Jeu
  # bricks/indicateurs.py
  CLES = ("ANNEE_LIBELLE", "TEXTE_PARTICIPATION", "TABLE_CHIFFRES", "TABLE_CATEGORIES", "NOTE_CATEGORIES",
          "TEXTE_COUVERTURE", "TABLE_COUVERTURE", "CARTE", "TEXTE_HISTORIQUE", "CHART_AIRES", "CHART_OBSERVATEURS",
          "TABLE_HISTORIQUE", "TEXTE_FIDELISATION", "TEXTE_ESPECES", "TABLE_ESPECES", "TABLE_EVOLUTION_ESPECES",
          "BLOCS_SPECIFIQUES")
  def cles_protocole(code: str) -> list[str]          # [f"{PREFIXES[code]}_{c}" for c in CLES]
  def jeu_protocole(ctx, code: str) -> Jeu            # ctx.cached(f"ind_jeu_{code}", ...)
  SPECIFIQUES: dict[str, Callable[[ctx, Jeu, int, dict], list[tuple]]]   # rempli aux tâches 10 et 11
  ```
  Brique `ind_socle` : `provides = ["AREA_NAME", "TITRE_RAPPORT", "ANNEE", "DATE_EXTRACTION", "TEXTE_ZONE"]` ;
  `data = {"annee", "zone", "departements", "par_departement", "q"}` ; `annee = params["annee"] or
  annee_par_defaut(date.today(), params["fin_saison"])`. `par_departement` est vrai si la zone touche au moins deux
  départements.
  Briques `stoc`, `shoc`, `stom`, `sterf`, `pop_reptile`, `pop_amphibien` : déclarées en boucle sur `PROTOCOLES`,
  `requires=["ind_socle"]`, `provides=cles_protocole(code)`. `data = {"jeu", "saison", "chiffres", "precedent",
  "fidelisation", "especes", "vide"}`.
  Une section est masquée (`meta={"sans_section": True}`, toutes les clés à `""`) si le jeu n'a **aucun passage**
  dans la zone, toutes saisons confondues. S'il a des passages mais aucun en N, la section reste, avec les textes
  « aucun … suivi en N » et l'historique.

`dossier.toml` (valeurs de la conception, §5.10 et §5.11) :

```toml
label = "Indicateurs de biodiversité - rapport d'exécution annuel"
template = "template.docx"

[declencheurs]
indicateurs = []

[analyses]
required = ["ind_socle", "ind_synthese"]
optional = ["stoc", "shoc", "stom", "sterf", "pop_reptile", "pop_amphibien"]
par_defaut = ["stoc", "shoc", "stom", "sterf", "pop_reptile", "pop_amphibien"]

[params]
titre = "Indicateurs de biodiversité en Auvergne-Rhône-Alpes"
annee = 0                  # 0 = dernière saison terminée ; jeton « annee_2024 » dans list_analyse pour forcer
fin_saison = "10-01"
annees_tableau = 5         # tableau des chiffres clés : N-4 à N
annees_especes = 5         # observations lues : N-4 à N (espèces, évolution, STOC-sites)
nb_especes = 20
nb_especes_evolution = 10
map_layout = "normal"

[params.protocoles.stoc]
label = "STOC-EPS"
source = "vigienature"
nom_protocole = ["STOC_EPS"]
aire = "carré"
unite = "point"
saison = "civile"
debut_serie = 2001
debut_observateurs = 2015
periodes = [["04-01", "05-08"], ["05-09", "06-15"]]
periode_optionnelle = ["03-01", "03-31"]
libelle_optionnelle = "mars"
note_statut = true
temps = { terrain_h = 10.5, unite_terrain = "aire", complement_h = 0, unite_complement = "aire" }
sites = { nom_protocole = ["STOC_SITES", "STOC_ONF", "STOC_SITES_RNF"], motif_n2000 = "STOC N2000%", debut_n2000 = 2021, nb_especes_rang = 40 }

[params.protocoles.shoc]
label = "SHOC"
source = "vigienature"
nom_protocole = ["SHOC"]
aire = "carré"
unite = "transect"
saison = "hiver"
debut_serie = 2015
debut_observateurs = 2015
periodes = [["12-01", "12-31"], ["01-01", "01-31"]]
note_statut = true
temps = { terrain_h = 2, unite_terrain = "visite", complement_h = 1, unite_complement = "aire" }

[params.protocoles.stom]
label = "STOM"
source = "monitoring"
module = "stom"
aire = "site"
unite = "point d'écoute"
saison = "civile"
debut_serie = 2019
periodes = [["05-10", "07-15"]]
temps = { terrain_h = 5, unite_terrain = "aire", complement_h = 1, unite_complement = "aire" }

[params.protocoles.sterf]
label = "STERF"
source = "monitoring"
module = "sterf_ebms"
aire = "site"
unite = "transect"
saison = "civile"
debut_serie = 2024
passages_par_unite = 4         # à confirmer avec le coordinateur STERF
periode_unite = ["05-01", "08-31"]
seuil_sterf_vrai = 5
objectif = 100
objectif_ideal = 150
objectifs_zbiog = {}           # objectifs par zone biogéographique (figure 13 du rapport 2025) : à renseigner
temps = { terrain_h = "mesure", unite_terrain = "visite", complement_h = 0, unite_complement = "visite" }

[params.protocoles.pop_reptile]
label = "POP Reptile"
source = "monitoring"
module = "POPReptile"
aire = "aire"
unite = "transect"
saison = "civile"
debut_serie = 2022
vue_etats = "v_popreptiles_aire_annee"
vue_anomalies = "v_popreptiles_anomalies"
objectif = 50
objectif_sur = "aires"         # 50 mailles 5 × 5 km
temps = { terrain_h = "mesure", unite_terrain = "visite", complement_h = 0, unite_complement = "visite" }

[params.protocoles.pop_amphibien]
label = "POP Amphibien"
source = "monitoring"
module = "POPAmphibien"
aire = "aire"
unite = "site (mare)"
saison = "civile"
debut_serie = 2022
vue_etats = "v_popamphibien_aire_annee"
vue_anomalies = "v_popamphibien_anomalies"
objectif = 500
objectif_sur = "unites"        # 500 mares
temps = { terrain_h = "mesure", unite_terrain = "visite", complement_h = 0, unite_complement = "visite" }
```

- [ ] **Étape 1 : écrire les tests qui échouent** (chargement remplacé par le jeu factice)

```python
def _ctx(tmp_path, monkeypatch, list_analyse, jeux):
    monkeypatch.setattr(chargement, "charger", lambda code, *a, **k: jeux.get(code, jeu_vide(code)))
    monkeypatch.setattr(IndicateursQueries, "zone", lambda self: {"wkt": ZONE_WKT, "surface_ha": 1000})
    monkeypatch.setattr(IndicateursQueries, "departements", lambda self: DEPARTEMENTS)
    d = load_dossier("indicateurs")
    enabled, _ = d.select_analyses(list_analyse)
    return ReportContext(service_name="factice", id_area=1, area_name="Test", referee="t", buffer=0, dossier=d,
                         enabled=enabled, output_dirs=create_analysis_dirs(tmp_path), queries=None,
                         params=d.params_for(list_analyse))


def test_section_masquee_sans_aire(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2025", {"stom": jeu_factice("stom")})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    r = get_brick("sterf").run(ctx)
    assert r.meta == {"sans_section": True} and set(r.texts) == set(cles_protocole("sterf"))
    r = get_brick("stom").run(ctx)
    assert not (r.meta or {}).get("sans_section")
    assert "3 sites" in r.texts["STOM_TEXTE_PARTICIPATION"]


def test_annee_sans_passage_texte_explicite(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2026", {"stom": jeu_factice("stom")})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    r = get_brick("stom").run(ctx)
    texte = " ".join(str(v) for v in r.texts.values())
    assert "Aucun site suivi en 2026" in texte and "nan" not in texte
```

Les briques appellent `chargement.charger(...)` par le module (et non par un `from … import charger`) pour que le
remplacement du test s'applique.

- [ ] **Étape 2 : lancer, échec attendu** (dossier inconnu).
- [ ] **Étape 3 : écrire `dossier.toml`, `chargement.py` (lève `NotImplementedError` pour l'instant),
  `bricks/indicateurs.py`.** Les tableaux passent par `analysis/plsoc/word.inserer_tableau` (colonnes et largeurs) et
  les blocs par `inserer_blocs`, importés depuis `analysis.plsoc.word`. `TABLE_CHIFFRES` : une ligne par indicateur
  (aires, unités, visites, observateurs, données, espèces, temps), colonnes N-1, N, écart. `TABLE_HISTORIQUE` :
  `annees_tableau` dernières saisons. `NOTE_CATEGORIES` : texte du §5.3 si `note_statut`, sinon `""`.
  `BLOCS_SPECIFIQUES` : `SPECIFIQUES.get(code)` ou liste vide.
- [ ] **Étape 4 : lancer, les tests passent** : `poetry run pytest tests/test_indicateurs.py -q`.
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : dossier, brique socle et sections par protocole"`.

---

### Tâche 9 : requêtes en lecture seule et chargement

**Fichiers :**
- Créer : `src/reportgenerator/analysis/indicateurs/queries.py`
- Modifier : `src/reportgenerator/analysis/indicateurs/chargement.py`
- Créer : `outils/verif/explain_indicateurs.py` (EXPLAIN de toutes les requêtes, transaction `read_only`)
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Produit (`IndicateursQueries(service_name: str, id_area: int)`, `_fetch` sur le modèle de `PlsocQueries`,
  CTE `{ZONE}` = géométrie de `ref_geo.l_areas` pour `id_area`, SRID 2154 partout) :

| Méthode | Lignes rendues | Sources |
|---|---|---|
| `zone()` | `wkt, surface_ha` | `ref_geo.l_areas` |
| `departements()` | `code, nom, wkt` (simplifié 200 m) | type `DEP` intersectant la zone |
| `localiser(centres: list[tuple[str, float, float]])` | `id_aire, commune, departement, zbiog` | `unnest` des centres ; types `COM`, `DEP`, `ZBIOG` contenant le point |
| `aires_vigienature(protocoles, par_site: bool)` | `id_aire, nom_aire, wkt, x, y, nb_unites` | `pr_vigienature.t_releve` ; aire = `carre_numnat` (ou `site_name` si `par_site`) ; géométrie = `l_carre_suivi.geom` par `numnat = carre_numnat`, sinon enveloppe des points tamponnée de 200 m (`l_carre_suivi` ne couvre pas tous les carrés) ; centre = centroïde des points |
| `releves_vigienature(protocoles, debut, par_site)` | colonnes de la tâche 4 | `t_releve` (`id`, `date_debut`, `observateur`, `point_num`, `passage_mnhn`), `nb_donnees` = nombre de `t_observation` du relevé ; unité = point (`geom_point`) ou transect SHOC (`geom_transect`, sinon `geom_point`) |
| `observations_vigienature(protocoles, annee_min, par_site)` | `id_passage, cd_ref, nom, effectif` | `t_observation.taxon_id` → `cor_taxon_referentiels.id` → `cd_nom` → `taxonomie.taxref` (`cd_ref`, `nom_vern`) ; `effectif = nombre`. Vérifié : 174 410 sur 176 166 observations STOC 2025 retrouvent un `cd_ref` |
| `observateurs_faune_france(ids: list[str])` | `observateur, id_role, nom, email, organisme` | `src_vn_json.observers_json` (`id_universal`, `item->>'email'`, `name`, `surname` ; doublons par `id_universal` : `DISTINCT ON`) → `utilisateurs.t_roles` par `lower(email)` → `bib_organismes.nom_organisme` |
| `aires_monitoring(module)` | `id_aire, nom_aire, wkt, x, y, nb_unites` | `t_base_sites` + `cor_site_module` + `t_site_complements.id_sites_group` (`coalesce(…::text, 'sans_aire')`) + `t_sites_groups` ; géométrie = `t_sites_groups.geom_local`, sinon enveloppe convexe tamponnée des sites |
| `unites_monitoring(module)` | `id_unite, id_aire, nom_unite` | sites du module des aires retenues |
| `passages_monitoring(module, debut, heures_sterf: bool)` | colonnes de la tâche 4 | `gn_monitoring.v_suivi_passage` (`id_base_visit`, `date_passage`, `duree_retenue_min`, `duree_estimee`) ; STERF : durée = `end_hour - start_hour` de `t_visit_complements.data` |
| `observateurs_monitoring(module)` | `id_passage, id_role, nom, email, organisme` | `gn_monitoring.v_suivi_passage_observateur` (`observateur`, `email`, `nom_organisme_brut`) ; la colonne `categorie` de la vue n'est **pas** lue |
| `observations_monitoring(module, annee_min)` | `id_passage, cd_ref, nom, effectif` | `t_observations.cd_nom` → `taxref` ; effectif : `stom` = `nb_0_5 + nb_5_10 + nb_10_15` (sans `nb_hors_proto`), `sterf_ebms` = `effectif`, POP = `count_max` (`t_observation_complements.data`) |
| `etats_pop(vue)` | `id_aire, saison, etat` | `gn_monitoring.<vue>` (`id_sites_group`, `annee`, `etat_aire`) ; `vue` vérifiée dans une liste blanche |
| `anomalies_pop(vue, annee)` | `code, libelle, aire, unite, date` | `gn_monitoring.<vue>` (`code_anomalie`, `libelle`, `aire`, `site` ou `transect`, `date_passage`) ; jamais `email_saisisseur` ni `observateurs` |

Filtre de zone (§5.5) : une aire est retenue si **au moins une** de ses unités intersecte la zone, toutes années
confondues ; elle est alors lue entière. Les modules monitoring sont filtrés par `module_code`, jamais par jeu de
données.

`chargement.charger` appelle ces méthodes selon `regle["source"]` et passe les lignes à `jeu_vigienature` ou
`jeu_monitoring` (`localiser` sur les centres des aires). Il ajoute `charger_stoc_sites(q, regle, saison,
annees_especes) -> Jeu` (code `"stoc_sites"`, `par_site=True`, observations depuis `sites["debut_n2000"]`).

- [ ] **Étape 1 : écrire le test qui échoue** (sans base)

```python
def test_queries_refuse_vue_inconnue():
    q = IndicateursQueries("factice", 1)
    with pytest.raises(ValueError):
        q.etats_pop("v_autre; drop table x")
```

- [ ] **Étape 2 : implémenter `queries.py` et `chargement.py`.** Paramètres psycopg pour toutes les valeurs ; seuls
  les noms de vue passent par une liste blanche.
- [ ] **Étape 3 : écrire `outils/verif/explain_indicateurs.py`**, qui remplace `_fetch` par un `EXPLAIN` en
  `read_only` et appelle chaque méthode pour la région (`2191961`). Lancer :
  `poetry run python outils/verif/explain_indicateurs.py 2191961`. Attendu : un plan par méthode, aucune erreur.
- [ ] **Étape 4 : contrôle des volumes** (script de scratchpad, lecture seule) : `charger` pour chaque protocole sur
  la région, année 2025. Attendu (base au 16/11/2026, §6 de la conception) : STOC-EPS 304 carrés et 216 observateurs
  en 2025, 680 carrés depuis 2001 ; SHOC 130 carrés en saison 2025 ; STERF 248 transects visités, 21 observateurs ;
  STOM 30 sites suivis ; POP Amphibien 24 aires et 118 sites existants, 50 sites visités. Un écart de quelques unités
  dû aux saisies récentes est accepté et noté.
- [ ] **Étape 5 : `pytest` + lint, puis commit** : `git commit -m "Indicateurs : requêtes en lecture seule et chargement des protocoles"`.

---

### Tâche 10 : analyses propres au STOC et au SHOC

**Fichiers :**
- Créer : `src/reportgenerator/analysis/indicateurs/specifiques.py`
- Modifier : `src/reportgenerator/bricks/indicateurs.py` (`SPECIFIQUES["stoc"]`, `SPECIFIQUES["shoc"]`)
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Produit :
  ```python
  def passages_par_aire(jeu, saison, regle) -> dict[str, int]    # libellé -> nombre d'aires
  def part_organisme(jeu, saison, organisme: str) -> tuple[int, int]   # (observateurs, % des observateurs)
  def stoc_sites_n2000(sites: Jeu, eps: Jeu, saison, regle_sites) -> dict
  def autres_stoc_sites(sites: Jeu, saison, motif) -> int
  def part_aires_communes(jeu, autre: Jeu, saison, saison_autre) -> tuple[int, int]   # (aires, %)
  def blocs_stoc(eps: Jeu, sites: Jeu, saison, regle) -> list[tuple]
  def blocs_shoc(shoc: Jeu, stoc: Jeu | None, saison) -> list[tuple]
  ```
  `passages_par_aire` : nombre de périodes principales couvertes par les visites de l'aire. Libellés « 1 passage »,
  « 2 passages », « 2 passages + mars » si la période optionnelle est aussi couverte, « mars seul » si elle est la
  seule, « Hors période » si aucune (`mars` = `regle["libelle_optionnelle"]`). Seules les aires suivies en N sont
  comptées, et les libellés à zéro sont omis.
  `stoc_sites_n2000` : `sites_suivis` (en N), `sites_total`, `donnees_cumul`, `taxons_cumul` (depuis `debut_n2000`)
  et `rangs` : les `nb_especes_rang` premières espèces par effectif cumulé sur les STOC-sites N2000, avec `rang_sites`
  et `rang_eps` (même calcul sur les STOC-EPS, mêmes saisons ; `None` si absente). Blocs STOC : titre « Passages »,
  tableau des passages, phrase OFB, sous-partie « STOC-sites » (texte, tableau des rangs, phrase des autres
  STOC-sites), sous-partie « Tendances MNHN » en `("a_rediger", …)`. Blocs SHOC : carrés aussi suivis en STOC
  (STOC de l'année civile N comparée à la saison SHOC N).

- [ ] **Étape 1 : tests qui échouent** (jeu factice)

```python
REGLE_P = {"periodes": [["05-01", "05-31"], ["06-01", "06-30"]], "periode_optionnelle": ["07-01", "07-31"],
           "libelle_optionnelle": "juillet"}


def test_passages_par_aire():
    # A1 (21/05) et A2 (11/06) : une période chacune ; A4 (01/07) : seulement la période optionnelle
    assert sp.passages_par_aire(jeu_factice(), 2025, REGLE_P) == {"1 passage": 2, "juillet seul": 1}



def test_part_organisme_et_aires_communes():
    j = jeu_factice()
    assert sp.part_organisme(j, 2025, "CEN Savoie") == (1, 33)
    assert sp.part_aires_communes(j, j, 2025, 2025) == (3, 100)


def test_stoc_sites_n2000():
    sites = jeu_factice()
    sites.aires["nom_aire"] = ["STOC N2000 A", "STOC N2000 B", "Autre", "STOC N2000 D"]
    r = sp.stoc_sites_n2000(sites, jeu_factice(), 2025, {"motif_n2000": "STOC N2000%", "nb_especes_rang": 2,
                                                        "debut_n2000": 2024})
    assert (r["sites_suivis"], r["sites_total"], r["taxons_cumul"]) == (3, 3, 3)
    assert [x["nom"] for x in r["rangs"]] == ["Merle noir", "Pinson des arbres"]
    assert sp.autres_stoc_sites(sites, 2024, "STOC N2000%") == 1
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : implémenter**, puis brancher `SPECIFIQUES` : la brique `stoc` charge les STOC-sites par
  `ctx.cached("ind_jeu_stoc_sites", …)` ; la brique `shoc` utilise `jeu_protocole(ctx, "stoc")` (chargé même si le
  STOC n'est pas demandé).
- [ ] **Étape 4 : lancer, les tests passent.**
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : analyses propres au STOC (passages, OFB, STOC-sites) et au SHOC"`.

---

### Tâche 11 : analyses propres au STOM, au STERF et aux POP

**Fichiers :**
- Modifier : `src/reportgenerator/analysis/indicateurs/specifiques.py`
- Modifier : `src/reportgenerator/bricks/indicateurs.py`
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Produit :
  ```python
  def liste_sites_stom(jeu, saison) -> list[dict]        # {date, site, departement, observateurs} (noms triés)
  def classer_sterf(jeu, saison, seuil: int) -> dict[str, str]   # id_aire -> "STERF vrai" | "Site type STERF"
  def tableau_sterf(jeu, saison, seuil) -> list[dict]    # {departement, observateurs, sterf_vrais, sites_type, transects, donnees} + total
  def unites_non_suivies(jeu, saison) -> int             # unités des aires suivies en N sans visite en N
  def tableau_zbiog(jeu, saison, objectifs: dict) -> list[dict]   # {zone, sites, objectif ("à définir" si absent)}
  def tableau_pop(jeu, saison, regle) -> list[dict]      # {departement, aires, unites, completes, nouvelles} + total
  def etats_pop(jeu, saison) -> dict[str, int]           # état -> nombre d'aires (jeu.etats)
  def avancement(jeu, saison, regle) -> tuple[int, int, int]   # (réalisé, objectif, %) ; objectif_sur aires|unites
  def blocs_stom(jeu, saison, regle) -> list[tuple]
  def blocs_sterf(jeu, saison, regle) -> list[tuple]
  def blocs_pop(jeu, saison, regle) -> list[tuple]
  ```
  STERF vrai : aire suivie en N dont `nb_unites >= seuil` (§5.11). `avancement` pour le STERF : sites suivis en N
  sur `objectif` (texte avec `objectif_ideal`). Pour les POP : aires suivies en N (`objectif_sur = "aires"`) ou
  unités existantes des aires suivies (`"unites"`).

- [ ] **Étape 1 : tests qui échouent**

```python
def test_stom_liste():
    l = sp.liste_sites_stom(jeu_factice(), 2025)
    assert l[0] == {"date": "21/05/2025", "site": "A1", "departement": "Savoie",
                    "observateurs": "Observateur 1, Observateur 2"}
    assert len(l) == 3


def test_sterf():
    j = jeu_factice()
    assert sp.classer_sterf(j, 2025, 5) == {"A1": "Site type STERF", "A2": "Site type STERF", "A4": "STERF vrai"}
    tot = sp.tableau_sterf(j, 2025, 5)[-1]
    assert (tot["sterf_vrais"], tot["sites_type"], tot["transects"], tot["donnees"]) == (1, 2, 4, 24)
    assert sp.unites_non_suivies(j, 2025) == 4                       # U4b à U4e
    assert sp.tableau_zbiog(j, 2025, {})[0]["objectif"] == "à définir"


def test_pop():
    j = jeu_factice()
    j.etats = pd.DataFrame({"id_aire": ["A1", "A2"], "saison": [2025, 2025], "etat": ["Complète", "Incomplète"]})
    assert sp.etats_pop(j, 2025) == {"Complète": 1, "Incomplète": 1}
    assert sp.avancement(j, 2025, {"objectif": 50, "objectif_sur": "aires"}) == (3, 50, 6)
    assert sp.avancement(j, 2025, {"objectif": 500, "objectif_sur": "unites"}) == (8, 500, 2)
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : implémenter et brancher `SPECIFIQUES`.**
- [ ] **Étape 4 : lancer, les tests passent.**
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : analyses propres au STOM, au STERF et aux POP"`.

---

### Tâche 12 : brique de synthèse (page de garde, conclusion, annexes)

**Fichiers :**
- Modifier : `src/reportgenerator/bricks/indicateurs.py`
- Tests : `tests/test_indicateurs.py`

**Interfaces :**
- Produit : brique `ind_synthese`, `requires=["ind_socle"]`, `last=True` (passe après les protocoles demandés),
  `provides=["TABLE_CHIFFRES_CLES", "TEXTE_CHIFFRES_CLES", "TEXTE_CONCLUSION", "BLOCS_ANNEXE_ESPECES",
  "BLOCS_ANNEXE_CONTROLE"]`. Elle lit `ctx.results[code].data` pour chaque code de `PROTOCOLES` exécuté et non vide.
  `TABLE_CHIFFRES_CLES` : une ligne par protocole (protocole, saison, aires, observateurs, données, temps avec « (estimé) »,
  écart des aires avec N-1). `TEXTE_CHIFFRES_CLES` inclut le nombre d'observateurs actifs sur plusieurs protocoles.
  `TEXTE_CONCLUSION` : récapitulatif chiffré pré-rédigé. `BLOCS_ANNEXE_ESPECES` : un titre et le tableau complet
  des espèces par protocole. `BLOCS_ANNEXE_CONTROLE` : anomalies de N de chaque jeu (code, libellé, aire, unité, date,
  nom pour `observateur_inconnu`), avec la mention « à supprimer avant envoi ».

- [ ] **Étape 1 : test qui échoue**

```python
def test_synthese_ignore_protocole_vide(tmp_path, monkeypatch):
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2025", {"stom": jeu_factice("stom")})
    ctx.results["ind_socle"] = get_brick("ind_socle").run(ctx)
    for code in ("stom", "sterf"):
        ctx.results[code] = get_brick(code).run(ctx)
    r = get_brick("ind_synthese").run(ctx)
    lignes = r.tables["TABLE_CHIFFRES_CLES"].data
    assert [l["protocole"] for l in lignes] == ["STOM"]
    assert "nan" not in r.texts["TEXTE_CONCLUSION"]
```

- [ ] **Étape 2 : lancer, échec attendu.**
- [ ] **Étape 3 : implémenter.**
- [ ] **Étape 4 : lancer, les tests passent.**
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : synthèse, conclusion et annexes"`.

---

### Tâche 13 : template Word

**Fichiers :**
- Créer : `outils/word/template_indicateurs.py`
- Créer : `src/reportgenerator/dossiers/indicateurs/template.docx` (produit par le script)
- Tests : `tests/test_indicateurs.py`

Le script suit `outils/word/template_plsoc.py` : il part de `src/reportgenerator/dossiers/plsoc/template.docx` (page
de garde, charte, sommaire en champ TOC), vide le contenu et écrit le plan du §5.9 :
1. Page de garde : `{{TITRE_RAPPORT}}`, `{{AREA_NAME}}`, `{{ANNEE}}`, date d'extraction `{{DATE_EXTRACTION}}`,
   `{{TEXTE_CHIFFRES_CLES}}`, `{{TABLE_CHIFFRES_CLES}}`.
2. Contexte : texte fixe repris de « LPO AuRA, 2025, Indicateurs de biodiversité en AURA.docx » (dossier
   `C:\Users\afourneyron\Desktop\projet enquête protocoler`, hors dépôt), `{{TEXTE_ZONE}}`.
3. Une section par protocole, dans l'ordre de `PROTOCOLES`, entre `{{#code}}` et `{{/code}}`, écrite par une **même
   fonction** appelée six fois avec le préfixe et le texte fixe « Protocole » du rapport 2025. Sous-titres : Protocole,
   Participation et chiffres clés, Couverture, Historique et fidélisation, Espèces, Analyses propres au protocole,
   Animation et perspectives (paragraphe surligné en jaune). Les 17 placeholders de `CLES`, chacun seul dans son
   paragraphe pour les tableaux, images et blocs.
4. Conclusion : `{{TEXTE_CONCLUSION}}` puis un paragraphe jaune à rédiger.
5. Annexes : `{{BLOCS_ANNEXE_ESPECES}}`, `{{BLOCS_ANNEXE_CONTROLE}}`.
Les règles métier visibles du lecteur (catégories, temps mesurés ou estimés, STERF vrai, périodes de passage) sont
écrites dans le texte fixe de chaque section.

- [ ] **Étape 1 : test de rendu complet qui échoue** (sur le modèle de `test_rendu_complet_donnees_factices` du
  PLSOC)

```python
def test_rendu_complet_donnees_factices(tmp_path, monkeypatch):
    jeux = {c: jeu_factice(c) for c in PROTOCOLES}
    monkeypatch.setattr(chargement, "charger_stoc_sites", lambda *a, **k: jeu_factice("stoc_sites"))
    ctx = _ctx(tmp_path, monkeypatch, "indicateurs, annee_2025", jeux)
    sortie = tmp_path / "rapport.docx"
    assert run_pipeline(ctx, output_file=sortie) == set()
    texte = "\n".join(p.text for p in Document(sortie).paragraphs)
    assert "{{" not in texte and "nan" not in texte and "None" not in texte


def test_dossier_indicateurs_pret():
    assert check_dossier(load_dossier("indicateurs")).ok
```

- [ ] **Étape 2 : écrire et lancer le script** :
  `poetry run python outils/word/template_indicateurs.py src/reportgenerator/dossiers/plsoc/template.docx src/reportgenerator/dossiers/indicateurs/template.docx`
- [ ] **Étape 3 : lancer les tests, ils passent**, puis
  `poetry run python src/reportgenerator/cli.py check --dossier indicateurs` → aucun placeholder sans source.
- [ ] **Étape 4 : ouvrir le rapport factice dans Word (COM)** avec `outils/verif/word_update.ps1` : pas de « fichier
  endommagé », sommaire mis à jour, aucun placeholder restant.
- [ ] **Étape 5 : commit** : `git commit -m "Indicateurs : template Word et script de construction"`.

---

### Tâche 14 : METHODO, documentation et validation sur la vraie base

**Fichiers :**
- Créer : `src/reportgenerator/dossiers/indicateurs/METHODO.md`
- Modifier : `doc.md` (nouveau dossier, jetons `annee_AAAA`, `par_defaut`)
- Modifier : `docs/indicateurs/conception.md` (§6 : chiffres obtenus)

- [ ] **Étape 1 : écrire `METHODO.md`** : déclenchement et jetons, sources par protocole, modèle commun, règle des
  catégories (et écart avec Grafana), comptes recréés à chaque changement de statut (la fidélisation compte des
  comptes ; STOC et SHOC au statut actuel), saisons, périodes et passages attendus, temps (tableau des paramètres),
  STERF vrai, périmètre POP, STOC-sites N2000, zone et rattachement, chiffres de recoupement.
- [ ] **Étape 2 : dry-run région, année 2025** (sortie hors dépôt, données sensibles) :
  `poetry run python outils/dryrun/dryrun_dossier.py "indicateurs, annee_2025" 2191961 0 AuRA_2025 <scratchpad>/aura_2025`
  Attendu : chiffres du tableau du §6, placeholders non remplis : aucun. Reporter les chiffres obtenus dans le §6 et
  expliquer chaque écart.
- [ ] **Étape 3 : dry-run Savoie** :
  `poetry run python outils/dryrun/dryrun_dossier.py "indicateurs, annee_2025" 2236653 0 Savoie_2025 <scratchpad>/savoie_2025`
  Attendu : tableaux par aire (un seul département), environ 25 carrés STOC et 6 SHOC (rapport 2025), sections sans
  aire masquées. Puis `"indicateurs, stoc, annee_2025"` : seule la section STOC reste.
- [ ] **Étape 4 : contrôle visuel** : pages du Word avec `outils/verif/pages_mot.py` / `montage_pages.py`, cartes
  lisibles. Rechercher « @ » dans le texte du rapport : seules les adresses de contact du gabarit peuvent
  apparaître, aucune adresse d'observateur.
- [ ] **Étape 5 : `pytest`, lint, `check --dossier indicateurs`.**
- [ ] **Étape 6 : commit** : `git commit -m "Indicateurs : METHODO, documentation et validation sur la base"`.
