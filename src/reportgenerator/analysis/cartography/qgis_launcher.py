import subprocess
from pathlib import Path

from reportgenerator.analysis.qgis_runtime import (qgis_subprocess_env,
                                                   resolve_qgis_python)


def launch_qgis_render(project_path, output_dir):

    qgis_python = resolve_qgis_python()
    print("QGIS PYTHON =", qgis_python)
    script = Path(__file__).parent / "qgis_render.py"

    print("Lancement du rendu QGIS...")

    subprocess.run(
        [
            str(qgis_python),
            str(script),
            "--project",
            str(project_path),
            "--output",
            str(output_dir),
        ],
        shell=True,
        check=True,
        env=qgis_subprocess_env(),
    )
