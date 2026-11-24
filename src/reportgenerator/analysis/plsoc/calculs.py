"""Calculs et textes du rapport PLSOC Œdicnème (fonctions pures, testées sans base).

Entrées : listes de dictionnaires lues par queries.py (couples, nids, événements…) et nomenclatures du schéma.
Règles (cf. METHODO.md) :
- succès et jours d'exposition Mayfield : valeur validée par les experts si elle existe, sinon valeur calculée
  (signalée comme provisoire) ; historique 2015-2025 : valeurs validées à l'époque ;
- Mayfield (méthode des rapports) : survie journalière = 1 - échecs certains / jours d'exposition ; probabilité de
  succès = survie ^ durée de la nidification ;
- secteurs et communes : rattachement spatial (polygones).
"""

from collections import Counter, defaultdict
from datetime import date, timedelta
from statistics import mean

SUCCES_CODES = ("succes_certain", "succes_probable", "echec_probable", "echec_certain")
REUSSITE = ("succes_certain", "succes_probable")
ECHECS = ("echec_certain", "echec_probable")
# libellés courts du degré de menace (colonne des tableaux par secteur, comme dans les rapports)
MENACE_COURT = {
    "projet_identifie": "Projet identifié",
    "en_attente_projet": "En attente de projet",
    "zone_au": "Zone « AU »",
    "zone_u": "Zone « U »",
    "non_menace": "Non menacé",
}
# regroupement des causes de fin pour le texte (rapport 2024 : prédation, activité humaine, inconnue)
GROUPES_CAUSES = {
    "predation": "prédation",
    "travaux_agricoles": "activité humaine",
    "derangement": "activité humaine",
    "disparition_oeufs": "disparition (cause inconnue)",
    "disparition_poussins": "disparition (cause inconnue)",
    "disparition_couple": "disparition (cause inconnue)",
    "abandon_nid": "abandon du nid",
    "cause_climatique": "cause climatique",
    "croissance_culture": "suivi interrompu (végétation)",
    "inconnu": "inconnue",
    None: "non renseignée",
}
MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


# --------------------------------------------------------------------------------------------------- formats
def fmt(n) -> str:
    return f"{int(round(n or 0)):,}".replace(",", " ")


def pct(a, b, dec=0):
    if not b:
        return None
    v = 100 * a / b
    return round(v, dec) if dec else int(round(v))


def fmt_pct(a, b, dec=0) -> str:
    v = pct(a, b, dec)
    return "–" if v is None else (f"{v:.{dec}f}".replace(".", ",") if dec else str(v)) + " %"


def date_courte(d) -> str:
    return d.strftime("%d/%m") if d else "–"


def date_longue(d) -> str:
    return f"{d.day}{'er' if d.day == 1 else ''} {MOIS[d.month - 1]}" if d else "–"


def liste_fr(items) -> str:
    items = [str(i) for i in items if i]
    if not items:
        return ""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def accord(n, singulier, pluriel=None) -> str:
    return f"{fmt(n)} {singulier if abs(n or 0) <= 1 else (pluriel or singulier + 's')}"


def libelle(nomenc, table, code, defaut="Non renseigné") -> str:
    r = nomenc.get(table, {}).get(code)
    return r["libelle"] if r else defaut


def annee_rapport(param, defaut: int) -> int:
    """Paramètre annee du dossier.toml ; 0 ou vide = dernière saison terminée."""
    return int(param) if param else int(defaut)


def de_annee(rows, annee):
    return [r for r in rows if r.get("annee") == annee]


# ----------------------------------------------------------------------------------------------------- bilan
def bilan_annee(couples, nids, annee) -> dict:
    cs, ns = de_annee(couples, annee), de_annee(nids, annee)
    s = Counter(n.get("succes_repro") for n in ns)
    return {
        "annee": annee,
        "couples": len(cs),
        "nicheurs": sum(1 for c in cs if (c.get("nb_nids") or 0) > 0),
        "nids": len(ns),
        **{k: s.get(k, 0) for k in SUCCES_CODES},
        "issue_inconnue": len(ns) - sum(s.get(k, 0) for k in SUCCES_CODES),
        "poussins": sum(n.get("nb_poussins") or 0 for n in ns),
        "jeunes": sum(n.get("nb_jeunes_envol") or 0 for n in ns),
        "proteges": sum(1 for n in ns if n.get("protege")),
        "valides": sum(1 for n in ns if n.get("succes_source") in ("validé", "historique")),
        "taux_succes": pct(s.get("succes_certain", 0) + s.get("succes_probable", 0), len(ns)),
    }


def serie_annuelle(couples, nids, debut, fin) -> list[dict]:
    return [bilan_annee(couples, nids, a) for a in range(debut, fin + 1)]


