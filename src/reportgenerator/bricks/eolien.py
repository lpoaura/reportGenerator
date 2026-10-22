"""
Briques du dossier éolien (synthèse avifaune).

Méthodes reprises des anciens scripts R (traitement_generale_v2.R + script_sql/),
cf. dossiers/eolien/METHODO.md. Toutes les données viennent de la VM principale :
les couches des cartes sont exportées en GPKG dans data/ avant la brique cartography.
"""

import re

from reportgenerator.analysis.cartography.export import export_gpkg
from reportgenerator.analysis.common.models import AnalysisResult, ImageBlock, TableBlock
from reportgenerator.analysis.common.figures import insert_figure_list
from reportgenerator.analysis.common.paragraphs import insert_paragraph_list
from reportgenerator.analysis.common.tables.excel_export import export_species_excel
from reportgenerator.analysis.common.tables.ring_table import insert_lpo_table, insert_ring_table
from reportgenerator.analysis.eolien import couches_qgis
from reportgenerator.analysis.eolien import selections as sel
from reportgenerator.analysis.eolien.queries import EolienQueries
from reportgenerator.analysis.eolien import vulnerabilite as vuln
from reportgenerator.analysis.eolien.cartes import attribuer_couleurs, load_couleurs, plan_cartes
from reportgenerator.analysis.eolien.dataviz import histogramme_vulnerabilite
from reportgenerator.analysis.eolien.tables import (ALL, anneaux_texte, est_enjeu, groupes_non_vides, lr_codes,
                                                    periode_etude, phrase_precautions, pivot_par_anneau,
                                                    resume_par_anneau, ring_labels,
                                                    sensibilite_totale, texte_connaissance, vulnerabilite_totale)
from reportgenerator.core.registry import register_brick

LR_LABELS = {"lr_aura": "LR AuRA", "lr_auv": "LR Auvergne", "lr_ra": "LR Rhône-Alpes"}
STATUS_FIELDS = ("lr_fr_nich", "lr_fr_hiv", "lr_fr_migr", "lr_france", "lr_aura", "lr_auv", "lr_ra")
METRICS = [("nb_obs", "Nb données"), ("derniere_annee", "Dernière obs.")]
METRICS_MIGRATION = [*METRICS, ("effectif_max", "Max ind.")]
STATUT_NIDIF = [("statut_nidif", "Statut nidif.")]
LR_HIVERNANT = [("lr_fr_hiv", "LR France hivernants")]
LR_MIGRATEUR = [("lr_fr_migr", "LR France migrateurs")]
# cellule « Vulnérabilité » : « 3,5 » sur fond coloré (dégradé de la matrice)
VULN_FORMAT = {"vulnerabilite": lambda v: (vuln.fmt_note(v), vuln.couleur(v), vuln.couleur_texte(v))}


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


def _hors_region(ctx):
    """Part et géométrie de l'aire d'étude hors de la région couverte par la base (requête faite une fois)."""
    region = ctx.params.get("region_donnees", "AUVERGNE-RHONE-ALPES")
    return ctx.cached("hors_region", lambda: _queries(ctx).hors_region(region))


def _qualite(ctx):
    return ctx.cached("qualite_donnees", lambda: _queries(ctx).qualite_donnees())


def precautions(ctx, groupe: str) -> str:
    """Phrase « Précautions de lecture » pour un groupe ('oiseaux' ou 'chiro')."""
    q = _qualite(ctx).get(groupe, {})
    return phrase_precautions(
        _hors_region(ctx).get("pct_hors_region"),
        ctx.params.get("region_libelle", "Auvergne-Rhône-Alpes"),
        q.get("nb_donnees", 0),
        q.get("nb_lieu_dit", 0),
    )


def _lr_regionale(ctx):
    return ctx.params.get("lr_regionale", "lr_aura")


