"""
run_queue.py

Récupère la liste des rapports en attente et orchestre leur génération en batch.
"""

from psycopg.rows import dict_row

from reportgenerator.db_auth import get_connection
from reportgenerator.run_single import run_single_report


def get_pending_areas(conn, max_area_km2: float = 1000):
    """Retourne la liste des zones en attente de génération de rapport."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id_area, area_name, referee, list_analyse, buffer,
                   round((st_area(st_transform(geom, 2154)) / 1000000)::numeric, 2) AS area_km2
            FROM src_gestion.v_reportgenerator_areas_lpo
            WHERE date_reportgenerate IS NULL
            AND st_area(st_transform(geom, 2154)) / 1000000 < %s
            ORDER BY date_created
            """,
            (max_area_km2,),
        )
        return cur.fetchall()


def run_all_report(service_name: str, limit: int | None = None, dry_run: bool = False):
    """
    Lance la génération de tous les rapports en attente, un par un.
    Chaque échec est isolé : il n'interrompt pas le traitement des suivants.
    """

    with get_connection(service_name) as conn:
        pending = get_pending_areas(conn)

    if limit:
        pending = pending[:limit]

    print(f"{len(pending)} rapport(s) en attente.")

    if dry_run:
        for area in pending:
            print(f"  [DRY-RUN] {area['area_name']} (id_area={area['id_area']}, {area['area_km2']} km²)")
        return

    successes, failures = [], []

    for area in pending:
        area_name = area["area_name"]
        try:
            print(f"\n=== Traitement : {area_name} (id_area={area['id_area']}) ===")
            run_single_report(
                service_name=service_name,
                id_area=area["id_area"],
                referee=area["referee"],
                list_analyse=area["list_analyse"],
                buffer=area["buffer"],
                area_name=area_name,
                output=f"{area_name}.docx",
            )
            successes.append(area_name)
        except Exception as e:
            print(f"[ERREUR] {area_name} (id_area={area['id_area']}) : {e}")
            failures.append((area_name, str(e)))
            continue

    print("\n=== Résumé du batch ===")
    print(f"Réussis : {len(successes)}")
    print(f"Échoués : {len(failures)}")
    for name, err in failures:
        print(f"  - {name} : {err}")