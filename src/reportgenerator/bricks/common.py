"""Briques réutilisables par tous les dossiers types."""

import re
from pathlib import Path

from reportgenerator.analysis.cartography.analysis import run_cartography
from reportgenerator.analysis.common.models import AnalysisResult, ImageBlock, TableBlock
from reportgenerator.analysis.common.tables.zonage_table import insert_zonage_table
from reportgenerator.analysis.environmental_zones.summary_text import (
    build_zonage_summary_text, pivot_zonage_data)
from reportgenerator.analysis.environmental_zones.zone_presentation import \
    build_zone_presentation_text
from reportgenerator.core.registry import register_brick

QGIS_LAYOUT_RE = re.compile(r'<Layout\b[^>]*\bname="([^"]+)"')


@register_brick("socle_data")
def socle_data(ctx):
    """Vue matérialisée des observations de la zone d'étude + anneaux (paramètres du dossier)."""
    p = ctx.params
    ctx.queries.set_global_data(
        anneaux_km=p.get("anneaux_km"),
        annees=p.get("annees"),
        groupes=p.get("groupes_taxo"),
        grille=p.get("grille"),
        statuts_validation=tuple(p.get("statuts_validation", ("0", "1", "2"))),
        avec_sensibilite_eolien=p.get("sensibilite_eolien", False),
    )
    return AnalysisResult()


@register_brick(
    "zonages",
    provides=["ZONAGE_TEXTE", "ZONAGE_PRESENTATION", "TABLE_ZONAGES"],
)
def zonages(ctx):
    """Zonages environnementaux (surfaces par anneau, textes de présentation)."""
    zonage_data = pivot_zonage_data(ctx.queries.get_zonage_surfaces())
    return AnalysisResult(
        data={"zonage_data": zonage_data},
        texts={
            "ZONAGE_TEXTE": build_zonage_summary_text(zonage_data),
            "ZONAGE_PRESENTATION": build_zone_presentation_text(zonage_data),
        },
        tables={"TABLE_ZONAGES": TableBlock(zonage_data, insert_zonage_table)},
    )


def qgis_layout_names(qgis_project: Path | None) -> list[str]:
    """Noms des mises en page du projet QGIS = noms des cartes exportées."""
    if not qgis_project or not qgis_project.exists():
        return []
    return QGIS_LAYOUT_RE.findall(qgis_project.read_text(encoding="utf-8", errors="ignore"))


@register_brick(
    "cartography",
    requires=["socle_data"],
    provides=lambda dossier: qgis_layout_names(dossier.qgis_project),
)
def cartography(ctx):
    """Cartes QGIS : une image par mise en page du projet QGIS du dossier."""
    run_cartography(
        synthese_queries=ctx.queries,
        output_dirs=ctx.output_dirs,
        area_name=ctx.area_name,
        template_path=ctx.dossier.qgis_project,
        render_config=ctx.params.get("qgis_render"),
        zonage_rayon_km=ctx.params.get("zonage_rayon_km"),
    )
    layout = ctx.params.get("map_layout", "A4")
    return AnalysisResult(
        images={
            png.stem: ImageBlock(png, layout)
            for png in sorted(ctx.output_dirs["maps"].glob("*.png"))
        }
    )
