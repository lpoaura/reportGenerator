"""
pipeline.py

Détermine l'ordre d'exécution des briques d'un dossier (dépendances comprises),
les exécute, puis génère le Word.
"""

from dataclasses import dataclass, field
from pathlib import Path

from reportgenerator.analysis.common.timing import RunTimer
from reportgenerator.core.dossier import Dossier
from reportgenerator.core.registry import get_brick, has_brick
from reportgenerator.core.renderer import render_report, template_placeholders


def build_plan(brick_names: list[str]) -> list[str]:
    """Ordonne les briques pour que chaque dépendance passe avant.
    Les dépendances non listées sont ajoutées automatiquement."""
    ordered: list[str] = []
    visiting: set[str] = set()

    def visit(name, chain):
        if name in ordered:
            return
        if name in visiting:
            raise ValueError(f"Dépendance circulaire : {' -> '.join(chain + [name])}")
        visiting.add(name)
        for dep in get_brick(name).requires:
            visit(dep, chain + [name])
        visiting.discard(name)
        ordered.append(name)

    for name in brick_names:
        visit(name, [])
    # les briques "last" (cartography) passent après celles qui produisent leurs couches
    return [n for n in ordered if not get_brick(n).last] + [n for n in ordered if get_brick(n).last]


def run_pipeline(ctx, output_file: Path) -> set[str]:
    """Exécute les briques puis génère le rapport. Retourne les placeholders non remplis."""
    timer = RunTimer()
    plan = build_plan(ctx.enabled)
    print(f"Dossier '{ctx.dossier.name}' - briques : {', '.join(plan)}")

    for name in plan:
        with timer.step(f"Brique {name}"):
            ctx.results[name] = get_brick(name).run(ctx)

    with timer.step("Génération du rapport Word"):
        # sections {{#brique}} ... {{/brique}} : gardées si la brique a été exécutée
        unresolved = render_report(ctx.dossier.template, ctx.results, output_file, sections=set(plan))

    timer.summary()
    return unresolved


@dataclass
class CheckReport:
    missing_template: bool = False
    no_placeholder: bool = False
    unknown_bricks: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    unused: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing_template or self.no_placeholder or self.unknown_bricks or self.unresolved)


def check_dossier(dossier: Dossier) -> CheckReport:
    """Vérification sans base de données ni QGIS : briques déclarées,
    placeholders du template sans source, sorties non utilisées."""
    report = CheckReport()
    names = list(dossier.required) + list(dossier.optional)

    report.unknown_bricks = [n for n in names if not has_brick(n)]
    known = [n for n in names if has_brick(n)]

    provided = set()
    for name in build_plan(known):
        provided |= get_brick(name).provided_keys(dossier)

    if not dossier.template.exists():
        report.missing_template = True
        return report

    in_template = template_placeholders(dossier.template)
    report.no_placeholder = not in_template
    report.unresolved = sorted(in_template - provided)
    report.unused = sorted(provided - in_template)
    return report
