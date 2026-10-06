"""
dossier.py

Un "dossier type" = un sous-dossier de reportgenerator/dossiers/ contenant :
  - dossier.toml  : manifeste (briques obligatoires / optionnelles, paramètres)
  - template.docx : modèle Word avec les placeholders {{CLE}}
  - METHODO.md    : (optionnel) méthodologie métier fournie par les collègues
"""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DOSSIERS_DIR = Path(__file__).resolve().parents[1] / "dossiers"
DEFAULT_DOSSIER = "generique"


@dataclass(frozen=True)
class Dossier:
    name: str
    label: str
    path: Path
    template: Path
    qgis_project: Path | None
    required: tuple[str, ...]
    optional: tuple[str, ...]
    params: dict = field(default_factory=dict)
    # valeurs de list_analyse (formulaire QGIS) qui déclenchent ce dossier,
    # avec les analyses optionnelles que chacune active
    trigger_analyses: dict = field(default_factory=dict)

    @property
    def triggers(self) -> tuple[str, ...]:
        return tuple(self.trigger_analyses)

    def select_analyses(self, list_analyse: str | None) -> tuple[list[str], list[str]]:
        """Retourne (briques à lancer, analyses demandées mais inconnues du dossier)."""
        values = parse_list_analyse(list_analyse)
        requested = [a for a in values if a not in self.trigger_analyses]
        for trigger in values:
            requested += self.trigger_analyses.get(trigger, [])
        enabled = list(dict.fromkeys(a for a in requested if a in self.optional))
        ignored = [a for a in requested if a not in self.optional]
        return list(self.required) + enabled, ignored


def parse_list_analyse(list_analyse: str | None) -> list[str]:
    """'analyse_eolien', 'atlas_nicheur, x' ou '{atlas_nicheur,"x"}' (choix multiple QGIS)
    -> liste de valeurs en minuscules, sans accolades ni guillemets."""
    cleaned = re.sub(r'[{}"\']', " ", list_analyse or "")
    return [a.lower() for a in re.split(r"[,;\s]+", cleaned) if a]


def list_dossiers() -> list[str]:
    return sorted(p.parent.name for p in DOSSIERS_DIR.glob("*/dossier.toml"))


def resolve_dossier(list_analyse: str | None) -> Dossier:
    """Choisit le type de dossier d'après list_analyse : le dossier dont un
    déclencheur figure dans la liste, sinon le dossier générique."""
    requested = set(parse_list_analyse(list_analyse))
    matches = [
        dossier for dossier in map(load_dossier, list_dossiers())
        if requested & set(dossier.triggers)
    ]
    if len(matches) > 1:
        raise ValueError(
            f"list_analyse {list_analyse!r} correspond à plusieurs types de rapport : "
            f"{', '.join(d.name for d in matches)}"
        )
    return matches[0] if matches else load_dossier(DEFAULT_DOSSIER)


def load_dossier(name: str | None) -> Dossier:
    name = name or DEFAULT_DOSSIER
    path = DOSSIERS_DIR / name
    manifest = path / "dossier.toml"

    if not manifest.exists():
        raise ValueError(
            f"Type de dossier inconnu : {name!r}. Disponibles : {', '.join(list_dossiers())}"
        )

    with manifest.open("rb") as f:
        config = tomllib.load(f)

    analyses = config.get("analyses", {})
    qgis_project = config.get("qgis_project")
    # declencheurs = ["analyse_x"]  ou  [declencheurs] analyse_x = ["option_1", ...]
    declencheurs = config.get("declencheurs", [])
    if not isinstance(declencheurs, dict):
        declencheurs = {t: [] for t in declencheurs}

    return Dossier(
        name=name,
        label=config.get("label", name),
        path=path,
        template=(path / config.get("template", "template.docx")).resolve(),
        qgis_project=(path / qgis_project).resolve() if qgis_project else None,
        required=tuple(analyses.get("required", [])),
        optional=tuple(analyses.get("optional", [])),
        params=config.get("params", {}),
        trigger_analyses={t.lower(): list(opts) for t, opts in declencheurs.items()},
    )
