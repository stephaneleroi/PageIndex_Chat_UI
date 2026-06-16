# Protocole A/B — passer (ou non) tout sur `gpt-oss:120b`

> **But** : décider, sur preuves, si `gpt-oss:120b` peut remplacer
> `nemotron-3-super` sur le profil `text` (fiches + rédaction + étapes agent) et,
> à terme, unifier aussi `light` → **un seul modèle, zéro swap Ollama**.
> Rien n'est basculé tant que l'A/B n'a pas tranché.

## Pourquoi c'est jouable (faits vérifiés le 2026-06-16)

- **Mémoire** : `gpt-oss:120b` = 60 Go de poids ; or `ollama ps` montre la
  machine faisant déjà tourner `nemotron-3-super` à **92 Go** en VRAM. Le 120b
  tient dans une enveloppe déjà encaissée.
- **Contexte** : l'app **ne passe aucun `num_ctx`** (cf. `services/rag_service.py`
  `_get_client`) → la fenêtre = défaut Ollama. `ollama ps` montre Nemotron alloué
  à **131072** *sans* `num_ctx` custom → le défaut effectif de cette installation
  est large (réglage global, pas le 4096 historique). Les budgets de l'app
  (`SIMPLE_CONTEXT_BUDGET`=60 000 car., `CORPUS_INVENTORY_BUDGET`=45 000 car. ≈
  20–30k tokens) y rentrent très largement.
- **Bascule réversible sans reload** : `config_manager.get_model_config` est lu à
  **chaque** appel (aucun cache de client), et `config.json` (gitignored) n'est
  pas surveillé par le reloader Werkzeug. Donc un `PUT /api/config/models/text`
  prend effet **immédiatement** et se **restaure** sans redémarrer.

## Étape 0 — confirmer le contexte du 120b (1 min)

```
ollama run gpt-oss:120b "ok" >/dev/null 2>&1 &   # le charge
sleep 20 && ollama ps                            # colonne CONTEXT
```
Attendu : `CONTEXT` ≥ ~32768 (idéalement 131072 comme Nemotron). Si bridé bas,
créer une variante Modelfile `PARAMETER num_ctx 65536` (comme `gpt-oss-20b-128k`)
**avant** de tester — sinon les budgets de l'app seraient tronqués → citations
cassées (viole le critère 1).

## Méthode

Script `tests/ab_redaction.py` (§ fin). Pour chaque modèle de `CANDIDATS`
(Nemotron d'abord = référence, puis 120b) :
1. `PUT /config/models/text` → bascule le profil `text` sur le modèle.
2. Pose chaque question à **vérité terrain** (mode kb sur le seul Dossier Théo →
   toutes les citations se résolvent sur ce PDF), **`TIRAGES`=3** fois.
3. **Restaure** le modèle initial (dans un `finally`).

Questions : note CHAUVIN (vérité terrain connue : fin de note = cannabis/CER/27
nov.), situation scolaire (ciblée), synthèse du dossier (rédaction longue +
citations groupées). Mode kb car Théo est un composite (voie corpus).

## Métriques (juge de paix = les pages)

- **Pages exactes** : pour chaque citation `(…, page N)`, des mots de
  l'affirmation qui précède doivent apparaître sur la page N du PDF (méthode
  `tests/accept_chauvin.py`). **C'est le critère décisif** (critère 1).
- **Fuite de raisonnement** : marqueurs de *chain-of-thought* dans la réponse
  finale (`analysis`, `<|channel|>`, « we need to », « je dois chercher »…) —
  **risque spécifique gpt-oss** (modèle de raisonnement verbeux).
- **Complétude** : présence des éléments attendus (qualité, critère 2).
- **Durée** moyenne, **nb de citations** moyen, longueur.

## Critère de décision

Retenir `gpt-oss:120b` **si**, sur les 3 tirages : taux de pages exactes **≥**
Nemotron (pas de régression), **0 fuite** de raisonnement, complétude
comparable, durée acceptable. Sinon, garder Nemotron sur `text`.
Si retenu → basculer `text` **et** `light` sur `gpt-oss:120b` (fin du swap).

## Lancement

⚠️ **Après** l'indexation E2E en cours (le 120b et Nemotron se disputeraient la
VRAM). Serveur up, aucun document en `pending`/`indexing`. Déposer d'abord le
script en `tests/ab_redaction.py` (éviter le reload : à faire hors indexation).

```
.venv/bin/python tests/ab_redaction.py
```

## Script (`tests/ab_redaction.py`)

