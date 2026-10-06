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
    "sensibilite", "id_rang", "n2k",
]
# rangs comptés comme espèces (les chiroptères gardent aussi genres et complexes)
ESPECE_RANGS = (None, "ES", "SSES")
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
            # genres et complexes comptent dans les données, pas dans le nombre d'espèces
            "nb_especes": sum(1 for sp in presentes if sp.get("id_rang") in ESPECE_RANGS),
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

    phrases = [
        f"Les données naturalistes de la base de données VisioNature concernent "
        f"{_fmt(total['nb_obs'])} données, regroupant {total['nb_especes']} espèces d'oiseaux "
        f"dans la zone étendue correspondant à un rayon de {max(anneaux_km):g} kilomètres "
        f"autour de la zone du projet."
    ]
    phrases += phrases_anneaux(par_anneau, anneaux_km, "inventoriées", "observations")
    # un seul paragraphe : des retours à la ligne forcés étirent les lignes justifiées
    return " ".join(phrases)


def _pl(n, mot: str) -> str:
    return f"{_fmt(n)} {mot}{'s' if (n or 0) > 1 else ''}"


def phrases_anneaux(par_anneau: dict, anneaux_km, verbe: str, unite: str,
                    unite_anneaux: str = "donnée") -> list[str]:
    """Une phrase par anneau, du plus éloigné à la zone d'étude (« aucune donnée » si vide).
    unite_anneaux : unité comptée (singulier), ex. « observation » pour les chiroptères."""
    bornes = [0, *anneaux_km]
    phrases = []
    for i in range(len(anneaux_km), 0, -1):
        ligne = par_anneau[i]
        debut = f"Entre {bornes[i - 1]:g} et {bornes[i]:g} km autour du projet"
        if not ligne["nb_obs"]:
            phrases.append(f"{debut}, aucune donnée n'est connue.")
        elif not ligne["nb_especes"]:  # uniquement des genres / complexes (chiroptères)
            phrases.append(f"{debut}, on compte {_pl(ligne['nb_obs'], unite_anneaux)}, "
                           f"sans identification à l'espèce.")
        else:
            phrases.append(f"{debut}, on compte {_pl(ligne['nb_obs'], unite_anneaux)} concernant "
                           f"{_pl(ligne['nb_especes'], 'espèce')}.")
    zone = par_anneau[0]
    debut = "Dans la zone d'étude immédiate du projet"
    if not zone["nb_obs"]:
        phrases.append("Aucune donnée n'est connue dans la zone d'étude immédiate du projet.")
    elif not zone["nb_especes"]:
        phrases.append(f"{debut}, on compte {_pl(zone['nb_obs'], unite_anneaux)}, sans identification à l'espèce.")
    else:
        pluriel = zone["nb_especes"] > 1
        phrases.append(f"{debut}, {_pl(zone['nb_especes'], 'espèce')} {'ont été' if pluriel else 'a été'} "
                       f"{verbe if pluriel else verbe.rstrip('s')} pour {_fmt(zone['nb_obs'])} {unite}.")
    return phrases


def phrase_precautions(pct_hors_region, region_libelle: str, nb_donnees: int, nb_lieu_dit: int,
                       seuil_hors_region=1, seuil_lieu_dit=5) -> str:
    """Mises en garde de lecture (zone hors région sans données, données localisées au lieu-dit)."""
    phrases = []
    if pct_hors_region is not None and float(pct_hors_region) >= seuil_hors_region:
        phrases.append(
            f"{float(pct_hors_region):.0f} % de l'aire d'étude se situe hors de la région {region_libelle}, "
            f"où la base de données ne contient pas de données : l'absence de données dans ce secteur ne "
            f"traduit pas une absence d'espèces."
        )
    pct_lieu_dit = 100 * nb_lieu_dit / nb_donnees if nb_donnees else 0
    if pct_lieu_dit >= seuil_lieu_dit:
        phrases.append(
            f"{pct_lieu_dit:.0f} % des données sont localisées au lieu-dit (centroïde) et non au point "
            f"précis : sur les cartes, les fortes concentrations de points correspondent souvent à ces "
            f"lieux-dits."
        )
    return ("Précautions de lecture : " + " ".join(phrases)) if phrases else ""


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