def texte_resultats(serie, annee, debut) -> str:
    b = next(r for r in serie if r["annee"] == annee)
    prec = [r for r in serie if r["annee"] < annee and r["couples"]]
    t = (
        f"Les prospections menées en {annee} ont permis de localiser "
        f"{accord(b['couples'], 'couple cantonné', 'couples cantonnés')}. Parmi ceux-ci, {fmt(b['nicheurs'])} ont "
        f"niché de façon certaine, et {accord(b['nids'], 'nid ou nichée', 'nids ou nichées')} ont été recensés. "
        f"Au total, {accord(b['jeunes'], 'jeune à l’envol a été observé', 'jeunes à l’envol ont été observés')}."
    )
    if prec:
        p = prec[-1]
        moy = mean(r["couples"] for r in prec)
        sens = "plus" if b["couples"] > p["couples"] else ("moins" if b["couples"] < p["couples"] else "autant")
        t += (
            f" L'effectif est {sens} élevé qu'en {p['annee']} ({accord(p['couples'], 'couple')}) ; "
            f"la moyenne {prec[0]['annee']}-{p['annee']} est de {fmt(moy)} couples."
        )
        if b["couples"] >= max(r["couples"] for r in prec):
            t += f" C'est l'effectif le plus élevé depuis le début des suivis ({debut})."
        elif b["couples"] <= min(r["couples"] for r in prec):
            t += f" C'est l'effectif le plus faible depuis le début des suivis ({debut})."
    return t


def tableau_communes(couples, nids, annee) -> list[dict]:
    """Couples (commune du couple) et nids (commune du nid) par collectivité et commune, avec sous-totaux."""
    tab = defaultdict(lambda: {"couples": 0, "nids": 0})
    for c in de_annee(couples, annee):
        tab[(c.get("nom_epci") or "Hors EPCI", c.get("nom_commune") or "Commune inconnue")]["couples"] += 1
    for n in de_annee(nids, annee):
        tab[(n.get("nom_epci") or "Hors EPCI", n.get("nom_commune") or "Commune inconnue")]["nids"] += 1
    par_epci = defaultdict(list)
    for (epci, commune), v in tab.items():
        par_epci[epci].append({"collectivite": epci, "commune": commune, **v})
    rows = []
    for epci in sorted(par_epci, key=lambda e: -sum(r["couples"] for r in par_epci[e])):
        lignes = sorted(par_epci[epci], key=lambda r: r["commune"])
        rows += lignes
        if len(lignes) > 1:
            rows.append(
                {
                    "collectivite": epci,
                    "commune": f"Total {epci}",
                    "total": True,
                    "couples": sum(r["couples"] for r in lignes),
                    "nids": sum(r["nids"] for r in lignes),
                }
            )
    return rows


# --------------------------------------------------------------------------------------------------- milieux
def milieux(couples, annee, nomenc) -> dict:
    cs = de_annee(couples, annee)
    agri = [c for c in cs if c.get("milieu") == "agricole"]
    non_agri = [c for c in cs if c.get("milieu") and c.get("milieu") != "agricole"]
    inconnus = [c for c in cs if not c.get("milieu")]
    evolution = []
    for a in sorted({c["annee"] for c in couples}):
        ca = [c for c in de_annee(couples, a) if c.get("milieu")]
        if ca:
            evolution.append(
                {
                    "annee": a,
                    "pct_agricole": pct(sum(1 for c in ca if c["milieu"] == "agricole"), len(ca)),
                    "n": len(ca),
                }
            )
    cultures = Counter((c.get("culture") or "Non renseignée") for c in agri)
    types = Counter(libelle(nomenc, "ref_milieu", c["milieu"]) for c in non_agri)
    deduits = sum(1 for c in cs if c.get("milieu_deduit") and c.get("milieu"))
    connus = len(agri) + len(non_agri)
    t = (
        f"En {annee}, {accord(len(agri), 'couple occupait', 'couples occupaient')} des milieux agricoles "
        f"({fmt_pct(len(agri), connus)} des couples dont le milieu est connu) et "
        f"{accord(len(non_agri), 'couple', 'couples')} des milieux non agricoles."
    )
    if types:
        t += " Parmi ces derniers : " + ", ".join(f"{k.lower()} ({v})" for k, v in types.most_common()) + "."
    if inconnus:
        t += f" Le milieu de {accord(len(inconnus), 'couple')} n'est pas renseigné."
    if deduits:
        t += (
            f" Pour {accord(deduits, 'couple')}, le milieu a été déduit automatiquement (couple situé dans une "
            "parcelle agricole suivie ou dans une mesure compensatoire) : à vérifier et compléter dans le projet QGIS."
        )
    return {
        "texte": t,
        "evolution": evolution,
        "cultures": dict(cultures.most_common()),
        "types": dict(types.most_common()),
        "n_agricole": len(agri),
        "n_non_agricole": len(non_agri),
        "n_inconnu": len(inconnus),
    }


