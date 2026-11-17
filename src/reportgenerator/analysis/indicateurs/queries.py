"""Requêtes du rapport Indicateurs de biodiversité : lecture SEULE, filtrée sur l'emprise de la demande.

Chaque requête ouvre une connexion en lecture seule (aucune vue ni table créée). Le SQL met les lignes en forme
attendue par les adaptateurs (adaptateurs.py). Géométries en Lambert 93 (2154).
"""

from reportgenerator.db_auth import get_connection

ZONE = "zone AS (SELECT ST_Multi(ST_Union(geom)) AS geom FROM ref_geo.l_areas WHERE id_area = %(id_area)s)"


class IndicateursQueries:
    def __init__(self, service_name: str, id_area: int):
        self.service_name = service_name
        self.id_area = int(id_area)

    def _fetch(self, sql: str, **params) -> list[dict]:
        with get_connection(self.service_name) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(sql.replace("{ZONE}", ZONE), {"id_area": self.id_area, **params})
                return cur.fetchall()

    # --------------------------------------------------------------------------------------------------- cadre
    def zone(self) -> dict:
        rows = self._fetch("""WITH {ZONE}
            SELECT ST_AsText(ST_SimplifyPreserveTopology(geom, 50)) AS wkt,
                   round((ST_Area(geom) / 10000)::numeric) AS surface_ha
            FROM zone""")
        if not rows or rows[0]["wkt"] is None:
            raise ValueError(f"Emprise vide ou introuvable (id_area={self.id_area})")
        return rows[0]

    def departements(self) -> list[dict]:
        return self._fetch("""WITH {ZONE}
            SELECT a.area_code AS code, a.area_name AS nom,
                   ST_AsText(ST_SimplifyPreserveTopology(a.geom, 200)) AS wkt
            FROM ref_geo.l_areas a, zone z
            WHERE a.id_type = ref_geo.get_id_area_type('DEP') AND a.enable
              AND ST_Intersects(a.geom, z.geom) AND NOT ST_Touches(a.geom, z.geom)
            ORDER BY a.area_code""")

    def zones_biogeo(self) -> list[dict]:
        return self._fetch("""WITH {ZONE}
            SELECT b.area_name AS nom, ST_AsText(ST_SimplifyPreserveTopology(b.geom, 200)) AS wkt
            FROM ref_geo.mv_aura_zb b, zone z
            WHERE ST_Intersects(b.geom, z.geom) AND NOT ST_Touches(b.geom, z.geom)
            ORDER BY b.area_name""")
