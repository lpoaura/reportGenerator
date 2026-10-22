# qgis_render.py

import sys
from pathlib import Path

# Ajout explicite de la racine du package, indépendamment de PYTHONPATH
# (le .bat QGIS peut écraser les variables d'environnement héritées)
package_root = Path(__file__).resolve().parents[3]  # .../src
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))


import argparse  # noqa: E402

from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsExpressionContextUtils,  # noqa: E402
                       QgsLayoutExporter, QgsLayoutItemLabel, QgsLayoutItemMap, QgsMarkerSymbol,
                       QgsPointDisplacementRenderer, QgsPointDistanceRenderer, QgsProject, QgsProperty,
                       QgsRectangle, QgsRendererCategory, QgsSimpleMarkerSymbolLayerBase, QgsSymbol, QgsSymbolLayer,
                       QgsUnitTypes, QgsVectorLayer)
from qgis.PyQt.QtGui import QColor  # noqa: E402

from reportgenerator.analysis.cartography.qgis_sources import (  # noqa: E402
    categories_dynamiques, filtre_page, load_render_config, relink_gpkg_source)
from reportgenerator.analysis.qgis_runtime import resolve_qgis_prefix  # noqa: E402

FORMES_QGIS = {"circle": QgsSimpleMarkerSymbolLayerBase.Circle, "square": QgsSimpleMarkerSymbolLayerBase.Square,
               "triangle": QgsSimpleMarkerSymbolLayerBase.Triangle,
               "diamond": QgsSimpleMarkerSymbolLayerBase.Diamond}
# propriétés définies par les données des symboles (noms de QGIS 3.40, avec repli sur les anciens)
PROP_TAILLE = getattr(QgsSymbolLayer, "PropertySize", None) or QgsSymbolLayer.Property.Size
PROP_CONTOUR = getattr(QgsSymbolLayer, "PropertyStrokeColor", None) or QgsSymbolLayer.Property.StrokeColor
PROP_LARGEUR = getattr(QgsSymbolLayer, "PropertyStrokeWidth", None) or QgsSymbolLayer.Property.StrokeWidth


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


LEGENDE_SEULE = "reportgenerator/legende_seule"   # couche de légende (jamais dessinée), laissée telle quelle
STYLE_FIXE = "reportgenerator/style_fixe"         # couche gardant son style du projet (ex. carte de synthèse)


def layers_gpkg(project, layer_name):
    """Couches du projet lisant la couche GPKG layer_name (layername de la source, ou nom affiché), hors couches
    « légende seule » ou « style fixe » (propriétés LEGENDE_SEULE, STYLE_FIXE) : ni restylées, ni filtrées."""
    return [lyr for lyr in project.mapLayers().values()
            if isinstance(lyr, QgsVectorLayer) and lyr.isValid()
            and not lyr.customProperty(LEGENDE_SEULE) and not lyr.customProperty(STYLE_FIXE)
            and (lyr.name() == layer_name or f"layername={layer_name}" in lyr.source().split("|"))]


def _symbole_modele(layer):
    """Symbole du projet servant de modèle (taille, contour), même après un premier style construit au rendu."""
    renderer = layer.renderer()
    if isinstance(renderer, QgsPointDistanceRenderer):
        renderer = renderer.embeddedRenderer()
    if hasattr(renderer, "sourceSymbol") and renderer.sourceSymbol():
        return renderer.sourceSymbol().clone()
    if hasattr(renderer, "symbol") and renderer.symbol():
        return renderer.symbol().clone()
    return QgsSymbol.defaultSymbol(layer.geometryType())


def _accentuer(symbol, champ):
    """Point grossi et cerclé de noir quand le champ booléen `champ` est vrai (ex. site occupé plusieurs années)."""
    sl = symbol.symbolLayer(0)
    taille = symbol.size() if isinstance(symbol, QgsMarkerSymbol) else 2
    sl.setDataDefinedProperty(PROP_TAILLE, QgsProperty.fromExpression(
        f'if("{champ}", {taille * 1.6:.2f}, {taille:.2f})'))
    sl.setDataDefinedProperty(PROP_CONTOUR, QgsProperty.fromExpression(f"if(\"{champ}\", '#000000', '#ffffff')"))
    sl.setDataDefinedProperty(PROP_LARGEUR, QgsProperty.fromExpression(f'if("{champ}", 0.5, 0.2)'))


