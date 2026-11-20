"""
suivi.py

Suivi des demandes en base : bilan de génération (src_gestion.update_reportgenerator_bilan), verrou entre deux
`generate`, demandes interrompues. Cf. docs/limites/conception.md.
"""

from contextlib import contextmanager

import psycopg
from psycopg.types.json import Jsonb

from reportgenerator.core.limites import Bilan
from reportgenerator.db_auth import get_connection

# fonction pas encore créée en base (docs/limites/sql/update_reportgenerator_bilan.sql) : repli sur la date seule
FONCTION_ABSENTE = (psycopg.errors.UndefinedFunction,)
# clé du verrou consultatif de `generate` (pg_try_advisory_lock : aucun objet créé en base)
VERROU_GENERATE = 7262_0001


def ecrire_bilan(service_name: str, id_area: int, bilan: Bilan) -> None:
    """Écrit le bilan (commentaire + additional_data.reportgenerate, date sauf en_cours). N'échoue jamais : une erreur
    d'écriture ne doit pas masquer l'erreur de génération (elle est seulement affichée)."""
    print(f"Bilan id_area={id_area} : {bilan.commentaire}")
    try:
        with get_connection(service_name) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT src_gestion.update_reportgenerator_bilan(%s, %s, %s, %s)",
                            (int(id_area), bilan.statut, bilan.commentaire, Jsonb(bilan.details)))
        return
    except FONCTION_ABSENTE:
        print("[AVERTISSEMENT] src_gestion.update_reportgenerator_bilan absente (docs/limites/sql/) : date seule")
    except Exception as e:
        # quelle que soit l'erreur, la date doit être écrite pour un bilan final : sinon relance à chaque `generate`
        print(f"[AVERTISSEMENT] Bilan non écrit pour id_area={id_area} : {e}")
    if bilan.statut == "en_cours":
        return
    try:
        with get_connection(service_name) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT src_gestion.update_reportgenerator_date(%s)", (int(id_area),))
    except Exception as e:
        print(f"[AVERTISSEMENT] Date non écrite pour id_area={id_area} : {e}")


@contextmanager
def verrou_generate(service_name: str):
    """True si ce processus est le seul `generate` en cours. Verrou de session : libéré à la fin du bloc, ou par la
    base si le processus est tué (connexion fermée)."""
    with psycopg.connect(service=service_name, autocommit=True) as conn:
        acquis = conn.execute("SELECT pg_try_advisory_lock(%s)", (VERROU_GENERATE,)).fetchone()[0]
        try:
            yield acquis
        finally:
            if acquis:
                conn.execute("SELECT pg_advisory_unlock(%s)", (VERROU_GENERATE,))


def demandes_interrompues(conn, ids: list[int]) -> list[int]:
    """Demandes en attente restées au statut en_cours : la génération précédente a été arrêtée en route (le verrou
    garantit qu'aucune autre ne tourne)."""
    if not ids:
        return []
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id_area FROM ref_geo.l_areas
               WHERE id_area = ANY(%s) AND additional_data->'reportgenerate'->>'statut' = 'en_cours'""",
            (list(ids),),
        )
        return [r["id_area"] for r in cur.fetchall()]
