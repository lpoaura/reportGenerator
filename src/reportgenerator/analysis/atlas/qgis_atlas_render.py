from pathlib import Path
import argparse

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsVectorLayer,
    QgsLayoutExporter,
    QgsRectangle,
    QgsLayoutItemMap,
    QgsFeatureRequest
)

QGIS_PREFIX = r"C:\Program Files\QGIS\3_40"

def reload_project(project, project_path):
    print("Sauvegarde du projet...")
    project.write(str(project_path))

    print("Rechargement du projet...")
    project.clear()
    loaded = project.read(str(project_path))
    
    if not loaded:
        raise Exception(f"Impossible de recharger le projet : {project_path}")
    
    print("Projet rechargé avec succès")
    return project

def relink_gpkg_layers(project, gpkg_path):

    print("Relink des couches GPKG Atlas...")

    print(gpkg_path)
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue

        source = layer.source()

        if "|layername=" not in source:
            continue

        layer_name = source.split("|layername=")[1]
        new_source = f"{gpkg_path}|layername={layer_name}"

        print(f"Relink : {layer.name()}")
        print(f"  -> {new_source}")

        layer.setDataSource(
            new_source,
            layer.name(),
            "ogr"
        )

        layer.reload()

def get_area_zone_extent(project,layer_name="atlas_area_zone",feature_name="Périmètres d'étude",name_field="secteur",margin_ratio=0.10,):

    print("Calcul emprise atlas fixe...")
    layers = project.mapLayersByName(layer_name)
    if not layers:
        raise Exception(f"Couche introuvable : {layer_name}")

    layer = layers[0]
    expression = f'"{name_field}" = \'{feature_name}\''
    request = QgsFeatureRequest().setFilterExpression(expression)
    features = list(layer.getFeatures(request))

    if not features:
        raise Exception( f"Feature introuvable : {feature_name}"  )

    feature = features[0]
    geom = feature.geometry()
    if geom is None or geom.isEmpty():
        raise Exception("Géométrie vide")

    extent = QgsRectangle(geom.boundingBox())
    width_margin = extent.width() * margin_ratio
    height_margin = extent.height() * margin_ratio
    extent.setXMinimum(extent.xMinimum() - width_margin)
    extent.setXMaximum(extent.xMaximum() + width_margin)
    extent.setYMinimum(extent.yMinimum() - height_margin)
    extent.setYMaximum(extent.yMaximum() + height_margin)
    print(extent.toString())
    return extent

def apply_extent_to_layout_maps(layout, extent):
    map_count = 0
    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap):
            print(f"Application extent : " f"{item.displayName()}")
            item.zoomToExtent(extent)
            item.invalidateCache()
            item.refresh()
            map_count += 1
            
    print(f"{map_count} cartes mises à jour")

def run_atlas(project_path: Path, output_path: Path, layout_name: str):

    QgsApplication.setPrefixPath(QGIS_PREFIX, True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    gpkg_path = ( Path(project_path).parent / "data" / "atlas.gpkg" )

    print("ATLAS render...")
    print(f"Project path: {project_path}")
    print(f"Output path: {output_path}")

    try:
        # -----------------------------
        # Chargement projet
        # -----------------------------
        project = QgsProject.instance()
        ok = project.read(str(project_path))
        if not ok:
            raise Exception( f"Impossible de charger le projet : {project_path}")
        print("Projet chargé")

        # -----------------------------
        # Relink GPKG
        # -----------------------------

        relink_gpkg_layers(project, gpkg_path)
        reload_project(project, project_path)

        # -----------------------------
        # Layout
        # -----------------------------
        layout_manager = project.layoutManager()
        print("Layouts disponibles :")
        for l in layout_manager.layouts():
            print(f" - {l.name()}")
        layout = layout_manager.layoutByName(layout_name)

        if layout is None:
            raise Exception( f"Layout introuvable : {layout_name}"  )

        print(f"Layout trouvé : {layout.name()}")

        layout = layout_manager.layoutByName(layout_name)

        # -----------------------------
        # Emprise atlas fixe
        # -----------------------------
        fixed_extent = get_area_zone_extent(project,layer_name="atlas_area_zone",feature_name="Périmètres d''étude",name_field="secteur",margin_ratio=0.10)

        # -----------------------------
        # Atlas
        # -----------------------------
        atlas = layout.atlas()
        if not atlas.enabled():
            raise Exception( f"L'atlas n'est pas activé : {layout_name}" )
        print("Atlas activé")
        atlas.updateFeatures()
        feature_count = atlas.count()
        print(f"{feature_count} pages atlas détectées")

        if feature_count == 0:
            raise Exception(
                "Aucune feature atlas détectée"
            )

        # -----------------------------
        # Dossier export
        # -----------------------------
        export_folder = output_path.parent
        export_folder.mkdir( parents=True, exist_ok=True )
        # -----------------------------
        # Rendu atlas
        # -----------------------------
        atlas.beginRender()
        for i in range(feature_count):
            print("-----------------------------------")
            print(f"Page atlas {i+1}/{feature_count}")
            atlas.seekTo(i)

            apply_extent_to_layout_maps(layout, fixed_extent)
            layout.refresh()

            current_feature = atlas.layout().reportContext().feature()

            if current_feature is None or not current_feature.isValid():
                print("Feature atlas vide")
                continue

            # -----------------------------
            # Nom espèce
            # -----------------------------
            try:
                species_name = current_feature["nom_vern"]
            except Exception:
                species_name = f"species_{i+1}"
            print(f"Espèce : {species_name}")
            safe_name = (str(species_name).replace(" ", "_").replace("/", "_")  )
            # -----------------------------
            # Export image
            # -----------------------------
            image_path = ( export_folder / f"{i+1:03d}_{safe_name}.png")
            print(f"Export : {image_path.name}")
            exporter = QgsLayoutExporter(layout)
            settings = QgsLayoutExporter.ImageExportSettings()
            settings.dpi = 150
            result = exporter.exportToImage( str(image_path), settings )
            if result != QgsLayoutExporter.Success:
                print( f"Erreur export pour : {species_name}" )
            else:
                print(f"Export OK : {image_path.name}")
        atlas.endRender()
        print("Atlas terminé")
    finally:
        qgs.exitQgis()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--layout", required=True)
    args = parser.parse_args()

    run_atlas(
        project_path=Path(args.project),
        output_path=Path(args.output),
        layout_name=args.layout,
    )


if __name__ == "__main__":
    main()