"""inspect_layout.py <projet.qgs> <mise en page> : éléments de la mise en page (type, id, position, taille, texte,
couches des légendes). Usage : python-qgis-ltr.bat outils/qgis/inspect_layout.py <projet.qgs> <mise en page>"""
import sys

from qgis.core import (QgsApplication, QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap,
                       QgsLayoutItemPicture, QgsLayoutItemScaleBar, QgsProject)

app = QgsApplication([], False)
app.initQgis()
P = QgsProject.instance()
P.read(sys.argv[1])
lay = P.layoutManager().layoutByName(sys.argv[2])
for it in lay.items():
    if not hasattr(it, "positionWithUnits"):
        continue
    pos, size = it.positionWithUnits(), it.sizeWithUnits()
    info = ""
    if isinstance(it, QgsLayoutItemLabel):
        info = repr(it.text()[:80])
    elif isinstance(it, QgsLayoutItemLegend):
        info = f"titre={it.title()!r} couches={[n.name() for n in it.model().rootGroup().findLayers()]} " \
               f"cols={it.columnCount()}"
    elif isinstance(it, QgsLayoutItemMap):
        info = f"follow={it.followVisibilityPreset()} keepLayers={it.keepLayerSet()}"
    elif isinstance(it, (QgsLayoutItemPicture, QgsLayoutItemScaleBar)):
        info = type(it).__name__
    print(f"{type(it).__name__:24} id={it.id()!r:22} pos=({pos.x():.1f},{pos.y():.1f}) "
          f"taille=({size.width():.1f},{size.height():.1f}) {info}")
print("groupes racine :", [c.name() for c in P.layerTreeRoot().children()])
app.exitQgis()
