"""Briques du rapport annuel PLSOC Œdicnème (dossier plsoc).

plsoc_socle lit une fois toutes les données de l'emprise (schéma pr_oedic_news, lecture seule) et applique les
déductions ; les autres briques calculent et mettent en forme (analysis/plsoc/calculs.py, fonctions pures).
"""

from datetime import date

from reportgenerator.analysis.common.models import AnalysisResult, ImageBlock, TableBlock
from reportgenerator.analysis.plsoc import calculs as k
from reportgenerator.analysis.plsoc import figures as fig
from reportgenerator.analysis.plsoc.deductions import deduire
from reportgenerator.analysis.plsoc.queries import PlsocQueries
from reportgenerator.analysis.plsoc.word import inserer_blocs, inserer_tableau
from reportgenerator.core.registry import register_brick


def _d(ctx) -> dict:
    return ctx.results["plsoc_socle"].data


def _tableau(data, colonnes, largeurs=None, vide="Aucune donnée pour cette année."):
    return TableBlock(data, inserer_tableau, {"colonnes": colonnes, "largeurs_mm": largeurs, "vide": vide})


def _deduit(lignes) -> bool:
    return any("*" in r["lieu_dit"] for r in lignes)


def _image_ou_rien(cle, path, layout="normal"):
    """Image si elle a été produite, sinon le placeholder est vidé (texte vide)."""
    return {"images": {cle: ImageBlock(path, layout)}} if path else {"texts": {cle: ""}}


# ----------------------------------------------------------------------------------------------------- socle
@register_brick(
    "plsoc_socle",
    provides=[
        "AREA_NAME",
        "TITRE_RAPPORT",
        "ANNEE",
        "ANNEE_DEBUT",
        "DATE_DONNEES",
        "TEXTE_ZONE",
        "MAYFIELD_DUREE",
        "BLOCS_ETAT_DONNEES",
        "CARTE_ZONE",
    ],
)
def plsoc_socle(ctx):
    """Données PLSOC de l'emprise du rapport (toutes années jusqu'à la saison du rapport) et déductions."""
    p = ctx.params
    q = PlsocQueries(ctx.service_name, ctx.id_area, p.get("emprise", "demande"), p.get("schema", "pr_oedic_news"))
    annee = k.annee_rapport(p.get("annee"), q.annee_par_defaut())
    zone = q.zone()
    couples, nids = q.couples(annee), q.nids(annee)
    annees = [c["annee"] for c in couples]
    debut = max(int(p.get("annee_debut_serie", 2015)), min(annees)) if annees else annee
    d = {
        "annee": annee,
        "debut": debut,
        "zone": zone,
        "nomenc": q.nomenclatures(),
        "communes": q.communes_carte(),
        "secteurs": q.secteurs(),
        "couples": couples,
        "nids": nids,
        "evenements": q.evenements(annee),
        "synthese": q.synthese(annee),
        "rassemblements": q.rassemblements(annee),
        "bagues": q.bagues(annee),
        "mesures": q.mesures(),
        "suivis_mesure": q.suivis_mesure(annee),
        "habitat": q.habitat_menace(annee),
        "anomalies": q.anomalies(annee),
        "duree_mayfield": int(p.get("mayfield_duree_jours", 64)),
    }
    d["deductions"] = deduire(
        couples,
        nids,
        q.parcelles_mergin(),
        q.suivis_parcelle(annee),
        q.lieux_dits(),
        int(p.get("distance_lieu_dit_m", 1000)),
    )
    d["serie"] = k.serie_annuelle(couples, nids, debut, annee)
    print(
        f"[plsoc] saison {annee} (série depuis {debut}) : {len(k.de_annee(couples, annee))} couples, "
        f"{len(k.de_annee(nids, annee))} nids ; déductions : {d['deductions']}"
    )
    carte = fig.carte(
        ctx.output_dirs["maps"] / "carte_zone.png",
        zone["wkt"],
        d["communes"],
        d["secteurs"],
        d["mesures"],
        [],
        titre_legende="Emprise et secteurs",
    )
    titre = p.get("titre", "Plan local de sauvegarde de l'Œdicnème criard")
    etat = [("texte", t) for t in k.qualite(couples, nids, d["anomalies"], annee)]
    return AnalysisResult(
        data=d,
        texts={
            "AREA_NAME": ctx.area_name,
            "TITRE_RAPPORT": titre,
            "ANNEE": str(annee),
            "ANNEE_DEBUT": str(debut),
            "DATE_DONNEES": date.today().strftime("%d/%m/%Y"),
            "TEXTE_ZONE": k.texte_zone(zone, d["secteurs"]),
            "MAYFIELD_DUREE": str(d["duree_mayfield"]),
        },
        tables={"BLOCS_ETAT_DONNEES": TableBlock(etat, inserer_blocs)},
        images={"CARTE_ZONE": ImageBlock(carte, "page")},
    )


