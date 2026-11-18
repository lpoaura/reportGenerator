"""Construit le projet QGIS du dossier Indicateurs de biodiversité à partir du projet Natura 2000 (même charte).

Usage : python-qgis-ltr.bat outils/qgis/build_projet_indicateurs.py <projet_n2000.qgs> <dossier de travail>
  Le dossier de travail doit contenir data/ (couches ind_*.gpkg d'un dry-run du dossier indicateurs). Le projet y est
  écrit (projet_indicateurs.qgs), ses couches pointant vers ./data/<couche>.gpkg. Installation dans le dépôt :
  outils/qgis/integrer_projet.py.

Contenu : groupe « Fond » (emprise, départements, zones biogéographiques, toujours visible avec le fond FDC) ; un
groupe et une mise en page par protocole (STOC_CARTE…) avec la couche ind_aires filtrée sur le protocole et
colorée par statut en N. La symbologie se règle ensuite directement dans QGIS.
"""
import os
import shutil
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsCentroidFillSymbolLayer, QgsFillSymbol,
                       QgsLayerTreeGroup, QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap, QgsMarkerSymbol,
                       QgsProject, QgsRendererCategory, QgsSingleSymbolRenderer, QgsVectorLayer)

QgsApplication.setPrefixPath(os.getenv("QGIS_PREFIX_PATH", r"C:\Program Files\QGIS\3_40\apps\qgis-ltr"), True)
app = QgsApplication([], False)
app.initQgis()

src, work = Path(sys.argv[1]), Path(sys.argv[2])
project_path = work / "projet_indicateurs.qgs"
shutil.copy2(src, project_path)
att = src.with_name(src.stem + "_attachments.zip")
if att.exists():
    shutil.copy2(att, work / "projet_indicateurs_attachments.zip")
P = QgsProject.instance()
assert P.read(str(project_path)), "lecture du projet impossible"
DATA = work / "data"
ROOT = P.layerTreeRoot()
MODELE = "Carte01_localisation"

# (code, préfixe, protocole, aires, « suivis » accordé) ; titres complétés par @annee_<préfixe> et
# @annee_prec_<préfixe> (variables de projet fournies par la brique ind_cartes : « 2025 », « 2024-2025 » pour le SHOC)
PROTOCOLES = [("stoc", "STOC", "STOC-EPS", "carrés", "suivis"),
              ("shoc", "SHOC", "SHOC", "carrés", "suivis"),
              ("stom", "STOM", "STOM", "sites", "suivis"),
              ("sterf", "STERF", "STERF", "sites", "suivis"),
              ("pop_reptile", "POPR", "POP Reptile", "aires", "suivies"),
              ("pop_amphibien", "POPA", "POP Amphibien", "aires", "suivies")]
# palette des graphiques du rapport (analysis/indicateurs/figures.py)
BLEU, ORANGE, VERT_EAU, GRIS, ROUGE, BLEU_PALE = "#2a78d6", "#eb6834", "#1baf7a", "#a6a6a6", "#e34948", "#b7d3f6"
STATUTS = [("suivie", "Suivi(e) cette année", BLEU),
           ("nouvelle", "Suivi(e) pour la première fois", ORANGE),
           ("non suivie", "Non suivi(e) cette année", GRIS)]
CATEGORIES = [("Salarié LPO", "Salarié LPO", BLEU), ("Organisme tiers", "Organisme tiers", ORANGE),
              ("Bénévole", "Bénévole", VERT_EAU), ("Non renseigné", "Non renseigné", GRIS)]
RECONDUCTION = [("abandon", "Suivi(e) la saison précédente, pas cette année", ROUGE),
                ("suivie", "Suivi(e) cette année", BLEU_PALE)]


TAILLE_POINT = "2.4"   # mm : point au centre de chaque aire (contour blanc : deux points proches restent distincts)


def remplissage(couleur, contour="35,35,35,255", largeur="0.15"):
    """Contour de l'aire + point au centre (les petites aires restent visibles à l'échelle de la région)."""
    s = QgsFillSymbol.createSimple({"color": couleur, "outline_color": contour, "outline_width": largeur})
    centre = QgsCentroidFillSymbolLayer()
    centre.setSubSymbol(QgsMarkerSymbol.createSimple({"name": "circle", "color": couleur, "outline_color": "white",
                                                      "outline_width": "0.35", "size": TAILLE_POINT}))
    s.appendSymbolLayer(centre)
    return s


def contour(couleur, largeur, style="solid"):
    return QgsFillSymbol.createSimple({"style": "no", "outline_color": couleur, "outline_width": largeur,
                                       "outline_style": style})


def couche(table, nom, subset=None):
    lyr = QgsVectorLayer(f"{DATA / table}.gpkg|layername={table}", nom, "ogr")
    assert lyr.isValid(), f"couche invalide : {table}"
    if subset:
        lyr.setSubsetString(subset)
    P.addMapLayer(lyr, False)
    return lyr


