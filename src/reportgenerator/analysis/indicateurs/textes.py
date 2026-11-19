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


def texte_protocoles(regles: list[dict]) -> str:
    """Phrase du contexte : protocoles couverts par le rapport (« label (nom complet) »), STOC-EPS présenté s'il en
    fait partie."""
    noms = [f"{r['label']} ({r['nom_complet']})" for r in regles]
    if not noms:
        return ""
    liste = noms[0] if len(noms) == 1 else f"{', '.join(noms[:-1])} et {noms[-1]}"
    texte = (f"Ce rapport d'exécution dresse l'état du déploiement en région "
             f"{'du protocole' if len(noms) == 1 else 'des protocoles'} {liste}.")
    if any(r["label"] == "STOC-EPS" for r in regles):
        texte = ("En Auvergne-Rhône-Alpes, le STOC-EPS est l'indicateur qui apporte le plus d'informations sur "
                 "l'évolution des populations d'oiseaux nicheurs ; il a débuté en 2001, lors de la relance du "
                 "programme national par le MNHN. " + texte)
    return texte


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


def _benevoles(n: int) -> str:
    return f"{nombre(n)} bénévole{'s' if n > 1 else ''}"


def valorisation(h, taux) -> str:
    """« , soit environ 12 300 € valorisés au taux de 12,5 €/h » ; vide si le taux n'est pas renseigné."""
    if not taux or not h:
        return ""
    t = f"{float(taux):g}".replace(".", ",")
    return f", soit environ {nombre(round(h * float(taux), -2))} € valorisés au taux de {t} €/h"


def texte_benevoles(label, aire, libelle, t: dict, t1: dict | None, statuts: dict, taux=0) -> str:
    """Synthèse du bénévolat d'un protocole : participants, part, travail, renouvellement (chiffres agrégés)."""
    n = t["participants"]
    partis = statuts.get("parti", 0)
    if not n:
        fin = f" ; {_benevoles(partis)} de la saison précédente n'ont pas reconduit leur suivi." if partis else "."
        return f"Aucun bénévole n'a participé au {label} en {libelle}{fin}"
    ec = f" ({ecart(n, t1['participants'])} par rapport à la saison précédente)" if t1 else ""
    part_obs = f", {t['part_observateurs']} % des observateurs" if t["part_observateurs"] is not None else ""
    part_aires = f" ({t['part_aires']} % des {pluriel(aire)} {'suivies' if feminin(aire) else 'suivis'})" \
        if t["part_aires"] is not None else ""
    texte = (f"En {libelle}, {_benevoles(n)} {'ont' if n > 1 else 'a'} participé au {label}{ec}{part_obs}. "
             f"Les bénévoles suivent {nombre(t['aires'])} {pluriel(aire, t['aires'])}{part_aires} et ont produit "
             f"{nombre(t['donnees'])} données, pour {heures(t['heures'], t['heures_estimees'])}"
             f"{valorisation(t['heures'], taux)}. ")
    fid, rev, nouv = (statuts.get(s, 0) for s in ("fidèle", "revenant", "nouveau"))
    texte += (f"Parmi eux : {nombre(fid)} fidèle{'s' if fid > 1 else ''} (déjà {'présents' if fid > 1 else 'présent'} "
              f"la saison précédente), {nombre(rev)} revenant{'s' if rev > 1 else ''} après une interruption et "
              f"{nombre(nouv)} nouveau{'x' if nouv > 1 else ''} ; ")
    texte += (f"{_benevoles(partis)} de la saison précédente n'ont pas reconduit leur suivi." if partis
              else "aucun bénévole de la saison précédente n'a arrêté.")
    return texte


def texte_reseau(annee, r: dict, r1: dict | None, h, taux=0) -> str:
    """Réseau bénévole tous protocoles du rapport : comptes distincts, multi-protocoles, temps."""
    n = r["participants"]
    if not n:
        return f"Aucun bénévole n'a participé aux protocoles du rapport en {annee}."
    ec = f" ({ecart(n, r1['participants'])} par rapport à {annee - 1})" if r1 else ""
    texte = (f"En {annee}, {_benevoles(n)} distinct{'s' if n > 1 else ''} (comptes GeoNature){ec} "
             f"{'ont' if n > 1 else 'a'} participé à au moins un des protocoles du rapport, pour environ "
             f"{nombre(round(h))} heures de travail (mesurées ou estimées){valorisation(h, taux)}. ")
    m = r["multi"]
    texte += (f"{_benevoles(m)} {'participent' if m > 1 else 'participe'} à au moins deux protocoles."
              if m else "Aucun bénévole ne participe à deux protocoles ou plus.")
    return texte


def texte_jamais_visitees(aire: str, n: int, nb: int) -> str:
    """Aires créées dans le module sans jamais être visitées : `n` au total, dont `nb` créées par un bénévole."""
    f = feminin(aire)
    if not n:
        return (f"Toutes les {pluriel(aire)} du module dans la zone ont été visitées au moins une fois." if f
                else f"Tous les {pluriel(aire)} du module dans la zone ont été visités au moins une fois.")
    accord = ("e" if f else "") + ("s" if n > 1 else "")
    if nb == 0:
        par = ((", aucune" if f else ", aucun") + " par un bénévole") if n > 1 else ""
    elif nb == n:
        par = ((", toutes" if f else ", tous") + " par des bénévoles") if n > 1 else ", par un bénévole"
    else:
        par = f", dont {nombre(nb)} par {'un bénévole' if nb == 1 else 'des bénévoles'}"
    return (f"{nombre(n)} {pluriel(aire, n)} de la zone {'ont' if n > 1 else 'a'} été créé{accord} dans le module "
            f"sans jamais être visité{accord}{par} (détail en annexe) : suivis envisagés mais non concrétisés, à "
            "relancer ou à retirer du module.")
