"""Calculs et textes du dossier Natura 2000 (fonctions pures, testées sans base)."""

import re

from reportgenerator.analysis.connaissance.indicateurs import ORDRE_GROUPES, cle, ordre_groupe  # noqa: F401

NIDIF_LIBELLES = {3: "nicheur certain", 2: "nicheur probable", 1: "nicheur possible"}
ESPECE_RANGS = ("ES", "SSES")

# annexes du rapport : un tableau par groupe, dans cet ordre ; les autres groupes vont dans « Invertébrés »
GROUPES_ANNEXES = [
    ("Oiseaux", "oiseaux"),
    ("Mammifères", "mammifères"),
    ("Chauves-souris", "chiroptères"),
    ("Amphibiens", "amphibiens"),
    ("Reptiles", "reptiles"),
    ("Poissons", "poissons"),
]
INVERTEBRES = ("Invertébrés", "invertébrés")

# libellés des ordres pour le texte des rayons
ORDRES_LIBELLES = {
    "Accipitriformes": "rapaces diurnes",
    "Falconiformes": "faucons",
    "Strigiformes": "rapaces nocturnes",
    "Chiroptera": "chiroptères",
}
RAPACES = {"Accipitriformes", "Falconiformes", "Strigiformes"}


def _fmt(n) -> str:
    return f"{int(n or 0):,}".replace(",", " ")


