import pandas as pd
import geopandas as gpd
from shapely import wkt, wkb
from pathlib import Path

def _to_geom(value):
    if value is None or value == "":
        return None

    # déjà une géométrie shapely
    if hasattr(value, "geom_type"):
        return value

    # mémoire / bytes / wkb
    if isinstance(value, (bytes, bytearray, memoryview)):
        try:
            return wkb.loads(bytes(value))
        except Exception:
            pass

    # texte wkt
    if isinstance(value, str):
        try:
            return wkt.loads(value)
        except Exception:
            pass

    return value


def _rows_to_gdf(rows, geom_col, crs="EPSG:2154"):
    df = pd.DataFrame.from_records(rows)

    if geom_col not in df.columns:
        raise ValueError(f"Colonne géométrique absente: {geom_col}")

    df["geometry"] = df[geom_col].apply(_to_geom)
    df = df.drop(columns=[geom_col])

    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs=crs)
    return gdf


def export_atlas_gpkg(grid_rows, summary_rows, output_path: Path, crs="EPSG:2154"):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # couche maille
    grid_gdf = _rows_to_gdf(
        grid_rows,
        geom_col="geom_maille",
        crs=crs,
    )
    grid_gdf.to_file(
        output_path,
        layer="atlas_species_grid",
        driver="GPKG",
    )

    # couche espèce (1 ligne par espèce)
    summary_gdf = _rows_to_gdf(
        summary_rows,
        geom_col="emprise_presence",
        crs=crs,
    )
    summary_gdf.to_file(
        output_path,
        layer="atlas_species_summary",
        driver="GPKG",
    )

    print(f"Atlas GPKG exporté : {output_path}")
    return output_path