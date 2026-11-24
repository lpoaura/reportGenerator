import json
import subprocess
from pathlib import Path

from reportgenerator.analysis.qgis_runtime import (qgis_subprocess_env,
                                                   resolve_qgis_python)


def launch_qgis_render(project_path, output_dir, config: dict | None = None):

    qgis_python = resolve_qgis_python()
    print("QGIS PYTHON =", qgis_python)
    script = Path(__file__).parent / "qgis_render.py"

    print("Lancement du rendu QGIS...")

    cmd = (
        f'"{qgis_python}" "{script}" '
        f'--project "{project_path}" '
        f'--output "{output_dir}"'
    )

    if config:
        config_path = Path(project_path).with_suffix(".render.json")
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        cmd += f' --config "{config_path}"'

    result = subprocess.run(
        cmd,
        shell=True,
        env=qgis_subprocess_env(),
        capture_output=True,
        text=True,
    )

    print("--- STDOUT QGIS ---")
    print(result.stdout)
    print("--- STDERR QGIS ---")
    print(result.stderr)

    result.check_returncode()
