# Architecture — POC Réponses Sourcées (PageIndex Chat UI)

> Application de **questions-réponses documentaires sourcées**, 100 % locale
> (Ollama), construite au-dessus de la bibliothèque [PageIndex](https://github.com/VectifyAI/PageIndex).
> Document de référence sur le fonctionnement interne. Plan :
> 1. Idée & paradigme · 2. **Vocabulaire** (à lire en premier) · 3. Couches,
> fichiers & **prompts externalisés** · 4. **Indexation** (à froid) ·
> 5. **Traitement d'une question** · 6. Citations, **notes** & IHM ·
> 7. Modèles & config · 8. Modifications locales · 9. Limites.

---

## 1. L'idée et le paradigme

### 1.1 En une phrase

PageIndex transforme un PDF en un **arbre** (sa table des matières) où chaque
nœud porte un **résumé**. Pour répondre à une question, un LLM **raisonne sur cet
arbre** (les titres et les résumés) pour localiser les bons passages, les lit,
puis rédige une réponse **citée à la page**. Pas de base vectorielle, pas
d'embeddings.

### 1.2 Similarité ≠ pertinence

Le RAG classique récupère les fragments *sémantiquement proches* de la question —
or le bon contexte n'est pas toujours le plus proche. PageIndex fait autrement :
on construit une **carte** du document (arbre + résumés) et on **navigue dedans
par raisonnement**, comme un greffier qui feuillette un dossier en lisant les
intitulés.

### 1.3 Règle structurante : le retrieval passe **uniquement** par l'arbre

Répondre se fait en **deux étapes** : on **choisit** d'abord où regarder (sur les
résumés), puis on **lit** seulement les passages choisis.

| Brique | Rôle |
|---|---|
| `pageindex/` | Bibliothèque amont : PDF → arbre de nœuds, **chaque nœud portant un titre et un résumé**. Fork local (§8). |
| `tree_search` | **Étape 1 — choisir où regarder.** Reçoit la question + l'arbre réduit à ses **titres et résumés** (`remove_fields(tree, ['text'])` : le *texte intégral des pages* est retiré, les résumés restent) → renvoie `{thinking, node_list}`. C'est **en lisant les résumés** qu'il décide quels nœuds sont pertinents. `PageIndexService.tree_search` (`services/rag_service.py`), prompt du cookbook officiel. |
| Lecture des nœuds | **Étape 2 — lire pour de vrai.** Le **texte** des seuls nœuds retenus à l'étape 1 est alors chargé et fourni au rédacteur. |
| Rédaction ancrée | « réponds uniquement à partir du contexte » + citations `(node_<id>, page N)`. |

**À quoi servent les résumés, alors ?** Ce sont eux — *pas* le texte — que
`tree_search` lit pour **choisir** les nœuds (étape 1). On retire le texte intégral
à cette étape pour deux raisons : (a) un dossier entier ne tiendrait pas dans le
contexte du modèle, et (b) on veut raisonner sur des **synthèses** (« cette pièce
est la note de X au juge Y ») plutôt que sur des pages brutes. Le texte n'est lu
qu'à l'**étape 2**, et seulement pour les nœuds retenus.

**Conséquence — la qualité des résumés EST la qualité du retrieval.** Puisque le
choix (étape 1) se fait sur les résumés, **un résumé pauvre rend une pièce
invisible**. Cas réel fondateur : « résume la note de M. X au juge Y » restait
**introuvable** parce que le résumé de cette note ne mentionnait ni auteur, ni
destinataire, ni nature — le modèle ne pouvait pas la relier à la question. Le
correctif **conforme** n'a pas été d'ajouter une recherche plein-texte, mais
d'**enrichir le résumé** pour qu'il porte cette identité (la « fiche d'identité »,
§2 et §4). Quand une pièce est introuvable, on améliore l'arbre — jamais on ne
contourne le paradigme.

---

## 2. Vocabulaire (lire ceci avant tout le reste)

Trois termes structurent toute l'application. Le schéma ci-dessous les relie.

```
            DOCUMENT (un PDF/.docx importé)
                 │  indexation PageIndex
                 ▼
              ARBRE de NŒUDS  (la table des matières du document)
                 │
   ┌─────────────┴───────────────┐
   ▼                             ▼
 NŒUD de niveau 1 = PIÈCE      NŒUD de niveau 1 = PIÈCE
   │ (= un document logique)     │
   ├─ nœud (section)             ├─ nœud (section)
   └─ nœud (sous-section)        └─ …
```

