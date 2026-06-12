# Étude : que reprendre de RAGFlow sans casser l'architecture ?

*Étude menée le 12/06/2026 sur https://github.com/infiniflow/ragflow (et son module
DeepDoc), à la lumière du travail déjà réalisé sur ce projet. Aucune implémentation
n'accompagne cette étude.*

## 1. Ce qu'est RAGFlow, en deux paragraphes

RAGFlow est un moteur RAG d'entreprise : ingestion multi-formats (Word, slides,
Excel, images, scans, pages web…), **parsing profond des documents** (module
DeepDoc), découpage par gabarits, indexation **vectorielle + plein texte**
(Elasticsearch/Infinity), reranking, GraphRAG, agents et workflows. Sa devise :
« *Quality in, quality out* » — la qualité du RAG se joue d'abord à l'ingestion.

Son infrastructure est lourde : Elasticsearch, MySQL, Redis, MinIO, modèles de
vision (OCR, reconnaissance de layout, reconnaissance de structure de tableaux),
le tout sous Docker/Kubernetes. C'est l'**antithèse de notre contrainte de
simplicité** et, sur le retrieval, l'antithèse de notre paradigme (similarité
vectorielle vs raisonnement sur l'arbre PageIndex).

## 2. Ce qu'il ne faut PAS reprendre (et pourquoi)

| Composant RAGFlow | Verdict | Raison |
|---|---|---|
| Base vectorielle, embeddings, reranking | ✘ | Conflit frontal avec le paradigme PageIndex (« vectorless ») qui est la raison d'être du projet |
| GraphRAG, RAPTOR | ✘ | L'arbre PageIndex EST déjà notre synthèse hiérarchique ; GraphRAG = infrastructure et complexité massives |
| Chunking par gabarits | ✘ | Notre « chunking » est l'arbre de structure — supérieur pour des documents structurés ; les gabarits RAGFlow compensent l'absence d'arbre |
| Workflows agents / sandbox / MCP | ✘ | Hors périmètre — on vient justement de *simplifier* l'agent |
| Infra (Elasticsearch, MinIO, Redis, MySQL) | ✘ | Le projet tient dans un Flask + fichiers ; c'est une qualité |

## 3. La leçon transposable : « Quality in, quality out »

Tout ce que RAGFlow investit dans DeepDoc part d'un constat que **notre propre
expérience confirme** : la majorité des défauts observés en aval viennent du
texte brut en amont. Inventaire de NOS symptômes constatés (sessions de travail
des 10-12/06), mis en regard de la réponse DeepDoc :

| Symptôme constaté chez nous | Cause amont | Réponse DeepDoc | Transposition « simple » possible |
|---|---|---|---|
| Mots coupés dans les réponses : « semai ne », « nov embre », « P a g e 8 \| 14 » | Extraction PyPDF2 médiocre | OCR + layout propres | **Passer l'extraction à PyMuPDF** (déjà installé, déjà supporté par `get_page_tokens(pdf_parser="PyMuPDF")` — il suffit de changer le défaut) |
| `verify_toc` répond « non » à tous les titres ; frontières de nœuds floues ; bruit dans les résumés | **En-têtes/pieds répétés** (« Page N \| 14 », cartouches ministériels) en tête de chaque page | Layout recognition classe Header/Footer et les écarte | **Détection des lignes répétées** sur N pages (heuristique pure Python, sans ML) et suppression avant indexation |
| Tableaux écrasés en texte plat (non constaté sur nos PDF de test, mais certain sur des pièces réelles : actes, relevés) | PyPDF2 ignore la structure | TSR (5 labels) + conversion en phrases | `page.find_tables()` de PyMuPDF → rendu Markdown dans le texte de page |
| **PDF scannés : invisibles** (limite n°1 documentée) | Pas de couche texte, pas d'OCR | OCR universel (modèles dédiés) | Deux voies « simples » : (a) OCR local léger (Tesseract/RapidOCR via PyMuPDF) ; (b) **transcription par notre modèle vision Ollama** (qwen3.6 supporte la vision) — cohérent avec l'architecture 100 % locale, zéro dépendance ML nouvelle |
| Conversions Word→PDF dégradées (cas « Dossier Théo » : sommaire faussé) | L'utilisateur convertit faute d'import .docx | Ingestion multi-formats native | Accepter le `.docx` à l'upload et le convertir en interne (texte par python-docx, ou PDF via LibreOffice headless si présent) — évite les conversions manuelles ratées |

