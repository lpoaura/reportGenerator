"""Couches des cartes QGIS du rapport Indicateurs (une mise en page par protocole dans le projet du dossier).

Fonction pure : elle prépare les lignes (géométries shapely, Lambert 93) exportées en GPKG par la brique ind_cartes.
Les filtres par protocole et la symbologie sont dans le projet QGIS, modifiable dans QGIS.
"""

from shapely import wkt

from reportgenerator.analysis.indicateurs.communes import aires_suivies, categorie_aires, statut_aires


def _geom(texte):
    """WKT -> géométrie ; None ou NaN (aire sans contour : sites « sans aire ») -> None."""
    return wkt.loads(texte) if isinstance(texte, str) and texte else None


def couches_cartes(jeux: dict, saisons: dict, zone: dict, departements: list[dict], zbiog: list[dict]) -> dict:
    """ind_zone, ind_departements, ind_zbiog (contours) et ind_aires (protocole ; statut en N : suivie, nouvelle,
    non suivie ; catégorie de l'aire en N ; reconduction : suivie en N, ou abandon = suivie en N-1 seulement)."""
    aires = []
    for code, jeu in jeux.items():
        n = saisons[code]
        statuts, categories = statut_aires(jeu, n), categorie_aires(jeu, n)
        suivies_n, suivies_n1 = aires_suivies(jeu, n), aires_suivies(jeu, n - 1)
        for a in jeu.aires.itertuples():
            if _geom(a.wkt) is None:
                continue
            # reconduction : « suivie » en N, « abandon » si suivie en N-1 mais pas en N (aire à reprendre)
            reconduction = "suivie" if a.id_aire in suivies_n else "abandon" if a.id_aire in suivies_n1 else None
            aires.append({"protocole": code, "id_aire": a.id_aire, "nom_aire": a.nom_aire,
                          "statut": statuts.get(a.id_aire, "non suivie"), "categorie": categories.get(a.id_aire),
                          "reconduction": reconduction, "departement": a.departement, "zbiog": a.zbiog,
                          "geom": _geom(a.wkt)})
    return {
        "ind_zone": [{"nom": zone.get("nom", ""), "geom": _geom(zone["wkt"])}],
        "ind_departements": [{"nom": d["nom"], "geom": _geom(d["wkt"])} for d in departements],
        "ind_zbiog": [{"nom": z["nom"], "geom": _geom(z["wkt"])} for z in zbiog],
        "ind_aires": aires,
    }


def emprises(aires: list[dict], minimum_m: float = 20000, marge: float = 0.05) -> dict:
    """Emprise des cartes de chaque protocole : étendue de ses aires (ind_aires), élargie de `marge` de chaque côté,
    puis portée à `minimum_m` au moins dans chaque dimension (centrée) pour ne pas zoomer à l'échelle d'une commune.
    Même emprise pour les trois cartes d'un protocole (comparables d'une page à l'autre)."""
    bornes: dict[str, list] = {}
    for a in aires:
        if a.get("geom") is None:
            continue
        x0, y0, x1, y1 = a["geom"].bounds
        b = bornes.setdefault(a["protocole"], [x0, y0, x1, y1])
        b[:] = [min(b[0], x0), min(b[1], y0), max(b[2], x1), max(b[3], y1)]
    out = {}
    for code, (x0, y0, x1, y1) in bornes.items():
        dx, dy = (x1 - x0) * marge, (y1 - y0) * marge
        x0, y0, x1, y1 = x0 - dx, y0 - dy, x1 + dx, y1 + dy
        if x1 - x0 < minimum_m:
            cx = (x0 + x1) / 2
            x0, x1 = cx - minimum_m / 2, cx + minimum_m / 2
        if y1 - y0 < minimum_m:
            cy = (y0 + y1) / 2
            y0, y1 = cy - minimum_m / 2, cy + minimum_m / 2
        out[code] = (x0, y0, x1, y1)
    return out
