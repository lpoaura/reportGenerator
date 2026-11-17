"""Briques du rapport Indicateurs de biodiversité (dossier indicateurs).

ind_socle fixe l'emprise et l'année ; une brique par protocole (stoc, shoc, stom, sterf, pop_reptile, pop_amphibien)
charge son jeu (modèle commun) et remplit sa section {{#code}} … {{/code}} avec les mêmes placeholders préfixés
(STOC_…, SHOC_…). Les analyses propres à un protocole sont des blocs (SPECIFIQUES, analysis/indicateurs/specifiques.py).
"""

from datetime import date
from pathlib import Path
from typing import Callable

from reportgenerator.analysis.cartography.export import copy_qgis_project, export_gpkg
from reportgenerator.analysis.cartography.qgis_launcher import launch_qgis_render
from reportgenerator.analysis.common.models import AnalysisResult, ImageBlock, TableBlock
from reportgenerator.analysis.indicateurs import cartes, chargement
from reportgenerator.analysis.indicateurs import communes as k
from reportgenerator.analysis.indicateurs import figures as fig
from reportgenerator.analysis.indicateurs import specifiques as sp
from reportgenerator.analysis.indicateurs import textes as tx
from reportgenerator.analysis.indicateurs.modele import Jeu
from reportgenerator.analysis.indicateurs.queries import IndicateursQueries
from reportgenerator.analysis.indicateurs.selections import PREFIXES, PROTOCOLES, annee_par_defaut, libelle_saison
from reportgenerator.analysis.plsoc.word import inserer_blocs, inserer_tableau
from reportgenerator.bricks.common import qgis_layout_names
from reportgenerator.core.registry import register_brick

CLES = ("ANNEE_LIBELLE", "TEXTE_PARTICIPATION", "TABLE_CHIFFRES", "TABLE_CATEGORIES", "NOTE_CATEGORIES",
        "TEXTE_COUVERTURE", "TABLE_COUVERTURE", "TABLE_COUVERTURE_ZBIOG", "TEXTE_HISTORIQUE", "CHART_AIRES",
        "CHART_OBSERVATEURS", "TABLE_HISTORIQUE", "TEXTE_FIDELISATION", "TEXTE_ESPECES", "TABLE_ESPECES",
        "TABLE_EVOLUTION_ESPECES", "BLOCS_SPECIFIQUES")
# la carte {PREFIXE}_CARTE est une mise en page du projet QGIS (brique ind_cartes)

# analyses propres à un protocole : code -> fonction(ctx, jeu, saison, regle) -> blocs (inserer_blocs)
SPECIFIQUES: dict[str, Callable] = {}

NOTE_STATUT = ("Catégorie des observateurs : statut actuel du compte GeoNature retrouvé par l'adresse Faune-France, "
               "appliqué à toutes les années (un changement de statut crée un nouveau compte).")


def cles_protocole(code: str) -> list[str]:
    return [f"{PREFIXES[code]}_{c}" for c in CLES]


def _socle(ctx) -> dict:
    return ctx.results["ind_socle"].data


def regle(ctx, code: str) -> dict:
    return ctx.params["protocoles"][code]


def jeu_protocole(ctx, code: str) -> Jeu:
    """Jeu du protocole pour l'emprise du rapport, chargé une seule fois par rapport."""
    s = _socle(ctx)
    return ctx.cached(f"ind_jeu_{code}", lambda: chargement.charger(
        code, s["q"], regle(ctx, code), s["annee"], int(ctx.params.get("annees_especes", 5))))


def tableau(data, colonnes, largeurs=None, vide="Aucune donnée pour cette saison.") -> TableBlock:
    return TableBlock(data, inserer_tableau, {"colonnes": colonnes, "largeurs_mm": largeurs, "vide": vide})


def blocs(liste) -> TableBlock:
    return TableBlock(liste, inserer_blocs)