- **Nœud** : une unité de l'arbre (`node_id` ex. `node_0006`), avec un *titre*, un
  *texte* (les pages du document, balisées `<page_N>…</page_N>`) et une *plage de
  pages*. Les nœuds forment une hiérarchie (sections, sous-sections).
  `N` est la **page physique du PDF** (index extrait par PyMuPDF) : les citations
  `(p. N)` et la visionneuse partagent cette numérotation (le clic ouvre la page N
  du PDF), qui peut différer du **folio imprimé** sur la page. Les PDF n'embarquent
  pas de PageLabels exploitables ; l'IHM l'explicite (« Page N du PDF »).

- **Pièce** = **un nœud de premier niveau** (le nœud de tête **+ tout son
  sous-arbre**) = **un document logique** (une audition, une note, un rapport, un
  chapitre…). C'est **l'unité de travail** de l'app : on sélectionne, résume, lit
  et cite *à la granularité de la pièce*. Détection déterministe
  (`piece_head_nodes`, `pageindex/utils.py`) :

  | Forme de l'arbre | Pièces |
  |---|---|
  | ≥ 2 racines | chaque racine est une pièce |
  | 1 racine contenant des pièces numérotées (« Document/Pièce/Annexe N ») | chaque enfant numéroté est une pièce |
  | sinon | le document entier = 1 pièce |

  Un **fichier** peut donc contenir **une** pièce (un PV isolé) ou **plusieurs**
  (un PDF « dossier » de 5 documents). Deux cas concrets :

  ```
  Cas A — dossier de FICHIERS séparés (Procedure-PN-1 : 25 PDF)
     Audition_LEGRAND.pdf   → 1 arbre → 1 PIÈCE
     Plainte_LEBRUN.pdf     → 1 arbre → 1 PIÈCE
     … (25 fichiers = 25 pièces)

  Cas B — FICHIER composite (Dossier Théo : 1 PDF = 5 documents)
     Dossier_Theo_Blanchet.pdf → 1 arbre →
        ├─ « Document 1 — rapport éducatif »  → PIÈCE
        ├─ « Document 2 — Note d'information » → PIÈCE
        └─ … (5 pièces dans 1 fichier)
  ```

  *Pourquoi cette granularité ?* Pour traiter chaque document logique séparément
  (citer la bonne pièce) et **éviter toute contamination** entre pièces voisines
  d'un même fichier.

- **Fiche d'identité** (= « fiche » = **résumé d'une pièce** : ce sont des
  **synonymes** dans ce document). Pour chaque pièce, `generate_node_summary`
  produit **un seul** résumé, structuré selon un **format fiche d'identité** :

  ```
  Nature        : <type de pièce : lettre, note, audition, ordonnance, rapport…>
  Auteur        : <qui l'a écrite/signée, rôle et service>
  Destinataire  : <à qui elle s'adresse>
  Date et heure : <date de la pièce>
  Personnes     : <chaque personne nommée + son rôle (mis en cause, victime…)>
  Objet         : <une phrase : à quoi sert cette pièce>
  Points saillants : <2 à 4 phrases, faits clés, CHACUN suivi de sa page « (p. N) »>
  ```

  *Exemple* (note de M. CHAUVIN, Dossier Théo) :
  ```
  Nature        : Note d'information
  Auteur        : M. CHAUVIN, éducateur (UEHC de Tulle)
  Destinataire  : M. LEMOINE, juge des enfants (Tribunal pour enfants de Limoges)
  Date et heure : —
  Personnes     : Théo Blanchet (mineur placé) ; Mme Germain (mère) ; …
  Objet         : rendre compte de l'évolution du placement de Théo.
  Points saillants : Placement jugé encourageant mais consommation de cannabis
     quotidienne persistante (p. 6) ; relation fusionnelle et harcelante envers la
     mère (p. 7) ; absentéisme scolaire (p. 3)…
  ```

  La fiche a **deux rôles** : (a) **informer** (vue de survol) et (b) servir de
  **support de sélection** — c'est sur les fiches que `tree_search` raisonne. Les
  `(p. N)` dans les « Points saillants » rendent **citable** toute réponse bâtie
  sur les seules fiches.

- **`node_map`** : table calculée à la préparation (nœud → plage de pages, texte,
  bbox de surlignage). Sert aux citations et à la visionneuse.

### 2.1 Pourquoi des nœuds *sous* la pièce ? (la profondeur = échelle)

Une pièce peut être un **sous-arbre profond** (sections, sous-sections) ou un
**nœud unique**. Cette profondeur sert un seul but : **naviguer dans les longs
documents** sans tout charger.

