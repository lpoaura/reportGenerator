"""
Briques du dossier Natura 2000 (synthèse faune d'un site), cf. dossiers/natura2000/METHODO.md.

Chaque taxon est pris en compte dans le site et jusqu'au rayon de son taxon (1 km par défaut, plus pour les
rapaces, chiroptères, grands prédateurs : [params.rayons_km]). Les tableaux ne sont pas découpés par anneau :
une colonne indique si le taxon est connu dans le site ou seulement à proximité.
"""

from datetime import datetime

from reportgenerator.analysis.cartography.export import export_gpkg
from reportgenerator.analysis.common.figures import insert_figure_list
from reportgenerator.analysis.common.models import AnalysisResult, ImageBlock, TableBlock
from reportgenerator.analysis.common.tables.excel_export import export_species_excel
from reportgenerator.analysis.common.tables.ring_table import insert_grouped_tables, insert_lpo_table
from reportgenerator.analysis.connaissance import indicateurs as ind
from reportgenerator.analysis.eolien import couches_qgis
from reportgenerator.analysis.knowledge_status.dataviz import (create_data_by_group_chart,
                                                               create_species_by_group_chart)
from reportgenerator.analysis.n2000 import tables as t
from reportgenerator.analysis.n2000.queries import N2000Queries
from reportgenerator.core.registry import register_brick

STATUS_FIELDS = ("lr_france", "lr_aura")
ITALIC_FIELDS = ("lb_nom",)


# =========================================================
# OUTILS
# =========================================================


def _queries(ctx) -> N2000Queries:
    return ctx.cached("n2000_queries", lambda: N2000Queries(ctx.queries))


def _rayons(ctx):
    p = ctx.params
    r = p.get("rayons_km", {})
    return float(p.get("rayon_defaut_km", 1)), dict(r.get("ordres", {})), dict(r.get("especes", {}))


def _periode(ctx) -> str:
    annee = datetime.now().year
    return f"{annee - int(ctx.params.get('annees', 10))}-{annee}"


def _complexes(ctx) -> list[dict]:
    return ctx.cached("n2000_complexes", lambda: t.complexes_n2000(
        _queries(ctx).complexes_candidats(), ctx.params.get("n2000_taxons_complexes", ())))


def _cd_complexes(ctx):
    return [c["cd_ref"] for c in _complexes(ctx)]


def _taxons(ctx) -> list[dict]:
    """Taxons retenus, dans le rayon de leur taxon (filtré dans la VM ; requête faite une fois)."""
    def load():
        rows = _queries(ctx).taxons(_cd_complexes(ctx), tuple(ctx.params.get("n2000_taxons_exclus", ())))
        for r in rows:
            r.update({"nom": t.nom_affiche(r), "presence": t.presence(r), "statut": t.statut_biologique(r),
                      "statut_nidif": t.NIDIF_LIBELLES.get(int(r.get("rang_nidif") or 0), "").capitalize(),
                      "statut_chiro": t.statut_chiro(r), "groupe_annexe": t.groupe_annexe(r.get("groupe"))})
        return t.tri(rows)
    return ctx.cached("n2000_taxons", load)


def _table(ctx, name, rows, columns, widths=None):
    """Tableau Word + copie Excel (mêmes colonnes)."""
    block = TableBlock(rows, insert_lpo_table, {"columns": columns, "status_fields": STATUS_FIELDS,
                                                "italic_fields": ITALIC_FIELDS, "widths": widths})
    path = ctx.output_dirs["tables"] / f"{name}.xlsx"
    if rows:
        export_species_excel(data=[{label: r.get(k) for k, label in columns} for r in rows], output_path=path)
    return block, path


# colonnes communes aux listes
NOM = [("nom", "Nom vernaculaire"), ("lb_nom", "Nom scientifique")]
STATUTS = [("prot_nat", "Protection nationale"), ("n2k", "Natura 2000"), ("lr_france", "LR France"),
           ("lr_aura", "LR AuRA")]
