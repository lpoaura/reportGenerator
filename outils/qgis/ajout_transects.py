"""Ajoute la carte des transects et placettes (Carte_transects) à un projet QGIS (copie : le source n'est pas modifié).

Usage : python-qgis-ltr.bat outils/qgis/ajout_transects.py <projet.qgs> <data_dir> <sortie.qgs>
  data_dir : dossier data/ d'un rapport (dry-run) contenant transects_lignes.gpkg et transects_polygones.gpkg.
  La sortie est écrite avec les sources ./data/<couche>.gpkg ; ses pièces jointes (_attachments.zip) sont copiées.
  Installation : copier la sortie (et ses pièces jointes) à la place du projet du dossier, ou integrer_projet.py.
"""
import os
import shutil
import sys
from pathlib import Path

from qgis.core import QgsApplication, QgsProject

sys.path.insert(0, str(Path(__file__).parent))
import connaissance_qgis  # noqa: E402
import transects_qgis  # noqa: E402

src, data_dir, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
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
print("Mise en page ajoutée :", transects_qgis.ajouter(P, data_dir))
assert P.write(str(dst)), "écriture impossible"
texte = transects_qgis.chemins_relatifs(connaissance_qgis.chemins_relatifs(dst.read_text(encoding="utf-8")))
# chemins absolus du projet d'origine recalés par QGIS sur le dossier de sortie : rétablis
texte = texte.replace(dst.parent.as_posix() + "/data/", src.parent.resolve().as_posix() + "/data/")
dst.write_text(texte, encoding="utf-8")
print("Projet écrit :", dst)
app.exitQgis()
