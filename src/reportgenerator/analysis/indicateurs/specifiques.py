"""Analyses propres à un protocole (conception §5.8), en fonctions pures sur le modèle commun. Chaque protocole a une
fonction blocs_<protocole> qui rend une suite de blocs pour inserer_blocs (analysis/plsoc/word.py) :
("titre", niveau, texte) | ("texte", texte) | ("a_rediger", texte) | ("tableau", lignes, colonnes)
| ("image", chemin) | ("legende", texte) | ("annexe", titre, lignes, colonnes).

Avec un dossier `sortie`, les tableaux sont remplacés par des graphiques dans la section et repris en annexe (bloc
« annexe », extrait par la brique) ; sans `sortie` (tests), les tableaux restent dans la section."""

from pathlib import Path

from reportgenerator.analysis.indicateurs import figures as fig
from reportgenerator.analysis.indicateurs.communes import (aires_suivies, completude, observateurs_de, pourcent,
                                                           releves, statut_aires)
from reportgenerator.analysis.indicateurs.selections import dans_periode, est_stoc_site_n2000, numero_periode
from reportgenerator.analysis.indicateurs.textes import nombre, pluriel

TITRE = 3   # niveau des titres des analyses propres (sous « Analyses propres au protocole »)


def _visuel(lignes, colonnes, sortie: Path | None, nom: str, dessin, legende: str, titre_annexe: str) -> list:
    """Tableau dans la section (sans sortie), ou graphique + légende dans la section et tableau en annexe."""
    if sortie is None:
        return [("tableau", lignes, colonnes)]
    return [("image", dessin(sortie / f"{nom}.png")), ("legende", legende), ("annexe", titre_annexe, lignes, colonnes)]


# ---------------------------------------------------------------------------------------------------- communs
def part_organisme(jeu, saison, organisme: str) -> tuple[int, int]:
    """(observateurs de cet organisme en N, % des observateurs de N)."""
    o = observateurs_de(jeu, releves(jeu, saison)["id_passage"]).drop_duplicates("id_observateur")
    n = int((o["organisme"] == organisme).sum())
    return n, pourcent(n, len(o))


def part_aires_communes(jeu, autre, saison, saison_autre) -> tuple[int, int]:
    """(aires de jeu suivies en N aussi suivies dans autre, % des aires de jeu)."""
    a, b = aires_suivies(jeu, saison), aires_suivies(autre, saison_autre)
    return len(a & b), pourcent(len(a & b), len(a))


# --------------------------------------------------------------------------------------------------------- STOC
def passages_par_aire(jeu, saison, regle) -> dict[str, int]:
    """Aires suivies en N selon le nombre de périodes de passage couvertes (« 2 passages + mars »…)."""
    p = releves(jeu, saison)
    lib = regle.get("libelle_optionnelle", "période optionnelle")
    compte = {}
    for _, pa in p.groupby("id_aire"):
        dates = set(pa["date"])
        k = len({numero_periode(d, regle["periodes"]) for d in dates} - {None})
        opt = bool(regle.get("periode_optionnelle")) and any(dans_periode(d, regle["periode_optionnelle"])
                                                             for d in dates)
        if k:
            libelle = f"{k} passage{'s' if k > 1 else ''}" + (f" + {lib}" if opt else "")
        else:
            libelle = f"{lib} seul" if opt else "Hors période"
        compte[libelle] = compte.get(libelle, 0) + 1
    return dict(sorted(compte.items()))


def _effectifs(jeu, ids) -> dict:
    o = jeu.observations[jeu.observations["id_passage"].isin(set(ids))]
    return o.groupby(["cd_ref", "nom"])["effectif"].sum().sort_values(ascending=False).to_dict()


