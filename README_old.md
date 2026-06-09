🤖 PageIndex Chat UI

> **Système de questions-réponses documentaires de type Agentic RAG fondé sur le raisonnement par structure arborescente**
> Sans vecteur, sans Embedding — permettre au LLM de lire les documents comme un humain

<p align="center">
  <a href="#-présentation-du-projet">Présentation</a> •
  <a href="#-fonctionnalités-clés">Fonctionnalités</a> •
  <a href="#-démarrage-rapide">Démarrage rapide</a> •
  <a href="#️-architecture-technique">Architecture</a> •
  <a href="#-api--modèles">API/Modèles</a> •
  <a href="#-estimation-des-coûts">Coûts</a> •
  <a href="#-remerciements">Remerciements</a>
</p>

---

## 📖 Présentation du projet

**PageIndex Chat UI** est un système de questions-réponses intelligent dédié aux documents PDF. Il s'appuie sur l'algorithme d'indexation central du projet open source PageIndex, par-dessus lequel il bâtit une interface d'interaction **Agentic RAG** complète.

![ui](image/WebUI1.png)

### 💡 Idée centrale : similarité ≠ pertinence

Les systèmes RAG traditionnels s'appuient sur des Embeddings vectoriels pour la recherche — or un fragment sémantiquement similaire n'est pas nécessairement le contexte requis pour répondre à la question. PageIndex adopte une approche radicalement différente :
* **Lors de l'indexation** : le PDF est analysé en une structure arborescente hiérarchique (semblable à la table des matières d'un livre), et un résumé est généré pour chaque nœud.
* **Lors des questions-réponses** : le LLM navigue par raisonnement dans la structure arborescente et localise, niveau par niveau, le chapitre/paragraphe contenant la réponse.

*Aucun Embedding, aucune base de données vectorielle : la recherche repose entièrement sur les capacités de raisonnement du LLM.*


---

## ✨ Fonctionnalités clés

### 🧠 Système d'Agent (cinq capacités)
Le moteur de questions-réponses de ce projet n'est pas un simple pipeline « recherche → génération », mais un Agent doté d'une chaîne de raisonnement complète :

| Capacité | Description |
| :--: | :--: |
| **Boucle ReAct** | Raisonnement itératif Think → Act → Observe, jusqu'à 5 tours |
| **Orchestration multi-outils** | 5 outils intégrés ; l'Agent choisit lui-même lequel utiliser à chaque étape |
| **Décomposition des questions** | Les questions complexes sont automatiquement décomposées en sous-questions, recherchées séparément puis synthétisées |
| **Auto-réflexion** | Après génération, la qualité de la réponse est évaluée automatiquement ; si elle est insuffisante, une recherche complémentaire est lancée et la réponse réécrite |
| **Analyse proactive** | Une fois l'indexation du document terminée, un résumé, des découvertes clés et des questions suggérées sont générés automatiquement |

### 🛠️ Outils intégrés
À chaque tour de boucle ReAct, l'Agent peut appeler les outils suivants :

| Nom de l'outil | Description fonctionnelle |
| :--: | :--: |
| `tree_search` | Recherche par raisonnement sur l'arborescence du document pour localiser les chapitres pertinents |
| `read_node` | Lit le texte complet d'un nœud donné |
| `keyword_search`| Correspondance exacte de mots-clés/expressions sur l'ensemble du texte |
| `view_pages` | Consulte les images de pages (en mode vision, analyse graphiques/formules/tableaux via le VLM) |
| `summarize_nodes`| Génère un résumé LLM du contenu des nœuds pour compresser l'information |

### 🌗 RAG en double mode

| Mode | Description | Cas d'usage |
| :--: | :--: | :--: |
| **Mode texte** | Utilise le texte des nœuds comme contexte et appelle le modèle texte | Documents principalement textuels |
| **Mode vision** | Utilise les images de pages comme contexte et appelle le modèle multimodal | Documents riches en graphiques, formules et tableaux |

