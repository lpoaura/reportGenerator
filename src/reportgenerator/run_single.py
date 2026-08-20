"""
run_single.py

Contient la logique de génération d'UN rapport.
Utilisé aussi bien par le mode "run" (unitaire) que par le mode "generate" (batch).
"""

from pathlib import Path
from datetime import datetime

from reportgenerator.analysis.atlas.analysis import run_atlas
from reportgenerator.analysis.cartography.analysis import run_cartography
from reportgenerator.analysis.common.filesystem import create_analysis_dirs
from reportgenerator.analysis.knowledge_status.analysis import run as run_knowledge_status
from reportgenerator.db_auth import get_connection
from reportgenerator.queries import SyntheseQueries
from reportgenerator.report import generate_report
from reportgenerator.analysis.common.timing import RunTimer 


def run_single_report(
    *,
    service_name: str,
    id_area: int,
    referee: str,
    list_analyse: str,
    buffer: int,
    area_name: str,
    output: str,
    output_dir_base: Path | None = None,
):
    """
    Génère un rapport complet pour une zone donnée.
    Lève une exception en cas d'échec (à charge de l'appelant de gérer / logguer).
    Ne met à jour la base (date_reportgenerate) QUE si tout s'est bien passé.
    """

    time_launch = datetime.now()
    print(f"Début de génération du rapport {area_name} - à {time_launch.strftime('%H:%M:%S')} :")

    output_dir = (output_dir_base or (Path(__file__).resolve().parent / "outputs")) / area_name
    output_dirs = create_analysis_dirs(output_dir)

    timer = RunTimer()

    with get_connection(service_name) as conn:
        synthese_queries = SyntheseQueries(conn=conn, id_area=id_area, buffer=buffer)

        with timer.step("Vue matérialisée + analyse état des connaissances"):
            analysis_result = run_knowledge_status(
                context=None, synthese_queries=synthese_queries, output_dirs=output_dirs
            )

        with timer.step("Cartographie QGIS"):
            run_cartography(
                synthese_queries=synthese_queries,
                output_dirs=output_dirs,
                area_name=area_name,
            )

        if "atlas_nicheur" in list_analyse:
            with timer.step("Atlas QGIS"):
                run_atlas(
                    synthese_queries=synthese_queries,
                    output_dirs=output_dirs,
                    area_name=area_name,
                    run_render=True,
                )

    with timer.step("Génération du rapport Word"):
        generate_report(
            service_name=service_name,
            output_file=output_dir / output,
            id_area=id_area,
            referee=referee,
            list_analyse=list_analyse,
            buffer=buffer,
            area_name=area_name,
            analysis_result=analysis_result,
            output_dir=output_dir,
        )

    time_end = datetime.now()
    timer.summary()
    print(f"Fin de génération - à {time_end.strftime('%H:%M:%S')}")
    print(f"Temps total d'exécution : {time_end - time_launch}")

    # Update uniquement si tout s'est bien passé (on arrive ici sans exception)
    with get_connection(service_name) as conn:
        synthese_queries = SyntheseQueries(conn=conn, id_area=id_area, buffer=buffer)
        synthese_queries.update_date_reportgenerator()
        synthese_queries.delete_reportgenerator_view()

    return output_dir / output