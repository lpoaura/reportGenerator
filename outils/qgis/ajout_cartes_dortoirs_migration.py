"""Cartes de dortoirs par groupe d'espèces et de migration par espèce : mises en page modèles du projet éolien
(copie ; le projet source n'est pas modifié).

Usage : python-qgis-ltr.bat outils/qgis/ajout_cartes_dortoirs_migration.py <projet.qgs> <data_dir> <sortie.qgs>
  data_dir : dossier data/ d'un dry-run éolien contenant vm_eolienne_dortoirs_cartes.gpkg et
  vm_eolienne_migration_especes.gpkg.

- Cartes_dortoirs (clone de Carte12.2_dortoir_milan) : couche « Dortoirs » (zones fusionnées, une couleur par espèce
  construite au rendu, semi-transparente) ; cartes 12.1 à 12.4 retirées ;
- Carte12_dortoir_toutes_donnees (synthèse) : sa couche (liste de noms figée) remplacée par les zones de toutes les
  espèces, couleur unique (« style fixe » : ni restylée ni filtrée au rendu) ;
- Cartes_migration (clone de Carte16_migration_effectif_Milan) : couche « Migration » (symbole de la carte 16 : rond
  creux, taille selon nb_ind_max ; couleur de l'espèce au contour, au rendu) ; carte 16 retirée.
Le rendu en tire une image par page (cf. [params.qgis_render] et METHODO.md §5 bis). Idempotent.
Installer ensuite avec integrer_projet.py.
"""
import os
import re
import shutil
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsFillSymbol, QgsLayoutItemLabel, QgsLayoutItemLegend, QgsProject,
                       QgsRenderContext, QgsSingleSymbolRenderer, QgsVectorLayer)

DORTOIRS, MIGRATION = "vm_eolienne_dortoirs_cartes", "vm_eolienne_migration_especes"
ANCIENNES_DORTOIRS = ("Carte12.1_dortoir_ardeide", "Carte12.2_dortoir_milan", "Carte12.3_dortoir_faucon",
                      "Carte12.4_dortoir_rapace")
SYNTHESE, CARTE16 = "Carte12_dortoir_toutes_donnees", "Carte16_migration_effectif_Milan"

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


def couche(table, nom_affiche, symbole, opacite=1.0):
    lyr = QgsVectorLayer(f"{(data_dir / table).as_posix()}.gpkg|layername={table}", nom_affiche, "ogr")
    assert lyr.isValid(), f"couche invalide : {data_dir / table}.gpkg"
    lyr.setRenderer(QgsSingleSymbolRenderer(symbole))
    lyr.setOpacity(opacite)
    P.addMapLayer(lyr, False)
    return lyr


def groupe(nom, apres, couches):
    noms = [c.name() for c in root.children()]
    g = root.insertGroup(noms.index(apres) + 1 if apres in noms else len(noms), nom)
    for lyr in couches:
        g.addLayer(lyr)
    g.setItemVisibilityChecked(False)
    return g


def legende_thematique(lay, lyr, titre):
    """Légende thématique de la mise en page (celle qui n'est pas la légende des contours) : la couche lyr seule."""
    for it in lay.items():
        if isinstance(it, QgsLayoutItemLegend) and "LEGENDE_ZONE_ETUDE" not in [
                n.name() for n in it.model().rootGroup().findLayers()]:
            it.setAutoUpdateModel(False)
            racine = it.model().rootGroup()
            racine.removeAllChildren()
            racine.addLayer(lyr).setCustomProperty("legend/title-label", titre)
            it.setLegendFilterByMapEnabled(False)
            it.setResizeToContents(True)
            it.updateLegend()


def cloner(modele, nom, titre):
    lay = manager.layoutByName(modele).clone()
    lay.setName(nom)
    manager.addLayout(lay)
    for it in lay.items():
        if isinstance(it, QgsLayoutItemLabel) and it.id() == "Titre":
            it.setText(titre)            # remplacé par le titre de chaque carte au rendu
    return lay


def au_dessus(couches):
    """Couches ajoutées dessinées au-dessus de tout (comme les anciens points)."""
    if root.hasCustomLayerOrder():
        ids = {c.id() for c in couches}
        root.setCustomLayerOrder([*couches, *[x for x in root.customLayerOrder() if x.id() not in ids]])


for nom in ("Cartes_dortoirs", "Cartes_migration"):
    retirer(nom)
assert manager.layoutByName("Carte12.2_dortoir_milan") and manager.layoutByName(CARTE16), \
    "mises en page modèles absentes (script déjà passé ?)"
ajoutees = []

# --- dortoirs par groupe : zones semi-transparentes, contour sombre
dortoirs = couche(DORTOIRS, "Dortoirs", QgsFillSymbol.createSimple(
    {"color": "#888888", "outline_color": "#323232", "outline_width": "0.3"}), opacite=0.65)
groupe("Cartes_dortoirs", SYNTHESE, [dortoirs])
legende_thematique(cloner("Carte12.2_dortoir_milan", "Cartes_dortoirs", "Données de dortoirs"), dortoirs,
                   "Zones de dortoir (fusion des données proches)")
ajoutees.append(dortoirs)

# --- synthèse des dortoirs : toutes les espèces, couleur unique, style fixe
g = root.findGroup(SYNTHESE)
for node in g.findLayers():
    P.removeMapLayer(node.layerId())
synthese = couche(DORTOIRS, "Zones de dortoir, toutes espèces", QgsFillSymbol.createSimple(
    {"color": "#eb5f1a", "outline_color": "#8c3207", "outline_width": "0.3"}), opacite=0.6)
synthese.setCustomProperty("reportgenerator/style_fixe", True)
g.addLayer(synthese)
legende_thematique(manager.layoutByName(SYNTHESE), synthese, "Dortoirs")
ajoutees.append(synthese)

# --- migration par espèce : symbole de la carte 16 (rond creux, taille selon l'effectif)
modele16 = root.findGroup(CARTE16).findLayers()[0].layer()
symbole16 = modele16.renderer().symbols(QgsRenderContext())[0]
migration = couche(MIGRATION, "Migration", symbole16.clone())   # copie : le style devient propriétaire du symbole
groupe("Cartes_migration", CARTE16, [migration])
cloner(CARTE16, "Cartes_migration", "Données de migration")   # légende des effectifs de la carte 16 gardée
ajoutees.append(migration)

for nom in (*ANCIENNES_DORTOIRS, CARTE16):
    retirer(nom)
au_dessus(ajoutees)

assert P.write(str(dst)), "écriture impossible"
texte = dst.read_text(encoding="utf-8")
texte = re.sub(r'[^"<>|=]*?[/\\](' + "|".join((DORTOIRS, MIGRATION)) + r')\.gpkg', r"./data/\1.gpkg", texte)
texte = texte.replace(dst.parent.as_posix() + "/data/", src.parent.resolve().as_posix() + "/data/")
dst.write_text(texte, encoding="utf-8")
print("Projet écrit :", dst)
print("Mises en page :", [m.name() for m in manager.layouts()])
app.exitQgis()
