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
* **Questions-réponses sur base de connaissances (KB)** : l'utilisateur coche des documents ou des dossiers entiers ; le dossier est traité comme **un seul arbre PageIndex** (les pièces sont les nœuds, leurs fiches les résumés). L'**unité de travail est la pièce**, pas le fichier : un fichier composite (plusieurs documents dans un même PDF/.docx) est lui-même éclaté en pièces traitées séparément. La voie corpus localise les pièces pertinentes par un raisonnement sur l'inventaire des fiches, puis les lit ; une demande de synthèse d'ensemble est rédigée directement sur les fiches.
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

### Moteur de réponse — 4 voies

Le moteur ne repose **pas** sur une boucle d'outils : selon le contexte, `run_session` (`services/agent.py`) choisit l'une de **quatre voies**, toutes fondées sur le même pipeline canonique PageIndex (recherche par raisonnement → lecture des nœuds → rédaction citée). **Règle structurante : le retrieval passe exclusivement par le raisonnement sur l'arbre PageIndex** (`tree_search`) — pas de recherche plein-texte, pas d'embeddings.

| Voie | Quand | Principe |
| :-- | :-- | :-- |
| **Conversation libre** | aucun document | modèle **nu** (sans prompt système), réponses « sans sources » |
| **Mono-pièce** | 1 pièce | un `tree_search` → lecture des nœuds → rédaction citée |
| **Corpus** | ≥ 2 pièces | un `tree_search` sur les fiches de toutes les pièces → lecture des pièces retenues (drill-down des pièces volumineuses) → rédaction avec inventaire en appui |
| **Synthèse globale** | demande de vue d'ensemble | rédaction directe sur les fiches de toutes les pièces |

Après chaque réponse documentée : **note de qualité calculée** (déterministe) et, si besoin, **réflexion** — une seule recherche complémentaire ciblée, jamais de boucle. Une fois l'indexation terminée, le document est analysé automatiquement (résumé + questions suggérées).

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
* **Unité = pièce** : qu'il s'agisse d'un répertoire de fichiers OU de plusieurs documents réunis dans un seul fichier, chaque pièce (sous-arbre de niveau 1) est une unité de travail isolée, citable par son propre `doc_id` ; à l'indexation, **un résumé par pièce** dont les points saillants citent la page `(p. N)`, avec régime compilation (fiches isolées) vs document unique (fiches cumulatives) détecté automatiquement.
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

Documentation détaillée : [`ARCHITECTURE.md`](./ARCHITECTURE.md) (fonctionnement interne, où PageIndex est utilisé et où il ne l'est pas, modifications locales de la bibliothèque), [`DIAGNOSTIC-UEMO.md`](./DIAGNOSTIC-UEMO.md) (enquête sur la dégradation du modèle par les enrobages de prompt), [`ETUDE-RAGFLOW.md`](./ETUDE-RAGFLOW.md) (étude comparative), [`ETUDE-SEGMENTATION-PIECES.md`](./ETUDE-SEGMENTATION-PIECES.md) (conception : pré-segmentation déterministe des pièces), [`ETUDE-MAP-REDUCE-CIBLE.md`](./ETUDE-MAP-REDUCE-CIBLE.md) (conception : fiches spécifiques à chaud / map-reduce orienté requête), [`tests/`](./tests/) (tests d'acceptation).

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
│   ├── agent.py            #   Agent : 4 voies de réponse + réflexion + analyse
│   ├── rag_service.py      #   PageIndexService (LLM/VLM, tree_search) + RAGService
│   ├── indexing_service.py #   Ordonnancement de l'indexation
│   └── skill_manager.py    #   Gestion des compétences (skills Markdown)
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

**Voie corpus en mode KB**

En mode KB, le retrieval ne charge jamais le texte intégral du dossier : un seul `tree_search` raisonne sur l'**inventaire des fiches de pièces** pour retenir les pièces pertinentes (≤ 12 lues en intégral, le reste restant citable via l'inventaire) ; une pièce composite volumineuse est elle-même sélectionnée section par section (hiérarchie niveau 2). Une demande de synthèse d'ensemble est rédigée directement sur les fiches de toutes les pièces.

---

## 🔌 API / Modèles

Ce projet appelle les LLM via le **SDK Python OpenAI** (`openai` >= 1.0) et est compatible avec tout point de terminaison de l'API Chat Completions.

| Profil | Modèle local (Ollama) | Description |
|------|----------|------|
| `text` **et** `light` | `gpt-oss-120b-64k` | **Modèle unique** : structure de l'arbre + résumés de pièces (indexation), rédaction, conversation libre et toutes les étapes internes de l'agent |
| `vision` | `qwen3.6` | Analyse visuelle de pages, OCR des scans |

**Un seul modèle pour tout → zéro swap** Ollama (`text` et `light` pointent sur le même modèle). **Gestion du contexte** : l'app ne passe pas de `num_ctx`, donc la fenêtre est figée dans le modèle — `gpt-oss-120b-64k` = `FROM gpt-oss:120b` + `PARAMETER num_ctx 65536` (dimensionné sur le pic des budgets, ~31k tokens, ~76 Go VRAM). Ce projet **n'utilise pas de modèle d'Embedding ni de base de données vectorielle**. Aucune température n'est imposée : chaque modèle tourne avec les réglages de son Modelfile.

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

* **JSON.** L'agent attend du JSON strict pour la réflexion (auto-évaluation) et l'analyse de document. Les petits modèles peuvent produire du JSON imparfait — des *fallbacks* évitent tout plantage, mais la qualité du raisonnement dépend de la capacité du modèle (privilégiez un modèle costaud).
* **Vision.** Le mode vision envoie des images en base64 ; utilisez un modèle multimodal et vérifiez sa prise en charge.
* **Vitesse.** L'indexation déclenche de nombreux appels LLM (TOC, résumé de chaque nœud) : cela peut être lent sur CPU local.

### ⚙️ Paramètres clés

| Paramètre | Valeur | Description |
|------|-----|------|
| `REFLECT_ACCEPT_THRESHOLD` | 6 | Une note de réflexion inférieure déclenche une recherche complémentaire (sur 10) |
| `SIMPLE_CONTEXT_BUDGET` | 60000 | Caractères de texte source fournis au rédacteur |
| `CORPUS_INVENTORY_BUDGET` | 45000 | Budget de l'inventaire des fiches (voie corpus) |
| `CORPUS_MAX_PIECES_READ` | 12 | Pièces lues en intégral par réponse |
| `SUMMARY_CONCURRENCY` | 3 | Résumés de pièces concurrents max à l'indexation |
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