# -------------------------------------------------------------------------------------------------- secteurs
def statut_reproduction(couple, nomenc) -> str:
    return libelle(nomenc, "ref_stade_repro", couple.get("stade_repro"), "Couple observé")


def succes_couple(couple, nomenc) -> str:
    if not couple.get("nb_nids"):
        return "Pas de nid trouvé"
    return libelle(nomenc, "ref_succes_repro", couple.get("succes_repro"), "Indéterminé")


def lignes_couples(couples, nomenc) -> list[dict]:
    rows = []
    for c in sorted(couples, key=lambda c: (c.get("nom_commune") or "", c.get("lieu_dit") or "")):
        ld = c.get("lieu_dit") or "–"
        rows.append(
            {
                "commune": c.get("nom_commune") or "–",
                "lieu_dit": ld + (" *" if c.get("lieu_dit_deduit") else ""),
                "statut": statut_reproduction(c, nomenc),
                "succes": succes_couple(c, nomenc),
                "menace": MENACE_COURT.get(c.get("degre_menace"), "–"),
            }
        )
    return rows


def secteurs(couples, nids, liste_secteurs, annee, debut, nomenc) -> list[dict]:
    """Un bloc par secteur intersectant l'emprise (+ « Hors secteur » s'il y a des couples hors polygones)."""
    noms = [s["nom_secteur"] for s in liste_secteurs]
    if any(not c.get("nom_secteur") for c in de_annee(couples, annee)):
        noms.append(None)
    blocs = []
    for nom in noms:
        cs_all = [c for c in couples if c.get("nom_secteur") == nom]
        serie = {a: sum(1 for c in cs_all if c["annee"] == a) for a in range(debut, annee + 1)}
        cs = de_annee(cs_all, annee)
        nicheurs = sum(1 for c in cs if (c.get("nb_nids") or 0) > 0)
        n_prec = serie.get(annee - 1, 0)
        prec = [v for a, v in serie.items() if a < annee]
        titre = nom or "Couples hors des secteurs"
        t = (
            f"En {annee}, {accord(len(cs), 'couple a été recensé', 'couples ont été recensés')} sur ce secteur, dont "
            f"{fmt(nicheurs)} {'a niché' if nicheurs <= 1 else 'ont niché'} de façon certaine "
            f"(contre {accord(n_prec, 'couple')} en {annee - 1})."
        )
        if prec and any(prec):
            if len(cs) > max(prec):
                t += f" C'est l'effectif le plus élevé depuis {debut}."
            elif len(cs) < min(prec):
                t += f" C'est l'effectif le plus faible depuis {debut}."
            else:
                t += f" La moyenne {debut}-{annee - 1} est de {fmt(mean(prec))} couples."
        succes = Counter(n.get("succes_repro") for n in de_annee(nids, annee) if n.get("nom_secteur") == nom)
        if sum(succes.values()):
            t += (
                f" Sur les {accord(sum(succes.values()), 'nid')} du secteur, "
                f"{fmt(succes['succes_certain'] + succes['succes_probable'])} ont connu un succès certain ou probable."
            )
        blocs.append(
            {
                "nom": titre,
                "texte": t,
                "serie": serie,
                "lignes": lignes_couples(cs, nomenc),
                "n": len(cs),
                "secteur": nom,
            }
        )
    return blocs


# ------------------------------------------------------------------------------------------------ protection
def eclosion(nid) -> str:
    if nid.get("date_eclosion") or nid.get("stade_repro") == "presence_de_poussins":
        return "Oui"
    if nid.get("succes_repro") in ECHECS:
        return "Non"
    return "?"


def protection(nids, couples, annee, nomenc) -> dict:
    par_cle = {c["cle_couple"]: c for c in couples}
    agri, non_agri = [], []
    for n in sorted(de_annee(nids, annee), key=lambda n: (n.get("nom_commune") or "")):
        if not n.get("protege"):
            continue
        c = par_cle.get(n.get("cle_couple"), {})
        milieu = n.get("milieu") or c.get("milieu")
        ligne = {
            "commune": n.get("nom_commune") or "–",
            "lieu_dit": (c.get("lieu_dit") or "–") + (" *" if c.get("lieu_dit_deduit") else ""),
            "site": libelle(nomenc, "ref_milieu", milieu),
            "protection": libelle(nomenc, "ref_type_protection", n.get("type_protection"), "–"),
            "eclosion": eclosion(n),
            "succes": libelle(nomenc, "ref_succes_repro", n.get("succes_repro"), "–"),
        }
        (agri if milieu == "agricole" else non_agri).append(ligne)
    tous = agri + non_agri
    ecloses = sum(1 for r in tous if r["eclosion"] == "Oui")
    reussis = sum(1 for r in agri if r["succes"].startswith("Succès"))
    t = (
        f"Au cours de la saison {annee}, {accord(len(tous), 'nid a', 'nids ont')} fait l'objet d'une protection, soit "
        f"{fmt(len(agri))} en milieu agricole et {fmt(len(non_agri))} en zone non agricole. Parmi ceux-ci, "
        f"{accord(ecloses, 'est arrivé', 'sont arrivés')} jusqu'à l'éclosion des œufs."
    )
    if agri:
        t += (
            f" En milieu agricole, {fmt(reussis)} des {fmt(len(agri))} nids protégés ont connu un succès certain "
            "ou probable."
        )
    return {"texte": t, "agricole": agri, "non_agricole": non_agri}