- **Petite pièce** (un PV de 2 pages, ou tout document ≤ `SMALL_DOC_MAX_PAGES` = 4
  pages → indexé comme **un seul nœud**) : pas de profondeur, on lit la pièce
  entière. La profondeur ne sert à rien ici.
- **Pièce/document volumineux** (ex. Synthèse_2026, 114 p.) : la profondeur permet
  un **second niveau de sélection** — un `tree_search` *interne* à la pièce
  retient les **sections** pertinentes, et on ne lit que celles-là.

```
  niveau 1 (entre pièces) :  tree_search sur les FICHES (résumés)  → quelle PIÈCE ?
  niveau 2 (dans une pièce) : tree_search sur les TITRES des sections → quelles SECTIONS ?
```

**Sur quoi raisonne `tree_search` ?** Toujours sur l'arbre **privé du texte**
(titres + résumés). Mais comme on résume **par pièce** (§4.2), **seul le nœud de
tête d'une pièce porte un résumé** ; ses **sous-nœuds n'ont que leur titre**. Donc
le niveau 1 raisonne sur les **résumés** des pièces, tandis que le niveau 2
raisonne sur les **titres** des sections (+ la fiche de la pièce restée sur le
nœud de tête comme contexte). *Compromis assumé* : la sélection de niveau 2 dépend
de la qualité des **titres** de sections — excellente pour un plan bien titré,
plus faible sinon (le levier futur serait un mini-résumé par section).

À noter : la profondeur ne sert **ni aux fiches** (résumé calculé sur la pièce
entière, §4.2) **ni aux petites pièces**. Elle n'intervient qu'à la **lecture**,
pour les gros documents — voie mono-pièce (§5.2) et drill-down « niveau 2 » de la
voie corpus (§5.4).

---

## 3. Architecture en couches & fichiers

```
┌──────────────────────────────────────────────────────────────────┐
│  IHM (navigateur)            templates/index.html                  │
│  3 pages, visionneuse PDF,   static/js/app.js (vanilla JS)         │
│  pastilles de citation       static/css/app.css                    │
├──────────────────────────────────────────────────────────────────┤
│  Serveur web                 app.py / main.py                      │
│  REST + Socket.IO (chat)     routes/api.py, routes/socket_handlers │
├──────────────────────────────────────────────────────────────────┤
│  Application (LE CŒUR)       services/                             │
│  · agent : voies de réponse  services/agent.py                     │
│  · LLM/VLM, tree_search      services/rag_service.py               │
│  · indexation (ordonnance.)  services/indexing_service.py          │
│  · skills (Markdown)         services/skill_manager.py             │
│  · stockage docs & sessions  models/document.py, models/session.py │
├──────────────────────────────────────────────────────────────────┤
│  Bibliothèque PageIndex      pageindex/  (fork amont)              │
│  PDF → arbre + résumés       page_index.py, utils.py               │
└──────────────────────────────────────────────────────────────────┘
```

```
PageIndex_Chat_UI/
├── main.py / app.py            # entrée Flask + Socket.IO (port 5001)
├── config.py                   # ConfigManager : profils de modèles (config.json, hors git)
├── pageindex/                  # bibliothèque d'indexation (fork)
│   ├── page_index.py           #   page_index_main : PDF → arbre
│   └── utils.py                #   extraction PDF, appels LLM, résumé par pièce
├── services/
│   ├── agent.py                #   DocumentAgent : routing + voies de réponse (§5)
│   ├── rag_service.py          #   PageIndexService (tree_search, LLM/VLM) + RAGService
│   ├── indexing_service.py     #   index_pdf : pilote page_index_main + étapes
│   ├── skill_manager.py        #   skills Markdown injectables dans les prompts
│   ├── prompt_templates.py     #   render_prompt(name, **kw) → gabarits Jinja
│   └── prompts/*.jinja         #   prompts ITÉRÉS/ÉVALUÉS (grounding ×3, map, décompose)
├── models/
│   ├── document.py             #   Document / DocumentStore (arbre, node_map, images, notes, fiches à chaud)
│   └── session.py              #   ChatSession / Message / SessionStore
├── routes/
│   ├── api.py                  #   API REST (documents, sessions, config, skills)
│   └── socket_handlers.py      #   chat en streaming Socket.IO
├── skills/                     # 3 compétences Markdown
├── templates/index.html · static/{js,css}   # SPA
├── uploads/  (gitignored)      # PDF téléversés
└── results/  (gitignored)      # documents/<id>/{structure.json, images, notes.json, focused_fiches.json}, sessions
```

Le retrieval **ne passe plus** par un registre d'outils ni une boucle ReAct
(supprimés) : les voies appellent directement `tree_search` et la lecture des
nœuds.

