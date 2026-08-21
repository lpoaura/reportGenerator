import subprocess
from pathlib import Path
from unittest import result

from reportgenerator.analysis.qgis_runtime import (qgis_subprocess_env,
                                                   resolve_qgis_python)


def launch_qgis_atlas_render(project_path, output_path, layout_name="atlas_species"):
    qgis_python = resolve_qgis_python()
    script_path = Path(__file__).with_name("qgis_atlas_render.py")

    print("Lancement du rendu atlas QGIS...")
    print("QGIS PYTHON =", qgis_python)

    subprocess.run(
        [
            str(qgis_python),
            str(script_path),
            "--project",
            str(project_path),
            "--output",
            str(output_path),
            "--layout",
            layout_name,
        ],
        ##shell=True,
        check=True,
        env=qgis_subprocess_env(),
    )

    print("--- STDOUT QGIS ---")
    print(result.stdout)
    print("--- STDERR QGIS ---")
    print(result.stderr)

    result.check_returncode()  # lève l'exception après avoir affiché la sortie