# ------------------------------------------------------------------------------------------------ phénologie
def _min(valeurs):
    return min(valeurs) if valeurs else None


def _hiver(d, debut_annee: bool) -> str:
    if d is None:
        return "–"
    if debut_annee and d.month == 1:
        return "Hivernage"
    if not debut_annee and d.month == 12:
        return "Hivernage"
    return date_courte(d)


def phenologie_dates(couples, nids, rassemblements, synthese, debut, fin) -> list[dict]:
    syn = {r["annee"]: r for r in synthese}
    rows = []
    for a in range(debut, fin + 1):
        cs, ns = de_annee(couples, a), de_annee(nids, a)
        rs = [r.get("date_premiere_obs") or r.get("date_comptage") for r in rassemblements if r.get("annee") == a]
        rs = [d for d in rs if d and d.month >= 6]
        if not cs and not ns and a not in syn:
            continue
        rows.append(
            {
                "annee": a,
                "premiere_obs": _hiver(syn.get(a, {}).get("premiere"), True),
                "premier_couple": date_courte(_min([c["date_premiere_obs"] for c in cs if c.get("date_premiere_obs")])),
                "premiere_couvaison": date_courte(_min([n["date_couvaison"] for n in ns if n.get("date_couvaison")])),
                "premier_poussin": date_courte(_min([n["date_eclosion"] for n in ns if n.get("date_eclosion")])),
                "premier_rassemblement": date_courte(_min(rs)),
                "derniere_obs": _hiver(syn.get(a, {}).get("derniere"), False),
            }
        )
    return rows


def decades(annee) -> list[tuple[date, date, str]]:
    out = []
    for m in range(2, 12):  # février à novembre
        for j in (1, 11, 21):
            d = date(annee, m, j)
            f = (date(annee, m + 1, 1) - timedelta(days=1)) if j == 21 else d + timedelta(days=9)
            out.append((d, f, f"{j}-{f.day} {MOIS[m - 1][:4]}."))
    return out


def phenologie_decades(couples, annee, debut) -> dict:
    """Couples présents par décade (1re-dernière observation) : année du rapport et moyenne des années antérieures."""

    def presents(a, i):
        d, f, _ = decades(a)[i]
        return sum(
            1
            for c in de_annee(couples, a)
            if c.get("date_premiere_obs")
            and c["date_premiere_obs"] <= f
            and (c.get("date_derniere_obs") or c["date_premiere_obs"]) >= d
        )

    anterieures = [a for a in range(debut, annee) if de_annee(couples, a)]
    rows = []
    for i, (_, _, lib) in enumerate(decades(annee)):
        rows.append(
            {
                "decade": lib,
                "n": presents(annee, i),
                "moyenne": round(mean(presents(a, i) for a in anterieures), 1) if anterieures else None,
            }
        )
    pic = max(rows, key=lambda r: r["n"]) if rows else None
    t = ""
    if pic and pic["n"]:
        t = (
            f"En {annee}, le nombre maximal de couples présents simultanément est de {fmt(pic['n'])}, atteint "
            f"lors de la décade du {pic['decade']}"
        )
        moy = max((r["moyenne"] or 0) for r in rows)
        t += f" (maximum moyen des années précédentes : {fmt(moy)})." if anterieures else "."
    return {"lignes": rows, "texte": t}


# ----------------------------------------------------------------------------------------- succès / Mayfield
def succes(nids, annee, nomenc) -> dict:
    ns = de_annee(nids, annee)
    c = Counter(n.get("succes_repro") for n in ns)
    rows = [
        {"succes": libelle(nomenc, "ref_succes_repro", k), "nids": c.get(k, 0), "pct": fmt_pct(c.get(k, 0), len(ns), 1)}
        for k in SUCCES_CODES
    ]
    autres = len(ns) - sum(c.get(k, 0) for k in SUCCES_CODES)
    if autres:
        rows.append({"succes": "Issue inconnue / en cours", "nids": autres, "pct": fmt_pct(autres, len(ns), 1)})
    reussis = c.get("succes_certain", 0) + c.get("succes_probable", 0)
    valides = sum(1 for n in ns if n.get("succes_source") in ("validé", "historique"))
    t = (
        f"Le taux de succès global est de {fmt_pct(reussis, len(ns))} en {annee} "
        f"({fmt(reussis)} nids sur {fmt(len(ns))})."
    )
    if valides < len(ns):
        t += (
            f" Attention : le succès de {accord(len(ns) - valides, 'nid')} n'a pas encore été validé par les "
            "experts ; la valeur utilisée est celle calculée automatiquement, ce chiffre est donc provisoire."
        )
    return {"lignes": rows, "texte": t, "taux": pct(reussis, len(ns)), "non_valides": len(ns) - valides}