# ------------------------------------------------------------------------------------------------- résultats
@register_brick(
    "plsoc_resultats",
    requires=["plsoc_socle"],
    provides=[
        "TEXTE_RESULTATS_GENERAUX",
        "TABLE_COMMUNES",
        "TABLE_SERIE",
        "CARTE_REPARTITION",
        "CHART_POPULATION",
        "CHART_SUCCES_HISTORIQUE",
    ],
)
def plsoc_resultats(ctx):
    """Résultats généraux : bilan de l'année, communes, série depuis le début du suivi, carte, graphiques."""
    d = _d(ctx)
    a, out = d["annee"], ctx.output_dirs
    serie_lignes = [
        {
            "annee": r["annee"],
            "couples": r["couples"],
            "nicheurs": r["nicheurs"],
            "nids": r["nids"],
            "sc": r["succes_certain"],
            "sp": r["succes_probable"],
            "ep": r["echec_probable"],
            "ec": r["echec_certain"],
            "jeunes": r["jeunes"],
            "taux": "–" if r["taux_succes"] is None else f"{r['taux_succes']} %",
        }
        for r in d["serie"]
    ]
    return AnalysisResult(
        texts={"TEXTE_RESULTATS_GENERAUX": k.texte_resultats(d["serie"], a, d["debut"])},
        tables={
            "TABLE_COMMUNES": _tableau(
                k.tableau_communes(d["couples"], d["nids"], a),
                [("collectivite", "Collectivité"), ("commune", "Commune"), ("couples", "Couples"), ("nids", "Nids")],
                [62, 62, 22, 22],
            ),
            "TABLE_SERIE": _tableau(
                serie_lignes,
                [
                    ("annee", "Année"),
                    ("couples", "Couples"),
                    ("nicheurs", "Nicheurs certains"),
                    ("nids", "Nids"),
                    ("sc", "Succès certain"),
                    ("sp", "Succès probable"),
                    ("ep", "Échec probable"),
                    ("ec", "Échec certain"),
                    ("jeunes", "Jeunes à l'envol"),
                    ("taux", "Taux de succès"),
                ],
            ),
        },
        images={
            "CARTE_REPARTITION": ImageBlock(
                fig.carte(
                    out["maps"] / "carte_repartition.png",
                    d["zone"]["wkt"],
                    d["communes"],
                    d["secteurs"],
                    d["mesures"],
                    k.de_annee(d["couples"], a),
                    titre_legende=f"Couples {a}",
                ),
                "page",
            ),
            "CHART_POPULATION": ImageBlock(fig.chart_population(d["serie"], out["dataviz"] / "population.png")),
            "CHART_SUCCES_HISTORIQUE": ImageBlock(
                fig.chart_succes_historique(d["serie"], out["dataviz"] / "succes_historique.png")
            ),
        },
    )


