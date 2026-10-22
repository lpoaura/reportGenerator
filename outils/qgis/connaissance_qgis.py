"""Cartes de l'état des connaissances (briques connaissance*) ajoutées à un projet QGIS existant, dans sa charte.

    ajouter(P, data_dir, profil, sources_variable=False)

Couches connaissance_mailles, connaissance_grille, connaissance_atlas_groupes (lues dans data_dir pour la
construction, enregistrées en ./data/<couche>.gpkg comme les autres couches des projets), et un groupe + une mise
en page par carte : Connaissance_effort_donnees, Connaissance_effort_jours, Atlas_connaissance_groupes,
Atlas_connaissance_croisee. Idempotent : groupes, couches et mises en page de ces noms sont remplacés.

Profils :
  eolien     charte du projet éolien (modèle Carte17_sensibilite) ; aussi pour Natura 2000 (construit depuis
             le projet éolien). sources_variable : texte « Sources » = variable @sources (Natura 2000).
  generique  projet_modele.qgs (modèle statut_connaissance : titre HTML, une seule légende à colonnes).
"""
import re

from qgis.core import (Qgis, QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsLayoutItemHtml,
                       QgsLayoutItemLabel, QgsLayoutItemLegend, QgsLayoutItemMap, QgsLayoutItemPicture,
                       QgsLayoutItemScaleBar, QgsLayoutItemShape, QgsLayoutPoint, QgsLayoutSize, QgsLegendRenderer,
                       QgsLegendStyle, QgsLinePatternFillSymbolLayer, QgsPalLayerSettings, QgsRendererRange,
                       QgsRuleBasedRenderer, QgsSingleSymbolRenderer, QgsTextBackgroundSettings, QgsTextFormat,
                       QgsVectorLayer, QgsVectorLayerSimpleLabeling)
from qgis.PyQt.QtCore import QSizeF, Qt
from qgis.PyQt.QtGui import QColor

LAYOUTS = ("Connaissance_effort_donnees", "Connaissance_effort_jours", "Atlas_connaissance_groupes",
           "Atlas_connaissance_croisee")
COUCHES = ("connaissance_mailles", "connaissance_grille", "connaissance_atlas_groupes")
VIRIDIS_5 = ["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"]
INSUFFISANT = "#9e9e9e"
# palette bivariée 3 x 3 (effort en lignes, richesse en colonnes)
BIV = {"e0r0": "#e8e8e8", "e0r1": "#e4acac", "e0r2": "#c85a5a",
       "e1r0": "#b0d5df", "e1r1": "#ad9ea5", "e1r2": "#985356",
       "e2r0": "#64acbe", "e2r1": "#627f8c", "e2r2": "#574249"}
ATLAS_G = "\"groupe\" = attribute(@atlas_feature, 'groupe')"

# charte éolien : positions (mm) de la légende thématique et de la note, reprises du dossier Natura 2000
EOL_LEGENDE_X, EOL_NOTE_X, EOL_NOTE_W, EOL_FLECHE_XY = 60, 60, 68, (130, 275)


def _move(item, xy, wh=None):
    item.attemptMove(QgsLayoutPoint(*xy))
    if wh:
        item.attemptResize(QgsLayoutSize(*wh))


def _maille(color):
    return QgsFillSymbol.createSimple({"color": color, "outline_color": "35,35,35,255", "outline_width": "0.1"})


