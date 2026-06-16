# Architecture — POC Réponses Sourcées (PageIndex Chat UI)

## 1. L'idée en une phrase

Ce projet est une **application complète de questions-réponses documentaire**
construite *au-dessus* de la bibliothèque open-source
[PageIndex](https://github.com/VectifyAI/PageIndex), qui ne fournit que
l'**indexation** (PDF → arbre de structure avec résumés). Tout ce qui *exploite*
cet arbre pour répondre — l'agent, le serveur, l'IHM — est du code propre au
projet, écrit **dans le paradigme PageIndex** : le retrieval se fait par
**raisonnement d'un LLM sur l'arbre** (titres + résumés), sans vecteurs, sans
embeddings, sans découpage arbitraire.

> **Principe directeur (similarité ≠ pertinence)** : un fragment sémantiquement
> proche n'est pas forcément le bon contexte. Plutôt que d'indexer des vecteurs,
> on construit une table des matières arborescente résumée et on laisse le LLM y
> naviguer comme le ferait un humain.

## 2. Le paradigme : où PageIndex est utilisé

Règle adoptée : **le retrieval passe exclusivement par le raisonnement sur
l'arbre**. Quand une information est introuvable, le correctif est
d'**améliorer l'arbre** (qualité des résumés), jamais de contourner le
paradigme (pas de recherche plein-texte, pas d'embeddings).

| Brique | Rôle |
|---|---|
| `pageindex/` | Bibliothèque amont : PDF → arbre (détection sommaire, vérification, résumés). Fork local (cf. §11). |
| `tree_search` | Recherche par raisonnement : (question + arbre **sans texte**) → JSON `{thinking, node_list}`. Prompt repris du cookbook officiel. C'est `PageIndexService.tree_search` (`services/rag_service.py`). |
| Lecture des nœuds | Le texte des nœuds retenus est chargé puis donné au rédacteur. |
| Rédaction ancrée | « Answer based only on the context » + règles de citation `(node_<id>, page N)`. |

Leçon fondatrice (cas réel) : une question désignant « la note de M. X au juge
Y » restait introuvable car les **résumés ne mentionnaient ni auteur, ni
destinataire, ni type de pièce**. Le correctif conforme a été d'enrichir le
prompt de résumé (fiche d'identité), pas d'ajouter une recherche littérale.

## 3. Les quatre couches

```
┌──────────────────────────────────────────────────────────────────┐
│  IHM (navigateur)              templates/index.html               │
│  3 pages, visionneuse PDF,     static/js/app.js  (vanilla JS)      │
│  pastilles de citation         static/css/app.css                 │
├──────────────────────────────────────────────────────────────────┤
│  Serveur web                   app.py / main.py                   │
│  REST (documents, sessions,    routes/api.py                      │
│  config, skills)               routes/socket_handlers.py          │
│  Socket.IO (streaming du chat)                                    │
├──────────────────────────────────────────────────────────────────┤
│  Application agentique         services/  ← LE CŒUR DU PROJET     │
│  · agent : 4 voies de réponse  services/agent.py                  │
│  · LLM/VLM + indexation        services/rag_service.py            │
│  · ordonnancement indexation   services/indexing_service.py       │
│  · skills (Markdown)           services/skill_manager.py          │
│  · stockage docs & sessions    models/document.py, session.py     │
├──────────────────────────────────────────────────────────────────┤
│  Bibliothèque PageIndex        pageindex/  ← fork amont           │
│  PDF → arbre de sections       pageindex/page_index.py            │
│  (sommaire, vérif, résumés)    pageindex/utils.py                 │
└──────────────────────────────────────────────────────────────────┘
```

## 4. Structure du code

```
PageIndex_Chat_UI/
├── main.py / app.py            # Point d'entrée Flask + Socket.IO (port 5001)
├── config.py                   # ConfigManager : profils de modèles (config.json, hors git)
│
├── pageindex/                  # Bibliothèque d'indexation (fork amont)
│   ├── page_index.py           #   page_index_main : PDF → arbre
│   └── utils.py                #   extraction PDF, appels LLM, résumés par pièce
│
├── services/
│   ├── agent.py                #   DocumentAgent : 4 voies de réponse (cf. §6)
│   ├── rag_service.py          #   PageIndexService (LLM/VLM, tree_search) + RAGService
│   ├── indexing_service.py     #   index_pdf : pilote page_index_main + stages
│   └── skill_manager.py        #   skills Markdown injectables dans les prompts
│
├── models/
│   ├── document.py             #   Document / DocumentStore (arbres, node_map, images)
│   └── session.py              #   ChatSession / Message / SessionStore
│
├── routes/
│   ├── api.py                  #   API REST (documents, sessions, config, skills)
│   └── socket_handlers.py      #   chat en streaming Socket.IO
│
├── skills/                     # 3 compétences Markdown (extraction, comparaison, tableaux)
├── templates/index.html        # SPA
├── static/js/app.js            # Front (vanilla JS) ; static/css/app.css
│
├── uploads/                    # PDF téléversés (gitignored)
└── results/                    # Index + sessions (gitignored)
    ├── documents/<id>/         #   structure.json, images de pages, analyse
    └── _sessions/ , _index/    #   sessions isolées par mode
```

Le retrieval ne passe **plus** par un registre d'outils ni une boucle ReAct
(supprimés) : les voies appellent directement `PageIndexService.tree_search` et
la lecture des nœuds.

## 5. Cycle de vie d'un document (indexation — 100 % PageIndex)

1. **Upload** (`routes/api.py:upload_document`) → fichier dans `uploads/`,
   indexation lancée en **file séquentielle** (`_INDEXING_GATE`). Import de
   **dossier** possible (chaque fichier porte son `Document.folder`). Les
   **`.docx`** sont convertis en PDF par LibreOffice headless.
2. **Cache de réimportation** : l'empreinte SHA-256 du PDF est comparée aux
   `<nom>.pdf.pageindex.json` du répertoire source (`SOURCE_DATA_DIR`, défaut
   `../data`). Correspondance → arbre restauré, **aucun appel LLM**. Sinon :
3. **`indexing_service.index_pdf`** appelle **`pageindex.page_index_main`** :
   extraction du texte (PyMuPDF + suppression des en-têtes/pieds répétés, OCR
   vision en repli), détection du sommaire (20 premières pages), table
   « titre → page physique », **vérification LLM** + réparation,
   hiérarchisation, identifiants de nœuds, texte balisé `<page_N>…</page_N>`,
   découpage des pages partagées, fusion des nœuds au texte identique, puis
   **résumé par pièce**. Échec → **deux tentatives** avant le statut erreur ;
   une pièce en erreur se relance d'un clic (`POST /documents/<id>/retry`).
4. Résultat dans `results/documents/<id>/structure.json`, copié à côté du PDF
   source (`.pageindex.json`) pour les réimportations futures.
5. **`rag_service.prepare_document`** : rendu JPEG des pages (visionneuse),
   `node_map` (nœud → plage de pages), surlignages (bbox PyMuPDF), analyse auto
   (résumé global + questions suggérées).

### Les fiches de pièces sont l'index de recherche

L'unité de résumé est la **pièce** = un sous-arbre de premier niveau
(`piece_head_nodes`), pas le nœud. `generate_summaries_for_structure`
(`pageindex/utils.py`) produit **un résumé par pièce**, construit sur le texte
concaténé de tout son sous-arbre, stocké sur son nœud de tête. Le prompt
(`generate_node_summary`) impose une **fiche d'identité** — nature
(lettre, note, rapport…), auteur, destinataire, date — puis des « Points
saillants » qui **citent la page de chaque fait `(p. N)`** (depuis les
`<page_N>`). Conséquences : retrouver une pièce désignée comme un humain le
ferait, **et** une synthèse globale bâtie sur les seules fiches citable à la
page.

**Régime de résumé** (`is_compilation`, détection asymétrique) : un dossier de
**pièces indépendantes** (défaut sûr, anti-contamination) est résumé pièce par
pièce **isolément** et en **concurrence bornée** (`SUMMARY_CONCURRENCY = 3` —
au-delà, N gros appels simultanés gèlent Ollama) ; un **document unique** (plan
cohérent : pas de pièces numérotées, dates/auteurs non divergents) est résumé de
façon **cumulative et séquentielle**, chaque section recevant en contexte les
fiches des précédentes.

Ces fiches sont dites **« à froid »** : produites une fois, figées, **neutres**
(indépendantes de toute question). Au moment d'une question, le système peut
aussi produire des fiches **« à chaud »**, *orientées par la requête* (map-reduce,
cf. §6.0 et §6.3) — c'est la distinction structurante du traitement des questions.

## 6. Cycle de vie d'une question

`services/agent.py`, événement Socket.IO `agent_chat` → `RAGService.agent_chat_stream`
→ `DocumentAgent.run_session`. **Quatre voies**, choisies par `run_session` :

**Unité = pièce** (`USE_PIECE_UNIT`) : la voie dépend du nombre de **pièces**,
pas de fichiers. `_extract_pieces` découpe chaque arbre en pièces (`_piece_heads`),
chacune gardant son **vrai `doc_id`** (citations `doc::node` exactes). Un fichier
composite (plusieurs documents dans un PDF/.docx) bascule donc sur la voie corpus.

**Décomposition & aiguillage** : avant de router, `run_session` appelle
`decompose_query` — **un seul** appel LLM qui (a) scinde la question en
sous-questions si elle regroupe plusieurs demandes distinctes, et (b) classe
l'**intention** de chaque (sous-)question : `overview` (synthèse / vue d'ensemble
→ fiches) ou `detail` (fait précis, comparaison de versions → **lecture du
texte**). Cette intention **prime** sur l'heuristique `_is_global_summary` (qui
ne sert plus que de repli). Si la question est composite, `_run_decomposed`
traite chaque sous-question par la voie de son intention et **assemble les
réponses en sections** sous un seul cycle. Ce n'est **pas** une boucle ReAct
(supprimée) : juste une décomposition + N voies normales + assemblage.

### 6.0 Vue d'ensemble : routing, et résumés « à froid » vs « à chaud »

**Deux moments produisent des résumés** — c'est la clé pour comprendre le système :

- **À FROID — à l'indexation** (une fois par document, cf. §5) :
  `generate_summaries_for_structure` crée **une fiche générique par pièce**,
  **neutre** (indépendante de toute question) et **persistée**. Elle a un *double
  rôle* : (a) **informer** (vue de survol) et (b) servir de support de
  **sélection** (`tree_search` raisonne sur ces fiches).
- **À CHAUD — au moment de la question** (`_focused_summary`, map-reduce) :
  **une fiche spécifique par pièce**, **orientée par la question** et
  **jetable** (gardée en cache pour la session). Elle n'est produite **que si
  c'est nécessaire** (voir l'aiguillage ci-dessous), et **conserve les pages
  `(p. N)`** pour rester citable.

