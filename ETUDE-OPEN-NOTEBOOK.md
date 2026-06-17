# Étude — Open Notebook : idées pertinentes pour PageIndex_Chat_UI

**Projet étudié** : [lfnovo/open-notebook](https://github.com/lfnovo/open-notebook) (v1.9, MIT),
« alternative open-source, privée et 100 % locale à Google NotebookLM ».
**Méthode** : lecture sur pièces du dépôt cloné (README, docs `2-CORE-CONCEPTS`,
`open_notebook/graphs/{ask,chat}.py`, `domain/transformation.py`, prompts
`ask/{entry,query_process}.jinja`). **Aucune ligne de code applicatif n'a été
modifiée** : ce document est une étude, pas une implémentation.

---

## 1. Ce qu'est Open Notebook (synthèse)

- **Stack** : Python / FastAPI (API REST par ressource) + frontend Next.js/React +
  **SurrealDB** (stockage unifié texte + vecteur + graphe) + **LangGraph** (les
  workflows) + **Esperanto** (abstraction 18+ fournisseurs LLM/embeddings/STT/TTS).
- **Modèle de données à 3 couches** (`notebooks-sources-notes.md`) :
  - **Notebook** = conteneur *isolé* d'un projet (les sources d'un notebook
    n'apparaissent jamais dans un autre — anti-mélange par conception) ;
  - **Source** = matière brute **immuable** (PDF, URL, audio, vidéo, texte) ;
  - **Note / Insight** = sortie *mutable* (manuelle ou IA), **citable**, qui
    devient elle-même cherchable et réutilisable.
- **Trois modes d'interaction** (`chat-vs-transformations.md`) :
  - **Chat** — contenu **complet** des sources sélectionnées envoyé au LLM,
    contexte **manuel**, **conversationnel** (mémoire via `SqliteSaver`). Pas de RAG.
  - **Ask** — **RAG automatique** : la question est **décomposée** en une stratégie
    de recherche, fan-out, une réponse par branche, puis *reduce*. One-shot.
  - **Transformations** — **gabarits réutilisables** appliqués à une source →
    produit une note structurée.
- **Paradigme de retrieval (Ask)** : extraction → **chunking ~500 mots** →
  **embeddings** → recherche **BM25 (texte) ou vectorielle (sémantique)** →
  augmentation + **citations**.
- **Extras** : génération de **podcasts** multi-voix (Episode Profiles), **MCP**,
  **API REST** complète, **contrôle de contexte par source** (3 niveaux), prompts
  **externalisés** en gabarits Jinja.

> Détail marquant : la doc d'Open Notebook emploie spontanément la **métaphore
> juridique** — « *Sources as Evidence — like exhibits in a legal case; once filed,
> they don't change; the ground truth for claims* ; *Notes as case brief* ». C'est
> très exactement notre domaine (procédure pénale, pièces, fidélité au source,
> citations).

---

## 2. Divergence de paradigme — à garder en tête avant toute reprise

| | Open Notebook | PageIndex_Chat_UI |
|---|---|---|
| Retrieval | **chunking + embeddings + recherche vectorielle/BM25** | **raisonnement sur l'arbre** (titres + résumés), `tree_search`, **aucun** embedding/chunk/recherche littérale |
| Citation | référence `[type:id]` (basique, « will improve » d'après leur README) | **citation à la page physique** vérifiable |
| Modèles | 18+ fournisseurs (Esperanto) | **modèle unique local** (gpt-oss-120b-64k), zéro swap |
| Stockage | SurrealDB (texte+vecteur+graphe) | cache d'arbre **sur disque** |

**Conséquence** : certaines briques d'Open Notebook sont **contraires** à nos choix
fondateurs (cf. `CLAUDE.md` principe 1 : recherche littérale *et* vectorielle
écartées ; principe 2 : un seul modèle) et **ne doivent pas** être reprises telles
quelles. D'autres sont **transposables** car indépendantes du moteur de retrieval.
Tout le tri ci-dessous repose sur cette distinction.

---

## 3. Idées à **adopter** (compatibles, à valeur ajoutée)

### 3.1 Niveaux de contexte **par pièce** (Full / Résumé / Exclu)
- **ON** : chaque source porte un niveau — *texte complet* / *résumé seul* / *hors
  contexte*. L'utilisateur décide explicitement ce que voit le modèle
  (`ai-context-rag.md`, « Context as a permission system »).
- **Chez nous** : nous avons **déjà** les deux granularités (fiche vs texte) et la
  sélection de pièces ; il manque le **contrôle explicite par pièce** dans l'IHM.
  Exposer un sélecteur *fiche-seule / texte / exclue* par pièce donnerait un
  contrôle fin coût/pertinence, **renforcerait l'anti-contamination** (principe 4)
  et resterait sous le budget de contexte (65 536). Idée la plus directement
  alignée avec notre architecture.

### 3.2 **Transformations** = gabarits d'extraction définis par l'utilisateur → notes
- **ON** : `Transformation = {name, title, description, prompt, apply_default}`
  appliqué à une source → insight/note ; `apply_default` = exécution automatique à
  l'ingestion (`domain/transformation.py`).
- **Chez nous** : nos **fiches d'identité** sont un gabarit **fixe**. Idée : permettre
  des **gabarits additionnels** (ex. « chronologie », « personnes & rôles »,
  « incohérences internes relevées ») appliqués à une pièce ou au dossier, persistés
  comme notes réutilisables et citables — en **réutilisant notre grounding**
  (fidélité, pas d'inférence, `(p. N)`).
- **Lien avec nos évals** : une transformation « anomalies internes » (certificat
  mal renseigné, profession divergente…) répondrait au reproche récurrent
  « l'app ne *signale* pas les incohérences du dossier » — sans dégrader la fidélité.

### 3.3 **Notes / Insights** comme objets de première classe, citables, réinjectables
- **ON** : une réponse Chat/Ask ou une transformation peut être **sauvegardée en
  note** ; les notes sont cherchables, citables, et constituent un **fil d'audit**.
- **Chez nous** : une synthèse pourrait être épinglée comme « note de synthèse » du
  dossier, réutilisable et citant les pièces — une **mémoire de travail** au-dessus
  des pièces, utile pour les dossiers volumineux travaillés en plusieurs passes.

### 3.4 Décomposition « stratégie + **instructions par branche** » (Ask)
- **ON** : une question → `Strategy {reasoning, searches:[{term, instructions}]}`
  (≤ 5) ; chaque branche reçoit une **consigne d'extraction explicite** (« dis au
  LLM ce que tu veux extraire de CETTE recherche »), fan-out (LangGraph `Send`),
  puis `write_final_answer` (*reduce*). (`graphs/ask.py`, `prompts/ask/*.jinja`.)
- **Chez nous** : nous décomposons déjà par **natures différentes** + map-reduce
  ciblé (`_focused_summary`). L'idée transposable = **attacher une consigne
  d'extraction explicite à chaque pièce/sous-question** du *map* (« ce que tu dois
  extraire de cette pièce au regard de la question »), ce qui affinerait
  `_focused_summary`. **NB** : chez nous la « recherche » reste `tree_search`,
  **pas** une recherche vectorielle.

### 3.5 **Prompts externalisés** en gabarits (Jinja), versionnés
- **ON** : tous les prompts sont des **templates Jinja** séparés du code
  (`prompts/ask`, `/chat`, `/podcast`…), rendus via `ai_prompter`.
- **Chez nous** : nos prompts sont des **chaînes Python inline** (grounding, fiches,
  décomposition). Les externaliser faciliterait l'itération et **surtout
  l'évaluation** (skill `evaluer-reponse-sourcee`) : diff de prompt lisible, A/B
  plus simple. Changement léger, **fort levier** vu notre travail d'éval en cours.

### 3.6 **Citations typées + garde-fous d'ID stricts**
- **ON** : citations `[type:id]` (`source:` / `note:` / `insight:`) avec des
  instructions très fermes — « n'invente pas d'ID, ne change pas le préfixe, utilise
  l'ID **exact** » — et **la liste des IDs autorisés injectée** dans le prompt
  (`prompts/ask/query_process.jinja`).
- **Chez nous** : nous avons déjà `(doc, node, page)` + linkify. À retenir :
  **injecter explicitement la liste des node ids autorisés** dans le prompt de
  rédaction et interdire toute déviation — verrou supplémentaire contre les
  placeholders « source » et les ids inventés.

### 3.7 **API REST** minimale pour la chaîne tests → évaluation
- **ON** : API REST exhaustive (un router par ressource) + MCP — tout est scriptable.
- **Chez nous** : nous pilotons déjà par Socket.IO (`accept_chauvin`, la chaîne
  d'éval). Une **API REST minimale** « poser une question / récupérer réponse +
  trace » fiabiliserait la chaîne *lancer-les-tests → évaluer* qu'on construit
  (séquençage plus simple qu'un client websocket). Optionnel : exposer le corpus en
  **serveur MCP** pour qu'un agent externe interroge le fonds sourcé.

---

## 4. Idées à **éviter** chez nous (contraires au paradigme ou hors besoin)

- **Chunking + embeddings + recherche vectorielle/BM25** — c'est le cœur d'Open
  Notebook, mais **précisément** ce que le paradigme PageIndex a écarté
  (`CLAUDE.md` principe 1). Le retrieval par similarité perd la **structure
  documentaire** et fragilise la **citation à la page**. Ne pas réintroduire.
- **Multi-fournisseurs (Esperanto)** — nous avons délibérément **un seul modèle
  local** (zéro swap, contexte figé). Non pertinent.
- **Podcasts / STT-TTS** — hors domaine (Q-R sourcée juridique). L'idée générique
  « générer un livrable structuré » est déjà couverte par nos synthèses ; le motif
  *Episode Profile* (config de génération réutilisable) pourrait au mieux inspirer
  des **gabarits de synthèse** (cf. §3.2), mais c'est secondaire.
- **SurrealDB** — notre cache d'arbre sur disque suffit au paradigme ; introduire
  une base vectorielle irait contre le choix de **simplicité** (principe 6) et de
  raisonnement-sur-arbre.

---

## 5. Tableau de synthèse

| Idée | Verdict | Effort | Alignement principes |
|---|---|---|---|
| Niveaux de contexte par pièce (Full/Résumé/Exclu) | **Adopter** | moyen | renforce anti-contamination (P4) |
| Transformations utilisateur → notes (dont « anomalies ») | **Adopter** | moyen | répond à un manque d'éval |
| Notes/insights citables réinjectables | Adopter (plus tard) | moyen | mémoire de travail |
| Consigne d'extraction par branche (map) | **Adopter** | léger | affine map-reduce existant |
| Prompts externalisés (Jinja) | **Adopter** | léger | levier pour l'évaluation |
| Liste d'IDs autorisés + garde-fous citation | **Adopter** | léger | fiabilité citations (P3) |
| API REST minimale (chaîne d'éval) | Adopter (opportun) | léger-moyen | sert la chaîne tests→éval |
| Exposition MCP du corpus | À considérer | moyen | intégration externe |
| Chunking + embeddings + recherche vectorielle | **Éviter** | — | contraire P1 |
| Multi-fournisseurs (Esperanto) | **Éviter** | — | contraire P2 (modèle unique) |
| Podcasts / STT-TTS | **Éviter** | — | hors domaine |
| SurrealDB (base vecteur/graphe) | **Éviter** | — | contraire P6 (simplicité) |

---

## 6. Recommandation (priorisation)

**Quick wins à fort levier, alignés sur nos chantiers en cours :**
1. **Prompts externalisés** — facilite l'itération *et* l'évaluation. Léger.
2. **Liste d'IDs autorisés** dans le prompt de rédaction — verrou citation. Léger.
3. **Niveaux de contexte par pièce** dans l'IHM — fort gain UX + anti-contamination.
4. **Transformation « anomalies internes » + notes persistées** — répond
   directement au reproche « ne signale pas les incohérences » remonté par les
   évaluations.

**À ne pas faire** : vectoriser / chunker / introduire une base vectorielle — cela
contredirait le paradigme PageIndex (raisonnement sur l'arbre) et la citation à la
page, qui sont nos différenciateurs.

**En une phrase** : Open Notebook est un **RAG vectoriel généraliste** ; nous sommes
un **moteur de raisonnement sur arbre, sourcé à la page**. Les idées à reprendre
sont celles de son **ergonomie de recherche** (contrôle de contexte, transformations,
notes citables, prompts externalisés, garde-fous de citation) — **pas** celles de
son moteur de retrieval.
