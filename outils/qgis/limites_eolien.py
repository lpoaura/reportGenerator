"""Limites de la zone d'étude du projet QGIS éolien : seulement la zone d'étude et les contours 6 km et 20 km, style
commun (trait sur un liseré blanc), tracées au-dessus des données sur certaines cartes (copie : le projet source n'est
pas modifié).

Usage : python-qgis-ltr.bat outils/qgis/limites_eolien.py <projet_eolien.qgs> <data_dir> <sortie.qgs>
  data_dir : dossier data/ d'un dry-run éolien (zone_etude.gpkg, vm_eolienne_limit.gpkg…), copié à côté du projet
  produit : sinon QGIS ouvre les couches invalides et réécrit leur ancienne définition (filtre perdu).

- LEGENDE_ZONE_ETUDE : filtre "secteur" = 'Zone d''étude' (zone_etude.gpkg contient aussi le tampon du formulaire et
  les 50 km autour, sinon tracés comme la zone d'étude) ;
- LEGENDE_LIMITE : une catégorie par contour affiché (CONTOURS_AFFICHES), les autres anneaux de vm_eolienne_limit
  (1 km) ne sont pas tracés ;
- cartes de CARTES_DESSUS : copie des deux couches dans le groupe de la carte, en tête de l'ordre de rendu (le moteur
  n'affiche que le groupe portant le nom de la carte) ; les légendes des mises en page ne changent pas.
Idempotent (copies précédentes retirées). Installer ensuite avec integrer_projet.py.
"""
import os
import shutil
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsFillSymbol, QgsMapLayerType, QgsProject,
                       QgsRendererCategory, QgsSimpleLineSymbolLayer, QgsSingleSymbolRenderer, QgsUnitTypes)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

FILTRE_ZONE = "\"secteur\" = 'Zone d''étude'"
CARTES_DESSUS = ("Carte1_zone_localisation", "Carte2_Donnee_disponible", "Carte3_Etat_connaissance_globale",
                 "Carte17_sensibilite", "Carte17bis_vulnerabilite")
MARQUE = "reportgenerator/limites_dessus"
HALO = QColor(255, 255, 255, 217)        # liseré blanc sous chaque trait (lisible sur le fond et sur les mailles)
# (couleur, épaisseur mm, tirets mm (trait, blanc) ou None = continu)
# zone d'étude : rouge continu (distinct des limites administratives, sombres) ; contours : gris foncé en tirets
# (limites calculées, pas des limites réelles), longs pour 6 km, courts pour 20 km
STYLE_ZONE = ("#d7191c", 0.7, None)
CONTOURS_AFFICHES = {
    "contour 6 km": ("Contour 6 km", "#262626", 0.55, (4.0, 1.5)),
    "contour 20 km": ("Contour 20 km", "#262626", 0.45, (1.5, 1.5)),
}

src, data_dir, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
QgsApplication.setPrefixPath(os.getenv("QGIS_PREFIX_PATH", r"C:\Program Files\QGIS\3_40\apps\qgis-ltr"), True)
app = QgsApplication([], False)
app.initQgis()

dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)
att = src.with_name(src.stem + "_attachments.zip")
if att.exists():
    shutil.copy2(att, dst.with_name(dst.stem + "_attachments.zip"))
if (dst.parent / "data").resolve() != data_dir.resolve():
    shutil.copytree(data_dir, dst.parent / "data", dirs_exist_ok=True)
P = QgsProject.instance()
assert P.read(str(dst)), "lecture du projet impossible"
root = P.layerTreeRoot()


def symbole(couleur, epaisseur, tirets):
    """Contour seul (pas de remplissage) : liseré blanc continu, puis le trait (continu ou en tirets)."""
    halo = QgsSimpleLineSymbolLayer(HALO, epaisseur + 0.6)
    trait = QgsSimpleLineSymbolLayer(QColor(couleur), epaisseur)
    for sl in (halo, trait):
        sl.setWidthUnit(QgsUnitTypes.RenderMillimeters)
        sl.setPenJoinStyle(Qt.RoundJoin)
    if tirets:
        trait.setUseCustomDashPattern(True)
        trait.setCustomDashVector(list(tirets))
        trait.setCustomDashPatternUnit(QgsUnitTypes.RenderMillimeters)
        trait.setPenCapStyle(Qt.FlatCap)
    return QgsFillSymbol([halo, trait])


def unique(nom):
    couches = [lyr for lyr in P.mapLayersByName(nom) if lyr.customProperty(MARQUE) is None]
    assert len(couches) == 1, f"couche {nom} : {len(couches)} trouvée(s)"
    assert couches[0].isValid(), f"couche {nom} invalide (data_dir ?)"
    return couches[0]


# copies d'un passage précédent
for lyr in list(P.mapLayers().values()):
    if lyr.customProperty(MARQUE) is not None:
        P.removeMapLayer(lyr.id())

zone, limite = unique("LEGENDE_ZONE_ETUDE"), unique("LEGENDE_LIMITE")
assert zone.setSubsetString(FILTRE_ZONE), "filtre de la zone d'étude refusé"
assert zone.featureCount() == 1, f"zone d'étude : {zone.featureCount()} entités après filtre"
zone.setRenderer(QgsSingleSymbolRenderer(symbole(*STYLE_ZONE)))
valeurs = set(limite.uniqueValues(limite.fields().indexOf("area_name")))
assert set(CONTOURS_AFFICHES) <= valeurs, f"contours absents de vm_eolienne_limit : {set(CONTOURS_AFFICHES) - valeurs}"
limite.setRenderer(QgsCategorizedSymbolRenderer("area_name", [
    QgsRendererCategory(valeur, symbole(couleur, ep, tirets), libelle)
    for valeur, (libelle, couleur, ep, tirets) in CONTOURS_AFFICHES.items()
]))

# copies au-dessus des données, une par carte (dans le groupe de la carte)
dessus = []
for carte in CARTES_DESSUS:
    groupe = root.findGroup(carte)
    assert groupe is not None, f"groupe {carte} absent"
    for modele in (limite, zone):           # zone d'étude au-dessus des contours
        copie = modele.clone()
        copie.setName(f"{modele.name()} (dessus) {carte}")
        copie.setCustomProperty(MARQUE, carte)
        P.addMapLayer(copie, False)
        groupe.insertLayer(0, copie)
        dessus.append(copie)

ordre = root.customLayerOrder() if root.hasCustomLayerOrder() else root.layerOrder()
root.setCustomLayerOrder([*dessus[::-1], *[lyr for lyr in ordre if lyr.customProperty(MARQUE) is None]])
root.setHasCustomLayerOrder(True)
fonds = [i for i, lyr in enumerate(root.customLayerOrder()) if lyr.type() == QgsMapLayerType.RasterLayer]
assert not fonds or not [lyr for lyr in root.customLayerOrder()[fonds[-1] + 1:]
                         if lyr.type() == QgsMapLayerType.VectorLayer], "couche vecteur sous le fond de carte"

assert P.write(str(dst)), "écriture impossible"
print("Projet écrit :", dst)
print("copies au-dessus :", [lyr.name() for lyr in dessus])
app.exitQgis()
