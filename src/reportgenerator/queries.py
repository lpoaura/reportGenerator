#!/bin/python3

from psycopg.rows import dict_row


class SyntheseQueries:
    """Synthese queries"""

    def __init__(self, conn, id_area, buffer):
        self.conn = conn
        self.id_area = id_area
        self.buffer = buffer

    def set_global_data(self):
        """Création de la vue matérialisée pour le rapport"""
        buffer_km = int(self.buffer) 
        id_area = int(self.id_area)  

        sql = f"""
            drop materialized view if exists lpoaura_afo.vm_reportgenerator_data;
            create materialized view lpoaura_afo.vm_reportgenerator_data as
            with zone_etude as (
                select ST_Buffer(l.geom, {buffer_km} * 1000) as geom
                from ref_geo.l_areas l
                where l.id_area = {id_area}
                and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)
                                ),
                obs_info as (  select s.id_synthese
                                        , s.date_max::date as date_max
                                        , case when t.id_rang = 'ES' then t.cd_ref
                                                when t.id_rang = 'SESS' then t.cd_sup
                                                else 0 end as cd_ref
                                        , case when s.count_max = 0 or s.count_max is null then 1
                                                else s.count_max end as count_max
                                        , tcse.bird_breed_code as oiso_code_nidif
                                        , tcse.breed_status as oiso_status_nidif
                                        , s.the_geom_local
                                        , s.comment_description
                                        , s.observers
                                        , tn.label_default as behaviour
                                        , tcse.mortality
                                        , tcse.mortality_cause
                                        , tcse.bat_is_gite
                                        , tcse.bat_breed_colo
                                        , tcse.bat_period
                                        , t.group2_inpn
                                        , t.group3_inpn
                                        , t.ordre
                                        , t.classe
                                        , t.famille
                                    from gn_synthese.synthese s
                                    left join taxonomie.taxref t on s.cd_nom = t.cd_nom
                                    left join src_lpodatas.t_c_synthese_extended tcse on tcse.id_synthese=s.id_synthese
                                    left join ref_nomenclatures.t_nomenclatures tn on s.id_nomenclature_behaviour = tn.id_nomenclature
                                    where s.id_nomenclature_observation_status = 89
                                    and (t.id_rang = 'ES' or t.id_rang = 'SSES')
                                    and s.id_nomenclature_valid_status = ANY (ARRAY[ref_nomenclatures.get_id_nomenclature('STATUT_VALID'::character varying, '2'::character varying), ref_nomenclatures.get_id_nomenclature('STATUT_VALID'::character varying, '1'::character varying)]) is true
                                    --and s.date_max <= date (CONCAT(extract( year from date(now()) - interval '10 year'),'-01-01'))
                                    and  ST_Within(s.the_geom_local, (select geom from zone_etude ))
                                    -- and t.cd_ref not in (select cd_ref from lpoaura_afo.vm_reportgenerator_data)
                ),
                obs_final as ( select  s.*
                                        , mcs.vn_nom_fr
                                        , mcs.vn_nom_sci
                                        , case when mcs.groupe_taxo_fr is not null then mcs.groupe_taxo_fr
                                                    when mcs.groupe_taxo_fr is null and s.group3_inpn = 'Lépidoptères' and s.cd_ref in (1015437, 249667, 716457, 716458, 961903)  then 'Papillons de nuit'
                                                    when mcs.groupe_taxo_fr is null and s.group3_inpn = 'Lépidoptères' and s.cd_ref in (716692)  then 'Papillons de jour'
                                                    when mcs.groupe_taxo_fr is null and s.group2_inpn in ('Insectes','Arachnides') then s.group3_inpn
                                                    when mcs.groupe_taxo_fr is null and s.group2_inpn in ('Oiseaux','Mammifères','Poissons', 'Amphibiens')  then s.group2_inpn
                                                    else s.group2_inpn end  as tx_group2_inpn_v2
                                        , mcs.lr_auv
                                        , lr_ra
                                        , lr_aura
                                        , lr_france
                                        , lr_fr_nich
                                        , lr_fr_hiv
                                        , lr_fr_migr
                                        , lr_euro
                                        , lr_monde
                                        , prot_nat
                                        , n2k
                                        , conv_berne
                                        , conv_bonn
                                        , pna_en_cours
                                        , pna_ex
                            from obs_info s
                            left join taxonomie.mv_c_statut mcs on s.cd_ref = mcs.cd_ref
                            )
            select s.*, la.id_area, la.geom as geom_maille from obs_final s
            left join gn_synthese.cor_area_synthese cas on s.id_synthese = cas.id_synthese
            left join ref_geo.l_areas la on cas.id_area = la.id_area
            where la.id_type = ref_geo.get_id_area_type('M1'::character varying)
            ;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
        self.conn.commit()
        print("Vue matérialisée créée : lpoaura_afo.vm_reportgenerator_data")


    def get_resum_taxo_group(self):
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                  with   list_esp_lr as (
                        select distinct s.id_synthese from lpoaura_afo.vm_reportgenerator_data s
                        where ( s.lr_aura in ('CR','EN','VU','NT') and s.tx_group2_inpn_v2 = 'Oiseaux' and oiso_status_nidif in ('Certain','Possible','Probable') )
                        OR (( s.lr_aura in ('CR','EN','VU','NT') and s.tx_group2_inpn_v2 != 'Oiseaux')
                        OR ( s.lr_monde in ('CR','EN','VU','NT') and s.tx_group2_inpn_v2 = 'Oiseaux' and oiso_status_nidif in ('Certain','Possible','Probable') and s.lr_aura is null )
                        OR ( s.lr_monde in ('CR','EN','VU','NT') and s.tx_group2_inpn_v2 != 'Oiseaux' and s.lr_aura is null ))
                    )
                    select s.tx_group2_inpn_v2 as group_taxo
                            , count(*) as nb_data_tot
                            , count(distinct(s.cd_ref)) as nb_espece
                            , count(distinct(s.cd_ref)) filter ( where oiso_status_nidif in ('Certain','Possible','Probable') ) as nb_espece_nicheuse
                            , count(distinct(s.cd_ref)) filter ( where s.prot_nat is not null )as nb_espece_protege
                            , count(distinct(s.cd_ref)) filter ( where s.prot_nat is not null and oiso_status_nidif in ('Certain','Possible','Probable')  )as nb_espece_protege_nicheuse
                            , count(distinct(s.cd_ref)) filter ( where s.id_synthese in (select id_synthese from list_esp_lr)  )as nb_espece_lr
                            , count(distinct(s.cd_ref)) filter ( where s.id_synthese in (select id_synthese from list_esp_lr) and oiso_status_nidif in ('Certain','Possible','Probable')  )as nb_espece_lr_nicheuse
                            , count(distinct(s.cd_ref)) filter ( where oiso_status_nidif in ('Certain','Possible','Probable') and s.ordre = 'Accipitriformes'  )as nb_espece_nicheuse_rapaces
                            , count(distinct(s.id_synthese)) filter ( where mortality_cause in ('ROAD_VEHICLE','UNKNOWN_TRANSPORT','OTHER_TRANSPORT') )as nb_data_mortalite
                            , count(distinct(s.cd_ref)) filter ( where mortality_cause in ('ROAD_VEHICLE','UNKNOWN_TRANSPORT','OTHER_TRANSPORT') )as nb_esp_mortalite
                    from lpoaura_afo.vm_reportgenerator_data s
                    group by s.tx_group2_inpn_v2
            """
            )
            return cur.fetchall()
        print("Données résumées par groupe taxonomique récupérées")




    def get_resum_temporal_evolution(self):
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                  with   list_esp_lr as (
                        select distinct s.id_synthese from lpoaura_afo.vm_reportgenerator_data s
                        where ( s.lr_aura in ('CR','EN','VU','NT') and s.tx_group2_inpn_v2 = 'Oiseaux' and oiso_status_nidif in ('Certain','Possible','Probable') )
                        OR (( s.lr_aura in ('CR','EN','VU','NT') and s.tx_group2_inpn_v2 != 'Oiseaux')
                        OR ( s.lr_monde in ('CR','EN','VU','NT') and s.tx_group2_inpn_v2 = 'Oiseaux' and oiso_status_nidif in ('Certain','Possible','Probable') and s.lr_aura is null )
                        OR ( s.lr_monde in ('CR','EN','VU','NT') and s.tx_group2_inpn_v2 != 'Oiseaux' and s.lr_aura is null ))
                    )
                    select extract(year from s.date_max) as annee
                            , count(*) as nb_data_tot
                            , count(distinct(s.cd_ref)) as nb_espece
                            , count(distinct(s.cd_ref)) filter ( where oiso_status_nidif in ('Certain','Possible','Probable') ) as nb_espece_nicheuse
                            , count(distinct(s.cd_ref)) filter ( where s.prot_nat is not null and oiso_status_nidif in ('Certain','Possible','Probable')  )as nb_espece_protege_nicheuse
                            , count(distinct(s.cd_ref)) filter ( where s.id_synthese in (select id_synthese from list_esp_lr)  )as nb_espece_lr
                            , count(distinct(s.cd_ref)) filter ( where s.id_synthese in (select id_synthese from list_esp_lr) and oiso_status_nidif in ('Certain','Possible','Probable')  )as nb_espece_lr_nicheuse
                            , count(distinct(s.id_synthese)) filter ( where mortality_cause in ('ROAD_VEHICLE','UNKNOWN_TRANSPORT','OTHER_TRANSPORT') )as nb_data_mortalite
                            , count(distinct(s.cd_ref)) filter ( where mortality_cause in ('ROAD_VEHICLE','UNKNOWN_TRANSPORT','OTHER_TRANSPORT') )as nb_esp_mortalite
                    from lpoaura_afo.vm_reportgenerator_data s
                    group by extract(year from s.date_max) ;
            """
            )
            return cur.fetchall()
        

    def get_raw_geodata(self):
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT id_synthese, date_max, cd_ref, count_max, oiso_code_nidif, oiso_status_nidif, ST_AsText(the_geom_local) as the_geom_local, comment_description, observers,behaviour,
                       mortality, mortality_cause, ordre, famille, vn_nom_fr, vn_nom_sci, tx_group2_inpn_v2
                FROM lpoaura_afo.vm_reportgenerator_data
                """
            )
            return cur.fetchall()
        print("Données géographiques brutes récupérées")
            