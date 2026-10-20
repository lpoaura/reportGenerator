"""Calculs et textes du dossier Natura 2000 (fonctions pures, testées sans base)."""

import re
import unicodedata

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


def marge_m(rayon_m: float, ratio=0.1, minimum_m=500.0) -> float:
    """Marge autour d'un contour : proportionnelle au rayon, avec un minimum."""
    return max(minimum_m, ratio * rayon_m)


def emprise_contour(bbox, distance_m: float) -> list[float]:
    """Rectangle englobant le contour à distance_m du site (= enveloppe du site élargie) : [xmin, ymin, xmax, ymax]."""
    xmin, ymin, xmax, ymax = bbox
    return [xmin - distance_m, ymin - distance_m, xmax + distance_m, ymax + distance_m]


def rectangle_wkt(rect) -> str:
    xmin, ymin, xmax, ymax = rect
    return f"POLYGON(({xmin} {ymin},{xmax} {ymin},{xmax} {ymax},{xmin} {ymax},{xmin} {ymin}))"


# ---------------------------------------------------------------- état des connaissances (cartes par maille)
# lecture croisée richesse x effort : 3 niveaux chacun (seuils fixes, identiques pour tous les groupes)
SEUILS_EFFORT_JOURS = (3, 10)     # 1-2 jours / 3-9 jours / 10 jours et plus
SEUILS_RICHESSE_PCT = (25, 50)    # < 25 % / 25-50 % / > 50 % du pool local
NIVEAUX = ("faible", "moyen", "fort")


def _niveau(valeur, seuils) -> int:
    return 0 if valeur < seuils[0] else (1 if valeur < seuils[1] else 2)


def indicateurs_mailles(mailles, pool_local: dict, seuil_donnees=2) -> list[dict]:
    """Ajoute aux mailles : % du pool local du groupe, « peu de données » (< seuil_donnees) et la classe
    croisée richesse x effort (« e<effort>r<richesse> », 0 à 2 chacun)."""
    out = []
    for m in mailles:
        pool = pool_local.get(m["groupe"])
        pct = round(100 * (m["nb_especes"] or 0) / pool, 1) if pool else None
        effort = _niveau(m["nb_jours"] or 0, SEUILS_EFFORT_JOURS)
        richesse = _niveau(pct or 0, SEUILS_RICHESSE_PCT)
        out.append({**m, "pct_pool_local": pct, "peu_donnees": (m["nb_donnees"] or 0) < seuil_donnees,
                    "effort": NIVEAUX[effort], "richesse": NIVEAUX[richesse],
                    "classe_croisee": f"e{effort}r{richesse}"})
    return out


