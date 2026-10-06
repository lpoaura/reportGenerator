"""
Requêtes du dossier éolien. Toutes lisent la vue matérialisée principale
(créée par la brique socle_data avec les paramètres du dossier) : pas de VM
secondaires à créer / supprimer comme dans les anciens scripts R.
"""

from psycopg.rows import dict_row

from reportgenerator.analysis.eolien import selections as sel
from reportgenerator.db_auth import get_connection

VM = "lpoaura_afo.vm_reportgenerator_data"
NOM_VERN = (
    "trim(REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),"
    "'(La)',''),'(Le)',''),'(L'')',''))"
)

POINT_COLUMNS = f"""s.id_synthese, s.cd_ref, {NOM_VERN} as nom_vern, s.vn_nom_sci as lb_nom,
                    s.famille, s.ordre, s.oiso_status_nidif, s.behaviour, s.count_max,
                    s.date_max, extract(year from s.date_max)::int as annee, s.anneau_ordre,
                    s.lr_aura, s.lr_fr_nich, s.sensibilite_eolien,
                    ST_AsText(s.the_geom_local) as geom"""


class EolienQueries:
    def __init__(self, synthese_queries):
        self.service_name = synthese_queries.service_name
        self.id_area = int(synthese_queries.id_area)
        self.anneaux_km = synthese_queries.anneaux_km

    def _fetch(self, sql, params=None):
        with get_connection(self.service_name) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def species_ring_stats(self, where: str = "true"):
        """Une ligne par (espèce, anneau) : nb données, dernière année,
        effectif max, meilleur statut de nidification + statuts de l'espèce."""
        sql = f"""
            select s.cd_ref, s.anneau_ordre,
                   max({NOM_VERN}) as nom_vern,
                   max(s.vn_nom_sci) as lb_nom,
                   max(s.famille) as famille,
                   max(s.ordre) as ordre,
                   max(s.prot_nat) as prot_nat,
                   max(s.lr_france) as lr_france,
                   max(coalesce(s.lr_fr_nich, s.lr_france)) as lr_fr_nich,
                   max(s.lr_fr_hiv) as lr_fr_hiv,
                   max(s.lr_fr_migr) as lr_fr_migr,
                   max(s.lr_aura) as lr_aura,
                   max(s.lr_auv) as lr_auv,
                   max(s.lr_ra) as lr_ra,
                   max(s.sensibilite_eolien) as sensibilite,
                   count(distinct s.id_synthese) as nb_obs,
                   max(extract(year from s.date_max))::int as derniere_annee,
                   max(s.count_max) as effectif_max,
                   max(case s.oiso_status_nidif when 'Certain' then 3 when 'Probable' then 2
                                                when 'Possible' then 1 else 0 end) as code_nidif
            from {VM} s
            where {sel.both(sel.OISEAUX, where)}
            group by s.cd_ref, s.anneau_ordre
        """
        return self._fetch(sql)

    def points(self, where: str, extra_columns: str = ""):
        """Observations ponctuelles (WKT) pour les couches GPKG des cartes."""
        sql = f"""
            select {POINT_COLUMNS} {extra_columns}
            from {VM} s
            where {sel.both(sel.OISEAUX, where)}
        """
        return self._fetch(sql)

    def perimetres(self):
        """Zone d'étude + un polygone (plein) par anneau, pour la légende des cartes."""
        unions = ["select 'Zone d''étude' as secteur, 0 as ordre, z.geom from z"]
        for i, km in enumerate(self.anneaux_km, start=1):
            unions.append(
                f"select 'Contour {km:g} km', {i}, ST_Buffer(z.geom, {km * 1000}) from z"
            )
        sql = f"""
            with z as (select l.geom from ref_geo.l_areas l
                       where l.id_area = {self.id_area}
                       and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying))
            {' union all '.join(unions)}
        """
        return self._fetch(sql)

    def nidification_tampons(self, tampons_km: dict, statuts=("Certain",)):
        """Tampons autour des sites de nidification (méthode SRE), fusionnés par espèce.
        tampons_km : {nom scientifique: rayon en km}."""
        if not tampons_km:
            return []
        sql = f"""
            with t as (select * from unnest(%s::text[], %s::numeric[]) as t(lb_nom, km))
            select t.lb_nom, max({NOM_VERN}) as nom_vern, t.km as distance_km,
                   count(distinct s.id_synthese) as nb_data,
                   ST_Union(ST_Buffer(s.the_geom_local, t.km * 1000)) as geom
            from {VM} s
            join t on s.vn_nom_sci = t.lb_nom
            where s.oiso_status_nidif = any(%s::text[])
            group by t.lb_nom, t.km
        """
        # types homogènes : psycopg refuse une liste mêlant int et float (5 et 2.5 du toml)
        noms = [str(nom) for nom in tampons_km]
        rayons = [float(km) for km in tampons_km.values()]
        return self._fetch(sql, (noms, rayons, [str(s) for s in statuts]))

    def sensibilite_mailles(self):
        """Indice de sensibilité par maille (grille de la VM) :
        note max des espèces (0-4) +1 nicheur, +1 dortoir, +1 migration
        (rapaces / grands voiliers). Le total est calculé en Python."""
        sql = f"""
            select s.geom_maille, s.id_area,
                   coalesce(max(s.sensibilite_eolien), 0) as sensi_especes,
                   max(case when {sel.both(sel.NICHEUR_PROBABLE_CERTAIN, sel.GROUPES_ENJEUX)} then 1 else 0 end)
                       as bonus_nidif,
                   max(case when {sel.both(sel.DORTOIR, sel.GROUPES_ENJEUX)} then 1 else 0 end) as bonus_dortoir,
                   max(case when {sel.both(sel.MIGRATION, sel.GROUPES_ENJEUX)} then 1 else 0 end) as bonus_migration,
                   count(distinct s.id_synthese) as nb_data
            from {VM} s
            where {sel.OISEAUX}
            group by s.geom_maille, s.id_area
        """
        return self._fetch(sql)

    def fetch(self, sql):
        """Requête brute (couches QGIS de compatibilité, cf. couches_qgis.py)."""
        return self._fetch(sql)
