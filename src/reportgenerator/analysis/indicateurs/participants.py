"""Participants d'une catégorie d'observateurs (bénévoles dans le rapport Indicateurs ; organismes tiers ou salariés
pour un futur rapport « participants ») : renouvellement, ancienneté, engagement, travail réalisé, réseau entre
protocoles. Fonctions pures sur le modèle commun `Jeu` ; comptes agrégés uniquement (jamais de nom ni d'email).
"""

from collections import Counter

from reportgenerator.analysis.indicateurs.communes import (aires_suivies, categorie_aires, categorie_passages,
                                                           observateurs_de, pourcent, releves, temps_heures)
from reportgenerator.analysis.indicateurs.selections import categorie_observateur

STATUTS = ("fidèle", "revenant", "nouveau", "parti")            # ordre des graphiques et tableaux
TRANCHES_ANCIENNETE = (("1 saison", 1, 1), ("2 à 4 saisons", 2, 4), ("5 à 9 saisons", 5, 9),
                       ("10 saisons et plus", 10, None))
TRANCHES_ENGAGEMENT = ("1", "2", "3+")
NON_LOCALISE = "Non localisé"


# ------------------------------------------------------------------------------------------------------ présences
def _de_categorie(jeu, categorie):
    """Lignes observateurs de la catégorie, avec la saison et l'aire du relevé."""
    o = jeu.observateurs[jeu.observateurs["categorie"] == categorie]
    return o.merge(jeu.passages[["id_passage", "saison", "id_aire"]], on="id_passage")


def _presences(jeu, categorie) -> dict:
    """Compte -> saisons où il a fait au moins un relevé."""
    o = _de_categorie(jeu, categorie)
    return {k: set(int(s) for s in v) for k, v in o.groupby("id_observateur")["saison"]}


def participants(jeu, saison, categorie) -> set:
    """Comptes de la catégorie ayant fait au moins un relevé de la saison."""
    return {o for o, s in _presences(jeu, categorie).items() if saison in s}


def statuts(jeu, saison, categorie) -> dict:
    """Statut de chaque compte en N : nouveau (première saison = N), fidèle (N et N-1), revenant (N, pas N-1, avant),
    parti (N-1, pas N)."""
    out = {}
    for o, s in _presences(jeu, categorie).items():
        if saison in s:
            out[o] = "fidèle" if saison - 1 in s else ("revenant" if min(s) < saison else "nouveau")
        elif saison - 1 in s:
            out[o] = "parti"
    return out


def serie_statuts(jeu, debut, saison, categorie) -> list[dict]:
    lignes = []
    for s in range(debut, saison + 1):
        compte = Counter(statuts(jeu, s, categorie).values())
        lignes.append({"saison": s, **{st: compte[st] for st in STATUTS}})
    return lignes


def _departements(jeu, saison, categorie) -> dict:
    """Compte -> départements des aires où il a fait un relevé de la saison."""
    o = _de_categorie(jeu, categorie)
    o = o[o["saison"] == saison].merge(jeu.aires[["id_aire", "departement"]], on="id_aire", how="left")
    o["departement"] = o["departement"].fillna(NON_LOCALISE)
    return {k: set(v) for k, v in o.groupby("id_observateur")["departement"]}


def statuts_par_departement(jeu, saison, categorie) -> list[dict]:
    """Statuts par département (un compte compte dans chaque département où il a fait un relevé ; les partis dans
    ceux de N-1). total = présents en N."""
    dep_n, dep_n1 = _departements(jeu, saison, categorie), _departements(jeu, saison - 1, categorie)
    par_dep: dict[str, Counter] = {}
    for o, st in statuts(jeu, saison, categorie).items():
        for d in (dep_n1 if st == "parti" else dep_n).get(o, ()):
            par_dep.setdefault(d, Counter())[st] += 1
    lignes = [{"departement": d, **{st: c[st] for st in STATUTS}, "total": sum(c[st] for st in STATUTS[:3])}
              for d, c in par_dep.items()]
    return sorted(lignes, key=lambda x: (-x["total"], x["departement"]))


# -------------------------------------------------------------------------------------- ancienneté, engagement
def anciennete(jeu, saison, categorie) -> dict:
    """Participants de N par nombre de saisons distinctes de participation jusqu'à N."""
    compte = dict.fromkeys((t[0] for t in TRANCHES_ANCIENNETE), 0)
    for s in _presences(jeu, categorie).values():
        if saison not in s:
            continue
        n = sum(1 for x in s if x <= saison)
        for lib, bas, haut in TRANCHES_ANCIENNETE:
            if n >= bas and (haut is None or n <= haut):
                compte[lib] += 1
    return compte


def engagement(jeu, saison, categorie) -> dict:
    """Participants de N par nombre d'aires suivies dans la saison : 1, 2, 3 et plus."""
    o = _de_categorie(jeu, categorie)
    n = o[o["saison"] == saison].groupby("id_observateur")["id_aire"].nunique()
    compte = dict.fromkeys(TRANCHES_ENGAGEMENT, 0)
    for v in n:
        compte["3+" if v >= 3 else str(int(v))] += 1
    return compte


def travail(jeu, saison, categorie, temps: dict) -> dict:
    """Travail réalisé par la catégorie en N, avec les mêmes règles que la répartition par catégorie : aires
    (catégorie de l'aire), relevés et données (catégorie du relevé), heures."""
    p = releves(jeu, saison)
    n_obs = int(observateurs_de(jeu, p["id_passage"])["id_observateur"].nunique())
    n_part = len(participants(jeu, saison, categorie))
    aires = Counter(categorie_aires(jeu, saison).values())[categorie]
    cat_p = categorie_passages(jeu)
    sel = p[p["id_passage"].map(cat_p) == categorie]
    t = temps_heures(jeu, saison, temps)
    return {"participants": n_part, "part_observateurs": pourcent(n_part, n_obs),
            "aires": aires, "part_aires": pourcent(aires, len(aires_suivies(jeu, saison))),
            "releves": len(sel), "donnees": int(sel["nb_donnees"].fillna(0).sum()),
            "heures": t["par_categorie"].get(categorie, 0), "heures_estimees": t["estime"]}


# ---------------------------------------------------------------------------------------- aires jamais visitées
def aires_jamais_visitees(jeu, createurs: list[dict]) -> list[dict]:
    """Aires de la zone sans aucune visite jusqu'à N (modules GeoNature), par catégorie du créateur du site le plus
    ancien de l'aire et année de création. Créateur inconnu : « Non renseigné ». Ni nom ni email en sortie."""
    visitees = set(jeu.passages["id_aire"])
    par_aire = {c["id_aire"]: c for c in createurs}
    compte = Counter()
    for a in jeu.aires["id_aire"]:
        if a in visitees:
            continue
        c = par_aire.get(a)
        cat = categorie_observateur(c["organisme"], c["email"], bool(c["connu"]))[0] if c else "Non renseigné"
        annee = c.get("annee_creation") if c else None
        compte[(cat, None if annee is None else int(annee))] += 1
    lignes = [{"categorie": cat, "annee_creation": annee, "aires": n} for (cat, annee), n in compte.items()]
    return sorted(lignes, key=lambda x: (x["annee_creation"] is None, x["annee_creation"] or 0, x["categorie"]))