def mayfield(nids, annee, duree) -> dict:
    ns = de_annee(nids, annee)
    exposes = [n for n in ns if (n.get("mayfield_jours_exposition") or 0) > 0]
    jours = float(sum(n["mayfield_jours_exposition"] for n in exposes))
    echecs = sum(1 for n in ns if n.get("succes_repro") == "echec_certain")
    survie = (1 - echecs / jours) if jours else None
    proba = survie**duree if survie is not None and survie > 0 else None
    non_valides = sum(1 for n in ns if n.get("mayfield_source") not in ("validé", "historique"))
    return {
        "nids_exposes": len(exposes),
        "jours": jours,
        "echecs": echecs,
        "survie": survie,
        "probabilite": proba,
        "duree": duree,
        "non_valides": non_valides,
    }


def texte_mayfield(m, annee) -> str:
    if not m["jours"]:
        return f"Aucun jour d'exposition n'est disponible pour {annee} : le taux de Mayfield ne peut pas être calculé."
    t = (
        f"En {annee}, l'échantillon compte {accord(m['nids_exposes'], 'nid')} pour {fmt(m['jours'])} jours "
        "d'exposition "
        f"et {accord(m['echecs'], 'échec certain', 'échecs certains')}. Le taux de survie journalier est de "
        f"{m['survie']:.5f}".replace(".", ",") + f", soit une probabilité de succès de "
        f"{100 * (m['probabilite'] or 0):.1f}".replace(".", ",") + f" % sur {m['duree']} jours."
    )
    if m["non_valides"]:
        t += (
            f" Les jours d'exposition de {accord(m['non_valides'], 'nid')} ne sont pas encore validés : seule leur "
            "période d'incubation calculée est comptée, ce qui sous-estime la probabilité de succès."
        )
    return t


def lignes_mayfield(m) -> list[dict]:
    return [
        {"indicateur": "Nids pris en compte", "valeur": fmt(m["nids_exposes"])},
        {"indicateur": "Nombre de nids en échec (certain)", "valeur": fmt(m["echecs"])},
        {"indicateur": "Total des jours d'exposition", "valeur": f"{m['jours']:.1f}".replace(".", ",")},
        {
            "indicateur": "Taux de survie journalier",
            "valeur": "–" if m["survie"] is None else f"{m['survie']:.5f}".replace(".", ","),
        },
        {
            "indicateur": f"Probabilité de succès ({m['duree']} jours)",
            "valeur": "–" if m["probabilite"] is None else f"{100 * m['probabilite']:.1f} %".replace(".", ","),
        },
    ]


def causes(nids, annee, nomenc) -> dict:
    echecs = [n for n in de_annee(nids, annee) if n.get("succes_repro") in ECHECS]
    detail = Counter(libelle(nomenc, "ref_cause_echec", n.get("cause_fin"), "Non renseignée") for n in echecs)
    groupes = Counter(GROUPES_CAUSES.get(n.get("cause_fin"), "autre") for n in echecs)
    if not echecs:
        t = f"Aucun échec de nidification n'est enregistré en {annee}."
    else:
        t = (
            f"Sur les {accord(len(echecs), 'nid en échec', 'nids en échec')} (certain ou probable), la cause est : "
            + ", ".join(f"{g} pour {fmt_pct(v, len(echecs))}" for g, v in groupes.most_common())
            + "."
        )
        if groupes.get("non renseignée"):
            t += " Les causes non renseignées sont à compléter lors de la validation des nids."
    return {"detail": dict(detail.most_common()), "texte": t}


# -------------------------------------------------------------------------------------------- rassemblements
def rassemblements(rass, annee) -> dict:
    sites = defaultdict(list)
    for r in rass:
        sites[(r.get("site") or "?", r.get("commune") or "")].append(r)
    lignes, historique = [], {}
    for (site, commune), rs in sorted(sites.items()):
        par_an = defaultdict(int)
        for r in rs:
            par_an[r["annee"]] = max(par_an[r["annee"]], r.get("effectif") or 0)
        historique[site] = dict(sorted(par_an.items()))
        cette = [r for r in rs if r["annee"] == annee and r.get("effectif") is not None]
        if not cette:
            continue
        top = max(cette, key=lambda r: r["effectif"])
        anciens = {a: v for a, v in par_an.items() if a < annee and v}
        rec = max(anciens.items(), key=lambda kv: kv[1]) if anciens else None
        lignes.append(
            {
                "site": site,
                "commune": commune,
                "effectif": fmt(top["effectif"]),
                "date": date_courte(top.get("date_comptage")),
                "comptages": len(cette),
                "record": f"{fmt(rec[1])} ({rec[0]})" if rec else "–",
            }
        )
    if lignes:
        top = max(lignes, key=lambda r: int(r["effectif"].replace(" ", "")))
        t = (
            f"En {annee}, "
            f"{accord(len(lignes), 'site de rassemblement a été suivi', 'sites de rassemblement ont été suivis')}. "
            f"L'effectif maximal compté est de {top['effectif']} individus ({top['site']}, le {top['date']})."
        )
    else:
        t = (
            f"Aucun comptage de rassemblement postnuptial n'est enregistré en base pour {annee} dans l'emprise du "
            "rapport."
        )
    return {"lignes": lignes, "historique": historique, "texte": t}


