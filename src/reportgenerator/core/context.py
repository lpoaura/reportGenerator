from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from reportgenerator.analysis.common.models import AnalysisResult
from reportgenerator.core.dossier import Dossier
from reportgenerator.queries import SyntheseQueries


@dataclass
class ReportContext:
    """Tout ce dont une brique a besoin pour s'exécuter."""

    service_name: str
    id_area: int
    area_name: str
    referee: str
    buffer: int
    dossier: Dossier
    enabled: list[str]
    output_dirs: dict[str, Path]
    queries: SyntheseQueries
    params: dict = field(default_factory=dict)

    # résultats des briques déjà exécutées, par nom de brique
    results: dict[str, AnalysisResult] = field(default_factory=dict)
    _cache: dict = field(default_factory=dict, repr=False)

    def is_enabled(self, name: str) -> bool:
        return name in self.enabled

    def cached(self, key: str, compute: Callable):
        """Exécute `compute()` une seule fois par rapport (évite de relancer
        la même requête SQL dans plusieurs briques)."""
        if key not in self._cache:
            self._cache[key] = compute()
        return self._cache[key]
