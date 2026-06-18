# Architecture — PageIndex Chat UI (Réponses documentaires sourcées)

> Application de **questions-réponses sur documents, sourcées et 100 % locales**
> (Ollama), bâtie **au-dessus** de la bibliothèque [PageIndex](https://github.com/VectifyAI/PageIndex).
> Ce document est la **référence interne**. Chaque affirmation renvoie au code
> (`fichier — fonction()`), pour qu'on puisse toujours vérifier.

**Plan.** 1. Modèle mental · 2. Vocabulaire · 3. **PageIndex vs notre couche** ·
4. Indexation (à froid) · 5. **La sélection : `tree_search`** · 6. Les briques de
réponse · 7. Routing & matrice voie×brique · 8. Les voies en détail · 9. Citations,
visionneuse, garde-fous · 10. Notes & annotations · 11. Modèles & config ·
12. Fork `pageindex/` · 13. Limites & études.

---

## 1. Le modèle mental (en 30 secondes)

1. **Indexer** : un PDF devient un **arbre** (sa table des matières) ; on calcule
   **une fiche d'identité par « pièce »** (résumé structuré : nature, auteur,
   destinataire, faits saillants…).
2. **Répondre** en **deux temps** :
   - **CHOISIR** où regarder — un LLM **raisonne sur les fiches + titres** de
     l'arbre (jamais sur le texte intégral) pour retenir les bons nœuds : c'est
     `tree_search`.
   - **LIRE puis RÉDIGER** — on charge le **texte** des seuls nœuds retenus et on
     rédige une réponse **citée à la page**.
3. Pas de base vectorielle, pas d'embeddings : on **navigue dans une carte du
   document par raisonnement**, comme un greffier qui feuillette un dossier en
   lisant les intitulés.

**Conséquence fondatrice — la qualité de la fiche EST la qualité du retrieval.**
Comme le *choix* se fait sur les fiches, **une fiche pauvre rend une pièce
invisible**. Cas réel : « résume la note de M. X au juge Y » restait introuvable
parce que la fiche ne portait ni auteur, ni destinataire, ni nature. Le correctif
**conforme** n'a pas été d'ajouter une recherche plein-texte, mais d'**enrichir la
fiche** (§4.3). *Quand une pièce est ratée, on améliore l'arbre — on ne contourne
jamais le paradigme.*

---

## 2. Vocabulaire (à lire avant tout le reste)

```
        DOCUMENT (un PDF / .docx importé)
             │  indexation PageIndex
             ▼
          ARBRE de NŒUDS  (≈ table des matières)
             │
   ┌─────────┴───────────┐
   ▼                     ▼
 PIÈCE (nœud niv. 1)    PIÈCE (nœud niv. 1)
   │  + 1 FICHE          │  + 1 FICHE
   ├─ nœud (section)     ├─ nœud (section)
   └─ nœud (sous-sect.)  └─ …
```

- **Nœud** — unité de l'arbre (`node_id`, ex. `node_0006`) : un *titre*, un *texte*
  (les pages, balisées `<page_N>…</page_N>`), une *plage de pages*. `N` = **page
  physique du PDF** (index PyMuPDF) : citations `(p. N)` et visionneuse partagent
  cette numérotation (le clic ouvre la page N), qui peut différer du **folio
  imprimé** ; l'IHM l'explicite (« Page N du PDF »).

- **Pièce** — **un nœud de premier niveau** (tête **+ tout son sous-arbre**) = **un
  document logique** (une audition, une note, un rapport, un chapitre…). C'est
  **l'unité de travail** : on sélectionne, résume, lit et cite *à la granularité de
  la pièce* (`USE_PIECE_UNIT = True`). Détection **déterministe**
  (`pageindex/utils.py — piece_head_nodes()`) :

  | Forme de l'arbre | Pièces |
  |---|---|
  | ≥ 2 racines | chaque racine est une pièce |
  | 1 racine dont des enfants sont **numérotés** (regex `^\s*(?:document\|pièce\|annexe\|rapport)\s`) | chaque enfant numéroté est une pièce |
  | sinon | le document entier = 1 pièce |

  Un **fichier** contient donc **une** pièce (un PV isolé) ou **plusieurs** (un PDF
  « dossier ») :
  ```
  Cas A — dossier de FICHIERS séparés (Procedure-PN-1 : 25 PDF) → 25 arbres → 25 pièces
  Cas B — FICHIER composite (Dossier Théo : 1 PDF) → 1 arbre →
            ├─ « Document 1 — rapport éducatif »   → PIÈCE
            └─ « Document 2 — Note d'information »  → PIÈCE … (5 pièces)
  ```
  *Pourquoi cette granularité ?* Traiter chaque document logique séparément (citer
  la bonne pièce) et **éviter la contamination** entre pièces voisines d'un fichier.

