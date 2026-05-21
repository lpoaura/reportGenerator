from analysis.cartography.export import export_raw_gpkg, copy_qgis_project
from analysis.cartography.qgis_launcher import launch_qgis_render
from pathlib import Path

def run_cartography(synthese_queries, output_dirs, area_name):

    # 1. DATA
    raw = synthese_queries.get_raw_geodata()
    gpkg_path = output_dirs["data"] / "toutes_les_donnees.gpkg"
    export_raw_gpkg(raw, gpkg_path, "donnees_brutes")

    # 2. QGIS PROJECT
    BASE_DIR = Path(__file__).resolve().parents[2]
    template_path = BASE_DIR / "templates" / "projet_modele.qgs"
    project_path = copy_qgis_project(
        template_path=template_path,
        output_path=output_dirs["root"]
    )

    # 3. RENDER QGIS
    launch_qgis_render(
    project_path=template_path,
    output_dir=output_dirs["maps"]
    )