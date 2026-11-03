"""Atlas des espèces du projet Natura 2000 : hiérarchie des symboles, ancienneté et sites de nidification récurrents.

Usage : python-qgis-ltr.bat outils/qgis/atlas_n2000_temporalite.py <projet_n2000.qgs> <data_dir> <sortie.qgs>
  data_dir : dossier data/ d'un dry-run n2000 (n2000_donnees avec « anciennete » et « ordre_dessin »,
  n2000_recurrence).
  Installer ensuite avec integrer_projet.py. Idempotent (couches de ce script remplacées).

- couche « Données de l'espèce » : couleur = type de donnée, taille croissante avec le niveau, forme = ancienneté
  (rond <= 1 an, carré 2-5 ans, triangle 6-10 ans, losange > 10 ans). Ordre de dessin : le statut prime (niveaux
  de symboles : autres < possible < probable < certain), puis, à statut égal, le champ « ordre_dessin » calculé par
  le dossier (analysis/n2000/tables.ordre_dessin : les plus récentes au-dessus) et la date. Les indices possibles
  et probables des 2 dernières saisons (ronds) ont en plus un anneau de leur couleur dessiné au-dessus de tous les
  remplissages : recouverts par un symbole de statut supérieur, ils restent visibles. (Un anneau pour toutes les
  anciennetés empâte les amas de points des lieux-dits.) ;
- couche « Sites de nidification récurrents » (n2000_recurrence) : cercle sans remplissage, contour blanc fin (liseré
  sombre pour rester visible sur fond clair), au-dessus de tout ;
- légende : bloc « Type de données » (+ site récurrent) et bloc « Ancienneté » (couche de légende jamais affichée).
"""
import os
import re
import shutil
import sys
from pathlib import Path

from qgis.core import (QgsApplication, QgsCategorizedSymbolRenderer, QgsFeatureRequest, QgsLayoutItemLegend,
                       QgsLegendRenderer, QgsLegendStyle, QgsMarkerSymbol, QgsProject, QgsProperty,
                       QgsReadWriteContext, QgsRendererCategory, QgsRuleBasedRenderer, QgsSymbolLayer, QgsVectorLayer)
from qgis.PyQt.QtXml import QDomDocument

sys.path.insert(0, str(Path(__file__).parent))
import connaissance_qgis  # noqa: E402

GROUPE, LAYOUT = "Atlas_especes_n2000", "Atlas_especes_n2000"
COUCHE_POINTS = "Données de l'espèce"
COUCHE_RECURRENCE = "Sites de nidification récurrents"
COUCHE_LEGENDE = "Ancienneté (légende)"
FILTRE = "\"cd_ref\" = attribute(@atlas_feature, 'cd_ref')"
# type de donnée : couleur (mêmes couleurs que analysis/n2000/dataviz.COULEURS_TYPES), taille (mm), passe de
# rendu du remplissage (plus haut = dessiné au-dessus), contour visible au-dessus des autres symboles
TYPES = [("Autres données", "#2b8cbe", 2.3, 0, False), ("Nicheur possible", "#fecc5c", 3.0, 1, True),
         ("Nicheur probable", "#fd8d3c", 3.3, 2, True), ("Nicheur certain", "#e31a1c", 3.7, 3, False)]
PASSE_CONTOURS = 4
CONTOUR_MM = 0.3
ANNEAU_ANCIENNETE = "tres_recent"   # anneau au-dessus des autres symboles : indices des 2 dernières saisons (ronds)
FORMES = [("tres_recent", "circle", "≤ 1 an"), ("recent", "square", "2 à 5 ans"),
          ("ancien", "triangle", "6 à 10 ans"), ("tres_ancien", "diamond", "> 10 ans")]
# (QGIS n'accepte que la forme « CASE WHEN condition THEN ... », pas « CASE champ WHEN valeur ... » ; sans entité,
# dans la légende « Type de données », l'expression vaut le ELSE : un rond)
FORME_EXPR = ("CASE " + " ".join(f"WHEN \"anciennete\" = '{c}' THEN '{f}'" for c, f, _ in FORMES)
              + " ELSE 'circle' END")

