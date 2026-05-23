import shutil
import pandas as pd
import geopandas as gpd
from shapely import wkt
from pathlib import Path


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