- **Fiche d'identité** (= « fiche » = **résumé d'une pièce** — synonymes). **Une
  seule** par pièce, format **structuré** (`pageindex/utils.py —
  generate_summaries_for_structure()`) :
  ```
  Nature        : type de pièce (lettre, note, audition, ordonnance, rapport, chapitre…)
  Auteur        : qui l'a écrite/signée (rôle, service)
  Destinataire  : à qui elle s'adresse
  Date et heure : date de la pièce
  Personnes     : chaque personne nommée + son rôle (mis en cause, victime, témoin…)
  Objet         : une phrase — à quoi sert cette pièce
  Points saillants : 2 à 4 phrases, faits clés, CHACUN suivi de sa page « (p. N) »
  ```
  Elle a **deux rôles** : (a) **informer** (survol) et (b) servir de **support de
  sélection** — *c'est sur les fiches que `tree_search` raisonne* (§5). Les `(p. N)`
  rendent **citable** toute réponse bâtie sur les seules fiches.

- **`node_map`** — table calculée à la préparation (nœud → plage de pages, texte,
  bbox de surlignage). Sert aux citations et à la visionneuse.

### 2.1 Profondeur de l'arbre = échelle (pas un autre niveau de fiches)

Une pièce peut être un **nœud unique** (petit document) ou un **sous-arbre profond**
(sections). La profondeur ne sert qu'à **naviguer dans les gros documents** :

```
niveau 1 (entre pièces)  : tree_search sur les FICHES        → quelle PIÈCE ?
niveau 2 (dans une pièce): tree_search sur les TITRES sections → quelles SECTIONS ?
```

Important : on **résume par pièce** (§4.3), donc **seul le nœud de tête porte une
fiche** ; ses sous-nœuds n'ont que leur **titre**. Le niveau 2 raisonne donc sur les
**titres de sections** (+ la fiche de tête en contexte). Petites pièces (≤
`SMALL_DOC_MAX_PAGES = 4`) = un seul nœud, pas de profondeur.

---

## 3. PageIndex (amont) **vs notre couche** — qui fait quoi

Frontière nette : **PageIndex construit l'arbre et le fouille (`tree_search`)** ;
tout le reste — **pièce, fiche identitaire, routing, voies, map-reduce, citations à
la page, notes** — est **notre couche** par-dessus (`services/`, `models/`, IHM).

| Brique | PageIndex (`pageindex/`) | Notre couche |
|---|---|---|
| PDF → arbre de nœuds (sommaire, hiérarchie, `node_id`) | **✅ cœur** | retouches d'extraction (§12) |
| Résumé d'un **nœud** | ✅ prompt canonique… | …**remplacé par une FICHE par PIÈCE** (`generate_summaries_for_structure`) |
| Notion de **pièce** (unité de travail) | ✘ (ne connaît que des nœuds) | **✅** `piece_head_nodes`, régime compilation/doc unique |
| **`tree_search`** (choisir des nœuds sur résumés/titres) | **✅ prompt du cookbook** | on **l'appelle** (niveau 1 sur fiches / niveau 2 sur sections) |
| `remove_fields(tree, ['text'])` (raisonner sans le texte) | ✅ | on l'utilise |
| **Citations à la page** (`<page_N>`, pastilles, visionneuse) | ✘ | **✅** |
| **Routing** (`decompose_query` : intention + `instructions`) | ✘ | **✅** |
| **Les 4 voies** (libre / mono-pièce / synthèse globale / corpus) | ✘ | **✅** `DocumentAgent` |
| **Map-reduce ciblé** + **fiches à chaud** persistées | ✘ | **✅** `_focused_summary` |
| **IDs de citation autorisés**, auto-éval déterministe, **notes** | ✘ | **✅** |

### 3.1 Couches & fichiers

```
┌── IHM (navigateur) ──────── templates/index.html · static/js/app.js · static/css/app.css
├── Serveur ───────────────── app.py / main.py · routes/api.py (REST) · routes/socket_handlers.py (chat)
├── Application (LE CŒUR) ─── services/
│     · agent.py           → DocumentAgent : routing + 4 voies (§7-8)
│     · rag_service.py     → PageIndexService (tree_search, LLM/VLM) + RAGService
│     · indexing_service.py→ index_pdf : pilote l'indexation
│     · prompt_templates.py + prompts/*.jinja → prompts itérés/évalués (§3.2)
│     · skill_manager.py   → skills Markdown injectables
│   models/
│     · document.py        → Document / DocumentStore (arbre, node_map, images, NOTES, FICHES à chaud)
│     · session.py         → ChatSession / Message / SessionStore
├── Bibliothèque ──────────── pageindex/ (fork amont) : page_index.py, utils.py
└── Données (gitignored) ──── uploads/ · results/documents/<id>/{structure.json, images, notes.json, focused_fiches.json}
```

