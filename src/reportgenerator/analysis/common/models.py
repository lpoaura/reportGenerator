from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class TableBlock:
    """Tableau à insérer à la place d'un placeholder {{CLE}}.

    `insert` est une fonction d'insertion existante (ex. insert_species_table),
    appelée avec document=, placeholder=, data= et les `options` en plus.
    """

    data: list
    insert: Callable
    options: dict = field(default_factory=dict)


@dataclass
class ImageBlock:
    """Image à insérer à la place d'un placeholder {{cle}} (ou {{cle.png}}).

    layout : "normal", "A4" ou "A3" (cf. core/renderer.py LAYOUTS).
    """

    path: Path
    layout: str = "normal"


@dataclass
class AnalysisResult:
    # données brutes utiles aux autres briques
    data: dict = field(default_factory=dict)

    # fichiers générés
    files: dict = field(default_factory=dict)

    # métadonnées optionnelles
    meta: dict | None = None

    # contenu à injecter dans le Word : clé du placeholder -> contenu
    texts: dict[str, Any] = field(default_factory=dict)
    tables: dict[str, TableBlock] = field(default_factory=dict)
    images: dict[str, ImageBlock] = field(default_factory=dict)