class _Projet:
    def __init__(self, P, data_dir, profil, sources_variable):
        self.P, self.data, self.profil, self.sources_variable = P, data_dir, profil, sources_variable
        self.root = P.layerTreeRoot()
        self.ajoutees = []

    def ordre_rendu(self):
        """Couches ajoutées dessinées juste SOUS les contours de la zone d'étude (sinon les mailles opaques les
        cachent) : ordre de rendu personnalisé = ordre actuel, couches ajoutées déplacées après la dernière couche
        de contour affichée (groupe FDC : éolien LEGENDE_ZONE_ETUDE / LEGENDE_LIMITE, générique zone et périmètre,
        limites administratives dans les deux cas)."""
        noms = ("LEGENDE_ZONE_ETUDE", "LEGENDE_LIMITE", "Zone d'étude", "Périmètre d'étude", "LEGENDE_Région",
                "LEGENDE_Départements")
        zone = {n.layerId() for n in self.root.findLayers() if n.name() in noms}
        ordre = self.root.customLayerOrder() if self.root.hasCustomLayerOrder() else self.root.layerOrder()
        ids = {lyr.id() for lyr in self.ajoutees}
        nouveaux = [lyr for lyr in ordre if lyr.id() in ids]
        reste = [lyr for lyr in ordre if lyr.id() not in ids]
        pos = max((i for i, lyr in enumerate(reste) if lyr.id() in zone), default=-1) + 1
        self.root.setCustomLayerOrder(reste[:pos] + nouveaux + reste[pos:])
        self.root.setHasCustomLayerOrder(True)

    # ---------------------------------------------------------------- nettoyage (idempotent)
    def nettoyer(self):
        manager = self.P.layoutManager()
        for name in LAYOUTS:
            lay = manager.layoutByName(name)
            if lay:
                manager.removeLayout(lay)
        for name in (*LAYOUTS, "Couvertures_connaissance"):
            g = self.root.findGroup(name)
            if g:
                for node in g.findLayers():
                    self.P.removeMapLayer(node.layerId())
                self.root.removeChildNode(g)

    # ---------------------------------------------------------------- couches et groupes
    def layer(self, table, name, subset=None, renderer=None, opacity=1.0):
        lyr = QgsVectorLayer(f"{(self.data / table).as_posix()}.gpkg|layername={table}", name, "ogr")
        assert lyr.isValid(), f"couche invalide : {self.data / table}.gpkg"
        if subset:
            lyr.setSubsetString(subset)
        if renderer:
            lyr.setRenderer(renderer)
        lyr.setOpacity(opacity)
        self.P.addMapLayer(lyr, False)
        self.ajoutees.append(lyr)
        return lyr

    def group(self, name, layers):
        names = [c.name() for c in self.root.children()]
        g = self.root.insertGroup(names.index("FDC") if "FDC" in names else len(names), name)
        for lyr in layers:
            g.addLayer(lyr)
        g.setItemVisibilityChecked(False)
        return g

    def grille_vide(self, nom):
        """Mailles de l'emprise sans donnée (fond), pour distinguer « aucune donnée » de « hors zone »."""
        sym = QgsFillSymbol.createSimple({"color": "255,255,255,90", "outline_color": "#9e9e9e",
                                          "outline_width": "0.1"})
        return self.layer("connaissance_grille", nom, renderer=QgsSingleSymbolRenderer(sym))

    # ---------------------------------------------------------------- mises en page
    def clone(self, name, title, legend_layers, note=None, **kw):
        return (self._clone_eolien if self.profil == "eolien" else self._clone_generique)(
            name, title, legend_layers, note, **kw)

    def _legende_thematique(self, lg, legend_layers, font_size):
        root = lg.model().rootGroup()
        # générique : couches thématiques en tête de la légende commune (insérées à l'envers en position 0)
        for lyr, label in (reversed(legend_layers) if self.profil == "generique" else legend_layers):
            node = root.insertLayer(0, lyr) if self.profil == "generique" else root.addLayer(lyr)
            if label is None:   # pas de titre de couche (seules les classes sont affichées)
                QgsLegendRenderer.setNodeLegendStyle(node, QgsLegendStyle.Hidden)
            else:
                node.setCustomProperty("legend/title-label", label)
        lg.setLegendFilterByMapEnabled(True)
        if font_size:
            style = lg.style(QgsLegendStyle.SymbolLabel)
            fmt = style.textFormat()
            fmt.setSize(font_size)
            style.setTextFormat(fmt)
            lg.setStyle(QgsLegendStyle.SymbolLabel, style)
            lg.setSymbolHeight(3)
            lg.setColumnSpace(3)
        lg.setResizeToContents(True)
        lg.updateLegend()

    def _note(self, lay, ref_label, note, xy, wh):
        lab = QgsLayoutItemLabel(lay)
        lab.setTextFormat(ref_label.textFormat())
        fmt = lab.textFormat()
        fmt.setSize(7)
        lab.setTextFormat(fmt)
        lab.setText(note)
        lab.setHAlign(Qt.AlignmentFlag.AlignLeft)
        lab.setVAlign(Qt.AlignmentFlag.AlignTop)
        lay.addLayoutItem(lab)
        _move(lab, xy, wh)
        return lab

    def _clone_eolien(self, name, title, legend_layers, note, columns=1, legend_y=252, note_y=279, font_size=None):
        """Clone de Carte17_sensibilite (mêmes réglages que les cartes du dossier Natura 2000)."""
        manager = self.P.layoutManager()
        lay = manager.layoutByName("Carte17_sensibilite").clone()
        lay.setName(name)
        manager.addLayout(lay)
        legends = [it for it in lay.items() if isinstance(it, QgsLayoutItemLegend)]
        thematic = [lg for lg in legends
                    if "LEGENDE_ZONE_ETUDE" not in [n.name() for n in lg.model().rootGroup().findLayers()]]
        for lg in thematic[1:]:
            lay.removeLayoutItem(lg)
        lg = thematic[0]
        lg.model().rootGroup().removeAllChildren()
        self._legende_thematique(lg, legend_layers, font_size)
        lg.setColumnCount(columns)
        _move(lg, (EOL_LEGENDE_X, legend_y))
        notes = []
        for it in list(lay.items()):
            if isinstance(it, QgsLayoutItemPicture) and it.id() == "Flèche du Nord":
                _move(it, EOL_FLECHE_XY)
            if isinstance(it, QgsLayoutItemScaleBar):
                _move(it, (147, 262))   # sous le bloc « Sources » (2 lignes)
            if not isinstance(it, QgsLayoutItemLabel):
                continue
            if it.id() == "Titre":
                it.setText(title)
            elif it.id() == "Infos sup":
                if self.sources_variable:
                    it.setText(it.text().replace("VisioNature (Réseau LPO en Auvergne-Rhône-Alpes)", "[% @sources %]"))
                _move(it, (108, 243), (101, 18))
                infos = it
            else:
                notes.append(it)
        for it in notes:
            lay.removeLayoutItem(it)
        if note:
            self._note(lay, infos, note, (EOL_NOTE_X, note_y), (EOL_NOTE_W, 297 - note_y - 1))
        return lay

    def _clone_generique(self, name, title, legend_layers, note, columns=2, legend_y=None, note_y=284,
                         font_size=8, legend_x=None):
        """Clone de statut_connaissance (projet générique) : titre HTML, légende unique à colonnes (couches
        thématiques en tête, zone d'étude et limites administratives gardées)."""
        manager = self.P.layoutManager()
        lay = manager.layoutByName("statut_connaissance").clone()
        lay.setName(name)
        manager.addLayout(lay)
        for mf in lay.multiFrames():
            if isinstance(mf, QgsLayoutItemHtml):
                lignes = title.split("\n")
                if len(lignes) > 1:   # deux lignes : taille et cadre des titres à deux lignes (observations_brutes)
                    mf.setUserStylesheet(mf.userStylesheet().replace("font-size: 23px", "font-size: 18px"))
                    _move(mf.frame(0), (5.7, 1.0), (140.3, 19.4))
                mf.setEvaluateExpressions(True)
                mf.setHtml("<br>\n".join(lignes))
                mf.loadHtml()
        lg = next(it for it in lay.items() if isinstance(it, QgsLayoutItemLegend))
        root = lg.model().rootGroup()
        modele = {n.layer().id() for n in root.findLayers() if n.layer() and n.name() == "statut_connaissance"}
        for node in [n for n in root.findLayers() if n.layer() and n.layer().id() in modele]:
            node.parent().removeChildNode(node)
        self._legende_thematique(lg, legend_layers, font_size)
        lg.setSplitLayer(False)
        lg.setColumnCount(columns)
        if legend_layers and len(root.children()) > len(legend_layers):
            # 1re colonne : couches thématiques ; 2e : zone d'étude et limites administratives
            root.children()[len(legend_layers)].setCustomProperty("legend/column-break", "1")
            lg.updateLegend()
        if legend_x is not None or legend_y is not None:
            pos = lg.positionWithUnits()
            _move(lg, (legend_x if legend_x is not None else pos.x(), legend_y if legend_y is not None else pos.y()))
        infos = next(it for it in lay.items() if isinstance(it, QgsLayoutItemLabel) and it.id() == "Infos sup")
        if note:
            self._note(lay, infos, note, (2, note_y), (86, 297 - note_y - 1))
        return lay

    def set_atlas(self, lay, coverage):
        atlas = lay.atlas()
        atlas.setCoverageLayer(coverage)
        atlas.setEnabled(True)
        atlas.setHideCoverage(True)
        atlas.setPageNameExpression('"groupe"')
        atlas.setSortFeatures(True)
        atlas.setSortExpression('"ordre"')
        atlas.setFilenameExpression('"cle"')
        for it in lay.items():
            if isinstance(it, QgsLayoutItemMap):
                it.setAtlasDriven(True)
                it.setAtlasScalingMode(QgsLayoutItemMap.Auto)
                # générique : la carte passe sous le bandeau du titre, d'où une marge plus large
                it.setAtlasMargin(0.10 if self.profil == "generique" else 0.02)


