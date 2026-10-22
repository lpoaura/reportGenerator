"""Construit le projet QGIS du dossier Natura 2000 à partir du projet éolien (même charte graphique).

Usage : python-qgis-ltr.bat outils/qgis/build_projet_n2000.py <projet_eolien.qgs> <dossier de travail>
  Le dossier de travail doit contenir data/ (couches GPKG d'un rapport). Le projet y est écrit
  (projet_n2000.qgs), ses couches pointant vers ./data/<couche>.gpkg.
"""
import os
import shutil
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsFillSymbol, QgsGradientColorRamp,
                       QgsGraduatedSymbolRenderer, QgsHeatmapRenderer, QgsLayerTreeGroup, QgsLayoutItemLabel,
                       QgsLayoutItemLegend, QgsLegendStyle, QgsLayoutItemMap, QgsLayoutItemPicture,
                       QgsLayoutItemScaleBar, QgsLayoutPoint, QgsLayoutSize,
                       QgsMarkerSymbol, QgsPointDisplacementRenderer, QgsProject, QgsProperty, QgsRendererCategory,
                       QgsRendererRange, QgsRuleBasedRenderer, QgsSingleSymbolRenderer, QgsSymbolLayer,
                       QgsUnitTypes, QgsVectorLayer)
from qgis.core import (Qgis, QgsLayoutItemShape, QgsLinePatternFillSymbolLayer, QgsPalLayerSettings,  # noqa
                       QgsTextBackgroundSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling)
from qgis.core import QgsLegendRenderer  # noqa
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

QgsApplication.setPrefixPath(os.getenv("QGIS_PREFIX_PATH", r"C:\Program Files\QGIS\3_40\apps\qgis-ltr"), True)
app = QgsApplication([], False)
app.initQgis()

src, work = Path(sys.argv[1]), Path(sys.argv[2])
project_path = work / "projet_n2000.qgs"
shutil.copy2(src, project_path)
att = src.with_name(src.stem + "_attachments.zip")
if att.exists():
    shutil.copy2(att, work / "projet_n2000_attachments.zip")
P = QgsProject.instance()
assert P.read(str(project_path)), "lecture du projet impossible"
DATA = work / "data"
ROOT = P.layerTreeRoot()

VIRIDIS_5 = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]
PALETTE = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#a65628", "#f781bf", "#17becf", "#bcbd22",
           "#7f7f7f", "#1b9e77", "#d95f02", "#7570b3", "#e7298a", "#66a61e"]
BLEU_COLONIE, ORANGE_GITE = "#1f78b4", "#ff7f00"
TYPES_DONNEE = [("Nicheur certain", "#e31a1c"), ("Nicheur probable", "#fd8d3c"),
                ("Nicheur possible", "#fecc5c"), ("Autres données", "#2b8cbe")]
EFFECTIFS = [(0, 3, "1 - 3", 1.6), (3.01, 10, "3 - 10", 2.4), (10.01, 30, "10 - 30", 3.3),
             (30.01, 100, "30 - 100", 4.3), (100.01, 300, "100 - 300", 5.5), (300.01, 1e9, "plus de 300", 7.0)]

LEGENDE_XY = (60, 252)
NOTE_XY, NOTE_WH = (60, 279), (68, 17)
FLECHE_XY = (130, 275)


# ---------------------------------------------------------------- symboles
def point(color, size=2.4, outline="white", shape="circle"):
    return QgsMarkerSymbol.createSimple({"name": shape, "color": color, "outline_color": outline,
                                         "outline_width": "0.25", "size": str(size)})


def maille(color):
    return QgsFillSymbol.createSimple({"color": color, "outline_color": "35,35,35,255", "outline_width": "0.1"})


def graduated(field, classes, symbol=maille):
    return QgsGraduatedSymbolRenderer(field, [QgsRendererRange(lo, hi, symbol(col), lab)
                                              for lo, hi, lab, col in classes])