COMPTAGES = [("nb_donnees", "Nombre de données"), ("derniere_annee", "Année dernière obs."),
             ("effectif_max", "Nombre d'individus max")]
PRESENCE = [("presence", "Présence")]


# =========================================================
# BRIQUES
# =========================================================


@register_brick(
    "n2000_info",
    provides=["TITRE_RAPPORT", "NOM_SITE", "PERIODE_ETUDE", "SURFACE_HA", "TEXTE_RAYONS"],
)
def n2000_info(ctx):
    """Titre, période, surface du site et phrase des méthodes sur les rayons."""
    defaut, ordres, especes = _rayons(ctx)
    site = _queries(ctx).site()
    noms = _queries(ctx).noms_vernaculaires(list(especes))
    return AnalysisResult(texts={
        "TITRE_RAPPORT": f"Synthèse de données sur la zone Natura 2000 « {ctx.area_name} »",
        "NOM_SITE": ctx.area_name,
        "PERIODE_ETUDE": _periode(ctx),
        "SURFACE_HA": f"{int(site['surface_ha'] or 0):,}".replace(",", " "),
        "TEXTE_RAYONS": t.texte_rayons(defaut, ordres, especes, noms),
    })


@register_brick(
    "n2000_synthese",
    requires=["socle_data"],
    provides=["TEXTE_CHIFFRES_SITE", "NB_ESPECES_N2000", "NB_OISEAUX_NICHEURS_N2000", "TABLE_ESPECES_N2000",
              "LISTE_ESPECES_GRAND_RAYON", "TEXTE_COMPLEXES", "CHART_ESPECES_GROUPES", "CHART_DONNEES_GROUPES"],
)
def n2000_synthese(ctx):
    """Chiffres clés du site (site seul), graphiques par groupe taxonomique (mêmes graphiques que le rapport
    générique) et tableau des taxons Natura 2000 (site + rayon du taxon)."""
    complexes = _complexes(ctx)
    par_groupe = _queries(ctx).chiffres_site(_cd_complexes(ctx), anneau_max=0)
    par_groupe_1km = _queries(ctx).chiffres_site(_cd_complexes(ctx), anneau_max=1)
    n2000 = [r for r in _taxons(ctx) if r["n2000"]]
    defaut_km, _, especes_grand_rayon = _rayons(ctx)
    grand_rayon = [r for r in n2000 if r.get("lb_nom") in especes_grand_rayon and not r.get("nb_donnees_site")]

    columns = [("groupe", "Groupe"), *NOM, *PRESENCE, ("statut", "Statut biologique"),
               ("nb_donnees", "Nombre de données"), ("derniere_annee", "Année dernière obs.")]
    table, path = _table(ctx, "1_especes_n2000", n2000, columns)
    noms_complexes = [t.nom_affiche(c) for c in complexes]

    # graphiques par groupe taxonomique, dans le site (comme la première phrase des chiffres clés)
    dataviz = ctx.output_dirs.get("dataviz", ctx.output_dirs["tables"])
    dataviz.mkdir(parents=True, exist_ok=True)
    groupes = t.groupes_pour_graphique(par_groupe)
    chart_especes, chart_donnees = dataviz / "n2000_especes_par_groupe.png", dataviz / "n2000_donnees_par_groupe.png"
    images = {}
    if groupes:
        create_species_by_group_chart(groupes, str(chart_especes))
        create_data_by_group_chart(groupes, str(chart_donnees))
        images = {"CHART_ESPECES_GROUPES": ImageBlock(chart_especes),
                  "CHART_DONNEES_GROUPES": ImageBlock(chart_donnees)}
    return AnalysisResult(
        data={"par_groupe": par_groupe, "par_groupe_1km": par_groupe_1km, "n2000": n2000, "complexes": complexes},
        files={"especes_n2000": path},
        images=images,
        texts={
            "TEXTE_CHIFFRES_SITE": t.texte_chiffres_site(par_groupe, _periode(ctx), par_groupe_1km,
                                                         min(ctx.queries.anneaux_km)),
            "NB_ESPECES_N2000": sum(1 for r in n2000 if t.est_espece(r)),
            "NB_OISEAUX_NICHEURS_N2000": sum(1 for r in n2000 if r["groupe"] == "Oiseaux" and r.get("rang_nidif")),
            "LISTE_ESPECES_GRAND_RAYON": ", ".join(r["nom"] for r in grand_rayon) or "aucune",
            "TEXTE_COMPLEXES": (
                "Des données non identifiées à l'espèce concernent des taxons Natura 2000 ; elles sont présentées "
                f"comme complexes : {', '.join(noms_complexes)}." if noms_complexes else ""),
        },
        tables={"TABLE_ESPECES_N2000": table},
    )


