# Architecture de PageIndex Chat UI

## L'idée en une phrase

Ce projet n'est **pas** seulement une IHM : c'est une **application complète de
questions-réponses documentaire** construite *au-dessus* de la bibliothèque
open-source [PageIndex](https://github.com/VectifyAI/PageIndex), qui elle ne
fournit que l'**indexation** (PDF → arbre de structure). Tout ce qui *exploite*
cet arbre pour répondre aux questions — l'agent, ses outils, le serveur, l'IHM —
est du code propre au projet.

## Pourquoi des outils à nous ? La frontière PageIndex / projet

Le dépôt officiel PageIndex publie l'algorithme d'indexation « vectorless »
(et un retrieval de base), mais **pas** d'application de chat : le produit
chat.pageindex.ai est un service propriétaire construit sur leur API payante.
Ce fork reproduit l'équivalent **en local** (Ollama / serveurs
OpenAI-compatibles) — il faut donc bien écrire soi-même la partie agentique
que l'API cloud aurait fournie. C'est le rôle de `services/`.

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
│  · outils de navigation dans   services/indexing_service.py      │
│    l'arbre (voir ci-dessous)   services/skill_manager.py         │
│  · stockage docs & sessions    models/document.py, session.py    │
├──────────────────────────────────────────────────────────────────┤
│  Bibliothèque PageIndex        pageindex/  ← code (quasi) amont  │
│  PDF → arbre de sections       pageindex/page_index.py           │
│  (détection sommaire,          pageindex/utils.py                │
│  vérification, résumés)                                          │
└──────────────────────────────────────────────────────────────────┘
```

## Cycle de vie d'un document (indexation)

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

Tous ces appels LLM utilisent le profil **« rapide »** (configurable, onglet
« Modèle rapide » des réglages).

## Cycle de vie d'une question (agent ReAct)

`services/agent.py`, événement Socket.IO `agent_chat` :

1. **Décomposition** (profil rapide) : sous-questions si nécessaire.
2. **Boucle ReAct** (≤ 5 étapes/sous-question, profil rapide) : à chaque tour le
   planificateur choisit un outil de `services/tools/` :

   | Outil | Rôle | LLM ? |
   |---|---|---|
   | `tree_search` | choisir les nœuds pertinents en lisant l'arbre (titres + résumés) — réutilise le retrieval PageIndex | oui |
   | `cross_search` | tree_search sur plusieurs documents + repli **littéral** sur le texte brut si zéro résultat | oui |
   | `keyword_search` | recherche littérale dans le texte des nœuds | non |
   | `read_node` | lire le texte complet (balisé par page) de nœuds | non |
   | `summarize_nodes` | résumer des nœuds (annoté par page) | oui |
   | `list_documents` / `read_toc` | inventaire / table des matières | non |
   | `view_pages` | analyse visuelle des images de pages | VLM |

3. **Rédaction** (profil **texte**, le « gros » modèle) : prompt avec la trace
   de raisonnement + le texte source balisé (plafond 60 000 caractères) +
   règles de citation `(node_<id>, page N)`.
4. **Auto-évaluation** (profil rapide) : score /10 ; si < 6 → **retry** (boucle
   complémentaire + réécriture).
5. Persistance dans la session (`models/session.py`, `results/_sessions/`).

## Citations & visionneuse (IHM)

`static/js/app.js` :
- `linkifyCitations` transforme les citations textuelles du modèle (toutes
  variantes tolérées : `(node_0007, page 3)`, `(doc: f.pdf, 1, page 5)`,
  `(pages 5-6)`, crochets `【】`…) en **pastilles uniformes** `p. N` ;
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

Le dossier `pageindex/` reste proche de l'amont, avec trois ajustements :
1. texte des nœuds balisé `<page_N>` (citations à la page près) ;
2. contournement de l'heuristique de couverture de `verify_toc` + réparation
   en dernier recours (documents à long chapitre final, sommaires périmés) ;
3. consignes de langue (titres jamais traduits, résumés dans la langue du
   document).

## Limites connues

- Pas d'OCR : un PDF scanné sans couche texte n'est pas indexable en mode texte.
- La détection de sommaire ne balaie que les 20 premières pages (les tables en
  fin d'ouvrage, usage français, sont ignorées — le mode « sans sommaire »
  compense).
- L'indexation est non déterministe (LLM) : deux imports du même document
  peuvent produire des arbres légèrement différents.
- La précision des citations dépend de la discipline du modèle rédacteur ;
  l'IHM tolère les écarts de format mais ne peut pas inventer une page absente.