### 🧩 Compétences personnalisées (Skills)
Des fichiers Markdown définissent des compétences spécialisées de l'Agent, permettant d'étendre son comportement sans modifier le code. Chaque skill comprend : conditions d'activation / conditions de non-déclenchement / flux d'appels d'outils / format de sortie / règles anti-hallucination. 7 compétences sont intégrées :

| Compétence | État par défaut | Rôle |
| :--: | :--: | :-- |
| **Priorité aux preuves et traçabilité** `evidence_grounding` | ✅ Activée | **Méta-compétence** : toute réponse doit être accompagnée des ID de nœuds/numéros de page ; toute incertitude doit être déclarée ; toute invention est interdite |
| **Lecture rapide de document (générique)** `key_info_extraction` | ✅ Activée | Fiche de lecture rapide générique pour articles/rapports/manuels/contrats/rapports financiers, avec sortie adaptée au type de document |
| **Comparaison structurée** `structured_comparison` | ⚪ À la demande | Comparaison multidimensionnelle de chapitres/méthodes/clauses/versions/produits |
| **Extraction et restitution de tableaux** `table_extraction` | ⚪ À la demande | Double mode texte/vision, restitution précise sous forme de tableau Markdown |
| **Explication de formules** `formula_explainer` | ⚪ À la demande | Formule originale/symboles/intuition/démonstration, respect strict des conventions LaTeX |
| **Suivi des références croisées** `cross_reference_tracing` | ⚪ À la demande | Suit automatiquement les renvois « voir section X / Figure Y / Appendix Z » pour lire et intégrer le contenu |
| **Questions-réponses sur données et indicateurs** `quantitative_qa` | ⚪ À la demande | Traçabilité stricte des questions quantitatives, estimation interdite, conservation de la précision et des unités d'origine |

### 🌟 Autres points forts
* **Sortie en streaming** : la réponse et le processus de raisonnement s'affichent en temps réel
* **Mémoire conversationnelle multi-tours** : conserve les 5 derniers tours de conversation comme contexte
* **Traçabilité des réponses** : chaque réponse indique les ID de nœuds et numéros de page cités, avec redirection directe possible
* **Surlignage des pages** : surligne sur l'image de la page PDF les nœuds source des blocs de texte correspondants
* **Configuration en ligne via l'interface web** : modèle, API Key et Base URL peuvent tous être modifiés dynamiquement depuis l'interface

---

## 🚀 Démarrage rapide

