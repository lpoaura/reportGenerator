"""
Cartes thématiques par groupe d'espèces (nidification, dortoirs) : plan des cartes et couleurs, sans base de données.

Principe (cf. METHODO.md §5 bis) :
- les groupes sont définis par des RÈGLES (ordre, famille, genre, nom scientifique) dans dossier.toml, dans l'ordre de
  priorité : une espèce va dans le premier groupe qui la reconnaît, jamais par son nom vernaculaire (qui change) ;
- une carte n'a jamais plus de `max_par_carte` espèces (lisibilité de la carte et de la légende) : un groupe trop
  grand est découpé selon ses sous-groupes s'il en a (ex. hiboux / chouettes), sinon en gardant les genres ensemble ;
- les espèces qu'aucun groupe ne reconnaît vont sur la (ou les) carte(s) « Autres » : aucune espèce n'est oubliée ;
- une couleur par espèce, la même sur toutes les cartes du rapport : celle du référentiel couleurs_especes.csv, sinon
  une couleur automatique ; deux espèces d'une même carte ont toujours des couleurs nettement différentes.
"""

import csv
import math
from pathlib import Path

# couleurs automatiques : palettes qualitatives de P. Tol (muted, puis bright), lisibles par les daltoniens
PALETTE_AUTO = ["#CC6677", "#332288", "#DDCC77", "#117733", "#88CCEE", "#882255", "#44AA99", "#999933", "#AA4499",
                "#4477AA", "#EE6677", "#228833", "#CCBB44", "#66CCEE", "#AA3377", "#BBBBBB", "#000000"]
ECART_MIN = 20   # écart minimal de couleur (CIE76, ΔE) entre deux espèces d'une même carte


# =========================================================
# GROUPES ET PLAN DES CARTES
# =========================================================


def genre(sp: dict) -> str:
    return (sp.get("lb_nom") or "").split(" ")[0]


def correspond(sp: dict, regle: dict) -> bool:
    """Règle {ordres, familles, genres, especes (noms scientifiques)} : vrai si l'un des critères reconnaît l'espèce."""
    return bool(sp.get("ordre") in regle.get("ordres", ())
                or sp.get("famille") in regle.get("familles", ())
                or genre(sp) in regle.get("genres", ())
                or sp.get("lb_nom") in regle.get("especes", ()))


def _tri(sp: dict):
    return genre(sp), sp.get("nom_vern") or "", sp.get("cd_ref")


def decouper(especes: list[dict], max_par_carte: int) -> list[list[dict]]:
    """Paquets de max_par_carte espèces au plus, en gardant les espèces d'un même genre ensemble (un genre plus grand
    que la carte est lui-même découpé), et équilibrés (7 espèces -> 4 + 3 plutôt que 6 + 1)."""
    if not especes:
        return []
    nb_cartes = math.ceil(len(especes) / max_par_carte)
    cible = math.ceil(len(especes) / nb_cartes)
    blocs, courant = [], []
    for sp in sorted(especes, key=_tri):
        if courant and genre(courant[-1]) != genre(sp):
            blocs.append(courant)
            courant = []
        courant.append(sp)
    if courant:
        blocs.append(courant)
    blocs = [b[i:i + max_par_carte] for b in blocs for i in range(0, len(b), max_par_carte)]
    pages, page = [], []
    for bloc in blocs:
        if page and (len(page) >= cible or len(page) + len(bloc) > max_par_carte):
            pages.append(page)
            page = []
        page = page + bloc
    if page:
        pages.append(page)
    return pages


def _pages_groupe(especes: list[dict], groupe: dict, max_par_carte: int) -> list[tuple[str, str, list[dict]]]:
    """[(suffixe de clé, titre, espèces)] d'un groupe : une carte, ou découpage (sous-groupes, puis genres)."""
    if len(especes) <= max_par_carte:
        return [("", groupe["titre"], sorted(especes, key=_tri))]
    morceaux, restants = [], list(especes)
    for sous in groupe.get("decoupage", ()):
        pris = [sp for sp in restants if correspond(sp, sous)]
        restants = [sp for sp in restants if sp not in pris]
        if pris:
            morceaux.append((sous["cle"], sous["titre"], pris))
    if restants:
        morceaux.append(("", groupe["titre"], restants))
    pages = []
    for cle, titre, sps in morceaux:
        paquets = decouper(sps, max_par_carte)
        for i, paquet in enumerate(paquets, start=1):
            suffixe = "_".join(x for x in (cle, str(i) if len(paquets) > 1 else "") if x)
            pages.append((suffixe, f"{titre} ({i}/{len(paquets)})" if len(paquets) > 1 else titre, paquet))
    return pages


