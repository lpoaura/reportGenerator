"""Analyses communes à tous les protocoles (conception §5.7), en fonctions pures sur le modèle commun `Jeu`.

Vocabulaire : un relevé est une ligne de `passages` (une unité visitée une fois) ; une visite est un couple
(aire, date) ; une aire est suivie en N si elle a au moins un relevé de la saison N.
"""

from collections import Counter

import pandas as pd

from reportgenerator.analysis.indicateurs.selections import (CATEGORIES, categorie_prioritaire, completer_durees,
                                                             dans_periode, numero_periode)


# ------------------------------------------------------------------------------------------------------- outils
def releves(jeu, saison) -> pd.DataFrame:
    return jeu.passages[jeu.passages["saison"] == saison]


def aires_suivies(jeu, saison) -> set:
    return set(releves(jeu, saison)["id_aire"])


def observateurs_de(jeu, ids) -> pd.DataFrame:
    return jeu.observateurs[jeu.observateurs["id_passage"].isin(set(ids))]


def premieres_saisons(jeu) -> dict:
    return jeu.passages.groupby("id_aire")["saison"].min().to_dict()


def _rang(categorie: str) -> int:
    return CATEGORIES.index(categorie) if categorie in CATEGORIES else len(CATEGORIES)


# --------------------------------------------------------------------------------------------------- catégories
def categorie_passages(jeu) -> dict:
    """Catégorie de chaque relevé : la plus prioritaire de ses observateurs ; sans observateur, « Non renseigné »."""
    cats = jeu.observateurs.groupby("id_passage")["categorie"].apply(list).to_dict()
    return {i: categorie_prioritaire(cats.get(i, [])) for i in jeu.passages["id_passage"]}


def categorie_aires(jeu, saison) -> dict:
    """Catégorie de chaque aire suivie en N : celle de l'observateur qui y a fait le plus de relevés ; égalité :
    Salarié LPO > Organisme tiers > Bénévole. Aire sans observateur : « Non renseigné »."""
    p = releves(jeu, saison)
    o = observateurs_de(jeu, p["id_passage"]).merge(p[["id_passage", "id_aire"]], on="id_passage")
    out = {}
    for aire in p["id_aire"].unique():
        lignes = o[o["id_aire"] == aire]
        if lignes.empty:
            out[aire] = "Non renseigné"
            continue
        compte = lignes.groupby(["id_observateur", "categorie"]).size().reset_index(name="n")
        compte["rang"] = compte["categorie"].map(_rang)
        out[aire] = compte.sort_values(["n", "rang", "id_observateur"], ascending=[False, True, True]).iloc[0][
            "categorie"]
    return out


def _categorie_visites(p: pd.DataFrame, cat_passages: dict) -> dict:
    cats = p.assign(c=p["id_passage"].map(cat_passages)).groupby(["id_aire", "date"])["c"].apply(list)
    return {k: categorie_prioritaire(v) for k, v in cats.items()}


# ---------------------------------------------------------------------------------------------------------- temps
def temps_heures(jeu, saison, temps: dict) -> dict:
    """Temps de travail de la saison : terrain (mesuré = somme des durées, ou forfait par aire / par visite) +
    complément forfaitaire (préparation, trajet, saisie). La part par catégorie suit la catégorie du relevé (durée
    mesurée), de la visite (forfait par visite) ou de l'aire (forfait par aire)."""
    p = releves(jeu, saison)
    if p.empty:
        return {"heures": 0, "estime": False, "par_categorie": {}}
    cat_p = categorie_passages(jeu)
    cat_aires = categorie_aires(jeu, saison)
    cat_visites = _categorie_visites(p, cat_p)
    par_cat, estime = Counter(), False

    def forfait(heures, unite):
        cats = cat_aires.values() if unite == "aire" else cat_visites.values()
        for c in cats:
            par_cat[c] += float(heures)

    if temps.get("terrain_h") == "mesure":
        p = completer_durees(p)
        estime = bool(p["duree_estimee"].any() or p["duree_min"].isna().any())
        for r in p.itertuples():
            if not pd.isna(r.duree_min):
                par_cat[cat_p[r.id_passage]] += r.duree_min / 60
    else:
        forfait(temps.get("terrain_h") or 0, temps.get("unite_terrain", "aire"))
        estime = True
    if temps.get("complement_h"):
        forfait(temps["complement_h"], temps.get("unite_complement", "aire"))
        estime = True
    par_categorie = {c: round(par_cat[c], 1) for c in sorted(par_cat, key=_rang) if par_cat[c]}
    return {"heures": round(sum(par_cat.values()), 1), "estime": estime, "par_categorie": par_categorie}


# ------------------------------------------------------------------------------------------------------- chiffres
def chiffres(jeu, saison, temps: dict) -> dict:
    p = releves(jeu, saison)
    obs = jeu.observations[jeu.observations["id_passage"].isin(set(p["id_passage"]))]
    t = temps_heures(jeu, saison, temps)
    return {
        "aires": int(p["id_aire"].nunique()),
        "unites": int(p["id_unite"].nunique()),
        "visites": int(len(p[["id_aire", "date"]].drop_duplicates())),
        "releves": int(len(p)),
        "observateurs": int(observateurs_de(jeu, p["id_passage"])["id_observateur"].nunique()),
        "donnees": int(p["nb_donnees"].fillna(0).sum()),
        "especes": int(obs["cd_ref"].nunique()) if not obs.empty else None,
        "heures": t["heures"],
        "heures_estimees": t["estime"],
    }