src, data_dir, dst = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
QgsApplication.setPrefixPath(os.getenv("QGIS_PREFIX_PATH", r"C:\Program Files\QGIS\3_40\apps\qgis-ltr"), True)
app = QgsApplication([], False)
app.initQgis()
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)
att = src.with_name(src.stem + "_attachments.zip")
if att.exists():
    shutil.copy2(att, dst.with_name(dst.stem + "_attachments.zip"))
# les couches du projet pointent vers ./data/ : sans ces fichiers à côté de la copie, QGIS les ouvre invalides et
# réécrit à l'enregistrement leur définition d'origine (symbologie modifiée perdue)
if (dst.parent / "data").resolve() != data_dir.resolve():
    shutil.copytree(data_dir, dst.parent / "data", dirs_exist_ok=True)
data_dir = dst.parent / "data"
P = QgsProject.instance()
assert P.read(str(dst)), "lecture du projet impossible"
root = P.layerTreeRoot()
groupe = root.findGroup(GROUPE)
assert groupe is not None, f"groupe {GROUPE} absent"
invalides = [lyr.name() for lyr in P.mapLayers().values() if not lyr.isValid() and lyr.providerType() == "ogr"]
assert not invalides, f"couches invalides (modifications non enregistrées par QGIS) : {invalides}"

# idempotence : couches ajoutées par une exécution précédente
for nom in (COUCHE_RECURRENCE, COUCHE_LEGENDE):
    for lyr in P.mapLayersByName(nom):
        P.removeMapLayer(lyr.id())


def symbole(couleur, taille, forme="circle"):
    return QgsMarkerSymbol.createSimple({"name": forme, "color": couleur, "outline_color": "white",
                                         "outline_width": "0.25", "size": str(taille)})


def couche(table, nom):
    lyr = QgsVectorLayer(f"{(data_dir / table).as_posix()}.gpkg|layername={table}", nom, "ogr")
    assert lyr.isValid(), f"couche invalide : {data_dir / table}.gpkg"
    P.addMapLayer(lyr, False)
    return lyr


# ------------------------------------------------------------------ points : type (couleur, ordre) et ancienneté
points = next(n.layer() for n in groupe.findLayers() if n.name() == COUCHE_POINTS)
racine = QgsRuleBasedRenderer.Rule(None)
for type_donnee, couleur, taille, passe, contour in reversed(TYPES):   # légende : certain en tête
    sym = symbole(couleur, taille)
    sym.symbolLayer(0).setDataDefinedProperty(QgsSymbolLayer.PropertyName, QgsProperty.fromExpression(FORME_EXPR))
    sym.symbolLayer(0).setRenderingPass(passe)
    if contour:   # anneau de la couleur du type, au-dessus de tous les remplissages, données récentes seulement
        trait = QgsMarkerSymbol.createSimple({"name": "circle", "color": "0,0,0,0", "outline_color": couleur,
                                              "outline_width": str(CONTOUR_MM), "size": str(taille - 0.5)})
        sym.appendSymbolLayer(trait.symbolLayer(0).clone())
        anneau = sym.symbolLayer(1)   # (réglages après l'ajout : clone() ne copie pas la passe de rendu)
        anneau.setRenderingPass(PASSE_CONTOURS)
        anneau.setDataDefinedProperty(QgsSymbolLayer.PropertyLayerEnabled,
                                      QgsProperty.fromExpression(f"\"anciennete\" = '{ANNEAU_ANCIENNETE}'"))
    racine.appendChild(QgsRuleBasedRenderer.Rule(sym, label=type_donnee,
                                                 filterExp=f"{FILTRE} and \"type_donnee\" = '{type_donnee}'"))
rendu = QgsRuleBasedRenderer(racine)
rendu.setUsingSymbolLevels(True)
rendu.setOrderBy(QgsFeatureRequest.OrderBy([QgsFeatureRequest.OrderByClause('"ordre_dessin"', True),
                                            QgsFeatureRequest.OrderByClause('"date"', True)]))
rendu.setOrderByEnabled(True)
points.setRenderer(rendu)

