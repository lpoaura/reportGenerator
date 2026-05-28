import shutil
import pandas as pd
import geopandas as gpd
from shapely import wkt, wkb
from pathlib import Path
from shapely.geometry.base import BaseGeometry


## export des données brutes pour cartographie QGIS
def export_raw_gpkg(rows, output_path, layer_name):

    print('Export des données brutes pour cartographie QGIS...')
    df = pd.DataFrame.from_records(rows)
    df["geometry"] = df["the_geom_local"].apply(
        lambda x: wkt.loads(x)
    )
    df = df.drop(columns=["the_geom_local"])
    gdf = gpd.GeoDataFrame(
        df,
        geometry="geometry",
        crs="EPSG:2154"
    )

   # output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(
        output_path,
        layer=layer_name,
        driver="GPKG"
    )

## copie du projet QGIS template dans le dossier de sortie pour que l'utilisateur puisse ouvrir le projet avec les données exportées
def copy_qgis_project(template_path: Path, output_path: Path):

    template_path = Path(template_path)
    output_path = Path(output_path)

    print("Template QGIS:", template_path)
    print("Output QGIS:", output_path)

    if not template_path.exists():
        raise FileNotFoundError(f"Template introuvable: {template_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy(template_path, output_path)

    # attachments
    template_path = Path(template_path)

    attachments = template_path.with_suffix("")  # enlève .qgs
    attachments = attachments.parent / f"{template_path.stem}_attachments"
  
    print("Attachments source:", attachments)

    if attachments.is_dir():
        dest = output_path.parent / f"{output_path.stem}_attachments"
        print("Copy attachments ->", dest)
        shutil.copytree(attachments, dest, dirs_exist_ok=True)
    else:
        print("No attachments folder found (ignored)")

    return output_path


def parse_geometry(value):

    if value is None:
        return None

    # déjà géométrie shapely
    if hasattr(value, "geom_type"):
        return value

    # WKB
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return wkb.loads(bytes(value))
        except Exception:
            pass

    # WKT
    if isinstance(value, str):
        try:
            return wkt.loads(value)
        except Exception:
            pass

    return value

def export_gpkg(
    data,
    gpkg_path,
    layer_name,
    geom_col="geometry",
    crs="EPSG:2154"
):

    print(f"\n--- Export GPKG : {layer_name} ---")

    if not data:
        raise ValueError(
            f"Aucune donnée fournie pour : {layer_name}"
        )

    # dataframe
    df = pd.DataFrame.from_records(data)

    print("Colonnes disponibles :")
    print(list(df.columns))

    if geom_col not in df.columns:
        raise ValueError(
            f"Colonne géométrique absente : {geom_col}"
        )

    print(f"Géométrie utilisée : {geom_col}")

    # récupération premier objet non null
    first_geom = df[geom_col].dropna().iloc[0]

    print("Exemple géométrie :")
    print(str(first_geom)[:120])

    # ---------------------------------------------------
    # CAS 1 : GEOMETRIE SHAPELY
    # ---------------------------------------------------

    if isinstance(first_geom, BaseGeometry):

        print("Type géométrie détecté : shapely")

        df["geometry"] = df[geom_col]

    # ---------------------------------------------------
    # CAS 2 : WKT
    # ---------------------------------------------------

    elif isinstance(first_geom, str) and (
        first_geom.startswith("POINT")
        or first_geom.startswith("POLYGON")
        or first_geom.startswith("MULTIPOLYGON")
        or first_geom.startswith("LINESTRING")
        or first_geom.startswith("MULTILINESTRING")
    ):

        print("Type géométrie détecté : WKT")

        df["geometry"] = df[geom_col].apply(
            lambda x: wkt.loads(x) if x else None
        )

    # ---------------------------------------------------
    # CAS 3 : WKB HEX
    # ---------------------------------------------------

    elif isinstance(first_geom, str):

        print("Type géométrie détecté : WKB HEX")

        df["geometry"] = df[geom_col].apply(
            lambda x: wkb.loads(x, hex=True) if x else None
        )

    else:

        raise ValueError(
            f"Type géométrie non supporté : {type(first_geom)}"
        )

    # suppression ancienne géométrie
    if geom_col != "geometry":

        df = df.drop(columns=[geom_col])

    # création geodataframe
    gdf = gpd.GeoDataFrame(
        df,
        geometry="geometry",
        crs=crs
    )

    # création dossier
    gpkg_path = Path(gpkg_path)

    gpkg_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    print(f"Export vers : {gpkg_path}")
    print(f"Nombre d'entités : {len(gdf)}")

    # export
    gdf.to_file(
        gpkg_path,
        layer=layer_name,
        driver="GPKG"
    )

    print(f"Couche exportée : {layer_name}")