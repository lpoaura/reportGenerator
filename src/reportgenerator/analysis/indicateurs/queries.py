"""Requêtes du rapport Indicateurs de biodiversité : lecture SEULE, filtrée sur l'emprise de la demande.

Chaque requête ouvre une connexion en lecture seule (aucune vue ni table créée). Le SQL met les lignes en forme
attendue par les adaptateurs (adaptateurs.py). Géométries en Lambert 93 (2154).
"""

from reportgenerator.db_auth import get_connection

ZONE = "zone AS (SELECT ST_Multi(ST_Union(geom)) AS geom FROM ref_geo.l_areas WHERE id_area = %(id_area)s)"

# effectif d'une observation des modules monitoring (t_observation_complements.data)
EFFECTIFS = {
    "stom": "coalesce((c.data->>'nb_0_5')::int, 0) + coalesce((c.data->>'nb_5_10')::int, 0)"
            " + coalesce((c.data->>'nb_10_15')::int, 0)",                       # sans nb_hors_proto
    "sterf_ebms": "coalesce((c.data->>'effectif')::int, (c.data->>'count_max')::int)",
    "POPReptile": "(c.data->>'count_max')::int",
    "POPAmphibien": "(c.data->>'count_max')::int",
}
# vues POP lues (liste blanche) : vue des anomalies -> colonne de l'unité
VUES_ETATS = ("v_popreptiles_aire_annee", "v_popamphibien_aire_annee")
VUES_ANOMALIES = {"v_popreptiles_anomalies": "transect", "v_popamphibien_anomalies": "site"}

# relevés Faune-France (pr_vigienature) : aire = carré (carre_numnat) ou site (site_name, STOC-sites) ; unité =
# point d'écoute ou transect SHOC (point_num) ; une aire est dans la zone si l'un de ses relevés l'intersecte
RELEVES_VN = """{ZONE},
r AS (SELECT r.id, r.date_debut, r.observateur, r.passage_mnhn, r.carre_numnat, r.point_num,
             CASE WHEN %(par_site)s THEN r.site_name ELSE r.carre_numnat::text END AS id_aire,
             coalesce(r.geom_transect, r.geom_point) AS g
      FROM pr_vigienature.t_releve r
      WHERE r.nom_protocole = ANY(%(protocoles)s) AND coalesce(r.geom_transect, r.geom_point) IS NOT NULL),
aires AS (SELECT DISTINCT r.id_aire FROM r, zone z
          WHERE r.id_aire IS NOT NULL AND r.g && z.geom AND ST_Intersects(r.g, z.geom)),
rz AS (SELECT r.* FROM r JOIN aires USING (id_aire))"""

# sites d'un module monitoring : rattachés au module (cor_site_module) ou visités dans le module (9 transects POP
# Reptile visités en 2025 ne sont pas rattachés) ; aire = groupe de sites (« sans_aire » sinon) ; une aire est dans
# la zone si l'un de ses sites l'intersecte (elle est alors lue entière) ; un site sans aire est retenu s'il
# intersecte la zone
SITES_MON = """{ZONE},
module AS (SELECT id_module FROM gn_commons.t_modules WHERE module_code = %(module)s),
sites AS (SELECT s.id_base_site, s.base_site_name, s.geom_local,
                 coalesce(sc.id_sites_group::text, 'sans_aire') AS id_aire
          FROM gn_monitoring.t_base_sites s
          LEFT JOIN gn_monitoring.t_site_complements sc ON sc.id_base_site = s.id_base_site
          WHERE s.id_base_site IN (SELECT csm.id_base_site FROM gn_monitoring.cor_site_module csm
                                   WHERE csm.id_module IN (SELECT id_module FROM module)
                                   UNION
                                   SELECT v.id_base_site FROM gn_monitoring.t_base_visits v
                                   WHERE v.id_module IN (SELECT id_module FROM module))),
dans AS (SELECT s.* FROM sites s, zone z WHERE s.geom_local && z.geom AND ST_Intersects(s.geom_local, z.geom)),
sz AS (SELECT s.* FROM sites s
       WHERE (s.id_aire <> 'sans_aire' AND s.id_aire IN (SELECT id_aire FROM dans))
          OR s.id_base_site IN (SELECT id_base_site FROM dans WHERE id_aire = 'sans_aire'))"""

# nom français : premier nom vernaculaire de TAXREF, sans l'article final des papillons (« Fadet commun (Le) »)
NOM_VERN = r"""regexp_replace(split_part(coalesce(t.nom_vern, t.lb_nom), ',', 1), '\s*\((Le|La|Les|L'')\)\s*$', '')"""

