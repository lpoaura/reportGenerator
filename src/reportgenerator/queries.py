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
                selection_grille AS (
                    SELECT
                        ST_Area(geom) / 1000000.0 as air_km2,
                        CASE
                            WHEN  ST_Area(ST_Envelope(geom)) / 1000000.0 < 25 THEN 'M0.2'
                            WHEN  ST_Area(ST_Envelope(geom)) / 1000000.0 < 250 THEN 'M0.5'
                            WHEN  ST_Area(ST_Envelope(geom)) / 1000000.0 < 750 THEN 'M1'
                            WHEN  ST_Area(ST_Envelope(geom)) / 1000000.0 < 4000 THEN 'M2'
                            ELSE 'M5'
                        END AS grille_code
                    FROM zone_etude
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
                                    AND (s.id_nomenclature_valid_status = ANY(ARRAY [
                                ref_nomenclatures.get_id_nomenclature('STATUT_VALID'::character varying,'2'::character varying),
                                ref_nomenclatures.get_id_nomenclature('STATUT_VALID'::character varying, '1'::character varying), 
                                ref_nomenclatures.get_id_nomenclature('STATUT_VALID'::character varying, '0'::character varying)
                                                                ])) IS TRUE
                                    and  ST_Within(s.the_geom_local, (select geom from zone_etude ))
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
            select s.*, la.id_area, la.geom as geom_maille , gs.grille_code, gs.air_km2 from obs_final s
            left join gn_synthese.cor_area_synthese cas on s.id_synthese = cas.id_synthese
            left join ref_geo.l_areas la on cas.id_area = la.id_area
            cross join selection_grille gs
            where la.id_type = ref_geo.get_id_area_type((select grille_code from selection_grille)::character varying)
            and tx_group2_inpn_v2 in ('Amphibiens','Chauves-souris','Mammifères','Odonates','Oiseaux','Papillons de jour','Poissons','Reptiles')
            and (ST_GeometryType(s.the_geom_local) = 'ST_Point')
            ;
            CREATE INDEX idx_id_synthese ON lpoaura_afo.vm_reportgenerator_data (id_synthese);
            CREATE INDEX idx_cd_ref ON lpoaura_afo.vm_reportgenerator_data (cd_ref);
            CREATE INDEX idx_date_max ON lpoaura_afo.vm_reportgenerator_data (date_max);
            CREATE INDEX idx_the_geom_local ON lpoaura_afo.vm_reportgenerator_data USING GIST (the_geom_local);
            CREATE INDEX idx_geom_maille ON lpoaura_afo.vm_reportgenerator_data USING GIST (geom_maille);
            ANALYZE lpoaura_afo.vm_reportgenerator_data;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
        self.conn.commit()

    def get_resum_taxo_group(self):
        """Tableau de synthèse par groupe taxonomique pour le rapport"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"""
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
            """)
            return cur.fetchall()

    def get_resum_data(self):
        """Tableau de synthèse global par zone étude et périmètre pour le rapport.

        Note : buffer_km n'est plus nécessaire ici. vm_reportgenerator_data
        contient déjà uniquement les observations de la zone d'étude + buffer
        (cf. set_global_data), donc "hors zone d'étude" = "dans le buffer",
        sans avoir à reconstruire un donut coûteux.
        """
        id_area = int(self.id_area)
        sql = f"""
            WITH study_area AS (
                SELECT geom
                FROM ref_geo.l_areas
                WHERE id_area = {id_area}
                AND id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY')
            ),
            flagged AS (
                SELECT
                    d.id_synthese,
                    d.cd_ref,
                    d.date_max,
                    ST_Intersects(d.the_geom_local, s.geom) AS in_zone
                FROM lpoaura_afo.vm_reportgenerator_data d
                CROSS JOIN study_area s
            )
            SELECT
                'zone_etude' AS secteur,
                COUNT(DISTINCT id_synthese) FILTER (WHERE in_zone) AS nb_observations,
                COUNT(DISTINCT cd_ref) FILTER (WHERE in_zone) AS nb_especes,
                MAX(date_max) FILTER (WHERE in_zone) AS derniere_observation
            FROM flagged
            UNION ALL
            SELECT
                'buffer_seul',
                COUNT(DISTINCT id_synthese) FILTER (WHERE NOT in_zone),
                COUNT(DISTINCT cd_ref) FILTER (WHERE NOT in_zone),
                MAX(date_max) FILTER (WHERE NOT in_zone)
            FROM flagged
            UNION ALL
            SELECT
                'ensemble',
                COUNT(DISTINCT id_synthese),
                COUNT(DISTINCT cd_ref),
                MAX(date_max)
            FROM flagged
            ;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
        
    def get_resum_temporal_evolution(self):
        """Graphique des évolutions temporelles pour le rapport"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"""
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
                    where extract(year from s.date_max) >= 2000
                    group by extract(year from s.date_max) ;
            """)
            return cur.fetchall()

    def get_raw_geodata(self):
        """Données brutes géographiques pour le volet cartographie du rapport + extraction données"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT id_synthese, date_max, cd_ref, count_max, oiso_code_nidif, oiso_status_nidif, ST_AsText(the_geom_local) as the_geom_local, comment_description, observers,behaviour,
                       mortality, mortality_cause, ordre, famille, vn_nom_fr, vn_nom_sci, tx_group2_inpn_v2
                FROM lpoaura_afo.vm_reportgenerator_data
                """)
            return cur.fetchall()
        print("Données géographiques brutes récupérées")

    def get_species_data(self):
        """Données par espèce pour le volet cartographie du rapport + extraction données"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"""
                  with prep as ( select row_number()over() as id,
                                        s.cd_ref,
                                        REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),'(La)',''),'(Le)',''),'(L'')','') as nom_vern,
                                        case when s.vn_nom_sci = 'Anas clypeata' then 'Spatula clypeata'
                                            when s.vn_nom_sci = 'Egretta alba' then 'Ardea alba'
                                            when s.vn_nom_sci = 'Larus ridibundus' then 'Chroicocephalus ridibundus'
                                            when s.vn_nom_sci = 'Miliaria calandra' then 'Emberiza calandra'
                                            when s.vn_nom_sci = 'Emberiza calandra calandra' then 'Emberiza calandra'
                                            when s.vn_nom_sci = 'Emberiza calandra parroti' then 'Emberiza calandra'
                                            else s.vn_nom_sci end as lb_nom,
                                        s.tx_group2_inpn_v2,
                                        MAX(EXTRACT(YEAR FROM s.date_max)) AS derniere_annee_observation, -- Dernière année d'observation
                                        MIN(EXTRACT(YEAR FROM s.date_max)) AS premiere_annee_observation, -- Première année d'observation
                                        COUNT(DISTINCT EXTRACT(YEAR FROM s.date_max)) AS nb_annees_observation, -- Nombre d'années d'observation distinctes
                                        COUNT(distinct s.id_synthese) AS nb_observations, -- Nombre total d'observations
                                        COUNT(distinct s.observers) AS nb_observateur, -- Nombre total d'observteur
                                        COUNT(distinct s.id_synthese) filter(where s.mortality is true ) AS nb_data_mortalité, -- Nombre total de données ed moratlité
                                        string_agg(distinct s.mortality_cause, ', ') AS liste_cause_mortalité,
                                        max(s.count_max) AS nb_effectif_max, -- Nombre max d'individus
                                        COUNT(distinct s.id_synthese) filter(where s.oiso_status_nidif in ('Possible','Probable','Certain') ) AS nb_data_nidif, -- Nombre total d'observations
                                        lr_auv,
                                        lr_ra,
                                        lr_aura,
                                        lr_france,
                                        case when lr_fr_nich is null and lr_france is not null then lr_france else lr_fr_nich end as lr_fr_nich,
                                        --lr_fr_nich,
                                        lr_fr_hiv,
                                        lr_fr_migr,
                                        lr_euro,
                                        lr_monde,
                                        prot_nat,
                                        n2k,
                                        conv_berne,
                                        conv_bonn,
                                        pna_en_cours,
                                        pna_ex,
                                        case when lr_aura is null and lr_auv is null then lr_ra
                                            when lr_aura is null and lr_ra is null then lr_auv
                                            when lr_aura is null and lr_ra is null and lr_auv is null then lr_france
                                            else lr_aura
                                        end as lr_qgis
                                from  lpoaura_afo.vm_reportgenerator_data s
                                GROUP BY  lr_auv,
                                        lr_ra,
                                        lr_aura,
                                        lr_france,
                                        lr_fr_nich,
                                        lr_fr_hiv,
                                        lr_fr_migr,
                                        lr_euro,
                                        lr_monde,
                                        prot_nat,
                                        n2k,
                                        conv_berne,
                                        conv_bonn,
                                        pna_en_cours,
                                        pna_ex,  s.cd_ref,
                                        REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),'(La)',''),'(Le)',''),'(L'')',''),
                                        case when s.vn_nom_sci = 'Anas clypeata' then 'Spatula clypeata'
                                            when s.vn_nom_sci = 'Egretta alba' then 'Ardea alba'
                                            when s.vn_nom_sci = 'Larus ridibundus' then 'Chroicocephalus ridibundus'
                                            when s.vn_nom_sci = 'Miliaria calandra' then 'Emberiza calandra'
                                            when s.vn_nom_sci = 'Emberiza calandra calandra' then 'Emberiza calandra'
                                            when s.vn_nom_sci = 'Emberiza calandra parroti' then 'Emberiza calandra'
                                            else s.vn_nom_sci end ,
                                        s.tx_group2_inpn_v2
                                    )
                                select *,
                                    case when lr_qgis ='EX' then '#000000'
                                        when lr_qgis ='EW' then '#3d1851'
                                        when lr_qgis ='RE' then '#5b1a62'
                                        when lr_qgis ='CR' then '#d20019'
                                        when lr_qgis ='EN' then '#fabf00'
                                        when lr_qgis ='VU' then '#ffed00'
                                        when lr_qgis ='NT' then '#faf2c7'
                                        when lr_qgis ='LC' then '#78b747'
                                        when lr_qgis ='DD' then '#d4d4d4'
                                    else '#ffffff'
                                    end as lr_qgis_color
                                from prep
                                order by nom_vern
            """)
            return cur.fetchall()

    def get_atlas_species_grid(self):
        """Tableau de synthèse par espèce, pour calcule des grilles de l'atlas, analyses de la phénologie, nidification, année d'observation"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """ with prep as (select row_number() over ()                                                                            as id,
                                        s.cd_ref,
                                        s.vn_nom_sci as lb_nom,
                                        s.tx_group2_inpn_v2 as group_taxo,
                                        REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),'(La)',''),'(Le)',''),'(L'')','') as nom_vern,
                                        COUNT(distinct s.id_synthese) as nb_observations,
                                        MAX(s.count_max) as nb_effectif_max,
                                        COUNT(distinct s.id_synthese) filter (where tn."hierarchy"::numeric >= 30) as nb_data_nidif, 
                                        COUNT(distinct EXTRACT(year FROM s.date_max)) as nb_annee,
                                        count(distinct s.geom_maille) as nb_maille,
                                        st_union(s.geom_maille) as emprise_presence,
                                        case when MAX(tn."hierarchy"::numeric) = 0 then 'Espèce absente'
                                            when MAX(tn."hierarchy"::numeric) < 30 then 'Absence de code'
                                            when MAX(tn."hierarchy"::numeric) < 40 then 'Possible'
                                            when MAX(tn."hierarchy"::numeric) < 50 then 'Probable'
                                            when MAX(tn."hierarchy"::numeric) >= 50 then 'Certain'
                                            else 'Absence de code'
                                        end AS code_repro_max,
                                        case when lr_aura is null then lr_france
                                             else lr_aura
                                        end as lr_qgis,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 1 ) AS data_janvier,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 2 ) AS data_fev,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 3 ) AS data_mars,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 4 ) AS data_avril,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 5 ) AS data_mais,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 6 ) AS data_juin,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 7 ) AS data_juillet,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 8 ) AS data_aout,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 9 ) AS data_sept,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 10 ) AS data_octo,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 11 ) AS data_nov,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(MONTH FROM s.date_max) = 12 ) AS data_decembre,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2009 ) AS _09,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2010 ) AS _10,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2011 ) AS _11,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2012 ) AS _12,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2013 ) AS _13,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2014 ) AS _14,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2015 ) AS _15,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2016 ) AS _16,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2017 ) AS _17,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2018 ) AS _18,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2019 ) AS _19,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2020 ) AS _20,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2021 ) AS _21,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2022 ) AS _22,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2023 ) AS _23,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2024 ) AS _24,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2025 ) AS _25,
                                        COUNT(distinct s.id_synthese) filter (where EXTRACT(year FROM s.date_max) = 2026 ) AS _26
                                from lpoaura_afo.vm_reportgenerator_data s
                                left join ref_nomenclatures.t_nomenclatures tn ON tn.cd_nomenclature = s.oiso_code_nidif::text AND tn.id_type = 118 -- a verif
                                -- On ne prend que les espèces avec des codes de nidification possibles, probables ou certains ou les espèces protégées pour la génération de l'atlas
                                GROUP BY s.cd_ref, s.vn_nom_sci,lr_aura, lr_france, s.tx_group2_inpn_v2,REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),'(La)',''),'(Le)',''),'(L'')','') )
                    select id, cd_ref,lb_nom,nom_vern,code_repro_max,nb_annee,nb_observations,group_taxo,nb_effectif_max, nb_data_nidif,nb_maille,lr_qgis,emprise_presence,
                          case  when lr_qgis ='EX' then '#000000'
                                when lr_qgis ='EW' then '#3d1851'
                                when lr_qgis ='RE' then '#5b1a62'
                                when lr_qgis ='CR' then '#d20019'
                                when lr_qgis ='EN' then '#fabf00'
                                when lr_qgis ='VU' then '#ffed00'
                                when lr_qgis ='NT' then '#faf2c7'
                                when lr_qgis ='LC' then '#78b747'
                                when lr_qgis ='DD' then '#d4d4d4'
                            else '#ffffff'
                            end as lr_qgis_color,
                        case when data_janvier>0 then '✔' else '-' end as janvier,
                        case when data_fev>0 then '✔' else '-' end as fevrier,
                        case when data_mars>0 then '✔' else '-' end as mars,
                        case when data_avril>0 then '✔' else '-' end as avril,
                        case when data_mais>0 then '✔' else '-' end as mai,
                        case when data_juin>0 then '✔' else '-' end as juin,
                        case when data_juillet>0 then '✔' else '-' end as juillet,
                        case when data_aout>0 then '✔' else '-' end as aout,
                        case when data_sept>0 then '✔' else '-' end as septembre,
                        case when data_octo>0 then '✔' else '-' end as octobre,
                        case when data_nov>0 then '✔' else '-' end as novembre,
                            case when data_decembre>0 then '✔' else '-' end as decembre,
                            case when _09>0 then '✔' else '-' end as _09,
                            case when _10>0 then '✔' else '-' end as _10,
                            case when _11>0 then '✔' else '-' end as _11,
                            case when _12>0 then '✔' else '-' end as _12,
                            case when _13>0 then '✔' else '-' end as _13,
                            case when _14>0 then '✔' else '-' end as _14,
                            case when _15>0 then '✔' else '-' end as _15,
                        case when _16>0 then '✔' else '-' end as _16,
                        case when _17>0 then '✔' else '-' end as _17,
                        case when _18>0 then '✔' else '-' end as _18,
                        case when _19>0 then '✔' else '-' end as _19,
                        case when _20>0 then '✔' else '-' end as _20,
                        case when _21>0 then '✔' else '-' end as _21,
                        case when _22>0 then '✔' else '-' end as _22,
                        case when _23>0 then '✔' else '-' end as _23,
                        case when _24>0 then '✔' else '-' end as _24,
                        case when _25>0 then '✔' else '-' end as _25,
                        case when _26>0 then '✔' else '-' end as _26
                        from prep
                         WHERE ( code_repro_max in ( 'Possible', 'Probable', 'Certain') OR lr_qgis in ('CR','EN','VU','NT') ) ;
                        """
            )
            return cur.fetchall()

    def get_atlas_species_summary(self):
        """Synthèse des données espèces à la maille pour l'atlas"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(""" select row_number() over () as id,
                                    s.geom_maille,
                                    s.cd_ref,
                                    s.vn_nom_sci as lb_nom,
                                    s.tx_group2_inpn_v2 as group_taxo,
                                    REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),'(La)',''),'(Le)',''),'(L'')','') as nom_vern,
                                    COUNT(distinct s.id_synthese) as nb_observations,
                                    MAX(s.count_max) as nb_effectif_max,
                                    COUNT(distinct s.id_synthese) filter (where tn."hierarchy"::numeric >= 30) as nb_data_nidif,
                                    COUNT(distinct EXTRACT(year FROM s.date_max)) as nb_annee,
                                    MAX(EXTRACT(year FROM s.date_max)) as last_annee,
                                    case when MAX(tn."hierarchy"::numeric) = 0 then 'Espèce absente'
                                        when MAX(tn."hierarchy"::numeric) < 30 then 'Absence de code'
                                        when MAX(tn."hierarchy"::numeric) < 40 then 'Possible'
                                        when MAX(tn."hierarchy"::numeric) < 50 then 'Probable'
                                        when MAX(tn."hierarchy"::numeric) >= 50 then 'Certain'
                                        else 'Absence de code'
                                    end AS code_repro_max
                                from lpoaura_afo.vm_reportgenerator_data s
                                left join ref_nomenclatures.t_nomenclatures tn ON tn.cd_nomenclature = s.oiso_code_nidif::text AND tn.id_type = 118 -- a verif                            
                                GROUP BY s.cd_ref,group_taxo,s.vn_nom_sci,s.geom_maille,REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),'(La)',''),'(Le)',''),'(L'')','');
                                """)
            return cur.fetchall()

    def get_area_zone(self):
        """Récupération de la zone d'étude et du buffer pour le rapport"""
        buffer_km = int(self.buffer)
        id_area = int(self.id_area)
        sql = f"""
                select ST_Buffer(l.geom, 50 * 1000) as geom, 'Alentour de la zone d''étude' as secteur
                from ref_geo.l_areas l
                where l.id_area = {id_area}
                and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)  
                union 
                select ST_Buffer(l.geom, {buffer_km} * 1000) as geom, 'Périmètres d''étude' as secteur
                from ref_geo.l_areas l
                where l.id_area = {id_area}
                and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)  
                union 
                select l.geom as geom, 'Zone d''étude' as secteur
                from ref_geo.l_areas l
                where l.id_area = {id_area}
                and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)  ;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def update_date_reportgenerator(self):
        print(f"Update date_reportgenerator pour id_area={self.id_area}")
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT src_gestion.update_reportgenerator_date(%s)
                """,
                (self.id_area,),
            )
        self.conn.commit()
        print("Update terminé")

    def delete_reportgenerator_view(self):
        """Suppression de la vue matérialisée pour le rapport"""
        sql = f"""
            drop materialized view if exists lpoaura_afo.vm_reportgenerator_data CASCADE;
            ;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
        self.conn.commit()

    def get_knowledge_status_grid(self):
        """Tableau de synthèse par maille pour l'état des connaissances : nombre d'observations, nombre d'espèces, nombre d'espèces nicheuses, liste des espèces nicheuses, nombre d'années d'observation, nombre de jours d'observation, code de nidification max"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""   select row_number() over () as id,
                                    s.geom_maille,
                                    COUNT(distinct s.id_synthese) as nb_observations,
                                    COUNT(distinct s.tx_group2_inpn_v2) as nb_group_taxo,
                                    string_agg(distinct s.tx_group2_inpn_v2, ', ') as list_group_taxo,
                                    COUNT(distinct s.id_synthese) filter (where tn."hierarchy"::numeric >= 30) as nb_observation_nidif,
                                    COUNT(distinct s.cd_ref) as nb_especes,
                                    string_agg(distinct s.vn_nom_sci, ', ') as list_esp_nom_sci,
                                    string_agg(distinct s.vn_nom_fr, ', ') as list_esp_nom_fr,
                                    COUNT(distinct s.cd_ref) filter (where tn."hierarchy"::numeric >= 30) as nb_especes_nidif,
                                    string_agg(distinct s.vn_nom_sci, ', ') filter (where tn."hierarchy"::numeric >= 30) as list_esp_nidif_nom_sci,
                                    string_agg(distinct s.vn_nom_fr, ', ') filter (where tn."hierarchy"::numeric >= 30) as list_esp_nidif_nom_fr,
                                    COUNT(distinct EXTRACT(year FROM s.date_max)) as nb_annee,
                                    COUNT(distinct EXTRACT(year FROM s.date_max)) filter (where tn."hierarchy"::numeric >= 30) as nb_annee_nidifi,
                                    COUNT(distinct s.date_max::date) as nb_jour_observations,
                                    count(distinct(s.cd_ref)) filter ( where mcs.prot_nat is not null and tn."hierarchy"::numeric >= 30 )as nb_espece_protege_nicheuse,
                                    count(distinct(s.cd_ref)) filter ( where mcs.prot_nat is not null ) as nb_espece_protege,
                                    count(distinct(s.cd_ref)) filter ( where  mcs.lr_france in ('CR','EN','VU','NT') or  mcs.lr_aura in ('CR','EN','VU','NT')) as nb_espece_lr,
                                    count(distinct(s.cd_ref)) filter ( where  (mcs.lr_france in ('CR','EN','VU','NT') or  mcs.lr_aura in ('CR','EN','VU','NT')) and tn."hierarchy"::numeric >= 30 ) as nb_espece_lr_nicheuse,
                                    case when MAX(tn."hierarchy"::numeric) = 0 then 'Espèce absente'
                                    when MAX(tn."hierarchy"::numeric) < 30 then 'Absence de code'
                                    when MAX(tn."hierarchy"::numeric) < 40 then 'Possible'
                                    when MAX(tn."hierarchy"::numeric) < 50 then 'Probable'
                                    when MAX(tn."hierarchy"::numeric) >= 50 then 'Certain'
                                    else 'Absence de code'
                                    end AS code_repro_max
                            from lpoaura_afo.vm_reportgenerator_data s
                            left join ref_nomenclatures.t_nomenclatures tn ON tn.cd_nomenclature = s.oiso_code_nidif::text AND tn.id_type = 118 -- a verif
                            left join taxonomie.taxref t ON t.cd_ref = s.cd_ref
                            left join taxonomie.mv_c_statut mcs on mcs.cd_ref = t.cd_ref
                            GROUP BY s.geom_maille;
                                """)
            return cur.fetchall()

    def get_knowledge_protected_area(self):
        """Récupération des différents zonages de protections"""
        buffer_km = int(self.buffer)
        id_area = int(self.id_area)
        sql = f"""with geom_fusion as ( select ST_Buffer(l.geom, {buffer_km} * 10000) as geom_10km -- 10 km pour une emprise plus large des zones de protection
                                        from ref_geo.l_areas l
                                        where l.id_area = {id_area}
                                        and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying) ),
                    pnr  as (  select bat.type_code, la2.geom as geom
                                from geom_fusion, ref_geo.l_areas la2
                                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                                where st_intersects(la2.geom, geom_fusion.geom_10km)
                                and bat.type_code in ('PNR') ),
                    apb  as (  select bat.type_code, la2.geom as geom
                                from geom_fusion, ref_geo.l_areas la2
                                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                                where st_intersects(la2.geom, geom_fusion.geom_10km)
                                and bat.type_code in ('APB') ),
                    znieff  as (  select bat.type_code, la2.geom as geom
                                from geom_fusion, ref_geo.l_areas la2
                                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                                where st_intersects(la2.geom, geom_fusion.geom_10km)
                                and bat.type_code in ('ZNIEFF1') ),
                    znieff2  as (  select bat.type_code, la2.geom as geom
                                from geom_fusion, ref_geo.l_areas la2
                                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                                where st_intersects(la2.geom, geom_fusion.geom_10km)
                                and bat.type_code in ('ZNIEFF2') ),
                    rnr  as (  select bat.type_code, la2.geom as geom
                                from geom_fusion, ref_geo.l_areas la2
                                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                                where st_intersects(la2.geom, geom_fusion.geom_10km)
                                and bat.type_code in ('RNR') ),
                    rnn  as (  select bat.type_code, la2.geom as geom
                                from geom_fusion, ref_geo.l_areas la2
                                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                                where st_intersects(la2.geom, geom_fusion.geom_10km)
                                and bat.type_code in ('RNN') ),
                    natura as ( select 'Natura 2000' as type_code, ST_Union(la2.geom) as geom
                                from geom_fusion, ref_geo.l_areas la2
                                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                                where st_intersects(la2.geom, geom_fusion.geom_10km)
                                and bat.type_code in ('ZSC','ZPS','SIC')),
                    /*pn as ( select 'Parc National' as type_code, ST_Union(la2.geom) as geom
                                from geom_fusion, ref_geo.l_areas la2
                                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                                where st_intersects(la2.geom, geom_fusion.geom_10km)
                                and bat.type_code in ('ZC')),*/
                    all_zone as (/*select * from pn
                                union*/
                                select * from pnr
                                union
                                select * from znieff
                                union
                                select * from znieff2
                                union
                                select * from rnn
                                union
                                select * from apb
                                union
                                select * from rnr
                                union
                                select * from natura)
                select ROW_NUMBER() OVER () as id, * from all_zone;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def get_zonage_surfaces(self):
        """Surfaces (km²) par type de zonage environnemental, réparties par anneau
        (zone d'étude / buffer / 10km fixes au-delà du buffer), sans chevauchement."""
        buffer_km = int(self.buffer)
        id_area = int(self.id_area)
        sql = f"""
            with zone_etude as (
                select l.geom as geom
                from ref_geo.l_areas l
                where l.id_area = {id_area}
                and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)
            ),
            emprise_totale as (
                select ST_Buffer(z.geom, ({buffer_km} * 1000) + 10000) as geom
                from zone_etude z
            ),
            zone_buffer as (
                select ST_Difference(
                    ST_Buffer(z.geom, {buffer_km} * 1000),
                    z.geom
                ) as geom
                from zone_etude z
            ),
            zone_10km as (
                select ST_Difference(
                    e.geom,
                    ST_Buffer(z.geom, {buffer_km} * 1000)
                ) as geom
                from zone_etude z
                cross join emprise_totale e
            ),
            zones as (
                select 'zone_etude' as zone_name, 1 as zone_order, geom from zone_etude
                union all
                select 'buffer', 2, geom from zone_buffer
                union all
                select '10km', 3, geom from zone_10km
            ),
            zonages_clip as (
                select
                    bat.type_code,
                    ST_Subdivide(ST_Intersection(la2.geom, e.geom), 128) as geom
                from ref_geo.l_areas la2
                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                cross join emprise_totale e
                where bat.type_code in ('PNR','APB','ZNIEFF1','ZNIEFF2','RNR','RNN')
                and st_intersects(la2.geom, e.geom)

                union all

                select
                    'Natura 2000' as type_code,
                    ST_Subdivide(ST_Intersection(la2.geom, e.geom), 128) as geom
                from ref_geo.l_areas la2
                inner join ref_geo.bib_areas_types bat on la2.id_type = bat.id_type
                cross join emprise_totale e
                where bat.type_code in ('ZSC','ZPS','SIC')
                and st_intersects(la2.geom, e.geom)
            ),
            zonages_union as (
                select type_code, ST_Union(geom) as geom
                from zonages_clip
                group by type_code
            )
            select
                zu.type_code,
                z.zone_name,
                z.zone_order,
                round((ST_Area(ST_Intersection(zu.geom, z.geom)) / 1000000.0)::numeric, 2) as surface_km2
            from zonages_union zu
            cross join zones z
            where ST_Intersects(zu.geom, z.geom)
            order by zu.type_code, z.zone_order;
        """
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(sql)
            return cur.fetchall()

    def get_number_esp_per_taxonomy(self):
         """Tableau du nombre d'espèces par groupe taxonomique, pour le graphique de l'état des connaissances"""
         with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""  select * from src_gestion.vm_reportgenerator_refere_taxo;
                                """)
            return cur.fetchall()

    def get_species_disparition(self, seuil_disparition=10, seuil_regression=5):
        """Espèces disparues ou en régression : première/dernière année d'observation"""
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(f"""
                with prep as (
                    select
                        s.cd_ref,
                        REPLACE(REPLACE(REPLACE(split_part(s.vn_nom_fr, ', ', 1),'(La)',''),'(Le)',''),'(L'')','') as nom_vern,
                        s.vn_nom_sci as lb_nom,
                        s.tx_group2_inpn_v2 as group_taxo,
                        MIN(EXTRACT(YEAR FROM s.date_max)) as premiere_annee,
                        MAX(EXTRACT(YEAR FROM s.date_max)) as derniere_annee,
                        COUNT(DISTINCT EXTRACT(YEAR FROM s.date_max)) as nb_annees_observation,
                        COUNT(DISTINCT s.id_synthese) as nb_observations,
                        case when s.lr_aura is null then s.lr_france else s.lr_aura end as lr_qgis,
                        bool_or(s.prot_nat is not null) as protegee
                    from lpoaura_afo.vm_reportgenerator_data s
                    group by s.cd_ref, s.vn_nom_fr, s.vn_nom_sci, s.tx_group2_inpn_v2, s.lr_aura, s.lr_france
                )
                select *,
                    (extract(year from now()) - derniere_annee) as anciennete,
                    case
                        when (extract(year from now()) - derniere_annee) >= {seuil_disparition} then 'Disparue'
                        when (extract(year from now()) - derniere_annee) >= {seuil_regression} then 'En régression'
                        else 'Présente'
                    end as statut_disparition
                from prep
                where nb_annees_observation >= 2
                and (extract(year from now()) - derniere_annee) >= {seuil_regression}
                order by derniere_annee asc, protegee desc
            """)
            return cur.fetchall()