def stoc_sites_n2000(sites, eps, saison, regle_sites) -> dict:
    """STOC-sites Natura 2000 de la LPO (nom reconnu par motif_n2000) depuis debut_n2000 : sites suivis, données et
    taxons cumulés, rang des espèces (effectif cumulé) comparé à leur rang en STOC-EPS sur les mêmes saisons."""
    motif, debut = regle_sites["motif_n2000"], int(regle_sites["debut_n2000"])
    n2000 = {a for a, nom in zip(sites.aires["id_aire"], sites.aires["nom_aire"]) if est_stoc_site_n2000(nom, motif)}
    p = sites.passages[(sites.passages["saison"].between(debut, saison)) & sites.passages["id_aire"].isin(n2000)]
    eff_sites = _effectifs(sites, p["id_passage"])
    pe = eps.passages[eps.passages["saison"].between(debut, saison)]
    rang_eps = {cd: i for i, (cd, _) in enumerate(_effectifs(eps, pe["id_passage"]), 1)}
    rangs = [{"rang_sites": i, "nom": nom, "effectif": nombre(int(e)), "effectif_n": int(e),
              "rang_eps": rang_eps.get(cd, "—")}
             for i, ((cd, nom), e) in enumerate(list(eff_sites.items())[:int(regle_sites.get("nb_especes_rang", 40))],
                                                1)]
    return {"sites_suivis": len(aires_suivies(sites, saison) & n2000), "sites_total": int(p["id_aire"].nunique()),
            "donnees_cumul": int(p["nb_donnees"].fillna(0).sum()), "taxons_cumul": len({cd for cd, _ in eff_sites}),
            "debut": debut, "rangs": rangs}


def autres_stoc_sites(sites, saison, motif) -> int:
    """STOC-sites suivis en N hors STOC-sites Natura 2000 de la LPO (autres STOC-sites, ONF, réserves)."""
    noms = dict(zip(sites.aires["id_aire"], sites.aires["nom_aire"]))
    return sum(1 for a in aires_suivies(sites, saison) if not est_stoc_site_n2000(noms.get(a), motif))


def blocs_stoc(eps, sites, saison, regle, sortie: Path | None = None) -> list[tuple]:
    passages = passages_par_aire(eps, saison, regle)
    b = [("titre", TITRE, "Passages réalisés"),
         ("texte", "Carrés suivis selon le nombre de périodes de passage couvertes (1er avril - 8 mai, 9 mai - "
                   "15 juin ; le passage de mars est facultatif)."),
         *_visuel([{"passages": k, "aires": v} for k, v in passages.items()], [("passages", "Passages"),
                                                                               ("aires", "Carrés")],
                  sortie, "stoc_passages", lambda p: fig.chart_barres(passages, p, "Carrés"),
                  f"Figure : carrés STOC-EPS selon le nombre de passages réalisés en {saison}.",
                  "Passages réalisés")]
    n_ofb, pct_ofb = part_organisme(eps, saison, "OFB")
    if n_ofb:
        b.append(("texte", f"{nombre(n_ofb)} observateurs de l'OFB ont participé en {saison} ({pct_ofb} % des "
                           "observateurs)."))
    if sites is not None and not sites.passages.empty:
        r = stoc_sites_n2000(sites, eps, saison, regle["sites"])
        autres = autres_stoc_sites(sites, saison, regle["sites"]["motif_n2000"])
        if r["sites_total"] or autres:
            b.append(("titre", TITRE, "STOC-sites"))
        if r["sites_total"]:
            b += [("texte", f"STOC-sites Natura 2000 de la LPO : {nombre(r['sites_suivis'])} sites suivis en {saison}. "
                            f"Depuis {r['debut']}, {nombre(r['sites_total'])} sites ont produit "
                            f"{nombre(r['donnees_cumul'])} données pour {nombre(r['taxons_cumul'])} taxons. Rang des "
                            "espèces sur ces sites (effectif cumulé) comparé à leur rang en STOC-EPS sur les mêmes "
                            "saisons :")]
            premieres = {f"{x['nom']} (rang STOC-EPS : {x['rang_eps']})": x["effectif_n"] for x in r["rangs"][:20]}
            b += _visuel(r["rangs"], [("rang_sites", "Rang STOC-sites"), ("nom", "Espèce"),
                                      ("effectif", "Effectif cumulé"), ("rang_eps", "Rang STOC-EPS")],
                         sortie, "stoc_sites_rangs",
                         lambda p: fig.chart_barres(premieres, p, f"Effectif cumulé depuis {r['debut']}"),
                         "Figure : 20 premières espèces des STOC-sites Natura 2000 (effectif cumulé) et leur rang en "
                         "STOC-EPS (tableau complet en annexe).", "STOC-sites Natura 2000 : rang des espèces")
        if autres:
            b.append(("texte", f"{nombre(autres)} autres STOC-sites ont été suivis en {saison} (sites hors Natura "
                               "2000, ONF, réserves naturelles)."))
    b += [("titre", TITRE, "Tendances MNHN"),
          ("a_rediger", "À compléter : figures et tableaux de tendances fournis par le MNHN (cortèges, espèces à court "
                        "et long terme).")]
    return b


