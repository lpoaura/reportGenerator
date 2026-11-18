"""Briques du rapport Indicateurs de biodiversité (dossier indicateurs).

ind_socle fixe l'emprise et l'année ; une brique par protocole (stoc, shoc, stom, sterf, pop_reptile, pop_amphibien)
charge son jeu (modèle commun) et remplit sa section {{#code}} … {{/code}} avec les mêmes placeholders préfixés
(STOC_…, SHOC_…). Les analyses propres à un protocole sont des blocs (SPECIFIQUES, analysis/indicateurs/specifiques.py).
"""

from collections import Counter
from datetime import date
from pathlib import Path
from typing import Callable

from reportgenerator.analysis.cartography.export import copy_qgis_project, export_gpkg
from reportgenerator.analysis.cartography.qgis_launcher import launch_qgis_render
from reportgenerator.analysis.common.models import AnalysisResult, ImageBlock, TableBlock
from reportgenerator.analysis.indicateurs import cartes, chargement
from reportgenerator.analysis.indicateurs import communes as k
from reportgenerator.analysis.indicateurs import figures as fig
from reportgenerator.analysis.indicateurs import participants as pt
from reportgenerator.analysis.indicateurs import specifiques as sp
from reportgenerator.analysis.indicateurs import textes as tx
from reportgenerator.analysis.indicateurs.modele import Jeu
from reportgenerator.analysis.indicateurs.queries import IndicateursQueries
from reportgenerator.analysis.indicateurs.selections import PREFIXES, PROTOCOLES, annee_par_defaut, libelle_saison
from reportgenerator.analysis.plsoc.word import inserer_blocs, inserer_tableau
from reportgenerator.bricks.common import qgis_layout_names
from reportgenerator.core.registry import register_brick

CLES = ("ANNEE_LIBELLE", "TEXTE_PARTICIPATION", "CHART_CHIFFRES", "CHART_CATEGORIES", "NOTE_CATEGORIES",
        "BLOCS_ORGANISMES", "TEXTE_COUVERTURE", "BLOCS_COUVERTURE", "TEXTE_HISTORIQUE", "CHART_HISTORIQUE",
        "CHART_OBSERVATEURS", "TEXTE_FIDELISATION", "TEXTE_ESPECES", "CHART_ESPECES", "CHART_EVOLUTION_ESPECES",
        "TEXTE_BENEVOLES", "BLOCS_BENEVOLES", "BLOCS_SPECIFIQUES")
# les cartes {PREFIXE}_CARTE, _CARTE_CATEGORIES, _CARTE_ABANDONS sont des mises en page du projet QGIS (ind_cartes) ;
# les tableaux détaillés de chaque protocole vont en annexe (data["annexe"], repris par ind_synthese)

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
@register_brick("ind_socle", provides=["AREA_NAME", "TITRE_RAPPORT", "ANNEE", "DATE_EXTRACTION", "TEXTE_ZONE",
                                       "TEXTE_PROTOCOLES"])
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
    # rapport limité à certains protocoles (list_analyse) : titre complété, contexte réduit à ces protocoles
    regles = [p["protocoles"][c] for c in PROTOCOLES if ctx.is_enabled(c)]
    titre = p.get("titre", "")
    if titre and 0 < len(regles) < len(PROTOCOLES):
        titre = f"{titre} : {', '.join(r['label'] for r in regles)}"
    return AnalysisResult(
        data={"annee": annee, "zone": zone, "departements": departements, "zbiog": zbiog,
              "par_departement": len(departements) >= 2, "par_zbiog": len(zbiog) >= 2, "q": q},
        texts={"AREA_NAME": ctx.area_name, "TITRE_RAPPORT": titre, "ANNEE": str(annee),
               "DATE_EXTRACTION": date.today().strftime("%d/%m/%Y"), "TEXTE_ZONE": texte_zone,
               "TEXTE_PROTOCOLES": tx.texte_protocoles(regles)},
    )


# ------------------------------------------------------------------------------------------- section protocole
def _pct(v) -> str:
    return "—" if v is None else f"{v} %"


