#!/bin/python3

from docx import Document
from docx.shared import Inches
from pathlib import Path
from db_auth import get_connection
from queries import SyntheseQueries



def replace_text(document, replacements: dict):

    # 1. Paragraphes classiques
    for paragraph in document.paragraphs:
        for key, value in replacements.items():
            placeholder = "{{" + key + "}}"
            if placeholder in paragraph.text:
                paragraph.text = paragraph.text.replace(
                    placeholder,
                    str(value)
                )

    # 2. Tableaux (IMPORTANT)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    for key, value in replacements.items():
                        placeholder = "{{" + key + "}}"
                        if placeholder in paragraph.text:
                            paragraph.text = paragraph.text.replace(
                                placeholder,
                                str(value)
                            )

def insert_table_after_placeholder(document, placeholder, data):

    for paragraph in document.paragraphs:

        if placeholder in paragraph.text:

            paragraph.text = paragraph.text.replace(placeholder, "")

            table = document.add_table(rows=1, cols=10)

            header = table.rows[0].cells

            header[0].text = "Groupe taxonomique"
            header[1].text = "Nombre de données"
            header[2].text = "Nombre d'espèces"
            header[3].text = "Nombre d'espèces nicheuses"
            header[4].text = "Nombre d'espèces protégées"
            header[5].text = "Nombre d'espèces protégées nicheuses"
            header[6].text = "Nombre d'espèces en danger"
            header[7].text = "Nombre d'espèces en danger nicheuses"
            header[8].text = "Nombre de données mortalité"
            header[9].text = "Nombre espèces mortalité"

            for item in data:

                row = table.add_row().cells

                row[0].text = str(item["group_taxo"])
                row[1].text = str(item["nb_data_tot"])
                row[2].text = str(item["nb_espece"])
                row[3].text = str(item["nb_espece_nicheuse"])
                row[4].text = str(item["nb_espece_protege"])
                row[5].text = str(item["nb_espece_protege_nicheuse"])
                row[6].text = str(item["nb_espece_lr"])
                row[7].text = str(item["nb_espece_lr_nicheuse"])
                row[8].text = str(item["nb_data_mortalite"])
                row[9].text = str(item["nb_esp_mortalite"])

            paragraph._element.addnext(table._element)

            break
        
def insert_image(document, placeholder, image_path):
    for paragraph in document.paragraphs:
        if placeholder in paragraph.text:
            paragraph.text = paragraph.text.replace(placeholder, "")
            run = paragraph.add_run()
            run.add_picture(image_path, width=Inches(6))
            break



def insert_images_from_folder(document, folder: Path):
    folder = Path(folder)
    images = list(folder.glob("*.png"))
    for img in images:
        placeholder = f"{{{{{img.name}}}}}"  # {{filename.png}}
        for paragraph in document.paragraphs:
            if placeholder in paragraph.text:
                paragraph.text = paragraph.text.replace(placeholder, "")
                run = paragraph.add_run()
                run.add_picture(str(img), width=Inches(6))
                break

def generate_report(service_name: str, output_file: str, id_area: int, referee: str, list_analyse: str, buffer: int, area_name: str, analysis_result: dict):

    TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
    OUTPUT_DIR = Path(__file__).resolve().parent / "outputs" / area_name

    with get_connection(service_name) as conn:
        synthese_queries = SyntheseQueries(conn=conn, id_area=id_area, buffer=buffer)
        synthese_queries.set_global_data()
        tableau_data = synthese_queries.get_resum_taxo_group()

    template_path = TEMPLATE_DIR / "Rapport_template.docx"
    dir_dataviz = OUTPUT_DIR / "dataviz"
    dir_maps = OUTPUT_DIR / "maps"

    print(f"Génération du rapport Word à partir du template {output_file}...")
    print(f"chemin pour dataviz {dir_dataviz}...")
    print(f"chemin pour carte {dir_maps}...")

    document = Document(template_path)

    tableau_data_dict = tableau_data[0]

    replace_text(document, {
    "AREA_NAME": area_name,
    "REFEREE": referee,
    #"DATE_REPORT": date.today(),
    "NB_DATA": tableau_data_dict["nb_data_tot"],
    })

    insert_table_after_placeholder(document, "{{TABLE_TAXO}}", tableau_data)

    #insert_images_from_folder(document, output_dirs["dataviz"])
    #insert_images_from_folder(document, output_dirs["maps"])
    
    document.save(output_file)