**Décomposition.** Une question peut regrouper plusieurs demandes ; `run_session`
appelle d'abord `decompose_query` (1 appel LLM) qui la **scinde** en
sous-questions autonomes *si* nécessaire, et **classe l'intention** de chacune.
Chaque sous-question suit ensuite son propre chemin ; les réponses sont
assemblées en sections (une réponse, plusieurs `##`).

**Le routing décide du chemin de chaque (sous-)question :**

```
question
 ├─ aucun document sélectionné ............... → Conversation libre (modèle nu, §6.1)
 └─ documents sélectionnés
     └─ decompose_query : composite ? ......... → scinde en sous-questions + intention
         pour chaque (sous-)question, selon l'INTENTION classée :
          ├─ "overview" (vue d'ensemble) ...... → Synthèse globale  → fiches À FROID (§6.4)
          └─ "detail" (fait précis / versions)
              ├─ 1 pièce ..................... → Voie mono-pièce : lecture du TEXTE (§6.2)
              └─ ≥ 2 pièces .................. → Voie corpus (§6.3) :
                   tree_search (sélection sur fiches à froid) → pièces retenues
                    ├─ texte ≤ budget ........ → LECTURE DIRECTE du texte
                    └─ texte > budget ........ → MAP-REDUCE → fiches À CHAUD
```