Le retrieval **ne passe plus** par un registre d'outils ni une boucle ReAct
(supprimés) : les voies appellent directement `tree_search` puis la lecture des nœuds.

### 3.2 Prompts externalisés (gabarits Jinja)

Les prompts qu'on **itère et évalue** vivent dans `services/prompts/*.jinja`, chargés
par `prompt_templates.render_prompt(name, **kw)` (Jinja `StrictUndefined` : variable
manquante = erreur). On édite **le gabarit**, pas une chaîne inline (diff lisible,
A/B simple) :

| Gabarit | Rôle | Règles clés |
|---|---|---|
| `grounding_single.jinja` | rédaction voie mono-pièce | citer `(node_<id>, page N)` (id réel) ; pas d'inversion de rôle ; dire si le contexte ne couvre pas |
| `grounding_kb.jinja` | rédaction voie corpus | citer `(doc, node_<id>, page N)` ; **pas d'affirmation d'exhaustivité/absence** ; **guillemets = verbatim exact** |
| `grounding_summary.jinja` | rédaction synthèse globale | citer **par thème** (pas par phrase) ; regrouper plusieurs pièces sous une citation |
| `decompose.jinja` | routing | sortie JSON `{needs_decomposition, items:[{question, intent, instructions}]}` |
| `focused_summary.jinja` | *map* du map-reduce | **chaque fait suivi de `(p. N)`** ; jamais deviner une page ; « (rien) » si la pièce n'apporte rien |

Les builders à flot de contrôle (`agent.py — _build_answer_prompt`, `_build_allowed_citations`…)
restent en Python et **interpolent** ces gabarits.

---

## 4. Indexation — la phase « à FROID »

Une fois par document, à l'import. Produit l'arbre **+** les fiches, **persistés**.
Fiches **« à froid »** = calculées une fois, figées, **neutres** (indépendantes de
toute question) — par opposition aux fiches **« à chaud »** du map-reduce (§8.4).

### 4.1 De l'upload à l'arbre (`routes/api.py` → `indexing_service` → `pageindex`)

1. **Upload** (`routes/api.py — upload_document()`) : PDF/DOCX accepté ; un **`.docx`**
   est converti en PDF (`_convert_to_pdf_with_libreoffice()`, `soffice --headless`).
   Indexation **séquentielle** : un seul document à la fois (`_INDEXING_GATE =
   Semaphore(1)`).
2. **Cache de réimportation SHA-256** (`routes/api.py — _find_cached_index()` /
   `_sha256_file()`) : si un fichier `<nom>.pdf.pageindex.json` (à côté du PDF source,
   `SOURCE_DATA_DIR`, défaut `../data`) a un champ `pdf_sha256` égal à l'empreinte du
   PDF **et** une `structure` → arbre **restauré sans aucun appel LLM**. Sinon, après
   indexation, le résultat y est **réécrit** (`{pdf_sha256, page_count, structure}`).
3. **Construction de l'arbre** (`indexing_service.index_pdf()` →
   `pageindex.page_index_main()`) : extraction texte (PyMuPDF + suppression
   en-têtes/pieds répétés ; OCR vision en repli pour pages scannées), détection du
   sommaire (**20 premières pages**), table « titre → page », vérification LLM +
   réparation (`fix_incorrect_toc_with_retries`, **3 tentatives**), hiérarchie,
   `node_id` (`0000`, `0001`…), texte balisé `<page_N>`, **découpage des pages
   partagées** entre deux pièces, **fusion des nœuds redondants**. Échec → statut
   erreur (bouton « Relancer »).
4. **Résumé par pièce** (§4.3).
5. **Préparation** (`rag_service.prepare_document()`) : rendu JPEG des pages,
   `node_map`, surlignages (bbox) ; statut `ready`. Tout est écrit dans
   `results/documents/<id>/structure.json`.

### 4.2 Pourquoi un résumé **par pièce** (pas par nœud)

