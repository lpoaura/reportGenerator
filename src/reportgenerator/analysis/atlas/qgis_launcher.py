from pathlib import Path
import subprocess


def launch_qgis_atlas_render(project_path, output_path, layout_name="atlas_species"):
    qgis_python = Path(r"C:\Program Files\QGIS\3_40\bin\python-qgis-ltr.bat")
    script_path = Path(__file__).with_name("qgis_atlas_render.py")

    print("Lancement du rendu atlas QGIS...")

    subprocess.run([
        str(qgis_python),
        str(script_path),
        "--project", str(project_path),
        "--output", str(output_path),
        "--layout", layout_name,
    ], check=True)