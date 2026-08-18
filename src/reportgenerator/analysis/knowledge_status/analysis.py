from reportgenerator.analysis.common.models import AnalysisResult
from reportgenerator.analysis.knowledge_status.dataviz import (
    create_temporal_evolution_chart,
    create_species_by_group_chart,
    create_data_by_group_chart,
    create_species_double_bar_chart,
    create_species_coverage_chart,
)


def run(context, synthese_queries, output_dirs):

    synthese_queries.set_global_data()

    # --- Évolution temporelle ---
    temporal_data = synthese_queries.get_resum_temporal_evolution()
    chart_evolution_path = output_dirs["dataviz"] / "chart_evolution.png"
    create_temporal_evolution_chart(temporal_data, str(chart_evolution_path))

    # --- Répartition par groupe taxonomique ---
    taxo_group_data = synthese_queries.get_resum_taxo_group()
    taxo_reference_data = synthese_queries.get_number_esp_per_taxonomy()

    chart_species_path = output_dirs["dataviz"] / "chart_species_by_group.png"
    create_species_by_group_chart(taxo_group_data, str(chart_species_path))

    chart_data_path = output_dirs["dataviz"] / "chart_data_by_group.png"
    create_data_by_group_chart(taxo_group_data, str(chart_data_path))

    chart_double_bar_path = output_dirs["dataviz"] / "chart_species_vs_pool.png"
    create_species_double_bar_chart(
        taxo_group_data, taxo_reference_data, str(chart_double_bar_path)
    )

    chart_coverage_path = output_dirs["dataviz"] / "chart_knowledge_rate.png"
    create_species_coverage_chart(
        taxo_group_data, taxo_reference_data, str(chart_coverage_path)
    )

    return AnalysisResult(
        data={
            "temporal_data": temporal_data,
            "taxo_group_data": taxo_group_data,
            "taxo_reference_data": taxo_reference_data,
        },
        files={
            "chart_evolution": chart_evolution_path,
            "chart_species_by_group": chart_species_path,
            "chart_data_by_group": chart_data_path,
            "chart_species_vs_pool": chart_double_bar_path,
            "chart_knowledge_rate": chart_coverage_path,
        },
        meta={"analysis_name": "knowledge_status"},
    )