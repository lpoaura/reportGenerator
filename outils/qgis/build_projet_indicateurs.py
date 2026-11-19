"""Construit le projet QGIS du dossier Indicateurs de biodiversité à partir du projet Natura 2000 (même charte).

Usage : python-qgis-ltr.bat outils/qgis/build_projet_indicateurs.py <projet_n2000.qgs> <dossier de travail>
            [<modèle de mise en page .qpt>]
  Le dossier de travail doit contenir data/ (couches ind_*.gpkg d'un dry-run du dossier indicateurs). Le projet y est
  écrit (projet_indicateurs.qgs), ses couches pointant vers ./data/<couche>.gpkg. Installation dans le dépôt :
  outils/qgis/integrer_projet.py. Modèle par défaut : outils/qgis/modeles/carte_paysage_lpo.qpt (A4 paysage LPO,
  bandeau bleu à gauche avec la légende, carte à droite).

Contenu : groupe « Fond » (emprise, départements, zones biogéographiques) au-dessus du fond FDC (tuiles vectorielles
OpenMapTiles de Mergin Maps, style par défaut à 75 % d'opacité) ; un groupe et une mise en page par protocole
(STOC_CARTE…) avec la couche ind_aires filtrée sur le protocole et colorée par statut en N. La symbologie se règle
ensuite directement dans QGIS.

Lisibilité : les points des aires sont dessinés au-dessus des limites (groupes des cartes en tête de l'arbre) ; dans
une carte, les niveaux de symboles placent les catégories utiles devant (nouvelles > suivies > non suivies ; abandons
devant ; « Non renseigné » derrière) ; les catégories de contexte ont un petit point pâle ; seul le fond OSM du
projet Natura 2000 est remplacé (ses région et départements doublaient ceux du groupe « Fond »).
"""
import os
import shutil
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsCentroidFillSymbolLayer,
                       QgsExpressionContextUtils, QgsFillSymbol, QgsLayerTreeGroup, QgsLayoutItemLabel,
                       QgsLayoutItemLegend, QgsLayoutItemMap, QgsLayoutItemScaleBar, QgsLayoutPoint, QgsLegendStyle,
                       QgsMapLayerLegendUtils, QgsMarkerSymbol, QgsPrintLayout, QgsProject, QgsReadWriteContext,
                       QgsRendererCategory, QgsSingleSymbolRenderer, QgsVectorLayer, QgsVectorTileLayer)
from qgis.PyQt.QtXml import QDomDocument

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
MODELE_QPT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path(__file__).parent / "modeles" / "carte_paysage_lpo.qpt"
# fond de carte : OpenMapTiles (OSM) servi par Mergin Maps, style par défaut
FOND_URI = ("styleUrl=https://tiles.merginmaps.com/styles/default.json&type=xyz"
            "&url=https://tiles.merginmaps.com/data/default/%7Bz%7D/%7Bx%7D/%7By%7D.pbf&zmax=14&zmin=0")
# images du modèle : sa source est l'expression @logo_gauche / @fleche_nord_blanche (variables du profil QGIS LPO),
# définies ici en variables du projet avec les images des cartes portrait
IMAGES = {"logo_gauche": "Z:/01_Modeles/CHARTE LPO/LOGOS/POUR LE WEB/LPO Auvergne-Rhône-Alpes_GAUCHE_transparent.png",
          "fleche_nord_blanche": "https://raw.githubusercontent.com/lpoaura/lpo_qgis_profiles/main/profiles/"
                                 "naturaliste/composer_templates/deco/Fleche_N_blanche.svg"}
# tailles de police (pt) : titre sur une ou deux lignes dans son bandeau, légende dans le bandeau gauche (61 mm)
TITRE_PT = 20
LEGENDE_PT = {QgsLegendStyle.Title: 14, QgsLegendStyle.Group: 11, QgsLegendStyle.Subgroup: 10,
              QgsLegendStyle.SymbolLabel: 8}
COUPURE = "|"   # coupure de ligne des libellés de légende trop longs
# flèche du Nord et barre d'échelle remontées (mm) : le cartouche des sources (aligné en bas) a besoin de place
REMONTEE_MM = {"fleche": 30, "echelle": 20}
# texte du cartouche (sources, conception, date), repris des cartes portrait
CARTOUCHE = ("Sources :  [% @sources %]\nConception :  [%@user_full_name %] (LPO Auvergne-Rhône-Alpes)\n"
             "Date de réalisation : $CURRENT_DATE(yyyy-MM-dd)")