def categorized(field, cats):
    return QgsCategorizedSymbolRenderer(field, [QgsRendererCategory(v, s, lab) for v, lab, s in cats])


def effectif_renderer(couleur_expr=None, couleur="#9e9e9e"):
    """Cercles proportionnels à l'effectif (classes fixes) ; couleur fixe ou selon une expression."""
    ranges = []
    for lo, hi, lab, size in EFFECTIFS:
        s = point(couleur, size, outline="white")
        if couleur_expr:
            s.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.PropertyFillColor,
                                                    QgsProperty.fromExpression(couleur_expr))
        ranges.append(QgsRendererRange(lo, hi, s, lab))
    r = QgsGraduatedSymbolRenderer("coalesce(\"effectif_max\", 1)", ranges)
    return r


def regles(filtre_atlas, cats, champ):
    """Rendu par règles : seules les entités de l'entité d'atlas courante, une règle par catégorie."""
    root = QgsRuleBasedRenderer.Rule(None)
    for valeur, label, sym in cats:
        root.appendChild(QgsRuleBasedRenderer.Rule(sym, filterExp=f"{filtre_atlas} and \"{champ}\" = '{valeur}'",
                                                   label=label))
    return QgsRuleBasedRenderer(root)


# ---------------------------------------------------------------- couches, groupes
def layer(table, name, subset=None, renderer=None, opacity=1.0):
    lyr = QgsVectorLayer(f"{DATA / table}.gpkg|layername={table}", name, "ogr")
    assert lyr.isValid(), f"couche invalide : {table}"
    if subset:
        lyr.setSubsetString(subset)
    if renderer:
        lyr.setRenderer(renderer)
    lyr.setOpacity(opacity)
    P.addMapLayer(lyr, False)
    return lyr


def group(name, layers, visible=False):
    names = [c.name() for c in ROOT.children()]
    g = ROOT.insertGroup(names.index("FDC"), name)
    for lyr in layers:
        g.addLayer(lyr)
    g.setItemVisibilityChecked(visible)
    return g


def relink(layer_name, table, subset=None):
    for lyr in P.mapLayersByName(layer_name):
        src_ = f"./data/{table}.gpkg|layername={table}" + (f"|subset={subset}" if subset else "")
        lyr.setDataSource(str(DATA / f"{table}.gpkg") + f"|layername={table}"
                          + (f"|subset={subset}" if subset else ""), lyr.name(), "ogr")
        assert lyr.isValid(), src_


# ---------------------------------------------------------------- mises en page
def move(item, xy, wh=None):
    item.attemptMove(QgsLayoutPoint(*xy))
    if wh:
        item.attemptResize(QgsLayoutSize(*wh))


