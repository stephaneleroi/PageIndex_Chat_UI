# Étude : parsing layout-aware (ocr_v2_src) vs construction des nœuds PageIndex

*Étude du 12/06/2026, demandée avant toute implémentation. Code étudié :
`/Users/stephaneleroi/Dev/demo_pageindex/ocr_v2_src` (~2 100 lignes,
14 modules). Verdict empirique inclus (heuristiques rejouées sur le corpus
réel de procédure).*

## 1. Ce que fait le pipeline du collègue

Architecture complète, lue intégralement :

1. **Ingestion** (`ingestion.py`) : PDF (ou ZIP de PDF, avec garde-fous
   sérieux — taille, chiffrement, doublons par SHA-256), rendu PNG par page,
   texte natif PyMuPDF, **OCR Tesseract fra+eng si < 40 caractères natifs**,
   indicateurs de qualité par page (`is_scan`, `low_text_confidence`).
2. **Chunking layout-aware** (`layout.py`) : blocs PyMuPDF
   (`get_text("dict", sort=True)` : texte + bbox + taille de police + gras),
   corps estimé par la **médiane des tailles** des blocs substantiels,
   titres détectés par seuils typographiques (H1 ≥ 1,5 × corps,
   H2 ≥ 1,22 ×, H3 = gras ≈ corps), chunks de 1 200-1 800 caractères dont
   les frontières respectent les titres, **chemin hiérarchique hérité de
   page en page** (`document > titre > sous-titre > page N`), **bbox par
   chunk stockée à l'indexation**.
3. **Stockage** (`db.py`) : SQLite (WAL) + **FTS5** (texte et chemin
   hiérarchique indexés, `remove_diacritics`).
4. **Recherche** (`retrieval.py`) : **hybride** — embeddings denses Harrier
   (sur `chemin hiérarchique + texte`, modèle local vérifié par manifeste),
   BM25/FTS5, embeddings visuels de pages, **fusion par rangs réciproques**.
5. **Réponse** (`answering.py`) : extractive (sans LLM) ou LLM, avec
   **vérification de claims** citation par citation.

C'est un système **RAG à embeddings** soigné, pensé pour le même domaine
(pièces judiciaires) et les mêmes exigences (citations auditables, bbox de
surlignage, tout en local).

## 2. La question de fond : deux paradigmes

| | ocr_v2_src | POC Réponses Sourcées |
|---|---|---|
| Unité d'index | chunk de ~1 200 caractères (taille fixe, frontières aidées par les titres) | nœud = **section sémantique** (plage de pages, résumé identitaire) |
| Hiérarchie | inférée par **seuils typographiques** (déterministe, instantané, gratuit) | inférée par **raisonnement LLM** sur le texte (coûteux, non déterministe) |
| Retrieval | embeddings + BM25 + fusion | **raisonnement LLM sur l'arbre** (vectorless) |
| Citation | bbox du chunk, stockée à l'indexation | page citée par le rédacteur, surlignage réattribué a posteriori |
| OCR | Tesseract (< 40 car.), sans coordonnées | LLM vision (< 20 car. ou scan < 200 car.), sans coordonnées |

Reprendre son **retrieval** est exclu par décision structurante du projet
(paradigme PageIndex pur, vectorless). La question posée — reprendre son
approche pour **le parsing et la construction des nœuds** — reste légitime :
la hiérarchie typographique pourrait en théorie remplacer ou assister la
construction d'arbre LLM. D'où le test empirique.

## 3. Verdict empirique : ses heuristiques sur NOTRE corpus

Heuristiques de `layout.py` rejouées à l'identique sur les pièces réelles :

| Pièce | Titres typographiques détectés | Sections trouvées par l'arbre LLM |
|---|---|---|
| SAISINE/Interpellation (2 p.) | 1 : « PROCES-VERBAL » (28 pt) ; page 2 : rien (10 pt uniforme) | PROCES-VERBAL, AFFAIRE, OBJET, SAISINE, Interpellation |
| Audition CARDON (2 p.) | 2 : « PROCES-VERBAL », « PV n° » ; page 2 : rien | + AFFAIRE, OBJET, SUR SON IDENTITE, SUR LES FAITS, Questions et Réponses |
| Compte-rendu d'enquête (6 p.) | corrects (SUITES JUDICIAIRES, sections numérotées) **+ bruit** (« Code INSEE » en H3, H1 éclaté en 3 blocs) | structure équivalente, sans bruit |
| Dossier Théo Blanchet (14 p., 8 pièces internes) | **4 titres seulement** — la plupart des frontières de pièces ratées | les 8 pièces internes identifiées |

