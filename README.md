# LPO reportGenerator

Python script to generate Word reports from GeoNature LPO databases.

## Usage

```bash
poetry install
poetry add plotly kaleido
poetry add kaleido
poetry add geopandas
poetry add openpyxl

poetry run python src/reportgenerator/cli.py --service <mon_service_pg> --output <mon_rapport.docx> --id_area <mon_rapport.docx> --referee <mon_rapport.docx> --list_analyse <mon_rapport.docx> --buffer <numero_buffer_en_km> --area_name <mon_nom_de_projet>
```


