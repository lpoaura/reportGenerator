"""Ajoute les cartes de l'état des connaissances à un projet QGIS (copie : le projet source n'est pas modifié).

Usage : python-qgis-ltr.bat outils/qgis/ajout_connaissance.py <projet.qgs> <data_dir> <eolien|generique> <sortie.qgs>
  data_dir : dossier data/ d'un rapport (dry-run) contenant connaissance_*.gpkg.
  La sortie est écrite avec les sources ./data/<couche>.gpkg ; ses pièces jointes (_attachments.zip) sont copiées.
"""
import os
import shutil
import sys
from pathlib import Path

from qgis.core import QgsApplication, QgsProject

sys.path.insert(0, str(Path(__file__).parent))
import connaissance_qgis  # noqa: E402

src, data_dir, profil, dst = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4])
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
ajoutees = connaissance_qgis.ajouter(P, data_dir, profil)
assert P.write(str(dst)), "écriture impossible"
texte = connaissance_qgis.chemins_relatifs(dst.read_text(encoding="utf-8"), data_dir)
# chemins absolus du projet d'origine (ex. relations) recalés par QGIS sur le dossier de sortie : rétablis
texte = texte.replace(dst.parent.as_posix() + "/data/", src.parent.resolve().as_posix() + "/data/")
dst.write_text(texte, encoding="utf-8")
print("Projet écrit :", dst)
print("Mises en page ajoutées :", ajoutees)
print("Toutes :", [lay.name() for lay in P.layoutManager().layouts()])
app.exitQgis()