def clone_layout(model, name, title, legend_layers, note=None, columns=1, legend_y=None, note_y=None,
                 font_size=None):
    manager = P.layoutManager()
    lay = manager.layoutByName(model).clone()
    lay.setName(name)
    manager.addLayout(lay)
    legends = [it for it in lay.items() if isinstance(it, QgsLayoutItemLegend)]
    thematic = [lg for lg in legends
                if "LEGENDE_ZONE_ETUDE" not in [n.name() for n in lg.model().rootGroup().findLayers()]]
    for lg in thematic[1:]:
        lay.removeLayoutItem(lg)
    lg = thematic[0]
    root = lg.model().rootGroup()
    root.removeAllChildren()
    for lyr, label in legend_layers:
        node = root.addLayer(lyr)
        if label is None:   # pas de titre de couche (seules les classes sont affichées)
            QgsLegendRenderer.setNodeLegendStyle(node, QgsLegendStyle.Hidden)
        else:
            node.setCustomProperty("legend/title-label", label)
    lg.setLegendFilterByMapEnabled(True)
    lg.setColumnCount(columns)
    lg.setSplitLayer(columns > 1 and len(legend_layers) == 1)
    if font_size:  # longues listes d'espèces : texte et symboles plus petits
        style = lg.style(QgsLegendStyle.SymbolLabel)
        fmt = style.textFormat()
        fmt.setSize(font_size)
        style.setTextFormat(fmt)
        lg.setStyle(QgsLegendStyle.SymbolLabel, style)
        lg.setSymbolHeight(3)
        lg.setColumnSpace(3)
    lg.setResizeToContents(True)
    lg.updateLegend()
    move(lg, (LEGENDE_XY[0], legend_y or LEGENDE_XY[1]))
    notes = []
    for it in list(lay.items()):
        if isinstance(it, QgsLayoutItemPicture) and it.id() == "Flèche du Nord":
            move(it, FLECHE_XY)
        if isinstance(it, QgsLayoutItemScaleBar):
            move(it, (147, 262))   # sous le bloc « Sources » (2 lignes)
        if not isinstance(it, QgsLayoutItemLabel):
            continue
        if it.id() == "Titre":
            it.setText(title)
        elif it.id() == "Infos sup":
            # sources réelles des données, passées par le générateur (variable de projet @sources)
            it.setText(it.text().replace("VisioNature (Réseau LPO en Auvergne-Rhône-Alpes)", "[% @sources %]"))
            move(it, (108, 243), (101, 18))
        else:
            notes.append(it)
    for it in notes[1:] if note else notes:
        lay.removeLayoutItem(it)
    if note:
        if notes:
            lab = notes[0]
        else:
            ref = next(i for i in lay.items() if isinstance(i, QgsLayoutItemLabel) and i.id() == "Infos sup")
            lab = QgsLayoutItemLabel(lay)
            lab.setFont(ref.font())
            lab.setFontColor(ref.fontColor())
            lay.addLayoutItem(lab)
        lab.setText(note)
        lab.setHAlign(Qt.AlignmentFlag.AlignLeft)
        lab.setVAlign(Qt.AlignmentFlag.AlignTop)
        move(lab, (NOTE_XY[0], note_y or NOTE_XY[1]), (NOTE_WH[0], 297 - (note_y or NOTE_XY[1]) - 1))
    return lay


def set_atlas(lay, coverage, page_name='"nom"'):
    atlas = lay.atlas()
    atlas.setCoverageLayer(coverage)
    atlas.setEnabled(True)
    atlas.setHideCoverage(True)
    atlas.setPageNameExpression(page_name)
    atlas.setSortFeatures(True)
    atlas.setSortExpression('"ordre"')
    atlas.setFilenameExpression('"cle"')
    for it in lay.items():
        if isinstance(it, QgsLayoutItemMap):
            it.setAtlasDriven(True)
            it.setAtlasScalingMode(QgsLayoutItemMap.Auto)
            it.setAtlasMargin(0.02)


# ================================================================= nettoyage du projet éolien
modeles = {"Carte1_zone_localisation", "Carte9_nidif_diurnes", "Carte17_sensibilite"}
for g in [c for c in ROOT.children() if isinstance(c, QgsLayerTreeGroup) and c.name() not in ("Zone_etude", "FDC")]:
    for node in g.findLayers():
        if not (g.name() == "Carte1_zone_localisation"):
            P.removeMapLayer(node.layerId())
    if g.name() != "Carte1_zone_localisation":
        ROOT.removeChildNode(g)

# contours 1 / 10 / 20 km (au lieu de 1 / 6 / 20 km) et zonages
for name in ("vm_eolienne_limit copier", "LEGENDE_LIMITE"):
    for lyr in P.mapLayersByName(name):
        lyr.setDataSource(str(DATA / "n2000_limit.gpkg") + "|layername=n2000_limit", lyr.name(), "ogr")
        # le projet éolien a des catégories en trop (5, 10 en double, 25 km) : on repart de 3 catégories propres,
        # avec les symboles existants (1 km tireté sombre, rose, orange)
        old = {}
        for c in lyr.renderer().categories():
            old.setdefault(c.value(), c.symbol().clone())
        tirete = QgsFillSymbol.createSimple({"style": "no", "outline_color": "#333333", "outline_width": "0.6",
                                             "outline_style": "dash"})
        rose = old.get("contour 6 km") or old.get("contour 5 km") or old.get("contour 10 km")
        lyr.setRenderer(QgsCategorizedSymbolRenderer("area_name", [
            QgsRendererCategory("contour 1 km", tirete, "Contour 1 km"),
            QgsRendererCategory("contour 10 km", rose, "Contour 10 km"),
            QgsRendererCategory("contour 20 km", old["contour 20 km"], "Contour 20 km")]))
