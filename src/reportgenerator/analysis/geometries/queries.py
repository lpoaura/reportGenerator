"""Requêtes sur la VM : lignes et polygones retenus (transects, placettes), regroupés par objet."""

from reportgenerator.analysis.common.vm_queries import VM, VmQueries


class GeometriesQueries(VmQueries):

    def objets(self):
        """Une ligne par objet (même géométrie d'origine, même source, même jeu de données) : un transect suivi chaque
        année donne un seul objet. Géométrie en multi (couches GPKG homogènes)."""
        return self._fetch(f"""
            select ST_AsText(ST_Multi(s.geom_origine)) as geom, s.type_geom, s.source,
                   coalesce(nullif(trim(ds.dataset_shortname), ''), ds.dataset_name) as jeu,
                   count(*) as nb_donnees, count(distinct s.cd_ref) as nb_especes,
                   string_agg(distinct s.tx_group2_inpn_v2, ', ' order by s.tx_group2_inpn_v2) as groupes,
                   min(extract(year from s.date_max))::int as premiere_annee,
                   max(extract(year from s.date_max))::int as derniere_annee,
                   count(distinct s.date_max) as nb_dates, max(s.etendue_m) as etendue_m,
                   min(s.anneau_ordre) as anneau_ordre
            from {VM} s
            left join gn_meta.t_datasets ds on ds.id_dataset = s.id_dataset
            where s.type_geom <> 'point'
            group by s.geom_origine, s.type_geom, s.source, ds.dataset_shortname, ds.dataset_name
            order by s.source, jeu
        """)

    def synthese(self):
        """Par source, jeu de données et type de géométrie (tableau du Word), points compris (nb_donnees_points) :
        nombre d'objets, de données, d'espèces, groupes et années."""
        return self._fetch(f"""
            select s.source, coalesce(nullif(trim(ds.dataset_shortname), ''), ds.dataset_name) as jeu, s.type_geom,
                   count(distinct s.geom_origine) as nb_objets, count(*) as nb_donnees,
                   count(distinct s.cd_ref) as nb_especes,
                   string_agg(distinct s.tx_group2_inpn_v2, ', ' order by s.tx_group2_inpn_v2) as groupes,
                   min(extract(year from s.date_max))::int as premiere_annee,
                   max(extract(year from s.date_max))::int as derniere_annee
            from {VM} s
            left join gn_meta.t_datasets ds on ds.id_dataset = s.id_dataset
            where s.type_geom <> 'point'
            group by s.source, ds.dataset_shortname, ds.dataset_name, s.type_geom
        """)

    def enveloppe(self) -> list[float]:
        """Rectangle englobant la zone d'étude et les lignes et polygones retenus [xmin, ymin, xmax, ymax]."""
        r = self._fetch(f"""
            select ST_XMin(b) as xmin, ST_YMin(b) as ymin, ST_XMax(b) as xmax, ST_YMax(b) as ymax
            from (select ST_Extent(g) as b from (
                      select l.geom as g from ref_geo.l_areas l where l.id_area = {self.id_area}
                      union all
                      select s.geom_origine from {VM} s where s.type_geom <> 'point') u) e
        """)[0]
        return [float(r["xmin"]), float(r["ymin"]), float(r["xmax"]), float(r["ymax"])]
