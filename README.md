# LPO reportGenerator

Python script to generate Word reports from GeoNature LPO databases.

## Usage

```bash
poetry install

poetry run reportgenerator --service <mon_service_pg> --output <mon_rapport.docx> [--output_dir <repertoire_de_sortie>] --id_area <mon_rapport.docx> --referee <mon_rapport.docx> --list_analyse <mon_rapport.docx> --buffer <numero_buffer_en_km> --area_name <mon_nom_de_projet>
```

Sans `--output_dir`, les fichiers sont générés dans `src/reportgenerator/outputs/<area_name>`.
