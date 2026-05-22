#!/bin/python3

from docx import Document
from docx.shared import Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.enum.section import WD_SECTION
from docx.shared import Mm
from docx.oxml import OxmlElement
from docx.text.paragraph import Paragraph

from pathlib import Path
from db_auth import get_connection
from queries import SyntheseQueries
from analysis.common.tables.generic_table import insert_general_table, insert_generic_table
from analysis.common.tables.species_table import insert_species_table

LAYOUTS = {
    "normal": {
        "width": Inches(6),
        "height": None,
        "full_page": False,
    },

    "A4": {
        "width": Mm(170),
        "height": Mm(247),
        "full_page": True,
    },

    "A3": {
        "width": Mm(250),
        "height": Mm(370),
        "full_page": True,
    },
}

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

## def insert_table_after_placeholder(document, placeholder, data):

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



def insert_paragraph_after(paragraph):
    new_p = OxmlElement("w:p")
    paragraph._p.addnext(new_p)
    return Paragraph(new_p, paragraph._parent)


def insert_images_from_folder(document, folder: Path, layout="normal"):

    folder = Path(folder)
    config = LAYOUTS.get(layout)

    if not config:
        raise ValueError(f"Layout inconnu : {layout}")
    images = list(folder.glob("*.png"))

    for img in images:
        placeholder = f"{{{{{img.name}}}}}"
        for paragraph in document.paragraphs:
            if placeholder in paragraph.text:
                # suppression du placeholder
                paragraph.text = paragraph.text.replace(placeholder, "")
                # ---------- IMAGE NORMALE ----------
                if not config["full_page"]:
                    run = paragraph.add_run()
                    run.add_picture(
                        str(img),
                        width=config["width"]
                    )
                # ---------- IMAGE PLEINE PAGE ----------
                else:
                    # paragraphe après le placeholder
                    image_p = insert_paragraph_after(paragraph)
                    image_p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                    run = image_p.add_run()
                    run.add_picture(
                        str(img),
                        width=config["width"],
                        height=config["height"]
                    )
                    # saut de page après
                    page_break_p = insert_paragraph_after(image_p)
                    page_break_p.add_run().add_break()
                break

def generate_report(service_name: str, output_file: str, id_area: int, referee: str, list_analyse: str, buffer: int, area_name: str, analysis_result: dict):

    TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
    OUTPUT_DIR = Path(__file__).resolve().parent / "outputs" / area_name

    with get_connection(service_name) as conn:
        synthese_queries = SyntheseQueries(conn=conn, id_area=id_area, buffer=buffer)
        synthese_queries.set_global_data()
        tableau_data = synthese_queries.get_resum_taxo_group()
        tableau_species = synthese_queries.get_species_data()

    template_path = TEMPLATE_DIR / "Rapport_template.docx"
    dir_dataviz = OUTPUT_DIR / "dataviz"
    dir_maps = OUTPUT_DIR / "maps"

    print(f"Génération du rapport Word à partir du template {output_file}...")
    #print(f"chemin pour dataviz {dir_dataviz}...")
    #print(f"chemin pour carte {dir_maps}...")

    document = Document(template_path)

    from docx.enum.style import WD_STYLE_TYPE

    tableau_data_dict = tableau_data[0]

    replace_text(document, {
    "AREA_NAME": area_name,
    "REFEREE": referee,
    #"DATE_REPORT": date.today(),
    "NB_DATA": tableau_data_dict["nb_data_tot"],
    })

    columns_taxo = [
        ('Groupe taxonomique', 'group_taxo'),
        ('Nombre de données', 'nb_data_tot'),
        ("Nombre d'espèces", 'nb_espece'),
        ("Espèces nicheuses", 'nb_espece_nicheuse'),
        ("Espèces protégées", 'nb_espece_protege'),
        ("Espèces en danger", 'nb_espece_lr'),
        ("Espèces en danger nicheuses", 'nb_espece_lr_nicheuse'),
    ]

    insert_general_table(
        document=document,
        placeholder="{{TABLE_TAXO}}",
        data=tableau_data,
        columns=columns_taxo
    )   

    insert_species_table(
        document=document,
        placeholder="{{TABLE_ESP}}",
        data=tableau_species
    )

    #insert_table_after_placeholder(document, "{{TABLE_TAXO}}", tableau_data)

    insert_images_from_folder(document, dir_dataviz, "normal")
    insert_images_from_folder(document, dir_maps, "A4")
    
    document.save(output_file)




