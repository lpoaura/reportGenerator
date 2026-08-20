#!/bin/python3

import argparse
from pathlib import Path

from reportgenerator.run_single import run_single_report
from reportgenerator.run_queue import run_all_report


def main():
    parser = argparse.ArgumentParser(
        description="Génération d'un rapport Word à partir de la base PostgreSQL"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- mode unitaire : équivalent à l'usage actuel ----
    run_parser = subparsers.add_parser("run", help="Génère un seul rapport")
    run_parser.add_argument("--service", required=True)
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--output_dir", type=Path, default=None)
    run_parser.add_argument("--id_area", type=int, required=True)
    run_parser.add_argument("--referee", required=True)
    run_parser.add_argument("--list_analyse", required=True)
    run_parser.add_argument("--buffer", type=int, required=True)
    run_parser.add_argument("--area_name", required=True)

    # ---- mode batch : tous les rapports en attente ----
    gen_parser = subparsers.add_parser("generate", help="Génère les rapports en attente")
    gen_parser.add_argument("--service", required=True)
    gen_parser.add_argument("--limit", type=int, default=None)
    gen_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()

    if args.command == "run":
        run_single_report(
            service_name=args.service,
            id_area=args.id_area,
            referee=args.referee,
            list_analyse=args.list_analyse,
            buffer=args.buffer,
            area_name=args.area_name,
            output=args.output,
            output_dir_base=args.output_dir,
        )

    elif args.command == "generate":
        run_all_report(
            service_name=args.service,
            limit=args.limit,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()