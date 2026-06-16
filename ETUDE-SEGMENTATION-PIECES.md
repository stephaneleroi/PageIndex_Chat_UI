# Étude — Pré-segmentation déterministe des pièces

> **Statut : étude / conception.** Rien n'est implémenté. À reprendre sur une
> **branche dédiée**. Ce document est autoporteur : contexte, faits mesurés,
> architecture proposée, point d'insertion exact, risques, et le script de
> diagnostic (à déposer en `tests/diag_segments.py`).

## 1. Problème

Sur un **fichier composite** (plusieurs pièces dans un seul PDF/.docx —
`Rapports_LSC.docx` = 4 rapports, `Dossier Théo` = 5 documents), ce sont
aujourd'hui **les frontières de pièces qui dépendent du LLM** :

- `page_index_main` (`pageindex/page_index.py:1092`) construit l'arbre via
  `tree_parser` (`:1055`) → `meta_processor` (`:960`, modes `process_no_toc` /
  `process_toc_with_page_numbers`) : détection de sommaire, vérification entrée
  par entrée, découpage récursif. **C'est l'étape lente** (`gpt-oss` / `light`
  sur Ollama, en série — observé à plus de 30 min sur un petit `.docx`).
- La **détection des pièces est déjà déterministe** (`piece_head_nodes`,
  `pageindex/utils.py:839` ; miroir `DocumentAgent._piece_heads`,
  `services/agent.py:905`) — pur Python, regex souple. **Mais elle s'applique en
  AVAL** : elle ne fait que *lire* les frontières que le LLM a posées. Elle hérite
  donc des erreurs de frontière du LLM.

**Idée à creuser :** poser les frontières de pièces **en amont, de façon
déterministe** (souple, sans libellés codés en dur), puis ne lancer le LLM que
pour la hiérarchie interne + les fiches de chaque pièce. Cela répond au **point
dur n°1** de l'unification hiérarchique (« garantir : nœuds de niveau 1 =
pièces ») et accélère (beaucoup de pièces tombent sous le court-circuit
`SMALL_DOC_MAX_PAGES`).

## 2. Inspiration : `ocr_v2_src` (`legal_evidence`)

Architecture **opposée** à PageIndex — lue le 2026-06-16. À retenir / à écarter :

- ✅ **`layout.py` `LayoutChunker`** : découpage **déterministe par typographie**
  — `_heading_level` détecte les titres par **taille de police relative**
  (≥ 1.5× corps → niv. 1, ≥ 1.22× → niv. 2, gras → niv. 3), `heading_path`
  hiérarchique, suppression d'en-têtes par position (`_is_running_header`,
  haut de page < 13 %). Zéro LLM, zéro libellé en dur. **Bon socle pour le
  signal typographique.**
- ❌ **Segmentation des pièces = physique** : `ZipCaseIngestor` exige 1 PDF = 1
  pièce (le ZIP *porte* la séparation). Il **évite** le composite, ne le résout
  pas. Inutile pour `Rapports_LSC`.
- ❌ **Retrieval = embeddings** (ColNomic visuel + Harrier texte, recherche
  hybride). C'est le RAG « similarité » que notre projet refuse par principe
  (cf. `ARCHITECTURE.md`). Non réutilisable.

## 3. Faits mesurés sur nos 3 fichiers (diagnostic read-only)

Signaux **déterministes** réellement présents (script § 7) :

| Fichier | Type | Signets PDF (`get_toc()`) | Autre signal | Verdict |
|---|---|---|---|---|
| **Synthèse_2026** (114 p.) | document unique, PDF natif | ✅ 6 signets niv. 1 = le plan exact (Avertissement, Chapitre intro, 3 Parties) | titres typo présents | 🟢 **trivial, fiable** |
| **Dossier Théo** (14 p.) | composite, PDF natif | ⚠️ 14 signets niv. 1 **mélangés** : « Document 1/2 » (vraies frontières) **et** sous-sections (« Scolarité », « Santé »…) | — | 🟡 **exploitable avec filtrage** |
| **Rapports_LSC** (9 p.) | composite, **.docx→PDF** | 🔴 **0 signet** | en-tête « SPIP » **identique sur les 9 pages** (mobilier, pas frontière) ; vrai séparateur = bloc d'identité `NOM/PRÉNOM/ÉCROU` réapparaissant **p.1, 3, 6, 8** — **libellé variable** (« RAPPORT LSC » p.1/3 vs « condamnée » p.6/8) | 🔴 **difficile en générique** |

Détail Rapports_LSC (les 4 pièces réelles) : p.1 GIRARD Hugo (écrou 75832),
p.3 HASSAN Karim, p.6 GONZALEZ Diego (113849), p.8 OUALI Rayan (105334). Un
motif `RAPPORT` raterait **2 frontières sur 4** (libellé change).

## 4. Verdict honnête

**Réaliste, mais pas universel.** Le déterministe est un excellent **chemin
rapide opportuniste**, pas un remplacement du LLM :

