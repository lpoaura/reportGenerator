"""
Fonctions sans dépendance QGIS utilisées par les scripts de rendu
(testables hors de l'environnement QGIS).
"""

import json
from pathlib import Path

DEFAULT_RENDER_CONFIG = {
    # groupes toujours visibles, en plus du groupe portant le nom de la mise en page
    "visible_groups": ["FDC"],
    # couche (nom dans le projet) dont l'emprise cadre toutes les cartes
    "extent_layer": "observations_brutes",
    "extent_margin_ratio": 0.1,
    # décalage vertical de l'emprise, en proportion de sa hauteur
    "extent_offset_y_ratio": 0.0,
    # élargissement de l'emprise (mètres) pour certaines mises en page
    "layout_buffers_m": {},
    "dpi": None,
}


def relink_gpkg_source(source: str, data_dir) -> str | None:
    """Réécrit la source OGR d'une couche vers <data_dir>/<layername>.gpkg
    en conservant les autres options (ex. |subset=...).

    Retourne None si la source n'est pas une couche GPKG nommée.
    """
    parts = source.split("|")
    options = parts[1:]
    layer_name = next((o.split("=", 1)[1] for o in options if o.startswith("layername=")), None)
    if layer_name is None:
        return None
    others = [o for o in options if not o.startswith("layername=")]
    new_source = f"{Path(data_dir).as_posix()}/{layer_name}.gpkg|layername={layer_name}"
    return "|".join([new_source, *others])


# Catégories construites au rendu (une couleur par valeur, ex. une par espèce) : palette qualitative lisible sur le
# fond topographique ; au-delà de 12 valeurs, les couleurs reviennent avec une autre forme de symbole.
PALETTE_CATEGORIES = ["#e6194b", "#4363d8", "#3cb44b", "#f58231", "#911eb4", "#42d4f4",
                      "#f032e6", "#9a6324", "#000075", "#bfef45", "#800000", "#ffe119"]
FORMES_CATEGORIES = ["circle", "square", "triangle", "diamond"]


def categories_dynamiques(valeurs) -> list[tuple]:
    """valeurs : [(valeur, ordre)] lues dans les entités (ordre : rang de légende, None = à la fin).
    -> [(valeur, couleur, forme)] : une catégorie par valeur distincte, triées par ordre puis par valeur."""
    ordres: dict = {}
    for valeur, ordre in valeurs:
        if valeur is None:
            continue
        rang = ordre if ordre is not None else float("inf")
        ordres[valeur] = min(ordres.get(valeur, rang), rang)
    triees = sorted(ordres, key=lambda v: (ordres[v], str(v)))
    n = len(PALETTE_CATEGORIES)
    return [(v, PALETTE_CATEGORIES[i % n], FORMES_CATEGORIES[(i // n) % len(FORMES_CATEGORIES)])
            for i, v in enumerate(triees)]


def filtre_page(champ: str, cle) -> str:
    """Filtre (subset) d'une couche sur la page d'une mise en page modèle : "cle" = 'nocturnes_hiboux'."""
    return f"\"{champ}\" = '{str(cle).replace(chr(39), chr(39) * 2)}'"


def load_render_config(path) -> dict:
    config = dict(DEFAULT_RENDER_CONFIG)
    if path:
        config.update(json.loads(Path(path).read_text(encoding="utf-8")))
    return config