@register_brick(
    "n2000_chiropteres",
    requires=["socle_data"],
    provides=["NB_CHIRO_N2000", "TABLE_CHIRO_N2000"],
)
def n2000_chiropteres(ctx):
    """Chiroptères Natura 2000 du site et des environs (rayon des chiroptères)."""
    chiro = [r for r in _taxons(ctx) if r["n2000"] and r.get("ordre") == "Chiroptera"]
    columns = [*NOM, ("nb_donnees", "Nb de données"), ("lr_france", "LR France"),
               ("lr_aura", "LR Auvergne-Rhône-Alpes"), ("n2k", "Natura 2000"), ("prot_nat", "Protection nationale"),
               ("effectif_max", "Nb d'individus max"), ("statut_chiro", "Statut"), *PRESENCE]
    table, path = _table(ctx, "2_chiropteres_n2000", chiro, columns)
    return AnalysisResult(
        files={"chiropteres_n2000": path},
        texts={"NB_CHIRO_N2000": sum(1 for r in chiro if t.est_espece(r))},
        tables={"TABLE_CHIRO_N2000": table},
    )


@register_brick("n2000_annexes", requires=["socle_data"], provides=["TABLES_ANNEXES"])
def n2000_annexes(ctx):
    """Annexes : liste de tous les taxons, un tableau par groupe (+ copie Excel de chacun)."""
    taxons = _taxons(ctx)
    groupes = [*t.GROUPES_ANNEXES, t.INVERTEBRES]
    blocs, files = [], {}
    for num, (groupe, libelle) in enumerate((g for g in groupes if any(r["groupe_annexe"] == g[0] for r in taxons)),
                                            start=1):
        rows = [r for r in taxons if r["groupe_annexe"] == groupe]
        if groupe == "Oiseaux":
            columns = [*NOM, *STATUTS, ("nb_donnees", "Nombre de données"), ("derniere_annee", "Année dernière obs."),
                       ("statut_nidif", "Statut nidif."), ("effectif_max", "Nombre d'individus max"), *PRESENCE]
        elif groupe == t.INVERTEBRES[0]:
            columns = [("groupe", "Groupe"), *NOM, *STATUTS, *COMPTAGES, *PRESENCE]
        else:
            columns = [*NOM, *STATUTS, *COMPTAGES, *PRESENCE]
        blocs.append({"titre": f"Annexe {num} : liste des {libelle} recensés sur le site et à proximité",
                      "rows": rows, "columns": columns})
        path = ctx.output_dirs["tables"] / f"annexe_{num}_{libelle}.xlsx"
        export_species_excel(data=[{label: r.get(k) for k, label in columns} for r in rows], output_path=path)
        files[f"annexe_{num}"] = path
    return AnalysisResult(
        files=files,
        tables={"TABLES_ANNEXES": TableBlock(blocs, insert_grouped_tables,
                                             {"status_fields": STATUS_FIELDS, "italic_fields": ITALIC_FIELDS})},
    )


# =========================================================
# CARTES
# =========================================================