**Point d'architecture décisif** : toutes ces transpositions se logent dans
**une seule fonction amont** — `get_page_tokens` (`pageindex/utils.py`) et son
voisinage immédiat — c'est-à-dire *avant* l'arbre. Rien ne change dans le
paradigme, l'agent, l'IHM ou les citations : on améliore la matière première
que PageIndex raisonne. C'est exactement la philosophie « quality in,
quality out », sans l'usine.

## 4. Une idée d'UX à retenir : l'humain dans la boucle d'indexation

RAGFlow met en avant la **visualisation des chunks avec intervention humaine**
avant indexation. Notre équivalent naturel, presque gratuit : rendre l'arbre
**éditable** depuis la modale « Structure » (corriger un titre, ajuster une
plage de pages, regénérer le résumé d'un nœud). Pour un dossier de procédure de
50 pièces, pouvoir corriger à la main « Document 2 » en « Note d'information
UEHC du 07/08/2023 » améliorerait directement le retrieval par raisonnement —
l'arbre étant l'index, c'est l'endroit le plus rentable où placer l'humain.

## 5. Ce que nous avons déjà et que RAGFlow n'a pas (à préserver)

- Le **retrieval par raisonnement** sur structure réelle du document (RAGFlow
  cite le chunk ; nous citons la *page* avec surlignage du passage dans le
  document affiché) ;
- la **traçabilité du raisonnement** (timeline de l'agent) ;
- la **vérification de l'arbre à l'indexation** (verify_toc + réparation) —
  RAGFlow n'audite pas ses chunks ;
- la légèreté : un venv, Ollama, zéro service externe.

## 6. Priorisation proposée (du plus rentable au plus optionnel)

| # | Amélioration | Effort | Risque | Impact attendu |
|---|---|---|---|---|
| 1 | Extraction PyMuPDF par défaut (au lieu de PyPDF2) | très faible (paramètre existant) | faible — à valider sur nos 2 docs de référence (réindexation comparative) | mots recollés, texte plus fidèle → meilleurs résumés, meilleure vérification |
| 2 | Suppression des en-têtes/pieds répétés (heuristique lignes identiques sur ≥ 60 % des pages) | faible (pur Python, dans `get_page_tokens`) | faible — garder les marqueurs `<page_N>` intacts | frontières de nœuds plus nettes, résumés sans bruit, `verify_toc` plus fiable |
| 3 | OCR de secours pour pages sans texte — via le modèle **vision** Ollama (transcription page→texte), activé seulement si la couche texte est vide | moyen | moyen (latence d'indexation sur scans ; qualité à évaluer) | lève la limite n°1 du projet ; 100 % local |
| 4 | Tableaux → Markdown via `find_tables()` PyMuPDF | moyen | moyen (faux positifs de détection) | pièces chiffrées exploitables (relevés, barèmes) |
| 5 | Import `.docx` direct | moyen | faible | supprime les conversions manuelles ratées (cas Théo) |
| 6 | Arbre éditable dans l'IHM (titres/résumés) | moyen+ | faible (endpoints existants à compléter) | l'humain améliore l'index là où il compte |

Les n° 1 et 2 sont de l'ordre de la journée et adressent des défauts *déjà
observés* sur vos documents réels. Les n° 3-6 sont des chantiers indépendants,
activables un par un, tous confinés à la couche d'ingestion ou à l'IHM.

## 7. Conclusion

RAGFlow ne nous apprend rien sur le retrieval (nos paradigmes sont
incompatibles, et c'est assumé) ; il nous apprend en revanche **où investir** :
la qualité du texte avant l'arbre. Sa réponse est industrielle (modèles de
vision, infrastructure) ; la nôtre peut rester artisanale (PyMuPDF, heuristique
d'en-têtes, OCR vision local) pour ~80 % du bénéfice et ~5 % de la complexité —
sans toucher ni au paradigme PageIndex, ni à l'agent, ni à l'IHM.
