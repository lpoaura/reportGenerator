"""Base des requêtes d'un dossier sur la vue matérialisée principale (créée par la brique socle_data)."""

import re

from psycopg.rows import dict_row

from reportgenerator.db_auth import get_connection

# nom générique dans le SQL, remplacé à l'exécution par la vue de la génération en cours
VM = "lpoaura_afo.vm_reportgenerator_data"


class VmQueries:
    def __init__(self, synthese_queries):
        self.service_name = synthese_queries.service_name
        self.id_area = int(synthese_queries.id_area)
        self.anneaux_km = synthese_queries.anneaux_km
        self.vm = getattr(synthese_queries, "vm", VM)

    def _fetch(self, sql, params=None):
        with get_connection(self.service_name) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(self._sql(sql), params)
                return cur.fetchall()

    def _sql(self, sql: str) -> str:
        """VM générique -> vue de la génération en cours (\\b : pas de remplacement dans un nom déjà unique)."""
        return re.sub(re.escape(VM) + r"\b", lambda _: self.vm, sql)

    def fetch(self, sql):
        """Requête brute (couches QGIS de compatibilité)."""
        return self._fetch(sql)


def with_params(sql: str) -> str:
    """Échappe les % littéraux (ilike 'transit%') puis place les paramètres psycopg ({P} -> %s)."""
    return sql.replace("%", "%%").replace("{P}", "%s")