# --------------------------------------------------------------------------------------------------- milieux
@register_brick(
    "plsoc_milieux",
    requires=["plsoc_socle"],
    provides=["TEXTE_MILIEUX", "CHART_MILIEUX_EVOLUTION", "CHART_MILIEUX_CULTURES", "CHART_MILIEUX_NON_AGRICOLES"],
)
def plsoc_milieux(ctx):
    """Milieux occupés : part agricole (évolution), cultures, milieux non agricoles."""
    d = _d(ctx)
    m = k.milieux(d["couples"], d["annee"], d["nomenc"])
    out = ctx.output_dirs["dataviz"]
    res = AnalysisResult(texts={"TEXTE_MILIEUX": m["texte"]})
    evo = (
        fig.chart_ligne(
            [(e["annee"], e["pct_agricole"]) for e in m["evolution"]],
            out / "milieux_evolution.png",
            "% de couples en milieu agricole",
            ymax=100,
        )
        if m["evolution"]
        else None
    )
    cult = fig.chart_barres(m["cultures"], out / "milieux_cultures.png") if m["cultures"] else None
    types = fig.chart_barres(m["types"], out / "milieux_non_agricoles.png", couleur="#8c6d31") if m["types"] else None
    for cle, path in (
        ("CHART_MILIEUX_EVOLUTION", evo),
        ("CHART_MILIEUX_CULTURES", cult),
        ("CHART_MILIEUX_NON_AGRICOLES", types),
    ):
        for attr, v in _image_ou_rien(cle, path).items():
            getattr(res, attr).update(v)
    return res


# -------------------------------------------------------------------------------------------------- secteurs
COLONNES_COUPLES = [
    ("commune", "Commune"),
    ("lieu_dit", "Lieu-dit"),
    ("statut", "Statut de reproduction"),
    ("succes", "Succès de reproduction"),
    ("menace", "Degré de menace"),
]


@register_brick("plsoc_secteurs", requires=["plsoc_socle"], provides=["SECTEURS"])
def plsoc_secteurs(ctx):
    """Un bloc par secteur : texte chiffré, série depuis le début du suivi, carte, tableau par couple."""
    d = _d(ctx)
    a = d["annee"]
    blocs = []
    geoms = {s["nom_secteur"]: s["wkt"] for s in d["secteurs"]}
    for i, s in enumerate(k.secteurs(d["couples"], d["nids"], d["secteurs"], a, d["debut"], d["nomenc"]), 1):
        annees = list(s["serie"])
        blocs += [
            ("titre", 3, s["nom"]),
            ("texte", s["texte"]),
            (
                "tableau",
                [{"lib": "Couples", **{str(x): s["serie"][x] for x in annees}}],
                [("lib", "")] + [(str(x), str(x)) for x in annees],
                [22] + [round(148 / max(len(annees), 1), 1)] * len(annees),
            ),
        ]
        if s["secteur"] in geoms:
            path = fig.carte(
                ctx.output_dirs["maps"] / f"secteur_{i:02d}.png",
                d["zone"]["wkt"],
                d["communes"],
                d["secteurs"],
                d["mesures"],
                k.de_annee(d["couples"], a),
                titre_legende=f"Couples {a}",
                emprise=fig.emprise_autour([geoms[s["secteur"]]]),
                etiquettes_secteurs=False,
            )
            blocs += [("image", path, 150), ("legende", f"Carte : secteur {s['nom']} en {a}.")]
        blocs += [
            ("tableau", s["lignes"], COLONNES_COUPLES, [32, 42, 36, 36, 30]),
            (
                "legende",
                f"Tableau : statut, succès de reproduction et degré de menace de chaque couple du secteur "
                f"{s['nom']} ({a}{' ; * lieu-dit déduit, à vérifier' if _deduit(s['lignes']) else ''}).",
            ),
            (
                "a_rediger",
                f"[Commentaire du secteur {s['nom']} à rédiger : évolution, sites occupés ou "
                "désertés, menaces, faits marquants.]",
            ),
        ]
    return AnalysisResult(tables={"SECTEURS": TableBlock(blocs, inserer_blocs)})


