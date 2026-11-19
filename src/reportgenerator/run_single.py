"""
run_single.py

Contient la logique de génération d'UN rapport.
Utilisé aussi bien par le mode "run" (unitaire) que par le mode "generate" (batch).
"""

import os
import time
from datetime import datetime
from pathlib import Path

from reportgenerator.analysis.common.filesystem import create_analysis_dirs
from reportgenerator.core.context import ReportContext
from reportgenerator.core.dossier import resolve_dossier
from reportgenerator.core.limites import Limites, bilan_echec, bilan_en_cours, bilan_ok
from reportgenerator.core.pipeline import run_pipeline
from reportgenerator.queries import SyntheseQueries
from reportgenerator.suivi import ecrire_bilan

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
    sans_limite: bool = False,
):
    """
    Génère un rapport complet pour une zone donnée.
    Le type de rapport est déduit de list_analyse (ex. "analyse_eolien"),
    sinon c'est le rapport générique.
    Lève une exception en cas d'échec (à charge de l'appelant de gérer / logguer).
    Écrit dans tous les cas le bilan de la demande (docs/limites/conception.md) : « en cours » au démarrage, puis
    OK, refusé ou échec, avec date_reportgenerate (la demande n'est pas relancée au `generate` suivant).
    sans_limite : lancement manuel d'une demande refusée (ni seuil de données, ni délai de la vue).
    """

    time_launch = datetime.now()
    debut = time.monotonic()
    print(f"Début de génération du rapport {area_name} - à {time_launch.strftime('%H:%M:%S')} :")

    dossier = None
    synthese_queries = None
    try:
        if not area_name or Path(area_name).name != area_name or area_name in (".", ".."):
            raise ValueError(f"Nom de zone invalide pour un dossier de sortie : {area_name!r}")

        dossier = resolve_dossier(list_analyse)
        print(f"Type de rapport : {dossier.name} ({dossier.label})")
        ecrire_bilan(service_name, id_area, bilan_en_cours(time_launch, dossier.name))
        enabled, ignored = dossier.select_analyses(list_analyse)
        if ignored:
            print(f"[AVERTISSEMENT] Analyses ignorées (inconnues du dossier '{dossier.name}') : {', '.join(ignored)}")

        # --output_dir, sinon OUTPUT_DIR (Docker), sinon src/reportgenerator/outputs/ (à côté de templates/)
        output_dir_base = Path(output_dir_base or os.getenv("OUTPUT_DIR") or DEFAULT_OUTPUT_DIR)
        output_dir = output_dir_base / area_name
        output_dirs = create_analysis_dirs(output_dir)

        params = dossier.params_for(list_analyse)
        synthese_queries = SyntheseQueries(service_name=service_name, id_area=id_area, buffer=buffer,
                                           limites=Limites.du_dossier(params, sans_limite))
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
            params=params,
        )
        run_pipeline(ctx, output_file=output_dir / output)
    except Exception as e:
        nom = dossier.name if dossier else "?"
        ecrire_bilan(service_name, id_area, bilan_echec(e, datetime.now(), time.monotonic() - debut, nom))
        raise
    finally:
        # la vue est supprimée même en cas d'échec ; un échec de suppression ne change pas le bilan (vue orpheline
        # supprimée au bout d'un jour, cf. queries.vues_orphelines)
        if synthese_queries is not None:
            try:
                synthese_queries.delete_reportgenerator_view()
            except Exception as e:
                print(f"[AVERTISSEMENT] Vue de travail non supprimée : {e}")

    ecrire_bilan(service_name, id_area, bilan_ok(datetime.now(), time.monotonic() - debut, dossier.name,
                                                 synthese_queries.nb_donnees, synthese_queries.duree_vue_s))

    time_end = datetime.now()
    print(f"Fin de génération - à {time_end.strftime('%H:%M:%S')}")
    print(f"Temps total d'exécution : {time_end - time_launch}")

    return output_dir / output
