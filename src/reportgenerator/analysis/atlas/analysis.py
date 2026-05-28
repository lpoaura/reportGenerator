from pathlib import Path
from analysis.atlas.qgis_launcher import launch_qgis_atlas_render
from analysis.cartography.export import export_gpkg, copy_qgis_project


def run_atlas(synthese_queries, output_dirs, area_name, run_render=True):
    print("Lancement du module atlas...")

    # 1. Données
    grid_rows = synthese_queries.get_atlas_species_grid()
    summary_rows = synthese_queries.get_atlas_species_summary()
    area_zone_rows = synthese_queries.get_atlas_area_zone()

    # 2. Export GPKG
    atlas_gpkg_path = output_dirs["data"] / "atlas.gpkg"
    
    export_gpkg(
        data=grid_rows,
        gpkg_path=atlas_gpkg_path,
        layer_name="atlas_species_grid",
        geom_col="emprise_presence"
    )

    export_gpkg(
        data=summary_rows,
        gpkg_path=atlas_gpkg_path,
        layer_name="atlas_species_summary",
        geom_col="geom_maille"
    )

    export_gpkg(
        data=area_zone_rows,
        gpkg_path=atlas_gpkg_path,
        layer_name="atlas_area_zone",
        geom_col="geom"
    )

    # 3. Copie du projet QGIS atlas
    template_path = ( Path(__file__).resolve().parents[2] / "templates"/ "atlas_modele.qgs" )
    print("Template QGIS Atlas:", template_path)
    project_path = output_dirs["root"] / "atlas_modele.qgs"
    copy_qgis_project(
        template_path=template_path,
        output_path=project_path,
    )

    # 4. Rendu atlas QGIS
    atlas_pdf_path = output_dirs["atlas"] / "atlas.pdf"

    if run_render:
        launch_qgis_atlas_render(
            project_path=project_path,
            output_path=atlas_pdf_path,
            layout_name="atlas_species",
        )

    return {
        "gpkg": atlas_gpkg_path,
        "qgis_project": project_path,
        "atlas_pdf": atlas_pdf_path,
    }