def _vulnerabilites(ctx) -> dict:
    """Indice de vulnérabilité par cd_ref, calculé une fois sur TOUTES les données d'oiseaux : les statuts
    migrateur / hivernant ne dépendent pas de la sélection d'un tableau (ex. nicheurs seuls)."""
    def calcul():
        lr = _lr_regionale(ctx)
        return {sp["cd_ref"]: vuln.indice_vulnerabilite(sp, lr) for sp in _species(ctx, "oiseaux", "true")}
    return ctx.cached("eolien_vulnerabilites", calcul)


def _avec_vulnerabilite(ctx, data):
    notes = _vulnerabilites(ctx)
    for sp in data:
        sp["vulnerabilite"] = notes.get(sp["cd_ref"])
    return data


def _seuil(ctx):
    """Seuil de l'indice (tableau principal, phrase, passereaux) : > 2,5, ou >= si vulnerabilite_seuil_inclus."""
    return {"seuil": float(ctx.params.get("vulnerabilite_seuil", 2.5)),
            "inclus": bool(ctx.params.get("vulnerabilite_seuil_inclus", False))}


def _lr_columns(ctx, lr_france_extra=()):
    lr = _lr_regionale(ctx)
    return [
        ("lr_fr_nich", "LR France"),
        *lr_france_extra,
        (lr, LR_LABELS.get(lr, lr)),
        # juste après la liste rouge régionale (demande des rédacteurs)
        ("vulnerabilite", "Vulnérabilité"),
        ("sensibilite", "Sensibilité éolien"),
    ]


