#!/bin/python3

import argparse
from report import generate_report

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
        "--dataset",
        type=int,
        required=True,
        help="ID dataset"
    )

    args = parser.parse_args()

    generate_report(
        service_name=args.service,
        output_file=args.output,
        id_dataset=args.dataset
    )


if __name__ == "__main__":
    main()