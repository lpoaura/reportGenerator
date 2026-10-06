"""
Couches du projet QGIS éolien, exportées sous les NOMS ET CHAMPS de l'ancien
workflow R (GPKG "data_eolien_interne" de traitement_generale_v2.R).

Le projet modèle Eolienne_QGIS.qgs (styles, filtres "subset", mises en page)
fonctionne ainsi sans modification : ses couches pointent vers
<layername>.gpkg|layername=<layername> et filtrent sur nom_vern, famille,
ordre, nb_annee, esp_enjeux...

nom_vern = vn_nom_fr complet (ex. 'Héron garde-boeufs, Pique bœufs'), comme
dans le R : les filtres du projet en dépendent.
"""

from reportgenerator.analysis.eolien import selections as sel

VM = "lpoaura_afo.vm_reportgenerator_data"

LR_MENACEE = (
    "concat_ws(',', s.lr_france, s.lr_auv, s.lr_ra, s.lr_aura) ~ '(CR|EN|VU)'"
)

STATUT_NIDIF_R = """case when bool_or(s.oiso_status_nidif = 'Certain') then 'Nicheur certain'
                         when bool_or(s.oiso_status_nidif = 'Probable') then 'Nicheur probable'
                         else 'Nicheur possible' end"""

# 11_vm_nidif.sql : nicheurs probables / certains, rapaces, grands voiliers ou espèces menacées,
# une ligne par espèce et par point
NIDIF_SQL = f"""
    select row_number() over (order by t.nom_vern) as id, t.*
    from (
        select s.vn_nom_fr as nom_vern, s.cd_ref as cd_nom, s.famille, s.ordre,
               count(distinct s.id_synthese) as nb_data,
               max(extract(year from s.date_max))::int as derniere_obs,
               count(distinct extract(year from s.date_max))::int as nb_annee,
               {STATUT_NIDIF_R} as oiso_status_nidif,
               ST_AsText(s.the_geom_local) as geom
        from {VM} s
        where {sel.both(sel.OISEAUX, sel.NICHEUR_PROBABLE_CERTAIN)}
        and ({sel.GROUPES_ENJEUX} or {LR_MENACEE})
        group by s.vn_nom_fr, s.cd_ref, s.famille, s.ordre, s.the_geom_local
    ) t
"""

# vm_eolienne_nidif_cn : Cigogne noire floutée à la maille 5 km (donnée sensible)
NIDIF_CN_SQL = f"""
    select row_number() over () as id, s.vn_nom_fr as nom_vern, s.cd_ref as cd_nom,
           s.famille, s.ordre,
           count(distinct s.id_synthese) as nb_data,
           max(extract(year from s.date_max))::int as derniere_obs,
           count(distinct extract(year from s.date_max))::int as nb_annee,
           {STATUT_NIDIF_R} as oiso_status_nidif,
           g.geom
    from {VM} s
    join ref_geo.mv_aura_gridl93_5x5 g on ST_Within(s.the_geom_local, g.geom)
    where {sel.NICHEUR_PROBABLE_CERTAIN} and s.vn_nom_sci = 'Ciconia nigra'
    group by s.vn_nom_fr, s.cd_ref, s.famille, s.ordre, g.geom
"""

# 14_vm_nidif_dortoir.sql
DORTOIRS_SQL = f"""
    select row_number() over (order by t.nom_vern) as id, t.*
    from (
        select s.vn_nom_fr as nom_vern, s.cd_ref as cd_nom, s.famille, s.ordre,
               max(extract(year from s.date_max))::int as derniere_obs,
               count(distinct s.id_synthese) as nb_data,
               ST_AsText(s.the_geom_local) as geom
        from {VM} s
        where {sel.both(sel.OISEAUX, sel.DORTOIR, sel.GROUPES_ENJEUX)}
        group by s.vn_nom_fr, s.cd_ref, s.famille, s.ordre, s.the_geom_local
    ) t
"""

# 16_vm_migration_all.sql
MIGRATION_SQL = f"""
    select row_number() over (order by t.nom_vern) as id, t.*
    from (
        select s.vn_nom_fr as nom_vern, s.cd_ref as cd_nom, s.famille, s.ordre,
               max(s.count_max) as nb_ind_max,
               max(extract(year from s.date_max))::int as derniere_obs,
               case when {sel.GROUPES_ENJEUX} then 'enjeux' else 'autres' end as esp_enjeux,
               ST_AsText(s.the_geom_local) as geom
        from {VM} s
        where {sel.both(sel.OISEAUX, sel.MIGRATION)}
        group by s.vn_nom_fr, s.cd_ref, s.famille, s.ordre, s.the_geom_local,
                 case when {sel.GROUPES_ENJEUX} then 'enjeux' else 'autres' end
    ) t
"""

# 03_vm_data.sql (vm_eolienne) : observations d'oiseaux
DONNEES_SQL = f"""
    select s.id_synthese as id, s.date_max as datetime, s.cd_ref as cd_nom, s.count_max,
           s.oiso_code_nidif, s.oiso_status_nidif, s.behaviour, s.comment_description,
           s.vn_nom_fr as nom_vern, s.classe, s.ordre, s.famille,
           ST_AsText(s.the_geom_local) as geom
    from {VM} s
    where {sel.OISEAUX}
"""

# 04_vm_connaissance_oiseau.sql (mailles sans donnée non incluses)
CONNAISSANCE_SQL = f"""
    select row_number() over (order by s.id_area) as id, s.id_area,
           count(distinct s.id_synthese) as sum_nb_data,
           count(distinct s.cd_ref) as sum_nb_esp,
           s.geom_maille as geom
    from {VM} s
    where {sel.OISEAUX}
    group by s.id_area, s.geom_maille
"""


def limit_sql(id_area: int, anneaux_km) -> str:
    """01_vm_limit.sql : un polygone plein par contour, area_name = 'contour X km'."""
    unions = [
        f"select ST_Buffer(z.geom, {km * 1000}) as geom, 'contour {km:g} km' as area_name from z"
        for km in anneaux_km
    ]
    return f"""
        with z as (select l.geom from ref_geo.l_areas l
                   where l.id_area = {int(id_area)}
                   and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying))
        select row_number() over () as id, c.geom, c.area_name
        from ({' union all '.join(unions)}) c
    """


def zone_etude_sql(id_area: int, area_name: str) -> str:
    """00_vm_zone_etude.sql."""
    nom = area_name.replace("'", "''")
    return f"""
        select 1 as id, '{nom}' as area_name, l.geom, '{nom}' as name_project
        from ref_geo.l_areas l
        where l.id_area = {int(id_area)}
        and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)
    """
