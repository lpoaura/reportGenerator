"""
Indice de vulnérabilité des oiseaux à l'éolien (sans base de données : testable).

Matrice du protocole de suivi environnemental des parcs éoliens terrestres (MEDDE 2015) :
vulnérabilité = (note de patrimonialité + note de sensibilité éolienne) / 2, cf. METHODO.md §4 bis.

Note de patrimonialité : la plus forte des listes rouges qui correspondent à un statut de l'espèce
sur l'aire d'étude :
- LR régionale (AuRA) et LR France des nicheurs : toujours ;
- LR France des migrateurs : seulement si l'espèce a au moins une donnée de migration ;
- LR France des hivernants : seulement si l'espèce a au moins une donnée d'hivernage (1er décembre - 31 janvier).
La ligne « espèce non protégée = 0,5 » de la matrice n'est pas appliquée (décision : elle ferait
disparaître des espèces chassables menacées, ex. Bécassine des marais CR).
"""

from reportgenerator.analysis.eolien.tables import _to_float, lr_codes

# catégories des listes rouges -> note de patrimonialité (matrice : CR-EN = 5 ... DD, NA, NE = 1)
NOTES_LR = {"RE": 5, "CR": 5, "EN": 5, "VU": 4, "NT": 3, "LC": 2, "DD": 1, "NA": 1, "NE": 1}
NOTE_SANS_STATUT = 1   # aucune liste rouge : non évaluée (NE)

# couleurs des cellules « Vulnérabilité » (dégradé de la matrice, à partir de 2,5)
COULEURS = {2.5: "FBE5D6", 3.0: "F8CBAD", 3.5: "F4B183", 4.0: "E46C0A", 4.5: "C55A11"}


def note_liste_rouge(valeur):
    """'CR' -> 5 ; 'LC, NAm, DDw' (lr_france agrégée) -> 2 : les codes suffixés m / w sont ignorés,
    les catégories migrateur et hivernant étant lues dans lr_fr_migr et lr_fr_hiv. Vide -> None."""
    notes = [NOTES_LR[code] for code in lr_codes(valeur) if code in NOTES_LR]
    return max(notes) if notes else None


def note_patrimoniale(sp: dict, lr_regionale="lr_aura") -> int:
    listes = [sp.get(lr_regionale), sp.get("lr_fr_nich")]
    if sp.get("migrateur"):
        listes.append(sp.get("lr_fr_migr"))
    if sp.get("hivernant"):
        listes.append(sp.get("lr_fr_hiv"))
    notes = [n for n in map(note_liste_rouge, listes) if n is not None]
    return max(notes, default=NOTE_SANS_STATUT)


def indice_vulnerabilite(sp: dict, lr_regionale="lr_aura") -> float:
    """(patrimonialité + sensibilité) / 2 ; sensibilité inconnue = 0 (comme le rapport de référence)."""
    sensibilite = _to_float(sp.get("sensibilite")) or 0
    return (note_patrimoniale(sp, lr_regionale) + sensibilite) / 2


def depasse_seuil(vulnerabilite, seuil=2.5, inclus=False) -> bool:
    """vulnerabilite > seuil (ou >= si inclus)."""
    if vulnerabilite is None:
        return False
    return vulnerabilite >= seuil if inclus else vulnerabilite > seuil


def libelle_seuil(seuil=2.5, inclus=False) -> str:
    """« supérieur à 2,5 » / « supérieur ou égal à 2,5 »."""
    return f"supérieur {'ou égal ' if inclus else ''}à {fmt_note(seuil)}"


def fmt_note(note) -> str:
    """3.5 -> '3,5' ; 3.0 -> '3' ; None -> ''."""
    if note is None:
        return ""
    note = float(note)
    return str(int(note)) if note == int(note) else f"{note:g}".replace(".", ",")


def couleur_texte(note):
    """Texte blanc sur les fonds foncés (4 et plus), sinon couleur par défaut (None)."""
    return "FFFFFF" if note is not None and float(note) >= 4 else None


def couleur(note):
    """Couleur de fond d'une cellule « Vulnérabilité » (None : pas de couleur)."""
    if note is None:
        return None
    paliers = [p for p in sorted(COULEURS) if float(note) >= p]
    return COULEURS[paliers[-1]] if paliers else None


def statut_biologique(sp: dict) -> str:
    """« Nicheur certain, migrateur, hivernant » : statuts observés sur l'aire d'étude, ceux qui déterminent
    les listes rouges prises en compte (migrateur, hivernant) dans la note de patrimonialité."""
    parts = [sp["statut_nidif"]] if sp.get("statut_nidif") else []
    parts += [statut for statut in ("migrateur", "hivernant") if sp.get(statut)]
    texte = ", ".join(parts)
    return texte[:1].upper() + texte[1:]


def tri_vulnerabilite(species: list[dict]) -> list[dict]:
    """Tableau principal : vulnérabilité décroissante, puis nombre de données décroissant, puis nom."""
    return sorted(species, key=lambda sp: (-(sp.get("vulnerabilite") or 0), -(sp.get("nb_obs__all") or 0),
                                           sp.get("nom_vern") or ""))


