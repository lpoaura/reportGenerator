"""
Brique commune des données localisées par une ligne ou un polygone (dossiers générique, éolien, Natura 2000).

La règle de prise en compte est dans la VM (queries.GEOM_ETENDUE_MAX_M : lignes et polygones de moins de 1 km
analysés à leur point représentatif, au-delà écartés). Cette brique en rend compte dans le rapport :

    TEXTE_GEOMETRIES   phrase de méthode (données sur des lignes / polygones retenues, données écartées)
    TABLE_GEOMETRIES   tableau par protocole / source et jeu de données
    Carte_transects    carte des transects et placettes par protocole (mise en page QGIS, brique cartography)

Section {{#geometries}} ... {{/geometries}} du template (carte et tableau) retirée quand aucune ligne ni aucun
polygone n'est retenu. Méthode : doc.md (« Géométries des données »).
"""

from collections import Counter

from reportgenerator.analysis.cartography.export import export_gpkg
from reportgenerator.analysis.common.models import AnalysisResult, TableBlock
from reportgenerator.analysis.common.tables.ring_table import insert_lpo_table
from reportgenerator.analysis.geometries import calculs as c
from reportgenerator.analysis.geometries.queries import GeometriesQueries
from reportgenerator.core.registry import register_brick
from reportgenerator.queries import GEOM_ETENDUE_MAX_M

CARTE = "Carte_transects"   # mise en page QGIS (même nom dans tous les dossiers)


@register_brick("geometries", requires=["socle_data"], provides=["TEXTE_GEOMETRIES", "TABLE_GEOMETRIES"])
def geometries(ctx):
    q = GeometriesQueries(ctx.queries)
    objets = q.objets()
    synthese = q.synthese()
    retenues = Counter()
    for r in synthese:
        retenues[r["type_geom"]] += int(r["nb_donnees"])
    texte = c.texte_methode(retenues, ctx.queries.geometries_exclues(), GEOM_ETENDUE_MAX_M)

    couches = c.couches(objets)
    for nom, rows in couches.items():
        export_gpkg(rows, ctx.output_dirs["data"], layer_name=nom, geom_col="geom", crs="EPSG:2154")
    if objets:
        # catégories de la carte construites sur les données (protocoles présents, couleur fournie par l'objet)
        render = dict(ctx.params.get("qgis_render") or {})
        render["categories_dynamiques"] = {**(render.get("categories_dynamiques") or {}),
                                           **{nom: ["protocole", "ordre", "couleur"] for nom in couches}}
        render["layout_extents"] = {**(render.get("layout_extents") or {}), CARTE: c.emprise(q.enveloppe())}
        ctx.params["qgis_render"] = render

    table = TableBlock(c.tableau(synthese), insert_lpo_table,
                       {"columns": c.COLONNES_TABLEAU, "widths": [1.6, 2.2, 1, 0.8, 0.8, 0.8, 1.4, 1],
                        "font_size": 8})
    return AnalysisResult(
        data={"objets": objets, "synthese": synthese, "retenues": dict(retenues),
              **{f"nb_{k}": len(v) for k, v in couches.items()}},
        meta={"sans_section": not objets},
        texts={"TEXTE_GEOMETRIES": texte},
        tables={"TABLE_GEOMETRIES": table},
    )
