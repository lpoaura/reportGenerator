"""Lignes et polygones retenus (transects, placettes) : protocole, couleurs, couches de la carte, tableau et phrase de
méthode du Word. Fonctions pures, testées sans base (tests/test_geometries.py)."""

# sources de protocoles de suivi : libellé de la carte et du tableau, couleur (lignes et contours des polygones)
PROTOCOLES = {
    "MONITORING_STERF_EBMS": ("STERF (papillons de jour)", "#e6550d"),
    "MONITORING_POPREPTILE": ("POPReptile (reptiles)", "#31a354"),
}
AUTRE_SUIVI = "Autre protocole de suivi"
AUTRES = "Autres sources (inventaires, études...)"
PALETTE = ["#756bb1", "#3182bd", "#c51b8a", "#8c6d31", "#17becf", "#bcbd22"]
COULEUR_AUTRES = "#636363"
TYPES = {"ligne": "Transects (lignes)", "polygone": "Placettes et sites (polygones)"}


def protocole(source) -> str:
    """Catégorie de la carte : protocole connu (PROTOCOLES), autre protocole de suivi (source MONITORING_xxx :
    « Suivi xxx »), sinon autres sources."""
    if source in PROTOCOLES:
        return PROTOCOLES[source][0]
    if str(source or "").upper().startswith("MONITORING_"):
        return f"Suivi {source[len('MONITORING_'):].replace('_', ' ')}"
    return AUTRES


def couleurs(libelles) -> dict:
    """Couleur de chaque catégorie : fixe pour les protocoles connus, palette dans l'ordre d'apparition pour les
    autres suivis, gris pour les autres sources."""
    fixes = {lib: c for lib, c in PROTOCOLES.values()}
    out, i = {}, 0
    for lib in dict.fromkeys(libelles):
        if lib in fixes:
            out[lib] = fixes[lib]
        elif lib == AUTRES:
            out[lib] = COULEUR_AUTRES
        else:
            out[lib] = PALETTE[i % len(PALETTE)]
            i += 1
    return out


def _ordre(libelles) -> dict:
    """Ordre de la légende : protocoles connus, autres suivis (alphabétique), autres sources."""
    connus = [lib for lib, _ in PROTOCOLES.values()]

    def cle(lib):
        return (0, connus.index(lib)) if lib in connus else ((2, lib) if lib == AUTRES else (1, lib))
    return {lib: i for i, lib in enumerate(sorted(set(libelles), key=cle), start=1)}


def couches(objets) -> dict:
    """Couches GPKG de la carte : {"transects_lignes": [...], "transects_polygones": [...]}, chaque objet avec son
    protocole, sa couleur et son ordre de légende (catégories construites au rendu sur les données)."""
    libs = [protocole(o["source"]) for o in objets]
    teintes, ordre = couleurs(libs), _ordre(libs)
    out = {"transects_lignes": [], "transects_polygones": []}
    for o, lib in zip(objets, libs):
        cible = "transects_lignes" if o["type_geom"] == "ligne" else "transects_polygones"
        out[cible].append({**o, "protocole": lib, "couleur": teintes[lib], "ordre": ordre[lib]})
    return out


COLONNES_TABLEAU = [("protocole", "Protocole / source"), ("jeu", "Jeu de données"), ("type", "Type"),
                    ("nb_objets", "Objets"), ("nb_donnees", "Données"), ("nb_especes", "Espèces"),
                    ("groupes", "Groupes"), ("annees", "Années")]


def tableau(synthese) -> list[dict]:
    """Lignes du tableau du Word : par protocole (ordre de la légende) puis nombre de données décroissant."""
    libs = [protocole(r["source"]) for r in synthese]
    ordre = _ordre(libs)
    rows = []
    for r, lib in zip(synthese, libs):
        a, b = r.get("premiere_annee"), r.get("derniere_annee")
        jeu = r.get("jeu") or ""
        if lib == AUTRES and r.get("source"):   # même nom de jeu dans plusieurs sources (ex. Observations BDFFH)
            jeu = f"{jeu} ({r['source']})" if jeu else r["source"]
        rows.append({**r, "protocole": lib, "jeu": jeu,
                     "type": "transects" if r["type_geom"] == "ligne" else "placettes",
                     "annees": "" if a is None else (str(a) if a == b else f"{a}-{b}")})
    return sorted(rows, key=lambda r: (ordre[r["protocole"]], -int(r["nb_donnees"] or 0), r["jeu"]))


def _nb(n: int, mot: str) -> str:
    return f"{n} {mot}{'s' if n > 1 else ''}"


def texte_methode(retenues: dict, exclues, etendue_max_m: float) -> str:
    """Phrase de méthode : données sur des lignes / polygones prises en compte à leur point central, données sur une
    emprise trop large écartées. retenues = {"ligne": nb données, "polygone": nb données} ; exclues = lignes de
    SyntheseQueries.geometries_exclues (type_geom, nb_donnees)."""
    km = f"{etendue_max_m / 1000:g} km"
    lignes, polys = int(retenues.get("ligne", 0)), int(retenues.get("polygone", 0))
    nb_exclues = sum(int(r["nb_donnees"]) for r in exclues)
    texte = ("Les données sont localisées par un point, une ligne (transect) ou un polygone (placette, site). "
             f"Les lignes et polygones de moins de {km} d'étendue, issus notamment des protocoles de suivi (STERF, "
             "POPReptile...), sont pris en compte à leur point central")
    if lignes and polys:
        texte += f" : {_nb(lignes + polys, 'donnée')} ({lignes} sur des lignes et {polys} sur des polygones)."
    elif lignes or polys:
        texte += f" : {_nb(lignes + polys, 'donnée')}, sur des {'lignes' if lignes else 'polygones'}."
    else:
        texte += " ; aucune donnée de ce type ici."
    if nb_exclues:
        s, verbe = ("s", "ne peuvent pas être localisées et ne sont pas utilisées") if nb_exclues > 1 else \
            ("", "ne peut pas être localisée et n'est pas utilisée")
        texte += (f" {nb_exclues} donnée{s} rattachée{s} à une emprise plus large (commune, maille de 10 km, site "
                  f"d'étude...) {verbe}.")
    return texte


def emprise(bbox, marge_ratio=0.08, minimum_m=2000) -> list[float]:
    """Emprise de la carte : rectangle englobant élargi (marge proportionnelle, au moins minimum_m)."""
    xmin, ymin, xmax, ymax = bbox
    m = max((xmax - xmin) * marge_ratio, (ymax - ymin) * marge_ratio, minimum_m)
    return [xmin - m, ymin - m, xmax + m, ymax + m]
