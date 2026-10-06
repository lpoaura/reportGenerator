"""
Briques du dossier éolien (synthèse avifaune).

Méthodes reprises des anciens scripts R (traitement_generale_v2.R + script_sql/),
cf. dossiers/eolien/METHODO.md. Toutes les données viennent de la VM principale :
les couches des cartes sont exportées en GPKG dans data/ avant la brique cartography.
"""

from reportgenerator.analysis.cartography.export import export_gpkg
from reportgenerator.analysis.common.models import AnalysisResult, TableBlock
from reportgenerator.analysis.common.tables.excel_export import export_species_excel
from reportgenerator.analysis.common.tables.ring_table import insert_lpo_table, insert_ring_table
from reportgenerator.analysis.eolien import couches_qgis
from reportgenerator.analysis.eolien import selections as sel
from reportgenerator.analysis.eolien.queries import EolienQueries
from reportgenerator.analysis.eolien.tables import (ALL, anneaux_texte, est_enjeu, lr_codes,
                                                    periode_etude, pivot_par_anneau,
                                                    resume_par_anneau, ring_labels,
                                                    sensibilite_totale, texte_connaissance)
from reportgenerator.core.registry import register_brick

LR_LABELS = {"lr_aura": "LR AuRA", "lr_auv": "LR Auvergne", "lr_ra": "LR Rhône-Alpes"}
STATUS_FIELDS = ("lr_fr_nich", "lr_france", "lr_aura", "lr_auv", "lr_ra")
METRICS = [("nb_obs", "Nb données"), ("derniere_annee", "Dernière obs.")]
METRICS_MIGRATION = [*METRICS, ("effectif_max", "Max ind.")]
STATUT_NIDIF = [("statut_nidif", "Statut nidif.")]


# =========================================================
# OUTILS
# =========================================================


def _queries(ctx) -> EolienQueries:
    return ctx.cached("eolien_queries", lambda: EolienQueries(ctx.queries))


def _species(ctx, key, where):
    """Espèces d'une sélection, pivotées par anneau (requête faite une fois)."""
    return ctx.cached(f"eolien_species_{key}", lambda: pivot_par_anneau(_queries(ctx).species_ring_stats(where)))


def _anneaux(ctx):
    return ctx.queries.anneaux_km


def _lr_regionale(ctx):
    return ctx.params.get("lr_regionale", "lr_aura")


def _ring_table(ctx, data, metrics=METRICS, extra_columns=()):
    fixed = [
        ("nom_vern", "Nom vernaculaire"),
        ("lb_nom", "Nom scientifique"),
        ("prot_nat", "Protection nationale"),
        ("lr_fr_nich", "LR France"),
        (_lr_regionale(ctx), LR_LABELS.get(_lr_regionale(ctx), _lr_regionale(ctx))),
        ("sensibilite", "Sensibilité éolien"),
        *extra_columns,
    ]
    groups = [(ALL, "Ensemble des zones"), *enumerate(ring_labels(_anneaux(ctx)))]
    return TableBlock(
        data,
        insert_ring_table,
        {"fixed_columns": fixed, "groups": groups, "metrics": metrics, "status_fields": STATUS_FIELDS},
    )


def _export_excel(ctx, name, block: TableBlock):
    """Copie Excel du tableau (en-têtes à plat : "Zone d'étude - Nb données")."""
    opts = block.options
    rows = []
    for item in block.data:
        row = {label: item.get(key) for key, label in opts["fixed_columns"]}
        for suffix, group_label in opts["groups"]:
            for metric, metric_label in opts["metrics"]:
                row[f"{group_label} - {metric_label}"] = item.get(f"{metric}__{suffix}")
        rows.append(row)
    path = ctx.output_dirs["tables"] / f"{name}.xlsx"
    if rows:
        export_species_excel(data=rows, output_path=path)
    return path


def _export_layer(ctx, rows, layer_name, geom_col="geom"):
    export_gpkg(rows, ctx.output_dirs["data"], layer_name=layer_name, geom_col=geom_col, crs="EPSG:2154")


# =========================================================
# BRIQUES
# =========================================================


@register_brick(
    "projet_info",
    provides=["LOCALISATION", "PERIODE_ETUDE", "RAYON_MAX_KM", "ANNEAUX_KM"],
)
def projet_info(ctx):
    """Localisation (nom de la zone), période d'étude et rayons des anneaux.
    Le commanditaire (entreprise, adresse) reste à compléter à la main dans le Word."""
    anneaux = ctx.params.get("anneaux_km") or [ctx.buffer]
    return AnalysisResult(texts={
        "LOCALISATION": ctx.area_name,
        "PERIODE_ETUDE": periode_etude(int(ctx.params.get("annees", 10))),
        "RAYON_MAX_KM": f"{max(anneaux):g}",
        "ANNEAUX_KM": anneaux_texte(sorted(anneaux)),
    })


