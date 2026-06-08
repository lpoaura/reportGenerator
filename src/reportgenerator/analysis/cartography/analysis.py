from pathlib import Path

from reportgenerator.analysis.cartography.export import (copy_qgis_project,
                                                         export_gpkg)
from reportgenerator.analysis.cartography.qgis_launcher import \
    launch_qgis_render


def run_cartography(synthese_queries, output_dirs, area_name):

    # 1. DATA
    raw = synthese_queries.get_raw_geodata()
    area_zone_rows = synthese_queries.get_area_zone()
    knowledge_status_grid = synthese_queries.get_knowledge_status_grid()

    gpkg_path = f"{output_dirs['data']}"
    export_gpkg(
        raw,
        gpkg_path,
        layer_name="donnees_brutes",
        geom_col="the_geom_local",
        crs="EPSG:2154",
    )

    export_gpkg(
        area_zone_rows,
        gpkg_path,
        layer_name="zone_etude",
        geom_col="geom",
        crs="EPSG:2154",
    )

    export_gpkg(
        knowledge_status_grid,
        gpkg_path,
        layer_name="statut_connaissance",
        geom_col="geom_maille",
        crs="EPSG:2154",
    )

    # 2. QGIS PROJECT
    BASE_DIR = Path(__file__).resolve().parents[2]
    template_path = BASE_DIR / "templates" / "projet_modele.qgs"
    output_path = f"{output_dirs['root']}/projet_{area_name}.qgs"

    project_path = copy_qgis_project(
        template_path=template_path, output_path=output_path
    )

    # 3. RENDER QGIS
    launch_qgis_render(project_path=output_path, output_dir=output_dirs["maps"])