`generate_summaries_for_structure()` calcule **une fiche par pièce**, sur le **texte
concaténé** de tout le sous-arbre (tronqué à `PIECE_SUMMARY_MAX_CHARS = 60000`),
stockée sur le **nœud de tête**. Les sous-nœuds gardent leur titre, sans résumé
propre. Bénéfices : beaucoup moins d'appels LLM (4-5 fiches au lieu de 36-43 nœuds) et
une fiche **complète** (pas le seul préambule de l'en-tête).

### 4.3 Régime de résumé (`is_compilation`, détection asymétrique)

| Cas | Détection (`pageindex/utils.py — is_compilation()`) | Traitement |
|---|---|---|
| **Compilation** (pièces indépendantes — **défaut sûr**) | pièces numérotées, **ou** dates/auteurs divergents | fiches **isolées**, en parallèle (`SUMMARY_CONCURRENCY = 3` — sinon N gros appels gèlent Ollama). Anti-contamination. |
| **Document unique** (plan cohérent) | aucune pièce numérotée, dates/auteurs non divergents, **et** natures de plan (chapitre/partie/section/préface…) | fiches **cumulatives** : chaque section reçoit en contexte les fiches précédentes (continuité du fil) |

Mal classer une compilation en document unique **contaminerait** les fiches : le défaut
penche toujours vers **compilation**.

---

## 5. ⭐ La sélection : `tree_search` (la brique centrale)

> **Réponse directe à la question la plus fréquente : oui, `tree_search` choisit les
> nœuds EN LISANT LES FICHES (résumés), pas en raisonnant sur la seule structure.**

### 5.1 Ce que `tree_search` reçoit exactement

`rag_service.py — tree_search(query, tree)` envoie au LLM l'arbre **privé de son seul
champ `text`** : `remove_fields(tree.copy(), ['text'])` — donc `node_id`, **`title`**
et **`summary` (la fiche) RESTENT**. Le prompt l'énonce noir sur blanc :

```
You are given a question and a tree structure of a document.
Each node contains a node id, node title, and a corresponding summary.   ← la FICHE
Your task is to find all nodes that are likely to contain the answer …
Document tree structure: { …arbre sans 'text', avec 'summary'… }
→ réponse JSON { "thinking": "<raisonnement en français>", "node_list": [ids] }
```

Donc la décision se fonde sur **titres + fiches**, jamais sur le texte intégral (qui
ne tiendrait pas dans le contexte, et qu'on veut justement éviter de lire pour
choisir). Le texte n'est lu **qu'après**, à l'étape de lecture (§6).

### 5.2 Deux échelles de sélection

| Échelle | Quoi choisir | Sur quoi le LLM raisonne |
|---|---|---|
| **Niveau 1** (entre pièces) | quelle(s) **pièce(s)** ? | **titres + FICHES** des pièces (signal principal) |
| **Niveau 2** (dans une grosse pièce) | quelles **sections** ? | **titres des sections** + la fiche de tête en contexte |

### 5.3 Comment on rend les fiches « visibles » par `tree_search`

`tree_search` est générique : il lit le champ `summary` des nœuds qu'on lui donne. Au
**niveau 1**, notre voie corpus ne lui passe pas l'arbre brut mais un **arbre de
sélection synthétique** dont chaque nœud-pièce porte, en `summary`, la fiche
construite par `agent.py — _piece_fiche()` / `_selection_fiche()` :

```
summary du nœud-pièce = FICHE de la pièce (résumé de tête)  +  "Sections :\n- titre…\n- titre…"
```

Le commentaire du code le dit : *« résumé du nœud de tête + titres des sous-sections,
**pour que le `tree_search` « voie » le contenu** »* — avec un cas réel cité (un en-tête
ministériel masquant un sujet de concours, **invisible** au niveau 1 sans cette
injection). C'est l'illustration concrète de la leçon fondatrice (§1) : **fiche pauvre
= pièce invisible**.

---

## 6. Les briques de réponse

Les voies recombinent **quatre briques** :

| Brique | Rôle | Origine |
|---|---|---|
| **`tree_search`** | *choisir* les nœuds (sur fiches niv.1 / titres niv.2) — ne lit jamais le texte | **PageIndex** |
| **Lecture du texte** | charger le **texte** des seuls nœuds retenus, pour la rédaction | notre couche |
| **Agrégation de fiches** | utiliser les **fiches déjà calculées** comme contenu (synthèse globale, inventaire en appui) | notre couche |
| **Map-reduce** | *recomposer à chaud* une fiche par pièce sous l'angle de la question, puis réduire | notre couche |

---

## 7. Routing & matrice voie × brique

Événement Socket.IO `agent_chat` → `rag_service.agent_chat_stream` (passthrough) →
`agent.py — run_session()`. Dispatch :

```
question
 ├─ mode kb SANS document ........................ → Conversation libre (modèle nu, §8.1)
 └─ documents sélectionnés
     └─ decompose_query (1 appel LLM, decompose.jinja) :
          • scinde SI plusieurs demandes de NATURES DIFFÉRENTES (→ sections ##)
          • classe l'INTENTION de chaque (sous-)question + une consigne `instructions`
        ┌─────────────────────────────────────────────────────────────┐
        │ "overview" → Synthèse globale → AGRÉGATION DES FICHES (§8.3)  │
        │ "detail"                                                      │
        │   ├─ 1 pièce  → Mono-pièce : tree_search + LECTURE TEXTE (§8.2)│
        │   └─ ≥ 2 pièces → Corpus (§8.4) : tree_search sur fiches →    │
        │        ├─ texte ≤ budget → LECTURE DIRECTE                    │
        │        └─ texte > budget → MAP-REDUCE (fiches à CHAUD)        │
        └─────────────────────────────────────────────────────────────┘
```

`decompose_query` renvoie `{needs_decomposition, items:[{question, intent, instructions}]}` ;
`intent` (`overview`/`detail`) **prime** sur l'ancienne heuristique de mots-clés
`_is_global_summary` (gardée en repli). `instructions` = *ce que le rédacteur / le map
doit extraire* (inspiré du « per-search instructions » d'Open Notebook).

**Matrice — quelle voie mobilise quelle brique** (seul `tree_search` est PageIndex) :

| Voie | Intention | `tree_search` n.1 (fiches) | `tree_search` n.2 (sections) | Lecture **texte** | **Fiches** |
|---|---|:--:|:--:|:--:|---|
| Conversation libre (§8.1) | — *(aucun doc)* | — | — | — | — |
| Mono-pièce (§8.2) | `detail`, 1 pièce | — | ✅ *interne à la pièce* | ✅ | — |
| Synthèse globale (§8.3) | `overview` | — | — | — | **agrégation de toutes** |
| Corpus — lecture directe (§8.4) | `detail`, ≥ 2 p. | ✅ | si pièce volumineuse | ✅ | inventaire en appui |
| Corpus — map-reduce (§8.4) | `detail`, ≥ 2 p., gros volume | ✅ | ✅ | *dans le map* | **fiches à chaud** + inventaire |

**Deux distinctions réglées d'après les tests :**
- **Pièce désignée vs dossier** : « résume *la note de M. X* » (pièce identifiée) =
  `detail` → on **lit le texte** ; « résume *le dossier* » = `overview` → fiches. Le
  mot « résume » seul ne tranche pas : c'est la **cible**.
- **Mono-nature sur N pièces ≠ décomposition** : « détaille **chaque** rapport » est
  **une** demande sur N pièces — **pas** décomposée (sinon le LLM devine un nombre de
  sous-questions et **sous-couvre** : cas réel 2 rapports sur 4). La voie corpus
  sélectionne elle-même toutes les pièces. La décomposition est réservée aux
  **natures différentes** (synthèse ET faits ET versions).

**Constantes (`agent.py`, classe `DocumentAgent`) :** `SIMPLE_CONTEXT_BUDGET = 60000`
(surchargeable par env `PAGEINDEX_CTX_BUDGET`), `SIMPLE_MAX_NODES = 10`,
`CORPUS_SELECT_BUDGET = 48000`, `CORPUS_INVENTORY_BUDGET = 45000`,
`CORPUS_MAX_PIECES_READ = 12`, `CORPUS_PIECE_DRILL_THRESHOLD = 20000`,
`MAP_CONCURRENCY = 3`, `REFLECT_ACCEPT_THRESHOLD = 6`, `USE_PIECE_UNIT = True`.

---

## 8. Les voies, une par une

### 8.1 Conversation libre (`_run_free_chat`)

Mode kb **sans document** : dialogue direct avec le modèle, **aucune instruction
système, aucun style, aucune température** — parité avec un chat Ollama brut (un cas
réel, `DIAGNOSTIC-UEMO.md`, a montré que des consignes de style font confabuler).
Réponses « sans sources » (ni citation, ni note de qualité).

### 8.2 Mono-pièce (`_run_single_simple`) — `detail`, une pièce

Si l'intention est `overview` → délègue à la synthèse globale (§8.3). Sinon, étapes :
1. **un** `tree_search` sur l'arbre de la pièce → ≤ `SIMPLE_MAX_NODES = 10` nœuds ;
2. **lecture du texte** des nœuds (budget `SIMPLE_CONTEXT_BUDGET = 60000`, chaque
   section préfixée de son `node_<id>` réel) ;
3. **rédaction citée** (`grounding_single`, `_build_allowed_citations`) ; en mode
   Vision → images des nœuds + VLM ;
4. **auto-évaluation** (§9.3).

### 8.3 Synthèse globale (`_run_global_summary`) — `overview`

**Aucun `tree_search`, aucune lecture de texte.** On **agrège les fiches de toutes les
pièces** (`_build_summary_entries`, budget par fiche adaptatif) et on rédige une vue
transversale **en un seul appel** (`grounding_summary`). Les fiches portant les
`(p. N)`, la synthèse **reste citée à la page**. Rapide, scalable.

> **Ne pas confondre avec le résumé *incrémental* de l'indexation (§4.3).** Le travail
> « fiches précédentes + section courante » a lieu **à froid, une fois**, pour
> *construire* les fiches d'un document unique. La synthèse globale, elle, **agrège
> des fiches déjà construites** ; « aucune lecture » = on ne relit pas le *texte*.

### 8.4 Corpus (`_run_corpus_simple`) — `detail`, ≥ 2 pièces

Le dossier est vu comme **un seul arbre** dont les enfants sont les pièces.
1. **Sélection niveau 1** : on construit l'**arbre de sélection** (chaque pièce = un
   nœud dont le `summary` est sa fiche + titres de sections, §5.3) et on lance **un**
   `tree_search` dessus (budget `CORPUS_SELECT_BUDGET = 48000`) → pièces retenues
   (≤ `CORPUS_MAX_PIECES_READ = 12`).
2. **Drill-down niveau 2** : une pièce composite **volumineuse**
   (> `CORPUS_PIECE_DRILL_THRESHOLD = 20000` car.) est affinée **section par section**
   (`tree_search` interne) — on ne lira que les sections pertinentes.
3. **Aiguillage selon le volume retenu** (`use_map_reduce = total_len >
   SIMPLE_CONTEXT_BUDGET and len(selected) > 1`) :
   - **lecture directe** du texte (défaut) ;
   - **map-reduce ciblé** sinon (ci-dessous).
4. **Rédaction** (`grounding_kb`) avec l'**inventaire complet** des fiches en appui
   (`_build_corpus_inventory`, `CORPUS_INVENTORY_BUDGET = 45000` — toute pièce reste
   citable même non lue) + `_build_allowed_citations`.
5. **Auto-évaluation** (§9.3).

**Map-reduce ciblé (fiches à CHAUD)** — *pourquoi* : le texte intégral de beaucoup de
pièces ne tient pas dans un contexte unique. *Comment* :
```
   fiches à froid (toutes les pièces) ── tree_search ──► pièces retenues
                                                          │ volume ?
   ≤ budget → LECTURE DIRECTE : texte des pièces ─────────┤
   > budget → MAP-REDUCE :                                 │
       MAP (1 appel / PIÈCE, ≤ MAP_CONCURRENCY=3 en //) :   ← _focused_summary (focused_summary.jinja)
          LEGRAND → « nie les faits (p.2), reconnaît la dispute (p.3) »   ← fiche à CHAUD
          LEPETIT → « accuse LEGRAND (p.1)… »
       REDUCE (1 appel) : confronte → réponse citée (doc, node, page)
```
- `_focused_summary()` résume **une pièce** sous l'angle de la question (+ la consigne
  `instructions`), **conserve les `(p. N)`** (→ citations préservées), renvoie `(rien)`
  → `None` si la pièce n'apporte rien.