def texte_vulnerabilite(species: list[dict], seuil=2.5, inclus=False) -> str:
    """« Au total, N espèces … dont M nicheuses, parmi les Z espèces … » (nicheur possible, probable ou certain)."""
    retenues = [sp for sp in species if depasse_seuil(sp.get("vulnerabilite"), seuil, inclus)]
    nicheuses = [sp for sp in retenues if (sp.get("code_nidif") or 0) >= 1]
    n, m, z = len(retenues), len(nicheuses), len(species)
    if not n:
        return (f"Aucune des {z} espèces d'oiseaux observées sur l'aire d'étude n'obtient un indice de "
                f"vulnérabilité {libelle_seuil(seuil, inclus)}.")
    especes = "espèces d'oiseaux obtiennent" if n > 1 else "espèce d'oiseau obtient"
    dont = f"dont {m} {'nicheuses' if m > 1 else 'nicheuse'}" if m else "dont aucune nicheuse"
    return (f"Au total, {n} {especes} un indice de vulnérabilité {libelle_seuil(seuil, inclus)}, {dont} "
            f"(nicheur possible, probable ou certain), parmi les {z} espèces observées sur l'aire d'étude.")


def _km(metres) -> str:
    km = float(metres) / 1000
    return f"{km:.1f}".replace(".", ",") + " km"


def _n(n) -> str:
    return f"{int(n or 0):,}".replace(",", " ")


def phrase_espece(sp: dict, distances: dict | None, premier_anneau_km: float, debut_periode: int) -> dict:
    """Phrase préremplie d'une espèce très vulnérable (à relire et compléter par le rédacteur) :
    {"nom": ..., "texte": " (vulnérabilité 4 ; nicheur certain, migrateur) : 3 293 données depuis 2016, dont 12 …"}.
    distances : ligne de EolienQueries.distances_especes (None : pas de donnée)."""
    d = distances or {}
    statut = sp.get("statut_bio") or statut_biologique(sp)
    entete = f" (vulnérabilité {fmt_note(sp.get('vulnerabilite'))}{' ; ' + statut.lower() if statut else ''})"
    proches = (sp.get("nb_obs__0") or 0) + (sp.get("nb_obs__1") or 0)
    rayon = f"{premier_anneau_km:g} km".replace(".", ",")
    parts = [f"{_n(sp.get('nb_obs__all'))} donnée{'s' if (sp.get('nb_obs__all') or 0) > 1 else ''} "
             f"depuis {debut_periode}, "
             + (f"dont {_n(proches)} dans la zone d'étude ou à moins de {rayon}" if proches
                else f"aucune dans la zone d'étude ni à moins de {rayon}")]
    if d.get("dist_min_m") is not None:
        dist = float(d["dist_min_m"])
        parts.append("donnée la plus proche dans la zone d'étude" if dist == 0
                     else f"donnée la plus proche à {_km(dist)} de la zone d'étude")
    if d.get("dist_nidif_m") is not None:
        statut_nid = (d.get("statut_nidif_proche") or "").lower()
        annee = f" ({d['annee_nidif_proche']})" if d.get("annee_nidif_proche") else ""
        lieu = ("dans la zone d'étude" if float(d["dist_nidif_m"]) == 0
                else f"à {_km(d['dist_nidif_m'])}")
        parts.append(f"site de nidification {statut_nid} le plus proche {lieu}{annee}".replace("  ", " "))
    else:
        parts.append("aucune nidification probable ou certaine connue sur l'aire d'étude")
    return {"nom": sp.get("nom_vern") or sp.get("lb_nom") or "", "texte": f"{entete} : {' ; '.join(parts)}."}


def texte_couverture(species: list[dict], cartographiees: set, note_min=3.0) -> str:
    """Contrôle pour le rédacteur : espèces d'indice >= note_min absentes de toutes les couches thématiques
    (cartographiees : cd_ref présents dans une couche de nidification, dortoir, migration ou passereaux)."""
    absentes = sorted((sp for sp in species if (sp.get("vulnerabilite") or 0) >= note_min
                       and sp["cd_ref"] not in cartographiees),
                      key=lambda sp: (-(sp.get("vulnerabilite") or 0), sp.get("nom_vern") or ""))
    seuil = f"de {fmt_note(note_min)} ou plus"
    if not absentes:
        return (f"[Contrôle des cartes, à supprimer : toutes les espèces d'indice de vulnérabilité {seuil} "
                f"apparaissent sur au moins une carte thématique (nidification, dortoirs, migration, passereaux).]")

    def detail(sp):
        statut = (sp.get("statut_bio") or statut_biologique(sp)).lower()
        return f"{sp.get('nom_vern')} ({fmt_note(sp.get('vulnerabilite'))}{' ; ' + statut if statut else ''})"

    liste = ", ".join(detail(sp) for sp in absentes)
    return (f"[Contrôle des cartes, à traiter puis supprimer : {len(absentes)} espèce(s) d'indice de vulnérabilité "
            f"{seuil} n'apparaissent sur aucune carte thématique (nidification, dortoirs, migration, passereaux) : "
            f"{liste}. Les cartographier ou commenter leur présence si nécessaire.]")


MATRICE_LIGNES = [("CR, EN", 5), ("VU", 4), ("NT", 3), ("LC", 2), ("DD, NA, non évaluée", 1)]


def matrice() -> list[dict]:
    """Matrice de calcul (tableau de la méthode) : une ligne par note de patrimonialité, une colonne par
    note de sensibilité (s0 à s4) ; mêmes notes et couleurs que les tableaux d'espèces."""
    return [{"statut": f"{libelle} = {note}", **{f"s{s}": (note + s) / 2 for s in range(5)}}
            for libelle, note in MATRICE_LIGNES]


def histogramme(species: list[dict]) -> list[dict]:
    """Nombre d'espèces par valeur d'indice (toutes les valeurs de 0,5 à 4,5, même vides)."""
    valeurs = [v / 2 for v in range(1, 10)]
    return [{"vulnerabilite": v, "nb_especes": sum(1 for sp in species if sp.get("vulnerabilite") == v)}
            for v in valeurs]
