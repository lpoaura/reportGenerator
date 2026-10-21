"""Requêtes du dossier Natura 2000 (toutes sur la VM principale, cf. selections.py)."""

from reportgenerator.analysis.common.vm_queries import VM
from reportgenerator.analysis.connaissance.queries import ConnaissanceQueries
from reportgenerator.analysis.eolien.queries import NOM_VERN
from reportgenerator.analysis.n2000 import selections as sel


class N2000Queries(ConnaissanceQueries):
    """(hérite des requêtes de l'état des connaissances : mailles, pool local, enveloppe de la zone)"""

    def site(self):
        """Surface (ha) et nombre de polygones de la zone d'étude."""
        sql = f"""
            select round((ST_Area(l.geom) / 10000)::numeric) as surface_ha, ST_NumGeometries(l.geom) as nb_polygones
            from ref_geo.l_areas l
            where l.id_area = {self.id_area}
            and l.id_type = ref_geo.get_id_area_type('LPO_REPORT_STUDY'::character varying)
        """
        rows = self._fetch(sql)
        return rows[0] if rows else {"surface_ha": None, "nb_polygones": None}

    def complexes_candidats(self):
        """Genres et complexes présents, avec le nombre de leurs espèces (dans mv_c_statut) et combien
        sont Natura 2000. Les complexes « A / B » ne sont pas rattachés à leurs espèces dans TAXREF
        (leur parent est le genre) : pour eux, n_especes = 0 et seule la liste manuelle s'applique."""
        sql = f"""
            with nes as (select distinct s.cd_ref, s.id_rang, s.taxref_lb_nom as lb_nom,
                                max(s.vn_nom_fr) over (partition by s.cd_ref) as nom_vern,
                                s.tx_group2_inpn_v2
                         from {VM} s where not {sel.ESPECE})
            select n.cd_ref, n.id_rang, n.lb_nom, n.nom_vern, n.tx_group2_inpn_v2,
                   count(t.cd_nom) as n_especes,
                   count(t.cd_nom) filter (
                       where (n.tx_group2_inpn_v2 = 'Oiseaux' and mcs.n2k ~ '{sel.N2K_ANNEXE_I_RE}')
                          or (n.tx_group2_inpn_v2 <> 'Oiseaux' and mcs.n2k ~ '{sel.N2K_ANNEXE_II_RE}')
                   ) as n_especes_n2000
            from nes n
            left join taxonomie.taxref t on t.cd_sup = n.cd_ref and t.id_rang = 'ES' and t.cd_nom = t.cd_ref
            left join (select distinct on (cd_ref) cd_ref, n2k from taxonomie.mv_c_statut order by cd_ref) mcs
                   on mcs.cd_ref = t.cd_ref
            where t.cd_nom is null or mcs.cd_ref is not null   -- espèces de la faune de France seulement
            group by 1, 2, 3, 4, 5
        """
        return self._fetch(sql)

    def taxons(self, complexes=(), exclus=()):
        """Une ligne par taxon retenu (la VM ne contient que les données dans le rayon de leur taxon) :
        effectifs, statuts, phénologie."""
        sql = f"""
            select s.cd_ref, max(s.id_rang) as id_rang,
                   max({NOM_VERN}) as nom_vern, max(s.vn_nom_sci) as lb_nom,
                   max(s.tx_group2_inpn_v2) as groupe, max(s.ordre) as ordre, max(s.famille) as famille,
                   max(s.n2k) as n2k, max(s.prot_nat) as prot_nat,
                   max(coalesce(s.lr_fr_nich, s.lr_france)) as lr_france, max(s.lr_aura) as lr_aura,
                   bool_or({sel.n2000_sql(complexes, exclus)}) as n2000,
                   count(*) as nb_donnees,
                   count(*) filter (where s.anneau_ordre = 0) as nb_donnees_site,
                   max(extract(year from s.date_max))::int as derniere_annee,
                   max(s.count_max) as effectif_max,
                   max({sel.STATUT_NIDIF_RANG}) as rang_nidif,
                   bool_or({sel.HIVERNANT}) as hivernant,
                   bool_or({sel.MIGRATION}) as migrateur,
                   bool_or({sel.CHIRO_COLONIE}) as colonie,
                   bool_or({sel.CHIRO_GITE}) as gite
            from {VM} s
            where {sel.retenu_sql(complexes)}
            group by s.cd_ref
        """
        return self._fetch(sql)  # sans paramètre : les % des motifs ilike restent littéraux

    def chiffres_site(self, complexes=(), anneau_max=0):
        """Par groupe : nombre de données (taxons retenus) et d'espèces, dans le site (anneau_max = 0)
        ou dans le site et le premier anneau (anneau_max = 1, le kilomètre autour)."""
        sql = f"""
            select s.tx_group2_inpn_v2 as groupe, count(*) as nb_donnees,
                   count(distinct s.cd_ref) filter (where {sel.ESPECE}) as nb_especes
            from {VM} s
            where {sel.both(sel.retenu_sql(complexes), f"s.anneau_ordre <= {int(anneau_max)}")}
            group by 1
        """
        return self._fetch(sql)

    # =========================================================
    # COUCHES DES CARTES
    # =========================================================

    def points(self, complexes=(), exclus=()):
        """Couche n2000_donnees : toutes les données retenues (pression d'observation, atlas par espèce)."""
        sql = f"""
            select s.id_synthese as id, s.cd_ref, {NOM_VERN} as nom_vern, s.vn_nom_sci as lb_nom, s.id_rang,
                   s.tx_group2_inpn_v2 as groupe, s.ordre, s.famille,
                   ({sel.n2000_sql(complexes, exclus)}) as n2000,
                   {sel.TYPE_DONNEE} as type_donnee,
                   s.date_max as date, extract(year from s.date_max)::int as annee, s.count_max,
                   s.source, s.precision_geo, coalesce(s.donnee_cachee, false) as donnee_cachee,
                   (s.anneau_ordre = 0) as dans_site, s.anneau_ordre, ST_AsText(s.the_geom_local) as geom
            from {VM} s
            where {sel.retenu_sql(complexes)}
        """
        return self._fetch(sql)

    def chiro_gites(self, complexes=(), exclus=()):
        """Couche n2000_chiro_gites : un point par lieu, taxon et type de gîte (toutes espèces de chiroptères),
        effectif maximal, taxon Natura 2000 ou non."""
        sql = f"""
            select {NOM_VERN} as nom_vern, max(s.vn_nom_sci) as lb_nom, s.cd_ref, max(s.id_rang) as id_rang,
                   bool_or({sel.n2000_sql(complexes, exclus)}) as n2000,
                   case when bool_or({sel.CHIRO_COLONIE}) then 'Colonie de reproduction'
                        else 'Gîte sans reproduction' end as type_gite,
                   bool_or({sel.CHIRO_COLONIE}) as reproduction,
                   max(s.count_max) as effectif_max, count(*) as nb_donnees,
                   min(extract(year from s.date_max))::int as premiere_annee,
                   max(extract(year from s.date_max))::int as derniere_annee,
                   bool_or(s.anneau_ordre = 0) as dans_site,
                   ST_AsText(s.the_geom_local) as geom
            from {VM} s
            where {sel.both("s.ordre = 'Chiroptera'", sel.CHIRO_GITE, sel.retenu_sql(complexes))}
            group by {NOM_VERN}, s.cd_ref, s.the_geom_local, {sel.CHIRO_COLONIE}
        """
        return self._fetch(sql)

    def sources(self):
        """Nombre de données par source (texte « Sources » des cartes et du rapport)."""
        return self._fetch(f"select s.source, count(*) as n from {VM} s group by 1 order by 2 desc")

    def noms_vernaculaires(self, lb_noms):
        """Nom vernaculaire des espèces (pour le texte des rayons), par nom scientifique."""
        if not lb_noms:
            return {}
        sql = """select distinct on (vn_nom_sci) vn_nom_sci, split_part(vn_nom_fr, ', ', 1) as nom
                 from taxonomie.mv_c_statut where vn_nom_sci = any(%s) order by vn_nom_sci"""
        return {r["vn_nom_sci"]: r["nom"] for r in self._fetch(sql, (list(lb_noms),))}