# ------------------------------------------------------------------------------------------------ protection
@register_brick(
    "plsoc_protection",
    requires=["plsoc_socle"],
    provides=["TEXTE_PROTECTION", "TABLE_PROTECTION_AGRICOLE", "TABLE_PROTECTION_NON_AGRICOLE"],
)
def plsoc_protection(ctx):
    """Nids protégés en milieu agricole et non agricole."""
    d = _d(ctx)
    pr = k.protection(d["nids"], d["couples"], d["annee"], d["nomenc"])
    return AnalysisResult(
        texts={"TEXTE_PROTECTION": pr["texte"]},
        tables={
            "TABLE_PROTECTION_AGRICOLE": _tableau(
                pr["agricole"],
                [
                    ("commune", "Commune"),
                    ("lieu_dit", "Lieu-dit"),
                    ("protection", "Protection"),
                    ("eclosion", "Éclosion"),
                    ("succes", "Succès reproduction"),
                ],
                [38, 48, 30, 20, 34],
                vide="Aucun nid protégé en milieu agricole.",
            ),
            "TABLE_PROTECTION_NON_AGRICOLE": _tableau(
                pr["non_agricole"],
                [
                    ("commune", "Commune"),
                    ("lieu_dit", "Lieu-dit"),
                    ("site", "Site"),
                    ("eclosion", "Éclosion"),
                    ("succes", "Succès reproduction"),
                ],
                [38, 44, 34, 20, 34],
                vide="Aucun nid protégé hors milieu agricole.",
            ),
        },
    )


# ---------------------------------------------------------------------------------------- phénologie, succès
@register_brick(
    "plsoc_succes",
    requires=["plsoc_socle"],
    provides=[
        "TABLE_PHENOLOGIE",
        "TEXTE_PHENOLOGIE",
        "CHART_PHENOLOGIE",
        "TABLE_SUCCES",
        "TEXTE_SUCCES",
        "TABLE_MAYFIELD",
        "TEXTE_MAYFIELD",
        "TEXTE_CAUSES",
        "CHART_CAUSES",
    ],
)
def plsoc_succes(ctx):
    """Phénologie (dates clés, présence par décade), succès de reproduction, Mayfield, causes d'échec."""
    d = _d(ctx)
    a, out = d["annee"], ctx.output_dirs["dataviz"]
    pheno = k.phenologie_dates(d["couples"], d["nids"], d["rassemblements"], d["synthese"], d["debut"], a)
    dec = k.phenologie_decades(d["couples"], a, d["debut"])
    su = k.succes(d["nids"], a, d["nomenc"])
    mf = k.mayfield(d["nids"], a, d["duree_mayfield"])
    ca = k.causes(d["nids"], a, d["nomenc"])
    res = AnalysisResult(
        texts={
            "TEXTE_PHENOLOGIE": dec["texte"],
            "TEXTE_SUCCES": su["texte"],
            "TEXTE_MAYFIELD": k.texte_mayfield(mf, a),
            "TEXTE_CAUSES": ca["texte"],
        },
        tables={
            "TABLE_PHENOLOGIE": _tableau(
                pheno,
                [
                    ("annee", "Année"),
                    ("premiere_obs", "1re observation"),
                    ("premier_couple", "1er couple cantonné"),
                    ("premiere_couvaison", "1re couvaison"),
                    ("premier_poussin", "1er poussin"),
                    ("premier_rassemblement", "1er rassemblement"),
                    ("derniere_obs", "Dernière observation"),
                ],
            ),
            "TABLE_SUCCES": _tableau(
                su["lignes"], [("succes", "Succès"), ("nids", "Nids"), ("pct", "%")], [60, 25, 25]
            ),
            "TABLE_MAYFIELD": _tableau(
                k.lignes_mayfield(mf), [("indicateur", "Indicateur"), ("valeur", "Valeur")], [80, 35]
            ),
        },
        images={"CHART_PHENOLOGIE": ImageBlock(fig.chart_phenologie(dec["lignes"], a, out / "phenologie.png"))},
    )
    causes_png = (
        fig.chart_barres(ca["detail"], out / "causes.png", "Nombre de nids", "#d73027") if ca["detail"] else None
    )
    for attr, v in _image_ou_rien("CHART_CAUSES", causes_png).items():
        getattr(res, attr).update(v)
    return res


