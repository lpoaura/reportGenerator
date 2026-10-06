"""
Briques d'analyse disponibles pour les dossiers types.

Une brique relie le code métier (reportgenerator/analysis/...) au rapport :
elle lance les requêtes / graphiques / cartes et retourne un AnalysisResult
dont les clés texts / tables / images correspondent aux placeholders du Word.

Pour ajouter une brique : créer (ou compléter) un module ici, décorer la
fonction avec @register_brick, et l'importer ci-dessous.
"""

from reportgenerator.bricks import chiropteres, common, eolien, generique  # noqa: F401
