"""Fabrique un corpus simulé de 50 pièces de procédure pénale, déjà indexées
(structures synthétiques déterministes, sans coût LLM), pour tester le
scénario « dossier de 50 pièces »."""
import json, os, random
import fitz

random.seed(42)
BASE = '/Users/stephaneleroi/Dev/demo_pageindex/PageIndex_Chat_UI'
UPLOADS = os.path.join(BASE, 'uploads')
DOCS = os.path.join(BASE, 'results', 'documents')

TYPES = [
    ("PV d'audition", "le Brigadier MARTIN", "audition de {tem} sur les faits du {date}"),
    ("Rapport d'expertise", "le Dr LAMBERT, expert", "expertise {sujet} ordonnée par le juge"),
    ("Ordonnance", "le juge d'instruction FAVRE", "ordonnance de {acte}"),
    ("Réquisitoire", "le procureur de la République", "réquisitoire {sujet}"),
    ("Rapport éducatif", "l'éducatrice DURAND", "situation éducative du mineur"),
]
TEMOINS = ["M. Bernard", "Mme Petit", "M. Moreau", "Mme Garnier", "M. Lefort"]
SUJETS = ["balistique", "psychiatrique", "téléphonique", "comptable", "ADN"]
ACTES = ["placement sous contrôle judiciaire", "perquisition", "mise en examen", "renvoi"]

created = []
for i in range(1, 51):
    t, auteur, objet_tpl = TYPES[i % len(TYPES)]
    objet = objet_tpl.format(tem=TEMOINS[i % 5], date=f"{(i%28)+1:02d}/03/2024",
                             sujet=SUJETS[i % 5], acte=ACTES[i % 4])
    # Fait unique traçable par pièce ; la pièce 47 porte LE fait du test de retrieval
    if i == 47:
        fait = ("Le témoin, Mme ROUSSEAU, déclare avoir vu un fourgon rouge vif "
                "immatriculé en Corrèze quitter l'entrepôt vers 23h15 le soir des faits, "
                "avec un phare arrière cassé.")
        t, auteur, objet = "PV d'audition", "le Brigadier MARTIN", "audition du témoin Mme ROUSSEAU"
    else:
        fait = f"Constat n°{i} : élément matériel référencé E-{i:03d} consigné au scellé S-{i:03d}."

    doc_id = f"20260612_0001{i:02d}_c{i:03d}"
    filename = f"Piece_{i:02d}_{t.replace(' ', '_').replace(chr(39), '')}.pdf"
    dir_name = f"{doc_id}_{filename}"

    p1 = (f"{t} — Pièce n°{i}\n{objet}\nRédigé par {auteur}, le {(i%28)+1:02d}/03/2024.\n"
          f"Dossier d'instruction n°2024/118.\n\nExposé :\n{fait}\n")
    p2 = (f"Suite et fin de la pièce n°{i}.\nObservations complémentaires et signature.\n"
          f"Signé : {auteur}.\n")

    # PDF minimal (2 pages) pour la récupération au démarrage + visionneuse
    pdf = fitz.open()
    for txt in (p1, p2):
        page = pdf.new_page()
        page.insert_text((72, 90), txt.split('\n')[0], fontsize=14)
        y = 130
        for line in txt.split('\n')[1:]:
            page.insert_text((72, y), line[:90], fontsize=10); y += 14
    pdf.save(os.path.join(UPLOADS, f"{doc_id}_{filename}"))

    tree = [{
        "node_id": "0000",
        "title": f"{t} — Pièce n°{i} ({objet})",
        "start_index": 1, "end_index": 2,
        "summary": (f"Il s'agit d'un {t.lower()} (pièce n°{i} du dossier 2024/118), rédigé par "
                    f"{auteur} le {(i%28)+1:02d}/03/2024 : {objet}. {fait[:140]}"),
        "text": f"<page_1>\n{p1}\n</page_1>\n<page_2>\n{p2}\n</page_2>\n",
        "nodes": [],
    }]
    os.makedirs(os.path.join(DOCS, dir_name), exist_ok=True)
    json.dump({"doc_name": filename, "structure": tree},
              open(os.path.join(DOCS, dir_name, 'structure.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump({"doc_id": doc_id, "filename": filename, "result_dir_name": dir_name,
               "status": "ready", "created_at": 1781200000 + i, "page_count": 2,
               "error_message": "", "stage": "done", "stage_message": "Indexation terminée",
               "stage_started_at": 0.0},
              open(os.path.join(DOCS, dir_name, 'metadata.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump({"summary": f"{t} n°{i} — {objet}, rédigé par {auteur}.",
               "key_findings": [fait[:120]], "main_topics": [t], "suggested_questions": []},
              open(os.path.join(DOCS, dir_name, 'analysis.json'), 'w'), ensure_ascii=False, indent=1)
    created.append(doc_id)

print(f"{len(created)} pièces fabriquées (la n°47 porte le fait test : fourgon rouge / Mme ROUSSEAU)")
