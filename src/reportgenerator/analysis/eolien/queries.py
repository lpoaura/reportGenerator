"""
Requêtes du dossier éolien. Toutes lisent la vue matérialisée principale
(créée par la brique socle_data avec les paramètres du dossier) : pas de VM
secondaires à créer / supprimer comme dans les anciens scripts R.
"""

from reportgenerator.analysis.common.vm_queries import VM, VmQueries
from reportgenerator.analysis.common.vm_queries import with_params as _with_params
from reportgenerator.analysis.eolien import selections as sel

__all__ = ["VM", "EolienQueries", "blur_sql"]

NOM_VERN = (
    "trim(REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),"
    "'(La)',''),'(Le)',''),'(L'')',''))"
)

POINT_COLUMNS = f"""s.id_synthese, s.cd_ref, {NOM_VERN} as nom_vern, s.vn_nom_sci as lb_nom,
                    s.famille, s.ordre, s.oiso_status_nidif, s.behaviour, s.count_max,
                    s.date_max, extract(year from s.date_max)::int as annee, s.anneau_ordre,
                    s.lr_aura, s.lr_fr_nich, s.sensibilite_eolien,
                    ST_AsText(s.the_geom_local) as geom"""


class EolienQueries(VmQueries):
    def species_ring_stats(self, where: str = "true", taxon: str = sel.OISEAUX):
        """Une ligne par (taxon, anneau) : nb données, dernière année,
        effectif max, meilleur statut de nidification + statuts du taxon."""
        sql = f"""
            select s.cd_ref, s.anneau_ordre,
                   max(s.id_rang) as id_rang,
                   max(s.n2k) as n2k,
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
                   -- observations distinctes (jour x lieu) : les enregistrements acoustiques de chiroptères
                   -- produisent des centaines de contacts pour un même taxon, un même jour, un même point
                   count(distinct (s.date_max, ST_AsText(s.the_geom_local))) as nb_sessions,
                   max(extract(year from s.date_max))::int as derniere_annee,
                   max(s.count_max) as effectif_max,
                   max(case s.oiso_status_nidif when 'Certain' then 3 when 'Probable' then 2
                                                when 'Possible' then 1 else 0 end) as code_nidif,
                   -- statuts biologiques observés : listes rouges migrateur / hivernant de l'indice de vulnérabilité
                   bool_or({sel.MIGRATION}) as migrateur,
                   bool_or({sel.HIVERNANT}) as hivernant
            from {VM} s
            where {sel.both(taxon, where)}
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

    def nidification_mailles(self, especes: list[dict]):
        """Couche des cartes de nidification par groupe : une ligne par espèce et par maille (regroupement des sites
        proches), point au centre des données de la maille, ou au centre de la maille pour une espèce floutée.
        especes : [{cd_ref, possible (nicheur possible accepté), maille_m, flouter}] ; sinon probable ou certain."""
        if not especes:
            return []
        sql = f"""
            with p as (select * from unnest({{P}}::int[], {{P}}::bool[], {{P}}::numeric[], {{P}}::bool[])
                       as p(cd_ref, possible, maille, flouter)),
                 d as (
                    select s.cd_ref, p.maille, p.flouter, s.id_synthese, extract(year from s.date_max)::int as annee,
                           s.oiso_status_nidif, coalesce(s.donnee_cachee, false) as cachee, s.precision_geo,
                           s.the_geom_local as geom,
                           floor(ST_X(s.the_geom_local) / p.maille) as cx,
                           floor(ST_Y(s.the_geom_local) / p.maille) as cy
                    from {VM} s
                    join p on p.cd_ref = s.cd_ref
                    where s.oiso_status_nidif in ('Probable', 'Certain')
                       or (p.possible and s.oiso_status_nidif = 'Possible'))
            select d.cd_ref, count(distinct d.id_synthese) as nb_data, count(distinct d.annee)::int as nb_annee,
                   max(d.annee) as derniere_obs,
                   case when bool_or(d.oiso_status_nidif = 'Certain') then 'Nicheur certain'
                        when bool_or(d.oiso_status_nidif = 'Probable') then 'Nicheur probable'
                        else 'Nicheur possible' end as statut_nidif,
                   bool_or(d.cachee) as donnee_cachee, max(d.precision_geo) as precision_geo,
                   ST_AsText(case when bool_or(d.flouter)
                                  then ST_SetSRID(ST_MakePoint((d.cx + 0.5) * max(d.maille),
                                                               (d.cy + 0.5) * max(d.maille)), 2154)
                                  else ST_Centroid(ST_Collect(d.geom)) end) as geom
            from d
            group by d.cd_ref, d.cx, d.cy
        """
        params = ([int(e["cd_ref"]) for e in especes], [bool(e.get("possible")) for e in especes],
                  [float(e["maille_m"]) for e in especes], [bool(e.get("flouter")) for e in especes])
        return self._fetch(_with_params(sql), params)

    def dortoirs_zones(self, cd_refs, rayon_m):
        """Couche des cartes de dortoirs par groupe : zones de dortoir d'une espèce = tampons de rayon_m autour de ses
        données de dortoir (rapaces, grands voiliers), fusionnés quand ils se touchent ; une ligne par zone."""
        if not cd_refs:
            return []
        sql = f"""
            with d as (
                select s.cd_ref, s.id_synthese, extract(year from s.date_max)::int as annee,
                       coalesce(s.donnee_cachee, false) as cachee, s.the_geom_local as p
                from {VM} s
                where {sel.both(sel.DORTOIR, sel.GROUPES_ENJEUX)} and s.cd_ref = any({{P}}::int[])),
                 z as (
                select u.cd_ref, row_number() over () as zid, u.geom
                from (select d.cd_ref, (ST_Dump(ST_Union(ST_Buffer(d.p, {float(rayon_m)})))).geom as geom
                      from d group by d.cd_ref) u),
                 st as (
                select z.zid, count(distinct d.id_synthese) as nb_data, count(distinct ST_AsBinary(d.p)) as nb_sites,
                       max(d.annee) as derniere_obs, count(distinct d.annee)::int as nb_annee,
                       bool_or(d.cachee) as donnee_cachee
                from z
                join d on d.cd_ref = z.cd_ref and ST_Intersects(d.p, z.geom)
                group by z.zid)
            select z.cd_ref, st.nb_data, st.nb_sites, st.derniere_obs, st.nb_annee, st.donnee_cachee,
                   ST_AsText(z.geom) as geom
            from z
            join st on st.zid = z.zid
        """
        return self._fetch(_with_params(sql), ([int(c) for c in cd_refs],))

    def migration_points(self, cd_refs):
        """Couche des cartes de migration par espèce : une ligne par espèce et par lieu, effectif maximal."""
        if not cd_refs:
            return []
        sql = f"""
            select s.cd_ref, count(distinct s.id_synthese) as nb_data, max(s.count_max) as nb_ind_max,
                   max(extract(year from s.date_max))::int as derniere_obs,
                   bool_or(coalesce(s.donnee_cachee, false)) as donnee_cachee, max(s.precision_geo) as precision_geo,
                   ST_AsText(s.the_geom_local) as geom
            from {VM} s
            where {sel.MIGRATION} and s.cd_ref = any({{P}}::int[])
            group by s.cd_ref, s.the_geom_local
        """
        return self._fetch(_with_params(sql), ([int(c) for c in cd_refs],))

    def distances_especes(self, cd_refs):
        """Par espèce : distance (m) de la donnée la plus proche de la zone d'étude (0 = dedans), et du site de
        nidification probable ou certain le plus proche, avec son statut et son année (phrases des espèces les
        plus vulnérables)."""
        if not cd_refs:
            return []
        nicheur = sel.NICHEUR_PROBABLE_CERTAIN
        sql = f"""
            with z as (select l.geom from ref_geo.l_areas l
                       where l.id_area = {int(self.id_area)}
                       and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)),
                 d as (select s.cd_ref, s.oiso_status_nidif, extract(year from s.date_max)::int as annee,
                              {nicheur} as nicheur, ST_Distance(s.the_geom_local, z.geom) as dist
                       from {VM} s, z
                       where s.cd_ref = any({{P}}::int[]))
            select d.cd_ref, min(d.dist) as dist_min_m,
                   min(d.dist) filter (where d.nicheur) as dist_nidif_m,
                   (array_agg(d.oiso_status_nidif order by d.dist, d.annee desc) filter (where d.nicheur))[1]
                       as statut_nidif_proche,
                   (array_agg(d.annee order by d.dist, d.annee desc) filter (where d.nicheur))[1] as annee_nidif_proche
            from d
            group by d.cd_ref
        """
        return self._fetch(_with_params(sql), ([int(c) for c in cd_refs],))

    def sensibilite_mailles(self, vulnerabilites: dict | None = None):
        """Indice de sensibilité par maille (grille de la VM) :
        note max des espèces (0-4) +1 nicheur, +1 dortoir, +1 migration
        (rapaces / grands voiliers). Le total est calculé en Python.
        vulnerabilites ({cd_ref: indice}) : ajoute vuln_especes, l'indice de vulnérabilité max de la maille
        (variante de la carte 17 bis)."""
        notes = vulnerabilites or {}
        cd_refs = [int(k) for k in notes] or [0]
        valeurs = [float(v) for v in notes.values()] or [0.0]
        sql = f"""
            with v as (select * from unnest({{P}}::int[], {{P}}::numeric[]) as v(cd_ref, note))
            select s.geom_maille, s.id_area,
                   coalesce(max(s.sensibilite_eolien), 0) as sensi_especes,
                   coalesce(max(v.note), 0) as vuln_especes,
                   max(case when {sel.both(sel.NICHEUR_PROBABLE_CERTAIN, sel.GROUPES_ENJEUX)} then 1 else 0 end)
                       as bonus_nidif,
                   max(case when {sel.both(sel.DORTOIR, sel.GROUPES_ENJEUX)} then 1 else 0 end) as bonus_dortoir,
                   max(case when {sel.both(sel.MIGRATION, sel.GROUPES_ENJEUX)} then 1 else 0 end) as bonus_migration,
                   count(distinct s.id_synthese) as nb_data
            from {VM} s
            left join v on v.cd_ref = s.cd_ref
            where {sel.OISEAUX} and s.geom_maille is not null
            group by s.geom_maille, s.id_area
        """
        return self._fetch(_with_params(sql), (cd_refs, valeurs))

    def hors_region(self, region: str):
        """Part (%) et géométrie de l'aire d'étude située hors de la région couverte par la base."""
        sql = f"""
            with z as (select ST_Buffer(l.geom, {max(self.anneaux_km) * 1000}) as geom from ref_geo.l_areas l
                       where l.id_area = {self.id_area}
                       and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)),
                 r as (select ST_Union(geom) as geom from ref_geo.mv_fr_region where area_name = %s)
            select round((100 * ST_Area(ST_Difference(z.geom, r.geom)) / ST_Area(z.geom))::numeric, 1)
                       as pct_hors_region,
                   ST_Difference(z.geom, r.geom) as geom
            from z, r
        """
        rows = self._fetch(sql, (region,))
        return rows[0] if rows else {"pct_hors_region": None, "geom": None}

    def qualite_donnees(self):
        """Par groupe : nb de données, localisées au lieu-dit (centroïde), cachées par l'observateur,
        et nb d'observations distinctes (taxon, jour, lieu)."""
        sql = f"""
            select case when {sel.CHIROPTERES} then 'chiro' else 'oiseaux' end as groupe,
                   count(*) as nb_donnees,
                   count(*) filter (where s.precision_geo in ('place', 'subplace')) as nb_lieu_dit,
                   count(*) filter (where s.donnee_cachee) as nb_cachees,
                   count(distinct (s.cd_ref, s.date_max, ST_AsText(s.the_geom_local))) as nb_observations
            from {VM} s
            group by 1
        """
        return {row["groupe"]: row for row in self._fetch(sql)}

    # =========================================================
    # CHIROPTÈRES
    # =========================================================

    def chiro_gites_stats(self, floutage_m=0):
        """Une ligne par (taxon, type de gîte, anneau) : nb de sites, effectif max, dernière année."""
        site = blur_sql("s.the_geom_local", floutage_m)
        sql = f"""
            select s.cd_ref, s.anneau_ordre, {sel.TYPE_GITE_SQL} as type_gite,
                   max(s.id_rang) as id_rang, max({NOM_VERN}) as nom_vern, max(s.vn_nom_sci) as lb_nom,
                   count(distinct ST_AsText({site})) as nb_sites,
                   max(s.count_max) as effectif_max,
                   max(extract(year from s.date_max))::int as derniere_annee
            from {VM} s
            where {sel.both(sel.CHIROPTERES, sel.CHIRO_GITE)}
            group by s.cd_ref, s.anneau_ordre, {sel.TYPE_GITE_SQL}
        """
        return self._fetch(sql)

    def chiro_gites_resume(self, floutage_m=0):
        site = blur_sql("s.the_geom_local", floutage_m)
        sql = f"""
            select count(distinct ST_AsText({site})) filter (where {sel.CHIRO_COLONIE}) as nb_colonies,
                   count(distinct ST_AsText({site})) filter (where {sel.CHIRO_GITE} and not {sel.CHIRO_COLONIE})
                       as nb_gites,
                   (min(extract(year from s.date_max)) filter (where {sel.CHIRO_COLONIE}))::int
                       as annee_min_colonies,
                   (max(extract(year from s.date_max)) filter (where {sel.CHIRO_COLONIE}))::int
                       as annee_max_colonies
            from {VM} s
            where {sel.CHIROPTERES}
        """
        return self._fetch(sql)[0]

    def chiro_periodes(self):
        """Par période (bat_period) : données, espèces, taxons non spécifiques, 3 taxons principaux."""
        sql = f"""
            with p as (
                select coalesce(s.bat_period, 'Non renseignée') as periode, s.cd_ref, s.id_rang,
                       s.id_synthese, {NOM_VERN} as nom_vern
                from {VM} s where {sel.CHIROPTERES}
            ),
            top as (
                select periode, nom_vern, count(*) as n,
                       row_number() over (partition by periode order by count(*) desc, nom_vern) as rang
                from p group by periode, nom_vern
            )
            select p.periode,
                   count(distinct p.id_synthese) as nb_donnees,
                   count(distinct p.cd_ref) filter (where p.id_rang in ('ES', 'SSES')) as nb_especes,
                   count(distinct p.cd_ref) filter (where p.id_rang not in ('ES', 'SSES')) as nb_non_especes,
                   (select string_agg(top.nom_vern || ' (' || top.n || ')', ', ' order by top.rang)
                    from top where top.periode = p.periode and top.rang <= 3) as principales
            from p group by p.periode
        """
        return self._fetch(sql)

    def chiro_points(self, floutage_m=0):
        """Couche vm_eolienne_chiro_data : toutes les données (gîtes floutés si demandé)."""
        geom = f"case when {sel.CHIRO_GITE} then {blur_sql('s.the_geom_local', floutage_m)} else s.the_geom_local end"
        sql = f"""
            select s.id_synthese as id, s.cd_ref as cd_nom, s.vn_nom_fr as nom_vern, s.vn_nom_sci as lb_nom,
                   s.id_rang, s.bat_period as periode,
                   coalesce(s.bat_is_gite, false) as gite, coalesce(s.bat_breed_colo, false) as colonie,
                   s.count_max, s.date_max as datetime, extract(year from s.date_max)::int as annee,
                   s.anneau_ordre, s.lr_aura, s.n2k, s.source, s.precision_geo,
                   coalesce(s.donnee_cachee, false) as donnee_cachee,
                   ST_AsText({geom}) as geom
            from {VM} s
            where {sel.CHIROPTERES}
        """
        return self._fetch(sql)

    def chiro_gites_points(self, floutage_m=0):
        """Couche vm_eolienne_chiro_gites : un point par site, taxon et type de gîte."""
        site = blur_sql("s.the_geom_local", floutage_m)
        sql = f"""
            select row_number() over () as id, t.*
            from (
                select s.cd_ref as cd_nom, max(s.vn_nom_fr) as nom_vern, max(s.vn_nom_sci) as lb_nom,
                       {sel.TYPE_GITE_SQL} as type_gite,
                       count(distinct s.id_synthese) as nb_data, max(s.count_max) as effectif_max,
                       min(extract(year from s.date_max))::int as premiere_obs,
                       max(extract(year from s.date_max))::int as derniere_obs,
                       string_agg(distinct s.bat_period, ', ') as periodes,
                       bool_or(coalesce(s.donnee_cachee, false)) as donnee_cachee,
                       max(s.precision_geo) as precision_geo,
                       ST_AsText({site}) as geom
                from {VM} s
                where {sel.both(sel.CHIROPTERES, sel.CHIRO_GITE)}
                group by s.cd_ref, {sel.TYPE_GITE_SQL}, {site}
            ) t
        """
        return self._fetch(sql)

    def chiro_connaissance_mailles(self):
        """Couche vm_eolienne_etat_connaissance_chiro (mailles avec données)."""
        sql = f"""
            select row_number() over (order by s.id_area) as id, s.id_area,
                   count(distinct s.id_synthese) as sum_nb_data,
                   -- observations (taxon, jour, lieu) : unité du texte, sans les répétitions acoustiques
                   count(distinct (s.cd_ref, s.date_max, ST_AsText(s.the_geom_local))) as sum_nb_obs,
                   count(distinct s.cd_ref) filter (where {sel.CHIRO_ESPECE}) as sum_nb_esp,
                   s.geom_maille as geom
            from {VM} s
            where {sel.CHIROPTERES} and s.geom_maille is not null
            group by s.id_area, s.geom_maille
        """
        return self._fetch(sql)

    def chiro_gite_tampons(self, distances_m: dict, floutage_m=0, defaut_m=1000):
        """Couche vm_eolienne_chiro_gite_tampon : tampons autour des gîtes et colonies,
        rayon par taxon (distances_m : {cd_ref: mètres}, defaut_m pour les taxons sans rayon,
        ex. genres et complexes), fusionnés par taxon."""
        site = blur_sql("s.the_geom_local", floutage_m)
        sql = f"""
            with d as (select * from unnest({{P}}::int[], {{P}}::numeric[]) as d(cd_ref, dist_m))
            select s.cd_ref as cd_nom, max(s.vn_nom_fr) as nom_vern, max(s.vn_nom_sci) as lb_nom,
                   coalesce(d.dist_m, {float(defaut_m)}) as distance_m,
                   (d.dist_m is null) as rayon_par_defaut,
                   count(distinct ST_AsText({site})) as nb_sites,
                   ST_Union(ST_Buffer({site}, coalesce(d.dist_m, {float(defaut_m)}))) as geom
            from {VM} s
            left join d on d.cd_ref = s.cd_ref
            where {sel.both(sel.CHIROPTERES, sel.CHIRO_GITE)}
            group by s.cd_ref, d.dist_m
        """
        cd_refs = [int(k) for k in distances_m] or [0]
        dists = [float(v) for v in distances_m.values()] or [0.0]
        return self._fetch(_with_params(sql), (cd_refs, dists))

    def chiro_sensibilite_mailles(self, scores: dict, score_transit_min=None):
        """Indice chiroptères par maille : classe de vulnérabilité éolien max (1-4)
        +1 colonie, +1 gîte, et +1 transit d'une espèce de vulnérabilité éolien >= score_transit_min
        (None = période non prise en compte, bonus_transit toujours à 0)."""
        cd_refs = [int(k) for k in scores] or [0]
        valeurs = [int(v) for v in scores.values()] or [0]
        if score_transit_min is None:
            transit_sql = "0"
        else:
            transit_sql = (f"max(case when {sel.CHIRO_TRANSIT} and coalesce(sc.score, 0) >= "
                           f"{int(score_transit_min)} then 1 else 0 end)")
        sql = f"""
            with sc as (select * from unnest({{P}}::int[], {{P}}::int[]) as sc(cd_ref, score))
            select s.geom_maille, s.id_area,
                   coalesce(max(sc.score), 0) as sensi_especes,
                   max(case when {sel.CHIRO_COLONIE} then 1 else 0 end) as bonus_colonie,
                   max(case when {sel.CHIRO_GITE} and not {sel.CHIRO_COLONIE} then 1 else 0 end) as bonus_gite,
                   {transit_sql} as bonus_transit,
                   count(distinct s.id_synthese) as nb_data
            from {VM} s
            left join sc on sc.cd_ref = s.cd_ref
            where {sel.CHIROPTERES} and s.geom_maille is not null
            group by s.geom_maille, s.id_area
        """
        return self._fetch(_with_params(sql), (cd_refs, valeurs))


def blur_sql(geom: str, floutage_m) -> str:
    """Floutage d'un point : centre de la maille de floutage_m mètres (0 = position précise)."""
    m = float(floutage_m or 0)
    if m <= 0:
        return geom
    return (f"ST_SetSRID(ST_MakePoint(floor(ST_X({geom}) / {m}) * {m} + {m / 2}, "
            f"floor(ST_Y({geom}) / {m}) * {m} + {m / 2}), 2154)")