# --------------------------------------------------------------------------------------------------------- SHOC
def blocs_shoc(shoc, stoc, saison) -> list[tuple]:
    if stoc is None or stoc.passages.empty or not aires_suivies(shoc, saison):
        return []
    n, pct = part_aires_communes(shoc, stoc, saison, saison)
    return [("titre", TITRE, "Carrés également suivis en STOC-EPS"),
            ("texte", f"{nombre(n)} {pluriel('carré', n)} SHOC de l'hiver {saison - 1}-{saison} ({pct} %) "
                      f"{'ont' if n > 1 else 'a'} aussi été suivi{'s' if n > 1 else ''} en STOC-EPS au printemps "
                      f"{saison}.")]


# --------------------------------------------------------------------------------------------------------- outils
def _info_aires(jeu) -> dict:
    return jeu.aires.set_index("id_aire").to_dict("index")


def _par_groupe(jeu, saison, cle, ligne) -> list[dict]:
    """Une ligne par valeur de `cle` (departement, zbiog) des aires suivies en N, puis le total."""
    p = releves(jeu, saison)
    info = _info_aires(jeu)
    groupes = {}
    for a in p["id_aire"].unique():
        groupes.setdefault(info.get(a, {}).get(cle) or "Non renseigné", set()).add(a)
    lignes = [{cle: g, **ligne(p[p["id_aire"].isin(aires)], aires)} for g, aires in sorted(groupes.items())]
    if lignes:
        lignes.append({cle: "Total", **ligne(p, set(p["id_aire"])), "total": True})
    return lignes


# --------------------------------------------------------------------------------------------------------- STOM
def liste_sites_stom(jeu, saison) -> list[dict]:
    """Sites suivis en N : date du passage, site, département, observateurs (noms, comme dans le rapport)."""
    p = releves(jeu, saison)
    info = _info_aires(jeu)
    noms = jeu.observateurs.groupby("id_passage")["nom"].apply(lambda s: {n for n in s if n}).to_dict()
    lignes = []
    for a, pa in p.groupby("id_aire"):
        obs = set().union(*(noms.get(i, set()) for i in pa["id_passage"]))
        premiere = min(pa["date"])
        lignes.append((premiere, {"date": premiere.strftime("%d/%m/%Y"), "site": info.get(a, {}).get("nom_aire", a),
                                  "departement": info.get(a, {}).get("departement"),
                                  "observateurs": ", ".join(sorted(obs))}))
    return [ligne for _, ligne in sorted(lignes, key=lambda x: (x[0], str(x[1]["site"])))]


def blocs_stom(jeu, saison, regle) -> list[tuple]:
    return [("titre", TITRE, "Sites suivis"),
            ("tableau", liste_sites_stom(jeu, saison), [("date", "Date"), ("site", "Site"),
                                                        ("departement", "Département"),
                                                        ("observateurs", "Observateurs")]),
            ("texte", "Le détail par massif n'est pas encore disponible (pas de couche des massifs en base) : les "
                      "tableaux de couverture sont présentés par département.")]