def _ring_table(ctx, data, metrics=METRICS, extra_columns=(), lr_france_extra=()):
    """Tableau par anneau ; les anneaux sans aucune donnée dans le tableau sont retirés."""
    _avec_vulnerabilite(ctx, data)
    fixed = [
        ("nom_vern", "Nom vernaculaire"),
        ("lb_nom", "Nom scientifique"),
        ("prot_nat", "Protection nationale"),
        *_lr_columns(ctx, lr_france_extra),
        *extra_columns,
    ]
    groups = groupes_non_vides(data, [(ALL, "Ensemble des zones"), *enumerate(ring_labels(_anneaux(ctx)))])
    return TableBlock(
        data,
        insert_ring_table,
        {"fixed_columns": fixed, "groups": groups, "metrics": metrics, "status_fields": STATUS_FIELDS,
         "cell_formats": VULN_FORMAT},
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


def _export_simple(ctx, name, data, columns):
    """Copie Excel d'un tableau simple (une ligne d'en-tête)."""
    rows = [{label: item.get(key) for key, label in columns} for item in data]
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
    provides=["LOCALISATION", "PERIODE_ETUDE", "RAYON_MAX_KM", "ANNEAUX_KM", "TITRE_RAPPORT", "ENJEUX_ETUDIES"],
)
def projet_info(ctx):
    """Titre, localisation (nom de la zone), période d'étude et rayons des anneaux.
    Le commanditaire (entreprise, adresse) reste à compléter à la main dans le Word."""
    anneaux = ctx.params.get("anneaux_km") or [ctx.buffer]
    chiro = ctx.is_enabled("chiropteres")
    return AnalysisResult(texts={
        # titre (page de garde, pieds de page) et objet de l'étude selon les analyses demandées
        "TITRE_RAPPORT": "Synthèse des données d’oiseaux "
                         + ("et de chiroptères " if chiro else "")
                         + "dans le cadre d’un projet éolien",
        "ENJEUX_ETUDIES": "avifaunistiques et chiroptérologiques" if chiro else "avifaunistiques",
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
        texts={"CONNAISSANCE_OISEAUX": " ".join(
            filter(None, [texte_connaissance(resume, _anneaux(ctx)), precautions(ctx, "oiseaux")]))},
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
    "vulnerabilite_eolien",
    requires=["socle_data"],
    provides=["TEXTE_VULNERABILITE", "SEUIL_VULNERABILITE", "NB_ESPECE_VULNERABLE", "TABLE_VULNERABILITE",
              "TABLE_VULNERABILITE_ANNEXE", "TABLE_MATRICE_VULNERABILITE", "CHART_VULNERABILITE",
              "LISTE_ESPECES_TRES_VULNERABLES", "VULNERABILITE_PHRASES_MIN"],
)
def vulnerabilite_eolien(ctx):
    """Indice de vulnérabilité (MEDDE 2015) : tableau principal (indice au-dessus du seuil, décroissant),
    annexe (toutes les espèces, ordre alphabétique), phrase de synthèse et histogramme."""
    species = _avec_vulnerabilite(ctx, _species(ctx, "oiseaux", "true"))
    for sp in species:
        sp["statut_bio"] = vuln.statut_biologique(sp)
    seuil = _seuil(ctx)
    retenues = vuln.tri_vulnerabilite([sp for sp in species if vuln.depasse_seuil(sp["vulnerabilite"], **seuil)])

    columns = [
        ("nom_vern", "Nom vernaculaire"),
        ("lb_nom", "Nom scientifique"),
        *_lr_columns(ctx, [*LR_HIVERNANT, *LR_MIGRATEUR]),
        ("statut_bio", "Statut sur l'aire d'étude"),
        (f"nb_obs__{ALL}", "Nb données"),
    ]
    # colonne « Statut sur l'aire d'étude » plus large (texte long), listes rouges étroites
    options = {"columns": columns, "status_fields": STATUS_FIELDS, "italic_fields": ("lb_nom",), "font_size": 8,
               "cell_formats": VULN_FORMAT, "widths": [1.6, 1.7, 0.7, 0.8, 0.8, 0.7, 1.0, 0.9, 2.4, 0.8],
               "fixed_widths": True}
    sensibilites = [f"s{s}" for s in range(5)]
    matrice = {"columns": [("statut", "Enjeu de conservation (liste rouge)"),
                           *[(k, f"Sensibilité {k[1]}") for k in sensibilites]],
               "cell_formats": {k: VULN_FORMAT["vulnerabilite"] for k in sensibilites}, "widths": [3, 1, 1, 1, 1, 1]}
    tables = {
        "TABLE_VULNERABILITE": TableBlock(retenues, insert_lpo_table, options),
        "TABLE_VULNERABILITE_ANNEXE": TableBlock(species, insert_lpo_table, options),  # déjà par ordre alphabétique
        "TABLE_MATRICE_VULNERABILITE": TableBlock(vuln.matrice(), insert_lpo_table, matrice),
    }

    dataviz = ctx.output_dirs.get("dataviz", ctx.output_dirs["tables"])
    dataviz.mkdir(parents=True, exist_ok=True)
    chart = dataviz / "eolien_histogramme_vulnerabilite.png"
    histogramme_vulnerabilite(vuln.histogramme(species), str(chart))

    # phrases préremplies des espèces les plus vulnérables (indice >= vulnerabilite_phrases_min)
    phrases_min = float(ctx.params.get("vulnerabilite_phrases_min", 4))
    tres_vulnerables = [sp for sp in retenues if sp["vulnerabilite"] >= phrases_min]
    distances = {d["cd_ref"]: d for d in _queries(ctx).distances_especes([sp["cd_ref"] for sp in tres_vulnerables])}
    debut = int(periode_etude(int(ctx.params.get("annees", 10)))[1:5])
    phrases = [vuln.phrase_espece(sp, distances.get(sp["cd_ref"]), min(_anneaux(ctx)), debut)
               for sp in tres_vulnerables]
    tables["LISTE_ESPECES_TRES_VULNERABLES"] = TableBlock(phrases, insert_paragraph_list)

    files = {"vulnerabilite": _export_simple(ctx, "2b_oiseaux_vulnerabilite", species, columns)}
    return AnalysisResult(
        data={"retenues": retenues},
        files=files,
        images={"CHART_VULNERABILITE": ImageBlock(chart)},
        texts={
            "TEXTE_VULNERABILITE": vuln.texte_vulnerabilite(species, **seuil),
            "SEUIL_VULNERABILITE": vuln.libelle_seuil(**seuil),
            "NB_ESPECE_VULNERABLE": len(retenues),
            "VULNERABILITE_PHRASES_MIN": vuln.fmt_note(phrases_min),
        },
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


@register_brick(
    "passereaux",
    requires=["socle_data"],
    provides=["NB_PASSEREAUX_NICHEURS", "NB_PASSEREAUX_VULNERABLES", "TABLE_PASSEREAUX_NICHEURS"],
)
def passereaux(ctx):
    """Passereaux nicheurs (possible, probable, certain) dont l'indice de vulnérabilité dépasse le seuil (§5) :
    tableau par anneau (cartes : brique cartes_nidification)."""
    nicheurs = _avec_vulnerabilite(ctx, _species(ctx, "passereaux_nicheurs", sel.both(sel.PASSEREAUX, sel.NICHEUR)))
    retenus = [sp for sp in nicheurs if vuln.depasse_seuil(sp["vulnerabilite"], **_seuil(ctx))]
    table = _ring_table(ctx, retenus, extra_columns=STATUT_NIDIF)
    return AnalysisResult(
        data={"retenus": retenus},
        files={"passereaux": _export_excel(ctx, "4b_nidif_passereaux", table)},
        texts={"NB_PASSEREAUX_NICHEURS": len(nicheurs), "NB_PASSEREAUX_VULNERABLES": len(retenus)},
        tables={"TABLE_PASSEREAUX_NICHEURS": table},
    )


@register_brick(
    "autres_nicheurs",
    requires=["socle_data"],
    provides=["NB_AUTRES_NICHEURS", "TABLE_AUTRES_NICHEURS"],
)
def autres_nicheurs(ctx):
    """Autres espèces nicheuses à enjeux (ni rapace, ni grand voilier, ni passereau) : nicheur probable ou certain,
    et menacée (CR, EN, VU sur la LR régionale ou France des nicheurs) ou indice de vulnérabilité au-dessus du seuil."""
    where = sel.both(sel.NICHEUR_PROBABLE_CERTAIN, sel.non(sel.RAPACES), sel.non(sel.GRANDS_VOILIERS),
                     sel.non(sel.PASSEREAUX))
    nicheurs = _avec_vulnerabilite(ctx, _species(ctx, "autres_nicheurs", where))
    statuts = set(ctx.params.get("enjeux_lr_statuts", ("CR", "EN", "VU")))
    retenus = [sp for sp in nicheurs
               if (lr_codes(sp.get(_lr_regionale(ctx))) | lr_codes(sp.get("lr_fr_nich"))) & statuts
               or vuln.depasse_seuil(sp["vulnerabilite"], **_seuil(ctx))]
    table = _ring_table(ctx, retenus, extra_columns=STATUT_NIDIF)
    return AnalysisResult(
        data={"retenus": retenus},
        files={"autres_nicheurs": _export_excel(ctx, "4c_nidif_autres", table)},
        texts={"NB_AUTRES_NICHEURS": len(retenus)},
        tables={"TABLE_AUTRES_NICHEURS": table},
    )


SECTIONS_NIDIF = ("rapaces", "grands_voiliers", "passereaux", "autres")
CARTES_NIDIF = "Cartes_nidification"      # mise en page modèle du projet QGIS (une image par carte du plan)


@register_brick("cartes_nidification", requires=["nidification", "passereaux", "autres_nicheurs"])
def cartes_nidification(ctx):
    """Plan des cartes de nidification par groupe d'espèces (§5 bis) : TOUTES les espèces des tableaux de
    nidification (rapaces, grands voiliers, passereaux, autres), groupées par règles, 6 espèces au plus par carte,
    carte « Autres » pour les espèces d'aucun groupe ; données regroupées par maille de 100 m (floutage par espèce)."""
    p = ctx.params
    tables = {
        "rapaces": _species(ctx, "rapaces_nicheurs", sel.both(sel.NICHEUR_PROBABLE_CERTAIN, sel.RAPACES)),
        "grands_voiliers": _species(ctx, "gv_nicheurs", sel.both(sel.NICHEUR_PROBABLE_CERTAIN, sel.GRANDS_VOILIERS)),
        "passereaux": ctx.results["passereaux"].data["retenus"],
        "autres": ctx.results["autres_nicheurs"].data["retenus"],
    }
    especes = list({sp["cd_ref"]: sp for section in tables.values() for sp in section}.values())
    plan = plan_cartes(especes, p.get("groupes_cartes", []), int(p.get("cartes_max_especes", 6)),
                       autres=("autres", "autres espèces", "autres"))
    # passereaux : nicheur possible accepté (comme leur tableau) ; floutage par nom scientifique
    passereaux_cd = {sp["cd_ref"] for sp in tables["passereaux"]}
    floutage = {str(k): float(v) for k, v in (p.get("nidif_floutage_m") or {}).items()}
    maille = float(p.get("nidif_regroupement_m", 100))
    rows = _queries(ctx).nidification_mailles([
        {"cd_ref": sp["cd_ref"], "possible": sp["cd_ref"] in passereaux_cd,
         "maille_m": floutage.get(sp.get("lb_nom"), maille), "flouter": sp.get("lb_nom") in floutage}
        for sp in especes])
    for k in plan:
        k["titre_carte"] = f"Données de nidification des {k['titre']}"
    return AnalysisResult(data={"plan": plan, "rows": rows})


CARTES_DORTOIRS = "Cartes_dortoirs"      # mise en page modèle : une image par groupe d'espèces
CARTES_MIGRATION = "Cartes_migration"    # mise en page modèle : une image par espèce


@register_brick("cartes_dortoirs", requires=["dortoirs"], provides=["DORTOIRS_RAYON"])
def cartes_dortoirs(ctx):
    """Plan des cartes de dortoirs par groupe (mêmes groupes et même maximum que la nidification, carte « Autres ») ;
    zones de dortoir : tampons de dortoirs_rayon_m autour des données d'une espèce, fusionnés quand ils se touchent."""
    p = ctx.params
    especes = _species(ctx, "dortoirs", sel.both(sel.DORTOIR, sel.GROUPES_ENJEUX))
    plan = plan_cartes(especes, p.get("groupes_cartes", []), int(p.get("cartes_max_especes", 6)),
                       autres=("autres", "autres espèces", "autres"))
    for k in plan:
        k["titre_carte"] = f"Données de dortoirs des {k['titre']}"
    rayon = float(p.get("dortoirs_rayon_m", 750))
    rows = _queries(ctx).dortoirs_zones([sp["cd_ref"] for sp in especes], rayon)
    return AnalysisResult(data={"plan": plan, "rows": rows}, texts={"DORTOIRS_RAYON": f"{rayon:g} m"})


@register_brick("cartes_migration", requires=["migration", "vulnerabilite_eolien"],
                provides=["MIGRATION_CARTES_SEUIL"])
def cartes_migration(ctx):
    """Une carte de migration par espèce migratrice d'indice de vulnérabilité >= migration_cartes_vulnerabilite_min,
    plus les espèces de migration_cartes_especes (Milan royal) quand elles ont des données de migration."""
    p = ctx.params
    seuil = float(p.get("migration_cartes_vulnerabilite_min", 4))
    toujours = list(p.get("migration_cartes_especes", ["Milvus milvus"]))
    especes = _avec_vulnerabilite(ctx, _species(ctx, "migration", sel.MIGRATION))
    retenues = [sp for sp in especes if (sp.get("vulnerabilite") or 0) >= seuil or sp.get("lb_nom") in toujours]
    retenues.sort(key=lambda sp: (sp.get("lb_nom") not in toujours, -(sp.get("vulnerabilite") or 0),
                                  sp.get("nom_vern") or ""))
    plan = [{"cle": re.sub(r"[^a-z0-9]+", "_", (sp.get("lb_nom") or str(sp["cd_ref"])).lower()).strip("_"),
             "titre": sp.get("nom_vern"), "titre_carte": f"Données de migration : {sp.get('nom_vern')}",
             "section": "migration", "groupe": "migration", "especes": [sp], "ordre": i}
            for i, sp in enumerate(retenues, start=1)]
    rows = _queries(ctx).migration_points([sp["cd_ref"] for sp in retenues])
    return AnalysisResult(data={"plan": plan, "rows": rows},
                          texts={"MIGRATION_CARTES_SEUIL": vuln.fmt_note(seuil)})


# (brique du plan, mise en page modèle, couche GPKG) : cartes produites une image par page du plan
THEMES_CARTES = (("cartes_nidification", CARTES_NIDIF, "vm_eolienne_nidif_cartes"),
                 ("cartes_dortoirs", CARTES_DORTOIRS, "vm_eolienne_dortoirs_cartes"),
                 ("cartes_migration", CARTES_MIGRATION, "vm_eolienne_migration_especes"))


@register_brick("couches_cartes", requires=["cartes_nidification", "cartes_dortoirs", "cartes_migration"])
def couches_cartes(ctx):
    """Couleurs (une par espèce, la même sur toutes les cartes : nidification, dortoirs, migration) et couches des
    cartes ; liste des cartes transmise au rendu QGIS (une image par carte : <mise en page>__<clé>.png)."""
    p = ctx.params
    plans = {brique: ctx.results[brique].data["plan"] for brique, _, _ in THEMES_CARTES}
    referentiel = load_couleurs(ctx.dossier.path / p.get("couleurs_especes", "couleurs_especes.csv"))
    couleurs, remplacees = attribuer_couleurs(
        [[sp["cd_ref"] for sp in k["especes"]] for plan in plans.values() for k in plan], referentiel)

    annees_site = int(p.get("nidif_annees_site", 3))
    render = dict(p.get("qgis_render") or {})
    pages = dict(render.get("pages") or {})
    effectifs = {}
    for brique, mise_en_page, couche in THEMES_CARTES:
        plan = plans[brique]
        infos = {sp["cd_ref"]: (k, i, sp) for k in plan for i, sp in enumerate(k["especes"], start=1)}
        rows = []
        for row in ctx.results[brique].data["rows"]:
            carte, rang, sp = infos[row["cd_ref"]]
            rows.append({**row, "id": len(rows) + 1, "cle": carte["cle"], "nom": sp.get("nom_vern"),
                         "lb_nom": sp.get("lb_nom"), "couleur": couleurs[row["cd_ref"]], "ordre_legende": rang})
            if brique == "cartes_nidification":
                rows[-1]["site_pluriannuel"] = (row.get("nb_annee") or 0) >= annees_site
        _export_layer(ctx, rows, couche)
        effectifs[couche] = len(rows)
        pages[mise_en_page] = {"champ": "cle", "couches": [couche],
                               "pages": [{"cle": k["cle"], "titre": k["titre_carte"]} for k in plan]}
    render["pages"] = pages
    ctx.params["qgis_render"] = render
    return AnalysisResult(data={"couleurs": couleurs, "remplacees": remplacees, **effectifs})


def _figures(ctx, mise_en_page, pages):
    """Bloc insert_figure_list : une carte par page, presque pleine page (225 mm sans légende pour les autres)."""
    maps = ctx.output_dirs["maps"]
    figures = [{"path": maps / f"{mise_en_page}__{k['cle']}.png", "legende": k["titre_carte"]} for k in pages]
    return TableBlock([{"titre": None, "figures": figures}], insert_figure_list, {"note": None, "hauteur_max_mm": 215})


@register_brick(
    "cartes_word",
    requires=["couches_cartes", "cartography"],
    provides=[*(f"CARTES_NIDIF_{s.upper()}" for s in SECTIONS_NIDIF), "CARTES_DORTOIRS", "CARTES_MIGRATION_ESPECES"],
    last=True,
)
def cartes_word(ctx):
    """Cartes par groupe ou par espèce insérées dans le Word : nidification par sous-partie (rapaces, grands voiliers,
    passereaux, autres), dortoirs, migration."""
    nidif = ctx.results["cartes_nidification"].data["plan"]
    tables = {f"CARTES_NIDIF_{s.upper()}": _figures(ctx, CARTES_NIDIF, [k for k in nidif if k["section"] == s])
              for s in SECTIONS_NIDIF}
    tables["CARTES_DORTOIRS"] = _figures(ctx, CARTES_DORTOIRS, ctx.results["cartes_dortoirs"].data["plan"])
    tables["CARTES_MIGRATION_ESPECES"] = _figures(ctx, CARTES_MIGRATION, ctx.results["cartes_migration"].data["plan"])
    return AnalysisResult(tables=tables)


@register_brick("dortoirs", requires=["socle_data"], provides=["TABLE_DORTOIRS"])
def dortoirs(ctx):
    """Dortoirs / reposoirs (comportement ou remarque) des rapaces et grands voiliers (§6)."""
    where = sel.both(sel.DORTOIR, sel.GROUPES_ENJEUX)
    data = _species(ctx, "dortoirs", where)

    table = _ring_table(ctx, data, lr_france_extra=LR_HIVERNANT)
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

    table = _ring_table(ctx, enjeux, metrics=METRICS_MIGRATION, lr_france_extra=LR_MIGRATEUR)
    return AnalysisResult(
        files={"migration": _export_excel(ctx, "6_migration", table)},
        texts={"NB_MIGRATION_TOTAL": len(toutes), "NB_MIGRATION_ENJEUX": len(enjeux)},
        tables={"TABLE_MIGRATION": table},
    )


@register_brick(
    "couverture_cartes",
    requires=["vulnerabilite_eolien", "cartes_nidification", "dortoirs", "migration"],
    provides=["TEXTE_COUVERTURE_CARTES"],
)
def couverture_cartes(ctx):
    """Contrôle : espèces très vulnérables (indice >= vulnerabilite_carte_min) absentes de toutes les cartes
    thématiques (cartes de nidification par groupe, dortoirs, migration à enjeux)."""
    cartographiees = {sp["cd_ref"] for k in ctx.results["cartes_nidification"].data["plan"] for sp in k["especes"]}
    for key in ("dortoirs", "migration_enjeux"):
        cartographiees |= {sp["cd_ref"] for sp in ctx.cached(f"eolien_species_{key}", lambda: [])}
    species = _avec_vulnerabilite(ctx, _species(ctx, "oiseaux", "true"))
    note_min = float(ctx.params.get("vulnerabilite_carte_min", 3))
    return AnalysisResult(texts={"TEXTE_COUVERTURE_CARTES": vuln.texte_couverture(species, cartographiees, note_min)})


@register_brick("couches_qgis_eolien", requires=["socle_data"])
def couches_qgis_eolien(ctx):
    """Couches GPKG du projet QGIS éolien, sous les noms et champs de l'ancien workflow R
    (vm_eolienne_*), pour que le projet modèle fonctionne sans modification."""
    q = _queries(ctx)
    anneaux = _anneaux(ctx)

    mailles = q.sensibilite_mailles(_vulnerabilites(ctx))
    vuln_mailles = []
    for i, row in enumerate(mailles, start=1):
        # carte 17 bis : même indice, en partant de la vulnérabilité max (0,5 à 4,5) au lieu de la sensibilité
        vuln_mailles.append({
            "id": i, "id_area": row["id_area"], "geom": row["geom_maille"],
            "vuln_especes": float(row.get("vuln_especes") or 0), "bonus_nidif": row["bonus_nidif"],
            "bonus_dortoir": row["bonus_dortoir"], "bonus_migration": row["bonus_migration"],
            "vulnerabilite": vulnerabilite_totale(row), "nb_data": row.get("nb_data"),
        })
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
        "vm_eolienne_nidif_tampon": tampons,
        "vm_eolienne_dortoirs": q.fetch(couches_qgis.DORTOIRS_SQL),
        "vm_eolienne_migration_all": q.fetch(couches_qgis.MIGRATION_SQL),
        "vm_eolienne_sensi_oiseau": mailles,
        "vm_eolienne_vuln_oiseau": vuln_mailles,
        # partie de l'aire d'étude hors région (pas de données) : à hachurer sur les cartes
        "vm_eolienne_hors_region": [r for r in [_hors_region(ctx)] if r.get("geom")],
    }
    for name, rows in couches.items():
        _export_layer(ctx, rows, name)
    return AnalysisResult(data={name: len(rows) for name, rows in couches.items()})