- **Cache mémoire** `_focused_cache` (clé `(doc_id, head_id, query, instructions)`) :
  anti-recalcul intra-session.
- **Persistance disque** : chaque fiche est écrite via `store.save_focused_fiche()`
  (`focused_fiches.json`, §10) — elle **survit au redémarrage** et s'affiche dans la
  Vue Structure.

### 8.5 Décomposition (`_run_decomposed` / `_relay_subquery`)

Une question de **natures différentes** est scindée par `decompose_query` ; chaque
sous-question suit la voie de **son** intention, et les réponses sont assemblées en
**sections `##`** sous un seul cycle. `_relay_subquery` masque les marqueurs de cycle
et accumule texte + citations. **Pas** de boucle ReAct.

---

## 9. Citations, visionneuse, garde-fous

### 9.1 Citations & visionneuse (IHM, `static/js/app.js`)

- `linkifyCitations()` transforme les citations du modèle (variantes tolérées :
  `(doc: f.pdf, node_0007, page 3)`, `(node_0007, page 3)`, `(pages 5-6)`, `node_0007`
  nu… ; regex `CITE_RE`) en **pastilles « p. N » cliquables**.
- Clic → `showPagePreviewModal()` : images des pages, défilement à la page citée,
  **surlignage du nœud source** (bbox) ; pour une citation « pages seules », le nœud
  est déduit du `node_map`. Le badge dit **« Page N du PDF »** (folio ≠ index).