def _indicateurs(r, c):
    """(libellé, clé) des chiffres clés d'un protocole, dans l'ordre des tuiles et du tableau d'annexe."""
    aire, unite = r["aire"], r["unite"]
    return [
        (f"{tx.pluriel(aire)} {'suivies' if tx.feminin(aire) else 'suivis'}".capitalize(), "aires"),
        (f"{tx.pluriel(unite)} {'visitées' if tx.feminin(unite) else 'visités'}".capitalize(), "unites"),
        ("Observateurs", "observateurs"),
        ("Données", "donnees"),
        ("Espèces", "especes"),
        ("Temps (h)" + (", estimé" if c["heures_estimees"] else ""), "heures"),
    ]


def _fmt(cle):
    return (lambda h: tx.nombre(None if h is None else round(h))) if cle == "heures" else tx.nombre


def _table_chiffres(r, c, c1):
    return [{"indicateur": lib, "n1": _fmt(cle)(c1[cle]) if c1 else "—", "n": _fmt(cle)(c[cle]),
             "ecart": tx.ecart(c[cle], c1[cle] if c1 else None)}
            for lib, cle in _indicateurs(r, c) + [("Visites (aire × date)", "visites")]]


def _annexe(titre, lignes, colonnes) -> list[tuple]:
    return [("titre", 3, titre), ("tableau", lignes, colonnes)]


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
    lib_saison = lambda a: libelle_saison(a, r["saison"])  # noqa: E731
    aires_lib, unites_lib = tx.pluriel(aire).capitalize(), tx.pluriel(r["unite"]).capitalize()
    suivis = "suivies" if tx.feminin(aire) else "suivis"
    categories = k.par_categorie(jeu, saison, temps)
    organismes = k.par_organisme(jeu, saison)

    def valeur(chiffres, cle):   # heures arrondies : l'écart affiché porte sur les valeurs affichées
        v = chiffres[cle] if chiffres else None
        return round(v) if cle == "heures" and v is not None else v

    images = {
        f"{P}_CHART_CHIFFRES": fig.chart_chiffres(
            [(lib, valeur(c, cle), valeur(c1, cle)) for lib, cle in _indicateurs(r, c)],
            out / f"{code}_chiffres.png", libelle, lib_saison(saison - 1)),
        f"{P}_CHART_CATEGORIES": fig.chart_categories(categories, out / f"{code}_categories.png", tx.pluriel(aire)),
        f"{P}_CHART_HISTORIQUE": fig.chart_historique(serie, out / f"{code}_historique.png",
                                                      {"aires": f"{aires_lib} {suivis}", "saison": lib_saison},
                                                      debut_obs),
        f"{P}_CHART_OBSERVATEURS": fig.chart_observateurs(series_cat, out / f"{code}_observateurs.png"),
        f"{P}_CHART_ESPECES": fig.chart_especes(esp, out / f"{code}_especes.png", aire),
        f"{P}_CHART_EVOLUTION_ESPECES": fig.chart_evolution(evo, out / f"{code}_evolution.png", lib_saison),
    }

    # couverture : graphique par département (ou liste des aires si la zone n'a qu'un département) et par zone
    # biogéographique ; les tableaux détaillés vont en annexe
    par = "departement" if s["par_departement"] else "aire"
    couv = k.couverture(jeu, saison, r, par)
    cols_groupe = [("aires", aires_lib), ("unites", unites_lib), ("visites", "Visites"),
                   ("observateurs", "Observateurs"), ("donnees", "Données"), ("nouvelles", "Nouveaux"),
                   ("completes", "Complets")]
    series = [("anciennes", f"Déjà {suivis} avant {libelle}", fig.BLEU),
              ("nouvelles", f"{suivis.capitalize()} pour la première fois", fig.ORANGE)]
    annexe = _annexe("Chiffres clés", _table_chiffres(r, c, c1), [
        ("indicateur", "Indicateur"), ("n1", "Saison précédente"), ("n", libelle), ("ecart", "Écart")])
    annexe += _annexe("Répartition par catégorie d'observateurs",
                      [{**x, "heures": tx.nombre(round(x["heures"]))} for x in categories],
                      [("categorie", "Catégorie"), ("aires", aires_lib), ("observateurs", "Observateurs"),
                       ("donnees", "Données"), ("heures", "Temps (h)")])
    if organismes:
        n_max = 12
        blocs_org = [("image", fig.chart_organismes(organismes, out / f"{code}_organismes.png", aire, n_max)),
                     ("legende", f"Figure : organismes tiers ayant participé en {libelle} ({tx.pluriel(aire)} où "
                                 "l'un de leurs observateurs a fait au moins un relevé"
                                 + (f" ; les {n_max} premiers, liste complète en annexe)." if len(organismes) > n_max
                                    else ")."))]
        annexe += _annexe("Organismes tiers participants",
                          [{**x, "donnees": tx.nombre(x["donnees"])} for x in organismes],
                          [("organisme", "Organisme"), ("aires", aires_lib), ("observateurs", "Observateurs"),
                           ("donnees", "Données")])
    else:
        blocs_org = [("texte", f"Aucun organisme tiers n'a participé en {libelle}.")]
    if par == "departement":
        lignes = [{**x, "anciennes": x["aires"] - x["nouvelles"]} for x in couv]
        couverture = [("image", fig.chart_groupes(lignes, "departement", out / f"{code}_departements.png", series,
                                                  f"{aires_lib} {suivis}")),
                      ("legende", f"Figure : {tx.pluriel(aire)} {suivis} en {libelle} par département "
                                  "(détail en annexe).")]
        annexe += _annexe("Couverture par département", couv, [("departement", "Département")] + cols_groupe)
    else:
        couverture = [("tableau", couv, [("aire", aire.capitalize()), ("commune", "Commune"), ("unites", unites_lib),
                                         ("visites", "Visites"), ("observateurs", "Observateurs"),
                                         ("completude", "Passages")]),
                      ("legende", f"Tableau : {tx.pluriel(aire)} {suivis} en {libelle}.")]
    if s["par_zbiog"]:
        zones = k.couverture(jeu, saison, r, "zbiog")
        lignes = [{**x, "anciennes": x["aires"] - x["nouvelles"]} for x in zones]
        couverture += [("image", fig.chart_groupes(lignes, "zbiog", out / f"{code}_zbiog.png", series,
                                                   f"{aires_lib} {suivis}")),
                       ("legende", f"Figure : {tx.pluriel(aire)} {suivis} en {libelle} par zone biogéographique.")]
        annexe += _annexe("Couverture par zone biogéographique", zones,
                          [("zbiog", "Zone biogéographique")] + cols_groupe)
    annexe += _annexe("Chiffres des dernières saisons", [
        {"saison": lib_saison(x["saison"]), "aires": x["aires"], "unites": x["unites"],
         "observateurs": x["observateurs"] if x["saison"] >= debut_obs else "—", "donnees": tx.nombre(x["donnees"]),
         "heures": tx.nombre(round(x["heures"]))} for x in serie[-int(p.get("annees_tableau", 5)):]],
        [("saison", "Saison"), ("aires", aires_lib), ("unites", unites_lib), ("observateurs", "Observateurs"),
         ("donnees", "Données"), ("heures", "Temps (h)")])
    if evo:
        annexe += _annexe("Évolution de la fréquence des espèces",
                          [{cle: (_pct(v) if cle != "nom" else v) for cle, v in e.items()} for e in evo],
                          [("nom", "Espèce")] + [(a, lib_saison(a)) for a in evo[0] if a != "nom"])

    # observateurs connus après le début du protocole : leur première saison connue ne dit pas qui est nouveau
    debut_ben = debut_obs + 1 if debut_obs > debut else debut_obs
    texte_ben, blocs_ben, annexe_ben, travail_ben = _benevoles(ctx, code, jeu, saison, c1 is not None, debut_ben)
    annexe += annexe_ben

    # analyses propres : graphiques dans la section, tableaux (blocs « annexe ») en annexe
    propres = SPECIFIQUES[code](ctx, jeu, saison, r) if code in SPECIFIQUES else []
    for b in propres:
        if b[0] == "annexe":
            annexe += _annexe(b[1], b[2], b[3])
    tables = {
        f"{P}_BLOCS_COUVERTURE": blocs(couverture),
        f"{P}_BLOCS_ORGANISMES": blocs(blocs_org),
        f"{P}_BLOCS_BENEVOLES": blocs(blocs_ben),
        f"{P}_BLOCS_SPECIFIQUES": blocs([b for b in propres if b[0] != "annexe"]),
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
        f"{P}_TEXTE_BENEVOLES": texte_ben,
    }
    print(f"[indicateurs] {code} {libelle} : {c['aires']} {tx.pluriel(aire)}, {c['observateurs']} observateurs, "
          f"{c['donnees']} données")
    return AnalysisResult(
        data={"jeu": jeu, "saison": saison, "libelle": libelle, "chiffres": c, "precedent": c1, "fidelisation": fid,
              "especes": esp, "vide": False, "regle": r, "annexe": annexe, "organismes": organismes,
              "benevoles": travail_ben},
        texts=texts, tables=tables, images={cle: ImageBlock(chemin) for cle, chemin in images.items()},
    )