def par_categorie(jeu, saison, temps: dict) -> list[dict]:
    """Une ligne par catégorie présente : aires (catégorie de l'aire), observateurs (comptes), données (catégorie du
    relevé), heures. Les sommes des aires et des données redonnent le total."""
    p = releves(jeu, saison)
    cat_p = categorie_passages(jeu)
    aires = Counter(categorie_aires(jeu, saison).values())
    obs = observateurs_de(jeu, p["id_passage"]).drop_duplicates("id_observateur")
    observateurs = Counter(obs["categorie"])
    donnees = Counter()
    for r in p.itertuples():
        donnees[cat_p[r.id_passage]] += 0 if pd.isna(r.nb_donnees) else int(r.nb_donnees)
    heures = temps_heures(jeu, saison, temps)["par_categorie"]
    lignes = []
    for c in CATEGORIES:
        ligne = {"categorie": c, "aires": aires[c], "observateurs": observateurs[c], "donnees": donnees[c],
                 "heures": heures.get(c, 0)}
        if any(ligne[k] for k in ("aires", "observateurs", "donnees", "heures")):
            lignes.append(ligne)
    return lignes


# ----------------------------------------------------------------------------------------------------- couverture
def statut_aires(jeu, saison) -> dict:
    """Toutes les aires de la zone : « nouvelle » (première saison = N), « suivie », ou « non suivie » en N."""
    suivies, premieres = aires_suivies(jeu, saison), premieres_saisons(jeu)
    return {a: ("nouvelle" if premieres.get(a) == saison else "suivie") if a in suivies else "non suivie"
            for a in jeu.aires["id_aire"]}


def completude(jeu, saison, regle) -> dict:
    """État des aires suivies en N : état fourni par la base (POP), sinon « complète » si chaque période attendue
    contient une visite (`periodes`), ou si chaque unité visitée a `passages_par_unite` dates dans `periode_unite`."""
    p = releves(jeu, saison)
    aires = list(dict.fromkeys(p["id_aire"]))
    if jeu.etats is not None:
        e = jeu.etats[jeu.etats["saison"] == saison].set_index("id_aire")["etat"].to_dict()
        return {a: e.get(a, "non renseigné") for a in aires}
    out = {}
    if regle.get("periodes"):
        for a in aires:
            couvertes = {numero_periode(d, regle["periodes"]) for d in p[p["id_aire"] == a]["date"]}
            out[a] = "complète" if couvertes >= set(range(1, len(regle["periodes"]) + 1)) else "incomplète"
    elif regle.get("passages_par_unite"):
        periode, n = regle.get("periode_unite", ["01-01", "12-31"]), int(regle["passages_par_unite"])
        dans = p[[dans_periode(d, periode) for d in p["date"]]]
        dates = dans.groupby("id_unite")["date"].nunique()
        for a in aires:
            unites = p[p["id_aire"] == a]["id_unite"].unique()
            out[a] = "complète" if all(dates.get(u, 0) >= n for u in unites) else "incomplète"
    return out


def _ligne(nom, p, jeu, nouvelles, completes, cle):
    return {cle: nom, "aires": int(p["id_aire"].nunique()), "unites": int(p["id_unite"].nunique()),
            "visites": int(len(p[["id_aire", "date"]].drop_duplicates())),
            "observateurs": int(observateurs_de(jeu, p["id_passage"])["id_observateur"].nunique()),
            "donnees": int(p["nb_donnees"].fillna(0).sum()),
            "nouvelles": len(set(p["id_aire"]) & nouvelles), "completes": len(set(p["id_aire"]) & completes)}


def couverture(jeu, saison, regle, par: str) -> list[dict]:
    """Aires suivies en N par département ou par zone biogéographique (avec une ligne de total), ou liste des aires."""
    p = releves(jeu, saison)
    statut = statut_aires(jeu, saison)
    etat = completude(jeu, saison, regle)
    aires = jeu.aires.set_index("id_aire")
    if par == "aire":
        lignes = []
        for a, pa in p.groupby("id_aire"):
            info = aires.loc[a] if a in aires.index else {}
            lignes.append({"aire": info.get("nom_aire", a), "commune": info.get("commune"),
                           "departement": info.get("departement"), "zbiog": info.get("zbiog"),
                           "unites": int(pa["id_unite"].nunique()),
                           "visites": int(len(pa[["id_aire", "date"]].drop_duplicates())),
                           "observateurs": int(observateurs_de(jeu, pa["id_passage"])["id_observateur"].nunique()),
                           "completude": etat.get(a, "")})
        return sorted(lignes, key=lambda r: str(r["aire"]))
    nouvelles = {a for a, s in statut.items() if s == "nouvelle"}
    completes = {a for a, e in etat.items() if e.lower().startswith("complète")}
    groupes = p.assign(groupe=p["id_aire"].map(aires[par]).fillna("Non renseigné"))
    lignes = [_ligne(g, pg, jeu, nouvelles, completes, par) for g, pg in groupes.groupby("groupe")]
    lignes.sort(key=lambda r: r[par])
    if lignes:
        lignes.append({**_ligne("Total", p, jeu, nouvelles, completes, par), "total": True})
    return lignes