```python
"""A/B rédaction : Nemotron (actuel) vs gpt-oss:120b, sur questions sourcées
RÉELLES, plusieurs tirages, avec vérification des PAGES citées contre le PDF.

Réversible : bascule le profil `text` via l'API /config/models (effet immédiat,
sans reload car config.json n'est pas surveillé), puis RESTAURE le modèle initial
dans un finally. Ne modifie aucun .py, ne change rien de façon permanente.
"""
import json
import re
import time
import urllib.request

import fitz
import socketio

BASE = "http://localhost:5001"
CANDIDATS = ["nemotron-3-super:latest", "gpt-oss:120b"]  # ordre = référence d'abord
TIRAGES = 3
DATA = "/Users/stephaneleroi/Dev/demo_pageindex/data"

DOC_FILTER = "Theo"
PDF = f"{DATA}/Dossier Théo Blanchet.pdf"
QUESTIONS = [
    {"label": "CHAUVIN/note",
     "q": ("Résume moi la note écrite par Monsieur CHAUVIN\nEducateur UEHC\n"
           "A l'attention de Monsieur LEMOINE\nJuge des Enfants\n"
           "Tribunal pour Enfants de LIMOGES"),
     "attendus": ["cannabis", "cer", "27 novembre"]},
    {"label": "scolarite",
     "q": "Quelle est la situation scolaire de Théo ? Cite tes sources.",
     "attendus": []},
    {"label": "synthese",
     "q": "Fais une synthèse du dossier de Théo Blanchet.",
     "attendus": []},
]


def api(path, data=None, method=None):
    req = urllib.request.Request(
        BASE + "/api" + path,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"},
        method=method or ("POST" if data else "GET"),
    )
    return json.load(urllib.request.urlopen(req))


def ask(doc_id, query):
    sess = api("/sessions", {"mode": "kb", "doc_ids": [doc_id], "title": "ab"})
    sid = sess["session"]["session_id"]
    sio = socketio.Client()
    answer, steps, done = [], [], [False]
    sio.on("chunk", lambda d: answer.append(d.get("content", "")))
    sio.on("agent_step", lambda d: steps.append(d.get("tool")))
    sio.on("done", lambda d: done.__setitem__(0, True))
    sio.on("error", lambda d: print("  SOCKET ERR:", d))
    sio.connect(BASE)
    t0 = time.time()
    sio.emit("agent_chat", {"session_id": sid, "query": query,
                            "model_type": "text", "use_memory": True})
    while not done[0] and time.time() - t0 < 900:
        time.sleep(0.5)
    sio.disconnect()
    return "".join(answer), steps, time.time() - t0


FUITE = re.compile(r'"thought"|tree_search\(|<\|channel\|>|\banalysis\b|'
                   r"we need to|let'?s |il faut que je|je dois (?:d'abord|chercher)",
                   re.IGNORECASE)
CITE = re.compile(r"\(\s*(?:doc:[^,]+,\s*)?node[_\s]*\w+\s*,\s*pages?[\s ]*(\d+)")
CLAIM_CITE = re.compile(r"([^.\n]{25,}?)\(\s*(?:doc:[^,]+,\s*)?node[_\s]*\w+\s*,\s*pages?[\s ]*(\d+)")


def evaluate(text, pages_txt, attendus):
    cites = [int(p) for p in CITE.findall(text)]
    bad = 0
    for m in CLAIM_CITE.finditer(text):
        claim, page = m.group(1), int(m.group(2))
        if not (1 <= page <= len(pages_txt)):
            bad += 1
            continue
        words = re.findall(r"[A-Za-zÀ-ÿ]{6,}", claim)[:8]
        hay = pages_txt[page - 1].lower()
        if words and not any(w.lower() in hay for w in words):
            bad += 1
    return {
        "len": len(text),
        "cites": len(cites),
        "pages_exactes": (len(cites) - bad, len(cites)),
        "fuite": bool(FUITE.search(text)),
        "attendus_ok": sum(1 for a in attendus if a.lower() in text.lower()),
        "attendus_n": len(attendus),
    }


def main():
    docs = api("/documents")["documents"]
    theo = next(d for d in docs if DOC_FILTER in d["filename"] and d["status"] == "ready")
    pages_txt = [p.get_text() for p in fitz.open(PDF)]

    text_cfg = api("/config/models/text")
    initial_name = text_cfg.get("name")
    print(f"Profil text initial : {initial_name}  | Théo doc_id={theo['doc_id']}")

    results = {}
    try:
        for model in CANDIDATS:
            api("/config/models/text", {**text_cfg, "name": model}, method="PUT")
            print(f"\n{'='*64}\n### MODÈLE text = {model}\n{'='*64}")
            results[model] = []
            for qc in QUESTIONS:
                for k in range(TIRAGES):
                    text, steps, dur = ask(theo["doc_id"], qc["q"])
                    ev = evaluate(text, pages_txt, qc["attendus"])
                    results[model].append((qc["label"], ev, dur, len(steps)))
                    ok, tot = ev["pages_exactes"]
                    print(f"  {qc['label']:12} t{k+1} | {dur:5.0f}s | "
                          f"{ev['cites']:2} cit ({ok}/{tot} pages exactes) | "
                          f"fuite={'OUI' if ev['fuite'] else 'non'} | "
                          f"attendus {ev['attendus_ok']}/{ev['attendus_n']} | "
                          f"{ev['len']} car")
    finally:
        api("/config/models/text", {**text_cfg, "name": initial_name}, method="PUT")
        print(f"\nProfil text RESTAURÉ → {initial_name}")

    print(f"\n{'='*64}\n### BILAN ({TIRAGES} tirages × {len(QUESTIONS)} questions)\n{'='*64}")
    print(f"{'modèle':28} {'pages exactes':>14} {'fuite':>7} {'durée moy':>10} {'cit moy':>8}")
    for model, rows in results.items():
        ok = sum(e["pages_exactes"][0] for _, e, _, _ in rows)
        tot = sum(e["pages_exactes"][1] for _, e, _, _ in rows)
        fuites = sum(1 for _, e, _, _ in rows if e["fuite"])
        dmoy = sum(d for _, _, d, _ in rows) / max(1, len(rows))
        cmoy = sum(e["cites"] for _, e, _, _ in rows) / max(1, len(rows))
        taux = f"{ok}/{tot} ({100*ok//max(1,tot)}%)"
        print(f"{model:28} {taux:>14} {fuites:>3}/{len(rows):<3} {dmoy:>9.0f}s {cmoy:>8.1f}")
    print("\nDécision : retenir gpt-oss:120b si pages exactes ≥ Nemotron, "
          "0 fuite, durée acceptable.")


if __name__ == "__main__":
    main()
```