# ----------------------------------------------------------------------------------------------------- socle
@register_brick("ind_socle", provides=["AREA_NAME", "TITRE_RAPPORT", "ANNEE", "DATE_EXTRACTION", "TEXTE_ZONE"])
def ind_socle(ctx):
    """Emprise du rapport (zone de la demande), départements et zones biogéographiques, année du rapport."""
    p = ctx.params
    q = IndicateursQueries(ctx.service_name, ctx.id_area)
    annee = int(p.get("annee") or annee_par_defaut(date.today(), p.get("fin_saison", "10-01")))
    zone, departements, zbiog = q.zone(), q.departements(), q.zones_biogeo()
    noms = ", ".join(d["nom"] for d in departements)
    surface_km2 = float(zone["surface_ha"] or 0) / 100
    texte_zone = (f"Zone du rapport : {ctx.area_name} ({tx.nombre(round(surface_km2))} km²), "
                  f"{len(departements)} département{'s' if len(departements) > 1 else ''} ({noms}).")
    print(f"[indicateurs] année {annee}, zone {ctx.area_name} : {len(departements)} départements, "
          f"{len(zbiog)} zones biogéographiques")
    return AnalysisResult(
        data={"annee": annee, "zone": zone, "departements": departements, "zbiog": zbiog,
              "par_departement": len(departements) >= 2, "par_zbiog": len(zbiog) >= 2, "q": q},
        texts={"AREA_NAME": ctx.area_name, "TITRE_RAPPORT": p.get("titre", ""), "ANNEE": str(annee),
               "DATE_EXTRACTION": date.today().strftime("%d/%m/%Y"), "TEXTE_ZONE": texte_zone},
    )


# ------------------------------------------------------------------------------------------- section protocole
def _pct(v) -> str:
    return "—" if v is None else f"{v} %"


def _table_chiffres(r, c, c1):
    def ligne(lib, cle, fmt=tx.nombre):
        n1 = c1[cle] if c1 else None
        return {"indicateur": lib, "n1": fmt(n1) if c1 else "—", "n": fmt(c[cle]), "ecart": tx.ecart(c[cle], n1)}

    aire, unite = r["aire"], r["unite"]
    return [
        ligne(f"{tx.pluriel(aire)} {'suivies' if tx.feminin(aire) else 'suivis'}".capitalize(), "aires"),
        ligne(f"{tx.pluriel(unite)} {'visitées' if tx.feminin(unite) else 'visités'}".capitalize(), "unites"),
        ligne("Visites (aire × date)", "visites"),
        ligne("Observateurs", "observateurs"),
        ligne("Données", "donnees"),
        ligne("Espèces", "especes"),
        ligne("Temps (h)" + (" estimé" if c["heures_estimees"] else ""), "heures", lambda h: tx.nombre(
            None if h is None else round(h))),
    ]