# (code, préfixe, protocole, aires, « suivis » accordé) ; titres complétés par @annee_<préfixe> et
# @annee_prec_<préfixe> (variables de projet fournies par la brique ind_cartes : « 2025 », « 2024-2025 » pour le SHOC)
PROTOCOLES = [("stoc", "STOC", "STOC-EPS", "carrés", "suivis"),
              ("shoc", "SHOC", "SHOC", "carrés", "suivis"),
              ("stom", "STOM", "STOM", "sites", "suivis"),
              ("sterf", "STERF", "STERF", "sites", "suivis"),
              ("pop_reptile", "POPR", "POP Reptile", "aires", "suivies"),
              ("pop_amphibien", "POPA", "POP Amphibien", "aires", "suivies")]
# palette des graphiques du rapport (analysis/indicateurs/figures.py)
BLEU, ORANGE, VERT_EAU, ROUGE, BLEU_PALE = "#2a78d6", "#eb6834", "#1baf7a", "#e34948", "#b7d3f6"
GRIS_PALE = "#c4c4c4"   # contexte (non suivies, non renseignées) : petit point pâle, comme les suivies des abandons
# (valeur, libellé, couleur, niveau, forme) : niveau = ordre de dessin (le plus grand devant) ;
# forme « plein » (point de TAILLE_POINT), « petit » (point plein réduit), « creux » (cercle vide réduit : contexte)
STATUTS = [("suivie", "Suivi(e) cette année", BLEU, 2, "plein"),
           ("nouvelle", "Suivi(e) pour la|première fois", ORANGE, 3, "plein"),
           ("non suivie", "Non suivi(e) cette année", GRIS_PALE, 1, "petit")]
CATEGORIES = [("Salarié LPO", "Salarié LPO", BLEU, 2, "plein"),
              ("Organisme tiers", "Organisme tiers", ORANGE, 2, "plein"),
              ("Bénévole", "Bénévole", VERT_EAU, 2, "plein"),
              ("Non renseigné", "Non renseigné", GRIS_PALE, 1, "petit")]
RECONDUCTION = [("abandon", "Suivi(e) la saison précédente,|pas cette année", ROUGE, 2, "plein"),
                ("suivie", "Suivi(e) cette année", BLEU_PALE, 1, "petit")]


TAILLE_POINT = "2.4"     # mm : point au centre de chaque aire (contour blanc : deux points proches restent distincts)
TAILLE_CONTEXTE = "1.7"  # mm : aires de contexte (non suivies, non renseignées, suivies sur la carte des abandons)
FOND_OPACITE = 0.75      # fond OpenMapTiles : couleurs adoucies mais présentes (localisation), points lisibles
ECHELLE_MM = (20, 40)    # barre d'échelle dans le bandeau gauche (61 mm) : plage assez large pour des valeurs rondes


def remplissage(couleur, niveau=1, forme="plein", contour="35,35,35,255", largeur="0.15"):
    """Contour de l'aire + point au centre (les petites aires restent visibles à l'échelle de la région).
    Le point est dessiné au passage `niveau` (niveaux de symboles), le polygone au passage 0."""
    creux = forme == "creux"
    s = QgsFillSymbol.createSimple({"color": couleur, "style": "no" if creux else "solid", "outline_color": contour,
                                    "outline_width": largeur})
    s.symbolLayer(0).setRenderingPass(0)
    centre = QgsCentroidFillSymbolLayer()
    if creux:
        point = {"color": "255,255,255,0", "outline_color": couleur, "outline_width": "0.45"}
    else:
        point = {"color": couleur, "outline_color": "white", "outline_width": "0.35"}
    centre.setSubSymbol(QgsMarkerSymbol.createSimple(
        {"name": "circle", "size": TAILLE_POINT if forme == "plein" else TAILLE_CONTEXTE, **point}))
    centre.setRenderingPass(niveau)
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


def groupe(nom, couches, visible=False, en_tete=False):
    """Groupe au-dessus du fond de carte (FDC) ; `en_tete` : tout en haut (dessiné devant les autres groupes)."""
    noms = [c.name() for c in ROOT.children()]
    g = ROOT.insertGroup(0 if en_tete else noms.index("FDC"), nom)
    for lyr in couches:
        g.addLayer(lyr)
    g.setItemVisibilityChecked(visible)
    return g


# ================================================================= nettoyage du projet Natura 2000
manager = P.layoutManager()
for g in [c for c in ROOT.children() if isinstance(c, QgsLayerTreeGroup) and c.name() != "FDC"]:
    for node in g.findLayers():
        P.removeMapLayer(node.layerId())
    ROOT.removeChildNode(g)
# fond FDC : remplacé par les tuiles vectorielles OpenMapTiles (région et départements du projet Natura 2000
# doublaient le groupe « Fond », zone d'étude et contours Natura 2000 sans objet)
for node in ROOT.findGroup("FDC").findLayers():
    P.removeMapLayer(node.layerId())
