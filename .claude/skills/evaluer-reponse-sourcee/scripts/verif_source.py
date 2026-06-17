#!/usr/bin/env python3
"""Vérifications déterministes pour auditer une réponse de PageIndex_Chat_UI
contre le TEXTE SOURCE des PDF. À lancer avec le python du venv :

    .venv/bin/python .claude/skills/evaluer-reponse-sourcee/scripts/verif_source.py <cmd> ...

Sous-commandes :
  page  <pdf> <N>          Texte de la PAGE PHYSIQUE N (index PyMuPDF, 1-based).
                           Sert à vérifier qu'une citation (p. N) tombe juste.
  grep  <chemin> <terme>   Cherche <terme> dans les PDF (fichier OU dossier,
                           récursif), avec contexte + page physique de chaque
                           occurrence. Sert à LOCALISER où un fait figure
                           réellement (et à confirmer un artefact de données).
  quote <chemin> <phrase>  Vérifie si <phrase> est un VERBATIM exact du source
                           (différences d'espaces/retours ligne tolérées, mots et
                           ordre identiques). Sert à contrôler les guillemets :
                           une paraphrase entre guillemets est un faux verbatim.

<chemin> = un .pdf, ou un dossier (parcouru récursivement sur *.pdf).

ATTENTION — texte non extractible : un formulaire ou une page-image renvoie
souvent un get_text() vide ou pauvre. Le contenu réel (en-têtes, champs) n'existe
alors que dans l'OCR vision de l'arbre indexé :
results/documents/<...>/structure.json (champ "text" des nœuds, balisé <page_N>).
Toujours recouper là quand `page` rend peu de texte.
"""
import sys, os, re, glob
import fitz


def pdfs(path):
    if os.path.isdir(path):
        return sorted(glob.glob(os.path.join(path, "**", "*.pdf"), recursive=True))
    return [path]


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def pattern(term):
    """Mots du terme dans l'ordre, séparés par n'importe quel blanc (gère les
    retours à la ligne du PDF). Insensible à la casse."""
    parts = [re.escape(w) for w in term.split()]
    return re.compile(r"\s+".join(parts), re.IGNORECASE)


def cmd_page(pdf, n):
    n = int(n)
    doc = fitz.open(pdf)
    if not (1 <= n <= doc.page_count):
        print(f"!! page {n} hors limites — le PDF a {doc.page_count} pages physiques")
        return
    txt = doc[n - 1].get_text().strip()
    print(f"=== {os.path.basename(pdf)} — PAGE PHYSIQUE {n}/{doc.page_count} ===")
    print(txt or "(aucun texte extractible — formulaire/page-image ? "
                 "lire l'OCR du nœud indexé : results/documents/<...>/structure.json)")


def _find(path, term):
    pat = pattern(term)
    out = []
    for pdf in pdfs(path):
        doc = fitz.open(pdf)
        for i, pg in enumerate(doc):
            raw = pg.get_text()
            m = pat.search(raw)
            if m:
                a, b = max(0, m.start() - 70), min(len(raw), m.end() + 70)
                ctx = re.sub(r"\s+", " ", raw[a:b]).strip()
                out.append((os.path.basename(pdf), i + 1, ctx))
    return out


def cmd_grep(path, term):
    hits = _find(path, term)
    if not hits:
        print(f"(aucune occurrence de « {term} »)")
        return
    for name, page, ctx in hits:
        print(f"[{name}] page physique {page} : …{ctx}…")


def cmd_quote(path, phrase):
    hits = _find(path, phrase)
    if hits:
        name, page, _ = hits[0]
        print(f"VERBATIM OK — présent tel quel dans [{name}] page physique {page}")
    else:
        print(f"!! FAUX VERBATIM — « {phrase} » introuvable mot pour mot dans le "
              f"source. Guillemets injustifiés (paraphrase présentée comme citation).")


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = args[0]
    if cmd == "page" and len(args) == 3:
        cmd_page(args[1], args[2])
    elif cmd == "grep" and len(args) >= 3:
        cmd_grep(args[1], " ".join(args[2:]))
    elif cmd == "quote" and len(args) >= 3:
        cmd_quote(args[1], " ".join(args[2:]))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
