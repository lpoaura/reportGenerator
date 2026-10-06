"""Briques du rapport générique (état des connaissances)."""

from datetime import datetime

import pandas as pd

from reportgenerator.analysis.atlas.analysis import run_atlas
from reportgenerator.analysis.common.models import AnalysisResult, ImageBlock, TableBlock
from reportgenerator.analysis.common.tables.excel_export import export_species_excel
from reportgenerator.analysis.common.tables.generic_table import insert_general_table
from reportgenerator.analysis.common.tables.species_table import insert_species_table
from reportgenerator.analysis.knowledge_status.analysis import run as run_knowledge_status
from reportgenerator.analysis.knowledge_status.summary_text import TEXTE_CONNAISSANCE
from reportgenerator.core.registry import register_brick

KNOWLEDGE_CHARTS = [
    "chart_evolution",
    "chart_species_by_group",
    "chart_data_by_group",
    "chart_species_vs_pool",
    "chart_knowledge_rate",
    "chart_disparition",
]

COLUMNS_TAXO = [
    ("Groupe taxo.", "group_taxo"),
    ("Nombre\nde données", "nb_data_tot"),
    ("Nombre\nd'espèces", "nb_espece"),
    ("Espèces\nnicheuses", "nb_espece_nicheuse"),
    ("Espèces\nprotégées", "nb_espece_protege"),
    ("Espèces\nen danger", "nb_espece_lr"),
]

LR_STATUS_COLS = ["lr_aura", "lr_fr_nich", "lr_fr_hiv", "lr_fr_migr"]
LR_THREATENED = ["CR", "EN", "VU", "NT"]


def _fmt(value) -> str:
    return f"{value:,}".replace(",", " ")


@register_brick(
    "knowledge_status",
    requires=["socle_data"],
    provides=["TEXTE_CONNAISSANCE", *KNOWLEDGE_CHARTS],
)
def knowledge_status(ctx):
    """État des connaissances : graphiques temporels et par groupe taxonomique."""
    result = run_knowledge_status(
        context=ctx, synthese_queries=ctx.queries, output_dirs=ctx.output_dirs
    )
    result.texts["TEXTE_CONNAISSANCE"] = TEXTE_CONNAISSANCE
    for key in KNOWLEDGE_CHARTS:
        if result.files[key].exists():
            result.images[key] = ImageBlock(result.files[key], "normal")
    return result


@register_brick(
    "synthese_generale",
    requires=["knowledge_status"],
    provides=[
        "AREA_NAME", "REFEREE", "DATE_REPORT", "BUFFER", "NB_DATA",
        "NB_OBS_ZONE", "NB_SPECIES_ZONE", "LAST_OBS_ZONE",
        "NB_OBS_BUFFER", "NB_SPECIES_BUFFER", "LAST_OBS_BUFFER",
        "NB_OBS_GLOBAL", "NB_SPECIES_GLOBAL", "LAST_OBS_GLOBAL",
        "TABLE_TAXO", "TABLE_ESP", "TABLE_ESP_LR",
    ],
)
def synthese_generale(ctx):
    """Chiffres clés par secteur, tableaux taxons / espèces, export Excel."""
    taxo_data = ctx.results["knowledge_status"].data["taxo_group_data"]
    species = ctx.queries.get_species_data()
    resum = {row["secteur"]: row for row in ctx.queries.get_resum_data()}

    year = datetime.now().year
    texts = {
        "AREA_NAME": ctx.area_name,
        "REFEREE": ctx.referee,
        "DATE_REPORT": f"({year - 10}-{year})",
        "BUFFER": ctx.buffer,
        "NB_DATA": _fmt(sum(row["nb_data_tot"] or 0 for row in taxo_data)),
    }
    for secteur, suffix in (("zone_etude", "ZONE"), ("buffer_seul", "BUFFER"), ("ensemble", "GLOBAL")):
        row = resum[secteur]
        texts[f"NB_OBS_{suffix}"] = _fmt(row["nb_observations"])
        texts[f"NB_SPECIES_{suffix}"] = _fmt(row["nb_especes"])
        texts[f"LAST_OBS_{suffix}"] = str(row["derniere_observation"])

    species_df = pd.DataFrame(species)
    if species_df.empty:
        species_lr = []
    else:
        mask = species_df[LR_STATUS_COLS].isin(LR_THREATENED).any(axis=1)
        species_lr = species_df[mask].to_dict(orient="records")

    excel_path = ctx.output_dirs["tables"] / "tableau_especes.xlsx"
    export_species_excel(data=species, output_path=excel_path)

    return AnalysisResult(
        data={"species": species, "resum": resum},
        files={"tableau_especes": excel_path},
        texts=texts,
        tables={
            "TABLE_TAXO": TableBlock(taxo_data, insert_general_table, {"columns": COLUMNS_TAXO}),
            "TABLE_ESP": TableBlock(species, insert_species_table),
            "TABLE_ESP_LR": TableBlock(species_lr, insert_species_table),
        },
    )


@register_brick("atlas_nicheur", requires=["socle_data"])
def atlas_nicheur(ctx):
    """Atlas des espèces nicheuses (PNG par espèce dans atlas/, hors Word pour l'instant)."""
    files = run_atlas(
        synthese_queries=ctx.queries,
        output_dirs=ctx.output_dirs,
        area_name=ctx.area_name,
        run_render=True,
    )
    return AnalysisResult(files=files)