# ----------------------------------------------------------------------------------- rassemblements, baguage
@register_brick(
    "plsoc_rassemblements",
    requires=["plsoc_socle"],
    provides=["TEXTE_RASSEMBLEMENTS", "TABLE_RASSEMBLEMENTS", "CHART_RASSEMBLEMENTS"],
)
def plsoc_rassemblements(ctx):
    """Rassemblements postnuptiaux : effectif maximal par site, historique."""
    d = _d(ctx)
    r = k.rassemblements(d["rassemblements"], d["annee"])
    res = AnalysisResult(
        texts={"TEXTE_RASSEMBLEMENTS": r["texte"]},
        tables={
            "TABLE_RASSEMBLEMENTS": _tableau(
                r["lignes"],
                [
                    ("site", "Site"),
                    ("commune", "Commune"),
                    ("effectif", "Effectif max"),
                    ("date", "Date"),
                    ("comptages", "Comptages"),
                    ("record", "Maximum antérieur (année)"),
                ],
                vide="Aucun comptage enregistré pour cette année.",
            )
        },
    )
    png = fig.chart_rassemblements(r["historique"], ctx.output_dirs["dataviz"] / "rassemblements.png")
    for attr, v in _image_ou_rien("CHART_RASSEMBLEMENTS", png).items():
        getattr(res, attr).update(v)
    return res


@register_brick("plsoc_baguage", requires=["plsoc_socle"], provides=["TEXTE_BAGUAGE", "TABLE_BAGUAGE"])
def plsoc_baguage(ctx):
    """Oiseaux bagués (poussins) et adultes bagués identifiés dans l'année."""
    d = _d(ctx)
    b = k.baguage(d["bagues"], d["couples"], d["annee"], d["nomenc"])
    return AnalysisResult(
        texts={"TEXTE_BAGUAGE": b["texte"]},
        tables={
            "TABLE_BAGUAGE": _tableau(
                b["lignes"],
                [
                    ("dep", "Dép."),
                    ("commune", "Commune"),
                    ("lieu_dit", "Lieu-dit"),
                    ("bague", "Bague"),
                    ("type", "Type"),
                    ("date", "Date"),
                    ("age", "Âge"),
                    ("habitat", "Habitat"),
                ],
                vide="Aucune bague enregistrée pour cette année.",
            )
        },
    )


# ---------------------------------------------------------------------------------------- urbanisme, mesures
@register_brick("plsoc_urbanisme", requires=["plsoc_socle"], provides=["TEXTE_URBANISME", "TABLE_URBANISME"])
def plsoc_urbanisme(ctx):
    """Sites occupés depuis le début du suivi en zone U / AU des documents d'urbanisme."""
    d = _d(ctx)
    u = k.urbanisme(d["habitat"], d["debut"], d["annee"])
    return AnalysisResult(
        texts={"TEXTE_URBANISME": u["texte"]},
        tables={
            "TABLE_URBANISME": _tableau(
                u["lignes"],
                [
                    ("collectivite", "Collectivité"),
                    ("zonage", "Zonage"),
                    ("couples", "Couples (années)"),
                    ("parcelles", "Parcelles"),
                    ("surface", "Surface (ha)"),
                    ("periode", "Période"),
                ],
            )
        },
    )


COLONNES_MESURES = [
    ("projet", "Projet"),
    ("commune", "Commune"),
    ("mise_en_place", "Mise en place"),
    ("parcelles", "Parcelles"),
    ("couples", "Couples"),
    ("nids", "Nids"),
    ("succes", "Meilleur succès"),
    ("jeunes", "Jeunes à l'envol"),
    ("derniere", "Dernière reproduction"),
]


