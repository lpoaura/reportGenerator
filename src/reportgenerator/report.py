#!/bin/python3

from docx import Document
from db_auth import get_connection
from queries import SyntheseQueries

def generate_report(service_name: str, output_file: str, id_dataset: int):

    with get_connection(service_name) as conn:
        synthese_queries = SyntheseQueries(conn=conn, id_dataset=id_dataset)
        count_data = synthese_queries.get_global_count()
        count_by_taxo_group = synthese_queries.get_count_by_taxo_group()

    document = Document()
    document.add_heading("Rapport de synthèse", level=1)

    # Résumé
    document.add_heading("Nombre total de données", level=2)
    document.add_paragraph(
        f"Nombre total de données : {count_data['count_data']}"
    )

    # Tableau clients
    document.add_heading("Par groupe taxo", level=2)

    table = document.add_table(rows=1, cols=2)
    header = table.rows[0].cells
    header[0].text = "Groupe taxonomique"
    header[1].text = "Nombre de données"

    for data in count_by_taxo_group:
        row = table.add_row().cells
        row[0].text = str(data["taxo_group"])
        row[1].text = str(data["count_data"])
    
    document.save(output_file)
