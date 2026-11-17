"""Textes pré-rédigés du rapport Indicateurs (français, chiffres au format français). Indicateurs descriptifs :
jamais le mot « tendance » (les tendances STOC sont celles du MNHN)."""

NBSP_FINE = " "
MOINS = "−"


def nombre(x) -> str:
    """81561 -> « 81 561 » (espace fine insécable) ; 10.5 -> « 10,5 » ; None -> « — »."""
    if x is None:
        return "—"
    if float(x) == int(x):
        return f"{int(x):,}".replace(",", NBSP_FINE)
    return f"{float(x):,.1f}".replace(",", NBSP_FINE).replace(".", ",")


def ecart(n, n1) -> str:
    """Écart avec l'année précédente : « +6 (+33 %) », « = », « −2 (−10 %) » ; « — » sans année précédente."""
    if n1 is None or n is None:
        return "—"
    d = n - n1
    if d == 0:
        return "="
    signe = "+" if d > 0 else MOINS
    if not n1:
        return f"{signe}{nombre(abs(d))}"
    return f"{signe}{nombre(abs(d))} ({signe}{int(abs(100 * d / n1) + 0.5)} %)"


def feminin(mot: str) -> bool:
    return mot.split(" ")[0] == "aire"


def pluriel(mot: str, n: int = 2) -> str:
    """« site » -> « sites », « point d'écoute » -> « points d'écoute » (premier mot)."""
    if n <= 1:
        return mot
    tete, _, reste = mot.partition(" ")
    return f"{tete}s {reste}".strip() if not tete.endswith("s") else mot


def _suivi(aire: str, n: int) -> str:
    return "suivi" + ("e" if feminin(aire) else "") + ("s" if n > 1 else "")


def heures(h, estime: bool) -> str:
    return f"{nombre(round(h))} h" + (" (estimation)" if estime else "")


def note_temps(temps: dict, estime: bool, aire: str = "aire") -> str:
    """Comment le temps est obtenu : mesuré (heures des passages) ou estimé (forfaits du dossier.toml)."""
    unites = {"aire": aire, "visite": "visite"}
    if temps.get("terrain_h") == "mesure":
        t = "Temps de terrain mesuré à partir des heures de début et de fin des passages"
        if estime:
            t += " (complété par une estimation quand les heures manquent)"
    else:
        t = (f"Temps estimé : {nombre(temps.get('terrain_h') or 0)} h par "
             f"{unites.get(temps.get('unite_terrain'), aire)}")
    if temps.get("complement_h"):
        t += (f", plus {nombre(temps['complement_h'])} h par {unites.get(temps.get('unite_complement'), aire)} "
              "(préparation, trajet, saisie)")
    return t + "."


def texte_participation(label, aire, libelle, c: dict, c1: dict | None, temps_note: str) -> str:
    if not c.get("aires"):
        return f"Aucun{'e' if feminin(aire) else ''} {aire} {_suivi(aire, 1)} en {libelle} dans la zone."
    n = c["aires"]
    t = (f"En {libelle}, {nombre(n)} {pluriel(aire, n)} {'ont' if n > 1 else 'a'} été {_suivi(aire, n)} dans le cadre "
         f"du {label} par {nombre(c['observateurs'])} observateur{'s' if c['observateurs'] > 1 else ''}, pour "
         f"{nombre(c['donnees'])} données et environ {heures(c['heures'], c['heures_estimees'])} de travail.")
    if c1 and c1.get("aires"):
        t += (f" Par rapport à la saison précédente : {pluriel(aire)} : {ecart(n, c1['aires'])}, observateurs : "
              f"{ecart(c['observateurs'], c1['observateurs'])}, données : {ecart(c['donnees'], c1['donnees'])}.")
    return f"{t} {temps_note}".strip()


def texte_couverture(aire, c: dict, fid: dict, par_departement: bool, nb_departements: int) -> str:
    n = c.get("aires") or 0
    if not n:
        return ""
    if par_departement and nb_departements <= 1:
        t = (f"Les {nombre(n)} {pluriel(aire, n)} {_suivi(aire, n)} sont tou{'tes' if feminin(aire) else 's'} dans le "
             "même département (tableau ci-dessous).")
    elif par_departement:
        t = (f"Les {nombre(n)} {pluriel(aire, n)} {_suivi(aire, n)} se répartissent sur {nb_departements} "
             "départements (tableau ci-dessous).")
    else:
        t = f"Liste des {pluriel(aire)} {_suivi(aire, 2)} dans la zone (tableau ci-dessous)."
    nouv, aband = fid.get("nouvelles", 0), fid.get("abandonnees", 0)
    if nouv:
        t += f" {nombre(nouv)} {pluriel(aire, nouv)} {'sont' if nouv > 1 else 'est'} {_suivi(aire, nouv)} " \
             "pour la première fois."
    if aband:
        t += (f" {nombre(aband)} {pluriel(aire, aband)} {_suivi(aire, aband)} la saison précédente "
              f"ne l'{'ont' if aband > 1 else 'a'} pas été cette année.")
    return t


def texte_fidelisation(aire, fid: dict) -> str:
    phrases = []
    if fid.get("taux_reconduction_aires") is not None:
        phrases.append(f"{fid['taux_reconduction_aires']} % des {pluriel(aire)} {_suivi(aire, 2)} la saison "
                       f"précédente l'ont été de nouveau ({nombre(fid['reconduites'])} sur {nombre(fid['aires_n1'])}).")
    if fid.get("taux_reconduction_observateurs") is not None:
        phrases.append(f"{fid['taux_reconduction_observateurs']} % des observateurs de la saison précédente ont "
                       f"participé de nouveau ; {nombre(fid['observateurs_gagnes'])} nouveaux participants et "
                       f"{nombre(fid['observateurs_perdus'])} non revus.")
    phrases.append(f"Depuis le début du suivi, {nombre(fid['cumul_aires'])} {pluriel(aire, fid['cumul_aires'])} et "
                   f"{nombre(fid['cumul_observateurs'])} observateurs (comptes) ont participé.")
    pa = fid.get("plus_ancienne")
    if pa:
        article = "La plus ancienne" if feminin(aire) else "Le plus ancien"
        phrases.append(f"{article} {aire} encore {_suivi(aire, 1)}, {pa['nom_aire']}, l'est depuis {pa['premiere']} "
                       f"({nombre(pa['annees'])} saisons de suivi) ; ancienneté moyenne : "
                       f"{nombre(fid['anciennete_moyenne'])} saisons.")
    return " ".join(phrases)


def texte_especes(c: dict, especes: list[dict], aire: str = "aire") -> str:
    if not especes:
        return "Aucune observation d'espèce disponible pour cette saison."
    premieres = ", ".join(f"{e['nom']} ({e['freq_aires']} % des {pluriel(aire)})" for e in especes[:5])
    return (f"{nombre(c.get('especes') or len(especes))} espèces ont été notées. Les plus fréquentes : {premieres}. "
            "Ces fréquences sont des indicateurs descriptifs, pas des tendances de population.")
