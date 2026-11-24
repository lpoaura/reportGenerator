"""plan_docx.py <docx> : titres, placeholders et paragraphes courts (structure du template)."""
import sys
from docx import Document
d = Document(sys.argv[1])
for i, p in enumerate(d.paragraphs):
    t = p.text.strip()
    st = p.style.name
    if st.startswith(("Heading", "Titre")) or "{{" in t:
        print(i, f"[{st}]", t[:110])