BENEVOLE = "Bénévole"


def _benevoles(ctx, code, jeu, saison, avec_precedent, debut_obs):
    """Sous-partie « Bénévoles » d'un protocole : (texte, blocs, annexe, travail). Chiffres agrégés seulement."""
    r, s, p = regle(ctx, code), _socle(ctx), ctx.params
    aire, temps, out = r["aire"], r.get("temps", {}), ctx.output_dirs["dataviz"]
    libelle = libelle_saison(saison, r["saison"])
    lib_saison = lambda a: libelle_saison(a, r["saison"])  # noqa: E731
    t = pt.travail(jeu, saison, BENEVOLE, temps)
    t1 = pt.travail(jeu, saison - 1, BENEVOLE, temps) if avec_precedent else None
    statuts = Counter(pt.statuts(jeu, saison, BENEVOLE).values())
    statuts1 = Counter(pt.statuts(jeu, saison - 1, BENEVOLE).values()) if avec_precedent else None
    texte = tx.texte_benevoles(r["label"], aire, libelle, t, t1, statuts, p.get("taux_horaire_benevolat", 0))
    aires_lib = tx.pluriel(aire).capitalize()
    blocs_ben, annexe = [], []
    if t["participants"]:
        def v(x, cle):
            return None if x is None else (round(x[cle]) if cle == "heures" else x[cle])
        tuiles = [("Bénévoles", t["participants"], v(t1, "participants")),
                  ("Nouveaux bénévoles", statuts["nouveau"], statuts1["nouveau"] if statuts1 is not None else None),
                  (f"{aires_lib} des bénévoles", t["aires"], v(t1, "aires")),
                  ("Relevés", t["releves"], v(t1, "releves")), ("Données", t["donnees"], v(t1, "donnees")),
                  ("Temps (h)" + (", estimé" if t["heures_estimees"] else ""), v(t, "heures"), v(t1, "heures"))]
        serie = pt.serie_statuts(jeu, debut_obs, saison, BENEVOLE)
        anc, eng = pt.anciennete(jeu, saison, BENEVOLE), pt.engagement(jeu, saison, BENEVOLE)
        blocs_ben += [
            ("image", fig.chart_chiffres(tuiles, out / f"{code}_benevoles_chiffres.png", libelle,
                                         lib_saison(saison - 1))),
            ("legende", f"Figure : chiffres clés des bénévoles, saison {libelle} ({tx.pluriel(aire)} attribuées à "
                        "leur observateur principal, relevés selon la catégorie prioritaire de leurs observateurs)."
             if tx.feminin(aire) else
             f"Figure : chiffres clés des bénévoles, saison {libelle} ({tx.pluriel(aire)} attribués à leur "
             "observateur principal, relevés selon la catégorie prioritaire de leurs observateurs)."),
            ("image", fig.chart_renouvellement(serie, out / f"{code}_benevoles_renouvellement.png", lib_saison)),
            ("legende", "Figure : bénévoles par saison : fidèles (présents la saison précédente), revenants (après "
                        "une interruption), nouveaux ; sous l'axe, bénévoles de la saison précédente qui n'ont pas "
                        "reconduit leur suivi."),
        ]
        annexe += _annexe("Bénévoles : renouvellement par saison",
                          [{**x, "saison": lib_saison(x["saison"])} for x in serie],
                          [("saison", "Saison"), ("fidèle", "Fidèles"), ("revenant", "Revenants"),
                           ("nouveau", "Nouveaux"), ("parti", "Partis")])
        if s["par_departement"]:
            deps = pt.statuts_par_departement(jeu, saison, BENEVOLE)
            blocs_ben += [
                ("image", fig.chart_statuts_departements(deps, out / f"{code}_benevoles_departements.png")),
                ("legende", f"Figure : bénévoles par département en {libelle} (un bénévole compte dans chaque "
                            f"département où il a fait un relevé ; partis : départements de la saison précédente)."),
            ]
            annexe += _annexe("Bénévoles par département", deps,
                              [("departement", "Département"), ("total", "Bénévoles"), ("fidèle", "Fidèles"),
                               ("revenant", "Revenants"), ("nouveau", "Nouveaux"), ("parti", "Partis")])
        blocs_ben += [
            ("image", fig.chart_anciennete_engagement(anc, eng, out / f"{code}_benevoles_anciennete.png", aire)),
            ("legende", f"Figure : bénévoles de {libelle} selon le nombre de saisons de participation au protocole et "
                        f"le nombre de {tx.pluriel(aire)} {'suivies' if tx.feminin(aire) else 'suivis'} dans la "
                        "saison."),
        ]
        annexe += _annexe("Bénévoles : ancienneté et engagement",
                          [{"critere": "Ancienneté", "tranche": k_, "benevoles": n} for k_, n in anc.items()]
                          + [{"critere": f"{aires_lib} {'suivies' if tx.feminin(aire) else 'suivis'}",
                              "tranche": k_.replace("+", " et plus"), "benevoles": n} for k_, n in eng.items()],
                          [("critere", "Critère"), ("tranche", "Tranche"), ("benevoles", "Bénévoles")])
    if r["source"] == "monitoring":
        jamais = pt.aires_jamais_visitees(jeu, s["q"].createurs_aires_monitoring(r["module"]))
        n = sum(x["aires"] for x in jamais)
        nb = sum(x["aires"] for x in jamais if x["categorie"] == BENEVOLE)
        ces = tx.pluriel(aire, n)
        blocs_ben.append(("texte", (
            f"{tx.nombre(n)} {ces} de la zone {'ont' if n > 1 else 'a'} été {'créées' if tx.feminin(aire) else 'créés'}"
            f" dans le module sans jamais être {'visitées' if tx.feminin(aire) else 'visités'}"
            f", dont {tx.nombre(nb)} par un bénévole (détail en annexe) : suivis envisagés mais non concrétisés, à "
            "relancer ou à retirer du module.") if n else
            f"Toutes les {tx.pluriel(aire)} du module dans la zone ont été visitées au moins une fois."
            if tx.feminin(aire) else
            f"Tous les {tx.pluriel(aire)} du module dans la zone ont été visités au moins une fois."))
        if jamais:
            annexe += _annexe(f"{aires_lib} créées jamais visitées" if tx.feminin(aire)
                              else f"{aires_lib} créés jamais visités",
                              [{**x, "annee_creation": x["annee_creation"] or "—"} for x in jamais],
                              [("annee_creation", "Année de création"), ("categorie", "Créateur"),
                               ("aires", aires_lib)])
    return texte, blocs_ben, annexe, t


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


