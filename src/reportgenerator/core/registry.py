"""
registry.py

Registre des briques d'analyse. Une brique est une fonction `run(ctx)` qui
retourne un AnalysisResult ; elle est déclarée avec @register_brick.

    @register_brick("zonages", provides=["TABLE_ZONAGES", "ZONAGE_TEXTE"])
    def zonages(ctx):
        ...

- requires : briques à exécuter avant (ajoutées automatiquement au plan).
- provides : clés de placeholders fournies. Sert uniquement à la commande
  `check` (vérification du template sans lancer les analyses). Peut être une
  fonction(dossier) -> liste quand les clés dépendent du dossier
  (ex. les mises en page du projet QGIS).
"""

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class Brick:
    name: str
    run: Callable
    requires: tuple[str, ...] = ()
    provides: tuple[str, ...] | Callable = ()
    label: str = ""

    def provided_keys(self, dossier) -> set[str]:
        if callable(self.provides):
            return set(self.provides(dossier))
        return set(self.provides)


_REGISTRY: dict[str, Brick] = {}


def register_brick(
    name: str,
    requires: Iterable[str] = (),
    provides: Iterable[str] | Callable = (),
    label: str = "",
):
    def decorator(func):
        if name in _REGISTRY:
            raise ValueError(f"Brique déjà déclarée : {name}")
        _REGISTRY[name] = Brick(
            name=name,
            run=func,
            requires=tuple(requires),
            provides=provides if callable(provides) else tuple(provides),
            label=label or (func.__doc__ or "").strip().split("\n")[0],
        )
        return func

    return decorator


def get_brick(name: str) -> Brick:
    _load_bricks()
    if name not in _REGISTRY:
        raise KeyError(f"Brique inconnue : {name}")
    return _REGISTRY[name]


def has_brick(name: str) -> bool:
    _load_bricks()
    return name in _REGISTRY


def all_bricks() -> dict[str, Brick]:
    _load_bricks()
    return dict(_REGISTRY)


def _load_bricks():
    # l'import du package déclenche l'enregistrement de toutes les briques
    import reportgenerator.bricks  # noqa: F401
