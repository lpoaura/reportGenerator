"""
run_queue.py

Récupère la liste des rapports en attente et orchestre leur génération en batch.
Limites et bilan des demandes : docs/limites/conception.md.
"""

from datetime import datetime

from psycopg.rows import dict_row

from reportgenerator.core.limites import bilan_interrompu
from reportgenerator.db_auth import get_connection
from reportgenerator.run_single import run_single_report
from reportgenerator.suivi import demandes_interrompues, ecrire_bilan, verrou_generate


def get_pending_areas(conn):
    """Retourne la liste des zones en attente de génération de rapport. Pas de filtre de surface : la charge est
    contrôlée par le comptage des données avant la vue de synthèse (queries.SyntheseQueries.set_global_data)."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT id_area, area_name, referee, list_analyse, buffer,
                   round((st_area(st_transform(geom, 2154)) / 1000000)::numeric, 2) AS area_km2
            FROM src_gestion.v_reportgenerator_areas_lpo
            WHERE date_reportgenerate IS NULL
            ORDER BY date_created
            """
        )
        return cur.fetchall()


def run_all_report(service_name: str, limit: int | None = None, dry_run: bool = False):
    """
    Lance la génération de tous les rapports en attente, un par un.
    Chaque échec est isolé : il n'interrompt pas le traitement des suivants, et il est écrit dans le bilan de la
    demande (qui n'est pas relancée). Un seul `generate` à la fois (verrou consultatif PostgreSQL).
    """
    if dry_run:
        with get_connection(service_name) as conn:
            pending = get_pending_areas(conn)
        pending = pending[:limit] if limit else pending
        print(f"{len(pending)} rapport(s) en attente.")
        for area in pending:
            print(
                f"  [DRY-RUN] {area['area_name']} (id_area={area['id_area']}, "
                f"{area['area_km2']} km², list_analyse={area['list_analyse']!r})"
            )
        return

    with verrou_generate(service_name) as seul:
        if not seul:
            print("Une autre génération (`generate`) est en cours : arrêt.")
            return
        _run_all(service_name, limit)


def _run_all(service_name: str, limit: int | None):
    with get_connection(service_name) as conn:
        pending = get_pending_areas(conn)
        interrompues = set(demandes_interrompues(conn, [a["id_area"] for a in pending]))

    # restées « en cours » alors qu'aucune génération ne tourne (verrou) : processus arrêté, pas de relance
    for area in pending:
        if area["id_area"] in interrompues:
            print(f"[INTERROMPUE] {area['area_name']} (id_area={area['id_area']}) : marquée en échec")
            ecrire_bilan(service_name, area["id_area"], bilan_interrompu(datetime.now()))
    pending = [a for a in pending if a["id_area"] not in interrompues]

    if limit:
        pending = pending[:limit]

    print(f"{len(pending)} rapport(s) en attente.")

    successes, failures = [], []

    for area in pending:
        area_name = area["area_name"]
        try:
            print(f"\n=== Traitement : {area_name} (id_area={area['id_area']}, {area['area_km2']} km²) ===")
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
    print(f"Échoués ou refusés : {len(failures)}")
    for name, err in failures:
        print(f"  - {name} : {err}")