Diagnostic : dans les PV de police, les intitulés de sections (« AFFAIRE : »,
« OBJET : », « SUR LES FAITS ») sont à la **même taille que le corps** —
aucun signal typographique ne les distingue. Les heuristiques de seuils,
calibrées pour des publications éditoriales (le filtre d'en-têtes contient en
dur « synthèses du rapport public annuel » — des rapports de la Cour des
comptes), **sous-détectent massivement sur ce corpus**. La sémantique
(« ceci est une rubrique de PV ») n'est accessible qu'au LLM. C'est la
limite que le collègue annonce lui-même pour les scans, mais elle vaut ici
même pour les PDF textuels.

**Conclusion : ne pas remplacer la construction d'arbre LLM par la
hiérarchie typographique.** Sur ce corpus, on y perdrait l'essentiel de la
structure (et donc du retrieval par raisonnement).

## 4. Ce qui mérite d'être repris (dans le paradigme)

Par ordre de valeur décroissante :

1. **La bbox calculée à l'indexation** — l'idée la plus forte du pipeline.
   Chez nous, le surlignage est **réattribué a posteriori** en faisant
   correspondre le texte des blocs PyMuPDF au texte des nœuds : les trois
   correctifs livrés aujourd'hui (fusion des nœuds identiques, attribution
   au plus spécifique, attribution ligne à ligne) sont des rustines sur
   cette correspondance fondamentalement fragile. Si, à l'indexation, on
   conservait pour chaque nœud les **offsets de blocs** qui le composent
   (PageIndex décide des frontières, PyMuPDF fournit blocs et bbox), le
   surlignage deviendrait exact par construction — et les textes de nœuds
   d'une même page cesseraient de s'emboîter (frontières intra-page nettes,
   fin du nœud pleine-page qui rafle tout).
2. **Les signaux typographiques comme INDICES pour le LLM** (pas comme
   décideurs) : annoter le texte soumis à la construction d'arbre
   (`[TAILLE 28, GRAS]` devant les candidats-titres) aiderait la détection
   de structure sans rien lui imposer — utile sur les documents éditoriaux
   (Théo, rapports), neutre sur les PV. Expérimental : à mesurer sur
   `tests/tree_gate_theo.py` avant adoption.
3. **Les indicateurs de qualité par page** (`is_scan`,
   `low_text_confidence`, provenance du texte) : stockés à l'indexation et
   affichables dans l'IHM (« cette pièce est un scan, texte issu de l'OCR ») —
   transparence utile pour un usage judiciaire, coût quasi nul.
4. **Tesseract en OCR de second repli** : plus rapide et plus sobre que le
   LLM vision pour les scans textuels propres ; le LLM vision reste
   supérieur sur les formulaires dégradés (notre certificat médical). Ordre
   raisonnable : natif → Tesseract → vision. Même limite que lui : pas de
   coordonnées (le surlignage des scans reste page entière).
5. **`get_text("dict", sort=True)`** : l'ordre de lecture trié — un
   paramètre que notre extraction n'utilise pas, pertinent pour les mises
   en page à colonnes.

## 5. Ce qui ne doit pas être repris

- **Embeddings (Harrier, visuels) + BM25 + fusion** : c'est l'anti-thèse de
  la décision « PageIndex pur » — le retrieval par similarité réintroduirait
  exactement ce que le projet a choisi d'exclure (« similarité ≠
  pertinence »).
- **Chunks à taille fixe (1 200/1 800 caractères)** : nos nœuds sont des
  sections sémantiques résumées ; les découper en chunks casserait les
  résumés identitaires, pivot du retrieval par raisonnement.
- **Le filtre d'en-têtes spécifique** (« synthèses du rapport public
  annuel ») : notre `strip_repeated_page_furniture` est générique
  (répétition inter-pages) et couvre déjà ce besoin.

## 6. Recommandation

L'approche du collègue ne doit pas remplacer la construction des nœuds —
le test empirique montre qu'elle rate la structure des PV (1 à 4 titres
détectés là où l'arbre LLM trouve toutes les sections). En revanche, son
pipeline contient une idée structurellement meilleure que la nôtre sur un
point : **la traçabilité géométrique (bbox) établie à l'indexation plutôt
que reconstruite a posteriori**. Si une évolution devait être retenue, c'est
celle-là (point 4.1) : elle supprimerait toute la classe de bugs de
surlignage corrigée aujourd'hui, sans toucher au paradigme — PageIndex
continue de décider des frontières, on mémorise simplement *où* elles
tombent dans la géométrie de la page.

Points 4.2 à 4.5 : améliorations opportunistes, à coût et risque faibles,
non urgentes. Aucune implémentation n'est lancée sans validation explicite.
