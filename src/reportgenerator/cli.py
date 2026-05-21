#!/bin/python3

import argparse
import logging
from datetime import datetime
from report import generate_report
from pathlib import Path
from db_auth import get_connection
from reportgenerator.queries import SyntheseQueries
from analysis.common.filesystem import create_analysis_dirs
from analysis.knowledge_status.analysis import run as run_knowledge_status
from analysis.cartography.analysis import run_cartography



logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(
        description="Génération d'un rapport Word à partir de la base PostgreSQL"
    )

    parser.add_argument(
        "--service",
        required=True,
        help="Nom du service pg_service.conf"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Fichier Word de sortie"
    )

    parser.add_argument(
        "--id_area",
        type=int,
        required=True,
        help="id de la geometrie de la zone la zone d'étude pour le rapport"
    )

    parser.add_argument(
        "--referee",
        type=str,
        required=True,
        help="Personne référente"
    )

    parser.add_argument(
        "--list_analyse",
        type=str,
        required=True,
        help="Listes des différentes analyses"
    )

    parser.add_argument(
        "--buffer",
        type=int,
        required=True,
        help="Taille du buffer en kilomètres"
    )

    parser.add_argument(
        "--area_name",
        type=str,
        required=True,
        help="Nom de la zone d'étude"
    )

    args = parser.parse_args()

    time_launch =  datetime.now()
    print(f"Début de génération du rapport {args.area_name} - à {time_launch.strftime('%H:%M:%S')} :")
    #logger.info(f"Début de génération du rapport {args.area_name} - à {time_launch} :")


    # Créer les répertoires de sortie
    output_dir = (Path(__file__).resolve().parent / "outputs" / args.area_name)
    output_dirs = create_analysis_dirs(output_dir)
    
    with get_connection(args.service) as conn:

            synthese_queries = SyntheseQueries(
                conn=conn,
                id_area=args.id_area,
                buffer=args.buffer
            )

            analysis_result = run_knowledge_status(
                context=args,
                synthese_queries=synthese_queries,
                output_dirs=output_dirs
            )

            carto_result = run_cartography(
                synthese_queries=synthese_queries,
                output_dirs=output_dirs,
                area_name=args.area_name
            )

    
    # Générer le rapport Word
    generate_report(
         service_name=args.service,
         output_file=output_dir / args.output,
         id_area=args.id_area,
         referee=args.referee,
         list_analyse=args.list_analyse,
         buffer=args.buffer,
         area_name=args.area_name,
         analysis_result=analysis_result 
     )
    
    
    time_end = datetime.now()
    duration = time_end - time_launch

    print(f"Fin de génération - à {time_end.strftime('%H:%M:%S')}")
    print(f"Temps total d'exécution : {duration}")


if __name__ == "__main__":
    main()