for lyr in P.mapLayersByName("vm_eolienne_zone_protection"):
    lyr.setDataSource(str(DATA / "zones_protegees.gpkg") + "|layername=zones_protegees", lyr.name(), "ogr")
loc = ROOT.findGroup("Carte1_zone_localisation")
ROOT.removeChildNode(loc)  # recréé sous son nouveau nom (même couche de zonages)
zonages = P.mapLayersByName("vm_eolienne_zone_protection")[0]

# couvertures des atlas : présentes dans le projet, jamais affichées
cov_especes = layer("n2000_atlas_especes", "n2000_atlas_especes")
cov_chiro = layer("n2000_atlas_chiro", "n2000_atlas_chiro")
group("Couvertures_atlas", [cov_especes, cov_chiro])

# ================================================================= cartes
# 01 localisation
group("Carte01_localisation", [zonages])
clone_layout("Carte1_zone_localisation", "Carte01_localisation",
             "Localisation du site et\ndes zonages environnementaux", [(zonages, "Zonages environnementaux")])

# 02 pression d'observation : points + carte de chaleur
pts = layer("n2000_donnees", "Données brutes", subset="\"anneau_ordre\" <= 1",
            renderer=QgsSingleSymbolRenderer(point("#2b8cbe", 0.8, outline="#2b8cbe")))
heat = layer("n2000_donnees", "Concentration de données", subset="\"anneau_ordre\" <= 1")
hr = QgsHeatmapRenderer()
hr.setRadius(4)
hr.setRadiusUnit(QgsUnitTypes.RenderMillimeters)
hr.setColorRamp(QgsGradientColorRamp(QColor(255, 140, 60, 0), QColor(230, 85, 13, 255)))
heat.setRenderer(hr)
heat.setOpacity(0.9)
group("Carte02_pression_observation", [heat, pts])
clone_layout("Carte9_nidif_diurnes", "Carte02_pression_observation", "Pression d'observation",
             [(pts, "Données")], note="En orange : zones de forte concentration de données.")

# cartes de l'état des connaissances : module commun aux projets (profil éolien, texte Sources = @sources)
sys.path.insert(0, str(Path(__file__).parent))
import connaissance_qgis  # noqa: E402

connaissance_qgis.ajouter(P, DATA, "eolien", sources_variable=True)

# atlas : espèces Natura 2000 (points, statut de nidification)
filtre = "\"cd_ref\" = attribute(@atlas_feature, 'cd_ref')"
esp = layer("n2000_donnees", "Données de l'espèce",
            renderer=regles(filtre, [(v, v, point(c, 3.2)) for v, c in TYPES_DONNEE], "type_donnee"))
group("Atlas_especes_n2000", [esp])
lay = clone_layout("Carte9_nidif_diurnes", "Atlas_especes_n2000", "Localisation des données\n[% \"nom\" %]",
                   [(esp, "Type de données")])
set_atlas(lay, cov_especes)

# 04 chiroptères N2000 : présence par espèce
chiro_pts = layer("n2000_chiro_donnees", "n2000_chiro_donnees")
noms = sorted({f["nom_vern"] for f in chiro_pts.getFeatures()})
chiro_pts.setRenderer(categorized("nom_vern", [(n, n, point(PALETTE[i % len(PALETTE)], 2.6))
                                               for i, n in enumerate(noms)]))
