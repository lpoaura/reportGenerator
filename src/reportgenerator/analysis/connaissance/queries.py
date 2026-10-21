"""Requêtes de l'état des connaissances : sur la VM principale (mailles, espèces) et sur la synthèse (pool local)."""

from reportgenerator.analysis.common.vm_queries import VM, VmQueries
from reportgenerator.analysis.connaissance.indicateurs import TOUS_GROUPES
from reportgenerator.analysis.connaissance.selections import ESPECE
from reportgenerator.queries import sql_literals


def _groupes_sql(groupes) -> str:
    return f"and s.tx_group2_inpn_v2 in ({sql_literals(groupes)})" if groupes else ""


class ConnaissanceQueries(VmQueries):
    def _zone(self) -> str:
        return f"z as (select l.geom from ref_geo.l_areas l where l.id_area = {self.id_area})"

    def especes_par_groupe(self, rayon_m: float, groupes=()):
        """Par groupe : espèces dans la zone (anneau 0) et dans l'emprise des mailles (zone + rayon_m)."""
        sql = f"""
            with {self._zone()}
            select s.tx_group2_inpn_v2 as groupe,
                   count(distinct s.cd_ref) filter (where {ESPECE} and s.anneau_ordre = 0) as nb_especes_zone,
                   count(distinct s.cd_ref) filter (where {ESPECE}) as nb_especes
            from {VM} s, z
            where ST_DWithin(s.the_geom_local, z.geom, {float(rayon_m)}) {_groupes_sql(groupes)}
            group by 1
        """
        return self._fetch(sql)

    def mailles(self, rayon_m: float, code_grille: str, groupes=(), enjeu_sql="false"):
        """Couche connaissance_mailles : par maille de la grille code_grille et par groupe (+ « Tous groupes » =
        les groupes analysés) : données, jours d'observation, espèces, espèces à enjeux, sur la zone + rayon_m.
        La maille est calculée spatialement (la grille de la VM peut être différente, ex. dossier générique)."""
        sql = f"""
            with {self._zone()},
            d as (select s.tx_group2_inpn_v2, s.date_max, s.cd_ref, s.the_geom_local,
                         ({ESPECE}) as espece, ({enjeu_sql}) as enjeu
                  from {VM} s, z
                  where ST_DWithin(s.the_geom_local, z.geom, {float(rayon_m)}) {_groupes_sql(groupes)}),
            m as (select d.*, g.id_area, g.geom
                  from d
                  join lateral (select la.id_area, la.geom from ref_geo.l_areas la
                                where la.id_type = ref_geo.get_id_area_type(%s)
                                  and ST_Intersects(la.geom, d.the_geom_local)
                                order by la.id_area limit 1) g on true)
            select coalesce(m.tx_group2_inpn_v2, '{TOUS_GROUPES}') as groupe, m.id_area,
                   count(*) as nb_donnees,
                   count(distinct m.date_max) as nb_jours,
                   count(distinct m.cd_ref) filter (where m.espece) as nb_especes,
                   count(distinct m.cd_ref) filter (where m.espece and m.enjeu) as nb_enjeux,
                   ST_AsText(m.geom) as geom
            from m
            group by grouping sets ((m.tx_group2_inpn_v2, m.id_area, m.geom), (m.id_area, m.geom))
        """
        return self._fetch(sql, (code_grille,))

    def grille(self, code_grille: str, rayon_m: float):
        """Couche connaissance_grille : toutes les mailles de la zone + rayon_m, y compris celles sans donnée."""
        sql = f"""
            select la.id_area, ST_AsText(la.geom) as geom
            from ref_geo.l_areas la,
                 (select ST_Buffer(l.geom, {float(rayon_m)}) as geom from ref_geo.l_areas l
                  where l.id_area = {self.id_area}) z
            where la.id_type = ref_geo.get_id_area_type(%s) and ST_Intersects(la.geom, z.geom)
        """
        return self._fetch(sql, (code_grille,))

    def pool_local(self, rayon_km: float, annees=None, statuts_validation=("0", "1", "2")):
        """Nombre d'espèces connues par groupe dans un rayon autour de la zone (référence des cartes). Mêmes règles
        que la VM : période (annees, None = toutes), statuts de validation, espèces (sous-espèces rattachées),
        groupes taxonomiques ; toutes les données de la synthèse dans le rayon (pas seulement celles de la VM)."""
        statuts = ", ".join(f"ref_nomenclatures.get_id_nomenclature('STATUT_VALID', '{int(c)}')"
                            for c in statuts_validation)
        periode = f"and s.date_max >= make_date(extract(year from now())::int - {int(annees)}, 1, 1)" if annees else ""
        sql = f"""
            with {self._zone()},
            d as (
                select distinct case when t.id_rang = 'SSES' then coalesce(tsup.cd_ref, t.cd_ref) else t.cd_ref end
                           as cd_ref,
                       t.ordre, t.group2_inpn, t.group3_inpn
                from gn_synthese.synthese s
                join taxonomie.taxref t on t.cd_nom = s.cd_nom
                left join taxonomie.taxref tsup on tsup.cd_nom = t.cd_sup, z
                where ST_DWithin(s.the_geom_local, z.geom, {float(rayon_km) * 1000})
                  and s.id_nomenclature_observation_status = 89
                  and s.id_nomenclature_valid_status = any(array[{statuts}])
                  {periode}
                  and t.id_rang in ('ES', 'SSES') and t.regne = 'Animalia')
            select case when d.ordre = 'Chiroptera' then 'Chauves-souris'
                        when mcs.groupe_taxo_fr is not null then mcs.groupe_taxo_fr
                        when d.group2_inpn in ('Insectes', 'Arachnides') then d.group3_inpn
                        else d.group2_inpn end as groupe,
                   count(distinct d.cd_ref) as nb_especes
            from d
            left join (select distinct on (cd_ref) cd_ref, groupe_taxo_fr from taxonomie.mv_c_statut order by cd_ref)
                 mcs on mcs.cd_ref = d.cd_ref
            group by 1
        """
        return {r["groupe"]: r["nb_especes"] for r in self._fetch(sql) if r["groupe"]}

    def enveloppe_zone(self) -> list[float]:
        """Rectangle englobant la zone d'étude [xmin, ymin, xmax, ymax] (Lambert 93) : base des emprises."""
        sql = f"""
            select ST_XMin(b) as xmin, ST_YMin(b) as ymin, ST_XMax(b) as xmax, ST_YMax(b) as ymax
            from (select Box2D(l.geom) as b from ref_geo.l_areas l where l.id_area = {self.id_area}) e
        """
        r = self._fetch(sql)[0]
        return [float(r["xmin"]), float(r["ymin"]), float(r["xmax"]), float(r["ymax"])]
