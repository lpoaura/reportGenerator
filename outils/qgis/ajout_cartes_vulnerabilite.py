"""Ajoute au projet QGIS éolien les cartes liées à l'indice de vulnérabilité (copie : le projet source n'est pas
modifié).

Usage : python-qgis-ltr.bat outils/qgis/ajout_cartes_vulnerabilite.py <projet.qgs> <data_dir> <sortie.qgs>
  data_dir : dossier data/ d'un dry-run éolien contenant vm_eolienne_passereaux.gpkg et vm_eolienne_vuln_oiseau.gpkg.

- Carte11.2_nidif_passereaux (clone de Carte11.1_nidif_Hérons) : couche vm_eolienne_passereaux, symbole rond simple ;
  couleurs et formes par espèce construites au rendu ([params.qgis_render.categories_dynamiques]).
- Carte17bis_vulnerabilite (clone de Carte17_sensibilite) : couche vm_eolienne_vuln_oiseau, mêmes classes et couleurs
  que la carte 17 (mailles de 3 et plus), sur le champ « vulnerabilite » (0,5 à 7,5).
Idempotent (groupes, couches et mises en page de ces noms remplacés). Installer ensuite avec integrer_projet.py.
"""
import os
import re
import shutil
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsLayoutItemLabel, QgsLayoutItemLegend, QgsMarkerSymbol, QgsProject,
                       QgsSingleSymbolRenderer, QgsVectorLayer)

COUCHES = ("vm_eolienne_passereaux", "vm_eolienne_vuln_oiseau")
NOTE_17BIS = ("L'indice de vulnérabilité dans une maille est calculé à partir de :\n"
              "l'indice de vulnérabilité le plus élevé des espèces observées (0,5 à 4,5),\n"
              "+1 si un rapace ou grand voilier y est nicheur probable ou certain,\n"
              "+1 si un dortoir de rapace ou grand voilier y est connu,\n"
              "+1 si une donnée de migration de rapace ou grand voilier y est connue.")

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


def nettoyer(nom):
    if manager.layoutByName(nom):
        manager.removeLayout(manager.layoutByName(nom))
    if root.findGroup(nom):
        for node in root.findGroup(nom).findLayers():
            P.removeMapLayer(node.layerId())
        root.removeChildNode(root.findGroup(nom))


def couche(table, nom_affiche, renderer):
    lyr = QgsVectorLayer(f"{(data_dir / table).as_posix()}.gpkg|layername={table}", nom_affiche, "ogr")
    assert lyr.isValid(), f"couche invalide : {data_dir / table}.gpkg"
    lyr.setRenderer(renderer)
    P.addMapLayer(lyr, False)
    return lyr


def groupe(nom, apres, lyr):
    noms = [c.name() for c in root.children()]
    g = root.insertGroup(noms.index(apres) + 1, nom)
    g.addLayer(lyr)
    g.setItemVisibilityChecked(False)
    return g


def mise_en_page(nom, modele, titre, lyr, titre_legende, colonnes=1, note=None):
    """Clone de la mise en page modele : titre, légende thématique (couche lyr) et note remplacés."""
    lay = manager.layoutByName(modele).clone()
    lay.setName(nom)
    manager.addLayout(lay)
    for it in list(lay.items()):
        if isinstance(it, QgsLayoutItemLabel) and it.id() == "Titre":
            it.setText(titre)
        elif isinstance(it, QgsLayoutItemLabel) and it.id() == "" and note is not None:
            it.setText(note)
        elif isinstance(it, QgsLayoutItemLegend) and "LEGENDE_ZONE_ETUDE" not in [
                n.name() for n in it.model().rootGroup().findLayers()]:
            it.setAutoUpdateModel(False)
            it.model().rootGroup().removeAllChildren()
            node = it.model().rootGroup().addLayer(lyr)
            node.setCustomProperty("legend/title-label", titre_legende)
            it.setLegendFilterByMapEnabled(True)
            it.setColumnCount(colonnes)
            it.setResizeToContents(True)
            it.updateLegend()
    return lay


# --- carte 11.2 : passereaux nicheurs à enjeux
nettoyer("Carte11.2_nidif_passereaux")
rond = QgsMarkerSymbol.createSimple(
    {"name": "circle", "color": "#e6194b", "size": "2.4", "outline_color": "#ffffff", "outline_width": "0.3"})
passereaux = couche("vm_eolienne_passereaux", "Passereaux nicheurs", QgsSingleSymbolRenderer(rond))
groupe("Carte11.2_nidif_passereaux", "Carte11.1_nidif_Hérons", passereaux)
mise_en_page("Carte11.2_nidif_passereaux", "Carte11.1_nidif_Hérons", "Données de nidification des passereaux à enjeux",
             passereaux, "Passereaux nicheurs à enjeux", colonnes=2)

# --- carte 17 bis : indice par maille calculé à partir de la vulnérabilité (même style que la carte 17)
nettoyer("Carte17bis_vulnerabilite")
modele = root.findGroup("Carte17_sensibilite").findLayers()[0].layer()
style = modele.renderer().clone()
style.setClassAttribute("vulnerabilite")
derniere = len(style.ranges()) - 1
style.updateRangeUpperValue(derniere, 7.5)
style.updateRangeLabel(derniere, "6 - 7,5")
vuln = couche("vm_eolienne_vuln_oiseau", "Carte17bis_vulnerabilite", style)
vuln.setOpacity(modele.opacity())
groupe("Carte17bis_vulnerabilite", "Carte17_sensibilite", vuln)
mise_en_page("Carte17bis_vulnerabilite", "Carte17_sensibilite", "Indice de vulnérabilité des oiseaux", vuln,
             "Indice de vulnérabilité", note=NOTE_17BIS)

# ordre de rendu : couches ajoutées à la place de leur modèle (points au-dessus de tout, mailles comme la carte 17)
if root.hasCustomLayerOrder():
    ordre = [x for x in root.customLayerOrder() if x.id() not in (passereaux.id(), vuln.id())]
    i17 = next(i for i, x in enumerate(ordre) if x.id() == modele.id())
    ordre.insert(i17, vuln)
    root.setCustomLayerOrder([passereaux, *ordre])

assert P.write(str(dst)), "écriture impossible"
texte = dst.read_text(encoding="utf-8")
texte = re.sub(r'[^"<>|=]*?[/\\](' + "|".join(COUCHES) + r')\.gpkg', r"./data/\1.gpkg", texte)
texte = texte.replace(dst.parent.as_posix() + "/data/", src.parent.resolve().as_posix() + "/data/")
dst.write_text(texte, encoding="utf-8")
print("Projet écrit :", dst)
app.exitQgis()
