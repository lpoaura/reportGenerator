"""Remet en ordre le rendu d'un projet : ordre de l'arbre des couches, couches des cartes de connaissance juste sous
les contours de la zone d'étude, aucune couche sous le fond de carte (sinon : cartes vides).

Usage : python-qgis-ltr.bat outils/qgis/ordre_rendu.py <projet.qgs> <sortie.qgs>
  Écrit une copie (installer ensuite avec integrer_projet.py) ; affiche les couches qui étaient sous le fond.
"""
import os
import shutil
import sys
from pathlib import Path

from qgis.core import QgsApplication, QgsMapLayerType, QgsProject

sys.path.insert(0, str(Path(__file__).parent))
import connaissance_qgis  # noqa: E402

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
QgsApplication.setPrefixPath(os.getenv("QGIS_PREFIX_PATH", r"C:\Program Files\QGIS\3_40\apps\qgis-ltr"), True)
app = QgsApplication([], False)
app.initQgis()

dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)
att = src.with_name(src.stem + "_attachments.zip")
if att.exists():
    shutil.copy2(att, dst.with_name(dst.stem + "_attachments.zip"))
P = QgsProject.instance()
assert P.read(str(dst)), "lecture du projet impossible"
root = P.layerTreeRoot()
avant = root.customLayerOrder() if root.hasCustomLayerOrder() else root.layerOrder()
rasters = [i for i, lyr in enumerate(avant) if lyr.type() == QgsMapLayerType.RasterLayer]
print("sous le fond avant :", [lyr.name() for lyr in avant[rasters[-1] + 1:]] if rasters else [])
connaissance_qgis.fixer_ordre_rendu(P, connaissance_qgis.couches_connaissance(P))
assert P.write(str(dst)), "écriture impossible"
print("Projet écrit :", dst)
app.exitQgis()