@register_brick(
    "plsoc_mesures", requires=["plsoc_socle"], provides=["TEXTE_MESURES", "TABLE_MESURES", "FICHES_MESURES"]
)
def plsoc_mesures(ctx):
    """Mesures compensatoires : synthèse, puis une fiche par projet (synthèse, carte, passages, suivis, historique)."""
    d = _d(ctx)
    a = d["annee"]
    m = k.mesures_compensatoires(
        d["mesures"],
        d["couples"],
        d["nids"],
        d["evenements"],
        d["suivis_mesure"],
        a,
        d["nomenc"],
        d["nomenc"].get("ref_statut_evenement", {}),
    )
    geoms = {x["id_site"]: x["wkt"] for x in d["mesures"]}
    blocs = []
    for i, f in enumerate(m["fiches"], 1):
        blocs += [
            ("titre", 3, f["nom"]),
            (
                "tableau",
                [{"cle": c, "valeur": v} for c, v in f["synthese"]],
                [("cle", "Synthèse"), ("valeur", "")],
                [60, 100],
            ),
        ]
        path = fig.carte(
            ctx.output_dirs["maps"] / f"mesure_{i:02d}.png",
            d["zone"]["wkt"],
            d["communes"],
            [],
            [x for x in d["mesures"] if x["id_site"] in f["sites"]],
            k.de_annee(d["couples"], a),
            titre_legende=f"Couples {a}",
            emprise=fig.emprise_autour([geoms[s] for s in f["sites"]], minimum=1200),
        )
        blocs += [
            ("image", path, 120),
            ("legende", f"Carte : mesure {f['nom']} et couples {a}."),
            ("titre", 4, f"Résultats {a}"),
            (
                "tableau",
                f["passages"],
                [("date", "Date"), ("evenement", "Observation / événement"), ("nombre", "Nombre")],
                [30, 100, 25],
            ),
            ("legende", f"Tableau : observations et événements de nid enregistrés sur la mesure en {a}."),
        ]
        if f["suivis"]:
            blocs += [
                (
                    "tableau",
                    f["suivis"],
                    [
                        ("date", "Date"),
                        ("galets", "Galets"),
                        ("herbes", "Herbacées"),
                        ("ligneux", "Ligneux"),
                        ("frequentation", "Fréquentation"),
                        ("dechets", "Déchets"),
                        ("bilan", "Bilan"),
                    ],
                ),
                ("legende", f"Tableau : suivis de l'état de la mesure en {a} (recouvrements)."),
            ]
        blocs += [
            ("a_rediger", f"[Résultats {a} de la mesure : commentaire à rédiger.]"),
            ("titre", 4, "Historique"),
            (
                "tableau",
                f["historique"],
                [
                    ("annee", "Année"),
                    ("presence", "Présence de couples"),
                    ("reproduction", "Reproduction"),
                    ("succes", "Succès"),
                    ("jeunes", "Jeunes à l'envol"),
                ],
            ),
            ("titre", 4, "Préconisations et bilan"),
            ("a_rediger", "[Préconisations de gestion et bilan de la mesure à rédiger.]"),
        ]
    return AnalysisResult(
        texts={"TEXTE_MESURES": m["texte"]},
        tables={
            "TABLE_MESURES": _tableau(
                m["synthese"], COLONNES_MESURES, vide="Aucune mesure compensatoire dans l'emprise du rapport."
            ),
            "FICHES_MESURES": TableBlock(blocs, inserer_blocs),
        },
    )


# --------------------------------------------------------------------------------------------- bilan, annexe
@register_brick(
    "plsoc_bilan",
    requires=["plsoc_socle", "plsoc_resultats", "plsoc_succes", "plsoc_rassemblements", "plsoc_mesures"],
    provides=["TEXTE_BILAN", "TABLE_ANOMALIES"],
)
def plsoc_bilan(ctx):
    """Bilan pré-rédigé de la saison et détail des anomalies de saisie (annexe)."""
    d = _d(ctx)
    a = d["annee"]
    su = k.succes(d["nids"], a, d["nomenc"])
    ra = k.rassemblements(d["rassemblements"], a)
    me = k.mesures_compensatoires(
        d["mesures"],
        d["couples"],
        d["nids"],
        d["evenements"],
        d["suivis_mesure"],
        a,
        d["nomenc"],
        d["nomenc"].get("ref_statut_evenement", {}),
    )
    return AnalysisResult(
        texts={"TEXTE_BILAN": k.texte_bilan(d["serie"], a, su, ra, me)},
        tables={
            "TABLE_ANOMALIES": _tableau(
                d["anomalies"],
                [("gravite", "Gravité"), ("code_anomalie", "Anomalie"), ("nb", "Nombre")],
                [35, 90, 25],
                vide="Aucune anomalie de saisie pour cette année.",
            )
        },
    )
