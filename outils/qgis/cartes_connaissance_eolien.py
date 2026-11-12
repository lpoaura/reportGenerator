"""Cartes de connaissance du projet QGIS éolien (copie : le projet source n'est pas modifié).

Usage : python-qgis-ltr.bat outils/qgis/cartes_connaissance_eolien.py <projet_eolien.qgs> <data_dir> <sortie.qgs>
  data_dir : dossier data/ d'un dry-run éolien, copié à côté du projet produit (couches valides à l'enregistrement).

- Cartes zoomées sur la zone d'étude (ZOOMS) : clones des mises en page des cartes 2 et 3, nouveau titre. La carte
  clonée garde une liste de couches figée : les couches que le moteur afficherait pour la carte d'origine (groupes
  « Zone_etude », « FDC » et groupe de la carte), dans l'ordre de rendu, avec la zone d'étude et les contours en tête.
  Les légendes (filtrées sur le contenu de la carte) restent donc justes. L'emprise (zone d'étude + marge) est réglée
  dans dossier.toml ([params.qgis_render.layout_extent_layers] et layout_buffers_m).
- Atlas « Part des espèces locales » : sans les chiffres rouges des espèces à enjeux (couche « Espèces à enjeux »
  retirée, phrase retirée de la note de légende). Illisibles avec les mailles des 20 km.
Idempotent (mises en page zoomées remplacées). Lancer ensuite limites_eolien.py, puis installer avec
integrer_projet.py. Une couche ajoutée plus tard au groupe d'une carte 2 ou 3 n'apparaît dans son zoom qu'après un
nouveau passage du script.
"""
import os
import shutil
import sys
from pathlib import Path

from qgis.core import QgsApplication, QgsLayoutItemLabel, QgsLayoutItemMap, QgsProject

# mise en page zoomée -> (mise en page d'origine, titre)
TITRE_ZOOM = "Observations oiseaux :\nzoom sur la zone d'étude"   # 2 lignes, comme les titres des autres cartes
ZOOMS = {
    "Carte2bis_Donnee_zone_etude": ("Carte2_Donnee_disponible", TITRE_ZOOM),
    "Carte3bis_Etat_connaissance_zone_etude": ("Carte3_Etat_connaissance_globale", TITRE_ZOOM),
}
GROUPES_TOUJOURS = ("Zone_etude", "FDC")          # = [params.qgis_render].visible_groups
LIMITES = ("LEGENDE_ZONE_ETUDE", "LEGENDE_LIMITE")
MARQUE_DESSUS = "reportgenerator/limites_dessus"  # copies de limites_eolien.py (pas reprises : la liste est figée)
ATLAS_GROUPE, COUCHE_ENJEUX = "Atlas_connaissance_groupes", "Espèces à enjeux"
PHRASE_ENJEUX = " Chiffre rouge : nombre d'espèces à enjeux (Natura 2000, liste rouge CR à NT)."

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
root, manager = P.layerTreeRoot(), P.layoutManager()
ordre = root.customLayerOrder() if root.hasCustomLayerOrder() else root.layerOrder()


def couches_affichees(carte):
    """Couches cochées des groupes toujours visibles et du groupe de la carte, dans l'ordre de rendu, limites en tête
    (hors copies « dessus »)."""
    ids = set()
    for nom in (*GROUPES_TOUJOURS, carte):
        groupe = root.findGroup(nom)
        assert groupe is not None, f"groupe {nom} absent"
        ids |= {n.layerId() for n in groupe.findLayers() if n.isVisible() or nom == carte and n.itemVisibilityChecked()}
    couches = [lyr for lyr in ordre if lyr.id() in ids and lyr.customProperty(MARQUE_DESSUS) is None]
    limites = [lyr for nom in LIMITES for lyr in couches if lyr.name() == nom]   # zone d'étude au-dessus
    assert len(limites) == len(LIMITES), f"limites absentes de {carte}"
    return [*limites, *[lyr for lyr in couches if lyr not in limites]]


# ---------------------------------------------------------------- cartes zoomées
for nom, (modele, titre) in ZOOMS.items():
    if manager.layoutByName(nom):
        manager.removeLayout(manager.layoutByName(nom))
    lay = manager.layoutByName(modele).clone()
    lay.setName(nom)
    couches = couches_affichees(modele)
    for it in lay.items():
        if isinstance(it, QgsLayoutItemMap):
            it.setFollowVisibilityPreset(False)
            it.setLayers(couches)
            it.setKeepLayerSet(True)
        elif isinstance(it, QgsLayoutItemLabel) and it.id() == "Titre":
            it.setText(titre)
    assert manager.addLayout(lay), f"ajout de {nom} impossible"
    print(f"{nom} : {[lyr.name() for lyr in couches]}")

# ---------------------------------------------------------------- atlas sans chiffres rouges
groupe = root.findGroup(ATLAS_GROUPE)
for node in groupe.findLayers():
    if node.layer() is not None and node.layer().name() == COUCHE_ENJEUX:
        P.removeMapLayer(node.layerId())
        print("couche retirée :", COUCHE_ENJEUX)
for it in manager.layoutByName(ATLAS_GROUPE).items():
    if isinstance(it, QgsLayoutItemLabel) and PHRASE_ENJEUX in it.text():
        it.setText(it.text().replace(PHRASE_ENJEUX, ""))
        print("note de légende :", it.text())

assert P.write(str(dst)), "écriture impossible"
print("Projet écrit :", dst)
app.exitQgis()
