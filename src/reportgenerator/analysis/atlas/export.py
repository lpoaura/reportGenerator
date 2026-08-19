from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkb, wkt


def _to_geom(value):
    if value is None or value == "":
        return None

    # déjà une géométrie shapely
    if hasattr(value, "geom_type"):
        return value

    # mémoire / bytes / wkb binaire
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return wkb.loads(bytes(value))
        except Exception:
            pass

    if isinstance(value, str):
        # WKB hex (EWKB), format par défaut renvoyé par psycopg pour une colonne geometry
        try:
            return wkb.loads(value, hex=True)
        except Exception:
            pass

        # WKT, au cas où
        try:
            return wkt.loads(value)
        except Exception:
            raise ValueError(f"Impossible de convertir la géométrie: {value!r}")

    return value


def _rows_to_gdf(rows, geom_col, crs="EPSG:2154"):
    df = pd.DataFrame.from_records(rows)

    if geom_col not in df.columns:
        raise ValueError(f"Colonne géométrique absente: {geom_col}")

    df["geometry"] = df[geom_col].apply(_to_geom)
    df = df.drop(columns=[geom_col])

    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=crs)
    return gdf


# atlas/export.py

def export_atlas_gpkg(data, gpkg_path, layer_name, geom_col="geometry", crs="EPSG:2154"):

    gpkg_path = Path(gpkg_path)
    gpkg_path.parent.mkdir(parents=True, exist_ok=True)

    gdf = _rows_to_gdf(data, geom_col=geom_col, crs=crs)

    # si le fichier gpkg existe déjà (couches précédentes), on ajoute
    # la nouvelle couche dedans, sinon on crée le fichier
    mode = "a" if gpkg_path.exists() else "w"

    gdf.to_file(gpkg_path, layer=layer_name, driver="GPKG", mode=mode)

    print(f"Couche '{layer_name}' exportée dans : {gpkg_path}")
    return gpkg_path