### 3.1 Prompts externalisés (gabarits Jinja)

Les prompts qu'on **itère et qu'on évalue** vivent dans `services/prompts/*.jinja`,
chargés par `prompt_templates.render_prompt(name, **kw)` — on édite **le gabarit**,
pas une chaîne inline (diff lisible, A/B simple pour le skill d'évaluation) :

| Gabarit | Rôle |
|---|---|
| `grounding_kb.jinja` · `grounding_single.jinja` · `grounding_summary.jinja` | règles d'ancrage des 3 voies : citer `(doc, node, page)`, ne pas inverser de rôle, **ne pas affirmer l'exhaustivité/absence**, **guillemets = verbatim exact** |
| `decompose.jinja` | décomposition + classement d'intention + `instructions` par (sous-)question (§5.5) |
| `focused_summary.jinja` | *map* du map-reduce : fiche à chaud orientée par la question, pages `(p. N)` conservées |

Les builders à flot de contrôle (`_build_answer_prompt`…) restent en Python et
**interpolent** ces gabarits.

---

## 4. Indexation — la phase « à FROID »

Une fois par document, à l'import. Produit l'arbre + les fiches, **persistés**.
On parle de fiches **« à froid »** : calculées une fois, figées, **neutres**
(indépendantes de toute question) — par opposition aux fiches **« à chaud »**
produites à la question (§5.4).

### 4.1 Pipeline (`indexing_service.index_pdf` → `pageindex.page_index_main`)

1. **Upload** (`routes/api.py`) → fichier dans `uploads/`, indexation en **file
   séquentielle** (`_INDEXING_GATE`, un document à la fois). Import de **dossier**
   possible (chaque fichier porte son `Document.folder`). **`.docx`** converti en
   PDF (LibreOffice headless).
2. **Cache de réimportation** : si un `<nom>.pdf.pageindex.json` du dossier source
   (`SOURCE_DATA_DIR`, défaut `../data`) a la même empreinte SHA-256 → arbre
   **restauré sans aucun appel LLM**. Sinon :
3. **Construction de l'arbre** : extraction texte (PyMuPDF + suppression
   en-têtes/pieds répétés, OCR vision en repli), détection du sommaire (20
   premières pages), table « titre → page », **vérification LLM** + réparation,
   hiérarchie, `node_id`, texte balisé `<page_N>`, découpage des pages partagées,
   fusion des nœuds redondants. Échec → **2 tentatives** avant statut erreur
   (bouton « Relancer »).
4. **Résumé par pièce** (`generate_summaries_for_structure`) : voir §4.2.
5. **Préparation** (`rag_service.prepare_document`) : rendu JPEG des pages,
   `node_map`, surlignages (bbox), analyse auto (résumé global + questions
   suggérées). Résultat dans `results/documents/<id>/structure.json`, recopié à
   côté du PDF source (cache).

### 4.2 Un résumé **par pièce** (pas par nœud)

