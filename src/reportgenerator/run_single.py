"""
run_single.py

Contient la logique de génération d'UN rapport.
Utilisé aussi bien par le mode "run" (unitaire) que par le mode "generate" (batch).
"""

import os
from datetime import datetime
from pathlib import Path

from reportgenerator.analysis.common.filesystem import create_analysis_dirs
from reportgenerator.core.context import ReportContext
from reportgenerator.core.dossier import resolve_dossier
from reportgenerator.core.pipeline import run_pipeline
from reportgenerator.queries import SyntheseQueries

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


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
    Le type de rapport est déduit de list_analyse (ex. "analyse_eolien"),
    sinon c'est le rapport générique.
    Lève une exception en cas d'échec (à charge de l'appelant de gérer / logguer).
    Ne met à jour la base (date_reportgenerate) QUE si tout s'est bien passé.
    """

    time_launch = datetime.now()
    print(f"Début de génération du rapport {area_name} - à {time_launch.strftime('%H:%M:%S')} :")

    if not area_name or Path(area_name).name != area_name or area_name in (".", ".."):
        raise ValueError(f"Nom de zone invalide pour un dossier de sortie : {area_name!r}")

    dossier = resolve_dossier(list_analyse)
    print(f"Type de rapport : {dossier.name} ({dossier.label})")
    enabled, ignored = dossier.select_analyses(list_analyse)
    if ignored:
        print(f"[AVERTISSEMENT] Analyses ignorées (inconnues du dossier '{dossier.name}') : {', '.join(ignored)}")

    # --output_dir, sinon OUTPUT_DIR (Docker), sinon src/reportgenerator/outputs/ (à côté de templates/)
    output_dir_base = Path(output_dir_base or os.getenv("OUTPUT_DIR") or DEFAULT_OUTPUT_DIR)
    output_dir = output_dir_base / area_name
    output_dirs = create_analysis_dirs(output_dir)

    synthese_queries = SyntheseQueries(service_name=service_name, id_area=id_area, buffer=buffer)
    ctx = ReportContext(
        service_name=service_name,
        id_area=id_area,
        area_name=area_name,
        referee=referee,
        buffer=buffer,
        dossier=dossier,
        enabled=enabled,
        output_dirs=output_dirs,
        queries=synthese_queries,
        params=dict(dossier.params),
    )

    try:
        run_pipeline(ctx, output_file=output_dir / output)
        # Update uniquement si tout s'est bien passé (on arrive ici sans exception)
        synthese_queries.update_date_reportgenerator()
    finally:
        # la vue est supprimée même en cas d'échec
        synthese_queries.delete_reportgenerator_view()

    time_end = datetime.now()
    print(f"Fin de génération - à {time_end.strftime('%H:%M:%S')}")
    print(f"Temps total d'exécution : {time_end - time_launch}")

    return output_dir / output