def section_protocole(ctx, code: str) -> AnalysisResult:
    r, s, p = regle(ctx, code), _socle(ctx), ctx.params
    saison, cles = s["annee"], cles_protocole(code)
    jeu = jeu_protocole(ctx, code)
    if jeu.passages.empty:   # aucun passage du protocole dans la zone : section masquée
        print(f"[indicateurs] {code} : aucune aire dans la zone, section masquée")
        return AnalysisResult(data={"jeu": jeu, "saison": saison, "vide": True}, meta={"sans_section": True},
                              texts={cle: "" for cle in cles})
    P, temps, aire = PREFIXES[code], r.get("temps", {}), r["aire"]
    libelle = libelle_saison(saison, r["saison"])
    debut = max(int(r["debut_serie"]), int(jeu.passages["saison"].min()))
    c = k.chiffres(jeu, saison, temps)
    c1 = k.chiffres(jeu, saison - 1, temps) if (jeu.passages["saison"] == saison - 1).any() else None
    fid = k.fidelisation(jeu, saison)
    serie = k.serie(jeu, debut, saison, temps)
    debut_obs = max(int(r.get("debut_observateurs", debut)), debut)
    series_cat = k.series_categories(jeu, debut_obs, saison)
    esp = k.especes(jeu, saison, int(p.get("nb_especes", 20)))
    evo = k.evolution_especes(jeu, saison, int(p.get("nb_especes_evolution", 10)), int(p.get("annees_especes", 5)))
    out = ctx.output_dirs["dataviz"]
    chart_aires = fig.chart_aires(serie, out / f"{code}_aires.png", aire)
    chart_obs = fig.chart_observateurs(series_cat, out / f"{code}_observateurs.png")

    # tableaux
    par = "departement" if s["par_departement"] else "aire"
    couv = k.couverture(jeu, saison, r, par)
    cols_couv = ([("departement", "Département"), ("aires", tx.pluriel(aire).capitalize()),
                  ("unites", tx.pluriel(r["unite"]).capitalize()), ("visites", "Visites"),
                  ("observateurs", "Observateurs"), ("donnees", "Données"), ("nouvelles", "Nouveaux"),
                  ("completes", "Complets")] if par == "departement" else
                 [("aire", aire.capitalize()), ("commune", "Commune"), ("unites", tx.pluriel(r["unite"]).capitalize()),
                  ("visites", "Visites"), ("observateurs", "Observateurs"), ("completude", "Passages")])
    tables = {
        f"{P}_TABLE_CHIFFRES": tableau(_table_chiffres(r, c, c1), [
            ("indicateur", "Indicateur"), ("n1", "Saison précédente"), ("n", libelle), ("ecart", "Écart")]),
        f"{P}_TABLE_CATEGORIES": tableau([{**x, "heures": tx.nombre(round(x["heures"]))}
                                          for x in k.par_categorie(jeu, saison, temps)], [
            ("categorie", "Catégorie"), ("aires", tx.pluriel(aire).capitalize()), ("observateurs", "Observateurs"),
            ("donnees", "Données"), ("heures", "Temps (h)")]),
        f"{P}_TABLE_COUVERTURE": tableau(couv, cols_couv),
        f"{P}_TABLE_HISTORIQUE": tableau([
            {"saison": libelle_saison(x["saison"], r["saison"]), "aires": x["aires"], "unites": x["unites"],
             "observateurs": x["observateurs"] if x["saison"] >= debut_obs else "—", "donnees": tx.nombre(x["donnees"]),
             "heures": tx.nombre(round(x["heures"]))}
            for x in serie[-int(p.get("annees_tableau", 5)):]], [
            ("saison", "Saison"), ("aires", tx.pluriel(aire).capitalize()),
            ("unites", tx.pluriel(r["unite"]).capitalize()), ("observateurs", "Observateurs"),
            ("donnees", "Données"), ("heures", "Temps (h)")]),
        f"{P}_TABLE_ESPECES": tableau([{**e, "freq_aires": _pct(e["freq_aires"]), "freq_unites": _pct(
            e["freq_unites"]), "effectif": tx.nombre(e["effectif"])} for e in esp], [
            ("rang", "Rang"), ("nom", "Espèce"), ("freq_aires", f"% des {tx.pluriel(aire)}"),
            ("freq_unites", f"% des {tx.pluriel(r['unite'])}"), ("effectif", "Effectif cumulé")]),
        f"{P}_TABLE_EVOLUTION_ESPECES": tableau(
            [{cle: (_pct(v) if cle != "nom" else v) for cle, v in e.items()} for e in evo],
            [("nom", "Espèce")] + [(a, libelle_saison(a, r["saison"])) for a in (evo[0] if evo else {}) if a != "nom"]),
        f"{P}_BLOCS_SPECIFIQUES": blocs(SPECIFIQUES[code](ctx, jeu, saison, r) if code in SPECIFIQUES else []),
    }
    texts = {
        f"{P}_ANNEE_LIBELLE": libelle,
        f"{P}_TEXTE_PARTICIPATION": tx.texte_participation(
            r["label"], aire, libelle, c, c1, tx.note_temps(temps, c["heures_estimees"], aire)),
        f"{P}_NOTE_CATEGORIES": NOTE_STATUT if r.get("note_statut") else "",
        f"{P}_TEXTE_COUVERTURE": tx.texte_couverture(
            aire, c, fid, s["par_departement"],
            len({x["departement"] for x in couv if not x.get("total")}) if par == "departement" else 1),
        f"{P}_TEXTE_HISTORIQUE": _texte_historique(r, serie, debut, debut_obs),
        f"{P}_TEXTE_FIDELISATION": tx.texte_fidelisation(aire, fid) if c["aires"] else "",
        f"{P}_TEXTE_ESPECES": tx.texte_especes(c, esp, aire) if c["aires"] else "",
    }
    if s["par_zbiog"]:
        tables[f"{P}_TABLE_COUVERTURE_ZBIOG"] = tableau(k.couverture(jeu, saison, r, "zbiog"), [
            ("zbiog", "Zone biogéographique")] + cols_couv[1:6])
    else:
        texts[f"{P}_TABLE_COUVERTURE_ZBIOG"] = ""
    print(f"[indicateurs] {code} {libelle} : {c['aires']} {tx.pluriel(aire)}, {c['observateurs']} observateurs, "
          f"{c['donnees']} données")
    return AnalysisResult(
        data={"jeu": jeu, "saison": saison, "libelle": libelle, "chiffres": c, "precedent": c1, "fidelisation": fid,
              "especes": esp, "vide": False, "regle": r},
        texts=texts, tables=tables,
        images={f"{P}_CHART_AIRES": ImageBlock(chart_aires), f"{P}_CHART_OBSERVATEURS": ImageBlock(chart_obs)},
    )