group("Carte04_chiro_presence_n2000", [chiro_pts])
clone_layout("Carte9_nidif_diurnes", "Carte04_chiro_presence_n2000", "Présence des chiroptères\nNatura 2000",
             [(chiro_pts, "Espèces")], columns=2, legend_y=258, font_size=8)

# 05 gîtes et colonies, toutes espèces : taille = effectif, couleur = reproduction
couleur = f"if(\"reproduction\", '{BLEU_COLONIE}', '{ORANGE_GITE}')"
gites = layer("n2000_chiro_gites", "n2000_chiro_gites", renderer=effectif_renderer(couleur))
group("Carte05_chiro_gites_colonies", [gites])
clone_layout("Carte9_nidif_diurnes", "Carte05_chiro_gites_colonies", "Gîtes et colonies\nde chauves-souris connus",
             [(gites, "Effectif maximal")], columns=2, legend_y=258, note_y=287,
             note="Bleu : colonies de reproduction. Orange : gîtes sans reproduction. Toutes espèces.")

# 06 colonies par espèce (espèces d'un même gîte disposées en cercle)
col = layer("n2000_chiro_gites", "Colonies par espèce", subset="\"reproduction\"")
noms_c = sorted({f["nom_vern"] for f in col.getFeatures()})
inner = categorized("nom_vern", [(n, n, point(PALETTE[i % len(PALETTE)], 2.6)) for i, n in enumerate(noms_c)])
disp = QgsPointDisplacementRenderer()
disp.setEmbeddedRenderer(inner)
disp.setTolerance(1)
disp.setToleranceUnit(QgsUnitTypes.RenderMillimeters)
disp.setPlacement(QgsPointDisplacementRenderer.Ring)
col.setRenderer(disp)
group("Carte06_chiro_colonies_especes", [col])
clone_layout("Carte9_nidif_diurnes", "Carte06_chiro_colonies_especes", "Colonies de reproduction\nconnues par espèce",
             [(col, "Espèces")], columns=2, legend_y=258, font_size=8)

# 07 gîtes sans reproduction des espèces N2000
g_n2000 = layer("n2000_chiro_gites", "Gîtes N2000", subset="\"n2000\" and not \"reproduction\"",
                renderer=effectif_renderer(couleur=ORANGE_GITE))
group("Carte07_chiro_gites_n2000", [g_n2000])
clone_layout("Carte9_nidif_diurnes", "Carte07_chiro_gites_n2000", "Gîtes sans reproduction\ndes espèces Natura 2000",
             [(g_n2000, "Effectif maximal")], columns=2, legend_y=258)

# atlas : gîtes et colonies par espèce N2000
g_atlas = layer("n2000_chiro_gites", "Gîtes de l'espèce")
rb = QgsRuleBasedRenderer.convertFromRenderer(effectif_renderer(couleur))   # classes d'effectif + filtre atlas
for child in rb.rootRule().children():
    child.setFilterExpression(f"({child.filterExpression()}) and {filtre}")
g_atlas.setRenderer(rb)
group("Atlas_chiro_gites", [g_atlas])
lay = clone_layout("Carte9_nidif_diurnes", "Atlas_chiro_gites", "Gîtes et colonies connus\n[% \"nom\" %]",
                   [(g_atlas, "Effectif maximal")], columns=2, legend_y=258, note_y=287,
                   note="Bleu : colonies de reproduction. Orange : gîtes sans reproduction.")
set_atlas(lay, cov_chiro)

# suppression des mises en page éoliennes (modèles compris)
manager = P.layoutManager()
for lay in list(manager.layouts()):
    if not lay.name().startswith(("Carte0", "Atlas_", "Connaissance_")):
        manager.removeLayout(lay)

assert P.write(str(project_path)), "écriture impossible"
print("Projet écrit :", project_path)
print("Mises en page :", [lay.name() for lay in manager.layouts()])
print("Groupes :", [c.name() for c in ROOT.children()])
app.exitQgis()
