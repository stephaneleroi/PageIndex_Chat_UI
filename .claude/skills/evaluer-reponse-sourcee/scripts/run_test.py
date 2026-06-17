#!/usr/bin/env python3
"""Rejoue une question via une VRAIE session KB de l'app (donc visible dans l'IHM)
et capture la réponse + la trace dans un audit Markdown daté. Étape 1 de la chaîne
« lancer un test → évaluer » (l'évaluation, étape 2, est faite par le skill).

Usage (dans le venv, app lancée) :
  .venv/bin/python .claude/skills/evaluer-reponse-sourcee/scripts/run_test.py \
      --dossier <theo|procedure|rapports|synthese> \
      (--question "..." | --question-file <chemin.txt>) \
      --out <audit.md> [--title "..."] [--port 5001]

Pour forcer le map-reduce (T5) : lancer l'app avec PAGEINDEX_CTX_BUDGET bas
(ex. 8000) — la sélection des pièces et l'évaluation restent identiques.
"""
import argparse, json, re, sys, time, datetime, subprocess, urllib.request
import socketio


def git(args):
    """Renvoie une info git du dépôt courant (ou '?' si indisponible)."""
    try:
        return subprocess.check_output(["git"] + args,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "?"

# Sélection des documents d'un dossier par motif de nom de fichier.
FILTERS = {
    "theo":      lambda f: "theo" in f.lower(),
    "procedure": lambda f: any(k in f.upper() for k in
                   ["ACTES GENERAUX", "ACTES_GENERAUX", "MEC_1", "MEC 1", "LEPETIT"]),
    "rapports":  lambda f: "rapports_lsc" in f.lower(),
    "synthese":  lambda f: "synth" in f.lower(),
}


def api(base, path, data=None):
    req = urllib.request.Request(
        base + "/api" + path,
        data=json.dumps(data).encode() if data else None,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET")
    return json.load(urllib.request.urlopen(req))


def _obs(d):
    o = d.get("observation", "")
    if isinstance(o, dict):
        o = o.get("summary", "") or json.dumps(o, ensure_ascii=False)
    return str(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dossier", required=True, choices=list(FILTERS))
    ap.add_argument("--question")
    ap.add_argument("--question-file")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--port", type=int, default=5001)
    a = ap.parse_args()
    question = a.question or open(a.question_file, encoding="utf-8").read().strip()
    base = f"http://localhost:{a.port}"

    docs = api(base, "/documents")["documents"]
    sel = [d for d in docs if d.get("status") == "ready" and FILTERS[a.dossier](d["filename"])]
    if not sel:
        sys.exit(f"Aucun document 'ready' pour dossier={a.dossier}")
    doc_ids = [d["doc_id"] for d in sel]
    title = a.title or f"EVAL {a.dossier}"
    sid = api(base, "/sessions", {"mode": "kb", "doc_ids": doc_ids, "title": title})["session"]["session_id"]

    answer, nodes, steps, reflects, done = [], [], [], [], [False]
    sio = socketio.Client()
    sio.on("chunk", lambda d: answer.append(d.get("content", "")))
    sio.on("nodes", lambda d: nodes.append(d.get("nodes", [])))
    sio.on("agent_step", lambda d: steps.append((d.get("tool"), _obs(d))))
    sio.on("agent_reflect", lambda d: reflects.append(d.get("score")))
    sio.on("error", lambda d: print("ERREUR SOCKET:", d))
    sio.on("done", lambda d: done.__setitem__(0, True))
    sio.connect(base)
    t0 = time.time()
    sio.emit("agent_chat", {"session_id": sid, "query": question,
                            "model_type": "text", "use_memory": True})
    while not done[0] and time.time() - t0 < 1800:
        time.sleep(0.5)
    sio.disconnect()
    text = "".join(answer)
    elapsed = time.time() - t0

    flat = []
    for nl in nodes:
        for n in nl:
            flat.append(str(n.get("id") or n.get("node_id") or n) if isinstance(n, dict) else str(n))
    flat = list(dict.fromkeys(flat))
    is_mr = any("map_reduce" in (t or "").lower() or "map-reduce" in o.lower()
                or "synthèse ciblée" in o or "ciblée par pièce" in o for t, o in steps)
    decomp = sum(1 for t, o in steps if "decompos" in (t or "").lower()
                 or "sous-question" in o.lower() or "section" in o.lower())
    cites = re.findall(r"\bp\.?\s*\d+|page\s+\d+", text, re.I)
    pages = sorted(set(int(re.search(r"\d+", c).group()) for c in cites))

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    desc = git(["describe", "--tags", "--always", "--dirty"])
    lines = [
        f"# Audit (run live) — {title} — {ts}", "",
        f"- **Branche / commit** : `{branch}` @ `{desc}`",
        f"- **Session IHM** : `{sid}` (mode kb) — {len(doc_ids)} document(s)",
        f"- **Question** : {question}",
        f"- **Durée** : {elapsed:.0f}s | réflexion(s) : {reflects}",
        f"- **map-reduce** : {'OUI' if is_mr else 'non'} | indices décomposition : {decomp}",
        f"- **Nœuds mobilisés** : {len(flat)} → {flat}",
        f"- **Citations (pages détectées dans la réponse)** : {len(cites)} → pages {pages}",
        "", "## Étapes (trace agent)",
        "\n".join(f"  {i+1}. [{t}] {o}" for i, (t, o) in enumerate(steps)) or "  (aucune étape)",
        "", "## Réponse complète", text or "(vide)",
    ]
    open(a.out, "w", encoding="utf-8").write("\n".join(lines))
    print(f"OK — {a.out} | map-reduce={is_mr} | {len(flat)} nœuds | {len(cites)} cit | {elapsed:.0f}s")


if __name__ == "__main__":
    main()
