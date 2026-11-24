# LPO reportGenerator

Génère des rapports Word (textes chiffrés, tableaux, graphiques, cartes QGIS) à partir des bases GeoNature LPO. Plusieurs types de rapport sont disponibles, choisis par le champ `list_analyse` du formulaire de demande :

| `list_analyse` | Rapport |
|---|---|
| `analyse_eolien` | synthèse avifaune pour un projet éolien ([fiche](src/reportgenerator/dossiers/eolien/METHODO.md)) |
| `atlas_nicheur` | état des connaissances + atlas des nicheurs ([fiche](src/reportgenerator/dossiers/generique/METHODO.md)) |
| autre valeur / vide | état des connaissances |

Documentation complète : [doc.md](doc.md).

## Usage

```bash
poetry install

# toutes les demandes en attente
poetry run reportgenerator generate --service gnlpoaura --limit 100
poetry run reportgenerator generate --service gnlpoaura --dry-run

# une demande précise
poetry run reportgenerator run --service gnlpoaura --id_area 2336982 --area_name "mon_projet" \
    --referee "Personne référente" --buffer 5 --list_analyse "atlas_nicheur" --output "mon_projet.docx"

# outils (sans base ni QGIS)
poetry run reportgenerator dossiers                  # types de rapport disponibles
poetry run reportgenerator check --dossier eolien    # vérifie template Word + analyses
poetry run pytest
```

- `run` et `generate` marquent la demande comme traitée en cas de succès.
- Sortie : `src/reportgenerator/outputs/<zone>/`, sauf si `--output_dir` ou la variable `OUTPUT_DIR` est définie.
- Si `poetry run` échoue avec le Python de wapt : `poetry config virtualenvs.use-poetry-python true`.

## Configuration QGIS

Les rendus QGIS utilisent un interpréteur Python QGIS externe. Par défaut, le projet essaie de le détecter automatiquement :

- Windows : `python-qgis-ltr.bat`, `python-qgis.bat`, puis quelques chemins QGIS courants.
- Linux/Docker : `/usr/bin/python3`, `/usr/bin/python`, puis `python3` ou `python` dans le `PATH`.

Si QGIS est installé ailleurs, configurez explicitement :

```bash
# Linux / Docker
export REPORTGENERATOR_QGIS_PYTHON=/usr/bin/python3
export REPORTGENERATOR_QGIS_PREFIX=/usr

# Windows PowerShell
$env:REPORTGENERATOR_QGIS_PYTHON = "C:\Program Files\QGIS\3_40\bin\python-qgis-ltr.bat"
$env:REPORTGENERATOR_QGIS_PREFIX = "C:\Program Files\QGIS\3_40"
```

Les alias `QGIS_PYTHON`, `QGIS_PREFIX_PATH` et `QGIS_PREFIX` sont aussi pris en charge.
