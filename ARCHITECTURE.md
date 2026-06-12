# Architecture de POC Réponses Sourcées (PageIndex Chat UI)

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

1. **Upload** (`routes/api.py`) → fichier dans `uploads/`, fil d'indexation
   lancé (`_launch_indexing`, file séquentielle). Un import de **dossier**
   est possible (bouton « Importer un dossier ») : chaque fichier porte son
   répertoire d'origine (`Document.folder`), affiché en groupes dans la
   bibliothèque et cochable d'un bloc en Q-R.
2. **Cache de réimportation** : l'empreinte SHA-256 du PDF est comparée aux
   fichiers `<nom>.pdf.pageindex.json` du répertoire source
   (`SOURCE_DATA_DIR`, défaut `../data`). Correspondance → l'arbre est
   restauré tel quel, **aucun appel LLM**, document prêt en quelques
   secondes. Sinon :
3. **`services/indexing_service.py`** appelle **`pageindex.page_index_main`**
   (la bibliothèque) : extraction du texte (PyMuPDF + suppression des
   en-têtes/pieds répétés, OCR vision en repli), détection du sommaire
   (20 premières pages), construction de la table « titre → page physique »
   (3 stratégies selon présence/qualité du sommaire), **vérification LLM**
   de chaque entrée + réparation, hiérarchisation, identifiants de nœuds,
   texte balisé `<page_N>…</page_N>`, découpage des pages partagées,
   fusion des nœuds au texte identique, résumés par nœud. Échec → **deux
   tentatives automatiques** avant le statut erreur ; une pièce en erreur
   se relance d'un clic (« Relancer » → `POST /documents/<id>/retry`).
4. Résultat figé dans `results/documents/<id>/structure.json`, et copié à
   côté du PDF source (`.pageindex.json`) pour les réimportations futures.
5. **`rag_service.prepare_document`** : rendu JPEG des pages (visionneuse),
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

## Cycle de vie d'une question

`services/agent.py`, événement Socket.IO `agent_chat`. Trois voies selon le mode :

### Conversation libre (Q-R sans document) : le modèle NU

Une nouvelle conversation démarre **sans document sélectionné** ; les
questions posées dans cet état sont un dialogue direct avec le modèle de
rédaction. **Principe structurant : l'application ne doit pas dégrader le
modèle.** Hors documents, aucune instruction système, aucun style imposé,
aucune température forcée : la question part telle quelle, l'historique
comme vrais tours de dialogue — parité totale avec un chat Ollama direct.

Ce principe vient d'un cas réel documenté dans `DIAGNOSTIC-UEMO.md` : des
consignes de style anodines (« réponds uniquement à la question, aucune
digression ») suppriment le réflexe de doute du modèle et le font confabuler
sur des connaissances fragiles (acronymes métier). Les réponses libres ne
portent ni citations ni note de qualité — cette frontière est visible dans
l'IHM (« conversation libre (sans sources) »).

### Mode mono-document : la voie simple (canonique cookbook)

`_run_single_simple` reproduit `cookbook/pageindex_RAG_simple.ipynb` :
1. **Une** recherche par raisonnement sur l'arbre (`tree_search`, profil rapide) ;
2. lecture des nœuds retenus (≤ 10 nœuds, budget 60 000 caractères, chaque
   section préfixée de son identifiant réel `node_<id>`) ;
3. rédaction (profil texte) avec les règles de citation ; mode Vision : images
   des nœuds retenus + VLM (cookbook vision) ;
4. auto-évaluation en garde-fou : si score < 6, au plus **une** recherche
   complémentaire ciblée sur les manques puis une réécriture — pas de boucle.

Ni décomposition, ni boucle ReAct, ni planificateur : 2 à 4 appels LLM par
question, déroulé prévisible.

### Mode multi-documents (Q-R) : l'agent ReAct

Justifié par les corpus type dossier de procédure (des dizaines de pièces) où
la divulgation progressive est nécessaire :