# ------------------------------------------------------------------ sites de nidification récurrents
recurrence = couche("n2000_recurrence", COUCHE_RECURRENCE)
cercle = QgsMarkerSymbol.createSimple({"name": "circle", "color": "0,0,0,0", "outline_color": "60,60,60,160",
                                       "outline_width": "0.8", "size": "6"})
blanc = QgsMarkerSymbol.createSimple({"name": "circle", "color": "0,0,0,0", "outline_color": "white",
                                      "outline_width": "0.35", "size": "6"})
cercle.appendSymbolLayer(blanc.symbolLayer(0).clone())
racine_r = QgsRuleBasedRenderer.Rule(None)
racine_r.appendChild(QgsRuleBasedRenderer.Rule(cercle, label="Site récurrent (≥ 3 ans)", filterExp=FILTRE))
recurrence.setRenderer(QgsRuleBasedRenderer(racine_r))
groupe.insertLayer(0, recurrence)                       # au-dessus des points

# ------------------------------------------------------------------ couche de légende « Ancienneté » (jamais affichée)
legende = couche("n2000_donnees", COUCHE_LEGENDE)
legende.setSubsetString("1 = 0")
legende.setRenderer(QgsCategorizedSymbolRenderer("anciennete", [
    QgsRendererCategory(code, symbole("#7f7f7f", 3.0, forme), libelle) for code, forme, libelle in FORMES]))
couvertures = root.findGroup("Couvertures_atlas") or root
couvertures.addLayer(legende)

# ------------------------------------------------------------------ légendes de la mise en page
lay = P.layoutManager().layoutByName(LAYOUT)
lg = next(it for it in lay.items() if isinstance(it, QgsLayoutItemLegend)
          and COUCHE_POINTS in [n.name() for n in it.model().rootGroup().findLayers()])
for it in [it for it in lay.items() if isinstance(it, QgsLayoutItemLegend) and it is not lg
           and COUCHE_LEGENDE in [n.name() for n in it.model().rootGroup().findLayers()]]:
    lay.removeLayoutItem(it)                            # bloc « Ancienneté » d'une exécution précédente
racine_lg = lg.model().rootGroup()
racine_lg.removeAllChildren()
racine_lg.addLayer(points).setCustomProperty("legend/title-label", "Type de données")
QgsLegendRenderer.setNodeLegendStyle(racine_lg.addLayer(recurrence), QgsLegendStyle.Hidden)
lg.setColumnCount(1)
style = lg.style(QgsLegendStyle.SymbolLabel)   # texte 8 pt (comme les autres légendes du projet)
fmt = style.textFormat()
fmt.setSize(8)
style.setTextFormat(fmt)
lg.setStyle(QgsLegendStyle.SymbolLabel, style)
lg.setSymbolHeight(3)
lg.updateLegend()

# bloc « Ancienneté » : copie de la légende (même style), sans filtre par la carte (la couche n'a aucune entité)
doc = QDomDocument()
conteneur = doc.createElement("copie")
lg.writeXml(conteneur, doc, QgsReadWriteContext())
copie = next(it for it in lay.addItemsFromXml(conteneur, doc, QgsReadWriteContext())
             if isinstance(it, QgsLayoutItemLegend))
racine_a = copie.model().rootGroup()
racine_a.removeAllChildren()
racine_a.addLayer(legende).setCustomProperty("legend/title-label", "Ancienneté")
copie.setLegendFilterByMapEnabled(False)
copie.setResizeToContents(True)
copie.updateLegend()
connaissance_qgis._move(copie, (101, 262))

connaissance_qgis.fixer_ordre_rendu(P, connaissance_qgis.couches_connaissance(P))
assert P.write(str(dst)), "écriture impossible"
# sources des couches lues dans data_dir (chemin absolu ou relatif écrit par QGIS) -> ./data/<couche>.gpkg
texte = re.sub(r'[^"<>|=]*?[/\\](n2000_recurrence|n2000_donnees)\.gpkg', r"./data/\1.gpkg",
               dst.read_text(encoding="utf-8"))
dst.write_text(texte, encoding="utf-8")
print("Projet écrit :", dst)
app.exitQgis()
