"""Diagnostic + PROTOTYPE de pré-segmentation déterministe des pièces (read-only,
sans LLM). Pour chaque fichier : signets PDF (niv.1) et frontières produites par
`segment_pieces()` (signal TYPOGRAPHIQUE, inspiré du LayoutChunker d'ocr_v2_src).
Sert à juger ce que le déterministe attrape AVANT de le câbler dans
`page_index_builder` (cf. ETUDE-SEGMENTATION-PIECES.md). Lancer dans le venv :
    .venv/bin/python tests/diag_segments.py
"""
import os
import sys
import statistics
import pymupdf

# Racine du projet sur le path (pour importer config / pageindex depuis tests/).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FILES = [
    ("Amal Hassan", "../data/Dossier Amal Hassan.pdf"),
    ("Théo", "../data/Dossier Théo Blanchet.pdf"),
    ("Rapports_LSC", "uploads/20260616_192819_0da4_Rapports_LSC.pdf"),
    ("Synthèse_2026", "../data/Synthèse_2026.pdf"),
]


def _body_size(doc) -> float:
    """Taille de police du CORPS = médiane des spans de texte long."""
    sizes = []
    for pg in doc:
        for b in pg.get_text("dict").get("blocks", []):
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    if len(s.get("text", "").strip()) > 30:
                        sizes.append(round(s.get("size", 10), 1))
    return statistics.median(sizes) if sizes else 10.0


def _top_title(pg, frac: float = 0.22):
    """Plus gros span dans le HAUT de page (< frac de la hauteur)."""
    top, txt = 0.0, ""
    for b in pg.get_text("dict").get("blocks", []):
        if b.get("bbox", [0, 1e9])[1] < pg.rect.height * frac:
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    t = s.get("text", "").strip()
                    if t and s.get("size", 0) > top:
                        top, txt = s.get("size", 0), t
    return top, txt


def _title_like(t: str) -> bool:
    return (1 <= len(t) <= 80 and not t.endswith((".", ",", ";", ":"))
            and len(t.split()) <= 12 and any(c.isalpha() for c in t))


def segment_pieces(doc, ratio: float = 1.25):
    """Frontières de pièces par signal TYPOGRAPHIQUE : une page qui s'ouvre sur un
    gros titre (≥ ratio × corps, ligne courte titre-like) = début de pièce. Seuil
    élevé = CONSERVATEUR (mieux vaut sous-segmenter que couper une pièce)."""
    body = _body_size(doc)
    starts = []
    for i, pg in enumerate(doc):
        top, txt = _top_title(pg)
        if i == 0 or (top >= body * ratio and _title_like(txt)):
            starts.append((i + 1, txt))
    bounds = []
    for k, (pn, t) in enumerate(starts):
        end = (starts[k + 1][0] - 1) if k + 1 < len(starts) else len(doc)
        bounds.append((pn, end, t))
    return bounds, body


def _page_heads(doc, n_lines: int = 5, max_chars: int = 200):
    """Pour chaque page : ses premières lignes non vides (compact, pour le LLM).
    On envoie plusieurs lignes : sur certains dossiers le séparateur (bloc
    Nom/Prénom/Écrou) est SOUS l'en-tête courant, pas en 1re ligne."""
    heads = []
    for i, pg in enumerate(doc):
        lines = [x.strip() for x in pg.get_text("text").splitlines() if x.strip()]
        heads.append((i + 1, " | ".join(lines[:n_lines])[:max_chars]))
    return heads


def llm_piece_starts(doc):
    """ÉTAGE 3 — UN seul appel LLM : « quelles pages débutent un nouveau document ? »
    Bien moins cher que le découpage récursif (on n'envoie que les en-têtes de page),
    et sémantique (comprend qu'un bloc sans gros titre est une nouvelle pièce)."""
    import json as _json
    import re as _re
    from config import config_manager
    from pageindex.utils import ChatGPT_API
    cfg = config_manager.get_model_config("text")
    model, base = cfg.get("name"), cfg.get("base_url")
    key = cfg.get("api_key") or "ollama-local"
    listing = "\n".join(f"p{pn}: {h}" for pn, h in _page_heads(doc))
    prompt = f"""Ce PDF réunit PLUSIEURS documents distincts dans un même fichier (un dossier de pièces).
Voici la/les première(s) ligne(s) de chaque page :

{listing}

Indique les pages où commence un NOUVEAU document/pièce (notice, rapport, note, ordonnance,
certificat, audition, avis, requête, lexique, procès-verbal…). Une SOUS-SECTION d'un même
document (ex. « Situation familiale », « Conclusions », « Recommandations », « Chiffres clés »)
n'est PAS un nouveau document. La page 1 est toujours un début.
Réponds UNIQUEMENT en JSON : {{"starts": [liste des numéros de page de début]}}"""
    raw = ChatGPT_API(model, prompt, api_key=key, base_url=base)
    starts = []
    m = _re.search(r"\{.*\}", raw or "", _re.DOTALL)
    if m:
        try:
            starts = _json.loads(m.group(0)).get("starts", [])
        except Exception:
            starts = []
    if not starts:
        starts = _re.findall(r"\b\d{1,3}\b", raw or "")
    starts = sorted({int(s) for s in starts if 1 <= int(s) <= len(doc)})
    if 1 not in starts:
        starts = [1] + starts
    return starts, raw


if __name__ == "__main__":
    import sys
    RUN_LLM = "llm" in sys.argv
    for name, path in FILES:
        print("=" * 72)
        print(f"### {name} — {path}")
        if not os.path.exists(path):
            print("  INACCESSIBLE"); continue
        doc = pymupdf.open(path)
        toc = doc.get_toc()
        lvl1 = [(t, p) for (lvl, t, p) in toc if lvl == 1]
        print(f"  pages={len(doc)} | signets={len(toc)} (dont {len(lvl1)} niv.1)")
        if lvl1:
            print("  niv.1:", [f"p{p}:{t[:22]}" for t, p in lvl1[:10]])
        bounds, body = segment_pieces(doc)
        print(f"  [typo] corps={body} → {len(bounds)} pièce(s) : "
              + ", ".join(f"p{a}-{b}" for a, b, _ in bounds))
        if RUN_LLM:
            starts, _raw = llm_piece_starts(doc)
            segs = [(s, (starts[i + 1] - 1 if i + 1 < len(starts) else len(doc)))
                    for i, s in enumerate(starts)]
            print(f"  [LLM étage 3] {len(starts)} pièce(s) : "
                  + ", ".join(f"p{a}-{b}" for a, b in segs))
        doc.close()
