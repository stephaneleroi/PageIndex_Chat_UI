# Architecture de PageIndex Chat UI

## L'idée en une phrase

Ce projet n'est **pas** seulement une IHM : c'est une **application complète de
questions-réponses documentaire** construite *au-dessus* de la bibliothèque
open-source [PageIndex](https://github.com/VectifyAI/PageIndex), qui elle ne
fournit que l'**indexation** (PDF → arbre de structure). Tout ce qui *exploite*
cet arbre pour répondre aux questions — l'agent, ses outils, le serveur, l'IHM —
est du code propre au projet, écrit **dans le paradigme PageIndex** (retrieval
par raisonnement, sans vecteurs, sans découpage arbitraire).

## Où PageIndex est utilisé — et où il ne l'est pas

C'est la question structurante du projet. Règle adoptée : **le retrieval passe
exclusivement par le raisonnement sur l'arbre** (titres + résumés de nœuds),
conformément au cookbook officiel. Quand une information est introuvable, le
correctif est d'**améliorer l'arbre** (qualité des résumés), jamais de
contourner le paradigme.

### ✔ Paradigme PageIndex (actif)

| Composant | Conformité |
|---|---|
| `pageindex/` (indexation PDF → arbre) | Bibliothèque amont, quasi intacte (cf. « Modifications locales ») |
| `tree_search` | Prompt **identique mot pour mot** à `cookbook/pageindex_RAG_simple.ipynb` (question + arbre sans texte → JSON `{thinking, node_list}`) |
| `cross_search` | `tree_search` exécuté en parallèle sur plusieurs documents — raisonnement pur |
| `read_node` | Lecture du texte des nœuds choisis (équivalent de `get_page_content` de `examples/agentic_vectorless_rag_demo.py`, à la granularité du nœud) |
| `list_documents` / `read_toc` | Métadonnées et structure (équivalents de `get_document` / `get_document_structure` de l'exemple officiel) |
| `view_pages` | RAG visuel sur les images de pages (`cookbook/vision_RAG_pageindex.ipynb`) |
| Rédaction ancrée | « Answer based only on the context » + règles de citation |

### ✘ Hors paradigme (code conservé, mais DÉSACTIVÉ)

| Composant | Pourquoi désactivé | Où |
|---|---|---|
| `keyword_search` (recherche littérale dans le texte) | Contourne le raisonnement sur l'arbre | non enregistré dans `DocumentAgent._register_tools` |
| `summarize_nodes` (résumé intermédiaire par outil) | Étape absente du flux canonique (arbre → lecture → réponse) ; dégrade la traçabilité des pages | non enregistré dans `_register_tools` |
| Repli littéral de `cross_search` | Idem keyword_search | drapeau `LITERAL_FALLBACK = False` dans `services/tools/cross_search.py` |

Leçon à l'origine de cette règle (cas réel) : une question désignant « la note
écrite par M. X au juge Y » restait introuvable par raisonnement car les
**résumés de nœuds ne mentionnaient ni auteur, ni destinataire, ni type de
pièce**. Le correctif conforme n'a pas été la recherche littérale mais
l'enrichissement du prompt de résumé (voir ci-dessous) : depuis, le
raisonnement pur trouve la pièce.

## Les quatre couches

```
┌──────────────────────────────────────────────────────────────────┐
│  IHM (navigateur)              templates/index.html              │
│  pages Documents / Q-R,        static/js/app.js  (vanilla JS)    │
│  visionneuse PDF, citations    static/css/app.css                │
├──────────────────────────────────────────────────────────────────┤
│  Serveur web                   app.py, main.py                   │
│  REST : documents, sessions,   routes/api.py                     │
│  config, skills                routes/socket_handlers.py         │
│  Socket.IO : streaming du chat                                   │
├──────────────────────────────────────────────────────────────────┤
│  Application agentique         services/  ← LE CŒUR DU PROJET    │
│  · agent ReAct (planifie,      services/agent.py                 │
│    appelle des outils, rédige, services/tools/*.py               │
│    s'auto-évalue, réessaie)    services/rag_service.py           │
│  · stockage docs & sessions    services/indexing_service.py      │
│                                models/document.py, session.py    │
├──────────────────────────────────────────────────────────────────┤
│  Bibliothèque PageIndex        pageindex/  ← code (quasi) amont  │
│  PDF → arbre de sections       pageindex/page_index.py           │
│  (détection sommaire,          pageindex/utils.py                │
│  vérification, résumés)                                          │
└──────────────────────────────────────────────────────────────────┘
```

## Cycle de vie d'un document (indexation — 100 % PageIndex)

1. **Upload** (`routes/api.py`) → fichier dans `uploads/`, fil d'indexation lancé.
2. **`services/indexing_service.py`** appelle **`pageindex.page_index_main`**
   (la bibliothèque) : extraction du texte (PyPDF2), détection du sommaire
   (20 premières pages), construction de la table « titre → page physique »
   (3 stratégies selon présence/qualité du sommaire), **vérification LLM**
   de chaque entrée + réparation, hiérarchisation, identifiants de nœuds,
   texte balisé `<page_N>…</page_N>`, résumés par nœud.
3. Résultat figé dans `results/documents/<id>/structure.json`.
4. **`rag_service.prepare_document`** : rendu JPEG des pages (visionneuse),
   `node_map` (nœud → plage de pages), surlignages (bbox par nœud, PyMuPDF),
   analyse automatique (résumé global + questions suggérées).

**Les résumés de nœuds sont l'index de recherche** : le prompt
(`generate_node_summary`, `pageindex/utils.py`) exige d'ouvrir chaque résumé
par l'**identité** de la partie — nature de la pièce (lettre, note, ordonnance,
rapport…), auteur/signataire, destinataire, date — avant les points couverts,
en citant les noms propres. C'est ce qui permet au raisonnement de retrouver
une pièce désignée comme un humain le ferait (« la note de M. X au juge Y »).

Tous ces appels LLM utilisent le profil **« rapide »** (configurable, onglet
« Modèle rapide » des réglages). Si une indexation est interrompue par un
redémarrage du serveur, le document est récupéré en statut « erreur »
explicite (boutons Réessayer / Supprimer).

## Cycle de vie d'une question (agent — paradigme PageIndex)

`services/agent.py`, événement Socket.IO `agent_chat` :

1. **Décomposition** (profil rapide) : sous-questions si nécessaire.
2. **Boucle ReAct** (≤ 5 étapes/sous-question, profil rapide) : le
   planificateur choisit parmi les outils actifs (`tree_search`,
   `cross_search`, `read_node`, `list_documents`, `read_toc`, `view_pages`).
   Le flux nominal est celui du cookbook : *raisonner sur l'arbre → lire les
   nœuds retenus*. Consigne de persistance : ne jamais conclure à l'absence
   après une seule recherche vide — reformuler la requête, lire les sections
   plausibles. Les appels d'outils **natifs** (`tool_calls`) émis par certains
   modèles sont reconvertis au format du planificateur (`rag_service.call_llm`).
3. **Rédaction** (profil **texte**, le « gros » modèle) : prompt avec la trace
   de raisonnement + le texte source balisé (plafond 60 000 caractères) +
   règles de citation `(node_<id>, page N)` ; enquête déclarée close (le
   rédacteur ne doit jamais « continuer » la boucle d'outils).
4. **Auto-évaluation** (« réflexion », profil rapide) — c'est l'encart
   « Auto-vérification n/10 » de l'IHM :
   - *Déclenchement* : automatique après chaque réponse, **sauf** pour les
     tours triviaux (l'agent a répondu sans appeler d'outil de contenu) où
     elle est sautée.
   - *Mécanique* (`DocumentAgent.reflect`) : un appel LLM juge la réponse
     **contre le même dossier de pièces que le rédacteur** (le contexte
     complet, pas un extrait) sur 4 critères : répond-elle à la question,
     est-elle étayée par le contexte, contradictions, manques. Sortie JSON
     `{score, issues, missing_info, action}`.
   - *Décision* : si `action = retry` **et** `score < 6`
     (`REFLECT_ACCEPT_THRESHOLD`) → **nouvelle tentative** : une boucle
     d'outils complémentaire ciblée sur `missing_info`, puis réécriture
     complète. Le brouillon reste affiché, grisé « Révisée après réflexion » ;
     la version finale le remplace comme réponse de référence (au plus
     `MAX_RETRY = 1` cycle).
   - *Pendant le retry* : l'IHM affiche « Recherche complémentaire en
     cours… » ; la durée dépend du modèle de rédaction (la réponse est
     écrite deux fois).
5. Persistance dans la session (`models/session.py`, `results/_sessions/`).

## Citations & visionneuse (IHM)

`static/js/app.js` :
- `linkifyCitations` transforme les citations textuelles du modèle (toutes
  variantes tolérées : `(node_0007, page 3)`, `(doc: f.pdf, 1, page 5)`,
  `(pages 5-6)`, crochets `【】`, placeholder `source`…) en **pastilles
  uniformes** `p. N` ;
- clic → panneau latéral (`showPagePreviewModal`) : images des pages, défilement
  à la page citée, surlignage du nœud source (bbox) ; pour une citation « pages
  seules », le nœud propriétaire est déduit des plages du `node_map`.

## Configuration des modèles (`config.py` → `config.json`, hors git)

| Profil | Usage | Exemple local |
|---|---|---|
| `text` | rédaction des réponses | nemotron-3-super |
| `light` | indexation + toutes les étapes internes de l'agent (hérite de `text` si absent) | gpt-oss-20b-128k |
| `vision` | réponses sur images de pages | (OpenAI par défaut) |

Tout serveur OpenAI-compatible fonctionne (Ollama, vLLM, LM Studio…) : URL de
base personnalisée, clé factice injectée si absente.

## Modifications locales apportées à la bibliothèque `pageindex/`

Le dossier `pageindex/` reste proche de l'amont, avec quatre ajustements :
1. texte des nœuds balisé `<page_N>` (citations à la page près) ;
2. résumés de nœuds « identitaires » (nature, auteur, destinataire, date —
   voir plus haut) et dans la langue du document, titres jamais traduits ;
3. contournement de l'heuristique de couverture de `verify_toc` + réparation
   en dernier recours (documents à long chapitre final, sommaires périmés) ;
4. tokenizer avec repli `o200k_base` pour les noms de modèles non-OpenAI.

## Limites connues

- Pas d'OCR : un PDF scanné sans couche texte n'est pas indexable en mode texte.
- La détection de sommaire ne balaie que les 20 premières pages (les tables en
  fin d'ouvrage, usage français, sont ignorées — le mode « sans sommaire »
  compense).
- L'indexation est non déterministe (LLM) : deux imports du même document
  peuvent produire des arbres légèrement différents.
- La précision des citations dépend de la discipline du modèle rédacteur ;
  l'IHM tolère les écarts de format mais ne peut pas inventer une page absente.
- Piste d'évolution identifiée : migrer le planificateur vers le function
  calling natif (comme `examples/agentic_vectorless_rag_demo.py` officiel)
  plutôt que le JSON-dans-le-texte hérité de l'amont.
