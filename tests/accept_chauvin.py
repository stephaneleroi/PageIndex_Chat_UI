"""Test d'acceptation : question CHAUVIN sur le dossier Théo.
Critères : bonne pièce (la note d'information), résumé complet (début ET fin
de la note), citations au bon format, et RENVOIS DE PAGES VÉRIFIÉS contre le
texte réel du PDF."""
import json, re, sys, time
import socketio
import fitz
import urllib.request

PDF = '/Users/stephaneleroi/Dev/demo_pageindex/data/Dossier Théo Blanchet.pdf'
QUESTION = ("Résume moi la note écrite par Monsieur CHAUVIN\nEducateur UEHC\n"
            "A l'attention de Monsieur LEMOINE\nJuge des Enfants\nTribunal pour Enfants de LIMOGES")

def api(path, data=None):
    req = urllib.request.Request('http://localhost:5001/api' + path,
        data=json.dumps(data).encode() if data else None,
        headers={'Content-Type': 'application/json'}, method='POST' if data else 'GET')
    return json.load(urllib.request.urlopen(req))

docs = api('/documents')['documents']
theo = next(d for d in docs if 'Theo' in d['filename'] and d['status'] == 'ready')
doc_id = theo['doc_id']
sess = api('/sessions', {'mode': 'kb', 'doc_ids': [doc_id], 'title': 'acceptation CHAUVIN'})
session_id = sess['session']['session_id']

sio = socketio.Client()
answer, nodes, steps, reflects, done = [], [], [], [], [False]
sio.on('chunk', lambda d: answer.append(d.get('content','')))
sio.on('nodes', lambda d: nodes.append(d.get('nodes', [])))
sio.on('agent_step', lambda d: steps.append((d.get('tool'), str(d.get('observation',''))[:90])))
sio.on('agent_reflect', lambda d: reflects.append(d.get('score')))
sio.on('error', lambda d: print('ERREUR SOCKET:', d))
def _done(d): done[0] = True
sio.on('done', _done)
sio.connect('http://localhost:5001')
t0 = time.time()
sio.emit('agent_chat', {'session_id': session_id, 'query': QUESTION, 'model_type': 'text', 'use_memory': True})
while not done[0] and time.time() - t0 < 900:
    time.sleep(0.5)
sio.disconnect()
text = ''.join(answer)
elapsed = time.time() - t0

# ---------- Vérifications ----------
results = []
def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"{'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail else ""))

pdf = fitz.open(PDF)
pages_txt = [p.get_text() for p in pdf]

# La note = la pièce signée CHAUVIN : pages réelles
note_pages = [i+1 for i, t in enumerate(pages_txt) if 'note d' in t.lower() and 'information' in t.lower()]
sig_page = [i+1 for i, t in enumerate(pages_txt) if 'CHAUVIN' in t]
print(f"(référence PDF : note d'information détectée p.{note_pages}, signature CHAUVIN p.{sig_page})")

check("réponse non vide", len(text) > 300, f"{len(text)} caractères")
check("pas de fuite d'appel d'outil", '"thought"' not in text and 'tree_search(' not in text)
check("durée raisonnable", elapsed < 600, f"{elapsed:.0f}s")
check("une seule étape de recherche (voie simple)", len(steps) <= 2, f"étapes: {[s[0] for s in steps]}")

cites = re.findall(r'\(\s*(?:doc:[^,]+,\s*)?node[_\s]*(\w+)\s*,\s*pages?[\s ]*([\d]+)', text)
check("citations présentes", len(cites) >= 3, f"{len(cites)} citations")

# Vérifier chaque renvoi de page : la page citée doit contenir un mot significatif
# de l'affirmation qui précède la citation
bad_refs = []
for m in re.finditer(r'([^.\n]{25,}?)\(\s*(?:doc:[^,]+,\s*)?node[_\s]*\w+\s*,\s*pages?[\s ]*(\d+)', text):
    claim, page = m.group(1), int(m.group(2))
    if not (1 <= page <= len(pages_txt)):
        bad_refs.append((page, "page hors document")); continue
    words = [w for w in re.findall(r'[A-Za-zÀ-ÿ]{6,}', claim)][:8]
    hay = pages_txt[page-1].lower()
    if words and not any(w.lower() in hay for w in words):
        bad_refs.append((page, f"aucun mot de « {claim.strip()[:50]}… » sur la page"))
check("renvois de pages exacts", not bad_refs, str(bad_refs[:3]) if bad_refs else "tous vérifiés contre le PDF")

# Complétude : début de la note (p.6-7) ET fin (p.8)
debut = any(k in text for k in ['7 août', '07 août', '5 mars', '26 juin', '1 août', '1er août'])
fin = any(k in text.lower() for k in ['cannabis', 'cer', '27 novembre'])
check("couvre le début de la note (p.6-7)", debut)
check("couvre la fin de la note (p.8)", fin)

# Pages citées dans la plage réelle de la note
cited_pages = sorted({int(p) for _, p in cites})
in_range = all(min(note_pages or [6]) <= p <= max(sig_page or [8]) for p in cited_pages)
check("pages citées dans la plage de la note", in_range, f"pages citées: {cited_pages}")

print()
print(f"reflets: {reflects} | nodes: {nodes}")
fails = [r for r in results if not r[1]]
print(f"=== {'ACCEPTATION : SUCCÈS' if not fails else f'ÉCHEC ({len(fails)} critère(s))'} ===")
print("--- RÉPONSE ---")
print(text[:2200])
sys.exit(0 if not fails else 1)
