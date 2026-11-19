-- =====================================================================================================================
-- src_gestion.update_reportgenerator_bilan : bilan d'une génération de rapport (reportGenerator)
-- ---------------------------------------------------------------------------------------------------------------------
-- Complète src_gestion.update_reportgenerator_date (gardée telle quelle) : en plus de la date, écrit
--   - ref_geo.l_areas.comment : une ligne lisible (OK / REFUSÉ / ÉCHEC / EN COURS, durée, nombre de données, motif) ;
--   - additional_data.reportgenerate : le même bilan en jsonb, pour régler les seuils sur des mesures réelles.
-- La vue src_gestion.v_reportgenerator_areas_lpo n'est pas modifiée.
--
-- Statuts :
--   en_cours : génération lancée ; date_reportgenerate n'est PAS remplie (une demande restée « en_cours » au
--              lancement suivant a été interrompue : elle est alors marquée en erreur) ;
--   ok, refuse, erreur : date_reportgenerate = date du jour, la demande sort de la file (pas de relance horaire).
-- Pour relancer une demande : effacer additional_data->date_reportgenerate (et le commentaire si besoin).
--
-- Exécution (rôle propriétaire de src_gestion, comme update_reportgenerator_date) :
--   psql "service=gnlpoaura user=dbadmin" -v ON_ERROR_STOP=1 --single-transaction -f update_reportgenerator_bilan.sql
-- Rejouable (CREATE OR REPLACE).
-- =====================================================================================================================

CREATE OR REPLACE FUNCTION src_gestion.update_reportgenerator_bilan(
    p_id_area integer,
    p_statut text,
    p_commentaire text,
    p_bilan jsonb DEFAULT '{}'::jsonb
)
    RETURNS void
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = pg_catalog, pg_temp
AS
$function$
DECLARE
    v_bilan jsonb;
    v_count integer;
BEGIN
    IF p_statut IS NULL OR p_statut NOT IN ('en_cours', 'ok', 'refuse', 'erreur') THEN
        RAISE EXCEPTION 'Statut inconnu : % (attendu : en_cours, ok, refuse, erreur)', p_statut;
    END IF;

    v_bilan := COALESCE(p_bilan, '{}'::jsonb)
                   || jsonb_build_object('statut', p_statut, 'horodatage', to_jsonb(now()));

    UPDATE ref_geo.l_areas
    SET comment         = left(p_commentaire, 2000),
        additional_data = CASE
                              WHEN p_statut = 'en_cours' THEN COALESCE(additional_data, '{}'::jsonb)
                              ELSE jsonb_set(COALESCE(additional_data, '{}'::jsonb), '{date_reportgenerate}',
                                             to_jsonb(CURRENT_DATE), true)
                          END || jsonb_build_object('reportgenerate', v_bilan)
    -- uniquement les demandes de rapport (fonction SECURITY DEFINER : pas d'écriture sur les autres zonages)
    WHERE id_area = p_id_area
      AND id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying);

    GET DIAGNOSTICS v_count = ROW_COUNT;
    IF v_count = 0 THEN
        RAISE EXCEPTION 'Demande de rapport introuvable : id_area=%', p_id_area;
    END IF;
END;
$function$;

COMMENT ON FUNCTION src_gestion.update_reportgenerator_bilan(integer, text, text, jsonb) IS
    'reportGenerator : bilan d''une génération (comment lisible + additional_data.reportgenerate), '
    'date_reportgenerate remplie sauf pour le statut en_cours.';

-- Mêmes droits que update_reportgenerator_date (relevés le 19/11/2026 : propriétaire dbadmin, EXECUTE pour PUBLIC
-- et dt). Le droit PUBLIC est celui par défaut d'une fonction : rien à ajouter pour le serveur Docker.
ALTER FUNCTION src_gestion.update_reportgenerator_bilan(integer, text, text, jsonb) OWNER TO dbadmin;
GRANT EXECUTE ON FUNCTION src_gestion.update_reportgenerator_bilan(integer, text, text, jsonb) TO dt;
