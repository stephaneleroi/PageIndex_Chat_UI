# PageIndex Chat UI

> ⚠️ **Projet en cours de refonte / Under Reconstruction**
>
> Ce projet est en phase de refonte ; l'architecture, le modèle de données et les modes d'interaction sont susceptibles d'évoluer.
> Une nouvelle documentation sera complétée une fois la refonte achevée.
>
> L'ancien README est conservé sous [`README_old.md`](./README_old.md),
> à titre de référence historique uniquement ; les modes d'utilisation qui y sont décrits peuvent ne pas correspondre au code actuel.

---

<p align="center">
  <a href="#-présentation-du-projet">Présentation</a> •
  <a href="#-fonctionnalités-clés">Fonctionnalités</a> •
  <a href="#-démarrage-rapide">Démarrage rapide</a> •
  <a href="#-api--modèles">API/Modèles</a> •
  <a href="#-remerciements">Remerciements</a>
</p>

---

## 📖 Présentation du projet

**PageIndex Chat UI** est un système de questions-réponses documentaires de type **Agentic RAG** basé sur [PageIndex](https://github.com/VectifyAI/PageIndex). Il ne nécessite ni base de données vectorielle ni Embedding : il s'appuie entièrement sur le LLM pour naviguer par raisonnement dans l'arborescence (table des matières) du document.

La version refondue prend en charge deux modes de conversation :

* **Conversation mono-document (Single)** : questions-réponses approfondies sur un seul PDF ; le system prompt intègre l'arborescence complète, ce qui permet à l'Agent de planifier plus finement.
* **Questions-réponses sur base de connaissances (KB)** : l'utilisateur choisit librement plusieurs documents à inclure dans la conversation ; l'Agent effectue une recherche et une synthèse automatiques entre documents par divulgation progressive (métadonnées → table des matières → contenu des chapitres).



### 💡 Idée centrale : similarité ≠ pertinence

Le RAG traditionnel s'appuie sur les Embeddings vectoriels — or un fragment sémantiquement similaire n'est pas nécessairement le contexte requis pour répondre à la question. PageIndex adopte une approche différente :

* **Lors de l'indexation** : le PDF est analysé en une structure arborescente hiérarchique (semblable à la table des matières d'un livre), et un résumé est généré pour chaque nœud.
* **Lors des questions-réponses** : l'Agent localise, niveau par niveau, le chapitre/paragraphe contenant la réponse en s'appuyant sur cette structure arborescente.

*Aucun Embedding, aucune base de données vectorielle.*

---

## Interface

![ui](image/readme/UI.png)
![kb_chat](image/readme/kb_chat.png)

---

## ✨ Fonctionnalités clés

### Agent multi-outils

Le moteur de questions-réponses est un Agent doté d'une chaîne de raisonnement complète. Face à une question de l'utilisateur, il planifie de manière autonome ses chemins de recherche, de lecture et de synthèse, en choisissant parmi 8 outils :

| Outil | Description |
| :--: | :--: |
| `tree_search` | Recherche par raisonnement sur l'arborescence du document pour localiser les chapitres pertinents |
| `read_node` | Lit le texte complet d'un nœud donné |
| `keyword_search` | Correspondance exacte de mots-clés/expressions sur l'ensemble du texte |
| `view_pages` | Envoie des images de pages au VLM pour analyser graphiques/formules/tableaux |
| `summarize_nodes` | Génère un résumé LLM du contenu des nœuds pour compresser l'information |
| `list_documents` | Liste les métadonnées des documents accessibles (mode KB) |
| `read_document_toc` | Lit la structure de la table des matières d'un document (mode KB) |
| `cross_search` | Recherche parallèle à travers plusieurs documents (mode KB) |

À chaque tour de conversation, l'Agent exécute le cycle complet **décomposition → recherche par raisonnement → génération de la réponse → auto-évaluation** :

* Les questions complexes sont automatiquement décomposées en sous-questions, recherchées séparément puis synthétisées.
* Après génération, la qualité de la réponse est évaluée automatiquement ; si elle est insuffisante, une recherche complémentaire est lancée et la réponse réécrite.
* Une fois l'indexation terminée, le document est analysé automatiquement pour produire un résumé, des découvertes clés et des questions suggérées.

### Double mode texte / vision

| Mode | Description |
| :--: | :--: |
| **Mode texte** | Utilise le texte des nœuds comme contexte et appelle le modèle texte |
| **Mode vision** | Utilise les images de pages comme contexte et appelle le modèle multimodal pour analyser graphiques/formules/tableaux |

### Compétences personnalisées (Skills)

Des fichiers Markdown définissent des compétences spécialisées de l'Agent, permettant d'étendre son comportement sans modifier le code. Chaque skill déclare ses conditions d'activation, son flux d'appels d'outils, son format de sortie et ses règles anti-hallucination :

| Compétence | Par défaut | Rôle |
| :--: | :--: | :-- |
| **Lecture rapide de document** `key_info_extraction` | ✅ | Fiche de lecture rapide générique pour articles/rapports/manuels/contrats/rapports financiers, avec sortie adaptée au type de document |
| **Comparaison structurée** `structured_comparison` | ✅ | Comparaison multidimensionnelle de chapitres/méthodes/clauses/versions/produits |
| **Extraction de tableaux** `table_extraction` | ✅ | Double mode texte/vision, restitution précise sous forme de tableau Markdown |

### Interface

* Disposition en trois pages : gestion de la base de connaissances / conversation mono-document / questions-réponses sur base de connaissances
* Traçabilité des nœuds : les réponses sont accompagnées des ID de nœuds et numéros de page cités ; un clic redirige vers l'emplacement correspondant du PDF
* La conversation mono-document et les questions-réponses sur base de connaissances disposent toutes deux d'une mémoire conversationnelle

