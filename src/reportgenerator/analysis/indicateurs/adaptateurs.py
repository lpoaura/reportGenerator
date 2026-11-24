"""Adaptateurs : lignes lues en base (listes de dicts, voir queries.py) -> modèle commun `Jeu` (conception §5.2).

Fonctions pures, testées sans base. La catégorie des observateurs est calculée ici, une fois, avec la règle de
selections.py ; l'email sert à cette règle et ne sort jamais de l'adaptateur.
"""

import pandas as pd

from reportgenerator.analysis.indicateurs.modele import COLONNES, Jeu, table_vide, verifier
from reportgenerator.analysis.indicateurs.selections import categorie_observateur, completer_durees, saison


def _table(nom: str, lignes) -> pd.DataFrame:
    lignes = list(lignes)
    if not lignes:
        return table_vide(nom)
    df = pd.DataFrame(lignes)
    for c in COLONNES[nom]:
        if c not in df.columns:
            df[c] = None
    return df[COLONNES[nom]]


def _aires(aires, localisation) -> pd.DataFrame:
    df = pd.DataFrame(list(aires), columns=["id_aire", "nom_aire", "wkt", "x", "y", "nb_unites"])
    df["id_aire"] = df["id_aire"].astype(str)
    loc = pd.DataFrame(list(localisation), columns=["id_aire", "commune", "departement", "zbiog"])
    loc["id_aire"] = loc["id_aire"].astype(str)
    df = df.merge(loc, on="id_aire", how="left")
    return df[COLONNES["aires"]]


def _passages(lignes, regle) -> pd.DataFrame:
    p = pd.DataFrame(list(lignes))
    if p.empty:
        return table_vide("passages")
    p["date"] = pd.to_datetime(p["date"]).dt.date
    p["saison"] = [saison(d, regle["saison"]) for d in p["date"]]
    p["id_aire"] = p["id_aire"].astype(str)
    p["id_unite"] = p["id_unite"].astype(str)
    for c in ("duree_min", "duree_estimee"):
        if c not in p.columns:
            p[c] = None if c == "duree_min" else False
    p["duree_estimee"] = p["duree_estimee"].fillna(False).astype(bool)
    p = p[p["saison"] >= int(regle["debut_serie"])].sort_values(["date", "id_passage"], kind="stable")
    return p.reset_index(drop=True)   # ordre chronologique : annexe de contrôle déterministe


def _observations(lignes, ids) -> pd.DataFrame:
    df = _table("observations", lignes)
    return df[df["id_passage"].isin(ids)].reset_index(drop=True)


def _avec_saison(anomalie: dict, mode: str) -> dict:
    """Saison de l'anomalie, selon la règle du protocole (SHOC : décembre compte pour l'année suivante)."""
    d = anomalie.get("date")
    return {"nom": None, **anomalie, "saison": saison(d, mode) if d is not None and not pd.isna(d) else None}


def jeu_vigienature(code, aires, releves, observations, observateurs, localisation, regle) -> Jeu:
    """Faune-France (pr_vigienature) : un passage = un relevé d'un point (STOC) ou d'un transect (SHOC)."""
    p = _passages(releves, regle)
    if p.empty:   # aucun relevé du protocole dans la zone
        return verifier(Jeu(code, _aires(aires, localisation), *(table_vide(n) for n in
                                                                 ("unites", "passages", "observateurs",
                                                                  "observations"))))
    debut_obs = int(regle.get("debut_observateurs", regle["debut_serie"]))
    connus = {str(o["observateur"]): o for o in observateurs}
    noms_aires = {str(a["id_aire"]): a["nom_aire"] for a in aires}
    lignes_obs, anomalies, inconnus = [], [], set()
    for r in p.itertuples():
        if r.observateur is None or pd.isna(r.observateur) or r.saison < debut_obs:
            continue
        o = connus.get(str(r.observateur))
        if o and o.get("id_role") is not None:
            cat, org = categorie_observateur(o.get("organisme"), o.get("email"))
            lignes_obs.append({"id_passage": r.id_passage, "id_observateur": f"role:{o['id_role']}",
                               "nom": o.get("nom"), "organisme": org, "categorie": cat})
            continue
        lignes_obs.append({"id_passage": r.id_passage, "id_observateur": f"ff:{r.observateur}",
                           "nom": (o or {}).get("nom"), "organisme": None, "categorie": "Non renseigné"})
        if (r.observateur, r.saison) not in inconnus:   # une ligne par observateur et par saison (annexe de N)
            inconnus.add((r.observateur, r.saison))
            anomalies.append(_avec_saison({
                "code": "observateur_inconnu", "libelle": "Observateur Faune-France sans compte GeoNature",
                "aire": noms_aires.get(r.id_aire), "unite": r.nom_unite, "date": r.date, "nom": (o or {}).get("nom")},
                regle["saison"]))
    for r in p.itertuples():
        if r.passage_mnhn is not None and not pd.isna(r.passage_mnhn) and int(r.passage_mnhn) not in (1, 2, 3):
            anomalies.append(_avec_saison({
                "code": "passage_mnhn", "libelle": f"Numéro de passage MNHN {int(r.passage_mnhn)} (attendu : 1 à 3)",
                "aire": noms_aires.get(r.id_aire), "unite": r.nom_unite, "date": r.date}, regle["saison"]))
    unites = _table("unites", p[["id_unite", "id_aire", "nom_unite"]].drop_duplicates().to_dict("records"))
    jeu = Jeu(code, _aires(aires, localisation), unites, p[COLONNES["passages"]], _table("observateurs", lignes_obs),
              _observations(observations, set(p["id_passage"])), anomalies=anomalies)
    return verifier(jeu)


def jeu_monitoring(code, aires, unites, passages, observateurs, observations, localisation, regle,
                   etats=(), anomalies=()) -> Jeu:
    """Modules gn_monitoring : aire = groupe de sites (« sans_aire » si le site n'a pas de groupe), unité = site,
    passage = visite. Les durées manquantes sont complétées (selections.completer_durees)."""
    p = _passages(passages, regle)
    if not p.empty:
        p = completer_durees(p, regle.get("duree_defaut_min"))
    ids = set(p["id_passage"])
    obs = []
    for o in observateurs:
        if o["id_passage"] in ids:
            cat, org = categorie_observateur(o.get("organisme"), o.get("email"))
            obs.append({"id_passage": o["id_passage"], "id_observateur": f"role:{o['id_role']}",
                        "nom": o.get("nom"), "organisme": org, "categorie": cat})
    u = _table("unites", unites)
    u["id_aire"] = u["id_aire"].astype(str)
    u["id_unite"] = u["id_unite"].astype(str)
    liste = [_avec_saison({"code": "site_sans_aire", "libelle": "Site rattaché à aucune aire (groupe de sites)",
                           "aire": None, "unite": r.nom_unite, "date": None}, regle["saison"])
             for r in u[u["id_aire"] == "sans_aire"].itertuples()]
    liste += [_avec_saison(dict(a), regle["saison"]) for a in anomalies]
    e = _table("etats", etats) if etats else None
    if e is not None:
        e["id_aire"] = e["id_aire"].astype(str)
    jeu = Jeu(code, _aires(aires, localisation), u, p[COLONNES["passages"]], _table("observateurs", obs),
              _observations(observations, ids), etats=e, anomalies=liste)
    return verifier(jeu)