1. **Décomposition** (profil rapide) : sous-questions si nécessaire.
2. **Boucle ReAct** (≤ 5 étapes/sous-question, profil rapide) — pilotée par
   **function calling natif** (outils déclarés via le paramètre `tools` de
   l'API, comme l'exemple officiel `agentic_vectorless_rag_demo.py` ; repli
   automatique sur le JSON texte pour les serveurs sans support) : le
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
   - *Déclenchement* : **conditionnel** — sautée quand la réponse est saine
     (substantielle, citée, sans fuite de syntaxe d'outil), la main revient
     immédiatement ; elle ne tourne que sur signe de faiblesse, avec le
     statut « Auto-vérification de la réponse… ». Chaque réponse documentée
     porte une **note de qualité calculée** (badge « Qualité estimée n/10 » —
     `_estimate_quality`, déterministe et sans LLM : longueur, présence de
     citations, nœuds cités ∈ sources, pages citées ∈ plages des nœuds,
     absence de fuite d'outil) qui guide l'utilisateur vers le bouton
     **« Vérifier la réponse »** (juge LLM à la demande,
     POST `/sessions/<id>/messages/<i>/verify`, verdict persisté dans le
     message, invalidé si la réponse est éditée). Les réponses libres (sans
     sources) n'ont ni note ni vérification.
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
| `text` | rédaction des réponses, conversation libre | nemotron-3-super |
| `light` | indexation + toutes les étapes internes de l'agent (hérite de `text` si absent) | gpt-oss-20b-128k |
| `vision` | réponses sur images de pages, OCR des pages scannées | qwen3.6 |

Tout serveur OpenAI-compatible fonctionne (Ollama, vLLM, LM Studio…) : URL de
base personnalisée, clé factice injectée si absente.

**Aucune température n'est imposée** : chaque modèle tourne avec les réglages
de son Modelfile (recommandations de l'éditeur — ex. NVIDIA prescrit
temp 1 / top_p 0.95 pour Nemotron). Forcer temp 0 dégradait les modèles à
raisonnement (cf. `DIAGNOSTIC-UEMO.md`) ; en contrepartie, les réponses ne
sont pas reproductibles à l'identique d'une exécution à l'autre — les
garde-fous structurels (note de qualité, vérification des pages citées)
prennent le relais.

## Modifications locales apportées à la bibliothèque `pageindex/`

L'indexation repose **exclusivement** sur la bibliothèque embarquée
(`page_index_main` est l'unique constructeur d'arbre) ; tout le reste du
projet orchestre *autour* (file, retry, cache) sans jamais construire
d'index autrement. Le dossier `pageindex/` est une copie de l'amont
[VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex) — un fork de
fait : les évolutions amont devront être fusionnées manuellement, et
plusieurs de nos correctifs génériques (3, 9, 10 ci-dessous, OCR de repli)
seraient de bons candidats à une contribution amont. Le paradigme (arbre par
raisonnement LLM, prompts canoniques du cookbook) n'est jamais modifié.
Ajustements locaux (« quality in, quality out », cf. ETUDE-RAGFLOW.md) :
1. **extraction PyMuPDF par défaut** (PyPDF2 coupait les mots : « semai ne »,
   « nov embre ») et **suppression des en-têtes/pieds répétés** avant
   indexation (heuristique de lignes identiques en haut/bas de page,
   chiffres normalisés — `strip_repeated_page_furniture`) ;
2. texte des nœuds balisé `<page_N>` (citations à la page près) ;
3. **découpage des pages de frontière partagées** entre deux nœuds
   (`split_shared_boundary_pages`) : quand une pièce finit au milieu d'une
   page où la suivante commence, chaque nœud ne garde que SA part du texte —
   fin des contaminations croisées (résumés, sélection, réponses) ;
4. résumés de nœuds « identitaires » (nature, auteur, destinataire, date —
   voir plus haut) et dans la langue du document, titres jamais traduits ;
5. garde-fou dans la génération de structure : les pages viennent des
   balises `<physical_index_X>` où le contenu commence réellement, jamais
   d'une liste/sommaire interne au document (pagination souvent périmée
   après conversion Word→PDF) ;
6. contournement de l'heuristique de couverture de `verify_toc` + réparation
   en dernier recours (documents à long chapitre final, sommaires périmés) ;
7. timeout explicite de 180 s sur les clients LLM (une requête perdue se
   relance en 3 min au lieu de bloquer 10 min) ;
8. tokenizer avec repli `o200k_base` pour les noms de modèles non-OpenAI ;
9. **fusion des nœuds au texte identique au parent**
   (`merge_redundant_children`, avant les résumés) : le sur-découpage d'une
   même page (un PV d'une page découpé en 5 nœuds au même texte) coûtait un
   résumé LLM par nœud et rendait les surlignages ambigus ;
10. **aucune température imposée** dans les appels LLM de la bibliothèque
    (réglages du Modelfile de chaque modèle).

## Dimensionnement multi-documents (dossiers de procédure)

Validé sur un corpus simulé de 52 pièces (`tests/make_corpus_50_pieces.py`) :
- l'inventaire des pièces transmis au planificateur est plafonné à 24 000
  caractères (≈ 70-80 pièces avec résumés identitaires) ;
- `cross_search` est plafonné à 12 documents par appel (un appel LLM par
  document) avec message invitant l'agent à cibler via `list_documents` ;
- les indexations d'un import par lot s'exécutent en **file séquentielle**
  (un document à la fois, les autres « en file d'attente ») ;
- les **`.docx` sont acceptés à l'import** (conversion interne en PDF par
  LibreOffice headless — évite les exports manuels approximatifs) ;
- l'**arbre est éditable** depuis la modale « Structure » (✏ sur chaque
  nœud : titre et résumé) — l'arbre étant l'index de recherche, c'est le
  levier d'intervention humaine le plus rentable.

## Style des réponses

`STYLE_INSTRUCTION` (prompts de rédaction uniquement) : prose continue collée
à la question — pas de puces, tableaux, titres ni gras, **sauf demande
explicite de l'utilisateur ou trame fournie** ; citations `(node_<id>,
page N)` et guillemets de citation toujours obligatoires. Le raisonnement
interne (planificateur, réflexion) garde ses formats structurés.

## Limites connues

- ~~Pas d'OCR~~ : les pages sans couche texte sont **transcrites par le
  modèle vision** configuré (profil « vision », ex. qwen3.6 local) au moment
  de l'extraction ; si aucun modèle vision n'est utilisable, comportement
  antérieur (page vide).
- La détection de sommaire ne balaie que les 20 premières pages (les tables en
  fin d'ouvrage, usage français, sont ignorées — le mode « sans sommaire »
  compense).
- L'indexation est non déterministe (LLM) : deux imports du même document
  peuvent produire des arbres légèrement différents.
- La précision des citations dépend de la discipline du modèle rédacteur ;
  l'IHM tolère les écarts de format mais ne peut pas inventer une page absente.
- Le déclencheur de l'OCR vision exige une couche texte quasi vide
  (< 20 caractères) : un scan portant quelques champs de formulaire passe
  au travers et échoue (« Processing failed ») — correctif identifié
  (déclencher aussi sur image + texte < ~200 caractères).
- Les réponses ne sont pas reproductibles à l'identique (températures des
  Modelfiles) : les évaluations factuelles se font sur plusieurs tirages,
  jamais sur une exécution isolée (cf. `DIAGNOSTIC-UEMO.md`).
