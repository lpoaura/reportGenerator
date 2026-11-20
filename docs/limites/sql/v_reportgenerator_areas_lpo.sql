-- =====================================================================================================================
-- src_gestion.v_reportgenerator_areas_lpo : vue des demandes + état de la génération (pour le projet QGIS)
-- ---------------------------------------------------------------------------------------------------------------------
-- Ajoute EN FIN de vue, en lecture seule, le bilan écrit par src_gestion.update_reportgenerator_bilan :
--   statut_rapport      : En attente / En cours / Fait / Refusé / Échec
--   commentaire_rapport : ref_geo.l_areas.comment (ex. « REFUSÉ le 20/11/2026 11:04 : trop de données, … »)
--   date_bilan          : horodatage du dernier bilan
--   duree_min           : durée de la dernière génération (minutes)
--   nb_donnees          : données de la vue de synthèse (ou comptées, si refus)
-- Les colonnes existantes, leur ordre, le filtre, les droits et les déclencheurs INSTEAD OF (création, modification,
-- suppression par le formulaire) ne changent pas. Les nouvelles colonnes sont ignorées à la saisie (les déclencheurs
-- n'écrivent que les champs d'origine) : à mettre en lecture seule dans le formulaire QGIS.
-- Le générateur et le serveur Docker lisent des colonnes nommées : pas d'impact.
--
-- Statut :
--   - date_reportgenerate vide : « En cours » si le dernier bilan est en_cours, sinon « En attente » (y compris une
--     demande modifiée dans le formulaire : sa date est effacée, l'ancien commentaire reste visible) ;
--   - date remplie : selon le dernier bilan (ok / refuse / erreur) ; sans bilan (demandes générées avant le
--     20/11/2026, avec update_reportgenerator_date) : « Fait ».
--
-- Exécution (propriétaire de la vue) :
--   psql "service=gnlpoaura user=dbadmin" -v ON_ERROR_STOP=1 --single-transaction -f v_reportgenerator_areas_lpo.sql
-- Rejouable (CREATE OR REPLACE VIEW : colonnes ajoutées en fin uniquement).
-- =====================================================================================================================

CREATE OR REPLACE VIEW src_gestion.v_reportgenerator_areas_lpo AS
SELECT id_area,
       geom,
       area_name,
       additional_data ->> 'referee'::text                         AS referee,
       additional_data ->> 'list_analyse'::text                    AS list_analyse,
       (additional_data ->> 'buffer'::text)::integer               AS buffer,
       (additional_data ->> 'report_annual'::text)::boolean        AS report_annual,
       (additional_data ->> 'date_created'::text)::date            AS date_created,
       (additional_data ->> 'date_reportgenerate'::text)::date     AS date_reportgenerate,
       -- nouvelles colonnes (lecture seule) : bilan de la génération
       CASE
           WHEN additional_data ->> 'date_reportgenerate' IS NULL THEN
               CASE WHEN additional_data -> 'reportgenerate' ->> 'statut' = 'en_cours' THEN 'En cours'
                    ELSE 'En attente' END
           ELSE CASE additional_data -> 'reportgenerate' ->> 'statut'
                    WHEN 'refuse' THEN 'Refusé'
                    WHEN 'erreur' THEN 'Échec'
                    ELSE 'Fait' END
       END                                                          AS statut_rapport,
       comment                                                      AS commentaire_rapport,
       (additional_data -> 'reportgenerate' ->> 'horodatage')::timestamptz AS date_bilan,
       round((additional_data -> 'reportgenerate' ->> 'duree_s')::numeric / 60, 1) AS duree_min,
       (additional_data -> 'reportgenerate' ->> 'nb_donnees')::integer AS nb_donnees
FROM ref_geo.l_areas
WHERE id_type = 83;