# -------------------------------------------------------------------------------------------------------- STERF
def classer_sterf(jeu, saison, seuil: int) -> dict[str, str]:
    """Site suivi en N : « STERF vrai » s'il compte au moins `seuil` transects, sinon « Site type STERF »."""
    info = _info_aires(jeu)
    return {a: "STERF vrai" if int(info.get(a, {}).get("nb_unites") or 0) >= seuil else "Site type STERF"
            for a in sorted(aires_suivies(jeu, saison))}


def tableau_sterf(jeu, saison, seuil) -> list[dict]:
    classes = classer_sterf(jeu, saison, seuil)

    def ligne(p, aires):
        return {"observateurs": int(observateurs_de(jeu, p["id_passage"])["id_observateur"].nunique()),
                "sterf_vrais": sum(1 for a in aires if classes[a] == "STERF vrai"),
                "sites_type": sum(1 for a in aires if classes[a] == "Site type STERF"),
                "transects": int(p["id_unite"].nunique()), "donnees": int(p["nb_donnees"].fillna(0).sum())}
    return _par_groupe(jeu, saison, "departement", ligne)


def unites_non_suivies(jeu, saison) -> int:
    """Unités des aires suivies en N sans visite en N."""
    p = releves(jeu, saison)
    u = jeu.unites[jeu.unites["id_aire"].isin(set(p["id_aire"]))]
    return int((~u["id_unite"].isin(set(p["id_unite"]))).sum())


def tableau_zbiog(jeu, saison, objectifs: dict) -> list[dict]:
    """Sites suivis en N par zone biogéographique, avec l'objectif de la zone (dossier.toml)."""
    suivies = aires_suivies(jeu, saison)
    zones = sorted(set(jeu.aires["zbiog"].dropna()) | set(objectifs))
    par_zone = jeu.aires.groupby("zbiog")["id_aire"].apply(set).to_dict()
    return [{"zone": z, "sites": len(par_zone.get(z, set()) & suivies), "objectif": objectifs.get(z, "à définir")}
            for z in zones]


def avancement(jeu, saison, regle) -> tuple[int, int, int]:
    """(réalisé, objectif, %) : aires suivies en N, ou unités existantes des aires suivies (objectif_sur)."""
    suivies = aires_suivies(jeu, saison)
    if regle.get("objectif_sur") == "unites":
        fait = int(jeu.unites["id_aire"].isin(suivies).sum())
    else:
        fait = len(suivies)
    objectif = int(regle.get("objectif") or 0)
    return fait, objectif, pourcent(fait, objectif)


def blocs_sterf(jeu, saison, regle, sortie: Path | None = None) -> list[tuple]:
    seuil = int(regle.get("seuil_sterf_vrai", 5))
    classes = classer_sterf(jeu, saison, seuil)
    vrais = sum(1 for c in classes.values() if c == "STERF vrai")
    fait, objectif, pct = avancement(jeu, saison, regle)
    par_dep = tableau_sterf(jeu, saison, seuil)
    zones = tableau_zbiog(jeu, saison, regle.get("objectifs_zbiog") or {})
    return [("titre", TITRE, "STERF vrais et sites type STERF"),
            ("texte", f"En {saison}, {nombre(vrais)} sites respectent le protocole national (STERF vrais : au moins "
                      f"{seuil} transects, suivis cette année) et {nombre(len(classes) - vrais)} sont des sites type "
                      f"STERF. {nombre(unites_non_suivies(jeu, saison))} transects des sites suivis n'ont pas été "
                      "parcourus cette année."),
            *_visuel(par_dep, [("departement", "Département"), ("observateurs", "Observateurs"),
                               ("sterf_vrais", "STERF vrais"), ("sites_type", "Sites type STERF"),
                               ("transects", "Transects"), ("donnees", "Données")],
                     sortie, "sterf_vrais_departements",
                     lambda p: fig.chart_groupes(par_dep, "departement", p, [
                         ("sterf_vrais", "STERF vrais", fig.BLEU), ("sites_type", "Sites type STERF", fig.ORANGE)],
                         "Sites suivis"),
                     f"Figure : STERF vrais et sites type STERF suivis en {saison}, par département.",
                     "STERF vrais et sites type STERF par département"),
            ("titre", TITRE, "Objectifs de déploiement"),
            ("texte", f"{nombre(fait)} sites suivis pour un objectif de {nombre(objectif)} ({pct} %), "
                      f"{nombre(regle.get('objectif_ideal'))} idéalement."),
            *(_visuel(zones, [("zone", "Zone biogéographique"), ("sites", "Sites suivis"), ("objectif", "Objectif")],
                      sortie, "sterf_objectifs", lambda p: fig.chart_objectifs(zones, p, "Sites suivis"),
                      f"Figure : sites STERF suivis en {saison} par zone biogéographique et objectif de la zone "
                      "(trait noir, quand il est défini).", "Sites STERF par zone biogéographique et objectifs")
              # sans objectif chiffré, le graphique répéterait celui de la couverture par zone biogéographique
              if sortie is None or any(isinstance(z["objectif"], (int, float)) for z in zones) else
              [("texte", "Objectifs par zone biogéographique : à renseigner (paramètre objectifs_zbiog du "
                         "dossier.toml) ; répartition des sites par zone : voir la couverture.")])]


