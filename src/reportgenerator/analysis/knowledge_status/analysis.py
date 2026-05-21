from analysis.knowledge_status.dataviz import create_temporal_evolution_chart
from analysis.common.models import AnalysisResult

def run(context, synthese_queries, output_dirs):

    temporal_data = synthese_queries.get_resum_temporal_evolution()
    chart_path = output_dirs["dataviz"] / "evolution_temporelle.png"
    create_temporal_evolution_chart(
        temporal_data,
        str(chart_path)
    )

    return AnalysisResult(
        data={
            "temporal_data": temporal_data
        },
        files={
            "chart_evolution": chart_path
        },
        meta={
            "analysis_name": "knowledge_status"
        }
    )