def _texte_historique(r, serie, debut, debut_obs) -> str:
    aire = r["aire"]
    valeurs = [x["aires"] for x in serie]
    t = (f"Depuis {libelle_saison(debut, r['saison'])}, le nombre de {tx.pluriel(aire)} "
         f"{'suivies' if tx.feminin(aire) else 'suivis'} par saison varie de {min(valeurs)} à {max(valeurs)}.")
    if debut_obs > debut:
        t += f" Les observateurs ne sont comptés qu'à partir de {debut_obs} (champ peu fiable auparavant)."
    return t


# ------------------------------------------------------------------------------------------------------ synthèse
def _sections(ctx) -> list[tuple[str, dict]]:
    """(code, data) des protocoles exécutés qui ont des aires dans la zone, dans l'ordre du rapport."""
    return [(c, ctx.results[c].data) for c in PROTOCOLES if c in ctx.results and not ctx.results[c].data["vide"]]


def _heures(c) -> str:
    return f"{tx.nombre(round(c['heures']))} h" + (" (estimé)" if c["heures_estimees"] else "")


@register_brick(
    "ind_synthese",
    requires=["ind_socle"],
    provides=["TABLE_CHIFFRES_CLES", "TEXTE_CHIFFRES_CLES", "TEXTE_CONCLUSION", "BLOCS_ANNEXE_ESPECES",
              "BLOCS_ANNEXE_CONTROLE"],
    last=True,
)
def ind_synthese(ctx):
    """Chiffres clés de tous les protocoles (page de garde), conclusion pré-rédigée, annexes."""
    annee, sections = _socle(ctx)["annee"], _sections(ctx)
    lignes, phrases, annexe_esp, controle = [], [], [], []
    for code, d in sections:
        r, c, c1 = d["regle"], d["chiffres"], d["precedent"]
        lignes.append({"protocole": r["label"], "saison": d["libelle"], "aires": f"{tx.nombre(c['aires'])} "
                       f"{tx.pluriel(r['aire'], c['aires'])}", "observateurs": tx.nombre(c["observateurs"]),
                       "donnees": tx.nombre(c["donnees"]), "temps": _heures(c),
                       "ecart": tx.ecart(c["aires"], c1["aires"] if c1 else None)})
        phrases.append(f"{r['label']} ({d['libelle']}) : {tx.nombre(c['aires'])} {tx.pluriel(r['aire'], c['aires'])} "
                       f"(écart avec la saison précédente : {tx.ecart(c['aires'], c1['aires'] if c1 else None)}), "
                       f"{tx.nombre(c['observateurs'])} observateurs, {tx.nombre(c['donnees'])} données.")
        especes = k.especes(d["jeu"], d["saison"], None)
        annexe_esp += [("titre", 2, f"{r['label']} - {d['libelle']}"),
                       ("tableau", [{**e, "freq_aires": _pct(e["freq_aires"]), "effectif": tx.nombre(e["effectif"])}
                                    for e in especes],
                        [("rang", "Rang"), ("nom", "Espèce"), ("freq_aires", f"% des {tx.pluriel(r['aire'])}"),
                         ("effectif", "Effectif cumulé")])]
        anomalies = [{**a, "date": a["date"].strftime("%d/%m/%Y") if a.get("date") else "", "nom": a.get("nom") or ""}
                     for a in d["jeu"].anomalies if a.get("saison") in (None, d["saison"])]
        if anomalies:
            controle += [("titre", 2, r["label"]),
                         ("tableau", anomalies, [("code", "Code"), ("libelle", "Anomalie"), ("aire", "Aire"),
                                                 ("unite", "Unité"), ("date", "Date"), ("nom", "Observateur")])]
    jeux = {code: d["jeu"] for code, d in sections}
    multi = k.observateurs_multi_protocoles(jeux, {code: d["saison"] for code, d in sections})
    total_donnees = sum(d["chiffres"]["donnees"] for _, d in sections)
    total_heures = sum(d["chiffres"]["heures"] for _, d in sections)
    texte = (f"En {annee}, {len(sections)} protocole{'s' if len(sections) > 1 else ''} de suivi "
             f"{'ont' if len(sections) > 1 else 'a'} produit {tx.nombre(total_donnees)} données dans la zone, pour "
             f"environ {tx.nombre(round(total_heures))} heures de travail (mesurées ou estimées). "
             f"{tx.nombre(multi)} observateurs (comptes) ont participé à au moins deux protocoles."
             if sections else f"Aucun protocole n'a d'aire suivie dans la zone en {annee}.")
    if not controle:
        controle = [("texte", "Aucune anomalie de saisie relevée.")]
    return AnalysisResult(
        texts={"TEXTE_CHIFFRES_CLES": texte, "TEXTE_CONCLUSION": " ".join(phrases) or texte},
        tables={
            "TABLE_CHIFFRES_CLES": tableau(lignes, [("protocole", "Protocole"), ("saison", "Saison"),
                                                    ("aires", "Aires suivies"), ("observateurs", "Observateurs"),
                                                    ("donnees", "Données"), ("temps", "Temps"),
                                                    ("ecart", "Écart des aires")]),
            "BLOCS_ANNEXE_ESPECES": blocs(annexe_esp),
            "BLOCS_ANNEXE_CONTROLE": blocs([("a_rediger", "Annexe de contrôle : à supprimer avant envoi.")]
                                           + controle),
        },
    )