- **Signets présents** (PDF natifs : Synthèse, en partie Théo) → segmentation
  **gratuite, instantanée, fiable**.
- **Signets absents** (`.docx` convertis, scans, impressions — le quotidien des
  dossiers) → aucun signal *générique* fiable. Le LLM reste **irremplaçable** là
  où il faut *comprendre* qu'un nouveau bloc « Nom/Écrou » = nouvelle pièce.

## 5. Architecture proposée : cascade (du moins cher au plus cher)

1. **Signets PDF** (`doc.get_toc()`) si présents et réguliers → frontières.
   Coût nul. *Filtrage* (cas Théo) : ne garder que le niveau des pièces (croiser
   avec un gabarit récurrent « Document N », ou détecter le niveau dominant).
2. **Sinon, périodicité d'un gabarit d'en-tête** : après retrait du mobilier
   commun (déjà fait par `strip_repeated_page_furniture`), repérer un **bloc
   structuré qui réapparaît périodiquement** en tête de page (cas Rapports_LSC :
   bloc Nom/Prénom/Écrou). Souple = détecter la *récurrence d'un motif*, pas un
   libellé figé.
3. **Repli** : aucun signal → soit **1 appel LLM ciblé** (« liste uniquement les
   pages de début de pièce » — bien moins cher que le découpage récursif), soit
   le comportement actuel (1 fichier = 1 pièce). Repli **conservateur** : en cas
   de doute, **sous-segmenter** (rater une frontière dégrade en douceur) plutôt
   que **sur-segmenter** (couper une pièce → contamination, viole le critère 1).

Une fois les frontières posées, chaque pièce passe par le flux **existant** :
courte (≤ `SMALL_DOC_MAX_PAGES`) → 1 nœud sans LLM ; longue → `tree_parser` sur
ses seules pages. La structure produite est **directement** « racines = pièces »,
ce que `_piece_heads` / `piece_head_nodes` attendent déjà.

## 6. Point d'insertion exact (vérifié)

Dans `page_index_main` (`pageindex/page_index.py:1108` `page_index_builder`),
**juste après** `page_list = get_page_tokens(doc)` (`:1103`) et **avant** le test
`if len(page_list) <= SMALL_DOC_MAX_PAGES` (`:1109`) :

```
page_list = get_page_tokens(doc)            # liste de tuples (texte, nb_tokens)
boundaries = segment_pieces(page_list, doc) # NOUVEAU : [(start,end,title), …]
if len(boundaries) <= 1:
    # comportement actuel inchangé (un seul document)
    ...
else:
    # une racine par pièce ; chaque pièce → court-circuit court / tree_parser
    structure = []
    for (start, end, title) in boundaries:
        sub_pages = page_list[start-1:end]
        if len(sub_pages) <= SMALL_DOC_MAX_PAGES:
            structure.append({'title': title, 'start_index': start, 'end_index': end})
        else:
            sub_tree = await tree_parser(sub_pages, opt, ...)   # indices à recaler
            structure.extend(sub_tree)  # ou envelopper dans un nœud-pièce
```

Repères de code utiles :
- `SMALL_DOC_MAX_PAGES = 4` (`pageindex/utils.py:706`) — court-circuit « 1 nœud,
  zéro LLM de structure » déjà existant (`page_index.py:1109`).
- `get_page_tokens` (`pageindex/utils.py:475`) : `page_list` = liste de
  `(texte_nettoyé, nb_tokens)` ; ouvre le PDF via `pymupdf` → **`doc.get_toc()`
  accessible** ici.
- Aval inchangé : `add_node_text_with_labels` → `split_shared_boundary_pages` →
  `merge_redundant_children` → `generate_summaries_for_structure`
  (`page_index.py:1121-1141`). Le **régime compilation/unique** (`is_compilation`,
  `utils.py:862`) et les **fiches par pièce** (`:892`) restent tels quels.
- ⚠️ **Recalage d'indices** : `tree_parser` raisonne en pages 1..N de SA
  sous-liste ; après coup, ré-additionner `start-1` aux `start_index`/`end_index`
  et aux `physical_index` du sous-arbre.