# mises en page « atlas » du projet QGIS : une image par entité de couverture (<mise en page>__<cle>.png)
ATLAS_ESPECES = "Atlas_especes_n2000"
ATLAS_CHIRO = "Atlas_chiro_gites"
# (état des connaissances par maille : briques communes, bricks/connaissance.py)


def _export(ctx, rows, name):
    export_gpkg(rows, ctx.output_dirs["data"], layer_name=name, geom_col="geom", crs="EPSG:2154")


# cartes simples cadrées sur un contour (les autres : emprise commune = site + layout_buffers_m)
CARTES_CONTOUR_1KM = ("Carte02_pression_observation",)   # (+ cartes d'effort : brique couches_qgis_connaissance)
CARTES_CHIRO = ("Carte04_chiro_presence_n2000", "Carte05_chiro_gites_colonies", "Carte06_chiro_colonies_especes",
                "Carte07_chiro_gites_n2000")


class _Emprises:
    """Emprises des cartes, toutes calculées à partir du rectangle englobant le site (cf. METHODO, « Emprises ») :
    - espèces (atlas, chiroptères) : contour du rayon de prise en compte du taxon + marge, donc le même cadrage
      pour toutes les espèces d'un même rayon ;
    - cartes par maille : contour 1 km + une marge d'une maille (toutes les mailles entières)."""

    def __init__(self, ctx, bbox):
        p = ctx.params
        defaut, ordres, especes = _rayons(ctx)
        self.rayons = {"defaut": defaut, "ordres": ordres, "especes": especes}
        self.bbox = bbox
        self.ratio = float(p.get("emprise_marge_ratio", 0.1))
        self.minimum_m = float(p.get("emprise_marge_min_km", 0.5)) * 1000
        self.maille_m = float(p.get("emprise_marge_mailles_km", 1)) * 1000

    def taxon(self, rayon_km):
        rayon_m = rayon_km * 1000
        return ind.emprise_contour(self.bbox, rayon_m + ind.marge_m(rayon_m, self.ratio, self.minimum_m))

    def mailles(self):
        return ind.emprise_contour(self.bbox, 1000 + self.maille_m)

    def rayon(self, lb_nom, ordre):
        return t.rayon_taxon_km(self.rayons, lb_nom, ordre)


def _couverture(rows, emprise_de):
    """Entités de couverture d'un atlas : une par ligne (ordre d'affichage), géométrie = rectangle d'emprise."""
    return [{**r, "ordre": i, "geom": ind.rectangle_wkt(emprise_de(r))} for i, r in enumerate(rows, start=1)]