`generate_summaries_for_structure` calcule **une fiche par pièce** (sous-arbre de
niveau 1), sur le **texte concaténé** de tout le sous-arbre, stockée sur le nœud
de tête. Les sous-nœuds gardent leur titre mais n'ont pas de résumé propre.
Bénéfices : beaucoup moins d'appels LLM (4-5 fiches au lieu de 36-43 nœuds sur un
dossier type) et une fiche **complète** (et non le seul préambule de l'en-tête).

**Régime de résumé** (`is_compilation`, détection asymétrique) :

| Cas | Détection | Traitement |
|---|---|---|
| **Compilation** (pièces indépendantes — défaut sûr) | pièces numérotées, ou dates/auteurs divergents | fiches **isolées**, en parallèle (concurrence bornée `SUMMARY_CONCURRENCY = 3` — sinon N gros appels gèlent Ollama). Anti-contamination. |
| **Document unique** (plan cohérent) | pas de pièces numérotées, dates/auteurs non divergents, natures de plan (chapitre/partie…) | fiches **cumulatives** et séquentielles : chaque section reçoit en contexte les fiches des précédentes (continuité). |

Mal détecter une compilation comme document unique contaminerait les fiches : le
défaut penche toujours vers **compilation**.

---

## 5. Traitement d'une question

Événement Socket.IO `agent_chat` → `RAGService.agent_chat_stream` →
`DocumentAgent.run_session` (`services/agent.py`).

### 5.1 Vue d'ensemble : routing + résumés froid/chaud

**Deux moments produisent des résumés** :

- **À FROID** (§4) : la **fiche** générique par pièce, neutre, persistée.
- **À CHAUD** (§5.4) : une **fiche ciblée** par pièce, *orientée par la question*,
  jetable (mise en cache) — produite **seulement si nécessaire**.

`run_session` aiguille chaque question selon ce schéma :

```
question
 ├─ aucun document ............................ → Conversation libre (modèle nu, §5.2)
 └─ documents sélectionnés
     └─ decompose_query (1 appel LLM) :
          • scinde si la question est composite (plusieurs demandes)
          • classe l'INTENTION de chaque (sous-)question :
        ┌────────────────────────────────────────────────────────────┐
        │  "overview" (vue d'ensemble) → Synthèse globale → FICHES (§5.3)
        │  "detail"  (fait précis / comparaison)
        │     ├─ 1 pièce  → Voie mono-pièce : lecture du TEXTE (§5.2)
        │     └─ ≥ 2 pièces → Voie corpus (§5.4) :
        │           tree_search (sélection sur fiches) → pièces retenues
        │            ├─ texte ≤ budget → LECTURE DIRECTE
        │            └─ texte > budget → MAP-REDUCE (fiches à CHAUD)
        └────────────────────────────────────────────────────────────┘
   (questions composites : chaque sous-réponse devient une section ## ; assemblage)
```

L'intention classée par le LLM **prime** sur l'ancienne heuristique de mots-clés
`_is_global_summary` (conservée en repli) — seul le *sens* décide, pas les mots.
Deux distinctions importantes (réglées d'après les tests) :

- **Une pièce désignée vs le dossier.** « Résumer *la note de M. X au juge Y* »
  (pièce identifiée par type / auteur / destinataire / date) = `detail` → on **lit
  le texte** de cette pièce. « Résumer *le dossier* » = `overview` → fiches. Le mot
  « résume » seul ne tranche pas : c'est la **cible** (une pièce ou l'ensemble).
- **Mono-nature sur plusieurs pièces ≠ décomposition.** « Détaille **chaque**
  rapport » est **une seule** demande portant sur N pièces — elle n'est **pas
  décomposée** ; la voie corpus sélectionne elle-même **toutes** les pièces
  pertinentes. (Décomposer ici ferait deviner un nombre de sous-questions au LLM
  et risquerait de n'en couvrir qu'une partie.) La décomposition est réservée aux
  demandes de **natures différentes** (synthèse ET faits ET versions).

**Exemples** (dossier de 25 pièces coché, sauf le 1ᵉʳ) :

| Question | Décision | Source de la réponse |
|---|---|---|
| « Qu'est-ce qu'un OPJ ? » *(aucun doc)* | conversation libre | modèle nu, sans sources |
| « Fais une **synthèse du dossier** » | `overview` → synthèse globale | **fiches** (aucune lecture) |
| « **Résume la note de M. CHAUVIN** au juge » | `detail` (pièce désignée) → corpus, lecture | **texte de la note** (pas sa fiche) |
| « Que dit l'**audition de LEGRAND** ? » | `detail`, peu de pièces → corpus, lecture directe | **texte** de l'audition |
| « **Détaille chaque rapport** » | `detail`, **non décomposé** → corpus retient **toutes** les pièces | **texte** de chaque rapport |
| « **Compare les versions** de tous les mis en cause » | `detail`, volumineux → corpus, map-reduce | **fiches à chaud** par audition, compilées |
| « Synthèse **+** faits reprochés **+** versions » | **décomposée** en 3 (natures ≠) | synthèse → fiches ; faits → texte ; versions → texte/map-reduce. Réponse en 3 sections |

### 5.2 Voie « conversation libre » et voie « mono-pièce »

**Conversation libre** (`_run_free_chat`) — mode kb **sans document** : dialogue
direct avec le modèle, **aucune instruction système, aucun style, aucune
température**. Parité totale avec un chat Ollama brut. Ce principe vient d'un cas
réel (`DIAGNOSTIC-UEMO.md`) où des consignes de style faisaient confabuler le
modèle. Réponses « sans sources » (ni citation ni note de qualité).

**Mono-pièce** (`_run_single_simple`) — une seule pièce, intention `detail`.
Pas de comparaison inter-pièces : on cherche *dans* l'arbre de la pièce.
1. **un** `tree_search` sur l'arbre → ≤ `SIMPLE_MAX_NODES` (10) nœuds ;
2. lecture du texte (budget `SIMPLE_CONTEXT_BUDGET` = 60 000 car., chaque section
   préfixée de son `node_<id>` réel) ;
3. rédaction citée (mode Vision → images des nœuds + VLM) ;
4. auto-évaluation (§5.5).

### 5.3 Voie « synthèse globale » (`_run_global_summary`) — intention `overview`

**Quand** : l'utilisateur veut une **vue d'ensemble** (« résume le dossier »).
**Comment** : on agrège les **fiches de toutes les pièces** (`_build_summary_entries`)
et on rédige une vue transversale **en un seul appel**, **sans `tree_search` ni
lecture**. Les fiches portant les `(p. N)`, la synthèse **reste citée à la page**.
Rapide et scalable. *Limite* : reste au niveau « fiches » (pas le détail
circonstancié — §9).

> **À ne pas confondre avec le résumé *incrémental* de l'indexation (§4.2).** Le
> travail « résumés précédents + pièce courante » a lieu **à froid, une fois**,
> pour *construire* les fiches d'un **document unique** (régime cumulatif). La
> synthèse globale, ici, **n'est pas incrémentale** : elle se contente d'**agréger
> les fiches déjà construites**. Autrement dit, « aucune lecture » = on ne relit
> pas le *texte* ; pour un document unique, la continuité du fil est déjà
> « capitalisée » dans les fiches (fruit de l'incrémental d'indexation).

### 5.4 Voie « corpus » (`_run_corpus_simple`) — intention `detail`, ≥ 2 pièces

Le dossier est vu comme **un seul arbre** dont les enfants sont les pièces.

1. **Sélection** : **un** `tree_search` sur les **fiches de toutes les pièces**
   (budget `CORPUS_SELECT_BUDGET` = 48 000) → pièces retenues (≤
   `CORPUS_MAX_PIECES_READ` = 12). Une pièce composite volumineuse (>
   `CORPUS_PIECE_DRILL_THRESHOLD` = 20 000 car.) est affinée section par section
   (`tree_search` interne — *hiérarchie niveau 2*).
2. **Aiguillage selon le volume du texte retenu** :
   - **≤ 60 000 car.** → **lecture directe** du texte (rapide, défaut) ;
   - **> 60 000 car.** → **MAP-REDUCE ciblé** (§ ci-dessous).
3. **Rédaction** (texte brut **ou** fiches ciblées) avec l'**inventaire complet**
   des fiches en appui (`CORPUS_INVENTORY_BUDGET` = 45 000 — toute pièce reste
   citable même non lue).
4. Auto-évaluation (§5.5).

**Map-reduce ciblé (fiches à CHAUD)** — *pourquoi* : le texte intégral de
beaucoup d'auditions ne tient pas dans un contexte unique. *Comment* : on résume
chaque **pièce** retenue *sous l'angle de la question* (et selon une consigne
d'**`instructions`** émise par `decompose_query` — ce que le *map* doit EXTRAIRE,
§5.5), dans **son propre** appel (`_focused_summary`, **pages `(p. N)` conservées**
→ citations préservées), concurrence bornée (`MAP_CONCURRENCY = 3`). Les fiches à
chaud sont mises en **cache mémoire** (`_focused_cache`, anti-recalcul
intra-session) **et persistées sur disque** (`focused_fiches.json`, §6.1) : elles
**survivent au redémarrage** et s'affichent par pièce dans la Vue Structure. Puis
on rédige sur ces fiches.

