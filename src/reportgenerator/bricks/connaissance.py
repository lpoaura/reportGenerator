"""
Briques communes de l'état des connaissances par maille (dossiers Natura 2000, générique, éolien).

    connaissance               indicateurs par maille et par groupe, tableau par groupe, textes du Word
    couches_qgis_connaissance  couches connaissance_* du projet QGIS, emprise des cartes d'effort
    connaissance_atlas         deux cartes par groupe cartographié (après le rendu QGIS)

Méthode et lecture des cartes : dossiers/natura2000/METHODO.md (§3.1.1). Paramètres (dossier.toml), tous
facultatifs : connaissance_rayon_km (emprise des mailles autour de la zone ; défaut : plus grand anneau de la VM),
pool_local_km, connaissance_groupes (+ connaissance_groupes_analyse), grille_connaissance, seuils
(connaissance_seuil_donnees, connaissance_min_especes_site, connaissance_alerte_jours_median),
enjeux_oiseaux_nicheurs_seulement, emprise_marge_mailles_km, vocabulaire du Word (connaissance_zone,
connaissance_zone_court, connaissance_renvoi), connaissance_niveau_titre, connaissance_excel.
"""

from reportgenerator.analysis.cartography.export import export_gpkg
from reportgenerator.analysis.common.figures import insert_figure_list
from reportgenerator.analysis.common.models import AnalysisResult, TableBlock
from reportgenerator.analysis.common.tables.excel_export import export_species_excel
from reportgenerator.analysis.common.tables.ring_table import insert_lpo_table
from reportgenerator.analysis.connaissance import indicateurs as ind
from reportgenerator.analysis.connaissance.queries import ConnaissanceQueries
from reportgenerator.analysis.connaissance.selections import enjeu_sql
from reportgenerator.core.registry import register_brick

# mises en page du projet QGIS (même nom dans tous les dossiers)
EFFORT_DONNEES = "Connaissance_effort_donnees"
EFFORT_JOURS = "Connaissance_effort_jours"
ATLAS_GROUPES = "Atlas_connaissance_groupes"
ATLAS_CROISEE = "Atlas_connaissance_croisee"


def _queries(ctx) -> ConnaissanceQueries:
    return ctx.cached("connaissance_queries", lambda: ConnaissanceQueries(ctx.queries))


def _rayon_km(ctx) -> float:
    """Emprise des mailles autour de la zone : paramètre, sinon le plus grand anneau de la VM (générique : buffer)."""
    r = ctx.params.get("connaissance_rayon_km")
    return float(r if r is not None else max(ctx.queries.anneaux_km or [0]))


def _groupes(ctx) -> tuple:
    """Groupes analysés (vide = tous ceux de la VM) ; un groupe lié à une analyse optionnelle (ex. chiroptères de
    l'éolien) n'est gardé que si elle est activée."""
    p = ctx.params
    liees = p.get("connaissance_groupes_analyse") or {}
    return tuple(g for g in (p.get("connaissance_groupes") or ()) if g not in liees or ctx.is_enabled(liees[g]))


def _libelles(ctx):
    p = ctx.params
    return (p.get("connaissance_zone", "la zone d'étude"), p.get("connaissance_zone_court", "zone"),
            p.get("connaissance_renvoi", "les tableaux d'espèces du rapport"))