def _organismes(sections) -> list[tuple]:
    """Organismes tiers × protocoles : « n aires · n obs. » par protocole ; tri par nombre de protocoles puis
    d'observateurs."""
    par_org: dict[str, dict] = {}
    for code, d in sections:
        for x in d["organismes"]:
            par_org.setdefault(x["organisme"], {})[code] = x
    if not par_org:
        return [("texte", "Aucun organisme tiers n'a participé aux protocoles dans la zone.")]
    ordre = sorted(par_org, key=lambda o: (-len(par_org[o]), -sum(x["observateurs"] for x in par_org[o].values()), o))
    lignes = []
    for o in ordre:
        ligne = {"organisme": o}
        for code, d in sections:
            x, aire = par_org[o].get(code), d["regle"]["aire"]
            ligne[code] = f"{x['aires']} {tx.pluriel(aire, x['aires'])} · {x['observateurs']} obs." if x else "—"
        lignes.append(ligne)
    return [("tableau", lignes, [("organisme", "Organisme")] + [(c, d["regle"]["label"]) for c, d in sections])]


def _reseau(ctx, annee, sections):
    """Partie « Le réseau bénévole » : (texte, blocs, annexe), tous protocoles du rapport, comptes GeoNature."""
    p, out = ctx.params, ctx.output_dirs["dataviz"]
    jeux = {code: d["jeu"] for code, d in sections}
    saisons = {code: d["saison"] for code, d in sections}
    labels = {code: d["regle"]["label"] for code, d in sections}
    res = pt.reseau(jeux, saisons, BENEVOLE)
    res1 = pt.reseau(jeux, {c: s - 1 for c, s in saisons.items()}, BENEVOLE) \
        if any(d["precedent"] for _, d in sections) else None
    heures = sum(d["benevoles"]["heures"] for _, d in sections)
    texte = tx.texte_reseau(annee, res, res1, heures, p.get("taux_horaire_benevolat", 0))
    if not res["participants"]:
        return texte, [], []
    serie = pt.serie_reseau(jeux, annee - int(p.get("annees_reseau", 10)) + 1, annee, BENEVOLE)
    blocs_r = [("image", fig.chart_reseau(serie, out / "reseau_benevoles.png", str)),
               ("legende", "Figure : bénévoles distincts (comptes GeoNature) ayant participé à au moins un protocole "
                           "du rapport, par saison (saison d'hiver du SHOC comptée avec l'année de janvier).")]
    annexe = _annexe("Bénévoles distincts par saison", serie, [("saison", "Saison"), ("participants", "Bénévoles")])
    if res["combinaisons"]:
        combis = [{"protocoles": " + ".join(labels[c] for c in codes), "benevoles": n}
                  for codes, n in res["combinaisons"]]
        blocs_r += [("image", fig.chart_combinaisons(res["combinaisons"], out / "reseau_combinaisons.png", labels)),
                    ("legende", f"Figure : bénévoles participant à plusieurs protocoles en {annee}, par combinaison "
                                "de protocoles (10 premières, liste complète en annexe).")]
        annexe += _annexe("Bénévoles sur plusieurs protocoles", combis,
                          [("protocoles", "Protocoles"), ("benevoles", "Bénévoles")])
    if _socle(ctx)["par_departement"]:
        deps = pt.reseau_par_departement(jeux, saisons, BENEVOLE)
        blocs_r += [("image", fig.chart_barres({x["departement"]: x["participants"] for x in deps},
                                               out / "reseau_departements.png", "Bénévoles", fig.VERT_EAU)),
                    ("legende", f"Figure : bénévoles distincts par département en {annee} (un bénévole compte dans "
                                "chaque département où il a fait un relevé).")]
        annexe += _annexe("Bénévoles par département (tous protocoles)", deps,
                          [("departement", "Département"), ("participants", "Bénévoles")])
    return texte, blocs_r, annexe


