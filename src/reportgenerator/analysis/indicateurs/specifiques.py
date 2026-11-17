"""Analyses propres à un protocole (conception §5.8), en fonctions pures sur le modèle commun. Chaque protocole a une
fonction blocs_<protocole> qui rend une suite de blocs pour inserer_blocs (analysis/plsoc/word.py) :
("titre", niveau, texte) | ("texte", texte) | ("a_rediger", texte) | ("tableau", lignes, colonnes)."""

from reportgenerator.analysis.indicateurs.communes import (aires_suivies, observateurs_de, pourcent, releves)
from reportgenerator.analysis.indicateurs.selections import dans_periode, est_stoc_site_n2000, numero_periode
from reportgenerator.analysis.indicateurs.textes import nombre, pluriel

TITRE = 3   # niveau des titres des analyses propres (sous « Analyses propres au protocole »)


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
    rangs = [{"rang_sites": i, "nom": nom, "effectif": nombre(int(e)), "rang_eps": rang_eps.get(cd, "—")}
             for i, ((cd, nom), e) in enumerate(list(eff_sites.items())[:int(regle_sites.get("nb_especes_rang", 40))],
                                                1)]
    return {"sites_suivis": len(aires_suivies(sites, saison) & n2000), "sites_total": int(p["id_aire"].nunique()),
            "donnees_cumul": int(p["nb_donnees"].fillna(0).sum()), "taxons_cumul": len({cd for cd, _ in eff_sites}),
            "debut": debut, "rangs": rangs}


def autres_stoc_sites(sites, saison, motif) -> int:
    """STOC-sites suivis en N hors STOC-sites Natura 2000 de la LPO (autres STOC-sites, ONF, réserves)."""
    noms = dict(zip(sites.aires["id_aire"], sites.aires["nom_aire"]))
    return sum(1 for a in aires_suivies(sites, saison) if not est_stoc_site_n2000(noms.get(a), motif))


def blocs_stoc(eps, sites, saison, regle) -> list[tuple]:
    b = [("titre", TITRE, "Passages réalisés"),
         ("texte", "Carrés suivis selon le nombre de périodes de passage couvertes (1er avril - 8 mai, 9 mai - "
                   "15 juin ; le passage de mars est facultatif)."),
         ("tableau", [{"passages": k, "aires": v} for k, v in passages_par_aire(eps, saison, regle).items()],
          [("passages", "Passages"), ("aires", "Carrés")])]
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
                            "saisons :"),
                  ("tableau", r["rangs"], [("rang_sites", "Rang STOC-sites"), ("nom", "Espèce"),
                                           ("effectif", "Effectif cumulé"), ("rang_eps", "Rang STOC-EPS")])]
        if autres:
            b.append(("texte", f"{nombre(autres)} autres STOC-sites ont été suivis en {saison} (sites hors Natura "
                               "2000, ONF, réserves naturelles)."))
    b += [("titre", TITRE, "Tendances MNHN"),
          ("a_rediger", "À compléter : figures et tableaux de tendances fournis par le MNHN (cortèges, espèces à court "
                        "et long terme).")]
    return b


# --------------------------------------------------------------------------------------------------------- SHOC
def blocs_shoc(shoc, stoc, saison) -> list[tuple]:
    if stoc is None or stoc.passages.empty:
        return []
    n, pct = part_aires_communes(shoc, stoc, saison, saison)
    return [("titre", TITRE, "Carrés également suivis en STOC-EPS"),
            ("texte", f"{nombre(n)} {pluriel('carré', n)} SHOC de l'hiver {saison - 1}-{saison} ({pct} %) "
                      f"{'ont' if n > 1 else 'a'} aussi été suivi{'s' if n > 1 else ''} en STOC-EPS au printemps "
                      f"{saison}.")]
