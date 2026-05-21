from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AnalysisResult:
    # données brutes utiles au rapport
    data: dict

    # fichiers générés
    files: dict

    # métadonnées optionnelles
    meta: dict | None = None