@register_brick(
    "perimetres_anneaux",
    requires=["socle_data"],
    provides=["TABLE_PERIMETRES", "CONNAISSANCE_OISEAUX"],
)
def perimetres_anneaux(ctx):
    """Répartition des données d'oiseaux par anneau (zone d'étude, contours, toute la zone)."""
    species = _species(ctx, "oiseaux", "true")
    resume = resume_par_anneau(species, _anneaux(ctx))

    columns = [
        ("zone", "Zone d'étude"),
        ("nb_obs", "Nombre d'observations"),
        ("nb_especes", "Nombre d'espèces"),
        ("derniere_annee", "Dernières observations"),
    ]
    return AnalysisResult(
        data={"resume": resume},
        texts={"CONNAISSANCE_OISEAUX": texte_connaissance(resume, _anneaux(ctx))},
        tables={"TABLE_PERIMETRES": TableBlock(resume, insert_lpo_table, {"columns": columns})},
    )


@register_brick(
    "especes_enjeux_eolien",
    requires=["perimetres_anneaux"],
    provides=["NB_ESPECE_TOTAL", "NB_ESPECE_ENJEUX", "TABLE_ESPECES_ENJEUX", "TABLE_AUTRES_ESPECES"],
)
def especes_enjeux_eolien(ctx):
    """Espèces à enjeux (§4) et autres espèces (annexe 2)."""
    species = _species(ctx, "oiseaux", "true")
    p = ctx.params
    criteres = {
        "lr_regionale": _lr_regionale(ctx),
        "lr_statuts": tuple(p.get("enjeux_lr_statuts", ("CR", "EN", "VU"))),
        "sensibilite_min": p.get("enjeux_sensibilite_min", 2),
    }
    enjeux = [sp for sp in species if est_enjeu(sp, **criteres)]
    autres = [sp for sp in species if not est_enjeu(sp, **criteres)]

    tables = {
        "TABLE_ESPECES_ENJEUX": _ring_table(ctx, enjeux),
        "TABLE_AUTRES_ESPECES": _ring_table(ctx, autres),
    }
    files = {
        "especes_enjeux": _export_excel(ctx, "2_oiseaux_especes_enjeux", tables["TABLE_ESPECES_ENJEUX"]),
        "autres_especes": _export_excel(ctx, "2_oiseaux_especes_autres", tables["TABLE_AUTRES_ESPECES"]),
    }
    return AnalysisResult(
        data={"enjeux": enjeux},
        files=files,
        texts={"NB_ESPECE_TOTAL": len(species), "NB_ESPECE_ENJEUX": len(enjeux)},
        tables=tables,
    )


@register_brick(
    "nidification",
    requires=["socle_data"],
    provides=["NB_RAPACE_NICHEUSE", "NB_RAPACE_NICHEUSE_ENJEUX", "TABLE_RAPACES_NICHEURS",
              "NB_ARDEIDES_NICHEUSE", "TABLE_ARDEIDES_NICHEURS"],
)
def nidification(ctx):
    """Nicheurs probables / certains : rapaces (§5.1), ardéidés, cigognes, laridés, grues (§5.2)."""
    rapaces = _species(ctx, "rapaces_nicheurs", sel.both(sel.NICHEUR_PROBABLE_CERTAIN, sel.RAPACES))
    grands_voiliers = _species(ctx, "gv_nicheurs", sel.both(sel.NICHEUR_PROBABLE_CERTAIN, sel.GRANDS_VOILIERS))

    statuts_enjeux = set(ctx.params.get("nicheur_enjeux_lr_statuts", ("CR", "EN", "VU", "NT")))
    rapaces_enjeux = [sp for sp in rapaces if lr_codes(sp.get(_lr_regionale(ctx))) & statuts_enjeux]

    tables = {
        "TABLE_RAPACES_NICHEURS": _ring_table(ctx, rapaces, extra_columns=STATUT_NIDIF),
        "TABLE_ARDEIDES_NICHEURS": _ring_table(ctx, grands_voiliers, extra_columns=STATUT_NIDIF),
    }
    files = {
        "rapaces": _export_excel(ctx, "3_nidif_rapaces", tables["TABLE_RAPACES_NICHEURS"]),
        "ardeides": _export_excel(ctx, "4_nidif_ardeides", tables["TABLE_ARDEIDES_NICHEURS"]),
    }
    return AnalysisResult(
        files=files,
        texts={
            "NB_RAPACE_NICHEUSE": len(rapaces),
            "NB_RAPACE_NICHEUSE_ENJEUX": len(rapaces_enjeux),
            "NB_ARDEIDES_NICHEUSE": len(grands_voiliers),
        },
        tables=tables,
    )


