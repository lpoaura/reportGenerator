"""Cartes de nidification par groupe d'espèces : mise en page modèle Cartes_nidification (copie du projet ; le projet
source n'est pas modifié).

Usage : python-qgis-ltr.bat outils/qgis/ajout_cartes_groupes.py <projet.qgs> <data_dir> <sortie.qgs>
  data_dir : dossier data/ d'un dry-run éolien contenant vm_eolienne_nidif_cartes.gpkg.

- groupe et mise en page Cartes_nidification, clone de Carte8_nidif_milan_busard (charte des cartes de nidification) ;
  le rendu en tire une image par carte du plan (filtre "cle", couleurs par espèce, points écartés en anneau,
  cf. [params.qgis_render] et dossiers/eolien/METHODO.md §5 bis) ;
- couche « Nidification » (symbole modèle : rond de 2,2 mm, contour blanc) et couche de légende « Site occupé au moins
  3 années » (jamais dessinée : filtre sans entité ; seul son symbole sert dans la légende) ;
- anciennes cartes de nidification (6 à 11.2) retirées : mises en page et groupes de couches.
Idempotent. Installer ensuite avec integrer_projet.py.
"""
import os
import re
import shutil
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsLayoutItemLabel, QgsLayoutItemLegend, QgsMarkerSymbol, QgsProject,
                       QgsSingleSymbolRenderer, QgsVectorLayer)

NOM, MODELE, COUCHE = "Cartes_nidification", "Carte8_nidif_milan_busard", "vm_eolienne_nidif_cartes"
ANCIENNES = ("Carte6_nidif_rapaces_nocturnes", "Carte7_nidif_buse_faucon", "Carte8_nidif_milan_busard",
             "Carte9_nidif_diurnes", "Carte10_nidif_Mouette_Sterne_Goeland", "Carte11_nidif_Cigogne",
             "Carte11.1_nidif_Hérons", "Carte11.2_nidif_passereaux")

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
root, manager = P.layerTreeRoot(), P.layoutManager()


def retirer(nom):
    if manager.layoutByName(nom):
        manager.removeLayout(manager.layoutByName(nom))
    g = root.findGroup(nom)
    if g:
        for node in g.findLayers():
            P.removeMapLayer(node.layerId())
        root.removeChildNode(g)


def couche(nom_affiche, symbole, filtre=None):
    lyr = QgsVectorLayer(f"{(data_dir / COUCHE).as_posix()}.gpkg|layername={COUCHE}", nom_affiche, "ogr")
    assert lyr.isValid(), f"couche invalide : {data_dir / COUCHE}.gpkg"
    lyr.setRenderer(QgsSingleSymbolRenderer(symbole))
    if filtre:
        lyr.setSubsetString(filtre)
    P.addMapLayer(lyr, False)
    return lyr


retirer(NOM)
assert manager.layoutByName(MODELE), f"mise en page modèle {MODELE} absente (script déjà passé ?)"
noms = [c.name() for c in root.children()]
position = min((noms.index(n) for n in ANCIENNES if n in noms), default=len(noms))

points = couche("Nidification", QgsMarkerSymbol.createSimple(
    {"name": "circle", "color": "#888888", "size": "2.2", "outline_color": "#ffffff", "outline_width": "0.2"}))
legende_site = couche("Site occupé au moins 3 années", QgsMarkerSymbol.createSimple(
    {"name": "circle", "color": "#bdbdbd", "size": "3.5", "outline_color": "#000000", "outline_width": "0.5"}),
    filtre='"fid" < 0')   # aucune entité : rien n'est dessiné, le symbole sert seulement à la légende
legende_site.setCustomProperty("reportgenerator/legende_seule", True)   # ignorée par le style et le filtre du rendu
groupe = root.insertGroup(position, NOM)
groupe.addLayer(points)
groupe.addLayer(legende_site)
groupe.setItemVisibilityChecked(False)
if root.hasCustomLayerOrder():   # points au-dessus de tout, comme les anciennes cartes de nidification
    ordre = [x for x in root.customLayerOrder() if x.id() not in (points.id(), legende_site.id())]
    root.setCustomLayerOrder([points, legende_site, *ordre])

lay = manager.layoutByName(MODELE).clone()
lay.setName(NOM)
manager.addLayout(lay)
for it in list(lay.items()):
    if isinstance(it, QgsLayoutItemLabel) and it.id() == "Titre":
        it.setText("Données de nidification")       # remplacé par le titre de chaque carte au rendu
    elif isinstance(it, QgsLayoutItemLegend) and "LEGENDE_ZONE_ETUDE" not in [
            n.name() for n in it.model().rootGroup().findLayers()]:
        it.setAutoUpdateModel(False)
        racine = it.model().rootGroup()
        racine.removeAllChildren()
        n_points = racine.addLayer(points)
        n_points.setCustomProperty("legend/title-label", "Nidification probable ou certaine")
        racine.addLayer(legende_site)          # symbole unique : une ligne « symbole + nom de la couche »
        it.setLegendFilterByMapEnabled(False)   # les catégories de la carte sont déjà celles de la page
        it.setColumnCount(1)
        it.setResizeToContents(True)
        it.updateLegend()

for nom in ANCIENNES:
    retirer(nom)

assert P.write(str(dst)), "écriture impossible"
texte = dst.read_text(encoding="utf-8")
texte = re.sub(r'[^"<>|=]*?[/\\](' + COUCHE + r')\.gpkg', r"./data/\1.gpkg", texte)
texte = texte.replace(dst.parent.as_posix() + "/data/", src.parent.resolve().as_posix() + "/data/")
dst.write_text(texte, encoding="utf-8")
print("Projet écrit :", dst)
print("Mises en page :", [m.name() for m in manager.layouts()])
app.exitQgis()