### 9.2 IDs de citation autorisés (`_build_allowed_citations`)

La rédaction reçoit la **liste explicite des `node_id` mobilisés** (« n'en cite AUCUNE
autre ») et ne peut citer **que ceux-là**, verbatim — **verrou anti-id-inventé et
anti-contamination**. L'évaluation A/B (`evaluations/RAPPORT_COMPARATIF.md`) a montré
que ce verrou réduit nettement la fuite de contenu entre pièces mal bornées d'un
fichier composite.

### 9.3 Auto-évaluation

- **Note de qualité** (`_estimate_quality`, **déterministe, sans LLM**) : citations
  présentes, `node_id` cités ∈ sources, pages ∈ plages réelles, pénalités des
  citations dégénérées. Affichée « Auto-vérification n/10 ».
- **Réflexion conditionnelle** (`reflect`, LLM) : **sautée** si la réponse est saine
  (> 400 car., ≥ 2 citations, pas de fuite de raisonnement) ; sinon, si score
  < `REFLECT_ACCEPT_THRESHOLD = 6` → **une** recherche complémentaire + réécriture
  (jamais de boucle).
- **Vérification à la demande** : bouton « Vérifier la réponse » (juge LLM,
  `POST /sessions/<id>/messages/<i>/verify`, verdict persisté).