### Prérequis
* Python >= 3.11
* Une clé API OpenAI (ou tout service compatible avec le format de l'API OpenAI)

### Installation

```bash
# Avec pip
pip install -r requirements.txt

# Ou avec uv (recommandé, plus rapide)
uv sync
```

### Lancement

```bash
# Méthode 1 : exécution directe
python app.py

# Méthode 2 : avec uv
uv run python app.py

# Méthode 3 : avec le script de lancement (Linux/macOS)
./start.sh
```

Le service tourne par défaut sur **http://localhost:5001**

### ⚙️ Première configuration

Une fois lancé, ouvrez votre navigateur à l'adresse `http://localhost:5001`, cliquez sur l'icône des paramètres en haut à gauche de l'interface, puis configurez :

1. **Modèle texte** : renseignez le nom du modèle, l'API Key et la Base URL
2. **Modèle vision** (facultatif) : pour utiliser le mode vision, renseignez la configuration du modèle multimodal

La configuration est enregistrée dans `config.json`



## 🏗️ Architecture technique

### 🗺️ Schéma de l'architecture système

![Schéma de l'architecture](image/architecture.png)

### 🔄 Flux de travail de l'Agent

![Flux de travail](image/workflow.png)

### 📁 Arborescence du projet

```
PageIndex_Agent_UI/
├── app.py                  # Initialisation de l'application Flask, enregistrement des routes
├── main.py                 # Point d'entrée principal (lit config et lance)
├── config.py               # Gestion de la configuration (singleton ConfigManager)
├── config.json             # Configuration d'exécution (gitignored, avec API Key)
├── requirements.txt        # Dépendances Python
├── pyproject.toml          # Métadonnées du projet & dépendances (compatible uv)
├── start.sh                # Script de lancement
│
├── pageindex/              # Moteur d'indexation central PageIndex
│   ├── page_index.py       #   Construction de l'arborescence : détection de la TOC → alignement des pages → division récursive
│   ├── utils.py            #   Analyse PDF, comptage de tokens, encapsulation des appels LLM
│   └── config.yaml         #   Valeurs par défaut des paramètres d'indexation
│
├── services/               # Couche de logique métier
│   ├── agent.py            #   DocumentAgent : ReAct / décomposition / réflexion / analyse
│   ├── rag_service.py      #   Service RAG + encapsulation PageIndex (appels LLM/VLM)
│   ├── indexing_service.py #   Ordonnancement de l'indexation PDF
│   ├── skill_manager.py    #   Chargement et gestion des fichiers de compétences
│   └── tools/              #   Les 5 outils appelables par l'Agent
│       ├── base.py         #     BaseTool + ToolRegistry
│       ├── tree_search.py  #     Outil de recherche arborescente
│       ├── node_reader.py  #     Outil de lecture de nœuds
│       ├── keyword_search.py#    Outil de recherche par mots-clés
│       ├── page_viewer.py  #     Outil de consultation de pages (VLM)
│       └── summarizer.py   #     Outil de résumé
│
├── skills/                 # Compétences personnalisées (format Markdown)
│   ├── formula_explainer.md
│   ├── key_info_extraction.md
│   ├── paper_comparison.md
│   └── table_extraction.md
│
├── models/                 # Modèles de données
│   └── document.py         #   Document / Message / DocumentStore
│
├── routes/                 # Routes & communication
│   ├── api.py              #   API REST (téléversement de fichiers, configuration, gestion des compétences)
│   └── socket_handlers.py  #   Traitement WebSocket (chat, progression de l'indexation)
│
├── templates/
│   └── index.html          # Page frontend (SPA en un seul fichier)
├── static/
│   └── js/app.js           # Logique frontend
│
├── uploads/                # Stockage des PDF téléversés (gitignored)
└── results/                # Stockage des résultats d'indexation (gitignored)
```


## 🔌 API / Modèles

### Modes d'appel

Ce projet appelle les LLM via le **SDK Python OpenAI** (`openai` >= 1.0) et prend en charge à la fois les appels synchrones et asynchrones :

| Scénario | Mode d'appel | Description |
|------|----------|------|
| Construction de l'index (PageIndex Core) | Appel synchrone `openai.OpenAI` | Famille de fonctions `ChatGPT_API` dans `pageindex/utils.py` |
| Raisonnement de questions-réponses (Agent / RAG) | Appel asynchrone `openai.AsyncOpenAI` | `call_llm` / `call_vlm` dans `services/rag_service.py` |

Tous les appels configurent le point de terminaison de l'API via le paramètre `base_url` ; par conséquent, **tout service compatible avec le format de l'API OpenAI Chat Completions peut être utilisé** (proxys tiers, modèles déployés localement, etc.).

### Modèles concernés

Ce projet **n'utilise pas de modèle d'Embedding ni de base de données vectorielle**. Toutes les capacités reposent uniquement sur l'API Chat Completion.

| Usage | Emplacement de configuration | Modèle par défaut | Description |
|------|----------|----------|------|
| **Construction de l'index** | `pageindex/config.yaml` ou modèle texte de l'interface web | `gpt-4o-2024-11-20` | Détection de la TOC, analyse de structure, alignement des pages, génération de résumés. La qualité de l'index dépend fortement des capacités de raisonnement de ce modèle |
| **Questions-réponses - mode texte** | Interface web → modèle texte | `gpt-4o-mini` | Raisonnement de l'Agent, recherche arborescente, génération des réponses, auto-réflexion. Un modèle au bon rapport qualité-prix est recommandé |
| **Questions-réponses - mode vision** | Interface web → modèle vision | `gpt-4.1` | Nécessite des capacités multimodales (entrée d'images), pour l'analyse visuelle de graphiques/formules/tableaux |

> Les modèles par défaut ci-dessus ne sont que des configurations recommandées ; ils peuvent être librement remplacés par tout modèle compatible OpenAI dans le panneau des paramètres de l'interface web.
> En phase de test, le modèle texte et le modèle vision étaient tous deux 'gpt-5-mini'

### ⚙️ Paramètres de configuration

#### Configuration des modèles (`config.json` / interface web)

| Paramètre | Description |
|------|------|
| `models.text.name` | Nom du modèle texte (ex. `gpt-4o-mini`) |
| `models.text.api_key` | API Key du modèle texte |
| `models.text.base_url` | Point de terminaison de l'API du modèle texte (ex. `https://api.openai.com/v1`) |
| `models.vision.name` | Nom du modèle vision (ex. `gpt-4.1`) |
| `models.vision.api_key` | API Key du modèle vision |
| `models.vision.base_url` | Point de terminaison de l'API du modèle vision |

#### Paramètres d'indexation (`pageindex/config.yaml`)

| Paramètre | Valeur par défaut | Description |
|------|--------|------|
| `model` | `gpt-4o-2024-11-20` | Modèle utilisé pour la construction de l'index |
| `toc_check_page_num` | `20` | Nombre de pages à scanner en début de document pour détecter la TOC |
| `max_page_num_each_node` | `10` | Nombre maximal de pages par nœud ; au-delà, division récursive |
| `max_token_num_each_node` | `20000` | Nombre maximal de tokens par nœud ; au-delà, division récursive |
| `if_add_node_id` | `yes` | Attribuer ou non un ID aux nœuds |
| `if_add_node_summary` | `yes` | Générer ou non un résumé de nœud |
| `if_add_doc_description` | `no` | Générer ou non une description du document entier |
| `if_add_node_text` | `no` | Conserver ou non le texte original du nœud dans la structure |

#### Paramètres de l'Agent (constantes dans `services/agent.py`)

| Paramètre | Valeur | Description |
|------|-----|------|
| `MAX_REACT_STEPS` | `5` | Nombre maximal de tours ReAct par sous-question |
| `MAX_RETRY` | `1` | Nombre maximal de nouvelles tentatives après échec de la réflexion |
| `REFLECT_ACCEPT_THRESHOLD` | `6` | Une note de réflexion inférieure à cette valeur déclenche une nouvelle tentative (sur 10) |


## 💰 Estimation des coûts

Comme ce projet est entièrement piloté par l'API d'un LLM, le coût d'utilisation dépend de la tarification du modèle choisi. Les estimations ci-dessous se fondent sur les prix officiels d'OpenAI (2025) et sont fournies à titre indicatif uniquement.

> En pratique, tant que l'on n'utilise pas un modèle très coûteux comme `GPT5.2 Pro`, les dépenses d'API de ce projet restent tout à fait acceptables.

### Phase d'indexation (ponctuelle, par document)

Le processus d'indexation implique de nombreux appels LLM : détection de la TOC, analyse de structure, alignement et vérification des pages, génération des résumés de nœuds, etc.

| Taille du document | Nb estimé d'appels LLM | Avec gpt-4o-mini | Avec gpt-4o | Avec gpt-5-mini |
|----------|-------------------|-----------------|-------------|-------------|
| Document court (~10 pages) | 30–60 appels | $0.01–0.04 | $0.20–0.60 | $0.03–0.10 |
| Article (~20 pages) | 50–100 appels | $0.02–0.08 | $0.40–1.20 | $0.05–0.20 |
| Document long (~100 pages) | 150–400 appels | $0.08–0.30 | $1.50–5.00 | $0.20–0.80 |

> **Remarque** : le nombre d'appels du processus d'indexation est fortement corrélé à la complexité structurelle du document. Les documents dotés d'une table des matières claire nécessitent moins d'appels ; les documents sans table des matières exigent de reconstruire la structure de zéro, d'où un nombre d'appels plus élevé.

### Phase de questions-réponses (par question)

Chaque question passe par : décomposition de la question (1 appel) → boucle ReAct (3–10 appels) → génération de la réponse (1 appel) → réflexion (1 appel), avec d'éventuelles nouvelles tentatives.

| Scénario | Nb estimé d'appels LLM | Avec gpt-4o-mini | Avec gpt-4o / gpt-4.1 | Avec gpt-5-mini |
|------|-------------------|-----------------|----------------------|-------------|
| Question simple (recherche en une étape) | 4–6 appels | $0.003–0.008 | $0.05–0.10 | $0.008–0.02 |
| Question courante (raisonnement multi-étapes) | 6–12 appels | $0.005–0.015 | $0.08–0.20 | $0.015–0.04 |
| Question complexe (décomposition + nouvelles tentatives) | 12–20 appels | $0.01–0.03 | $0.15–0.40 | $0.03–0.09 |
| Mode vision (avec entrée d'images) | 6–15 appels | — | $0.10–0.50 | $0.01–0.05 |

> **Remarque** : le mode vision, qui doit transmettre les images de pages (base64), consomme nettement plus de tokens que le mode texte pur.

### Exemples de coûts d'utilisation typiques

| Scénario | Configuration des modèles | Coût estimé |
|------|----------|---------|
| Indexer un article de 20 pages + poser 10 questions | Indexation gpt-4o-mini, questions-réponses gpt-4o-mini | ~$0.10–0.20 |
| Indexer un article de 20 pages + poser 10 questions | Indexation gpt-4o, questions-réponses gpt-4o-mini | ~$0.50–1.50 |
| Indexer un article de 20 pages + poser 10 questions	| Indexation gpt-5-mini, questions-réponses gpt-5-mini | ~$0.20–0.60 |

### Référence de tests réels

**Document : Attention is All You need**

> Ce document est un PDF de 11 pages ; le modèle gpt5mini est utilisé pour le texte comme pour la vision

**Coût de construction de l'index : $0.11**

#### 1. Questions-réponses courantes - modèle texte

Q : Résume-moi le contenu central de cet article.

**Coût $0.01**

#### 2. Questions-réponses courantes - modèle vision

Q : Que décrit la Figure 1 ? Quelles couleurs ont été utilisées pour la réaliser ?

**Coût $0.02**

#### 3. Skill - Explication de formules - modèle texte

Q : Explique-moi la formule (1).

**Coût $0.03**

#### 4. Skill - Extraction d'informations clés - modèle texte

Q : Comment l'attention Multi-Head atténue-t-elle concrètement les limites de la représentation de l'information, et pourquoi est-elle plus efficace qu'une seule tête ?

**Coût $0.04**

#### 5. Skill - Comparaison d'articles - modèle texte

Q : Dans des scénarios à faibles ressources ou sensibles à la latence, quels sont les avantages ou inconvénients du Transformer par rapport aux modèles récurrents/convolutifs ?

**Coût $0.03**

#### 6. Skill - Extraction de données de tableaux - modèle texte

Q : Extrais-moi le contenu du Table 2.

**Coût $0.02**

#### 7. Skill - Extraction de données de tableaux - modèle vision

Q : Extrais-moi le contenu du Table 2.

**Coût $0.03**


## 📦 Dépendances du projet

| Dépendance | Version | Usage |
|------|------|------|
| Flask | >= 3.0 | Framework web |
| Flask-SocketIO | >= 5.3 | Communication WebSocket en temps réel |
| Flask-CORS | >= 4.0 | Prise en charge du cross-origin |
| openai | >= 1.0 | Appels d'API LLM / VLM |
| tiktoken | >= 0.5 | Comptage de tokens |
| PyMuPDF (fitz) | >= 1.23 | Rendu des pages PDF en images, extraction de texte |
| PyPDF2 | >= 3.0 | Extraction de texte PDF |
| python-dotenv | >= 1.0 | Chargement des variables d'environnement |
| PyYAML | >= 6.0 | Analyse des fichiers de configuration |


## 🙏 Remerciements

L'algorithme central d'indexation PageIndex de ce projet s'inspire du projet open source [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex).


## 📄 License

MIT License

---

<p align="center">
  Made with care for better document understanding
</p>