def _mediane(valeurs):
    v = sorted(valeurs)
    return (v[len(v) // 2] + v[(len(v) - 1) // 2]) / 2 if v else 0


def medianes_jours(mailles) -> dict:
    """Médiane, par groupe, du nombre de jours d'observation du groupe dans les mailles où il a des données."""
    par_groupe: dict = {}
    for m in mailles:
        if m["groupe"] != "Tous groupes":
            par_groupe.setdefault(m["groupe"], []).append(m["nb_jours"] or 0)
    return {g: _mediane(j) for g, j in par_groupe.items()}


def groupes_cartographies(mailles, especes_site: dict, min_especes_site=4) -> list[str]:
    """Groupes cartographiés : au moins min_especes_site espèces dans le site (en dessous, l'atlas des espèces et
    le tableau suffisent). L'effort de prospection ne bloque pas la carte : il déclenche un avertissement."""
    presents = {m["groupe"] for m in mailles if m["groupe"] != "Tous groupes"}
    retenus = [g for g in presents if (especes_site.get(g) or 0) >= min_especes_site]
    return sorted(retenus, key=lambda g: (ordre_groupe(g), g))


def _jours(valeur) -> str:
    return f"{valeur:g}".replace(".", ",") + (" jours" if valeur >= 2 else " jour")


def texte_groupes_cartographies(groupes, min_especes_site=4, alertes=None, seuil_jours=2) -> str:
    """Phrase du Word : groupes cartographiés, critère retenu et groupes à prospection ponctuelle (alertes :
    {groupe: médiane des jours par maille} sous seuil_jours)."""
    critere = f"au moins {min_especes_site} espèces connues dans le site"
    if not groupes:
        return (f"Aucun groupe ne compte {critere} : les espèces se consultent dans l'atlas et le tableau "
                "ci-dessus.")
    noms = _liste(g.lower() for g in groupes)
    texte = (f"Les groupes comptant {critere} sont cartographiés, soit {len(groupes)} "
             f"groupe{'s' if len(groupes) > 1 else ''} : {noms}. En dessous, une carte par maille "
             "apporte peu : les espèces se consultent plutôt dans l'atlas et le tableau ci-dessus.")
    alertes = [g.lower() for g in groupes if g in (alertes or {})]
    if alertes:
        texte += (f" Pour {_liste(alertes)}, la moitié au moins des mailles n'ont été prospectées qu'un jour "
                  f"(médiane inférieure à {_jours(seuil_jours)} d'observation par maille) : leurs cartes sont "
                  "précédées d'un avertissement. Elles reposent sur des passages ponctuels, souvent des campagnes "
                  "d'inventaire d'une journée. Menée par un spécialiste dans de bonnes conditions, une telle "
                  "campagne peut être presque complète, et la carte reste utile pour voir où les espèces ont été "
                  "notées et si elles sont regroupées ou réparties. Mais les écarts entre mailles peuvent aussi "
                  "tenir aux dates et aux lieux de passage plutôt qu'aux milieux, et sur la carte « Richesse et "
                  "prospection » la plupart des mailles sont logiquement dans la ligne « 1 - 2 j ».")
    return texte


def texte_avertissement_effort(mediane, seuil_jours=2):
    """Avertissement court (la carte doit tenir sur la même page) avant les cartes d'un groupe prospecté surtout
    ponctuellement (médiane < seuil) ; l'explication complète est dans texte_groupes_cartographies."""
    if mediane >= seuil_jours:
        return None
    return (f"À lire avec prudence : prospection surtout ponctuelle (médiane : {_jours(mediane)} d'observation "
            f"par maille, pour un seuil de {_jours(seuil_jours)}). Les écarts entre mailles peuvent tenir aux dates "
            "et aux lieux de passage autant qu'aux milieux.")


def texte_lecture_croisee(seuils_effort=SEUILS_EFFORT_JOURS, seuils_richesse=SEUILS_RICHESSE_PCT) -> str:
    """Phrase du Word : classes de la carte « Richesse et prospection »."""
    (e1, e2), (r1, r2) = seuils_effort, seuils_richesse
    return (f"L'effort est classé en trois niveaux (1 à {e1 - 1} jours, {e1} à {e2 - 1} jours, {e2} jours et plus), "
            f"de même que la richesse (moins de {r1} %, {r1} à {r2} %, plus de {r2} % des espèces locales).")


def synthese_groupes(mailles, site_par_groupe: dict, pool_local: dict, pool_regional: dict,
                     cartographies, seuil_donnees=2, especes_site=None) -> list[dict]:
    """Tableau par groupe (site_par_groupe : espèces du site + 1 km ; especes_site : espèces dans le site) :
    espèces, pool local, pool régional, mailles, effort."""
    rows = []
    for g in sorted(site_par_groupe, key=lambda g: (ordre_groupe(g), g)):
        mg = [m for m in mailles if m["groupe"] == g]
        n, local, region = site_par_groupe[g], pool_local.get(g), pool_regional.get(g)
        jours = sorted(m["nb_jours"] or 0 for m in mg)
        rows.append({
            "groupe": g, "nb_especes_site": (especes_site or {}).get(g) or 0, "nb_especes": n, "pool_local": local,
            "pct_local": f"{round(100 * n / local)} %" if local else "",
            "pool_regional": region, "pct_regional": f"{round(100 * n / region)} %" if region else "",
            "nb_mailles": len(mg), "mailles_peu_donnees": sum(1 for m in mg if (m["nb_donnees"] or 0) < seuil_donnees),
            "jours_median": f"{_mediane(jours):g}".replace(".", ","),
            "carte": "oui" if g in cartographies else "non",
        })
    return rows


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


def cle(texte: str) -> str:
    """Clé stable pour un nom de fichier de carte : « Martin-pêcheur d'Europe » -> « martin_pecheur_d_europe »."""
    ascii_ = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return "_".join(re.findall(r"[a-z0-9]+", ascii_.lower())) or "sans_nom"


# ordre des groupes dans le rapport (cartes, atlas) : vertébrés puis principaux groupes d'insectes ; les autres ensuite
ORDRE_GROUPES = [*(g for g, _ in GROUPES_ANNEXES), "Odonates", "Papillons de jour", "Papillons de nuit",
                 "Orthoptères", "Coléoptères"]


def ordre_groupe(groupe: str) -> int:
    return ORDRE_GROUPES.index(groupe) if groupe in ORDRE_GROUPES else len(ORDRE_GROUPES)


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
