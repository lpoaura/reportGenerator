#!/bin/python3

import argparse
import os
import sys
from pathlib import Path

from reportgenerator.core.dossier import DEFAULT_DOSSIER, list_dossiers, load_dossier
from reportgenerator.core.pipeline import check_dossier
from reportgenerator.core.registry import has_brick
from reportgenerator.run_queue import run_all_report
from reportgenerator.run_single import run_single_report


def print_dossiers():
    for name in list_dossiers():
        dossier = load_dossier(name)
        trigger = ", ".join(dossier.triggers) if dossier.triggers else "par défaut"
        print(f"{name} : {dossier.label} (list_analyse : {trigger})")
        for kind, bricks in (("obligatoires", dossier.required), ("optionnelles", dossier.optional)):
            if bricks:
                labels = [b if has_brick(b) else f"{b} (à coder)" for b in bricks]
                print(f"  {kind} : {', '.join(labels)}")


def print_check(name) -> bool:
    dossier = load_dossier(name)
    report = check_dossier(dossier)
    print(f"Vérification du dossier '{dossier.name}' ({dossier.label})")

    if report.unknown_bricks:
        print(f"\n✗ Briques déclarées mais pas encore codées ({len(report.unknown_bricks)}) :")
        for b in report.unknown_bricks:
            print(f"  - {b}")
    if report.missing_template:
        print(f"\n✗ Template Word absent : {dossier.template}")
    if report.no_placeholder:
        print(f"\n✗ Aucun placeholder {{{{...}}}} dans le template : {dossier.template}")
        print("  (les variables doivent être écrites {{CLE}}, cf. METHODO.md du dossier)")
    if report.unresolved:
        print(f"\n✗ Placeholders du Word sans brique qui les fournit ({len(report.unresolved)}) :")
        for key in report.unresolved:
            print(f"  - {{{{{key}}}}}")
    if report.unused:
        print(f"\n• Sorties disponibles non utilisées dans le Word ({len(report.unused)}) :")
        for key in report.unused:
            print(f"  - {{{{{key}}}}}")

    print("\n✓ Dossier prêt." if report.ok else "\nDossier incomplet.")
    return report.ok


def main():
    parser = argparse.ArgumentParser(
        description="Génération d'un rapport Word à partir de la base PostgreSQL"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ---- mode unitaire ----
    run_parser = subparsers.add_parser("run", help="Génère un seul rapport")
    run_parser.add_argument("--service", required=True)
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--output_dir", type=Path, default=os.getenv("REPORTGENERATOR_OUTPUT_DIR"))
    run_parser.add_argument("--id_area", type=int, required=True)
    run_parser.add_argument("--referee", required=True)
    run_parser.add_argument(
        "--list_analyse", default="",
        help="Valeur du formulaire : atlas_nicheur, analyse_eolien... (vide = rapport générique)",
    )
    run_parser.add_argument("--buffer", type=int, required=True)
    run_parser.add_argument("--area_name", required=True)

    # ---- mode batch : tous les rapports en attente ----
    gen_parser = subparsers.add_parser("generate", help="Génère les rapports en attente")
    gen_parser.add_argument("--service", default=os.getenv("REPORTGENERATOR_SERVICE_NAME"))
    gen_parser.add_argument("--limit", type=int, default=None)
    gen_parser.add_argument("--dry-run", action="store_true")

    # ---- outils dossiers types ----
    subparsers.add_parser("dossiers", help="Liste les types de dossiers et leurs analyses")
    check_parser = subparsers.add_parser(
        "check", help="Vérifie un dossier type (template Word / briques) sans base ni QGIS"
    )
    check_parser.add_argument("--dossier", default=DEFAULT_DOSSIER)

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
        if not args.service:
            parser.error("--service requis (ou variable REPORTGENERATOR_SERVICE_NAME)")
        run_all_report(
            service_name=args.service,
            limit=args.limit,
            dry_run=args.dry_run,
        )

    elif args.command == "dossiers":
        print_dossiers()

    elif args.command == "check":
        sys.exit(0 if print_check(args.dossier) else 1)


if __name__ == "__main__":
    main()