DUREE_HEURES_VISITE = r"""CASE WHEN vc.data->>'start_hour' ~ '^\d{1,2}:\d{2}'
      AND vc.data->>'end_hour' ~ '^\d{1,2}:\d{2}'
      AND (vc.data->>'end_hour')::time > (vc.data->>'start_hour')::time
     THEN extract(epoch FROM (vc.data->>'end_hour')::time - (vc.data->>'start_hour')::time) / 60 END"""


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

    def villes(self, distance_m: int = 30000) -> list[dict]:
        """Chefs-lieux à moins de `distance_m` de la zone, étiquetés sur les cartes (à la place des noms du fond de
        carte) : rang 1 préfecture de région, 2 préfecture, 3 sous-préfecture ; point = centre de la commune."""
        return self._fetch("""WITH {ZONE}
            SELECT m.nom_com AS nom,
                   CASE m.status WHEN 'Préfecture de région' THEN 1 WHEN 'Préfecture' THEN 2 ELSE 3 END AS rang,
                   ST_AsText(coalesce(a.centroid, ST_PointOnSurface(a.geom))) AS wkt
            FROM ref_geo.li_municipalities m
            JOIN ref_geo.l_areas a ON a.id_area = m.id_area AND a.enable, zone z
            WHERE m.status IN ('Préfecture de région', 'Préfecture', 'Sous-préfecture')
              AND ST_DWithin(a.geom, z.geom, %(distance)s)
            ORDER BY rang, nom""", distance=int(distance_m))

    def localiser(self, centres: list[tuple]) -> list[dict]:
        """Commune, département et zone biogéographique du centre de chaque aire (département et zone : les plus
        proches si le centre tombe hors de la région, ex. carré à cheval sur une limite)."""
        if not centres:
            return []
        ids, xs, ys = (list(t) for t in zip(*centres))
        return self._fetch("""
            WITH p AS (SELECT id_aire, ST_SetSRID(ST_MakePoint(x, y), 2154) AS g
                       FROM unnest(%(ids)s::text[], %(xs)s::float8[], %(ys)s::float8[]) AS t(id_aire, x, y)),
            dep AS (SELECT area_name, geom FROM ref_geo.l_areas
                    WHERE id_type = ref_geo.get_id_area_type('DEP') AND enable)
            SELECT p.id_aire,
                   (SELECT c.area_name FROM ref_geo.l_areas c
                     WHERE c.id_type = ref_geo.get_id_area_type('COM') AND ST_Intersects(c.geom, p.g) LIMIT 1)
                     AS commune,
                   (SELECT d.area_name FROM dep d ORDER BY ST_Distance(d.geom, p.g) LIMIT 1) AS departement,
                   (SELECT b.area_name FROM ref_geo.mv_aura_zb b ORDER BY ST_Distance(b.geom, p.g) LIMIT 1) AS zbiog
            FROM p""", ids=[str(i) for i in ids], xs=[float(x) for x in xs], ys=[float(y) for y in ys])

    # ------------------------------------------------------------------------------------------- Faune-France
    def aires_vigienature(self, protocoles: list[str], par_site: bool = False) -> list[dict]:
        return self._fetch(f"""WITH {RELEVES_VN}
            SELECT rz.id_aire,
                   CASE WHEN %(par_site)s THEN rz.id_aire ELSE 'Carré ' || rz.id_aire END AS nom_aire,
                   ST_AsText(coalesce(min(l.geom::text)::geometry,
                                      ST_Envelope(ST_Buffer(ST_Collect(rz.g), 200)))) AS wkt,
                   ST_X(ST_Centroid(ST_Collect(rz.g))) AS x, ST_Y(ST_Centroid(ST_Collect(rz.g))) AS y,
                   count(DISTINCT rz.point_num) AS nb_unites
            FROM rz
            LEFT JOIN pr_vigienature.l_carre_suivi l ON NOT %(par_site)s AND l.numnat = rz.carre_numnat
            GROUP BY rz.id_aire""", protocoles=list(protocoles), par_site=par_site)

    def releves_vigienature(self, protocoles: list[str], debut: int, par_site: bool = False) -> list[dict]:
        return self._fetch(f"""WITH {RELEVES_VN}
            SELECT rz.id AS id_passage, rz.id_aire, rz.id_aire || '/' || coalesce(rz.point_num::text, '?') AS id_unite,
                   coalesce(rz.point_num::text, '?') AS nom_unite, rz.date_debut AS date, rz.observateur,
                   (SELECT count(*) FROM pr_vigienature.t_observation o WHERE o.releve_id = rz.id) AS nb_donnees,
                   rz.passage_mnhn
            FROM rz WHERE rz.date_debut >= make_date(%(debut)s - 1, 7, 1)""",
                           protocoles=list(protocoles), par_site=par_site, debut=int(debut))

    def observations_vigienature(self, protocoles: list[str], annee_min: int, par_site: bool = False) -> list[dict]:
        return self._fetch(f"""WITH {RELEVES_VN}
            SELECT o.releve_id AS id_passage, t.cd_ref, {NOM_VERN} AS nom,
                   sum(coalesce(o.nombre, 0)) AS effectif
            FROM rz
            JOIN pr_vigienature.t_observation o ON o.releve_id = rz.id
            JOIN pr_vigienature.cor_taxon_referentiels ct ON ct.id = o.taxon_id
            JOIN taxonomie.taxref t ON t.cd_nom = ct.cd_nom
            WHERE rz.date_debut >= make_date(%(annee_min)s - 1, 7, 1)
            GROUP BY 1, 2, 3""", protocoles=list(protocoles), par_site=par_site, annee_min=int(annee_min))

    def observateurs_faune_france(self, ids: list[str]) -> list[dict]:
        """Identifiant Faune-France -> compte GeoNature (par l'email, compte le plus récent) et organisme. L'email
        sert seulement à la catégorie (adaptateur) ; il n'est jamais écrit dans le rapport."""
        if not ids:
            return []
        return self._fetch("""
            WITH oj AS (SELECT DISTINCT ON (id_universal) id_universal::text AS observateur,
                               lower(item->>'email') AS email,
                               nullif(concat_ws(' ', item->>'name', item->>'surname'), '') AS nom
                        FROM src_vn_json.observers_json
                        WHERE id_universal::text = ANY(%(ids)s::text[])
                        ORDER BY id_universal, id DESC)
            SELECT oj.observateur, tr.id_role,
                   coalesce(nullif(concat_ws(' ', tr.prenom_role, tr.nom_role), ''), oj.nom) AS nom,
                   oj.email, bo.nom_organisme AS organisme
            FROM oj
            LEFT JOIN LATERAL (SELECT * FROM utilisateurs.t_roles tr WHERE lower(tr.email) = oj.email
                               ORDER BY tr.id_role DESC LIMIT 1) tr ON oj.email IS NOT NULL
            LEFT JOIN utilisateurs.bib_organismes bo ON bo.id_organisme = tr.id_organisme""",
                           ids=[str(i) for i in ids])

    # ------------------------------------------------------------------------------------------- monitoring
    def aires_monitoring(self, module: str) -> list[dict]:
        return self._fetch(f"""WITH {SITES_MON}
            SELECT sz.id_aire, coalesce(min(sg.sites_group_name), 'Sans aire') AS nom_aire,
                   CASE WHEN sz.id_aire <> 'sans_aire'   -- pas de contour pour les sites sans aire (dispersés)
                        THEN ST_AsText(coalesce(min(sg.geom_local::text)::geometry,
                                                ST_Buffer(ST_ConvexHull(ST_Collect(sz.geom_local)), 100))) END AS wkt,
                   ST_X(ST_Centroid(ST_Collect(sz.geom_local))) AS x,
                   ST_Y(ST_Centroid(ST_Collect(sz.geom_local))) AS y,
                   count(DISTINCT sz.id_base_site) AS nb_unites
            FROM sz LEFT JOIN gn_monitoring.t_sites_groups sg ON sg.id_sites_group::text = sz.id_aire
            GROUP BY sz.id_aire""", module=module)

    def createurs_aires_monitoring(self, module: str) -> list[dict]:
        """Créateur (id_inventor) et année de création du site le plus ancien de chaque aire du module. Organisme et
        email servent seulement à la catégorie (jamais affichés)."""
        return self._fetch(f"""WITH {SITES_MON},
            premier AS (SELECT DISTINCT ON (sz.id_aire) sz.id_aire, s.meta_create_date, s.id_inventor
                        FROM sz JOIN gn_monitoring.t_base_sites s ON s.id_base_site = sz.id_base_site
                        ORDER BY sz.id_aire, s.meta_create_date NULLS LAST, s.id_base_site)
            SELECT p.id_aire, extract(year FROM p.meta_create_date)::int AS annee_creation,
                   bo.nom_organisme AS organisme, tr.email, tr.id_role IS NOT NULL AS connu
            FROM premier p
            LEFT JOIN utilisateurs.t_roles tr ON tr.id_role = p.id_inventor
            LEFT JOIN utilisateurs.bib_organismes bo ON bo.id_organisme = tr.id_organisme""", module=module)

    def unites_monitoring(self, module: str) -> list[dict]:
        return self._fetch(f"""WITH {SITES_MON}
            SELECT sz.id_base_site::text AS id_unite, sz.id_aire, sz.base_site_name AS nom_unite FROM sz""",
                           module=module)

    def passages_monitoring(self, module: str, debut: int, heures_visite: bool = False) -> list[dict]:
        """Visites (v_suivi_passage : durée retenue, estimée ou non). heures_visite : durée lue dans les heures de
        début et de fin de la visite (t_visit_complements : STERF, que la vue ne lit pas)."""
        duree = DUREE_HEURES_VISITE if heures_visite else "v.duree_retenue_min"
        estimee = "false" if heures_visite else "coalesce(v.duree_estimee, false)"
        return self._fetch(f"""WITH {SITES_MON}
            SELECT v.id_base_visit AS id_passage, sz.id_aire, v.id_base_site::text AS id_unite,
                   v.date_passage AS date,
                   (SELECT count(*) FROM gn_monitoring.t_observations o WHERE o.id_base_visit = v.id_base_visit)
                     AS nb_donnees,
                   {duree} AS duree_min, {estimee} AS duree_estimee
            FROM gn_monitoring.v_suivi_passage v
            JOIN sz ON sz.id_base_site = v.id_base_site
            LEFT JOIN gn_monitoring.t_visit_complements vc ON vc.id_base_visit = v.id_base_visit
            WHERE v.module_code = %(module)s AND v.annee >= %(debut)s""", module=module, debut=int(debut))

    def observateurs_monitoring(self, module: str) -> list[dict]:
        """Observateurs des visites du module ; la colonne categorie de la vue n'est pas lue (règle du rapport)."""
        return self._fetch("""
            SELECT po.id_base_visit AS id_passage, po.id_role, po.observateur AS nom, po.email,
                   po.nom_organisme_brut AS organisme
            FROM gn_monitoring.v_suivi_passage_observateur po WHERE po.module_code = %(module)s""", module=module)

    def observations_monitoring(self, module: str, annee_min: int) -> list[dict]:
        if module not in EFFECTIFS:
            raise ValueError(f"Module sans règle d'effectif : {module!r}")
        return self._fetch(f"""WITH {SITES_MON}
            SELECT o.id_base_visit AS id_passage, t.cd_ref,
                   {NOM_VERN} AS nom, sum({EFFECTIFS[module]}) AS effectif
            FROM gn_monitoring.t_base_visits v
            JOIN gn_commons.t_modules m ON m.id_module = v.id_module AND m.module_code = %(module)s
            JOIN sz ON sz.id_base_site = v.id_base_site
            JOIN gn_monitoring.t_observations o ON o.id_base_visit = v.id_base_visit
            LEFT JOIN gn_monitoring.t_observation_complements c ON c.id_observation = o.id_observation
            JOIN taxonomie.taxref t ON t.cd_nom = o.cd_nom
            WHERE v.visit_date_min >= make_date(%(annee_min)s, 1, 1)
            GROUP BY 1, 2, 3""", module=module, annee_min=int(annee_min))

    def etats_pop(self, vue: str) -> list[dict]:
        if vue not in VUES_ETATS:
            raise ValueError(f"Vue inconnue : {vue!r}")
        return self._fetch(f"""SELECT id_sites_group::text AS id_aire, annee AS saison, etat_aire AS etat
                               FROM gn_monitoring.{vue} WHERE id_sites_group IS NOT NULL""")

    def anomalies_pop(self, vue: str, annee: int) -> list[dict]:
        """Anomalies de saisie de l'année dans la zone (sans email ni observateurs)."""
        if vue not in VUES_ANOMALIES:
            raise ValueError(f"Vue inconnue : {vue!r}")
        return self._fetch(f"""WITH {{ZONE}}
            SELECT a.code_anomalie AS code, a.libelle, a.aire, a.{VUES_ANOMALIES[vue]} AS unite,
                   a.date_passage AS date
            FROM gn_monitoring.{vue} a, zone z
            WHERE a.annee = %(annee)s AND (a.geom IS NULL OR ST_Intersects(a.geom, z.geom))
            ORDER BY a.code_anomalie, a.aire""", annee=int(annee))