# ---------------------------------------------------------------------------------------------------------- POP
def etats_pop(jeu, saison) -> dict[str, int]:
    """Nombre d'aires de la zone par état (vue POP de la base) en N."""
    if jeu.etats is None:
        return {}
    e = jeu.etats[(jeu.etats["saison"] == saison) & jeu.etats["id_aire"].isin(set(jeu.aires["id_aire"]))]
    return {k: int(v) for k, v in e["etat"].value_counts().sort_index().items()}


def tableau_pop(jeu, saison, regle) -> list[dict]:
    etat, statut = completude(jeu, saison, regle), statut_aires(jeu, saison)

    def ligne(p, aires):
        return {"aires": len(aires), "unites": int(p["id_unite"].nunique()),
                "completes": sum(1 for a in aires if str(etat.get(a, "")).lower().startswith("complète")),
                "nouvelles": sum(1 for a in aires if statut.get(a) == "nouvelle")}
    return _par_groupe(jeu, saison, "departement", ligne)


def blocs_pop(jeu, saison, regle, sortie: Path | None = None) -> list[tuple]:
    unite = regle.get("unite", "site")
    fait, objectif, pct = avancement(jeu, saison, regle)
    sur = pluriel(unite) if regle.get("objectif_sur") == "unites" else "aires"
    etats = etats_pop(jeu, saison)
    par_dep = [{**r, "autres": r["aires"] - r["completes"]} for r in tableau_pop(jeu, saison, regle)]
    code = regle.get("module", "pop")   # nom des fichiers des graphiques
    return [("titre", TITRE, "État des aires"),
            *_visuel([{"etat": k, "aires": v} for k, v in etats.items()], [("etat", "État de l'aire"),
                                                                           ("aires", "Aires")],
                     sortie, f"{code}_etats", lambda p: fig.chart_barres(etats, p, "Aires"),
                     f"Figure : aires selon leur état en {saison} (règles de la base POP).", "État des aires"),
            ("titre", TITRE, "Suivi par département"),
            *_visuel(par_dep, [("departement", "Département"), ("aires", "Aires suivies"),
                               ("unites", f"{pluriel(unite)} visités"), ("completes", "Suivis complets"),
                               ("nouvelles", "Nouvelles aires")],
                     sortie, f"{code}_departements",
                     lambda p: fig.chart_groupes(par_dep, "departement", p, [
                         ("completes", "Suivi complet", fig.BLEU), ("autres", "Suivi incomplet", fig.BLEU_CLAIR)],
                         "Aires suivies"),
                     f"Figure : aires suivies en {saison} par département, selon que le suivi est complet ou non.",
                     "Aires suivies par département"),
            ("titre", TITRE, "Objectif"),
            ("texte", f"{nombre(fait)} {sur} pour un objectif de {nombre(objectif)} ({pct} %).")]
