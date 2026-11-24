"""Chargement d'un protocole : requêtes en lecture seule (queries.py) puis adaptateur (adaptateurs.py) -> `Jeu`."""

import dataclasses
import time

from reportgenerator.analysis.indicateurs.adaptateurs import jeu_monitoring, jeu_vigienature
from reportgenerator.analysis.indicateurs.modele import Jeu


def borner(jeu: Jeu, annee_min: int, saison: int) -> Jeu:
    """Jeu vu depuis la saison du rapport : aucune saison postérieure (saisies déjà faites l'année suivante), ni
    aire visitée pour la première fois après ; observations des seules saisons annee_min à saison."""
    p = jeu.passages[jeu.passages["saison"] <= saison]
    futures = set(jeu.passages["id_aire"]) - set(p["id_aire"])
    fenetre = set(p.loc[p["saison"] >= annee_min, "id_passage"])
    return dataclasses.replace(
        jeu, passages=p, aires=jeu.aires[~jeu.aires["id_aire"].isin(futures)],
        unites=jeu.unites[~jeu.unites["id_aire"].isin(futures)],
        observateurs=jeu.observateurs[jeu.observateurs["id_passage"].isin(set(p["id_passage"]))],
        observations=jeu.observations[jeu.observations["id_passage"].isin(fenetre)])


def _centres(aires) -> list[tuple]:
    return [(a["id_aire"], a["x"], a["y"]) for a in aires if a["x"] is not None]


def _vigienature(code, q, regle, protocoles, annee_min, par_site=False) -> Jeu:
    aires = q.aires_vigienature(protocoles, par_site)
    releves = q.releves_vigienature(protocoles, regle["debut_serie"], par_site)
    observations = q.observations_vigienature(protocoles, annee_min, par_site)
    observateurs = q.observateurs_faune_france(sorted({str(r["observateur"]) for r in releves if r["observateur"]}))
    return jeu_vigienature(code, aires, releves, observations, observateurs, q.localiser(_centres(aires)), regle)


def charger(code: str, q, regle: dict, saison: int, annees_especes: int) -> Jeu:
    """Toutes les saisons du protocole depuis debut_serie, pour les aires de l'emprise ; observations des
    annees_especes dernières saisons."""
    t0 = time.time()
    annee_min = saison - int(annees_especes) + 1
    if regle["source"] == "vigienature":
        jeu = _vigienature(code, q, regle, regle["nom_protocole"], annee_min)
    else:
        module = regle["module"]
        aires = q.aires_monitoring(module)
        etats = q.etats_pop(regle["vue_etats"]) if regle.get("vue_etats") else ()
        anomalies = q.anomalies_pop(regle["vue_anomalies"], saison) if regle.get("vue_anomalies") else ()
        jeu = jeu_monitoring(code, aires, q.unites_monitoring(module),
                             q.passages_monitoring(module, regle["debut_serie"], bool(regle.get("heures_visite"))),
                             q.observateurs_monitoring(module), q.observations_monitoring(module, annee_min),
                             q.localiser(_centres(aires)), regle, etats, anomalies)
    jeu = borner(jeu, annee_min, saison)
    print(f"[indicateurs] {code} chargé en {time.time() - t0:.0f} s : {len(jeu.aires)} aires, "
          f"{len(jeu.passages)} relevés, {len(jeu.observations)} observations")
    return jeu


def charger_stoc_sites(q, regle: dict, saison: int, annees_especes: int) -> Jeu:
    """STOC-sites (STOC_SITES, STOC_ONF, STOC_SITES_RNF) : aire = site (nom), observations depuis debut_n2000."""
    sites = regle["sites"]
    annee_min = min(int(sites.get("debut_n2000", saison)), saison - int(annees_especes) + 1)
    jeu = _vigienature("stoc_sites", q, regle, sites["nom_protocole"], annee_min, par_site=True)
    return borner(jeu, annee_min, saison)
