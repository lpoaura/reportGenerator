"""Chargement d'un protocole : requêtes (queries.py) puis adaptateur (adaptateurs.py) -> `Jeu`."""

from reportgenerator.analysis.indicateurs.modele import Jeu


def charger(code: str, q, regle: dict, saison: int, annees_especes: int) -> Jeu:
    raise NotImplementedError("chargement des protocoles : tâche 9 du plan")


def charger_stoc_sites(q, regle: dict, saison: int, annees_especes: int) -> Jeu:
    raise NotImplementedError("chargement des STOC-sites : tâche 9 du plan")