@register_brick("dortoirs", requires=["socle_data"], provides=["TABLE_DORTOIRS"])
def dortoirs(ctx):
    """Dortoirs / reposoirs (comportement ou remarque) des rapaces et grands voiliers (§6)."""
    where = sel.both(sel.DORTOIR, sel.GROUPES_ENJEUX)
    data = _species(ctx, "dortoirs", where)

    table = _ring_table(ctx, data)
    return AnalysisResult(
        files={"dortoirs": _export_excel(ctx, "5_dortoirs", table)},
        tables={"TABLE_DORTOIRS": table},
    )


@register_brick(
    "migration",
    requires=["socle_data"],
    provides=["NB_MIGRATION_TOTAL", "NB_MIGRATION_ENJEUX", "TABLE_MIGRATION"],
)
def migration(ctx):
    """Données de migration (§7) ; enjeux = rapaces et grands voiliers."""
    toutes = _species(ctx, "migration", sel.MIGRATION)
    enjeux = _species(ctx, "migration_enjeux", sel.both(sel.MIGRATION, sel.GROUPES_ENJEUX))

    table = _ring_table(ctx, enjeux, metrics=METRICS_MIGRATION)
    return AnalysisResult(
        files={"migration": _export_excel(ctx, "6_migration", table)},
        texts={"NB_MIGRATION_TOTAL": len(toutes), "NB_MIGRATION_ENJEUX": len(enjeux)},
        tables={"TABLE_MIGRATION": table},
    )


@register_brick("couches_qgis_eolien", requires=["socle_data"])
def couches_qgis_eolien(ctx):
    """Couches GPKG du projet QGIS éolien, sous les noms et champs de l'ancien workflow R
    (vm_eolienne_*), pour que le projet modèle fonctionne sans modification."""
    q = _queries(ctx)
    anneaux = _anneaux(ctx)

    mailles = q.sensibilite_mailles()
    for i, row in enumerate(mailles, start=1):
        total = sensibilite_totale(row)
        sensi = int(float(row["sensi_especes"] or 0))
        row.update({
            "id": i, "geom": row.pop("geom_maille"), "sensibilite": total,
            # mêmes champs que 17_vm_sensi_oiseau.sql (les sum_* du R étaient faussés par les jointures)
            "max_sensi": sensi, "max_sensi_n": row["bonus_nidif"], "max_sensi_d": row["bonus_dortoir"],
            "max_sensi_m": row["bonus_migration"], "tot_max_sensi": total,
            "sum_sensi": sensi, "sum_sensi_n": row["bonus_nidif"], "sum_sensi_d": row["bonus_dortoir"],
            "sum_sensi_m": row["bonus_migration"], "tot_sensi": total,
        })

    tampons = q.nidification_tampons(
        ctx.params.get("tampons_nidification_km", {}),
        statuts=tuple(ctx.params.get("tampons_statuts_nidif", ("Certain",))),
    )

    couches = {
        "vm_eolienne_zone_etude": q.fetch(couches_qgis.zone_etude_sql(ctx.id_area, ctx.area_name)),
        "vm_eolienne_limit": q.fetch(couches_qgis.limit_sql(ctx.id_area, anneaux)),
        "vm_eolienne_zone_protection": ctx.queries.get_knowledge_protected_area(
            rayon_km=ctx.params.get("zonage_rayon_km")),
        "vm_eolienne": q.fetch(couches_qgis.DONNEES_SQL),
        "vm_eolienne_etat_connaissance": q.fetch(couches_qgis.CONNAISSANCE_SQL),
        "vm_eolienne_nidif": q.fetch(couches_qgis.NIDIF_SQL),
        "vm_eolienne_nidif_cn": q.fetch(couches_qgis.NIDIF_CN_SQL),
        "vm_eolienne_nidif_tampon": tampons,
        "vm_eolienne_dortoirs": q.fetch(couches_qgis.DORTOIRS_SQL),
        "vm_eolienne_migration_all": q.fetch(couches_qgis.MIGRATION_SQL),
        "vm_eolienne_sensi_oiseau": mailles,
    }
    for name, rows in couches.items():
        _export_layer(ctx, rows, name)
    return AnalysisResult(data={name: len(rows) for name, rows in couches.items()})
