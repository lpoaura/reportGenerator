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


def load_render_config(path) -> dict:
    config = dict(DEFAULT_RENDER_CONFIG)
    if path:
        config.update(json.loads(Path(path).read_text(encoding="utf-8")))
    return config