# --------------------------------------------------------------------------------------------------- baguage
def baguage(bagues, couples, annee, nomenc) -> dict:
    par_cle = {c["cle_couple"]: c for c in couples}
    vues, lignes = set(), []
    for b in sorted(bagues, key=lambda b: (b.get("date_obs") or date(annee, 12, 31), b.get("bague") or "")):
        cle = (b.get("bague"), b.get("classe_age"))
        if not b.get("bague") or b["bague"].startswith("NON") or cle in vues:  # « NONBAGUE » saisi dans l'historique
            continue
        vues.add(cle)
        c = par_cle.get(b.get("cle_couple"), {})
        lignes.append(
            {
                "dep": (c.get("code_insee") or "")[:2] or "–",
                "commune": c.get("nom_commune") or "–",
                "lieu_dit": (c.get("lieu_dit") or "–") + (" *" if c.get("lieu_dit_deduit") else ""),
                "bague": b.get("bague"),
                "type": (b.get("type_bague") or "").capitalize(),
                "date": b["date_obs"].strftime("%d/%m/%Y") if b.get("date_obs") else "–",
                "age": "Poussin" if b.get("classe_age") == "poussin" else "Adulte",
                "habitat": libelle(nomenc, "ref_milieu", c.get("milieu"), "–"),
            }
        )
    poussins = sum(1 for r in lignes if r["age"] == "Poussin")
    adultes = len(lignes) - poussins
    t = (
        f"En {annee}, {accord(poussins, 'poussin a été bagué', 'poussins ont été bagués')} et "
        f"{accord(adultes, 'adulte bagué a été identifié', 'adultes bagués ont été identifiés')} "
        "au sein des couples suivis."
    )
    return {"lignes": lignes, "texte": t, "poussins": poussins, "adultes": adultes}


# ------------------------------------------------------------------------------------------------- urbanisme
def urbanisme(rows, debut, annee) -> dict:
    lignes = [
        {
            "collectivite": r["nom_epci"],
            "zonage": f"« {r['zonage_plu']} »",
            "couples": fmt(r["nb_couples_annees"]),
            "parcelles": fmt(r["nb_parcelles"]),
            "surface": "–" if r.get("surface_ha") is None else f"{r['surface_ha']}".replace(".", ","),
            "periode": f"{r['premiere_annee']}-{r['derniere_annee']}",
        }
        for r in rows
    ]
    total = sum(r["nb_couples_annees"] for r in rows)
    t = (
        f"Depuis {debut}, {accord(total, 'couple a occupé', 'couples ont occupé')} (un même site compté chaque année) "
        "des parcelles classées en zone urbaine (U) ou à urbaniser (AU) des documents d'urbanisme. Ces sites sont "
        "menacés à plus ou moins long terme."
    )
    return {"lignes": lignes, "texte": t}


# ------------------------------------------------------------------------------------ mesures compensatoires
def _groupe_mesures(mesures):
    projets = defaultdict(list)
    for m in mesures:
        projets[m.get("id_projet") or m["id_site"]].append(m)
    return projets