fond = QgsVectorTileLayer(FOND_URI, "OpenMapTiles (Mergin Maps)")
assert fond.isValid(), "fond de carte OpenMapTiles invalide"
message, ok = fond.loadDefaultStyle()
assert ok, f"style du fond de carte non chargé : {message}"
fond.setOpacity(FOND_OPACITE)
P.addMapLayer(fond, False)
ROOT.findGroup("FDC").addLayer(fond)

for nom, valeur in IMAGES.items():
    QgsExpressionContextUtils.setProjectVariable(P, nom, valeur)

# ================================================================= fond commun
zone = couche("ind_zone", "Zone du rapport")
zone.setRenderer(QgsSingleSymbolRenderer(contour("#2b2b2b", "0.6")))
deps = couche("ind_departements", "Départements")
deps.setRenderer(QgsSingleSymbolRenderer(contour("#555555", "0.3")))
zbiog = couche("ind_zbiog", "Zones biogéographiques")
zbiog.setRenderer(QgsSingleSymbolRenderer(contour("#8b5a2b", "0.4", "dash")))
groupe("Fond", [zone, deps, zbiog], visible=True)

# ================================================================= trois mises en page par protocole
modele = QgsPrintLayout(P)
gabarit = QDomDocument()
assert gabarit.setContent(MODELE_QPT.read_text(encoding="utf-8")), f"modèle illisible : {MODELE_QPT}"
_, ok = modele.loadFromTemplate(gabarit, QgsReadWriteContext())
assert ok, f"chargement du modèle impossible : {MODELE_QPT}"


def carte(nom, champ, categories, subset, titre, legende):
    """Groupe + mise en page `nom` (clone du modèle) : couche ind_aires filtrée et catégorisée sur `champ`."""
    aires = couche("ind_aires", "Aires", subset=subset)
    renderer = QgsCategorizedSymbolRenderer(champ, [
        QgsRendererCategory(v, remplissage(c, niveau, forme), lab) for v, lab, c, niveau, forme in categories])
    renderer.setUsingSymbolLevels(True)
    aires.setRenderer(renderer)
    groupe(nom, [aires], en_tete=True)   # points devant les limites du groupe « Fond »
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
    # limites fines et grises : symbole de légende éclairci, lisible sur le fond bleu de la légende
    QgsMapLayerLegendUtils.setLegendNodeCustomSymbol(racine.addLayer(deps), 0, contour("#e6e6e6", "0.4"))
    QgsMapLayerLegendUtils.setLegendNodeCustomSymbol(racine.addLayer(zbiog), 0, contour("#f2e3cf", "0.5", "dash"))
    for style, taille in LEGENDE_PT.items():
        format_ = principale.rstyle(style).textFormat()
        format_.setSize(taille)
        principale.rstyle(style).setTextFormat(format_)
    principale.setWrapString(COUPURE)
    principale.setAutoUpdateModel(False)
    principale.setLegendFilterByMapEnabled(False)
    principale.setResizeToContents(True)
    principale.updateLegend()
    for it in lay.items():
        if isinstance(it, QgsLayoutItemLabel) and it.id() == "Titre":
            it.setText(titre)
            format_ = it.textFormat()
            format_.setSize(TITRE_PT)
            it.setTextFormat(format_)
        if isinstance(it, QgsLayoutItemLabel) and it.id() == "Infos sup":
            it.setText(CARTOUCHE)
        if isinstance(it, QgsLayoutItemMap):
            it.setKeepLayerSet(False)
            it.setFollowVisibilityPreset(False)
        if isinstance(it, QgsLayoutItemScaleBar):
            it.setMinimumBarWidth(ECHELLE_MM[0])
            it.setMaximumBarWidth(ECHELLE_MM[1])
            it.update()
        if isinstance(it, QgsLayoutItemScaleBar) or getattr(it, "id", lambda: "")() == "Flèche du Nord":
            pos = it.positionWithUnits()
            cle = "echelle" if isinstance(it, QgsLayoutItemScaleBar) else "fleche"
            it.attemptMove(QgsLayoutPoint(pos.x(), pos.y() - REMONTEE_MM[cle], pos.units()))


for code, prefixe, protocole, aires_, suivis in PROTOCOLES:
    du_protocole = f"\"protocole\" = '{code}'"
    annee, prec = f"[% @annee_{prefixe} %]", f"[% @annee_prec_{prefixe} %]"
    carte(f"{prefixe}_CARTE", "statut", STATUTS, du_protocole,
          f"{protocole} : {aires_} {suivis} en {annee}", aires_.capitalize())
    carte(f"{prefixe}_CARTE_CATEGORIES", "categorie", CATEGORIES, f"{du_protocole} AND \"categorie\" IS NOT NULL",
          f"{protocole} : observateurs\ndes {aires_} {suivis} en {annee}", "Catégorie de l'observateur|principal")
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