**Conformité paradigme (critère 3) :** on ne touche ni au retrieval (raisonnement
sur l'arbre) ni aux fiches LLM ; on décide seulement des frontières de niveau 1.

## 7. Leviers annexes

- **Conserver les signets à la conversion `.docx`→PDF** (`routes/api.py`
  `_convert_to_pdf_with_libreoffice`, `:209`). LibreOffice peut exporter les
  styles « Titre 1 » en bookmarks PDF (filtre PDF `ExportBookmarks`). Si
  `Rapports_LSC.docx` a des titres stylés, on récupère **gratuitement** le cas 1
  (signets) au lieu d'une heuristique fragile. **À tester en priorité** — peut
  rendre l'étage 2 inutile sur les `.docx`.
- **Vitesse — nuance** : le gain vient surtout du court-circuit
  `SMALL_DOC_MAX_PAGES` (Rapports_LSC = 4 pièces de 2-3 p. → **0 appel LLM de
  structure**). Mais la lenteur observée vient d'abord de `gpt-oss` sur Ollama,
  pas de l'absence de segmentation : la segmentation **réduit** le travail LLM,
  elle ne le supprime pas pour les pièces longues.

## 8. Risques / garde-fous

- **Sur-segmentation = danger n°1** (couper une pièce en deux → contamination,
  citations fausses, viole le critère 1). Défaut **conservateur** et asymétrique,
  comme `is_compilation`.
- **Scans purs** : pas de texte natif → signaux faibles. Repli LLM/vision.
- **Signets bruités** (Théo) : niv. 1 ⊋ frontières de pièces → filtrage requis,
  sinon sur-segmentation.
- Valider sur **plusieurs tirages** et **vérifier les pages citées** après
  réindexation (cf. `CLAUDE.md`, `tests/accept_chauvin.py`).

## 9. Prochaines étapes (branche dédiée)

1. Déposer le script en `tests/diag_segments.py` (fait une fois l'indexation en
   cours terminée — éviter le reload Werkzeug).
2. Tester le levier `.docx`→signets (étage 1 gratuit ?).
3. Prototyper `segment_pieces` étage 1 (signets + filtrage) avec repli sûr sur
   l'existant ; valider sur Synthèse + Théo.
4. Étage 2 (périodicité de gabarit) seulement si nécessaire (Rapports_LSC).

## 10. Script de diagnostic (read-only, sans LLM)

À déposer en `tests/diag_segments.py`. Lancer depuis la racine du projet :
`.venv/bin/python tests/diag_segments.py`. Adapter `CIBLES` aux chemins réels.

```python
"""Diagnostic READ-ONLY : quels signaux DÉTERMINISTES de frontière de pièce
existent dans nos PDF ? Aucun LLM, aucune écriture. Sert à juger le réalisme
d'une pré-segmentation déterministe AVANT de coder quoi que ce soit."""
import re
import pymupdf

CIBLES = [
    ("Rapports_LSC", "uploads/20260616_150636_d032_Rapports_LSC.pdf"),
    ("Dossier Théo", "../data/Dossier Théo Blanchet.pdf"),
    ("Synthèse_2026", "../data/Synthèse_2026.pdf"),
]

# Motifs de DÉBUT de pièce (diagnostic uniquement — pour voir s'ils existent ;
# en prod on ne hard-coderait pas, on détecterait la RÉCURRENCE d'un gabarit).
DEBUT = re.compile(r"^\s*(document|pi[eè]ce|annexe|rapport|proc[eè]s[- ]verbal|"
                   r"audition|notification|requ[eê]te|certificat|compte[- ]rendu)\b",
                   re.IGNORECASE)
PAGINATION = re.compile(r"\b(\d{1,3})\s*/\s*(\d{1,3})\b")

for nom, path in CIBLES:
    try:
        doc = pymupdf.open(path)
    except Exception as e:
        print(f"\n### {nom} — INACCESSIBLE ({e})")
        continue
    n = len(doc)
    print(f"\n{'='*70}\n### {nom} — {n} pages\n{'='*70}")

    # (A) Signets PDF (le plus fiable s'ils existent)
    toc = doc.get_toc()
    lvl1 = [(lvl, t, p) for (lvl, t, p) in toc if lvl == 1]
    print(f"(A) SIGNETS PDF : {len(toc)} entrées, dont {len(lvl1)} de niveau 1")
    for lvl, t, p in lvl1[:12]:
        print(f"      p.{p:>3}  {t[:60]}")

    # (B/C/D) Signaux page par page
    print("(B/C/D) signaux par page (début de pièce / reset pagination / gros titre) :")
    body_sizes = []
    for page in doc:
        d = page.get_text("dict")
        for b in d.get("blocks", []):
            for l in b.get("lines", []):
                for s in l.get("spans", []):
                    if len(s.get("text", "")) > 30:
                        body_sizes.append(s.get("size", 10))
    body = sorted(body_sizes)[len(body_sizes)//2] if body_sizes else 10.0

    for i, page in enumerate(doc):
        pn = i + 1
        txt = page.get_text("text")
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        first = lines[0] if lines else ""
        debut = bool(DEBUT.match(first))
        pags = PAGINATION.findall(txt)
        reset = any(a == "1" for a, b in pags)
        d = page.get_text("dict")
        top_size = 0.0
        for b in d.get("blocks", []):
            if b.get("bbox", [0, 999])[1] < page.rect.height * 0.25:
                for l in b.get("lines", []):
                    for s in l.get("spans", []):
                        if s.get("text", "").strip():
                            top_size = max(top_size, s.get("size", 0))
        gros = top_size >= body * 1.3
        flags = []
        if debut: flags.append("DÉBUT")
        if reset: flags.append("RESET-PAGIN")
        if gros: flags.append(f"GROS-TITRE({top_size:.0f}/{body:.0f})")
        if flags:
            print(f"      p.{pn:>3} [{' '.join(flags)}]  « {first[:55]} »")
    doc.close()
```