def _texte(lay, txt, xy, wh, taille=6.5, gras=False):
    lab = QgsLayoutItemLabel(lay)
    f = QgsTextFormat()
    f.setSize(taille)
    f.setColor(QColor("white"))
    if gras:
        font = f.font()
        font.setBold(True)
        f.setFont(font)
    lab.setTextFormat(f)
    lab.setText(txt)
    lay.addLayoutItem(lab)
    _move(lab, xy, wh)


def _matrice(lay, x0, y0, c):
    """Légende de la carte croisée : matrice 3 x 3 (effort en lignes, richesse en colonnes)."""
    for code, col in BIV.items():
        e, r = int(code[1]), int(code[3])
        case = QgsLayoutItemShape(lay)
        case.setShapeType(QgsLayoutItemShape.Rectangle)
        case.setSymbol(QgsFillSymbol.createSimple({"color": col, "outline_color": "white", "outline_width": "0.2"}))
        lay.addLayoutItem(case)
        _move(case, (x0 + r * c, y0 + (2 - e) * c), (c, c))
    _texte(lay, "Effort de prospection (jours)", (x0 - 13, y0 - 5), (45, 5), 7, True)
    for i, t_ in enumerate(("10 j et +", "3 - 9 j", "1 - 2 j")):
        _texte(lay, t_, (x0 - 13, y0 + i * c + 2), (12, 4))
    for i, t_ in enumerate(("<25 %", "25-50 %", ">50 %")):
        _texte(lay, t_, (x0 + i * c + 0.3, y0 + 3 * c + 0.3), (c, 4), 5.5)
    _texte(lay, "Part des espèces connues localement", (x0 - 4, y0 + 3 * c + 3.5), (50, 5), 7, True)


