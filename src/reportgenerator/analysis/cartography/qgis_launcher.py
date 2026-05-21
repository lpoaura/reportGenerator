import subprocess
from pathlib import Path

def launch_qgis_render(project_path, output_dir):

    qgis_python = Path(r"C:\Program Files\QGIS\3_40\bin\python-qgis-ltr.bat")
    print("QGIS PYTHON =", qgis_python)
    script = Path(__file__).parent / "qgis_render.py"

    print("Lancement du rendu QGIS...")

    subprocess.run([
        qgis_python,
        str(script),
        "--project", str(project_path),
        "--output", str(output_dir)
    ], check=True)