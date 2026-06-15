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

> **Note (voie corpus)** : depuis le passage à la **voie corpus** en mode
> multi-documents (cf. « Mode multi-documents : la voie corpus »), le retrieval
> ne passe plus par les outils du registre (`cross_search`, `read_node`,
> `list_documents`…) mais par un `tree_search` sur les fiches de pièces. Le
> tableau ci-dessous décrit les briques canoniques ; plusieurs sont désormais
> **dormantes** (conservées, réactivables via `USE_CORPUS_SIMPLE = False`).

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

La construction de la structure (sommaire, arbre) utilise le profil
**« rapide »** (`light`, configurable via l'onglet « Modèle rapide ») ; les
résumés de nœuds — l'index de recherche — sont au contraire confiés au profil
**« texte »** (plus fiable sur les relations auteur/destinataire). C'est le
**seul** moment où le profil `light` est employé : tout le reste tourne sur
`text` (voir « Configuration des modèles »). Si une indexation est interrompue
par un redémarrage du serveur, le document est récupéré en statut « erreur »
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
1. **Une** recherche par raisonnement sur l'arbre (`tree_search`, profil texte) ;
2. lecture des nœuds retenus (≤ 10 nœuds, budget 60 000 caractères, chaque
   section préfixée de son identifiant réel `node_<id>`) ;
3. rédaction (profil texte) avec les règles de citation ; mode Vision : images
   des nœuds retenus + VLM (cookbook vision) ;
4. auto-évaluation en garde-fou : si score < 6, au plus **une** recherche
   complémentaire ciblée sur les manques puis une réécriture — pas de boucle.

Ni décomposition, ni boucle ReAct, ni planificateur : 2 à 4 appels LLM par
question, déroulé prévisible.

### Mode multi-documents (Q-R) : la voie corpus

Le dossier est traité comme **un seul arbre PageIndex** (« le dossier est
l'arbre, les pièces sont les nœuds, les fiches les résumés »).
`_run_corpus_simple` (mode kb, ≥ 2 pièces), profil texte :

1. **Une** recherche par raisonnement sur les **fiches de toutes les pièces**
   (un `tree_search` sur l'inventaire ; alias courts `p0/p1…` pour éviter les
   collisions d'identifiants entre arbres) → les pièces pertinentes (≤ 12 lues,
   `CORPUS_MAX_PIECES_READ`). Remplace l'ancien `cross_search` (un appel LLM
   par pièce) par **un seul** appel sur l'inventaire.
2. **Lecture** des pièces retenues. Une pièce **composite volumineuse**
   (> `CORPUS_PIECE_DRILL_THRESHOLD = 20 000` car.) est sélectionnée section par
   section (`tree_search` interne — *hiérarchie niveau 2*) au lieu d'être lue en
   entier ; une pièce courte est lue telle quelle.
3. **Rédaction** (profil texte) avec l'**inventaire complet** des fiches en appui
   (toute pièce reste citable même non lue) + citations
   `(doc: <fichier>, node_<id>, page N)`.
4. **Auto-évaluation** conditionnelle (commune aux voies, voir ci-dessous).

**Synthèse globale par défaut** — quand la question est une demande de synthèse
d'ensemble (`_is_global_summary` : « synthèse / résumé **du dossier** », « vue
d'ensemble »… ; les questions ciblées comme « résumé des faits reprochés »
restent sur la voie normale), `_run_global_summary` court-circuite la recherche
et rédige une **vue transversale** directement sur les fiches de toutes les
pièces (le « map » par pièce est amorti à l'indexation). Citations au niveau
pièce (nœud racine + page de début).

Voies mono-document et corpus partagent l'**auto-évaluation** (« réflexion »,
profil texte) — encart « Auto-vérification n/10 » de l'IHM :
- *Déclenchement* **conditionnel** : sautée quand la réponse est saine
  (substantielle, citée, sans fuite d'outil). Chaque réponse documentée porte
  une **note de qualité calculée** (`_estimate_quality`, déterministe, sans LLM :
  citations présentes, nœuds cités ∈ sources, pages ∈ plages des nœuds, pénalité
  des citations dégénérées « source » / 【】) qui guide vers le bouton
  **« Vérifier la réponse »** (juge LLM à la demande,
  POST `/sessions/<id>/messages/<i>/verify`, verdict persisté, invalidé à
  l'édition). Les réponses libres (sans sources) n'ont ni note ni vérification.
- *Mécanique* (`DocumentAgent.reflect`) : un appel LLM juge la réponse contre le
  contexte fourni (répond-elle, étayée, contradictions, manques) → JSON
  `{score, issues, missing_info, action}`.

L'ancienne **boucle ReAct + `cross_search`** (décomposition, outils du registre,
retry par boucle d'outils) est **conservée mais dormante** (réactivable via
`USE_CORPUS_SIMPLE = False`) : sur Ollama, `cross_search` émettait un appel LLM
par pièce, sérialisé → une étape > 3 min sur Nemotron, budget de temps épuisé
avant la rédaction.

Persistance dans la session (`models/session.py`, `results/_sessions/`).

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
| `text` | rédaction, conversation libre **ET toutes les étapes internes de l'agent** (décomposition, ReAct, `tree_search` au runtime, réflexion, analyse) + résumés de nœuds à l'indexation | nemotron-3-super |
| `light` | **indexation initiale uniquement** : construction de la structure de l'arbre (hérite de `text` si absent) | gpt-oss-20b-128k |
| `vision` | réponses sur images de pages, OCR des pages scannées | qwen3.6 |

**Pourquoi l'agent tourne entièrement sur `text` et non sur `light`** :
décision délibérée liée à Ollama, où alterner entre deux modèles force un
rechargement VRAM (décharge/charge) à *chaque* étape — coût prohibitif sur la
boucle de l'agent. L'indexation, elle, est un long lot homogène : le seul swap
vers `light` y est amorti. Le paramètre `model_type` propagé dans les méthodes
de l'agent ne route donc plus le profil interne (vestigial) ; il ne sert qu'à
basculer texte/vision sur la rédaction finale.

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
- la voie corpus lit ≤ 12 pièces en intégral par réponse
  (`CORPUS_MAX_PIECES_READ`), le reste du dossier restant citable via
  l'inventaire complet des fiches ;
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

- **Synthèse globale = niveau « fiches »** : elle dégage la structure et les
  thèmes du dossier mais ne restitue pas le détail factuel fin de chaque pièce
  (le texte intégral de toutes les pièces ne tient pas dans le contexte — 145 k
  car. pour 26 pièces vs budget 60 k). Le levier de qualité est la richesse des
  fiches (prompt `generate_node_summary`). De plus, sous la pression du
  grounding (« cite chaque affirmation »), le modèle tend encore à **énumérer**
  les pièces par catégorie plutôt qu'à les fondre en une vraie synthèse
  transversale — l'instruction de prompt seule n'y suffit pas toujours.
- **Sélection hiérarchique tributaire de la fiche racine** : au niveau 1, une
  pièce composite est jugée sur le résumé de son **nœud racine**. Si ce résumé
  ne reflète pas le contenu profond (cas réel : un en-tête ministériel pour un
  sujet de concours), la pièce est **ratée** et donc jamais sélectionnée ni
  « drillée » (niveau 2). Correctif identifié, non implémenté : enrichir la
  fiche de niveau 1 avec les titres/résumés des sous-sections.
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
- Les textes des nœuds d'une même page s'emboîtent (le découpage des
  frontières ne coupe que la fin, pas le début) : l'attribution des
  surlignages choisit le nœud englobant le plus spécifique, mais un bloc
  PyMuPDF chevauchant deux sections n'est surligné nulle part.
- Les réponses ne sont pas reproductibles à l'identique (températures des
  Modelfiles) : les évaluations factuelles se font sur plusieurs tirages,
  jamais sur une exécution isolée (cf. `DIAGNOSTIC-UEMO.md`).