L'intention classée **prime** sur l'ancienne heuristique de mots-clés
`_is_global_summary` (conservée comme repli si l'appel LLM échoue).

**Exemples** (dossier pénal de 25 pièces coché, sauf le 1ᵉʳ) :

| Question | Décision | Source de la réponse |
|---|---|---|
| « Qu'est-ce qu'un OPJ ? » *(aucun doc)* | conversation libre | modèle nu, sans sources |
| « Fais une **synthèse** du dossier » | `overview` → synthèse globale | **fiches à froid** (pas de lecture) |
| « Que dit l'**audition de LEGRAND** ? » | `detail`, peu de pièces → corpus, lecture directe | **texte** de l'audition |
| « **Compare les versions** de tous les mis en cause » | `detail`, auditions volumineuses > budget → corpus, map-reduce | **fiches à chaud** (une par audition, orientée « versions », pages conservées) puis compilées |
| « Synthèse du dossier **+** résumé des faits **+** versions des personnes » | **décomposée** en 3 sous-questions | facette synthèse → fiches à froid ; faits → texte ; versions → texte ou map-reduce. Réponse en 3 sections |

Ainsi le travail coûteux (lecture, fiches à chaud) n'est fait **que** là où la
question l'exige ; une demande de survol reste rapide sur les fiches à froid.

### 6.1 Conversation libre (`_run_free_chat`) — le modèle NU

Mode kb **sans document** : dialogue direct avec le modèle. **Aucune instruction
système, aucun style, aucune température** : parité totale avec un chat Ollama
direct. Ce principe vient d'un cas réel (`DIAGNOSTIC-UEMO.md`) où des consignes de
style anodines faisaient confabuler le modèle. Réponses sans citations ni note de
qualité (signalé « sans sources » dans l'IHM).

### 6.2 Voie mono-pièce (`_run_single_simple`) — pipeline canonique du cookbook

1. **Un** `tree_search` sur l'arbre de la pièce ;
2. lecture des nœuds retenus (≤ `SIMPLE_MAX_NODES`=10, budget
   `SIMPLE_CONTEXT_BUDGET`=60 000 car., chaque section préfixée de `node_<id>`) ;
3. rédaction (`_build_simple_answer_prompt`) ; mode Vision → images des nœuds + VLM ;
4. auto-évaluation conditionnelle (cf. §6.5).

### 6.3 Voie corpus (`_run_corpus_simple`) — le dossier est un arbre

Mode kb, ≥ 2 pièces, intention `detail` :
1. **Un** `tree_search` sur les **fiches de toutes les pièces** (`CORPUS_SELECT_BUDGET`)
   → pièces retenues (≤ `CORPUS_MAX_PIECES_READ`=12) ; une pièce composite
   volumineuse (> `CORPUS_PIECE_DRILL_THRESHOLD`=20 000 car.) est sélectionnée
   section par section (`tree_search` interne — *hiérarchie niveau 2*) ;
2. **Aiguillage lecture directe vs map-reduce ciblé**, selon le volume du texte
   retenu :
   - **tient** dans `SIMPLE_CONTEXT_BUDGET`=60 000 car. → **lecture directe** du
     texte intégral (rapide, défaut) ;
   - **déborde** → **map-reduce ciblé** : chaque PIÈCE retenue (sous-arbre de
     niveau 1, même granularité que les fiches génériques) est résumée *sous
     l'angle de la question* (`_focused_summary` — **pages `(p. N)` conservées**,
     concurrence bornée `MAP_CONCURRENCY`=3, fiches mises en **cache**
     `_focused_cache`). La couverture n'est plus plafonnée par un contexte
     unique ; les citations restent à la page (cf. §6.5) ;
3. rédaction (texte brut **ou** synthèses ciblées) avec l'**inventaire complet**
   des fiches en appui (`CORPUS_INVENTORY_BUDGET`=45 000 car. — toute pièce reste
   citable même non lue) ;
4. auto-évaluation conditionnelle.

> **Aiguillage du map-reduce, en clair** : il n'est invoqué que (a) pour une
> intention `detail` (les `overview` partent sur les fiches via la synthèse
> globale) **et** (b) si le texte retenu déborde le budget de lecture directe.
> Sinon, lecture directe.

### 6.4 Synthèse globale (`_run_global_summary`)

Déclenchée par `_is_global_summary` (« synthèse du dossier », « vue
d'ensemble »…). Court-circuite la recherche et rédige une **vue transversale**
directement sur les fiches de toutes les pièces (le « map » par pièce est amorti
à l'indexation), avec citations au niveau pièce (le `(p. N)` des fiches voyage
dans la synthèse).

### 6.5 Auto-évaluation partagée

- **Note de qualité calculée** (`_estimate_quality`, déterministe, sans LLM) :
  citations présentes, nœuds cités ∈ sources, pages ∈ plages des nœuds, pénalité
  des citations dégénérées (`source`, `【】`). Affichée « Auto-vérification n/10 ».
- **Réflexion conditionnelle** (`reflect`, LLM) : sautée si la réponse est saine.
  Si score < `REFLECT_ACCEPT_THRESHOLD`=6 → **une** recherche complémentaire puis
  réécriture (pas de boucle).
- **Vérification à la demande** : bouton « Vérifier la réponse » (juge LLM,
  `POST /sessions/<id>/messages/<i>/verify`, verdict persisté).

### 6.6 Les méthodes de `DocumentAgent`

| Groupe | Méthodes |
|---|---|
| Contexte | `_build_tool_context`, `_ensure_doc_loaded`, `_build_docs_overview`, `_single_doc_tree_summary`, `_build_history_context` |
| Pièces | `_piece_heads`, `_subtree_nodes`, `_extract_pieces`, `_piece_fiche`, `_selection_fiche`, `_build_corpus_inventory` |
| Décomposition | `decompose_query` (scinde + classe l'intention), `_run_decomposed` (assemble en sections), `_relay_subquery` (relaie une sous-voie sans dupliquer le cycle) |
| Voies | `run_session`, `_run_free_chat`, `_run_single_simple`, `_run_corpus_simple`, `_run_global_summary` |
| Map-reduce ciblé | `_focused_summary` (fiche à chaud d'une pièce, pages conservées), cache `_focused_cache` |
| Rédaction | `_build_simple_answer_prompt`, `_build_answer_prompt`, `_build_vision_answer_prompt`, `_collect_images_for_refs` |
| Évaluation | `_estimate_quality`, `reflect`, `_is_global_summary` (repli d'aiguillage), `_build_summary_entries` |
| Analyse | `analyze_document` (résumé + questions suggérées après indexation) |
| Divers | `_step_marker` (télémétrie `[AGENT_STEP]`), `_extract_json_str` (repli JSON) |

## 7. API REST (`routes/api.py`)

| Endpoint | Méthode | Rôle |
|---|---|---|
| `/documents` | GET | liste des documents |
| `/documents/upload` | POST | upload (PDF/DOCX, dossier) |
| `/documents/<id>` | GET / DELETE | détail / suppression |
| `/documents/<id>/retry` | POST | relancer une indexation en erreur |
| `/documents/<id>/status` | GET | polling de l'indexation |
| `/documents/<id>/tree` | GET | arbre de structure |
| `/documents/<id>/nodes/<nid>` | PUT | éditer titre/résumé d'un nœud |
| `/documents/<id>/node-info` | GET | node_map (nœud → pages) |
| `/documents/<id>/analysis` | GET | analyse auto |
| `/documents/<id>/text-highlights` | GET | surlignages (bbox) |
| `/sessions` | GET / POST | liste / création |
| `/sessions/<id>` | GET / PUT / DELETE | détail / renommage / suppression |
| `/sessions/<id>/truncate` | POST | tronquer (régénération, édition) |
| `/sessions/<id>/messages/<i>` | PUT | éditer un message |
| `/sessions/<id>/messages/<i>/verify` | POST | juge LLM à la demande |
| `/config/models[/...]` | GET / PUT | configuration des profils de modèles |
| `/skills[/...]` | GET/POST/PUT/DELETE | gestion des skills |

## 8. Streaming Socket.IO (`routes/socket_handlers.py`)

Entrée (frontend → backend) : `agent_chat` (poser une question), `get_history`,
`stop_generating`, `connect`/`disconnect`.

Le flux de réponse est une **suite de marqueurs** texte (`[SEARCHING]`,
`[NODES]…`, `[ANSWER_DONE]`, `[AGENT_STEP]…`, `[AGENT_REFLECT]…`, `[Error…]`…)
que `_process_chunk` traduit en événements (sortie backend → frontend) :
`status`, `nodes`, `chunk`, `thinking_chunk`, `answer_done`, `agent_step`,
`agent_reflect`, `done` / `stopped` / `error`, `history`. Le bouton Stop annule
la tâche immédiatement (un watcher poll le flag d'annulation).

## 9. Modèles de données

- **`Document` / `DocumentStore`** (`models/document.py`) : métadonnées + statut
  d'indexation (`stage`, `stage_message`), caches en mémoire de l'arbre, du
  `node_map` et des images de pages. Les sessions `single` sont rattachées à un
  document (supprimer le doc nettoie ses sessions).
- **`ChatSession` / `Message` / `SessionStore`** (`models/session.py`) : sessions
  isolées par **mode** (`single` / `kb`), persistées sous `results/_sessions/`.
  Une session `kb` porte une **liste** de `doc_ids`.

## 10. Frontend (`static/js/app.js`)

SPA en vanilla JS, **3 pages** : Bibliothèque (import, statut, structure,
aperçu), conversation mono-document, questions-réponses KB (sélection de
documents/dossiers). Communication via `fetch` (REST) + Socket.IO (streaming).

- `linkifyCitations` transforme les citations du modèle (variantes tolérées :
  `(node_0007, page 3)`, `(doc: f.pdf, 1, page 5)`, `(pages 5-6)`…) en
  **pastilles `p. N`** cliquables ;
- clic → visionneuse (`showPagePreviewModal`) : images des pages, défilement à la
  page citée, surlignage du nœud source (bbox) ; pour une citation « pages
  seules », le nœud propriétaire est déduit du `node_map`.

## 11. Configuration des modèles (`config.py` → `config.json`, hors git)

| Profil | Usage | Modèle local |
|---|---|---|
| `text` **et** `light` | structure de l'arbre + résumés de pièces + rédaction + toutes les étapes internes | **gpt-oss-120b-64k** |
| `vision` | réponses sur images de pages, OCR des scans | qwen3.6 |

**Un seul modèle pour tout → zéro swap** Ollama (`text` et `light` pointent sur
le même modèle ; seul `vision`, rarement appelé, reste distinct).

**Gestion du contexte** : l'application **ne passe aucun `num_ctx`** dans ses
appels (`rag_service`) → la fenêtre effective est celle du **Modelfile**. Le
contexte est donc **figé dans le modèle** : `gpt-oss-120b-64k` =
`FROM gpt-oss:120b` + `PARAMETER num_ctx 65536`, dimensionné sur le pic réel des
budgets (`CORPUS_INVENTORY_BUDGET` 45 000 + `SIMPLE_CONTEXT_BUDGET` 60 000 car. +
instructions ≈ 31 000 tokens, marge ~1,6×), pour ~76 Go VRAM. **Règle :** toute
hausse de ces budgets doit rester sous 65536, sinon Ollama tronque silencieusement
le contexte (citations faussées).

**Aucune température imposée** : chaque modèle tourne avec les réglages de son
Modelfile (ex. `gpt-oss:120b` fixe `temperature 1`). Forcer temp 0 dégradait les
modèles à raisonnement (`DIAGNOSTIC-UEMO.md`) ; en contrepartie les réponses ne
sont pas reproductibles à l'identique — les garde-fous structurels (note de
qualité, vérification des pages) prennent le relais.

Tout serveur OpenAI-compatible fonctionne (Ollama, vLLM, LM Studio…) : `base_url`
personnalisée, clé factice injectée si absente.

## 12. Modifications locales apportées à `pageindex/`

Le dossier `pageindex/` est une copie de l'amont
[VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) — un fork de fait.
Le paradigme (arbre par raisonnement, prompts canoniques) n'est jamais modifié.
Ajustements locaux (« quality in, quality out ») :

1. **extraction PyMuPDF par défaut** (PyPDF2 coupait les mots) + **suppression
   des en-têtes/pieds répétés** (`strip_repeated_page_furniture`) ;
2. texte des nœuds balisé `<page_N>` (citations à la page près) ;
3. **découpage des pages de frontière partagées** (`split_shared_boundary_pages`) :
   fin des contaminations entre pièces voisines ;
4. résumés **identitaires par PIÈCE** (`generate_summaries_for_structure`,
   `piece_head_nodes`) dans la langue du document, titres jamais traduits ;
5. garde-fou : les pages viennent des balises `<physical_index_X>` où le contenu
   commence, jamais d'un sommaire interne (pagination périmée après Word→PDF) ;
6. contournement de l'heuristique de couverture de `verify_toc` + réparation ;
7. timeout explicite (180 s) sur les clients LLM ;
8. tokenizer avec repli `o200k_base` pour les modèles non-OpenAI ;
9. **fusion des nœuds au texte identique au parent** (`merge_redundant_children`) ;
10. **aucune température imposée** dans les appels LLM de la bibliothèque ;
11. **régime de résumé compilation vs document unique** (`is_compilation`) ;
12. **citations de page dans les fiches** (« Points saillants » + `(p. N)`) ;
13. **concurrence bornée des résumés** (`SUMMARY_CONCURRENCY = 3`) — sinon N gros
    appels simultanés gèlent Ollama.

## 13. Style des réponses

`STYLE_INSTRUCTION` (prompts de rédaction uniquement) : prose continue, pas de
puces/tableaux/titres/gras **sauf demande explicite ou trame fournie** ;
citations `(node_<id>, page N)` et guillemets de citation obligatoires ; ordre
chronologique respecté. Le raisonnement interne (réflexion) garde ses formats
structurés.

## 14. Limites connues

- **Synthèse globale (overview) = niveau « fiches »** : une vue d'ensemble dégage
  structure et thèmes mais pas le détail fin de chaque pièce. Le levier de qualité
  est la richesse des fiches — citables à la page. Sous la pression du grounding,
  le modèle tend encore à **énumérer** les pièces plutôt qu'à les fondre. *(Les
  questions de détail / comparaison passent, elles, en intention `detail` →
  lecture du texte, voire map-reduce ciblé à l'échelle, cf. §6.3.)*
- **Sélection hiérarchique tributaire de la fiche** : une pièce composite est
  jugée sur sa fiche (résumé de tête + titres des sous-sections via
  `_selection_fiche`/`_piece_fiche`). Si la fiche ne reflète pas le contenu
  profond, la pièce peut être ratée.
- **Découpage en pièces dépend de l'arbre LLM** : les frontières de pièces sont
  posées par l'indexation LLM. Une pré-segmentation déterministe est à l'étude
  (`ETUDE-SEGMENTATION-PIECES.md`).
- Les pages sans couche texte sont **transcrites par le modèle vision** ; sans
  modèle vision, page vide.
- La détection de sommaire ne balaie que les 20 premières pages.
- L'indexation est non déterministe (LLM) : deux imports peuvent produire des
  arbres légèrement différents.
- Les réponses ne sont pas reproductibles à l'identique : les évaluations
  factuelles se font sur **plusieurs tirages** (cf. `DIAGNOSTIC-UEMO.md`).
