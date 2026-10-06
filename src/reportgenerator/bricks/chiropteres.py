"""
Briques chiroptères du dossier éolien (cf. dossiers/eolien/METHODO.md, partie chiroptères).

Toutes les données viennent de la VM principale (VisioNature, DBchiro et partenaires
sont déjà dans gn_synthese : aucune requête directe sur src_dbchirogcra, donc pas de doublon).
La brique "chiropteres" regroupe toutes les autres : c'est elle qu'un déclencheur active,
et elle délimite la section {{#chiropteres}} ... {{/chiropteres}} du template.
"""

from reportgenerator.analysis.common.models import AnalysisResult, TableBlock
from reportgenerator.analysis.common.tables.ring_table import insert_lpo_table, insert_ring_table
from reportgenerator.analysis.eolien import selections as sel
from reportgenerator.analysis.eolien.chiropteres import (CLASS_SCORES, est_espece, groupe, liste_vulnerables,
                                                         load_referentiel, pivot_gites, resume_periodes,
                                                         texte_connaissance_chiro, texte_gites,
                                                         tri_vulnerabilite, vulnerabilite)
from reportgenerator.analysis.eolien.tables import (ALL, pivot_par_anneau, resume_par_anneau,
                                                    ring_labels, sensibilite_totale)
from reportgenerator.bricks.eolien import (_anneaux, _export_excel, _export_layer, _qualite, _queries,
                                           precautions)
from reportgenerator.core.registry import register_brick

DEFAULT_SEUILS_NE = [[10, "Très forte"], [7, "Forte"], [5, "Moyenne"]]
DEFAULT_SEUILS_NH = [[8, "Forte"], [5, "Moyenne"]]
STATUS_FIELDS = ("lr_fr_nich", "lr_aura")


# =========================================================
# OUTILS
# =========================================================


def _referentiel(ctx):
    path = ctx.dossier.path / ctx.params.get("chiro_referentiel", "ref_chiropteres.csv")
    return ctx.cached("chiro_referentiel", lambda: load_referentiel(path))


def _floutage(ctx):
    return ctx.params.get("chiro_floutage_m", 0)


def _taxons(ctx):
    """Taxons de chiroptères (espèces, complexes, genres) pivotés par anneau, avec vulnérabilité."""
    def compute():
        rows = _queries(ctx).species_ring_stats("true", taxon=sel.CHIROPTERES)
        for row in rows:
            # unité de comptage : observation (taxon, jour, lieu) ; les contacts acoustiques bruts
            # (souvent des centaines par nuit et par point) sont gardés dans nb_contacts
            row["nb_contacts"] = row["nb_obs"]
            row["nb_obs"] = row.get("nb_sessions", row["nb_obs"])
        ne = ctx.params.get("chiro_seuils_ne", DEFAULT_SEUILS_NE)
        nh = ctx.params.get("chiro_seuils_nh", DEFAULT_SEUILS_NH)
        return [vulnerabilite(sp, _referentiel(ctx), ne, nh) for sp in pivot_par_anneau(rows)]
    return ctx.cached("chiro_taxons", compute)


def _ring_groups(ctx):
    return [(ALL, "Ensemble des zones"), *enumerate(ring_labels(_anneaux(ctx)))]


# =========================================================
# BRIQUES
# =========================================================


@register_brick(
    "chiro_connaissance",
    requires=["socle_data"],
    provides=["NB_CHIRO_DONNEES", "NB_CHIRO_OBSERVATIONS", "NB_CHIRO_ESPECES", "NB_CHIRO_DONNEES_NON_ESPECE",
              "CHIRO_CONNAISSANCE", "TABLE_CHIRO_PERIMETRES"],
)
def chiro_connaissance(ctx):
    """Connaissance des chiroptères : données et espèces par anneau."""
    taxons = _taxons(ctx)
    resume = resume_par_anneau(taxons, _anneaux(ctx))
    total = next(r for r in resume if r["anneau"] == ALL)
    non_especes = sum(sp[f"nb_obs__{ALL}"] for sp in taxons if not est_espece(sp))
    contacts = _qualite(ctx).get("chiro", {}).get("nb_donnees", 0)

    columns = [
        ("zone", "Zone d'étude"),
        ("nb_obs", "Nombre d'observations (jour × lieu)"),
        ("nb_especes", "Nombre d'espèces"),
        ("derniere_annee", "Dernières observations"),
    ]
    return AnalysisResult(
        data={"resume": resume},
        texts={
            "NB_CHIRO_DONNEES": contacts,
            "NB_CHIRO_OBSERVATIONS": total["nb_obs"],
            "NB_CHIRO_ESPECES": total["nb_especes"],
            "NB_CHIRO_DONNEES_NON_ESPECE": non_especes,
            "CHIRO_CONNAISSANCE": " ".join(filter(None, [
                texte_connaissance_chiro(resume, _anneaux(ctx), non_especes, contacts),
                precautions(ctx, "chiro"),
            ])),
        },
        tables={"TABLE_CHIRO_PERIMETRES": TableBlock(resume, insert_lpo_table, {"columns": columns})},
    )