def groupe(nom, couches, visible=False):
    noms = [c.name() for c in ROOT.children()]
    g = ROOT.insertGroup(noms.index("FDC"), nom)   # au-dessus du fond de carte
    for lyr in couches:
        g.addLayer(lyr)
    g.setItemVisibilityChecked(visible)
    return g


# ================================================================= nettoyage du projet Natura 2000
manager = P.layoutManager()
assert manager.layoutByName(MODELE) is not None, f"mise en page modèle « {MODELE} » absente du projet source"
for g in [c for c in ROOT.children() if isinstance(c, QgsLayerTreeGroup) and c.name() != "FDC"]:
    for node in g.findLayers():
        P.removeMapLayer(node.layerId())
    ROOT.removeChildNode(g)
# fond FDC : on garde le fond OSM, la région et les départements ; zone d'étude et contours Natura 2000 retirés
for node in ROOT.findGroup("FDC").findLayers():
    if node.name() in ("LEGENDE_ZONE_ETUDE", "LEGENDE_LIMITE"):
        P.removeMapLayer(node.layerId())

# ================================================================= fond commun
zone = couche("ind_zone", "Zone du rapport")
zone.setRenderer(QgsSingleSymbolRenderer(contour("#191919", "0.8")))
deps = couche("ind_departements", "Départements")
deps.setRenderer(QgsSingleSymbolRenderer(contour("#626a6e", "0.35")))
zbiog = couche("ind_zbiog", "Zones biogéographiques")
zbiog.setRenderer(QgsSingleSymbolRenderer(contour("#007e85", "0.5", "dash")))
groupe("Fond", [zone, deps, zbiog], visible=True)

# ================================================================= trois mises en page par protocole
modele = manager.layoutByName(MODELE)


def carte(nom, champ, categories, subset, titre, legende):
    """Groupe + mise en page `nom` (clone du modèle) : couche ind_aires filtrée et catégorisée sur `champ`."""
    aires = couche("ind_aires", "Aires", subset=subset)
    aires.setRenderer(QgsCategorizedSymbolRenderer(champ, [
        QgsRendererCategory(v, remplissage(c), lab) for v, lab, c in categories]))
    groupe(nom, [aires])
    lay = modele.clone()
    lay.setName(nom)
    manager.addLayout(lay)
    legendes = [it for it in lay.items() if isinstance(it, QgsLayoutItemLegend)]
    principale = next(lg for lg in legendes if lg.title() == "Légende")
    for lg in legendes:
        if lg is not principale:
            lay.removeLayoutItem(lg)
    racine = principale.model().rootGroup()
    racine.removeAllChildren()
    noeud = racine.addLayer(aires)
    noeud.setCustomProperty("legend/title-label", legende)
    racine.addLayer(zone)
    racine.addLayer(deps)
    racine.addLayer(zbiog)
    principale.setAutoUpdateModel(False)
    principale.setLegendFilterByMapEnabled(False)
    principale.setResizeToContents(True)
    principale.updateLegend()
    for it in lay.items():
        if isinstance(it, QgsLayoutItemLabel) and it.id() == "Titre":
            it.setText(titre)
        if isinstance(it, QgsLayoutItemMap):
            it.setKeepLayerSet(False)
            it.setFollowVisibilityPreset(False)


for code, prefixe, protocole, aires_, suivis in PROTOCOLES:
    du_protocole = f"\"protocole\" = '{code}'"
    annee, prec = f"[% @annee_{prefixe} %]", f"[% @annee_prec_{prefixe} %]"
    carte(f"{prefixe}_CARTE", "statut", STATUTS, du_protocole,
          f"{protocole} : {aires_} {suivis} en {annee}", aires_.capitalize())
    carte(f"{prefixe}_CARTE_CATEGORIES", "categorie", CATEGORIES, f"{du_protocole} AND \"categorie\" IS NOT NULL",
          f"{protocole} : observateurs\ndes {aires_} {suivis} en {annee}", "Catégorie de l'observateur principal")
    carte(f"{prefixe}_CARTE_ABANDONS", "reconduction", RECONDUCTION,
          f"{du_protocole} AND \"reconduction\" IS NOT NULL",
          f"{protocole} : {aires_} à reprendre\n({suivis} en {prec}, pas en {annee})", aires_.capitalize())

# suppression des autres mises en page (modèle compris)
for lay in list(manager.layouts()):
    if "_CARTE" not in lay.name():
        manager.removeLayout(lay)

# ordre de rendu = ordre de l'arbre (groupes au-dessus du fond de carte)
ROOT.setHasCustomLayerOrder(False)
sys.path.insert(0, str(Path(__file__).parent))
import connaissance_qgis  # noqa: E402

connaissance_qgis.verifier_fond_de_carte(P)

assert P.write(str(project_path)), "écriture impossible"
print("Projet écrit :", project_path)
print("Mises en page :", [lay.name() for lay in manager.layouts()])
print("Groupes :", [c.name() for c in ROOT.children()])
app.exitQgis()
