"""Requêtes du rapport PLSOC Œdicnème : lecture SEULE du schéma pr_oedic_news, filtrée sur l'emprise du rapport.

L'emprise est la zone dessinée par l'utilisateur (id_area de la demande, ref_geo.l_areas), ou, pour les essais,
une zone d'étude du suivi (paramètre emprise = "zone_etude:<id>"). Toutes les données dont la géométrie intersecte
l'emprise sont prises en compte, quel que soit le département : c'est l'emprise qui délimite le rapport.
Aucune vue n'est créée : chaque requête ouvre une connexion en lecture seule.
"""

import re

from reportgenerator.db_auth import get_connection

SCHEMA_DEFAUT = "pr_oedic_news"


class PlsocQueries:
    def __init__(self, service_name: str, id_area: int, emprise: str = "demande", schema: str = SCHEMA_DEFAUT):
        if not re.fullmatch(r"[a-z_][a-z0-9_]*", schema):
            raise ValueError(f"Nom de schéma invalide : {schema!r}")
        self.service_name = service_name
        self.id_area = int(id_area)
        self.schema = schema
        self.zone_sql = self._zone_sql(emprise)

    def _zone_sql(self, emprise: str) -> str:
        if emprise == "demande":
            return "SELECT ST_Multi(ST_Union(geom)) AS geom FROM ref_geo.l_areas WHERE id_area = %(id_area)s"
        m = re.fullmatch(r"zone_etude:(\d+)", emprise or "")
        if m:
            return (
                f"SELECT ST_Multi(ST_Union(geom)) AS geom FROM {self.schema}.ref_zone_etude WHERE id_zone = {int(m[1])}"
            )
        raise ValueError(f"Emprise inconnue : {emprise!r} (attendu : 'demande' ou 'zone_etude:<id>')")

    def _fetch(self, sql: str, **params) -> list[dict]:
        sql = sql.replace("{S}", self.schema).replace("{ZONE}", f"zone AS ({self.zone_sql})")
        with get_connection(self.service_name) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(sql, {"id_area": self.id_area, **params})
                return cur.fetchall()

    # -------------------------------------------------------------------------------------------------- cadre
    def annee_par_defaut(self) -> int:
        """Dernière saison terminée (paramètre fin_saison du schéma)."""
        sql = """SELECT CASE WHEN current_date >= {S}.f_fin_saison(extract(year FROM current_date)::integer)
                             THEN extract(year FROM current_date)::integer
                             ELSE extract(year FROM current_date)::integer - 1 END AS annee"""
        return self._fetch(sql)[0]["annee"]

    def nomenclatures(self) -> dict[str, dict]:
        """Libellés (et ordre) des nomenclatures du schéma : {table: {code: {libelle, ordre, ...}}}."""
        out = {}
        for table in (
            "ref_succes_repro",
            "ref_stade_repro",
            "ref_milieu",
            "ref_cause_echec",
            "ref_degre_menace",
            "ref_type_protection",
            "ref_statut_evenement",
        ):
            out[table] = {r["code"]: r for r in self._fetch(f"SELECT * FROM {{S}}.{table}")}
        return out

    def zone(self) -> dict:
        sql = """WITH {ZONE}
                 SELECT round((ST_Area(z.geom) / 10000)::numeric) AS surface_ha,
                        ST_AsText(ST_SimplifyPreserveTopology(z.geom, 20)) AS wkt,
                        (SELECT count(*) FROM ref_geo.l_areas c
                          WHERE c.id_type = (SELECT id_type FROM ref_geo.bib_areas_types WHERE type_code = 'COM')
                            AND ST_Intersects(c.geom, z.geom)) AS nb_communes
                 FROM zone z"""
        rows = self._fetch(sql)
        if not rows or rows[0]["wkt"] is None:
            raise ValueError(f"Emprise vide ou introuvable (id_area={self.id_area})")
        return rows[0]

    def communes_carte(self) -> list[dict]:
        sql = """WITH {ZONE}
                 SELECT c.area_name AS nom, ST_AsText(ST_SimplifyPreserveTopology(c.geom, 30)) AS wkt
                 FROM ref_geo.l_areas c, zone z
                 WHERE c.id_type = (SELECT id_type FROM ref_geo.bib_areas_types WHERE type_code = 'COM')
                   AND ST_Intersects(c.geom, z.geom)"""
        return self._fetch(sql)

    def secteurs(self) -> list[dict]:
        sql = """WITH {ZONE}
                 SELECT s.nom_secteur, s.ordre, ST_AsText(ST_SimplifyPreserveTopology(s.geom, 10)) AS wkt
                 FROM {S}.ref_secteur s, zone z WHERE ST_Intersects(s.geom, z.geom) ORDER BY s.ordre"""
        return self._fetch(sql)

    # ----------------------------------------------------------------------------------------- couples / nids
    def couples(self, annee: int) -> list[dict]:
        sql = """WITH {ZONE}
                 SELECT c.source, c.cle_couple, c.code_couple, c.annee, c.date_premiere_obs, c.date_derniere_obs,
                        c.lieu_dit, c.milieu, c.culture, c.statut_nidification, c.nb_nids, c.nb_nids_succes,
                        c.nb_nids_proteges, c.nb_jeunes_envol, c.succes_repro, c.stade_repro, c.degre_menace,
                        c.code_insee, c.nom_commune, c.nom_epci, c.nom_secteur, c.id_mesure_compensatoire,
                        c.zonage_plu, ST_X(c.geom) AS x, ST_Y(c.geom) AS y
                 FROM {S}.mv_ana_couple c, zone z
                 WHERE ST_Intersects(c.geom, z.geom) AND c.annee <= %(annee)s"""
        return self._fetch(sql, annee=annee)

    def nids(self, annee: int) -> list[dict]:
        sql = """WITH {ZONE}
                 SELECT n.source, n.cle_nid, n.cle_couple, n.code_nid, n.annee, n.numero_nichee, n.stade_repro,
                        n.succes_repro, n.succes_source, n.nb_oeufs, n.nb_poussins, n.nb_jeunes_envol,
                        n.type_protection, n.protege, n.date_couvaison, n.date_eclosion, n.date_echec,
                        n.date_protection, n.mayfield_jours_exposition, n.mayfield_source, n.cause_fin, n.milieu,
                        n.agricole, n.code_insee, n.nom_commune, n.nom_epci, n.nom_secteur,
                        n.id_mesure_compensatoire, ST_X(n.geom) AS x, ST_Y(n.geom) AS y
                 FROM {S}.mv_ana_nid n, zone z
                 WHERE ST_Intersects(n.geom, z.geom) AND n.annee <= %(annee)s"""
        return self._fetch(sql, annee=annee)

    # --------------------------------------------------------------------------------------------- déductions
    def parcelles_mergin(self) -> list[dict]:
        """Parcelles agricoles saisies dans Mergin (déduction du milieu « agricole »)."""
        sql = """WITH {ZONE}
                 SELECT p.cle_parcelle, ST_AsText(p.geom) AS wkt
                 FROM {S}.v_mergin_parcelles p, zone z WHERE ST_Intersects(p.geom, z.geom)"""
        return self._fetch(sql)

    def suivis_parcelle(self, annee: int) -> list[dict]:
        """Relevés de parcelles de l'année (culture / végétation)."""
        sql = """WITH {ZONE}
                 SELECT s.date_suivi, s.type_vegetation, s.favorable, ST_AsText(s.geom) AS wkt
                 FROM {S}.v_mergin_suivis_parcelle s, zone z
                 WHERE s.annee = %(annee)s AND s.geom IS NOT NULL AND ST_Intersects(s.geom, z.geom)"""
        return self._fetch(sql, annee=annee)

    def lieux_dits(self, marge_m: int = 1500) -> list[dict]:
        """Lieux-dits VisioNature / Faune-France dans le rectangle de l'emprise (projetés en Lambert 93)."""
        sql = """WITH {ZONE}, b AS (
                     SELECT ST_Transform(ST_SetSRID(ST_Expand(ST_Envelope(geom), %(marge)s), 2154), 4326) AS g
                     FROM zone)
                 SELECT item ->> 'name' AS nom,
                        ST_X(ST_Transform(ST_SetSRID(ST_MakePoint((item ->> 'coord_lon')::float,
                                                                  (item ->> 'coord_lat')::float), 4326), 2154)) AS x,
                        ST_Y(ST_Transform(ST_SetSRID(ST_MakePoint((item ->> 'coord_lon')::float,
                                                                  (item ->> 'coord_lat')::float), 4326), 2154)) AS y
                 FROM src_vn_json.places_json, b
                 WHERE (item ->> 'coord_lon')::float BETWEEN ST_XMin(b.g) AND ST_XMax(b.g)
                   AND (item ->> 'coord_lat')::float BETWEEN ST_YMin(b.g) AND ST_YMax(b.g)
                   AND coalesce(item ->> 'name', '') <> ''"""
        return self._fetch(sql, marge=marge_m)

    # ------------------------------------------------------------------------------------------------- saison
    def evenements(self, annee: int) -> list[dict]:
        """Passages et événements datés de l'année, avec la mesure compensatoire éventuelle."""
        sql = """WITH {ZONE}
                 SELECT e.source, e.date_obs, e.code, e.categorie, e.nombre, e.observateur, e.cle_couple, e.cle_nid,
                        m.id_mesure_compensatoire
                 FROM {S}.v_ana_evenement e
                 CROSS JOIN zone z
                 LEFT JOIN LATERAL {S}.f_mesure(e.geom) m ON true
                 WHERE e.annee = %(annee)s AND e.geom IS NOT NULL AND ST_Intersects(e.geom, z.geom)"""
        return self._fetch(sql, annee=annee)

    def synthese(self, annee: int) -> list[dict]:
        """Dates extrêmes des données Faune-France / GeoNature par année (phénologie)."""
        sql = """WITH {ZONE}
                 SELECT s.annee, min(s.date_debut) AS premiere, max(s.date_fin) AS derniere, count(*) AS nb
                 FROM {S}.mv_synthese_oedicneme s, zone z
                 WHERE s.annee <= %(annee)s AND coalesce(s.est_presence, true) AND ST_Intersects(s.geom, z.geom)
                 GROUP BY s.annee"""
        return self._fetch(sql, annee=annee)

    def rassemblements(self, annee: int) -> list[dict]:
        sql = """WITH {ZONE}
                 SELECT r.source, r.site, r.commune, r.annee, r.date_comptage, r.effectif, r.date_premiere_obs,
                        r.date_derniere_obs
                 FROM {S}.v_ana_rassemblement r, zone z
                 WHERE r.annee <= %(annee)s AND r.geom IS NOT NULL AND ST_Intersects(r.geom, z.geom)"""
        return self._fetch(sql, annee=annee)

    def bagues(self, annee: int) -> list[dict]:
        """Bagues de l'année. Les bagues de poussins Mergin sont rattachées à l'événement de nid (modèle) ou
        directement au nid (saisie actuelle : fk_uuid_evenement contient l'uuid du nid)."""
        sql = """WITH {ZONE}
                 SELECT b.source, b.date_obs, b.classe_age, b.bague, b.type_bague, b.cle_couple, b.cle_nid
                 FROM {S}.v_ana_bague b, zone z
                 WHERE b.annee = %(annee)s AND b.source <> 'mergin_poussin' AND ST_Intersects(b.geom, z.geom)
                 UNION ALL
                 SELECT DISTINCT 'mergin_poussin', coalesce(e.date_obs, n.date_derniere_obs_poussins), 'poussin',
                        {S}.f_bague(x ->> 'num_bague'), lower(x ->> 'type_bague'),
                        'M' || {S}.f_norm_uuid(n.uuid_couple), 'M' || n.cle_nid
                 FROM {S}.v_mergin_evenement_poussins p
                 CROSS JOIN LATERAL jsonb_array_elements(p.poussins) x
                 LEFT JOIN {S}.v_mergin_observations e
                        ON e.source <> 'Observation'
                       AND {S}.f_norm_uuid(e.uuid_source) = {S}.f_norm_uuid(p.uuid_evenement)
                 JOIN {S}.v_mergin_nids n
                        ON n.cle_nid = coalesce({S}.f_norm_uuid(e.uuid_nid), {S}.f_norm_uuid(p.uuid_evenement))
                 CROSS JOIN zone z
                 WHERE n.annee = %(annee)s AND {S}.f_bague(x ->> 'num_bague') IS NOT NULL
                   AND ST_Intersects(n.geom, z.geom)"""
        return self._fetch(sql, annee=annee)

    # ------------------------------------------------------------------------------------ mesures / urbanisme
    def mesures(self) -> list[dict]:
        sql = """WITH {ZONE}
                 SELECT m.id_site, m.id_projet, m.nom_projet, m.commune, m.lieu_dit, m.porteur_projet, m.ref_arrete,
                        m.surface_galet_ha, m.surface_prairie_ha, m.substrat, m.annee_mise_en_place,
                        m.annee_premiere_presence, m.hors_plsoc, m.structure_suivi,
                        round((ST_Area(m.geom) / 10000)::numeric, 2) AS surface_ha,
                        ST_AsText(ST_SimplifyPreserveTopology(m.geom, 2)) AS wkt
                 FROM {S}.ref_mesure_compensatoire m, zone z WHERE ST_Intersects(m.geom, z.geom)
                 ORDER BY m.id_projet, m.id_site"""
        return self._fetch(sql)

    def suivis_mesure(self, annee: int) -> list[dict]:
        sql = """WITH {ZONE}
                 SELECT s.id_mesure_compensatoire, s.date_mesure, s.observateur, s.rec_galets, s.rec_herbes,
                        s.rec_arbustes, s.rec_ronces, s.h_moy_herbe, s.frequentation, s.cloture, s.dechets,
                        s.etat_cloture, s.autres_obs, s.bilan
                 FROM {S}.v_mergin_suivis_mesure s, zone z
                 WHERE s.annee = %(annee)s AND s.geom IS NOT NULL AND ST_Intersects(s.geom, z.geom)"""
        return self._fetch(sql, annee=annee)

    def habitat_menace(self, annee: int) -> list[dict]:
        """Couples en zone U / AU du PLU depuis le début du suivi, et parcelles cadastrales concernées."""
        sql = """WITH {ZONE}, cp AS (
                     SELECT coalesce(c.nom_epci, 'Hors EPCI') AS nom_epci, c.zonage_plu, c.cle_couple, c.annee,
                            p.id_hist, p.surface
                     FROM {S}.mv_ana_couple c
                     CROSS JOIN zone z
                     LEFT JOIN {S}.hist_parcelle p ON ST_Within(c.geom, p.geom)
                     WHERE c.zonage_plu IN ('U', 'AU') AND c.annee <= %(annee)s AND ST_Intersects(c.geom, z.geom))
                 SELECT nom_epci, zonage_plu, count(DISTINCT cle_couple) AS nb_couples_annees,
                        count(DISTINCT id_hist) AS nb_parcelles,
                        (SELECT round((sum(d.surface) / 10000)::numeric, 1)
                           FROM (SELECT DISTINCT c2.id_hist, c2.surface FROM cp c2
                                 WHERE c2.nom_epci = cp.nom_epci AND c2.zonage_plu = cp.zonage_plu
                                   AND c2.id_hist IS NOT NULL) d) AS surface_ha,
                        min(annee) AS premiere_annee, max(annee) AS derniere_annee
                 FROM cp GROUP BY nom_epci, zonage_plu ORDER BY nom_epci, zonage_plu"""
        return self._fetch(sql, annee=annee)

    # ------------------------------------------------------------------------------------------------ qualité
    def anomalies(self, annee: int) -> list[dict]:
        sql = """WITH {ZONE}
                 SELECT a.gravite, a.code_anomalie, count(*) AS nb
                 FROM {S}.v_ctrl_anomalies a, zone z
                 WHERE a.annee = %(annee)s AND (a.geom IS NULL OR ST_Intersects(a.geom, z.geom))
                 GROUP BY a.gravite, a.code_anomalie ORDER BY a.gravite, a.code_anomalie"""
        return self._fetch(sql, annee=annee)