def mesures_compensatoires(mesures, couples, nids, evenements, suivis, annee, nomenc, statuts_evenement) -> dict:
    """Synthèse de toutes les mesures, et une fiche par projet (synthèse, passages de l'année, historique)."""
    projets = _groupe_mesures(mesures)
    synthese, fiches = [], []
    tot = Counter()
    for _pid, ms in sorted(
        projets.items(),
        key=lambda kv: (min(m.get("annee_mise_en_place") or 9999 for m in kv[1]), kv[1][0].get("nom_projet") or ""),
    ):
        sites = {m["id_site"] for m in ms}
        nom = ms[0].get("nom_projet") or ms[0]["id_site"]
        mise = min((m.get("annee_mise_en_place") for m in ms if m.get("annee_mise_en_place")), default=None)
        cs_all = [c for c in couples if c.get("id_mesure_compensatoire") in sites]
        ns_all = [n for n in nids if n.get("id_mesure_compensatoire") in sites]
        cs, ns = de_annee(cs_all, annee), de_annee(ns_all, annee)
        best = min(
            (n.get("succes_repro") for n in ns if n.get("succes_repro") in SUCCES_CODES),
            key=SUCCES_CODES.index,
            default=None,
        )
        derniere = max((n["annee"] for n in ns_all), default=None)
        jeunes = sum(n.get("nb_jeunes_envol") or 0 for n in ns)
        tot.update(
            projets=1,
            parcelles=len(ms),
            couples=len(cs),
            nids=len(ns),
            jeunes=jeunes,
            occupees=len({c.get("id_mesure_compensatoire") for c in cs}),
        )
        synthese.append(
            {
                "projet": nom,
                "commune": liste_fr(sorted({m.get("commune") for m in ms if m.get("commune")})),
                "mise_en_place": mise or "–",
                "parcelles": len(ms),
                "couples": len(cs),
                "nids": len(ns),
                "succes": libelle(nomenc, "ref_succes_repro", best, "–") if ns else "–",
                "jeunes": jeunes,
                "derniere": derniere or "–",
            }
        )
        # fiche

        def surf(cle):
            return sum(m[cle] for m in ms if m.get(cle)) or None

        fiche_synthese = [
            ("Nom du projet", nom),
            ("N° d'arrêté préfectoral", liste_fr(sorted({m["ref_arrete"] for m in ms if m.get("ref_arrete")})) or "–"),
            (
                "Porteur du projet",
                liste_fr(sorted({m["porteur_projet"] for m in ms if m.get("porteur_projet")})) or "–",
            ),
            ("Parcelles", f"{len(ms)} ({_ha(sum(float(m.get('surface_ha') or 0) for m in ms))})"),
            ("Surface en galets", _ha(surf("surface_galet_ha"))),
            ("Surface en prairie", _ha(surf("surface_prairie_ha"))),
            ("Année de mise en place", mise or "–"),
            ("Commune", liste_fr(sorted({m.get("commune") for m in ms if m.get("commune")})) or "–"),
            ("Lieu-dit", liste_fr(sorted({m.get("lieu_dit") for m in ms if m.get("lieu_dit")})) or "–"),
            (f"Nombre de couples {annee}", len(cs)),
            (f"Succès de reproduction {annee}", libelle(nomenc, "ref_succes_repro", best, "–") if ns else "Pas de nid"),
            ("Dernière reproduction", derniere or "Aucune"),
        ]
        passages = Counter()
        for e in evenements:
            if e.get("id_mesure_compensatoire") in sites and e.get("date_obs"):
                lib = statuts_evenement.get(e.get("code"), {}).get("libelle") or e.get("code") or "Observation"
                passages[(e["date_obs"], lib)] += e.get("nombre") or 0
        lignes_passages = [
            {
                "date": d.strftime("%d/%m/%Y"),
                "evenement": lib.replace(" (historique)", ""),
                "nombre": fmt(nb) if nb else "–",
            }
            for (d, lib), nb in sorted(passages.items())
        ]
        lignes_suivis = [
            {
                "date": s["date_mesure"].strftime("%d/%m/%Y") if s.get("date_mesure") else "–",
                "galets": _pct_txt(s.get("rec_galets")),
                "herbes": _pct_txt(s.get("rec_herbes")),
                "ligneux": _pct_txt(
                    (s.get("rec_arbustes") or 0) + (s.get("rec_ronces") or 0)
                    if s.get("rec_arbustes") is not None or s.get("rec_ronces") is not None
                    else None
                ),
                "frequentation": _oui_non(s.get("frequentation")),
                "dechets": _oui_non(s.get("dechets")),
                "bilan": s.get("bilan") or s.get("autres_obs") or "–",
            }
            for s in sorted(suivis, key=lambda s: s.get("date_mesure") or date.min)
            if s.get("id_mesure_compensatoire") in sites
        ]
        historique = []
        for a in range(mise or annee, annee + 1):
            ca, na = de_annee(cs_all, a), de_annee(ns_all, a)
            if a < (mise or annee):
                continue
            b = min(
                (n.get("succes_repro") for n in na if n.get("succes_repro") in SUCCES_CODES),
                key=SUCCES_CODES.index,
                default=None,
            )
            historique.append(
                {
                    "annee": a,
                    "presence": f"Oui ({len(ca)})" if ca else "Non",
                    "reproduction": (
                        f"Certaine ({len(na)} nid{'s' if len(na) > 1 else ''})"
                        if na
                        else ("Couple sans nid trouvé" if ca else "–")
                    ),
                    "succes": libelle(nomenc, "ref_succes_repro", b, "–") if na else "–",
                    "jeunes": fmt(sum(n.get("nb_jeunes_envol") or 0 for n in na)) if na else "–",
                }
            )
        fiches.append(
            {
                "nom": nom,
                "sites": sorted(sites),
                "synthese": fiche_synthese,
                "passages": lignes_passages,
                "suivis": lignes_suivis,
                "historique": historique,
                "n_couples": len(cs),
            }
        )
    t = (
        f"En {annee}, l'emprise du rapport compte {accord(tot['projets'], 'projet')} de compensation "
        f"({accord(tot['parcelles'], 'parcelle')}). "
        f"{accord(tot['couples'], 'couple s’est installé', 'couples se sont installés')} "
        f"sur {accord(tot['occupees'], 'parcelle')} ({fmt_pct(tot['occupees'], tot['parcelles'])} des parcelles), "
        f"pour {accord(tot['nids'], 'nid')} et {accord(tot['jeunes'], 'jeune à l’envol', 'jeunes à l’envol')}."
    )
    return {"synthese": synthese, "fiches": fiches, "texte": t, "totaux": dict(tot)}