def _liste(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def est_espece(taxon) -> bool:
    return taxon.get("id_rang") in ESPECE_RANGS


def presence(taxon) -> str:
    return "Dans le site" if taxon.get("nb_donnees_site") else "À proximité"


def statut_biologique(taxon) -> str:
    """Oiseaux : « Nicheur certain, migrateur, hivernant »... (vide pour les autres groupes)."""
    if taxon.get("groupe") != "Oiseaux":
        return ""
    parts = []
    if taxon.get("rang_nidif"):
        parts.append(NIDIF_LIBELLES[int(taxon["rang_nidif"])])
    if taxon.get("migrateur"):
        parts.append("migrateur")
    if taxon.get("hivernant"):
        parts.append("hivernant")
    # ni nicheur, ni hivernant, ni comportement de migration saisi : cellule vide (à compléter par l'expert)
    texte = ", ".join(parts)
    return texte[:1].upper() + texte[1:]


def statut_chiro(taxon) -> str:
    if taxon.get("colonie"):
        return "Colonies de reproduction"
    if taxon.get("gite"):
        return "Gîtes sans reproduction"
    return "Contacts"


def nom_affiche(taxon) -> str:
    """Nom vernaculaire, marqué « (complexe) » pour un genre ou un complexe d'espèces."""
    nom = taxon.get("nom_vern") or taxon.get("lb_nom") or ""
    return nom if est_espece(taxon) else f"{nom} (complexe)"


def complexes_n2000(candidats, liste_manuelle=()) -> list[dict]:
    """Genres / complexes retenus comme Natura 2000 : toutes leurs espèces le sont (détection
    automatique, genres seulement), ou nom scientifique présent dans la liste manuelle du dossier."""
    manuels = {str(n).strip().lower() for n in liste_manuelle}
    out = []
    for c in candidats:
        auto = c.get("n_especes") and c.get("n_especes") == c.get("n_especes_n2000")
        manuel = (c.get("lb_nom") or "").strip().lower() in manuels
        if auto or manuel:
            out.append({**c, "origine": "automatique" if auto else "liste du dossier"})
    return out


def groupe_annexe(groupe: str) -> str:
    return groupe if groupe in dict(GROUPES_ANNEXES) else INVERTEBRES[0]


def tri(taxons):
    return sorted(taxons, key=lambda t: ((t.get("groupe") or ""), (t.get("nom_vern") or t.get("lb_nom") or "")))


# ---------------------------------------------------------------- emprises des cartes
def rayon_taxon_km(rayons_km: dict, lb_nom: str, ordre: str) -> float:
    """Rayon de prise en compte d'un taxon, même règle que la vue (queries._rayon_par_taxon_sql) : espèce
    (binôme, sous-espèces comprises), sinon ordre, sinon rayon par défaut."""
    binome = " ".join((lb_nom or "").split()[:2])
    especes, ordres = rayons_km.get("especes") or {}, rayons_km.get("ordres") or {}
    if binome in especes:
        return float(especes[binome])
    if ordre in ordres:
        return float(ordres[ordre])
    return float(rayons_km.get("defaut", 1))


def groupes_pour_graphique(par_groupe, max_groupes=15) -> list[dict]:
    """Lignes des graphiques « par groupe taxonomique » (format des graphiques du dossier générique :
    group_taxo, nb_espece, nb_data_tot). Au-delà de max_groupes, les plus petits sont regroupés en « Autres
    groupes » (lisibilité)."""
    tries = sorted(par_groupe, key=lambda g: -(g["nb_donnees"] or 0))
    gardes, reste = tries[:max_groupes - 1], tries[max_groupes - 1:]
    if len(reste) == 1:
        gardes, reste = tries, []
    rows = [{"group_taxo": g["groupe"], "nb_espece": g["nb_especes"] or 0, "nb_data_tot": g["nb_donnees"] or 0}
            for g in gardes]
    if reste:
        rows.append({"group_taxo": f"Autres groupes ({len(reste)})",
                     "nb_espece": sum(g["nb_especes"] or 0 for g in reste),
                     "nb_data_tot": sum(g["nb_donnees"] or 0 for g in reste)})
    return rows


def _totaux(par_groupe):
    return sum(g["nb_donnees"] or 0 for g in par_groupe), sum(g["nb_especes"] or 0 for g in par_groupe)


def texte_chiffres_site(par_groupe, periode: str, par_groupe_1km=None, rayon_km=1) -> str:
    """« Sur la période 2015-2025, 14 509 données pour 906 espèces ont été recensées au sein du site Natura 2000
    (54 000 données pour 1 300 espèces en comptant le kilomètre autour du site)... »"""
    total_d, total_e = _totaux(par_groupe)
    autour = ""
    if par_groupe_1km:
        d1, e1 = _totaux(par_groupe_1km)
        s = "s" if rayon_km > 1 else ""
        autour = (f" ({_fmt(d1)} données pour {_fmt(e1)} espèces en comptant le{s} {rayon_km:g} kilomètre{s} "
                  f"autour du site)")
    if not total_d:
        return f"Sur la période {periode}, aucune donnée n'est connue au sein du site Natura 2000{autour}."
    principal = max(par_groupe, key=lambda g: g["nb_donnees"] or 0)
    return (f"Sur la période {periode}, {_fmt(total_d)} données pour {_fmt(total_e)} espèces ont été recensées "
            f"au sein du site Natura 2000{autour}. Dans le site, le groupe le plus largement connu est celui des "
            f"{principal['groupe'].lower()} ({_fmt(principal['nb_especes'])} espèces / "
            f"{_fmt(principal['nb_donnees'])} données).")


def taxons_atlas(taxons, oiseaux_non_nicheurs=False) -> list[dict]:
    """Taxons N2000 cartographiés (hors chiroptères, qui ont leur propre atlas de gîtes), dans l'ordre du rapport.
    Oiseaux : nicheurs seulement, sauf si oiseaux_non_nicheurs."""
    retenus = [r for r in taxons if r.get("n2000") and r.get("ordre") != "Chiroptera"
               and (r.get("groupe") != "Oiseaux" or oiseaux_non_nicheurs or r.get("rang_nidif"))]
    return sorted(retenus, key=lambda r: (ordre_groupe(r.get("groupe")), r.get("groupe") or "", r.get("nom") or ""))


def titre_groupe_atlas(groupe: str, oiseaux_non_nicheurs=False) -> str:
    if groupe == "Oiseaux":
        return "Oiseaux" if oiseaux_non_nicheurs else "Oiseaux nicheurs"
    return groupe


# ---------------------------------------------------------------- atlas : ancienneté et fiche annuelle par espèce
# classe d'ancienneté d'une donnée (forme du symbole sur les cartes de l'atlas) : âge = année du rapport - année
ANCIENNETE = {"tres_recent": "2 dernières saisons", "recent": "2 à 5 ans", "ancien": "6 à 10 ans",
              "tres_ancien": "plus de 10 ans"}
NIDIF_CODES = {"Nicheur certain": (3, "C"), "Nicheur probable": (2, "Pr"), "Nicheur possible": (1, "Po")}


def classe_anciennete(annee, annee_ref: int, seuils=(1, 5, 10)) -> str | None:
    """Âge (années) <= seuils[0] : très récent (saison en cours et précédente) ; <= seuils[1] : récent ;
    <= seuils[2] : ancien ; au-delà : très ancien."""
    if annee is None:
        return None
    age = annee_ref - int(annee)
    for code, seuil in zip(ANCIENNETE, seuils):
        if age <= seuil:
            return code
    return "tres_ancien"


def ordre_dessin(anciennete, type_donnee) -> int:
    """Ordre de dessin d'une donnée sur l'atlas (croissant : la dernière dessinée est au-dessus). Le statut prime
    (autres données < nicheur possible < probable < certain), puis l'ancienneté (à statut égal, une donnée n'est
    jamais recouverte par une plus ancienne). Ancienneté inconnue : sous les autres données de même statut."""
    ages = list(ANCIENNETE)   # du plus récent au plus ancien
    age = ages.index(anciennete) if anciennete in ages else len(ages)
    statut = NIDIF_CODES.get(type_donnee, (0,))[0]
    return statut * (len(ages) + 1) + (len(ages) - age)


def texte_lecture_atlas(seuils=(1, 5, 10), rayon_m=50, min_annees=3, contenu=("graphique", "tableau")) -> str:
    """Paragraphe du Word expliquant la lecture des cartes de l'atlas et de la page qui suit chaque carte (mêmes
    paramètres que les cartes : atlas_anciennete_ans, recurrence_rayon_m, recurrence_min_annees, atlas_fiche)."""
    s1, s2, s3 = seuils
    formes = (f"rond : {s1 + 1} dernières saisons ; carré : {s1 + 1} à {s2} ans ; triangle : {s2 + 1} à {s3} ans ; "
              f"losange : plus de {s3} ans")
    parties = [x for x in ("graphique", "tableau") if x in contenu]
    detail = f" ({' et '.join(parties)})" if parties else ""
    return (f"Sur chaque carte, la couleur du symbole indique le type de donnée (nicheur certain, probable, possible "
            f"ou autre donnée) et sa forme l'ancienneté de l'observation ({formes}). Les statuts de nidification les "
            f"plus élevés sont dessinés au-dessus ; un anneau de couleur signale un indice de nidification récent "
            f"recouvert par un autre symbole. Un cercle blanc entoure les sites de nidification récurrents : "
            f"indices de nidification d'une même espèce situés à moins de {rayon_m:g} m les uns des autres "
            f"et notés au moins {min_annees} années différentes. La page qui suit chaque carte résume les "
            f"observations de l'espèce année par année{detail}, avec l'effectif le plus élevé observé.")


def _annees_txt(n: int) -> str:
    return f"{n} année{'s' if n > 1 else ''}"


def _enumeration(elements) -> str:
    """« a », « a et b », « a, b et c »."""
    elements = list(elements)
    return ", ".join(elements[:-1]) + " et " + elements[-1] if len(elements) > 1 else "".join(elements)


# fiche : séries du graphique (dans l'ordre d'empilement, de bas en haut) = types de donnée de la carte
TYPES_DONNEE = ("Nicheur certain", "Nicheur probable", "Nicheur possible", "Autres données")
# comportements sans information (nomenclature « Comportement » de la synthèse)
COMPORTEMENTS_VIDES = {"", "inconnu", "non renseigné", "ne sait pas", "pas de comportement"}


def contexte_effectif(point) -> str:
    """Ce que représente l'effectif d'une donnée : comportement saisi dans VisioNature, sinon comportement de la
    synthèse, sinon statut de nidification ; vide si rien n'est renseigné."""
    for champ in ("comportement", "behaviour"):
        valeur = (point.get(champ) or "").strip()
        if valeur.lower() not in COMPORTEMENTS_VIDES:
            return valeur
    return point.get("type_donnee", "").lower() if point.get("type_donnee") in NIDIF_CODES else ""


def _effectif(point) -> int:
    try:
        return int(point.get("count_max") or 0)
    except (TypeError, ValueError):
        return 0


def _phrase_presence(avec, annees) -> str:
    if not avec:
        return "Aucune donnée sur la période."
    if len(avec) == len(annees):
        return f"Espèce observée chaque année de {annees[0]} à {annees[-1]}."
    if len(avec) == 1:
        return f"Espèce observée 1 année sur {len(annees)}, en {avec[0]}."
    return f"Espèce observée {len(avec)} années sur {len(annees)}, de {avec[0]} à {avec[-1]}."


def _phrase_nidification(nidif, annees) -> str:
    """Années classées par niveau de nidification maximal de l'année."""
    niveau_max = {a: max(nidif[a])[0] for a in annees if nidif[a]}
    if not niveau_max:
        return "Aucun indice de nidification sur la période."
    par_niveau = {n: sorted(a for a, m in niveau_max.items() if m == n) for n in (3, 2, 1)}
    if len(par_niveau[3]) == len(annees):
        return "La nidification est certaine chaque année."
    mots = {3: "certaine", 2: "probable", 1: "possible"}
    parties = [f"{mots[n]} {_annees_txt(len(v))}" for n, v in par_niveau.items() if v]
    texte = f"La nidification est {_enumeration(parties)}"
    if par_niveau[3]:
        return texte + f" ; la dernière nidification certaine date de {par_niveau[3][-1]}."
    return texte + f", sans preuve de nidification certaine ; le dernier indice date de {max(niveau_max)}."


def fiche_espece(nom: str, points, annees, nb_sites_recurrents=0, oiseau=False) -> dict:
    """Fiche annuelle d'une espèce de l'atlas (2e page de sa carte) : texte de synthèse, tableau par année et séries
    du graphique. Tableau : données ; oiseaux : données de nidification, niveau de nidification maximal, effectif
    maximal des données de nidification et des autres données (autres groupes : effectif maximal).
    points : données de l'espèce (annee, type_donnee, count_max, date, comportement, behaviour) ;
    annees : années de la période du rapport."""
    annees = list(annees)
    par_an = {a: [p for p in points if p.get("annee") == a] for a in annees}
    donnees = {a: len(v) for a, v in par_an.items()}
    nidif = {a: [NIDIF_CODES[p["type_donnee"]] for p in v if p.get("type_donnee") in NIDIF_CODES]
             for a, v in par_an.items()}

    def eff_max(a, filtre=lambda p: True):
        return max((_effectif(p) for p in par_an[a] if filtre(p)), default=0) or ""

    est_nidif = lambda p: p.get("type_donnee") in NIDIF_CODES   # noqa: E731
    lignes = [{"ligne": "Données", **{str(a): donnees[a] or "" for a in annees}}]
    phrases = [_phrase_presence([a for a in annees if donnees[a]], annees)]
    if oiseau:
        lignes += [{"ligne": "Données de nidification", **{str(a): len(nidif[a]) or "" for a in annees}},
                   {"ligne": "Nidification maximale", **{str(a): max(nidif[a])[1] if nidif[a] else "" for a in annees}},
                   {"ligne": "Effectif max nidif.", **{str(a): eff_max(a, est_nidif) for a in annees}},
                   {"ligne": "Effectif max autres",
                    **{str(a): eff_max(a, lambda p: not est_nidif(p)) for a in annees}}]
        phrases.append(_phrase_nidification(nidif, annees))
        if nb_sites_recurrents:
            pl = "s" if nb_sites_recurrents > 1 else ""
            verbe = "sont identifiés (cercles blancs" if pl else "est identifié (cercle blanc"
            phrases.append(f"{nb_sites_recurrents} site{pl} de nidification récurrent{pl} {verbe} sur la carte).")
        elif any(nidif.values()):
            phrases.append("Aucun site de nidification récurrent n'est identifié.")
    else:
        lignes.append({"ligne": "Effectif max", **{str(a): eff_max(a) for a in annees}})
    # effectif le plus élevé de la période, avec ce qu'il représente (migration, nidification...)
    record = max((p for v in par_an.values() for p in v), key=_effectif, default=None)
    if record is not None and _effectif(record) > 1:
        date = record.get("date")
        quand = f", le {date:%d/%m/%Y}" if hasattr(date, "strftime") else (f", en {record['annee']}")
        contexte = contexte_effectif(record)
        phrases.append(f"L'effectif le plus élevé est de {_effectif(record)} individus{quand}"
                       + (f" ({contexte})" if contexte else "") + ".")
    series = {ty: [sum(p.get("type_donnee") == ty for p in par_an[a]) for a in annees] for ty in TYPES_DONNEE}
    colonnes = [("ligne", "")] + [(str(a), str(a)) for a in annees]
    return {"titre": nom, "texte": " ".join(phrases), "colonnes": colonnes, "lignes": lignes,
            "annees": annees, "series": {ty: v for ty, v in series.items() if any(v)}}


# libellés des sources de données (champ name_source de la synthèse) ; inconnue = nom brut
SOURCES_LIBELLES = {
    "faune-france": "VisioNature (Réseau LPO)",
    "dbChiroGCRA": "DBchiro (GCRA)",
    "gn2pg_cen_savoie": "CEN Savoie",
    "gn2pg_cen_auv": "CEN Auvergne",
    "orb_invertebres": "ORB (invertébrés)",
    "api2gn_gbif": "GBIF",
    "sinp": "SINP",
}


SIGLES = {"pnr": "PNR", "cen": "CEN", "cd": "CD", "pnv": "PN Vanoise", "orb": "ORB", "lpo": "LPO", "onf": "ONF"}


def libelle_source(source: str, libelles=None) -> str:
    """Libellé lisible d'une source : table de libellés, sinon nom nettoyé (« gn2pg_pnr_bauges » -> « PNR Bauges »)."""
    libelles = {**SOURCES_LIBELLES, **(libelles or {})}
    if source in libelles:
        return libelles[source]
    mots = re.sub(r"^(gn2pg|api2gn)_", "", source or "").split("_")
    out = []
    for m in mots:
        sigle = re.fullmatch(r"([a-z]+)(\d*)", m.lower())
        if sigle and sigle.group(1) in SIGLES:
            out.append(SIGLES[sigle.group(1)] + (f" {sigle.group(2)}" if sigle.group(2) else ""))
        else:
            out.append(m.capitalize() if m.islower() else m)
    return " ".join(out)


def texte_sources(sources, libelles=None, seuil_pct=1.0) -> str:
    """« VisioNature (Réseau LPO), DBchiro (GCRA), CEN Savoie et autres partenaires » : sources d'au moins
    seuil_pct % des données, de la plus fournie à la moins."""
    total = sum(s["n"] for s in sources) or 1
    noms, autres = [], False
    for s in sorted(sources, key=lambda s: -s["n"]):
        nom = libelle_source(s["source"], libelles)
        if 100 * s["n"] / total < seuil_pct:
            autres = True
        elif nom and nom not in noms:
            noms.append(nom)
    return ", ".join(noms) + (" et autres partenaires" if autres else "")


def texte_rayons(defaut_km, ordres: dict, especes: dict, noms: dict) -> str:
    """Phrase des méthodes sur les rayons de prise en compte, générée depuis le dossier.toml."""
    par_km: dict = {}
    ordres = dict(ordres or {})
    if RAPACES <= set(ordres) and len({ordres[o] for o in RAPACES}) == 1:
        par_km.setdefault(ordres[next(iter(RAPACES))], []).append("les rapaces")
        ordres = {o: km for o, km in ordres.items() if o not in RAPACES}
    for ordre, km in ordres.items():
        par_km.setdefault(km, []).append(f"les {ORDRES_LIBELLES.get(ordre, ordre)}")
    par_km_especes: dict = {}
    for nom_sci, km in (especes or {}).items():
        par_km_especes.setdefault(km, []).append(noms.get(nom_sci, nom_sci))
    for km, sp in par_km_especes.items():
        # noms entre parenthèses : pas d'article à accorder (« la Loutre », « le Loup »)
        par_km.setdefault(km, []).append(f"certaines espèces ({', '.join(sp)})")
    texte = (f"Un tampon de {defaut_km:g} kilomètre{'s' if defaut_km > 1 else ''} autour du site a été pris en "
             f"compte pour visualiser la différence ou la complémentarité entre le site et ses environs proches.")
    if par_km:
        details = [f"à {km:g} km pour {_liste(qui)}" for km, qui in sorted(par_km.items())]
        texte += (" Pour les espèces à grand rayon de déplacement ou à grand territoire, cette zone a été élargie "
                  + _liste(details) + ".")
    return texte