```
   fiches à froid (toutes les pièces)
         │  tree_search → sélection
         ▼
   pièces retenues : [Audition LEGRAND, Audition LEPETIT, Plainte LEBRUN, …]
         │  volume ?
         ├─ ≤ 60 000 car → LECTURE DIRECTE : texte des pièces → rédaction citée
         └─ > 60 000 car → MAP-REDUCE :
              MAP (1 appel/PIÈCE, ≤3 en //) :
                 LEGRAND → « nie les faits (p.2), reconnaît la dispute (p.3) »
                 LEPETIT → « accuse LEGRAND (p.1)… »        ← fiches à CHAUD
              REDUCE (1 appel) : confronte → réponse citée (doc, node, page)
```

### 5.5 Garde-fous : auto-évaluation et décomposition

- **Note de qualité** (`_estimate_quality`, **déterministe, sans LLM**) :
  citations présentes, nœuds cités ∈ sources, pages ∈ plages réelles, pénalité
  des citations dégénérées. Affichée « Auto-vérification n/10 ».
- **Réflexion conditionnelle** (`reflect`, LLM) : sautée si la réponse est saine ;
  si score < `REFLECT_ACCEPT_THRESHOLD` (6) → **une** recherche complémentaire
  puis réécriture (jamais de boucle).
- **Vérification à la demande** : bouton « Vérifier la réponse » (juge LLM,
  `POST /sessions/<id>/messages/<i>/verify`, verdict persisté).