@register_brick("couches_qgis_n2000", requires=["socle_data"])
def couches_qgis_n2000(ctx):
    """Couches GPKG du projet QGIS Natura 2000 et couvertures des atlas des espèces et des gîtes de chiroptères
    (connaissance par maille : brique couches_qgis_connaissance). Le texte « Sources » des cartes est passé au
    projet (variable @sources)."""
    q = _queries(ctx)
    complexes, exclus = _cd_complexes(ctx), tuple(ctx.params.get("n2000_taxons_exclus", ()))
    oiseaux_nn = bool(ctx.params.get("atlas_oiseaux_non_nicheurs", False))

    points = q.points(complexes, exclus)
    gites = q.chiro_gites(complexes, exclus)
    sources = t.texte_sources(q.sources(), ctx.params.get("sources_libelles"))
    emp = _Emprises(ctx, q.enveloppe_zone())

    # atlas des espèces : emprise = contour du rayon du taxon (1, 10 ou 20 km) + marge
    especes = [{"cd_ref": r["cd_ref"], "cle": t.cle(r["nom"]), "nom": r["nom"], "lb_nom": r["lb_nom"],
                "groupe": r["groupe"], "titre_groupe": t.titre_groupe_atlas(r["groupe"], oiseaux_nn),
                "rayon_km": emp.rayon(r["lb_nom"], r["ordre"])}
               for r in t.taxons_atlas(_taxons(ctx), oiseaux_nn)]
    atlas_especes = _couverture(especes, lambda r: emp.taxon(r["rayon_km"]))

    # atlas des gîtes de chiroptères : taxons N2000 ayant au moins un gîte ou une colonie ; même emprise
    chiro = sorted({(g["cd_ref"], g["nom_vern"], g["lb_nom"]) for g in gites if g["n2000"]}, key=lambda c: c[1])
    chiro_rows = [{"cd_ref": c, "cle": t.cle(n), "nom": n, "rayon_km": emp.rayon(lb, "Chiroptera")}
                  for c, n, lb in chiro]
    atlas_chiro = _couverture(chiro_rows, lambda r: emp.taxon(r["rayon_km"]))

    couches = {
        "n2000_limit": q.fetch(couches_qgis.limit_sql(ctx.id_area, ctx.queries.anneaux_km)),
        "n2000_donnees": points,
        "n2000_chiro_donnees": [p for p in points if p["ordre"] == "Chiroptera" and p["n2000"]],
        "n2000_chiro_gites": gites,
        "n2000_atlas_especes": atlas_especes,
        "n2000_atlas_chiro": atlas_chiro,
    }
    for name, rows in couches.items():
        _export(ctx, rows, name)

    # rendu QGIS : variables du projet (texte des sources...) et emprises (site pour la localisation, contours
    # pour les autres cartes simples)
    render = dict(ctx.params.get("qgis_render") or {})
    render["project_variables"] = {**(render.get("project_variables") or {}), "sources": sources}
    render["extent_bbox"] = emp.bbox
    rayon_chiro = emp.taxon(emp.rayon("", "Chiroptera"))
    render["layout_extents"] = {**(render.get("layout_extents") or {}),
                                **{c: emp.mailles() for c in CARTES_CONTOUR_1KM},
                                **{c: rayon_chiro for c in CARTES_CHIRO}}
    ctx.params["qgis_render"] = render
    return AnalysisResult(
        data={"atlas_especes": atlas_especes, "atlas_chiro": atlas_chiro,
              **{f"nb_{k}": len(v) for k, v in couches.items()}},
        texts={"SOURCES_DONNEES": sources},
    )


def _figures(ctx, layout, rows, legende):
    maps = ctx.output_dirs["maps"]
    return [{"path": maps / f"{layout}__{r['cle']}.png", "legende": legende(r)} for r in rows]


@register_brick(
    "n2000_atlas",
    requires=["couches_qgis_n2000", "cartography"],
    provides=["ATLAS_ESPECES_N2000", "ATLAS_CHIRO_GITES"],
    last=True,
)
def n2000_atlas(ctx):
    """Cartes des atlas des espèces et des gîtes insérées dans le Word (après le rendu QGIS) : une figure par page
    d'atlas, regroupées par groupe taxonomique pour l'atlas des espèces."""
    data = ctx.results["couches_qgis_n2000"].data
    blocs = []
    for titre in dict.fromkeys(r["titre_groupe"] for r in data["atlas_especes"]):
        rows = [r for r in data["atlas_especes"] if r["titre_groupe"] == titre]
        figures = _figures(ctx, ATLAS_ESPECES, rows, lambda r: f"Répartition – {r['nom']}")
        blocs.append({"titre": titre, "figures": figures})
    chiro = [{"titre": None, "figures": _figures(ctx, ATLAS_CHIRO, data["atlas_chiro"],
                                                 lambda r: f"Gîtes et colonies connus – {r['nom']}")}]
    return AnalysisResult(tables={
        "ATLAS_ESPECES_N2000": TableBlock(blocs, insert_figure_list),
        "ATLAS_CHIRO_GITES": TableBlock(chiro, insert_figure_list,
                                        {"note": "[Description des gîtes à rédiger]"}),
    })