def filtrer_zone_etude(P):
    """Charte éolien : LEGENDE_ZONE_ETUDE lit zone_etude.gpkg, qui contient aussi le tampon de la demande et les
    50 km autour (brique cartography) : seule la zone d'étude doit être tracée (comme dans le projet générique)."""
    for lyr in P.mapLayersByName("LEGENDE_ZONE_ETUDE"):
        src = lyr.source()
        if "layername=zone_etude" in src and "subset=" not in src:
            lyr.setDataSource(src + "|subset=\"secteur\" = 'Zone d''étude'", lyr.name(), "ogr")


def ajouter(P, data_dir, profil, sources_variable=False):
    pr = _Projet(P, data_dir, profil, sources_variable)
    pr.nettoyer()
    if profil == "eolien":
        filtrer_zone_etude(P)
    cov = pr.layer("connaissance_atlas_groupes", "connaissance_atlas_groupes")
    pr.group("Couvertures_connaissance", [cov])
    gen = profil == "generique"

    # ------------------------------------------------------------ cartes d'effort (tous groupes analysés)
    for nom_lay, champ, titre, classes, note in [
            (LAYOUTS[0], "nb_donnees", "Nombre de données\npar maille de 1 km",
             [(0, 1, "1 donnée (connaissance insuffisante)", INSUFFISANT), (2, 5, "2 - 5 données", VIRIDIS_5[1]),
              (6, 20, "6 - 20 données", VIRIDIS_5[2]), (21, 100, "21 - 100 données", VIRIDIS_5[3]),
              (101, 1e9, "plus de 100 données", VIRIDIS_5[4])],
             "Groupes étudiés. Mailles blanches : aucune donnée."),
            (LAYOUTS[1], "nb_jours", "Nombre de jours d'observation\npar maille de 1 km",
             [(0, 1, "1 jour", INSUFFISANT), (2, 3, "2 - 3 jours", VIRIDIS_5[1]), (4, 10, "4 - 10 jours", VIRIDIS_5[2]),
              (11, 30, "11 - 30 jours", VIRIDIS_5[3]), (31, 1e9, "plus de 30 jours", VIRIDIS_5[4])],
             "Groupes étudiés. Nombre de dates différentes avec au moins une donnée (effort de prospection).")]:
        eff = pr.layer("connaissance_mailles", "Effort", subset="\"groupe\" = 'Tous groupes'",
                       renderer=QgsGraduatedSymbolRenderer(champ, [QgsRendererRange(lo, hi, _maille(col), lab)
                                                                   for lo, hi, lab, col in classes]), opacity=0.85)
        pr.group(nom_lay, [eff, pr.grille_vide("Mailles sans donnée")])
        if gen:
            pr.clone(nom_lay, titre, [(eff, "Effort de prospection")], note=note)
        else:
            pr.clone(nom_lay, titre, [(eff, None)], note=note, legend_y=256, note_y=284, font_size=8)

    # ------------------------------------------------------------ atlas : part des espèces connues localement
    classes_pct = [(0, 10, "< 10 %"), (10, 25, "10 - 25 %"), (25, 50, "25 - 50 %"), (50, 75, "50 - 75 %"),
                   (75, 1000, "> 75 %")]
    root = QgsRuleBasedRenderer.Rule(None)
    for (lo, hi, lab), col in zip(classes_pct, VIRIDIS_5):
        filtre = f"{ATLAS_G} and \"pct_pool_local\" >= {lo} and \"pct_pool_local\" < {hi}"
        root.appendChild(QgsRuleBasedRenderer.Rule(_maille(col), label=lab, filterExp=filtre))
    richesse = pr.layer("connaissance_mailles", "Part des espèces", renderer=QgsRuleBasedRenderer(root), opacity=0.9)
    hach = QgsFillSymbol.createSimple({"style": "no", "outline_style": "no"})
    lp = QgsLinePatternFillSymbolLayer()
    lp.setLineAngle(45)
    lp.setDistance(1.2)
    lp.setLineWidth(0.25)
    lp.setColor(QColor("#ffffff"))
    hach.changeSymbolLayer(0, lp)
    root_h = QgsRuleBasedRenderer.Rule(None)
    root_h.appendChild(QgsRuleBasedRenderer.Rule(hach, label="moins de 2 données (lecture prudente)",
                                                 filterExp=f"{ATLAS_G} and \"peu_donnees\""))
    hachures = pr.layer("connaissance_mailles", "Hachures", renderer=QgsRuleBasedRenderer(root_h))
    # nombre d'espèces à enjeux : étiquette rouge au centre de la maille
    enjeux = pr.layer("connaissance_mailles", "Espèces à enjeux", renderer=QgsSingleSymbolRenderer(
        QgsFillSymbol.createSimple({"style": "no", "outline_style": "no"})))
    fmt = QgsTextFormat()
    fmt.setSize(7)
    fmt.setColor(QColor("white"))
    fond = QgsTextBackgroundSettings()
    fond.setEnabled(True)
    fond.setType(QgsTextBackgroundSettings.ShapeCircle)
    fond.setFillColor(QColor("#d7191c"))
    fond.setStrokeColor(QColor("#d7191c"))
    fond.setSizeType(QgsTextBackgroundSettings.SizeBuffer)
    fond.setSize(QSizeF(0.6, 0.6))
    fmt.setBackground(fond)
    lbl = QgsPalLayerSettings()
    lbl.isExpression = True
    lbl.fieldName = f"if({ATLAS_G} and \"nb_enjeux\" > 0, \"nb_enjeux\", NULL)"
    lbl.setFormat(fmt)
    lbl.placement = Qgis.LabelPlacement.OverPoint
    enjeux.setLabeling(QgsVectorLayerSimpleLabeling(lbl))
    enjeux.setLabelsEnabled(True)
    pr.group(LAYOUTS[2], [enjeux, hachures, richesse, pr.grille_vide("Mailles sans donnée du groupe")])
    note = ("Référence : [% \"pool_local\" %] espèces du groupe connues à moins de [% @pool_local_km %] km. "
            "Chiffre rouge : nombre d'espèces à enjeux (Natura 2000, liste rouge CR à NT).")
    titre = "Part des espèces locales\n[% \"groupe\" %]"
    if gen:
        lay = pr.clone(LAYOUTS[2], titre, [(richesse, "Part des espèces locales"), (hachures, None)], note=note)
    else:
        lay = pr.clone(LAYOUTS[2], titre, [(richesse, "Part des espèces locales"), (hachures, None)], note=note,
                       legend_y=250, note_y=284, font_size=8)
    pr.set_atlas(lay, cov)

    # ------------------------------------------------------------ atlas : lecture croisée richesse x effort
    root_b = QgsRuleBasedRenderer.Rule(None)
    for code, col in BIV.items():
        root_b.appendChild(QgsRuleBasedRenderer.Rule(_maille(col), label=code,
                                                     filterExp=f"{ATLAS_G} and \"classe_croisee\" = '{code}'"))
    croisee = pr.layer("connaissance_mailles", "Richesse x effort", renderer=QgsRuleBasedRenderer(root_b))
    pr.group(LAYOUTS[3], [croisee, pr.grille_vide("Mailles sans donnée du groupe")])
    note = ("Clair : peu prospecté. Bleu : prospecté, peu d'espèces. Rouge : riche malgré peu de prospection. "
            "Foncé : prospecté et riche.")
    titre = "Richesse et prospection\n[% \"groupe\" %]"
    if gen:
        # légende : zone d'étude et limites seulement (à droite de la matrice)
        lay = pr.clone(LAYOUTS[3], titre, [], note=note, columns=1, legend_x=64, note_y=288)
        _matrice(lay, 16, 254, 8)
    else:
        lay = pr.clone(LAYOUTS[3], titre, [(croisee, "")], note=note, legend_y=258, note_y=286)
        for it in list(lay.items()):   # légende par catégorie remplacée par la matrice
            if isinstance(it, QgsLayoutItemLegend) and "LEGENDE_ZONE_ETUDE" not in [
                    n.name() for n in it.model().rootGroup().findLayers()]:
                lay.removeLayoutItem(it)
        _matrice(lay, 73, 251, 8)
    pr.set_atlas(lay, cov)
    pr.ordre_rendu()
    return [n for n in LAYOUTS if P.layoutManager().layoutByName(n)]


def chemins_relatifs(qgs_text: str, data_dir=None) -> str:
    """Sources des couches connaissance_* : chemin de construction (absolu ou relatif, écrit par QGIS) ->
    ./data/<couche>.gpkg (convention des projets ; redirigé vers le dossier du rapport au rendu)."""
    return re.sub(r'[^"<>|=]*?[/\\](' + "|".join(COUCHES) + r')\.gpkg', r"./data/\1.gpkg", qgs_text)