@register_brick(
    "chiro_vulnerabilite",
    requires=["socle_data"],
    provides=["TABLE_CHIRO_VULNERABILITE", "CHIRO_VULN_EOLIEN", "CHIRO_VULN_HABITAT",
              "TABLE_CHIRO_ESPECES", "TABLE_CHIRO_REFERENTIEL"],
)
def chiro_vulnerabilite(ctx):
    """Vulnérabilité éolien / habitat des espèces contactées, liste par anneau, référentiel."""
    taxons = _taxons(ctx)
    especes = tri_vulnerabilite([sp for sp in taxons if est_espece(sp)])

    # colonnes du tableau final du document chiroptères (NP et annexe II sont détaillés dans la méthode)
    vuln_columns = [
        ("nom_vern", "Nom vernaculaire"),
        ("lb_nom", "Nom scientifique"),
        (f"nb_obs__{ALL}", "Nb d'observations (jour × lieu)"),
        ("lr_fr_nich", "LR France"),
        ("lr_aura", "LR AuRA"),
        ("nh", "Note habitat (NH)"),
        ("nh_classe", "Vulnérabilité destruction d'habitat"),
        ("ne", "Note éolien (NE)"),
        ("ne_classe", "Vulnérabilité collisions et barotraumatismes"),
    ]
    vuln_widths = [3, 3, 1.2, 1, 1, 1.1, 1.8, 1.1, 1.8]
    especes_table = TableBlock(
        taxons,
        insert_ring_table,
        {
            "fixed_columns": [("nom_vern", "Nom vernaculaire"), ("lb_nom", "Nom scientifique"),
                              ("lr_fr_nich", "LR France"), ("lr_aura", "LR AuRA"),
                              ("ne_classe", "Vulnérabilité éolien")],
            "groups": _ring_groups(ctx),
            "metrics": [("nb_obs", "Nb obs. (jour × lieu)"), ("derniere_annee", "Dernière obs.")],
            "status_fields": STATUS_FIELDS,
        },
    )
    referentiel = sorted(
        ({**r, "dist_gite_km": r["dist_gite_m"] / 1000 if r["dist_gite_m"] else None}
         for r in _referentiel(ctx).values() if r["nse"] is not None),
        key=lambda r: (-r["nse"], -r["nhab"], r["nom_vern"]),
    )
    ref_columns = [
        ("nom_vern", "Nom vernaculaire"), ("lb_nom", "Nom scientifique"),
        ("nse", "Note sensibilité éolien (NSE)"), ("nhab", "Note habitat (NHab)"),
        ("dist_gite_km", "Rayon autour des gîtes (km)"),
    ]
    return AnalysisResult(
        data={"especes": especes},
        files={"chiro_especes": _export_excel(ctx, "7_chiro_especes", especes_table)},
        texts={
            "CHIRO_VULN_EOLIEN": liste_vulnerables(especes, "ne_classe"),
            "CHIRO_VULN_HABITAT": liste_vulnerables(especes, "nh_classe"),
        },
        tables={
            "TABLE_CHIRO_VULNERABILITE": TableBlock(
                especes, insert_lpo_table,
                {"columns": vuln_columns, "status_fields": STATUS_FIELDS, "italic_fields": ("lb_nom",),
                 "font_size": 8, "widths": vuln_widths}),
            "TABLE_CHIRO_ESPECES": especes_table,
            "TABLE_CHIRO_REFERENTIEL": TableBlock(
                referentiel, insert_lpo_table,
                {"columns": ref_columns, "italic_fields": ("lb_nom",), "widths": [3, 3, 1.5, 1.5, 1.5]}),
        },
    )