def _ha(v) -> str:
    return "–" if not v else f"{round(float(v), 2)} ha".replace(".", ",")


def _pct_txt(v):
    return "–" if v is None else f"{v} %"


def _oui_non(v):
    return "–" if v is None else ("Oui" if v else "Non")


# -------------------------------------------------------------------------------------- zone, qualité, bilan
def texte_zone(zone, liste_secteurs) -> str:
    noms = [s["nom_secteur"] for s in liste_secteurs]
    t = (
        f"L'emprise de ce rapport couvre {fmt(zone['surface_ha'])} ha et "
        f"{accord(zone['nb_communes'], 'commune')}. Toutes les données du suivi situées dans cette emprise sont prises "
        "en compte."
    )
    if noms:
        t += f" Elle comprend {accord(len(noms), 'secteur')} de suivi : {liste_fr(noms)}."
    return t


def qualite(couples, nids, anomalies, annee) -> list[str]:
    """Phrases de l'encadré « État des données » (début du rapport)."""
    cs, ns = de_annee(couples, annee), de_annee(nids, annee)
    out = []
    valides = sum(1 for n in ns if n.get("succes_source") in ("validé", "historique"))
    mf = sum(1 for n in ns if n.get("mayfield_source") in ("validé", "historique"))
    out.append(
        f"Validation experte : {fmt(valides)} nids sur {fmt(len(ns))} ont un succès validé, {fmt(mf)} des jours "
        "d'exposition Mayfield validés."
        + (
            ""
            if valides == len(ns)
            else " Les autres valeurs sont calculées automatiquement : les chiffres de "
            "succès et de Mayfield sont provisoires."
        )
    )
    saisis = sum(1 for c in cs if c.get("milieu") and not c.get("milieu_deduit"))
    deduits = sum(1 for c in cs if c.get("milieu") and c.get("milieu_deduit"))
    out.append(
        f"Milieu : saisi pour {fmt(saisis)} couples, déduit automatiquement pour {fmt(deduits)}, inconnu pour "
        f"{fmt(len(cs) - saisis - deduits)} (à compléter dans le projet QGIS)."
    )
    ld_saisis = sum(1 for c in cs if c.get("lieu_dit") and not c.get("lieu_dit_deduit"))
    ld_deduits = sum(1 for c in cs if c.get("lieu_dit_deduit"))
    out.append(
        f"Lieu-dit : saisi pour {fmt(ld_saisis)} couples, déduit pour {fmt(ld_deduits)} (lieu-dit Faune-France le "
        "plus proche, marqué d'un astérisque dans les tableaux)."
    )
    echecs = [n for n in ns if n.get("succes_repro") in ECHECS]
    out.append(
        f"Causes d'échec : renseignées pour {fmt(sum(1 for n in echecs if n.get('cause_fin')))} nids en échec "
        f"sur {fmt(len(echecs))}."
    )
    bloquants = sum(a["nb"] for a in anomalies if a["gravite"] == "BLOQUANT")
    importants = sum(a["nb"] for a in anomalies if a["gravite"] == "IMPORTANT")
    out.append(
        f"Contrôle de la saisie : {accord(bloquants, 'anomalie bloquante', 'anomalies bloquantes')} et "
        f"{accord(importants, 'anomalie importante', 'anomalies importantes')} en {annee} dans l'emprise "
        "(détail en annexe)."
    )
    return out


def texte_bilan(serie, annee, succ, rass, mes) -> str:
    b = next(r for r in serie if r["annee"] == annee)
    return (
        f"Le suivi {annee} a permis de recenser {accord(b['couples'], 'couple')}, dont {fmt(b['nicheurs'])} nicheurs "
        f"certains, pour {accord(b['nids'], 'nid ou nichée', 'nids ou nichées')}. Le succès de reproduction est "
        f"estimé à {succ['taux'] if succ['taux'] is not None else '–'} % et "
        f"{accord(b['jeunes'], 'jeune à l’envol a été observé', 'jeunes à l’envol ont été observés')}. "
        f"{rass['texte']} {mes['texte']}"
    )