- **Décomposition** (`decompose_query` + `_run_decomposed`) : une question
  réunissant des demandes de **natures différentes** (synthèse ET faits ET
  versions) est scindée ; chaque sous-question suit la voie de **son** intention,
  les réponses sont assemblées en **sections `##`** sous un seul cycle. **Pas** de
  boucle ReAct (supprimée) : décomposition + N voies normales + assemblage.
  `decompose_query` émet aussi, par (sous-)question, une **`instructions`** (ce que
  le rédacteur / le *map* doit EXTRAIRE — inspiré du « per-search instructions »
  d'Open Notebook, `ETUDE-OPEN-NOTEBOOK.md`).
- **IDs de citation autorisés** (`_build_allowed_citations`) : la rédaction reçoit
  la **liste explicite des `node_id` mobilisés** et ne peut citer **que ceux-là**,
  verbatim — verrou anti-id-inventé et **anti-contamination**. L'évaluation A/B a
  montré que ce verrou réduit nettement la fuite de contenu entre pièces mal bornées
  d'un fichier composite (`evaluations/`, `RAPPORT_COMPARATIF.md`).
  ⚠️ Une demande **mono-nature portant sur plusieurs pièces** (« détaille chaque
  rapport ») n'est **pas** décomposée — sinon le LLM devine un nombre de
  sous-questions et risque de **sous-couvrir** (cas observé : 2 rapports sur 4).
  La voie corpus, elle, sélectionne toutes les pièces pertinentes.

---

## 6. Citations & visionneuse (IHM)

`static/js/app.js` :
- `linkifyCitations` transforme les citations du modèle (variantes tolérées :
  `(node_0007, page 3)`, `(doc: f.pdf, 1, page 5)`, `(pages 5-6)`…) en
  **pastilles `p. N`** cliquables ;
- clic → `showPagePreviewModal` : images des pages, défilement à la page citée,
  **surlignage du nœud source** (bbox) ; pour une citation « pages seules », le
  nœud propriétaire est déduit du `node_map`.

L'IHM a **3 pages** : Bibliothèque (import, statut, structure, aperçu),
conversation mono-document, questions-réponses KB (sélection de documents/dossiers).
Sessions persistées et **isolées par mode** (`single` / `kb`). La **Vue Structure**
(deux panneaux : arbre des pièces persistant à gauche, lecture du PDF à droite)
affiche, **par pièce**, ses **fiches à chaud** (🔥, map-reduce) et les **notes
utilisateur** (§6.1).

**API REST** (`routes/api.py`) : `documents` (CRUD, upload, retry, status, tree,
node-info, analysis, text-highlights, **`notes`** GET/POST/DELETE,
**`focused-fiches`** GET), `sessions` (CRUD, truncate, messages, verify),
`config/models`, `skills`. **Socket.IO** : entrée `agent_chat`,
`get_history`, `stop_generating` ; sortie `status` / `nodes` / `chunk` /
`agent_step` / `agent_reflect` / `answer_done` / `done` / `error`.

### 6.1 Notes & annotations (persistées, sans toucher l'arbre)

Deux familles de **notes par pièce**, stockées **à part** de l'arbre PageIndex
(qui reste l'index de recherche **intact**), selon **le même motif** (un JSON à
côté de `structure.json`, géré par `DocumentStore`) :

| | Notes **utilisateur** | **Fiches à chaud** (map-reduce) |
|---|---|---|
| Origine | saisies (« Ajouter une note ») | générées par le *map* (§5.4) |
| Fichier | `notes.json` | `focused_fiches.json` |
| Store | `add_note` / `get_notes` / `delete_note` | `save_focused_fiche` / `get_focused_fiches` |
| Forme | `{node_id: [{id, text, ts}]}` | `{head_id: [{query, text, nid, ts}]}` |
| Route | `/documents/<id>/notes` | `/documents/<id>/focused-fiches` |
| Durée | disque — survit au redémarrage | disque — survit au redémarrage |

Les deux sont rendues par pièce dans la **Vue Structure** (`srExtrasHtml`). Les
fiches à chaud sont **dédupliquées par (pièce, question)** ; le cache mémoire
`_focused_cache` ne sert qu'à éviter de **recalculer** un *map* dans la même
session — la **source d'affichage est le disque**.

---

## 7. Modèles & configuration (`config.py` → `config.json`, hors git)

| Profil | Usage | Modèle local |
|---|---|---|
| `text` **et** `light` | structure de l'arbre + résumés (indexation) + rédaction + étapes agent | **gpt-oss-120b-64k** |
| `vision` | réponses sur images de pages, OCR des scans | qwen3.6 |

- **Un seul modèle pour tout → zéro swap** Ollama (`text` et `light` identiques).
- **Gestion du contexte** : l'app **ne passe pas de `num_ctx`** → la fenêtre est
  celle du **Modelfile**. D'où une variante à contexte figé : `gpt-oss-120b-64k`
  = `FROM gpt-oss:120b` + `PARAMETER num_ctx 65536`, dimensionnée sur le pic des
  budgets (~31k tokens, marge ~1,6×), ~76 Go VRAM. **Toute hausse des budgets
  doit rester sous 65536**, sinon Ollama tronque silencieusement (citations
  faussées). Le seuil de bascule map-reduce `SIMPLE_CONTEXT_BUDGET` (défaut 60000)
  est **surchargeable par variable d'environnement** `PAGEINDEX_CTX_BUDGET` — sert à
  **forcer le map-reduce en test** (budget bas) sans modifier le code.
- **Aucune température imposée** (réglages du Modelfile ; `gpt-oss:120b` fixe
  `temperature 1`). Forcer temp 0 dégradait les modèles à raisonnement
  (`DIAGNOSTIC-UEMO.md`) ; en contrepartie les réponses ne sont pas reproductibles
  à l'identique — les garde-fous structurels (note de qualité, vérif des pages)
  prennent le relais.

Tout serveur OpenAI-compatible fonctionne (Ollama, vLLM, LM Studio…).

---

## 8. Modifications locales de `pageindex/` (fork)

`pageindex/` est une copie de [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex).
Le paradigme (arbre par raisonnement, prompts du cookbook) n'est jamais modifié.
Ajustements locaux :

1. extraction **PyMuPDF** + suppression des en-têtes/pieds répétés ;
2. texte des nœuds balisé `<page_N>` (citations à la page) ;
3. découpage des **pages de frontière partagées** (anti-contamination entre pièces) ;
4. **résumé identitaire par PIÈCE** (`generate_summaries_for_structure`), langue du document ;
5. pages issues des balises `<physical_index_X>`, jamais d'un sommaire interne périmé ;
6. contournement de la couverture de `verify_toc` + réparation ;
7. timeout LLM (180 s) ;
8. tokenizer avec repli `o200k_base` ;
9. **fusion des nœuds redondants** avant résumés ;
10. **aucune température imposée** dans les appels de la bibliothèque ;
11. **régime compilation vs document unique** (`is_compilation`) ;
12. **citations de page dans les fiches** (« Points saillants » + `(p. N)`) ;
13. **concurrence bornée des résumés** (`SUMMARY_CONCURRENCY = 3`).

---

## 9. Limites connues

- **Synthèse globale (overview) = niveau « fiches »** : dégage structure et thèmes,
  pas le détail circonstancié de chaque pièce. Levier = richesse des fiches.
  *(Les questions de détail/comparaison passent en `detail` → texte, voire
  map-reduce — §5.4.)* Sous la pression du grounding, le modèle tend à **énumérer**
  les pièces plutôt qu'à les fondre.
- **Sélection tributaire de la fiche** : une pièce est jugée sur sa fiche (résumé
  de tête + titres des sous-sections, `_selection_fiche`/`_piece_fiche`). Fiche
  pauvre → pièce potentiellement ratée.
- **Frontières de pièces posées par le LLM** à l'indexation ; une pré-segmentation
  déterministe est à l'étude (`ETUDE-SEGMENTATION-PIECES.md`).
- Pages sans couche texte **transcrites par le modèle vision** (sinon page vide).
- Détection de sommaire limitée aux 20 premières pages.
- Indexation non déterministe (LLM) ; réponses non reproductibles à l'identique
  (températures Modelfile) → évaluer sur **plusieurs tirages** (`DIAGNOSTIC-UEMO.md`).

---

*Études liées : `ETUDE-SEGMENTATION-PIECES.md` (pré-segmentation déterministe),
`ETUDE-MAP-REDUCE-CIBLE.md` (fiches à chaud, implémenté), `ETUDE-OPEN-NOTEBOOK.md`
(instructions par recherche, prompts externalisés, IDs de citation autorisés),
`DIAGNOSTIC-UEMO.md` (dégradation du modèle par les enrobages), `ETUDE-RAGFLOW.md`
(comparatif). Évaluation : `FONCTIONNEMENT-PAR-TESTS.md` (les voies par 4 cas réels)
et le skill `.claude/skills/evaluer-reponse-sourcee/` (audit sourcé + chaîne
« lancer un test → évaluer » ; résultats dans `evaluations/`).*