@register_brick(
    "ind_synthese",
    requires=["ind_socle"],
    provides=["TABLE_CHIFFRES_CLES", "TEXTE_CHIFFRES_CLES", "TEXTE_CONCLUSION", "BLOCS_ANNEXE_TABLEAUX",
              "BLOCS_ANNEXE_CONTROLE", "BLOCS_ORGANISMES", "TEXTE_RESEAU_BENEVOLE", "BLOCS_RESEAU_BENEVOLE"],
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
        annexe_esp += [("titre", 2, f"{r['label']} - {d['libelle']}"), *d["annexe"],
                       *_annexe("Espèces notées", [
                           {**e, "freq_aires": _pct(e["freq_aires"]), "freq_unites": _pct(e["freq_unites"]),
                            "effectif": tx.nombre(e["effectif"])} for e in especes],
                           [("rang", "Rang"), ("nom", "Espèce"), ("freq_aires", f"% des {tx.pluriel(r['aire'])}"),
                            ("freq_unites", f"% des {tx.pluriel(r['unite'])}"), ("effectif", "Effectif cumulé")])]
        anomalies = [{**a, "date": a["date"].strftime("%d/%m/%Y") if a.get("date") else "", "nom": a.get("nom") or ""}
                     for a in d["jeu"].anomalies if a.get("saison") in (None, d["saison"])]
        if anomalies:
            controle += [("titre", 2, r["label"]),
                         ("tableau", anomalies, [("code", "Code"), ("libelle", "Anomalie"), ("aire", "Aire"),
                                                 ("unite", "Unité"), ("date", "Date"), ("nom", "Observateur")])]
    jeux = {code: d["jeu"] for code, d in sections}
    organismes = _organismes(sections)
    texte_reseau, blocs_reseau, annexe_reseau = _reseau(ctx, annee, sections)
    if annexe_reseau:
        annexe_esp += [("titre", 2, "Le réseau bénévole"), *annexe_reseau]
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
        texts={"TEXTE_CHIFFRES_CLES": texte, "TEXTE_CONCLUSION": " ".join(phrases) or texte,
               "TEXTE_RESEAU_BENEVOLE": texte_reseau},
        tables={
            "TABLE_CHIFFRES_CLES": tableau(lignes, [("protocole", "Protocole"), ("saison", "Saison"),
                                                    ("aires", "Aires suivies"), ("observateurs", "Observateurs"),
                                                    ("donnees", "Données"), ("temps", "Temps"),
                                                    ("ecart", "Écart des aires")]),
            "BLOCS_ORGANISMES": blocs(organismes),
            "BLOCS_RESEAU_BENEVOLE": blocs(blocs_reseau),
            "BLOCS_ANNEXE_TABLEAUX": blocs(annexe_esp),
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
    variables.update({f"annee_prec_{PREFIXES[c]}": libelle_saison(s["annee"] - 1, regle(ctx, c)["saison"])
                      for c in PROTOCOLES})
    variables.update({"zone": ctx.area_name,
                      "sources": "Faune-France (STOC, SHOC) et GeoNature (STOM, STERF, POP), LPO Auvergne-Rhône-Alpes"})
    # seulement les mises en page des protocoles présents dans le rapport ({PREFIXE}_CARTE…)
    prefixes = {PREFIXES[c] for c, _ in sections}
    layouts = [n for n in qgis_layout_names(projet) if n.split("_")[0] in prefixes]
    # cadrage de chaque protocole sur l'étendue de ses aires (+ marge, étendue minimale), commun à ses trois cartes
    p = ctx.params
    par_code = cartes.emprises(couches["ind_aires"], float(p.get("emprise_min_km", 20)) * 1000,
                               float(p.get("emprise_marge", 0.05)))
    code_de = {PREFIXES[c]: c for c, _ in sections}
    emprises = {n: par_code[code_de[n.split("_")[0]]] for n in layouts if code_de[n.split("_")[0]] in par_code}
    config = {**p.get("qgis_render", {}), "project_variables": variables, "layouts": layouts,
              "layout_extents": emprises}
    launch_qgis_render(project_path=copie, output_dir=ctx.output_dirs["maps"], config=config)
    layout = ctx.params.get("map_layout", "normal")
    return AnalysisResult(images={png.stem: ImageBlock(png, layout)
                                  for png in sorted(ctx.output_dirs["maps"].glob("*.png"))})


# ------------------------------------------------------------------------------ analyses propres à un protocole
def _stoc(ctx, jeu, saison, r):
    s = _socle(ctx)
    sites = ctx.cached("ind_jeu_stoc_sites", lambda: chargement.charger_stoc_sites(
        s["q"], r, saison, int(ctx.params.get("annees_especes", 5))))
    return sp.blocs_stoc(jeu, sites, saison, r, sortie=ctx.output_dirs["dataviz"])


def _shoc(ctx, jeu, saison, r):
    return sp.blocs_shoc(jeu, jeu_protocole(ctx, "stoc"), saison)   # STOC chargé même s'il n'est pas demandé


SPECIFIQUES.update({
    "stoc": _stoc,
    "shoc": _shoc,
    "stom": lambda ctx, jeu, saison, r: sp.blocs_stom(jeu, saison, r),
    "sterf": lambda ctx, jeu, saison, r: sp.blocs_sterf(jeu, saison, r, sortie=ctx.output_dirs["dataviz"]),
    "pop_reptile": lambda ctx, jeu, saison, r: sp.blocs_pop(jeu, saison, r, sortie=ctx.output_dirs["dataviz"]),
    "pop_amphibien": lambda ctx, jeu, saison, r: sp.blocs_pop(jeu, saison, r, sortie=ctx.output_dirs["dataviz"]),
})


def _brique(code: str):
    def run(ctx):
        return section_protocole(ctx, code)
    run.__doc__ = f"Section {PREFIXES[code]} du rapport Indicateurs de biodiversité."
    return run


for _code in PROTOCOLES:
    register_brick(_code, requires=["ind_socle"], provides=cles_protocole(_code))(_brique(_code))