### 9.4 API & Socket.IO

**REST** (`routes/api.py`) : `documents` (CRUD, upload, retry, status, tree,
node-info, analysis, text-highlights, **`notes`** GET/POST/DELETE,
**`focused-fiches`** GET, édition titre/résumé d'un nœud),
**`folders/<folder>/structure`** GET (structure consolidée d'un répertoire, §10.1),
`sessions` (CRUD, truncate, messages, verify), `config/models`, `skills`.
**Socket.IO** (`routes/socket_handlers.py`) — entrée : `agent_chat`, `get_history`,
`stop_generating` ; sortie : `status` / `nodes` / `chunk` / `agent_step` /
`agent_reflect` / `answer_done` / `done` / `stopped` / `error`.

---

## 10. Notes & annotations (persistées, sans toucher l'arbre)

Deux familles de **notes par pièce**, stockées **à part** de l'arbre PageIndex (qui
reste l'index de recherche **intact**), selon **le même motif** (`models/document.py`,
un JSON à côté de `structure.json`) :

| | Notes **utilisateur** | **Fiches à chaud** (map-reduce) |
|---|---|---|
| Origine | saisies (« Ajouter une note ») | générées par le *map* (§8.4) |
| Fichier | `notes.json` | `focused_fiches.json` |
| Méthodes | `add_note` / `get_notes` / `delete_note` | `save_focused_fiche` / `get_focused_fiches` |
| Forme | `{node_id: [{id, text, ts}]}` | `{head_id: [{query, text, nid, ts}]}` |
| Route | `/documents/<id>/notes` | `/documents/<id>/focused-fiches` |
| Persistance | disque (survit au redémarrage) | disque (survit au redémarrage) |

Les deux sont rendues **par pièce** dans la **Vue Structure** (`app.js —
srExtrasHtml` : bloc « 🔥 Fiches à chaud » + bloc « Mes notes »). Les fiches à chaud
sont **dédupliquées par (pièce, question)** ; le cache mémoire `_focused_cache` ne sert
qu'à **recalculer** moins — la **source d'affichage est le disque**.

La **Vue Structure** elle-même est une vue deux panneaux (arbre des pièces persistant
à gauche, lecture du PDF + fiches + notes à droite), en plus des 3 pages
(Bibliothèque · conversation mono-document · questions-réponses KB). Sessions
persistées et **isolées par mode** (`single` / `kb`).

### 10.1 Structure consolidée d'un répertoire (Bibliothèque)

Conceptuellement, **un dossier de N pièces ≡ un document concaténant N pièces** —
c'est déjà ainsi que la voie corpus le traite (arbre synthétique « Dossier », §8.4).
La Bibliothèque le **reflète** : chaque groupe-dossier (« Mes documents ») offre un
aperçu dépliable **« Structure consolidée du dossier »** qui liste **les pièces de
niveau 1 de TOUS ses fichiers prêts** (titre + fiche + pages), cliquables vers la
pièce source (`app.js — loadFolderStructure` / `renderFolderPiece`, **chargé en
lazy** à l'ouverture). Données fournies par `GET /api/folders/<folder>/structure`,
qui agrège via la **détection canonique** `pageindex.piece_head_nodes` (lecture
seule, **0 appel LLM**). Un fichier lui-même composite y voit **toutes** ses pièces
remonter (ex. dossier de 25 fichiers → 30 pièces). **100 % présentation** — aucun
impact indexation/retrieval/citations ; les cartes par fichier restent.

---

## 11. Modèles & configuration (`config.py` → `config.json`, hors git)

| Profil | Usage | Modèle (déploiement local) |
|---|---|---|
| `text` **et** `light` | structure de l'arbre + fiches (indexation) + rédaction + étapes agent | **gpt-oss-120b-64k** |
| `vision` | réponses sur images de pages, OCR des scans | qwen3.6 |

- **Un seul modèle pour tout → zéro swap** Ollama (`text` = `light`). *(Les défauts du
  code `config.py` — `gpt-5-mini`/OpenAI — sont des placeholders ; le `config.json`
  local, hors git, fixe gpt-oss-120b-64k via Ollama.)*
- **Contexte** : l'app **ne passe pas de `num_ctx`** → la fenêtre est celle du
  **Modelfile**. `gpt-oss-120b-64k` = `FROM gpt-oss:120b` + `PARAMETER num_ctx 65536`
  (~76 Go VRAM). **Tout budget doit rester sous 65536**, sinon Ollama tronque
  silencieusement (citations faussées). `SIMPLE_CONTEXT_BUDGET` est surchargeable par
  env **`PAGEINDEX_CTX_BUDGET`** (sert à **forcer le map-reduce en test**, budget bas).
- **Aucune température imposée** (réglages du Modelfile). En contrepartie les réponses
  ne sont pas reproductibles → **évaluer sur plusieurs tirages** (cf. §13).

Tout serveur OpenAI-compatible fonctionne (Ollama, vLLM, LM Studio…). Serveur Flask +
Socket.IO sur le port `5001` (`config.py`, `debug=True`).

---

## 12. Modifications locales de `pageindex/` (fork)

`pageindex/` est une copie de [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex).
Le **paradigme** (arbre par raisonnement, prompts du cookbook pour `tree_search`)
n'est jamais modifié. Ajustements locaux : (1) extraction **PyMuPDF** + suppression
en-têtes/pieds ; (2) texte des nœuds balisé `<page_N>` ; (3) **découpage des pages de
frontière** (anti-contamination) ; (4) **résumé identitaire par PIÈCE**
(`generate_summaries_for_structure`), dans la langue du document ; (5) pages issues
des `<physical_index_X>` ; (6) réparation du sommaire ; (7) timeout LLM 180 s ;
(8) tokenizer avec repli `o200k_base` ; (9) **fusion des nœuds redondants** ;
(10) **aucune température imposée** ; (11) **régime compilation vs document unique**
(`is_compilation`) ; (12) **citations de page dans les fiches** (`(p. N)`) ;
(13) **concurrence bornée des résumés** (`SUMMARY_CONCURRENCY = 3`).

---

## 13. Limites connues

- **Synthèse globale (`overview`) = niveau « fiches »** : structure et thèmes, pas le
  détail circonstancié — levier = richesse des fiches. *(Les questions de détail
  passent en `detail` → texte, voire map-reduce.)* Sous la pression du grounding, le
  modèle tend à **énumérer** les pièces plutôt qu'à les fondre.
- **Sélection tributaire de la fiche** : une pièce est jugée sur sa fiche (§5.3) —
  fiche pauvre → pièce potentiellement ratée.
- **Frontières de pièces posées par le LLM** à l'indexation ; les fichiers composites
  mal bornés peuvent faire « déborder » une pièce sur sa voisine (atténué par les IDs
  de citation autorisés, §9.2 ; pré-segmentation déterministe à l'étude).
- Pages sans couche texte **transcrites par le modèle vision** (sinon page vide).
- Détection de sommaire limitée aux **20 premières pages**.
- Indexation et réponses **non déterministes** (LLM, température Modelfile) → évaluer
  sur **plusieurs tirages**.

---

*Études & évaluation : `ETUDE-SEGMENTATION-PIECES.md` (pré-segmentation déterministe),
`ETUDE-MAP-REDUCE-CIBLE.md` (fiches à chaud), `ETUDE-OPEN-NOTEBOOK.md` (instructions
par recherche, prompts externalisés, IDs autorisés), `DIAGNOSTIC-UEMO.md` (dégradation
du modèle par les enrobages), `ETUDE-RAGFLOW.md` (comparatif). Évaluation :
`FONCTIONNEMENT-PAR-TESTS.md` (les voies par 4 cas réels) et le skill
`.claude/skills/evaluer-reponse-sourcee/` (audit sourcé + chaîne « lancer → évaluer » ;
résultats dans `evaluations/`).*
