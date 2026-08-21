import subprocess
from pathlib import Path

from reportgenerator.analysis.qgis_runtime import (qgis_subprocess_env,
                                                   resolve_qgis_python)


def launch_qgis_atlas_render(project_path, output_dir, layout_name="atlas_species"):

    qgis_python = resolve_qgis_python()
    print("QGIS PYTHON =", qgis_python)
    script = Path(__file__).parent / "qgis_atlas_render.py"

    print("Lancement du rendu Atlas QGIS...")

    cmd = (
        f'"{qgis_python}" "{script}" '
        f'--project "{project_path}" '
        f'--output "{output_dir}" '
        f'--layout "{layout_name}"'
    )

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