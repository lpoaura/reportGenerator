# LPO reportGenerator

Python script to generate Word reports from GeoNature LPO databases.

## Usage

```bash
poetry install

poetry run python src/reportgenerator/cli.py generate --service gnlpoaura --limit 1000
poetry run python src/reportgenerator/cli.py run --service "mon_service_pg" --output "mon_rapport.docx" --id_area 2336982 --referee "Personne référentes" --list_analyse "mes_analyses" --buffer numero_buffer_en_km --area_name "mon_nom_de_projet"

```

Sans `--output_dir`, les fichiers sont générés dans `src/reportgenerator/outputs/<area_name>`.

## Configuration QGIS

Les rendus QGIS utilisent un interpréteur Python QGIS externe. Par défaut, le projet essaie de le détecter automatiquement:

- Windows: `python-qgis-ltr.bat`, `python-qgis.bat`, puis quelques chemins QGIS courants.
- Linux/Docker: `/usr/bin/python3`, `/usr/bin/python`, puis `python3` ou `python` dans le `PATH`.

Si QGIS est installé ailleurs, configurez explicitement:

```bash
# Linux / Docker
export REPORTGENERATOR_QGIS_PYTHON=/usr/bin/python3
export REPORTGENERATOR_QGIS_PREFIX=/usr

# Windows PowerShell
$env:REPORTGENERATOR_QGIS_PYTHON = "C:\Program Files\QGIS\3_40\bin\python-qgis-ltr.bat"
$env:REPORTGENERATOR_QGIS_PREFIX = "C:\Program Files\QGIS\3_40"
```

Les alias `QGIS_PYTHON`, `QGIS_PREFIX_PATH` et `QGIS_PREFIX` sont aussi pris en charge.