def apply_dynamic_categories(project, spec):
    """Style catégorisé construit à partir des données de la zone (après le filtre de la page s'il y en a un) :
    spec = {couche GPKG: [champ, champ d'ordre(, champ couleur(, champ booléen d'accent))]}.
    Sans champ couleur : palette automatique (qgis_sources.categories_dynamiques) ; avec : couleur de la donnée."""
    for layer_name, champs in (spec or {}).items():
        field, order_field = champs[0], champs[1]
        color_field = champs[2] if len(champs) > 2 else None
        accent_field = champs[3] if len(champs) > 3 else None
        layers = layers_gpkg(project, layer_name)
        if not layers:
            print(f"Catégories : couche {layer_name} absente du projet")
        for layer in layers:
            names = layer.fields().names()
            if field not in names:
                print(f"Catégories : champ {field} absent de {layer_name}")
                continue
            features = list(layer.getFeatures())
            valeurs = [(f[field], f[order_field] if order_field in names else None) for f in features]
            couleurs = ({f[field]: f[color_field] for f in features} if color_field in names else {})
            base = _symbole_modele(layer)
            categories = []
            for valeur, couleur, forme in categories_dynamiques(valeurs):
                symbol = base.clone()
                sl = symbol.symbolLayer(0)
                teinte = QColor(couleurs.get(valeur) or couleur)
                if sl.color().alpha() == 0 and hasattr(sl, "setStrokeColor"):
                    sl.setStrokeColor(teinte)      # symbole creux (ex. effectifs de migration) : couleur au contour
                else:
                    symbol.setColor(teinte)
                if hasattr(sl, "setShape") and not couleurs:
                    sl.setShape(FORMES_QGIS[forme])
                if accent_field in names:
                    _accentuer(symbol, accent_field)
                categories.append(QgsRendererCategory(valeur, symbol, str(valeur)))
            renderer = QgsCategorizedSymbolRenderer(field, categories)
            renderer.setSourceSymbol(base.clone())
            layer.setRenderer(renderer)
            layer.legendChanged.emit()   # légendes des mises en page (modèle propre, mise à jour automatique coupée)
            layer.triggerRepaint()
            print(f"Catégories {layer_name} : {len(categories)} valeurs de {field}")


def apply_displacement(project, spec):
    """Points superposés écartés en anneau autour de leur position : spec = {couche GPKG: distance en mm}.
    Le style de la couche (ex. catégories) est gardé comme style des points."""
    for layer_name, distance in (spec or {}).items():
        for layer in layers_gpkg(project, layer_name):
            renderer = layer.renderer()
            if isinstance(renderer, QgsPointDistanceRenderer):
                renderer = renderer.embeddedRenderer()
            disp = QgsPointDisplacementRenderer("")   # pas d'étiquette
            disp.setEmbeddedRenderer(renderer.clone())
            disp.setTolerance(float(distance))
            disp.setToleranceUnit(QgsUnitTypes.RenderMillimeters)
            disp.setPlacement(QgsPointDisplacementRenderer.Ring)
            disp.setCircleWidth(0)                       # pas de cercle autour du groupe
            disp.setCircleColor(QColor(0, 0, 0, 0))
            disp.setCenterSymbol(QgsMarkerSymbol.createSimple(   # petit point : position réelle du groupe
                {"name": "circle", "size": "0.6", "color": "#3c3c3c", "outline_style": "no"}))
            layer.setRenderer(disp)
            layer.legendChanged.emit()
            layer.triggerRepaint()


def export_pages(project, layout, spec, config, settings, output_path):
    """Une image par page (<mise en page>__<clé>.png) : couches filtrées sur la clé de la page, styles construits sur
    les données de la page, titre de la page. spec = {champ, couches, pages: [{cle, titre}]}."""
    champ, couches = spec.get("champ", "cle"), spec.get("couches", [])
    layers = [lyr for nom in couches for lyr in layers_gpkg(project, nom)]
    titres = [it for it in layout.items() if isinstance(it, QgsLayoutItemLabel) and it.id() == "Titre"]
    styles = {k: v for k, v in (config.get("categories_dynamiques") or {}).items() if k in couches}
    ecarts = {k: v for k, v in (config.get("deplacement_mm") or {}).items() if k in couches}
    for page in spec.get("pages", []):
        for lyr in layers:
            lyr.setSubsetString(filtre_page(champ, page["cle"]))
        apply_dynamic_categories(project, styles)
        apply_displacement(project, ecarts)
        for it in titres:
            it.setText(page.get("titre", ""))
        output_file = output_path / f"{layout.name()}__{page['cle']}.png"
        result = QgsLayoutExporter(layout).exportToImage(str(output_file), settings)
        if result != QgsLayoutExporter.Success:
            print(f"[ERREUR] Export de la carte {layout.name()} / {page['cle']} : code {result}")
    for lyr in layers:
        lyr.setSubsetString("")


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
        apply_dynamic_categories(project, config.get("categories_dynamiques"))
        apply_displacement(project, config.get("deplacement_mm"))
        pages = config.get("pages") or {}

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

            # mise en page modèle : une image par page de la liste fournie par les briques (ex. cartes par groupe)
            if layout_name in pages:
                export_pages(project, layout, pages[layout_name], config, settings, output_path)
                continue

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