@register_brick(
    "connaissance",
    requires=["socle_data"],
    provides=["TABLE_CONNAISSANCE_GROUPES", "POOL_LOCAL_KM", "SEUIL_PEU_DONNEES", "TEXTE_GROUPES_CARTOGRAPHIES",
              "TEXTE_LECTURE_CROISEE", "CONNAISSANCE_EMPRISE"],
)
def connaissance(ctx):
    """État des connaissances par maille (zone + connaissance_rayon_km) : effort (données, jours d'observation),
    richesse rapportée au pool local du groupe (espèces connues dans un rayon de pool_local_km), espèces à enjeux,
    tableau de synthèse par groupe et groupes cartographiés (avec avertissement si la prospection est ponctuelle)."""
    p = ctx.params
    q = _queries(ctx)
    zone, court, renvoi = _libelles(ctx)
    rayon_km = _rayon_km(ctx)
    pool_km = max(float(p.get("pool_local_km", 10)), rayon_km)
    groupes_vm = _groupes(ctx)
    seuil = int(p.get("connaissance_seuil_donnees", 2))
    min_especes = int(p.get("connaissance_min_especes_site", 4))
    seuil_jours = float(p.get("connaissance_alerte_jours_median", 2))

    pool_local = q.pool_local(pool_km, p.get("annees"), tuple(p.get("statuts_validation", ("0", "1", "2"))))
    pool_regional = {r["tx_group2_inpn_v2"]: r["nb_esp"] for r in ctx.queries.get_number_esp_per_taxonomy()}
    enjeu = enjeu_sql(bool(p.get("enjeux_oiseaux_nicheurs_seulement", True)))
    mailles = ind.indicateurs_mailles(
        q.mailles(rayon_km * 1000, p.get("grille_connaissance", "M1"), groupes_vm, enjeu), pool_local, seuil)
    especes = q.especes_par_groupe(rayon_km * 1000, groupes_vm)
    dans_zone = {r["groupe"]: r["nb_especes_zone"] for r in especes if r["nb_especes_zone"]}
    emprise = {r["groupe"]: r["nb_especes"] for r in especes if r["nb_especes"]}

    groupes = ind.groupes_cartographies(mailles, dans_zone, min_especes)
    medianes = ind.medianes_jours(mailles)
    alertes = {g: medianes[g] for g in groupes if medianes.get(g, 0) < seuil_jours}
    synthese = ind.synthese_groupes(mailles, emprise, pool_local, pool_regional, groupes, seuil, dans_zone)

    columns = [("groupe", "Groupe"), ("nb_especes_site", f"Espèces ({court})")]
    if rayon_km:
        columns.append(("nb_especes", f"Espèces ({court} + {rayon_km:g} km)"))
    columns += [("pool_local", f"Espèces à {pool_km:g} km"), ("pct_local", "Part locale"),
                ("pool_regional", "Espèces en région"), ("nb_mailles", "Mailles avec données"),
                ("mailles_peu_donnees", f"dont < {seuil} données"), ("jours_median", "Jours par maille (médiane)"),
                ("carte", "Carte")]
    # jusqu'à 10 colonnes : police réduite pour que les en-têtes ne se coupent pas au milieu des mots
    widths = [1.4] + [1] * (len(columns) - 2) + [0.8]
    table = TableBlock(synthese, insert_lpo_table, {"columns": columns, "widths": widths, "font_size": 7.5})
    path = ctx.output_dirs["tables"] / f"{p.get('connaissance_excel', 'connaissance_groupes')}.xlsx"
    if synthese:
        export_species_excel(data=[{label: r.get(k) for k, label in columns} for r in synthese], output_path=path)

    return AnalysisResult(
        data={"mailles": mailles, "groupes": groupes, "pool_local": pool_local, "synthese": synthese,
              "rayon_km": rayon_km, "pool_km": pool_km,
              "avertissements": {g: ind.texte_avertissement_effort(m, seuil_jours) for g, m in alertes.items()}},
        files={"connaissance_groupes": path},
        texts={"POOL_LOCAL_KM": f"{pool_km:g}", "SEUIL_PEU_DONNEES": str(seuil),
               "CONNAISSANCE_EMPRISE": ind.texte_emprise(zone, rayon_km),
               "TEXTE_GROUPES_CARTOGRAPHIES": ind.texte_groupes_cartographies(groupes, min_especes, alertes,
                                                                              seuil_jours, zone, renvoi),
               "TEXTE_LECTURE_CROISEE": ind.texte_lecture_croisee()},
        tables={"TABLE_CONNAISSANCE_GROUPES": table},
    )


@register_brick("couches_qgis_connaissance", requires=["socle_data", "connaissance"])
def couches_qgis_connaissance(ctx):
    """Couches du projet QGIS (connaissance_mailles, connaissance_grille, couverture connaissance_atlas_groupes)
    et emprise commune des cartes d'effort et des atlas : contour de l'emprise des mailles + une maille de marge."""
    p = ctx.params
    q = _queries(ctx)
    data = ctx.results["connaissance"].data
    rayon_m = data["rayon_km"] * 1000
    rect = ind.emprise_contour(q.enveloppe_zone(), rayon_m + float(p.get("emprise_marge_mailles_km", 1)) * 1000)
    couverture = [{"cle": t, "groupe": g, "pool_local": data["pool_local"].get(g), "ordre": i,
                   "geom": ind.rectangle_wkt(rect)}
                  for i, (g, t) in enumerate(((g, ind.cle(g)) for g in data["groupes"]), start=1)]
    couches = {
        "connaissance_mailles": data["mailles"],
        "connaissance_grille": q.grille(p.get("grille_connaissance", "M1"), rayon_m),
        "connaissance_atlas_groupes": couverture,
    }
    for name, rows in couches.items():
        export_gpkg(rows, ctx.output_dirs["data"], layer_name=name, geom_col="geom", crs="EPSG:2154")

    render = dict(ctx.params.get("qgis_render") or {})
    render["project_variables"] = {**(render.get("project_variables") or {}), "pool_local_km": f"{data['pool_km']:g}"}
    render["layout_extents"] = {**(render.get("layout_extents") or {}), EFFORT_DONNEES: rect, EFFORT_JOURS: rect}
    ctx.params["qgis_render"] = render
    return AnalysisResult(data={"couverture": couverture, **{f"nb_{k}": len(v) for k, v in couches.items()}})


@register_brick(
    "connaissance_atlas",
    requires=["couches_qgis_connaissance", "cartography"],
    provides=["ATLAS_CONNAISSANCE_GROUPES"],
    last=True,
)
def connaissance_atlas(ctx):
    """Par groupe cartographié : titre, avertissement éventuel, carte « Part des espèces locales » et carte
    « Richesse et prospection » (images produites par le rendu QGIS)."""
    maps = ctx.output_dirs["maps"]
    avertissements = ctx.results["connaissance"].data.get("avertissements", {})
    blocs = [{"titre": r["groupe"], "avertissement": avertissements.get(r["groupe"]),
              "figures": [{"path": maps / f"{ATLAS_GROUPES}__{r['cle']}.png",
                           "legende": f"Part des espèces locales – {r['groupe']}"},
                          {"path": maps / f"{ATLAS_CROISEE}__{r['cle']}.png",
                           "legende": f"Richesse et prospection – {r['groupe']}"}]}
             for r in ctx.results["couches_qgis_connaissance"].data["couverture"]]
    niveau = int(ctx.params.get("connaissance_niveau_titre", 3))
    return AnalysisResult(tables={
        "ATLAS_CONNAISSANCE_GROUPES": TableBlock(blocs, insert_figure_list, {"note": None, "niveau": niveau})})
