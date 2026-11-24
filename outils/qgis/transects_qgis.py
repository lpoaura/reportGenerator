"""Carte des transects et placettes (brique commune geometries) ajoutée à un projet QGIS existant, dans sa charte.

    ajouter(P, data_dir)

Couches transects_lignes et transects_polygones (lues dans data_dir pour la construction, enregistrées en
./data/<couche>.gpkg), un groupe et une mise en page Carte_transects, clone de Connaissance_effort_donnees (présente
dans les projets générique, éolien et Natura 2000, chacun dans sa charte) : titre et légende remplacés, note du
modèle retirée (les titres de la légende suffisent ; une note chevaucherait la légende, de hauteur variable).
Couleurs : catégories construites au rendu sur les données (protocole, couleur et ordre fournis par la brique :
qgis_render.categories_dynamiques) ; le style du projet ne donne que l'épaisseur des traits. Idempotent.
"""
import re

from qgis.core import (QgsFillSymbol, QgsLayoutItemHtml, QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLineSymbol,
                       QgsSingleSymbolRenderer, QgsVectorLayer)

import connaissance_qgis

LAYOUT = "Carte_transects"
MODELE = "Connaissance_effort_donnees"
COUCHES = {"transects_lignes": "Transects (lignes)", "transects_polygones": "Placettes et sites (polygones)"}
TITRE = "Transects et placettes\npar protocole"


def _nettoyer(P):
    lay = P.layoutManager().layoutByName(LAYOUT)
    if lay:
        P.layoutManager().removeLayout(lay)
    g = P.layerTreeRoot().findGroup(LAYOUT)
    if g:
        for node in g.findLayers():
            P.removeMapLayer(node.layerId())
        P.layerTreeRoot().removeChildNode(g)


def _couche(P, data_dir, table):
    lyr = QgsVectorLayer(f"{(data_dir / table).as_posix()}.gpkg|layername={table}", COUCHES[table], "ogr")
    assert lyr.isValid(), f"couche invalide : {data_dir / table}.gpkg"
    if table == "transects_lignes":
        sym = QgsLineSymbol.createSimple({"line_width": "1.2", "line_color": "#636363", "capstyle": "round"})
    else:   # remplissage transparent : la couleur de la catégorie va au contour (qgis_render.apply_dynamic_categories)
        sym = QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": "#636363", "outline_width": "0.8"})
    lyr.setRenderer(QgsSingleSymbolRenderer(sym))
    P.addMapLayer(lyr, False)
    return lyr


def _titre(lay):
    for it in lay.items():
        if isinstance(it, QgsLayoutItemLabel) and it.id() == "Titre":
            it.setText(TITRE)
    for mf in lay.multiFrames():
        if isinstance(mf, QgsLayoutItemHtml):
            mf.setHtml("<br>\n".join(TITRE.split("\n")))
            mf.loadHtml()


def _sans_note(lay):
    notes = [it for it in lay.items() if isinstance(it, QgsLayoutItemLabel) and it.text().startswith("Groupes étudiés")]
    assert notes, f"note de {MODELE} introuvable"
    for it in notes:
        lay.removeLayoutItem(it)


def _legende(lay, modele_ids, couches):
    """Légende thématique du modèle (celle qui affiche la couche d'effort) : couches du modèle remplacées par les
    couches des transects, avec leur titre."""
    for lg in [it for it in lay.items() if isinstance(it, QgsLayoutItemLegend)]:
        root = lg.model().rootGroup()
        anciens = [n for n in root.findLayers() if n.layer() and n.layer().id() in modele_ids]
        if not anciens:
            continue
        for n in anciens:
            n.parent().removeChildNode(n)
        for lyr in reversed(couches):
            root.insertLayer(0, lyr).setCustomProperty("legend/title-label", lyr.name())
        lg.setLegendFilterByMapEnabled(True)
        lg.updateLegend()
        return
    raise AssertionError(f"légende thématique de {MODELE} introuvable")


def ajouter(P, data_dir):
    _nettoyer(P)
    root = P.layerTreeRoot()
    modele = P.layoutManager().layoutByName(MODELE)
    assert modele is not None, f"mise en page {MODELE} absente (ajouter d'abord l'état des connaissances)"
    groupe_modele = root.findGroup(MODELE)
    modele_ids = {n.layerId() for n in groupe_modele.findLayers()} if groupe_modele else set()

    couches = [_couche(P, data_dir, t) for t in COUCHES]
    noms = [c.name() for c in root.children()]
    g = root.insertGroup(noms.index("FDC") if "FDC" in noms else len(noms), LAYOUT)
    for lyr in couches:
        g.addLayer(lyr)
    g.setItemVisibilityChecked(False)

    lay = modele.clone()
    lay.setName(LAYOUT)
    P.layoutManager().addLayout(lay)
    _titre(lay)
    _sans_note(lay)
    _legende(lay, modele_ids, couches)
    # sous les contours de la zone d'étude, au-dessus du fond de carte (avec les couches de connaissance)
    connaissance_qgis.fixer_ordre_rendu(P, connaissance_qgis.couches_connaissance(P) | {c.id() for c in couches})
    return LAYOUT


def chemins_relatifs(qgs_text: str) -> str:
    """Sources des couches transects_* : chemin de construction -> ./data/<couche>.gpkg."""
    return re.sub(r'[^"<>|=]*?[/\\](' + "|".join(COUCHES) + r')\.gpkg', r"./data/\1.gpkg", qgs_text)
