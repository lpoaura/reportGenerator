# qgis_render.py

import sys
from pathlib import Path

# Ajout explicite de la racine du package, indépendamment de PYTHONPATH
# (le .bat QGIS peut écraser les variables d'environnement héritées)
package_root = Path(__file__).resolve().parents[3]  # .../src
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))


import argparse  # noqa: E402

from qgis.core import (QgsApplication, QgsExpressionContextUtils, QgsLayoutExporter,  # noqa: E402
                       QgsLayoutItemMap, QgsProject, QgsRectangle, QgsVectorLayer)

from reportgenerator.analysis.cartography.qgis_sources import (  # noqa: E402
    load_render_config, relink_gpkg_source)
from reportgenerator.analysis.qgis_runtime import resolve_qgis_prefix  # noqa: E402


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


def layer_extent(project, layer_name):
    layers = project.mapLayersByName(layer_name)
    if not layers:
        print(f"Couche introuvable pour l'emprise : {layer_name}")
        return None
    layer = layers[0]
    if not layer.isValid():
        print(f"Couche invalide pour l'emprise : {layer_name}")
        return None
    layer.updateExtents()
    extent = QgsRectangle(layer.extent())
    if extent.isEmpty():
        print(f"Emprise vide : {layer_name}")
        return None
    return extent


def zoom_layout_maps(layout, base_extent, config):
    """Cadre les cartes de la mise en page sur l'emprise de référence
    (+ marge, + tampon propre à la mise en page, + décalage vertical)."""
    extent = QgsRectangle(base_extent)
    buffer_m = config["layout_buffers_m"].get(layout.name(), 0)
    if buffer_m:
        extent = extent.buffered(buffer_m)

    dx = extent.width() * config["extent_margin_ratio"]
    dy = extent.height() * config["extent_margin_ratio"]
    offset = (extent.height() + 2 * dy) * config["extent_offset_y_ratio"]
    extent = QgsRectangle(extent.xMinimum() - dx, extent.yMinimum() - dy + offset,
                          extent.xMaximum() + dx, extent.yMaximum() + dy + offset)

    for item in layout.items():
        if isinstance(item, QgsLayoutItemMap):
            print(f"Zoom carte : {item.displayName()}")
            item.zoomToExtent(extent)
            item.refresh()


def relink_gpkg_layers(project, data_dir):
    print(f"Relink des couches GPKG vers {data_dir}...")
    for layer in project.mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        new_source = relink_gpkg_source(layer.source(), data_dir)
        if new_source is None:
            continue
        print(f"Relink : {layer.name()} -> {new_source}")
        layer.setDataSource(new_source, layer.name(), "ogr")
        layer.reload()


def export_atlas(layout, output_path, settings):
    """Une image par entité de la couche de couverture : <mise en page>__<clé>.png
    (champ « cle » de la couverture s'il existe, sinon numéro de page). L'emprise de chaque page est celle de
    l'entité (carte « pilotée par l'atlas »)."""
    atlas = layout.atlas()
    atlas.updateFeatures()
    print(f"Atlas {layout.name()} : {atlas.count()} pages")
    if not atlas.beginRender():
        print(f"[ERREUR] Atlas {layout.name()} : rendu impossible")
        return
    for i in range(atlas.count()):
        atlas.seekTo(i)
        feature = atlas.layout().reportContext().feature()
        key = feature["cle"] if "cle" in feature.fields().names() else f"{i + 1:03d}"
        output_file = output_path / f"{layout.name()}__{key}.png"
        result = QgsLayoutExporter(layout).exportToImage(str(output_file), settings)
        if result != QgsLayoutExporter.Success:
            print(f"[ERREUR] Atlas {layout.name()}, page {key} : code {result}")
    atlas.endRender()


def set_group_visibility(project, group_name, visibility):
    group = project.layerTreeRoot().findGroup(group_name)
    if group is None:
        print(f"Groupe introuvable : {group_name}")
        return
    group.setItemVisibilityChecked(visibility)
    print(f"Groupe {group.name()} -> {visibility}")


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--output")
    parser.add_argument("--config", default=None, help="JSON de configuration du rendu")

    args = parser.parse_args()

    project_path = Path(args.project)
    output_path = Path(args.output)
    config = load_render_config(args.config)

    data_path = project_path.parent / "data"

    print("Lancement du rendu QGIS...")
    print(f"Project path: {project_path}")
    print(f"Output path: {output_path}")
    print(f"Config: {config}")

    output_path.mkdir(parents=True, exist_ok=True)

    QgsApplication.setPrefixPath(str(resolve_qgis_prefix()), True)
    qgs = QgsApplication([], False)
    qgs.initQgis()

    try:
        print("Chargement du projet...")
        project = QgsProject.instance()
        if not project.read(str(project_path)):
            raise Exception(f"Impossible de charger le projet : {project_path}")

        relink_gpkg_layers(project, data_path)
        reload_project(project, project_path)

        manager = project.layoutManager()
        layouts_to_export = [layout.name() for layout in manager.layouts()]
        print("Layouts disponibles :", ", ".join(layouts_to_export))

        # variables de projet (ex. @sources dans le texte « Sources » des mises en page)
        for name, value in (config.get("project_variables") or {}).items():
            QgsExpressionContextUtils.setProjectVariable(project, name, value)

        # emprise commune : rectangle calculé par le générateur (extent_bbox), sinon emprise d'une couche
        bbox = config.get("extent_bbox")
        base_extent = QgsRectangle(*bbox) if bbox else layer_extent(project, config["extent_layer"])
        settings = QgsLayoutExporter.ImageExportSettings()
        if config["dpi"]:
            settings.dpi = config["dpi"]

        for layout_name in layouts_to_export:
            print(f"Export du layout : {layout_name}")
            layout = manager.layoutByName(layout_name)
            if layout is None:
                print(f"Layout introuvable : {layout_name}")
                continue

            # un seul groupe thématique visible : celui qui porte le nom de la mise en page
            for g in layouts_to_export:
                set_group_visibility(project, g, False)
            for g in config["visible_groups"]:
                set_group_visibility(project, g, True)
            set_group_visibility(project, layout_name, True)

            # atlas : seulement s'il a une couche de couverture (certaines mises en page des projets modèles
            # ont l'atlas « activé » sans couverture : ce sont des cartes simples)
            if layout.atlas().enabled() and layout.atlas().coverageLayer() is not None:
                export_atlas(layout, output_path, settings)
                continue

            # emprise propre à la mise en page (rectangle calculé, sinon couche), sinon emprise commune
            fixed = (config.get("layout_extents") or {}).get(layout_name)
            extent_name = (config.get("layout_extent_layers") or {}).get(layout_name)
            if fixed:
                extent = QgsRectangle(*fixed)
            else:
                extent = layer_extent(project, extent_name) if extent_name else base_extent
            if extent is not None:
                zoom_layout_maps(layout, extent, config)

            output_file = output_path / f"{layout_name}.png"
            if output_file.exists():
                output_file.unlink()
            result = QgsLayoutExporter(layout).exportToImage(str(output_file), settings)
            if result != QgsLayoutExporter.Success:
                print(f"[ERREUR] Export de la carte {layout_name} : code {result}")
    finally:
        qgs.exitQgis()
    print("Rendu QGIS terminé")


if __name__ == "__main__":
    main()
