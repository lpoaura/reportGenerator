# qgis_render.py

import argparse
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsLayoutExporter,
    QgsVectorLayer,
    QgsRectangle,
    QgsLayoutItemMap
)


def zoom_layout_maps_to_layer(project, layout, layer_name, margin_ratio=0.1):
    print(f"Recalcul emprise layout : {layout.name()}")
    layers = project.mapLayersByName(layer_name)

    if not layers:
        print(f"Couche introuvable : {layer_name}")
        return
    layer = layers[0]
    if not layer.isValid():
        print(f"Couche invalide : {layer_name}")
        return

    # important
    layer.updateExtents()
    extent = QgsRectangle(layer.extent())

    if extent.isEmpty():
        print(f"Extent vide : {layer_name}")
        return
    # marge
    width_margin = extent.width() * margin_ratio
    height_margin = extent.height() * margin_ratio

    extent.setXMinimum(extent.xMinimum() - width_margin)
    extent.setXMaximum(extent.xMaximum() + width_margin)
    extent.setYMinimum(extent.yMinimum() - height_margin)
    extent.setYMaximum(extent.yMaximum() + height_margin)
    for item in layout.items():

        if isinstance(item, QgsLayoutItemMap):
            print(f"Zoom carte : {item.displayName()}")
            item.zoomToExtent(extent)
            item.refresh()


def relink_gpkg_layers(project, gpkg_path):

    print("Relink des couches GPKG...")

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

def set_group_visibility(project, group_name, visibility):

    root = project.layerTreeRoot()
    group = root.findGroup(group_name)

    if group:
        group.setItemVisibilityChecked(visibility)
        print(f"Groupe {group.name()} -> {visibility}")
    if group is None:
        print(f"Groupe introuvable : {group_name}")
        return


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--output")

    args = parser.parse_args()

    project_path = Path(args.project) / "projet_modele.qgs"
    output_path = Path(args.output)
    data_path = project_path.parent / "data" / "toutes_les_donnees.gpkg"

    print("Lancement du rendu QGIS...")
    print(f"Project path: {project_path}")
    print(f"Output path: {output_path}")

    output_path.mkdir(parents=True, exist_ok=True)


    # Init QGIS
    QgsApplication.setPrefixPath(
        "C:/Program Files/QGIS/3_40",
        True
    )

    qgs = QgsApplication([], False)
    qgs.initQgis()

    # Chargement projet
    print("Chargement du projet...")
    project = QgsProject.instance()
    loaded = project.read(str(project_path))
    print("Projet chargé :", loaded)
    if not loaded:
        raise Exception(
            f"Impossible de charger le projet : {project_path}"
        )


    manager = project.layoutManager()
    root = project.layerTreeRoot()
    model = project.mapThemeCollection()

    relink_gpkg_layers(project, data_path)



    print("Layouts disponibles :")
    layouts_to_export = []
    for layout in manager.layouts():
        print("-", layout.name())
        layouts_to_export.append(layout.name())

    # EXPORT
    for layout_name in layouts_to_export:
        print(f"Export du layout : {layout_name}")

        # gestion des groupes à afficher
        for g in layouts_to_export:
            set_group_visibility(project, g, False)

        set_group_visibility(project, "FDC", True)
        set_group_visibility(project, layout_name, True)

        layout = manager.layoutByName(layout_name)

        zoom_layout_maps_to_layer(project, layout, "observations_brutes")

        ### si est introuvable, on affiche un message d'erreur et on continue
        if layout is None:
            print(f"Layout introuvable : {layout_name}")
            continue

        exporter = QgsLayoutExporter(layout)
        output_file = output_path / f"{layout_name}.png"

        # suppression si existe
        if output_file.exists():
            output_file.unlink()

        settings = QgsLayoutExporter.ImageExportSettings()
        export_result = exporter.exportToImage(str(output_file), settings)
        print("Résultat export :", export_result)

    qgs.exitQgis()
    print("Rendu QGIS terminé")


if __name__ == "__main__":
    main()