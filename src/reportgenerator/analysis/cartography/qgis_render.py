# qgis_render.py

import argparse
from pathlib import Path

from qgis.core import (
    QgsApplication,
    QgsProject,
    QgsLayoutExporter,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer
)

def set_group_visibility(project, group_name, visibility):

    root = project.layerTreeRoot()
    group = root.findGroup(group_name)

    if group is None:
        print(f"Groupe introuvable : {group_name}")
        return

    # Fonction récursive
    def set_visibility_recursive(node, visibility):
        # Active/désactive le noeud courant
        node.setItemVisibilityChecked(visibility)

        # Si c'est un groupe, parcourir ses enfants
        if isinstance(node, QgsLayerTreeGroup):
            for child in node.children():
                set_visibility_recursive(child, visibility)

    # Appliquer au groupe et à tout son contenu
    set_visibility_recursive(group, visibility)
    print(f"Groupe {group_name} -> {visibility}")


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--project")
    parser.add_argument("--output")

    args = parser.parse_args()

    project_path = Path(args.project)
    output_path = Path(args.output)

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