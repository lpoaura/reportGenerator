"""
Mise en forme des données éoliennes (sans base de données : testable).

Les anneaux sont disjoints ("donuts") : anneau_ordre 0 = zone d'étude,
i = entre le contour i-1 et le contour i. Les totaux "Ensemble des zones"
sont donc de simples sommes, sans double comptage.
"""

from datetime import datetime

NIDIF_LABELS = {3: "Nicheur certain", 2: "Nicheur probable", 1: "Nicheur possible", 0: ""}
SPECIES_ATTRS = [
    "cd_ref", "nom_vern", "lb_nom", "famille", "ordre", "prot_nat",
    "lr_france", "lr_fr_nich", "lr_fr_hiv", "lr_fr_migr", "lr_aura", "lr_auv", "lr_ra",
    "sensibilite",
]
ALL = "all"


def ring_labels(anneaux_km) -> list[str]:
    return ["Zone d'étude"] + [f"Contour {km:g} km" for km in anneaux_km]


def _max(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def pivot_par_anneau(rows) -> list[dict]:
    """Lignes (espèce, anneau) -> une ligne par espèce avec des colonnes
    nb_obs__<i>, derniere_annee__<i>, effectif_max__<i> et __all."""
    species: dict = {}
    for row in rows:
        sp = species.get(row["cd_ref"])
        if sp is None:
            sp = {k: row.get(k) for k in SPECIES_ATTRS}
            sp.update({f"nb_obs__{ALL}": 0, f"derniere_annee__{ALL}": None,
                       f"effectif_max__{ALL}": None, "code_nidif": 0})
            species[row["cd_ref"]] = sp

        i = row["anneau_ordre"]
        sp[f"nb_obs__{i}"] = row["nb_obs"]
        sp[f"derniere_annee__{i}"] = row["derniere_annee"]
        sp[f"effectif_max__{i}"] = row.get("effectif_max")
        sp[f"nb_obs__{ALL}"] += row["nb_obs"] or 0
        sp[f"derniere_annee__{ALL}"] = _max(sp[f"derniere_annee__{ALL}"], row["derniere_annee"])
        sp[f"effectif_max__{ALL}"] = _max(sp[f"effectif_max__{ALL}"], row.get("effectif_max"))
        sp["code_nidif"] = max(sp["code_nidif"], row.get("code_nidif") or 0)

    for sp in species.values():
        sp["statut_nidif"] = NIDIF_LABELS.get(sp["code_nidif"], "")
    return sorted(species.values(), key=lambda sp: (sp["nom_vern"] or "", sp["lb_nom"] or ""))


def lr_codes(value) -> set[str]:
    """'LC, NAm, VUw' -> {'LC', 'NAm', 'VUw'} (les suffixes m/w = migrateur/hivernant
    ne correspondent donc pas aux catégories nicheur 'VU', 'EN'...)."""
    if not value:
        return set()
    return {code.strip() for code in str(value).split(",") if code.strip()}


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def est_enjeu(sp: dict, lr_regionale="lr_aura", lr_statuts=("CR", "EN", "VU"), sensibilite_min=2,
              familles=("Ardeidae", "Ciconiidae", "Laridae", "Gruidae"),
              ordres=("Accipitriformes", "Falconiformes", "Strigiformes")) -> bool:
    """Critères "espèce à enjeux" des scripts R (traitement_generale_v2.R),
    avec la liste rouge régionale réellement appliquée (bug du script R)."""
    sensi = _to_float(sp.get("sensibilite"))
    return bool(
        lr_codes(sp.get(lr_regionale)) & set(lr_statuts)
        or lr_codes(sp.get("lr_fr_nich")) & set(lr_statuts)
        or (sensi is not None and sensi > sensibilite_min)
        or sp.get("famille") in familles
        or sp.get("ordre") in ordres
    )


def resume_par_anneau(species: list[dict], anneaux_km) -> list[dict]:
    """Tableau "Répartition des données" : une ligne par anneau + toute la zone."""
    labels = ring_labels(anneaux_km)
    lignes = []
    for i, label in [*enumerate(labels), (ALL, "Toute la zone")]:
        presentes = [sp for sp in species if sp.get(f"nb_obs__{i}")]
        annees = [sp[f"derniere_annee__{i}"] for sp in presentes if sp.get(f"derniere_annee__{i}")]
        lignes.append({
            "anneau": i,
            "zone": label,
            "nb_obs": sum(sp[f"nb_obs__{i}"] for sp in presentes),
            "nb_especes": len(presentes),
            "derniere_annee": max(annees) if annees else "",
        })
    return lignes


def _fmt(n) -> str:
    return f"{n:,}".replace(",", " ")


def texte_connaissance(resume: list[dict], anneaux_km) -> str:
    """Texte VARIABLE_CONNAISSANCE_OISEAUX (repris du script R, construit
    à partir des anneaux réels au lieu de libellés écrits en dur)."""
    par_anneau = {ligne["anneau"]: ligne for ligne in resume}
    total = par_anneau[ALL]
    bornes = [0, *anneaux_km]

    phrases = [
        f"Les données naturalistes de la base de données VisioNature concernent "
        f"{_fmt(total['nb_obs'])} données, regroupant {total['nb_especes']} espèces d'oiseaux "
        f"dans la zone étendue correspondant à un rayon de {max(anneaux_km):g} kilomètres "
        f"autour de la zone du projet."
    ]
    for i in range(len(anneaux_km), 0, -1):
        ligne = par_anneau[i]
        phrases.append(
            f"Entre {bornes[i - 1]:g} et {bornes[i]:g} km autour du projet, on compte "
            f"{_fmt(ligne['nb_obs'])} données concernant {ligne['nb_especes']} espèces."
        )
    zone = par_anneau[0]
    phrases.append(
        f"Dans la zone d'étude immédiate du projet, {zone['nb_especes']} espèces ont été "
        f"inventoriées pour {_fmt(zone['nb_obs'])} observations."
    )
    # un seul paragraphe : des retours à la ligne forcés étirent les lignes justifiées
    return " ".join(phrases)


def periode_etude(annees: int, now: datetime | None = None) -> str:
    year = (now or datetime.now()).year
    return f"({year - annees} à {year})"


def anneaux_texte(anneaux_km) -> str:
    kms = [f"{km:g} km" for km in anneaux_km]
    return kms[0] if len(kms) == 1 else ", ".join(kms[:-1]) + " et " + kms[-1]


def sensibilite_totale(row: dict, plafond=None) -> int:
    total = int(float(row.get("sensi_especes") or 0)) + sum(
        int(row.get(k) or 0) for k in ("bonus_nidif", "bonus_dortoir", "bonus_migration")
    )
    return min(total, plafond) if plafond else total