# -------------------------------------------------------------------------------------------------------- cartes
@register_brick("ind_cartes", requires=["ind_socle"], provides=lambda d: qgis_layout_names(d.qgis_project),
                last=True)
def ind_cartes(ctx):
    """Cartes QGIS : couches GPKG (aires par statut, départements, zones biogéographiques) puis une image par mise en
    page du projet du dossier ({PREFIXE}_CARTE)."""
    s, data_dir = _socle(ctx), ctx.output_dirs["data"]
    sections = _sections(ctx)
    couches = cartes.couches_cartes({c: d["jeu"] for c, d in sections}, {c: d["saison"] for c, d in sections},
                                    {**s["zone"], "nom": ctx.area_name}, s["departements"], s["zbiog"])
    for nom, lignes in couches.items():
        export_gpkg(lignes, data_dir, layer_name=nom, geom_col="geom", crs="EPSG:2154")
    projet = ctx.dossier.qgis_project
    if not projet or not Path(projet).exists():
        print(f"[AVERTISSEMENT] Projet QGIS absent ({projet}) : couches exportées dans {data_dir}, pas de carte")
        return AnalysisResult()
    copie = ctx.output_dirs["root"] / f"projet_{ctx.area_name}.qgs"
    copy_qgis_project(template_path=projet, output_path=copie)
    # titres des cartes : @annee_<PREFIXE> (« 2024-2025 » pour le SHOC), @zone ; texte « Sources » : @sources
    variables = {f"annee_{PREFIXES[c]}": libelle_saison(s["annee"], regle(ctx, c)["saison"]) for c in PROTOCOLES}
    variables.update({"zone": ctx.area_name,
                      "sources": "Faune-France (STOC, SHOC) et GeoNature (STOM, STERF, POP), LPO Auvergne-Rhône-Alpes"})
    config = {**ctx.params.get("qgis_render", {}), "project_variables": variables}
    launch_qgis_render(project_path=copie, output_dir=ctx.output_dirs["maps"], config=config)
    layout = ctx.params.get("map_layout", "normal")
    return AnalysisResult(images={png.stem: ImageBlock(png, layout)
                                  for png in sorted(ctx.output_dirs["maps"].glob("*.png"))})


# ------------------------------------------------------------------------------ analyses propres à un protocole
def _stoc(ctx, jeu, saison, r):
    s = _socle(ctx)
    sites = ctx.cached("ind_jeu_stoc_sites", lambda: chargement.charger_stoc_sites(
        s["q"], r, saison, int(ctx.params.get("annees_especes", 5))))
    return sp.blocs_stoc(jeu, sites, saison, r)


def _shoc(ctx, jeu, saison, r):
    return sp.blocs_shoc(jeu, jeu_protocole(ctx, "stoc"), saison)   # STOC chargé même s'il n'est pas demandé


SPECIFIQUES.update({
    "stoc": _stoc,
    "shoc": _shoc,
    "stom": lambda ctx, jeu, saison, r: sp.blocs_stom(jeu, saison, r),
    "sterf": lambda ctx, jeu, saison, r: sp.blocs_sterf(jeu, saison, r),
    "pop_reptile": lambda ctx, jeu, saison, r: sp.blocs_pop(jeu, saison, r),
    "pop_amphibien": lambda ctx, jeu, saison, r: sp.blocs_pop(jeu, saison, r),
})


def _brique(code: str):
    def run(ctx):
        return section_protocole(ctx, code)
    run.__doc__ = f"Section {PREFIXES[code]} du rapport Indicateurs de biodiversité."
    return run


for _code in PROTOCOLES:
    register_brick(_code, requires=["ind_socle"], provides=cles_protocole(_code))(_brique(_code))