def plan_cartes(especes: list[dict], groupes: list[dict], max_par_carte=6,
                autres=("autres", "autres espèces", "autres")) -> list[dict]:
    """Cartes à produire : [{cle, titre, section, groupe, especes: [espèces], ordre}].
    groupes : [{cle, titre, section, ordres/familles/genres/especes, decoupage: [{cle, titre, règle}]}] (priorité =
    ordre de la liste) ; autres = (clé, titre, section) des cartes des espèces qu'aucun groupe ne reconnaît."""
    par_groupe = {g["cle"]: [] for g in groupes}
    sans_groupe = []
    for sp in especes:
        g = next((g for g in groupes if correspond(sp, g)), None)
        (par_groupe[g["cle"]] if g else sans_groupe).append(sp)
    cartes = []
    for g in groupes:
        if par_groupe[g["cle"]]:
            for suffixe, titre, sps in _pages_groupe(par_groupe[g["cle"]], g, max_par_carte):
                cartes.append({"cle": "_".join(x for x in (g["cle"], suffixe) if x), "titre": titre,
                               "section": g.get("section", g["cle"]), "groupe": g["cle"], "especes": sps})
    if sans_groupe:
        cle, titre, section = autres
        paquets = decouper(sans_groupe, max_par_carte)
        for i, paquet in enumerate(paquets, start=1):
            cartes.append({"cle": f"{cle}_{i}" if len(paquets) > 1 else cle,
                           "titre": f"{titre} ({i}/{len(paquets)})" if len(paquets) > 1 else titre,
                           "section": section, "groupe": cle, "especes": paquet})
    for i, carte in enumerate(cartes, start=1):
        carte["ordre"] = i
    return cartes


# =========================================================
# COULEURS
# =========================================================


def load_couleurs(path: Path) -> dict[int, str]:
    """couleurs_especes.csv (cd_ref;…;couleur, lignes « # » ignorées) -> {cd_ref: '#rrggbb'}."""
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        lignes = [ligne for ligne in f if ligne.strip() and not ligne.startswith("#")]
    return {int(r["cd_ref"]): r["couleur"].strip().lower() for r in csv.DictReader(lignes, delimiter=";")
            if (r.get("cd_ref") or "").strip() and (r.get("couleur") or "").strip()}


def _lab(couleur: str):
    """#rrggbb -> CIE L*a*b* (sRGB, D65)."""
    rgb = [int(couleur.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    x = (0.4124 * lin[0] + 0.3576 * lin[1] + 0.1805 * lin[2]) / 0.95047
    y = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    z = (0.0193 * lin[0] + 0.1192 * lin[1] + 0.9505 * lin[2]) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def ecart(c1: str, c2: str) -> float:
    """Écart de couleur perçu (ΔE CIE76) : < 10 quasi identiques, > 20 nettement différentes sur un petit symbole."""
    return math.dist(_lab(c1), _lab(c2))


def attribuer_couleurs(cartes: list[list[int]], referentiel: dict[int, str], palette=PALETTE_AUTO,
                       ecart_min=ECART_MIN) -> tuple[dict[int, str], list[int]]:
    """Une couleur par espèce (cd_ref), la même sur toutes les cartes : celle du référentiel si elle reste nettement
    différente des espèces déjà colorées des cartes où l'espèce figure, sinon une couleur automatique.
    cartes : listes de cd_ref (une par carte, toutes thématiques confondues), dans l'ordre des légendes.
    Retourne ({cd_ref: couleur}, cd_ref dont la couleur du référentiel a été remplacée)."""
    voisins: dict[int, set] = {}
    for carte in cartes:
        for cd in carte:
            voisins.setdefault(cd, set()).update(c for c in carte if c != cd)
    couleurs, remplacees = {}, []
    ordre = list(dict.fromkeys(cd for carte in cartes for cd in carte))
    # d'abord les espèces du référentiel (leur couleur est choisie), puis les autres
    for cd in sorted(ordre, key=lambda c: c not in referentiel):
        prises = [couleurs[v] for v in voisins[cd] if v in couleurs]
        ref = referentiel.get(cd)
        if ref and all(ecart(ref, p) >= ecart_min for p in prises):
            couleurs[cd] = ref
            continue
        if ref:
            remplacees.append(cd)
        candidats = [c.lower() for c in palette]
        libres = [c for c in candidats if all(ecart(c, p) >= ecart_min for p in prises)]
        couleurs[cd] = libres[0] if libres else max(candidats, key=lambda c: min((ecart(c, p) for p in prises),
                                                                                 default=0))
    return couleurs, remplacees
