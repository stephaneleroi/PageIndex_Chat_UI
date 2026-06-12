# POC Réponses Sourcées (PageIndex Chat UI)

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

**POC Réponses Sourcées** est un système de questions-réponses documentaires de type **Agentic RAG** basé sur [PageIndex](https://github.com/VectifyAI/PageIndex). Il ne nécessite ni base de données vectorielle ni Embedding : il s'appuie entièrement sur le LLM pour naviguer par raisonnement dans l'arborescence (table des matières) du document. Il tourne intégralement en local sur Ollama (ou tout serveur OpenAI-compatible).

Trois modes de conversation :

* **Conversation mono-document (Single)** : questions-réponses approfondies sur un seul PDF, via la voie simple canonique du cookbook PageIndex (une recherche par raisonnement → lecture des nœuds → rédaction citée).
* **Questions-réponses sur base de connaissances (KB)** : l'utilisateur coche des documents ou des dossiers entiers ; l'Agent effectue recherche et synthèse entre documents par divulgation progressive (métadonnées → table des matières → contenu des chapitres).
* **Conversation libre** : sans document sélectionné, le dialogue passe au modèle **nu** — aucune instruction ajoutée, aucun réglage forcé (principe : l'application ne doit pas dégrader le modèle, voir `DIAGNOSTIC-UEMO.md`). Ces réponses sont signalées « sans sources ».



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

Le moteur de questions-réponses est un Agent (function calling natif, repli JSON texte) qui planifie ses chemins de recherche, de lecture et de synthèse. **Règle structurante : le retrieval passe exclusivement par le raisonnement sur l'arbre PageIndex** — les outils hors paradigme sont désactivés (code conservé) :

| Outil | État | Description |
| :--: | :--: | :--: |
| `tree_search` | ✔ | Recherche par raisonnement sur l'arborescence (prompt canonique du cookbook) |
| `read_node` | ✔ | Lit le texte complet d'un nœud donné |
| `view_pages` | ✔ | Envoie des images de pages au VLM pour analyser graphiques/formules/tableaux |
| `list_documents` | ✔ | Liste les métadonnées des documents accessibles (mode KB) |
| `read_document_toc` | ✔ | Lit la structure de la table des matières d'un document (mode KB) |
| `cross_search` | ✔ | `tree_search` en parallèle sur plusieurs documents (mode KB) |
| `keyword_search` | ✘ désactivé | Recherche littérale — contourne le raisonnement sur l'arbre |
| `summarize_nodes` | ✘ désactivé | Étape absente du flux canonique, dégrade la traçabilité des pages |

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

### Réponses sourcées et vérifiables

* **Citations à la page près** : chaque affirmation porte une pastille cliquable `p. N` ouvrant la visionneuse PDF à la page citée, avec surlignage de la section source.
* **Note de qualité calculée** sur chaque réponse documentée (vérification déterministe : citations présentes, nœuds cités ∈ sources, pages citées ∈ plages réelles) + bouton « Vérifier la réponse » (juge LLM à la demande, verdict persisté).
* Boutons **copier** et **modifier** sur chaque réponse.

### Robustesse documentaire (dossiers de procédure)

* **Import de dossiers** entiers (arborescence conservée dans la bibliothèque et cochable d'un bloc), import **.docx** (conversion LibreOffice), **OCR vision** pour les pages scannées.
* **File d'indexation séquentielle**, **deux tentatives automatiques** par pièce, bouton « Relancer » sur les pièces en erreur.
* **Cache de réimportation** : l'arbre est sauvegardé à côté du PDF source (`<nom>.pdf.pageindex.json`) ; réimporter le même fichier ne refait aucun appel LLM.
* **Arbre éditable** (titres et résumés des nœuds) depuis la modale « Structure » — l'arbre étant l'index de recherche, c'est le levier d'intervention humaine le plus rentable.

### Interface

* Disposition en trois pages : gestion de la base de connaissances / conversation mono-document / questions-réponses sur base de connaissances
* Mémoire conversationnelle dans les deux modes de chat

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
# toujours dans le venv
.venv/bin/python main.py
```

Le service tourne par défaut sur **http://localhost:5001**.

> ⚠️ Le serveur de développement recharge automatiquement à chaque
> modification d'un fichier `.py` — ce qui **tue les indexations en cours**
> (les pièces interrompues passent en erreur, bouton « Relancer »).
> Ne modifiez pas le code pendant une indexation par lot.

### ⚙️ Première configuration

Ouvrez le panneau des paramètres et renseignez le nom, la clé API et la Base URL du modèle texte et du modèle vision. La configuration est enregistrée dans `config.json`.

> Vous pouvez aussi utiliser un fournisseur compatible OpenAI ou un modèle **local via Ollama** — voir [API / Modèles](#-api--modèles).

---

## 🏗️ Architecture technique

### 📁 Arborescence du projet

Documentation détaillée : [`ARCHITECTURE.md`](./ARCHITECTURE.md) (fonctionnement interne, où PageIndex est utilisé et où il ne l'est pas, modifications locales de la bibliothèque), [`DIAGNOSTIC-UEMO.md`](./DIAGNOSTIC-UEMO.md) (enquête sur la dégradation du modèle par les enrobages de prompt), [`ETUDE-RAGFLOW.md`](./ETUDE-RAGFLOW.md) (étude comparative), [`tests/`](./tests/) (tests d'acceptation).

```
PageIndex_Chat_UI/
├── main.py / app.py        # Point d'entrée de l'application Flask
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

| Profil | Exemple local (Ollama) | Description |
|------|----------|------|
| `light` (rapide) | `gpt-oss-20b-128k` | Indexation (TOC, structure, résumés) + étapes internes de l'agent ; hérite de `text` si absent |
| `text` | `nemotron-3-super` | Rédaction des réponses, conversation libre |
| `vision` | `qwen3.6` | Analyse visuelle de pages, OCR des scans |

Ce projet **n'utilise pas de modèle d'Embedding ni de base de données vectorielle**. Aucune température n'est imposée : chaque modèle tourne avec les réglages de son Modelfile (recommandations de l'éditeur).

### 🔧 Configurer le LLM (URL personnalisée, fournisseurs compatibles)

Chaque modèle (texte **et** vision) se configure indépendamment via **trois champs** — *Nom du modèle*, *API Key*, *Base URL* — dans le panneau ⚙️ (« Configuration des modèles ») ou dans `config.py` / `config.json`.

Le `base_url` est pleinement pris en charge à la fois pour **l'indexation** et pour **les réponses**. Vous pouvez donc pointer vers n'importe quel point de terminaison compatible OpenAI :

```
Base URL : https://votre-fournisseur/v1
API Key  : votre-clé
Nom      : nom-du-modèle
```

Exemples compatibles : Azure OpenAI, OpenRouter, Together, Groq, vLLM, LM Studio, LiteLLM…

### 🦙 Utilisation avec Ollama en local

Ollama expose une API compatible OpenAI. Après avoir récupéré un modèle (`ollama pull llama3.1`), configurez :

| Champ | Valeur |
|------|------|
| **Base URL** | `http://localhost:11434/v1` |
| **API Key** | *(facultatif)* — laissez vide ou mettez n'importe quoi ; une clé factice est injectée automatiquement |
| **Nom du modèle** | un modèle installé, ex. `llama3.1`, `qwen2.5` (texte) ; `llama3.2-vision`, `llava` (vision) |

> 💡 Dès que la *Base URL* n'est pas celle d'OpenAI, l'application n'exige plus de clé : une valeur factice est fournie au SDK aussi bien pour l'indexation que pour le chat.

**À garder en tête avec des modèles locaux :**

* **JSON.** L'Agent attend du JSON strict (décomposition, ReAct, auto-évaluation, analyse). Les petits modèles peuvent produire du JSON imparfait — des *fallbacks* évitent tout plantage, mais la qualité du raisonnement dépend de la capacité du modèle (privilégiez ≥ 14B).
* **Vision.** Le mode vision envoie des images en base64 ; utilisez un modèle multimodal et vérifiez sa prise en charge.
* **Vitesse.** L'indexation déclenche de nombreux appels LLM (TOC, résumé de chaque nœud) : cela peut être lent sur CPU local.

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
