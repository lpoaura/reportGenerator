"""Calculs et textes de l'état des connaissances par maille (fonctions pures, testées sans base).

Vocabulaire passé par les briques (paramètres du dossier) : `zone` = « le site » (Natura 2000) ou « la zone
d'étude » ; `renvoi` = où lire les espèces d'un groupe non cartographié (atlas, tableaux...).
"""

import re
import unicodedata

# ordre des groupes dans les tableaux et l'atlas (les autres suivent, par ordre alphabétique)
ORDRE_GROUPES = ["Oiseaux", "Mammifères", "Chauves-souris", "Amphibiens", "Reptiles", "Poissons", "Odonates",
                 "Papillons de jour", "Papillons de nuit", "Orthoptères", "Coléoptères"]
TOUS_GROUPES = "Tous groupes"

# lecture croisée richesse x effort : 3 niveaux chacun (seuils fixes, identiques pour tous les groupes)
SEUILS_EFFORT_JOURS = (3, 10)     # 1-2 jours / 3-9 jours / 10 jours et plus
SEUILS_RICHESSE_PCT = (25, 50)    # < 25 % / 25-50 % / > 50 % du pool local
NIVEAUX = ("faible", "moyen", "fort")


def ordre_groupe(groupe: str) -> int:
    return ORDRE_GROUPES.index(groupe) if groupe in ORDRE_GROUPES else len(ORDRE_GROUPES)


def cle(texte: str) -> str:
    """Clé stable pour un nom de fichier de carte : « Martin-pêcheur d'Europe » -> « martin_pecheur_d_europe »."""
    ascii_ = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return "_".join(re.findall(r"[a-z0-9]+", ascii_.lower())) or "sans_nom"


def _liste(items) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " et " + items[-1]


def _niveau(valeur, seuils) -> int:
    return 0 if valeur < seuils[0] else (1 if valeur < seuils[1] else 2)


def _mediane(valeurs):
    v = sorted(valeurs)
    return (v[len(v) // 2] + v[(len(v) - 1) // 2]) / 2 if v else 0


def _jours(valeur) -> str:
    return f"{valeur:g}".replace(".", ",") + (" jours" if valeur >= 2 else " jour")


# ---------------------------------------------------------------- indicateurs par maille
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


def medianes_jours(mailles) -> dict:
    """Médiane, par groupe, du nombre de jours d'observation du groupe dans les mailles où il a des données."""
    par_groupe: dict = {}
    for m in mailles:
        if m["groupe"] != TOUS_GROUPES:
            par_groupe.setdefault(m["groupe"], []).append(m["nb_jours"] or 0)
    return {g: _mediane(j) for g, j in par_groupe.items()}


def groupes_cartographies(mailles, especes_site: dict, min_especes_site=4) -> list[str]:
    """Groupes cartographiés : au moins min_especes_site espèces dans la zone (en dessous, les tableaux ou l'atlas
    des espèces suffisent). L'effort de prospection ne bloque pas la carte : il déclenche un avertissement."""
    presents = {m["groupe"] for m in mailles if m["groupe"] != TOUS_GROUPES}
    retenus = [g for g in presents if (especes_site.get(g) or 0) >= min_especes_site]
    return sorted(retenus, key=lambda g: (ordre_groupe(g), g))


def synthese_groupes(mailles, site_par_groupe: dict, pool_local: dict, pool_regional: dict,
                     cartographies, seuil_donnees=2, especes_site=None) -> list[dict]:
    """Tableau par groupe (site_par_groupe : espèces de l'emprise des mailles ; especes_site : espèces dans la
    zone) : espèces, pool local, pool régional, mailles, effort."""
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


# ---------------------------------------------------------------- textes du Word
def texte_groupes_cartographies(groupes, min_especes_site=4, alertes=None, seuil_jours=2, zone="le site",
                                renvoi="l'atlas et le tableau ci-dessus") -> str:
    """Phrase du Word : groupes cartographiés, critère retenu et groupes à prospection ponctuelle (alertes :
    {groupe: médiane des jours par maille} sous seuil_jours)."""
    critere = f"au moins {min_especes_site} espèces connues dans {zone}"
    if not groupes:
        return f"Aucun groupe ne compte {critere} : les espèces se consultent dans {renvoi}."
    noms = _liste(g.lower() for g in groupes)
    texte = (f"Les groupes comptant {critere} sont cartographiés, soit {len(groupes)} "
             f"groupe{'s' if len(groupes) > 1 else ''} : {noms}. En dessous, une carte par maille "
             f"apporte peu : les espèces se consultent plutôt dans {renvoi}.")
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


def texte_emprise(zone="le site", rayon_km=1.0) -> str:
    """« le site et le kilomètre autour », « la zone d'étude et les 6 km autour »..."""
    if not rayon_km:
        return zone
    autour = "le kilomètre autour" if rayon_km == 1 else f"les {rayon_km:g} km autour".replace(".", ",")
    return f"{zone} et {autour}"


# ---------------------------------------------------------------- emprises des cartes (rectangles Lambert 93)
def marge_m(rayon_m: float, ratio=0.1, minimum_m=500.0) -> float:
    """Marge autour d'un contour : proportionnelle au rayon, avec un minimum."""
    return max(minimum_m, ratio * rayon_m)


def emprise_contour(bbox, distance_m: float) -> list[float]:
    """Rectangle englobant le contour à distance_m de la zone (= enveloppe élargie) : [xmin, ymin, xmax, ymax]."""
    xmin, ymin, xmax, ymax = bbox
    return [xmin - distance_m, ymin - distance_m, xmax + distance_m, ymax + distance_m]


def rectangle_wkt(rect) -> str:
    xmin, ymin, xmax, ymax = rect
    return f"POLYGON(({xmin} {ymin},{xmax} {ymin},{xmax} {ymax},{xmin} {ymax},{xmin} {ymin}))"