@register_brick(
    "chiro_gites",
    requires=["socle_data"],
    provides=["NB_CHIRO_COLONIES", "NB_CHIRO_GITES", "CHIRO_TEXTE_GITES", "TABLE_CHIRO_GITES"],
)
def chiro_gites(ctx):
    """Colonies de reproduction et gîtes connus, par anneau."""
    q = _queries(ctx)
    gites = pivot_gites(q.chiro_gites_stats(_floutage(ctx)))
    resume = q.chiro_gites_resume(_floutage(ctx))
    table = TableBlock(
        gites,
        insert_ring_table,
        {
            "fixed_columns": [("nom_vern", "Nom vernaculaire"), ("lb_nom", "Nom scientifique"),
                              ("type_gite", "Type"), ("effectif_max", "Effectif max")],
            "groups": _ring_groups(ctx),
            "metrics": [("nb_sites", "Nb sites"), ("derniere_annee", "Dernière obs.")],
        },
    )
    return AnalysisResult(
        data={"resume": resume},
        files={"chiro_gites": _export_excel(ctx, "8_chiro_gites", table)},
        texts={
            "NB_CHIRO_COLONIES": resume.get("nb_colonies") or 0,
            "NB_CHIRO_GITES": resume.get("nb_gites") or 0,
            "CHIRO_TEXTE_GITES": texte_gites(resume, gites, max(_anneaux(ctx))),
        },
        tables={"TABLE_CHIRO_GITES": table},
    )


@register_brick("chiro_periodes", requires=["socle_data"], provides=["TABLE_CHIRO_PERIODES"])
def chiro_periodes(ctx):
    """Données par période du cycle biologique (transit, estivage, hivernage)."""
    columns = [
        ("periode", "Période"),
        ("nb_donnees", "Nb de données"),
        ("nb_especes", "Nb d'espèces"),
        ("nb_non_especes", "Taxons non précisés à l'espèce"),
        ("principales", "Taxons les plus contactés (nb de données)"),
    ]
    rows = resume_periodes(_queries(ctx).chiro_periodes())
    return AnalysisResult(tables={"TABLE_CHIRO_PERIODES": TableBlock(rows, insert_lpo_table, {"columns": columns})})


@register_brick("couches_qgis_chiro", requires=["socle_data"])
def couches_qgis_chiro(ctx):
    """Couches GPKG des cartes chiroptères (vm_eolienne_*chiro*)."""
    q = _queries(ctx)
    floutage = _floutage(ctx)
    vuln = {sp["cd_ref"]: sp for sp in _taxons(ctx)}

    def enrich(rows):
        for row in rows:
            sp = vuln.get(row.get("cd_nom"), {})
            row.update({
                "groupe": groupe(row.get("lb_nom")),
                "ne": sp.get("ne"), "ne_classe": sp.get("ne_classe"),
                "nh": sp.get("nh"), "nh_classe": sp.get("nh_classe"),
            })
        return rows

    scores = {cd_ref: sp["ne_score"] for cd_ref, sp in vuln.items() if sp.get("ne_score")}
    # bonus « transit » seulement si une classe est configurée (période non prise en compte pour l'instant)
    transit_classe = ctx.params.get("chiro_transit_classe_min")
    mailles = q.chiro_sensibilite_mailles(
        scores, score_transit_min=CLASS_SCORES[transit_classe] if transit_classe else None)
    for i, row in enumerate(mailles, start=1):
        row["id"] = i
        row["geom"] = row.pop("geom_maille")
        row["sensibilite"] = sensibilite_totale({
            "sensi_especes": row["sensi_especes"], "bonus_nidif": row["bonus_colonie"],
            "bonus_dortoir": row["bonus_gite"], "bonus_migration": row["bonus_transit"],
        })

    distances = {cd_ref: r["dist_gite_m"] for cd_ref, r in _referentiel(ctx).items() if r["dist_gite_m"]}
    couches = {
        "vm_eolienne_chiro_data": enrich(q.chiro_points(floutage)),
        "vm_eolienne_etat_connaissance_chiro": q.chiro_connaissance_mailles(),
        "vm_eolienne_chiro_gites": enrich(q.chiro_gites_points(floutage)),
        "vm_eolienne_chiro_gite_tampon": q.chiro_gite_tampons(
            distances, floutage, defaut_m=ctx.params.get("chiro_dist_gite_defaut_m", 1000)),
        "vm_eolienne_sensi_chiro": mailles,
    }
    for name, rows in couches.items():
        _export_layer(ctx, rows, name)
    return AnalysisResult(data={name: len(rows) for name, rows in couches.items()})


@register_brick(
    "chiropteres",
    # chiro_periodes n'est pas inclus : le champ période n'est presque jamais renseigné
    # (6 données sur 12 828 sur la zone de test). À reprendre avec une période déduite de la date.
    requires=["chiro_connaissance", "chiro_vulnerabilite", "chiro_gites", "couches_qgis_chiro"],
)
def chiropteres(ctx):
    """Partie chiroptères du rapport éolien (active toutes les briques chiro_*)."""
    return AnalysisResult()