---

## 🚀 Démarrage rapide

### Prérequis

* Python >= 3.11
* Une clé API OpenAI (ou tout service compatible avec le format de l'API OpenAI)

### Installation

```bash
# Avec uv (recommandé)
uv sync

# Ou avec pip
pip install -r requirements.txt
```

### Lancement

```bash
python app.py          # ou uv run python app.py / ./start.sh
```

Le service tourne par défaut sur **http://localhost:5001**.

### ⚙️ Première configuration

Ouvrez le panneau des paramètres et renseignez le nom, la clé API et la Base URL du modèle texte et du modèle vision. La configuration est enregistrée dans `config.json`.

---

## 🏗️ Architecture technique

### 📁 Arborescence du projet

```
PageIndex_Chat_UI/
├── app.py                  # Point d'entrée de l'application Flask
├── config.py               # Gestion de la configuration
├── config.json             # Configuration d'exécution (avec clé API)
├── pyproject.toml          # Métadonnées du projet & dépendances
├── start.sh                # Script de lancement
│
├── pageindex/              # Moteur d'indexation PageIndex
│   ├── page_index.py       #   Construction de l'arborescence : détection de la TOC → alignement des pages → division récursive
│   ├── utils.py            #   Analyse PDF, encapsulation des appels LLM
│   └── config.yaml         #   Paramètres d'indexation
│
├── services/               # Couche de logique métier
│   ├── agent.py            #   Agent : décomposition / ReAct / réflexion / analyse
│   ├── rag_service.py      #   Service RAG + appels LLM/VLM
│   ├── indexing_service.py #   Ordonnancement de l'indexation
│   ├── skill_manager.py    #   Gestion des compétences
│   └── tools/              #   8 outils de l'Agent
│       ├── base.py
│       ├── tree_search.py  ├── node_reader.py  ├── keyword_search.py
│       ├── page_viewer.py  ├── summarizer.py
│       ├── list_documents.py  ├── read_toc.py  ├── cross_search.py
│
├── skills/                 # Compétences personnalisées (Markdown)
│   ├── key_info_extraction.md
│   ├── structured_comparison.md
│   └── table_extraction.md
│
├── models/                 # Modèles de données
│   ├── document.py         #   Document / DocumentStore
│   └── session.py          #   ChatSession / Message / SessionStore
│
├── routes/
│   ├── api.py              #   API REST
│   └── socket_handlers.py  #   Chat en streaming Socket.IO
│
├── templates/index.html    # SPA frontend
├── static/
│   ├── css/app.css
│   └── js/app.js
│
├── uploads/                # Téléversements de PDF (gitignored)
├── results/                # Résultats d'indexation et données de session (gitignored)
│   ├── _index/             #   Index des sessions (par mode)
│   ├── _sessions/          #   Données de session (isolées par mode)
│   └── documents/          #   Résultats d'indexation des documents
└── image/                  # Illustrations du README
```

### 🔑 Points clés de l'architecture

**Découplage entre Session et Document**

Le changement central de la refonte : la Session n'est plus liée au cycle de vie du Document. Chaque Session est stockée indépendamment et peut être associée à un ou plusieurs documents :

* Les sessions en mode `single` sont regroupées par document ; supprimer un document nettoie automatiquement les sessions associées.
* Les sessions en mode `kb` sont stockées à plat, indépendamment d'un document unique.

Les sessions des deux modes n'interfèrent pas entre elles ; le stockage et l'indexation sont isolés par mode.

**Divulgation progressive en mode KB**

En mode KB, le system prompt n'intègre pas l'arborescence complète (coût en tokens trop élevé) ; l'Agent décide lui-même de la profondeur d'exploration : `list_documents` (métadonnées) → `read_document_toc` (table des matières) → `tree_search` (contenu détaillé).

---

## 🔌 API / Modèles

Ce projet appelle les LLM via le **SDK Python OpenAI** (`openai` >= 1.0) et est compatible avec tout point de terminaison de l'API Chat Completions.

| Usage | Modèle par défaut | Description |
|------|----------|------|
| Construction de l'index | `gpt-5-mini` | Détection de la TOC, analyse de structure, génération de résumés |
| Questions-réponses texte | `gpt-5-mini` | Raisonnement de l'Agent, appels d'outils, génération des réponses |
| Questions-réponses vision | `gpt-5-mini` | Analyse visuelle de graphiques/formules/tableaux |

Ce projet **n'utilise pas de modèle d'Embedding ni de base de données vectorielle**.

### ⚙️ Paramètres clés

| Paramètre | Valeur | Description |
|------|-----|------|
| `MAX_REACT_STEPS` | 5 | Nombre maximal d'étapes ReAct |
| `MAX_RETRY` | 1 | Nombre maximal de nouvelles tentatives en cas d'échec de la réflexion |
| `REFLECT_ACCEPT_THRESHOLD` | 6 | Une note de réflexion inférieure déclenche une nouvelle tentative (sur 10) |
| `max_page_num_each_node` | 10 | Nombre maximal de pages par nœud |
| `max_token_num_each_node` | 20000 | Nombre maximal de tokens par nœud |

---

## 📦 Dépendances

| Dépendance | Usage |
|------|------|
| Flask + Flask-SocketIO | Framework web + communication en temps réel |
| openai | API LLM / VLM |
| PyMuPDF | Rendu PDF, extraction de texte |
| PyPDF2 | Extraction de texte PDF |
| tiktoken | Comptage de tokens |
| PyYAML | Analyse de la configuration |

---

## 🙏 Remerciements

L'algorithme central d'indexation PageIndex s'inspire de [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex).

---

## 📄 License

MIT License
