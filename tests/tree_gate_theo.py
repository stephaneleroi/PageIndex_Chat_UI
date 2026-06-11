"""Contrôle qualité de l'arbre du dossier Théo contre la vérité du PDF :
chaque pièce doit commencer à la page où son contenu commence réellement."""
import json, sys, urllib.request
import fitz

PDF = '/Users/stephaneleroi/Dev/demo_pageindex/data/Dossier Théo Blanchet.pdf'
pdf = fitz.open(PDF)
pages = [p.get_text() for p in pdf]

# Vérité terrain : où chaque pièce commence (l'en-tête "Document N" dans le corps, pas la liste de la p.1)
truth = {}
for n in range(1, 6):
    for i, t in enumerate(pages):
        if i == 0:  # la liste de pièces en p.1 ne compte pas
            continue
        if f"Document {n}" in t:
            truth[n] = i + 1
            break
print("vérité terrain (début réel des pièces):", truth)

docs = json.load(urllib.request.urlopen('http://localhost:5001/api/documents'))['documents']
theo = next(d for d in docs if 'Theo' in d['filename'] and d['status'] == 'ready')
tree = json.load(urllib.request.urlopen(f"http://localhost:5001/api/documents/{theo['doc_id']}/tree"))['tree']

def walk(n):
    if isinstance(n, list):
        for x in n: yield from walk(x)
        return
    yield n
    yield from walk(n.get('nodes', n.get('children', [])))

ok = True
found = {}
for node in walk(tree):
    title = node.get('title', '')
    for n in range(1, 6):
        if title.startswith(f"Document {n}"):
            found[n] = (node['node_id'], node['start_index'], node['end_index'])
for n, real_start in truth.items():
    if n not in found:
        print(f"✗ Document {n}: ABSENT de l'arbre"); ok = False; continue
    nid, s, e = found[n]
    # tolérance : la pièce peut commencer en bas de la page précédente (page partagée)
    good = real_start - 1 <= s <= real_start
    print(f"{'✓' if good else '✗'} Document {n} [{nid}]: arbre p.{s}-{e}, réel p.{real_start}")
    ok = ok and good
print("=== ARBRE", "CONFORME" if ok else "NON CONFORME", "===")
sys.exit(0 if ok else 1)
