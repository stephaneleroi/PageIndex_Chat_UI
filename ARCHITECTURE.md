# Architecture — PageIndex Chat UI (Réponses documentaires sourcées)

> Application de **questions-réponses sur documents, sourcées et 100 % locales**
> (Ollama), bâtie **au-dessus** de la bibliothèque [PageIndex](https://github.com/VectifyAI/PageIndex).
> Ce document est la **référence interne**. Chaque affirmation renvoie au code
> (`fichier — fonction()`), pour qu'on puisse toujours vérifier.

**Plan.** 1. Modèle mental · 2. Vocabulaire · 3. **PageIndex vs notre couche** ·
4. Indexation (à froid) · 5. **La sélection : `tree_search`** · 6. Les briques de
réponse · 7. Routing & matrice voie×brique · 8. Les voies en détail · 9. Citations,
visionneuse, garde-fous · 10. **Vérification des réponses** · 11. Notes & annotations ·
12. Modèles & config · 13. Fork `pageindex/` · 14. Limites & études.

---

## 1. Le modèle mental

### 1.1 Le principe (en 30 secondes)

1. **Indexer** : un PDF devient un **arbre** (sa table des matières — reprise des
   **signets** du PDF si présents, sinon reconstruite, §4.1), puis on calcule **une
   fiche d'identité par « pièce »** (résumé structuré : nature, auteur, destinataire,
   faits saillants…). **Une seule fiche par pièce, jamais par nœud** ; selon la
   **nature détectée** du fichier (`is_compilation`, §4.3), elle est construite de
   **deux manières** :
   - **dossier de pièces indépendantes** (défaut) → chaque fiche **isolée**, pièce par
     pièce (anti-contamination) ;
   - **document unique à plan cohérent** (chapitres/parties) → fiches **cumulatives** :
     chaque section est résumée avec, **en contexte, les fiches des sections
     précédentes** (continuité du fil).

   *(Les deux produisent le même objet — une fiche par pièce ; seul le mode de
   construction change. La voie « synthèse globale » à la requête se contente ensuite
   d'**agréger** ces fiches déjà construites — §1.3, §8.3.)*
2. **Répondre** en **deux temps** :
   - **CHOISIR** où regarder — un LLM **raisonne sur les fiches + titres** de
     l'arbre (jamais sur le texte intégral) pour retenir les bons nœuds : c'est
     `tree_search`.
   - **LIRE puis RÉDIGER** — on charge le **texte** des seuls nœuds retenus et on
     rédige une réponse **citée à la page**.
3. Pas de base vectorielle, pas d'embeddings : on **navigue dans une carte du
   document par raisonnement**, comme un greffier qui feuillette un dossier.

**Conséquence fondatrice — la qualité de la fiche EST la qualité du retrieval.**
Comme le *choix* se fait sur les fiches, **une fiche pauvre rend une pièce
invisible**. Cas réel : « résume la note de M. X au juge Y » restait introuvable
parce que la fiche ne portait ni auteur, ni destinataire, ni nature. Le correctif
**conforme** n'a pas été d'ajouter une recherche plein-texte, mais d'**enrichir la
fiche** (§4.3). *Quand une pièce est ratée, on améliore l'arbre — on ne contourne
jamais le paradigme.*

### 1.2 Trois mots à connaître (détaillés en §2)

- **Pièce** — un **document logique** (une audition, une note, un rapport, un
  chapitre…) = un **nœud de premier niveau** de l'arbre. C'est l'**unité de
  travail** : on sélectionne, lit et cite *par pièce*. Un fichier peut contenir
  **une** pièce (un PV) ou **plusieurs** (un PDF « dossier ») ; et **un répertoire
  de fichiers est, lui aussi, un dossier de pièces**.
- **Fiche (d'identité)** — le **résumé structuré d'une pièce** (nature, auteur,
  destinataire, personnes, objet, points saillants — chaque fait suivi de sa page).
- **`tree_search`** — l'étape « **choisir** » : un LLM lit les **fiches + titres**
  (jamais le texte) et renvoie la liste des nœuds pertinents.

### 1.3 Les quatre voies de réponse (survol — détail en §7-8)

Selon la question, l'app emprunte **automatiquement** (routing, §7) **une** voie :

| Voie | Quand | Comment (en bref) |
|---|---|---|
| **Conversation libre** | aucun document | modèle **nu**, sans sources |
| **Mono-pièce** | une pièce visée (intention `detail`) | `tree_search` dans la pièce → **lecture du texte** |
| **Synthèse globale** | « vue d'ensemble » (intention `overview`) | **agrège les fiches**, sans lire le texte |
| **Voie corpus** | un **dossier de ≥ 2 pièces** (intention `detail`) | `tree_search` choisit des pièces **sur leurs fiches** → **lecture de leur texte** (ou **map-reduce** si le volume déborde) ; les fiches de **toutes** les pièces restent jointes **« en appui » (mode inventaire)** pour rester citables |

> Les termes employés partout dans la suite — **voie corpus**, **inventaire**,
> **map-reduce**, intentions **`overview` / `detail`** — sont posés ici en survol,
> puis détaillés en **§5** (sélection), **§7** (routing) et **§8** (voies). Garde
> cette table en tête : elle rend le reste du document lisible d'une traite.

---

## 2. Vocabulaire (à lire avant tout le reste)

```
        DOCUMENT (un PDF / .docx importé)
             │  indexation PageIndex
             ▼
          ARBRE de NŒUDS  (≈ table des matières)
             │
   ┌─────────┴───────────┐
   ▼                     ▼
 PIÈCE (nœud niv. 1)    PIÈCE (nœud niv. 1)
   │  + 1 FICHE          │  + 1 FICHE
   ├─ nœud (section)     ├─ nœud (section)
   └─ nœud (sous-sect.)  └─ …
```

- **Nœud** — unité de l'arbre (`node_id`, ex. `node_0006`) : un *titre*, un *texte*
  (les pages, balisées `<page_N>…</page_N>`), une *plage de pages*. `N` = **page
  physique du PDF** (index PyMuPDF) : citations `(p. N)` et visionneuse partagent
  cette numérotation (le clic ouvre la page N), qui peut différer du **folio
  imprimé** ; l'IHM l'explicite (« Page N du PDF »).

- **Pièce** — **un nœud de premier niveau** (tête **+ tout son sous-arbre**) = **un
  document logique** (une audition, une note, un rapport, un chapitre…). C'est
  **l'unité de travail** : on sélectionne, résume, lit et cite *à la granularité de
  la pièce* (`USE_PIECE_UNIT = True`). Détection **déterministe**
  (`pageindex/utils.py — piece_head_nodes()`) :

  | Forme de l'arbre | Pièces |
  |---|---|
  | ≥ 2 racines | chaque racine est une pièce |
  | 1 racine dont des enfants sont **numérotés** (regex `^\s*(?:document\|pièce\|annexe\|rapport)\s`) | chaque enfant numéroté est une pièce |
  | sinon | le document entier = 1 pièce |

  Un **fichier** contient donc **une** pièce (un PV isolé) ou **plusieurs** (un PDF
  « dossier ») :
  ```
  Cas A — dossier de FICHIERS séparés (Procedure-PN-1 : 25 PDF) → 25 arbres → 25 pièces
  Cas B — FICHIER composite (Dossier Théo : 1 PDF) → 1 arbre →
            ├─ « Document 1 — rapport éducatif »   → PIÈCE
            └─ « Document 2 — Note d'information »  → PIÈCE … (5 pièces)
  ```
  *Pourquoi cette granularité ?* Traiter chaque document logique séparément (citer
  la bonne pièce) et **éviter la contamination** entre pièces voisines d'un fichier.

- **Fiche d'identité** (= « fiche » = **résumé d'une pièce** — synonymes). **Une
  seule** par pièce, format **structuré** (`pageindex/utils.py —
  generate_summaries_for_structure()`) :
  ```
  Nature        : type de pièce (lettre, note, audition, ordonnance, rapport, chapitre…)
  Auteur        : qui l'a écrite/signée (rôle, service)
  Destinataire  : à qui elle s'adresse
  Date et heure : date de la pièce
  Personnes     : chaque personne nommée + son rôle (mis en cause, victime, témoin…)
  Objet         : une phrase — à quoi sert cette pièce
  Points saillants : 2 à 4 phrases, faits clés, CHACUN suivi de sa page « (p. N) »
  ```
  Elle a **deux rôles** : (a) **informer** (survol) et (b) servir de **support de
  sélection** — *c'est sur les fiches que `tree_search` raisonne* (§5). Les `(p. N)`
  rendent **citable** toute réponse bâtie sur les seules fiches.

  > **`(p. N)` ≠ `<page_N>` — ne pas confondre.** `<page_N>…</page_N>` est le
  > **balisage technique** du texte source (§2, *Nœud*), jamais montré ; le prompt
  > de fiche **interdit** de le recopier. `(p. N)` en est la **traduction lisible
  > et citable** : le modèle lit la page dans le marqueur englobant et l'écrit
  > `(p. N)` après chaque fait des *Points saillants*. C'est un contenu **destiné à
  > être lu** (affiché en Vue Structure, repris comme citation par la synthèse
  > globale) — pas une scorie technique. *(Forme effective parfois `(p.1)` sans
  > espace : le parseur IHM `CITE_RE` tolère ces variantes, §9.1.)*

- **`node_map`** — table calculée à la préparation (nœud → plage de pages, texte,
  bbox de surlignage). Sert aux citations et à la visionneuse.

### 2.1 Profondeur de l'arbre = échelle (pas un autre niveau de fiches)

Une pièce peut être un **nœud unique** (petit document) ou un **sous-arbre profond**
(sections). La profondeur ne sert qu'à **naviguer dans les gros documents** :

```
niveau 1 (entre pièces)  : tree_search sur les FICHES        → quelle PIÈCE ?
niveau 2 (dans une pièce): tree_search sur les TITRES sections → quelles SECTIONS ?
```

Important : on **résume par pièce** (§4.3), donc **seul le nœud de tête porte une
fiche** ; ses sous-nœuds n'ont que leur **titre**. Le niveau 2 raisonne donc sur les
**titres de sections** (+ la fiche de tête en contexte). Petites pièces (≤
`SMALL_DOC_MAX_PAGES = 4`) = un seul nœud, pas de profondeur.

### 2.2 Où servent les fiches (récapitulatif)

La fiche d'une pièce sert à **quatre endroits** — à garder en tête, car « fiche pauvre
= pièce ratée » se répercute partout :

| # | Où | Ce que la fiche y fait | Réf. |
|---|---|---|---|
| 1 | **Sélection** (`tree_search` niveau 1) | c'est **sur les fiches** que le LLM choisit les pièces (titres + fiches, **jamais** le texte) ; au niveau 2, la fiche de tête sert de contexte | §5 |
| 2 | **Synthèse globale** (`overview`) | on **agrège les fiches** et on rédige dessus, **sans lire le texte** | §8.3 |
| 3 | **Inventaire en appui** (voie corpus `detail`) | voir l'encadré ci-dessous | §8.4 |
| 4 | **Affichage IHM** | Vue Structure + structure consolidée de dossier (`renderFiche`) | §11–11.1 |

*(Le **régime** cumulatif/isolé des fiches, lui, est décidé en amont sur les **titres**
des têtes — pas sur les fiches : voir `is_compilation`, §4.3.)*

> **Le « mode inventaire » (point 3) — à bien comprendre.** Dans la voie **corpus**
> (`detail`, ≥ 2 pièces), `tree_search` ne retient que **quelques** pièces dont on
> lit le **texte**. Mais **en plus** de ce texte, on **joint au contexte de
> rédaction la fiche de TOUTES les pièces du dossier** (`_build_corpus_inventory`,
> budget `CORPUS_INVENTORY_BUDGET`). *Pourquoi :* qu'une pièce **non lue** reste
> **citable** et que le rédacteur garde la vue d'ensemble. Cet inventaire est joint
> dans **les deux sous-cas** de la voie corpus — **lecture directe** ET
> **map-reduce**. C'est donc un usage des fiches **distinct** de la synthèse globale
> (§8.3) : là on n'a *que* les fiches ; ici on lit du **texte** ET on a les fiches
> **en appui**.

> **Ne pas confondre avec le résumé *par document*.** Le **routing**
> (`decompose_query`) et le léger `docs_overview` des prompts s'appuient sur le
> **résumé global du document** (`analysis.json`, via `_build_docs_overview`),
> **pas** sur les fiches de pièces — deux sources de résumé distinctes (niveau
> document vs niveau pièce).

---

## 3. PageIndex (amont) **vs notre couche** — qui fait quoi

Frontière nette : **PageIndex construit l'arbre et le fouille (`tree_search`)** ;
tout le reste — **pièce, fiche identitaire, routing, voies, map-reduce, citations à
la page, notes** — est **notre couche** par-dessus (`services/`, `models/`, IHM).

| Brique | PageIndex (`pageindex/`) | Notre couche |
|---|---|---|
| PDF → arbre de nœuds (sommaire, hiérarchie, `node_id`) | **✅ cœur** | retouches d'extraction (§13) |
| Résumé d'un **nœud** | ✅ prompt canonique… | …**remplacé par une FICHE par PIÈCE** (`generate_summaries_for_structure`) |
| Notion de **pièce** (unité de travail) | ✘ (ne connaît que des nœuds) | **✅** `piece_head_nodes`, régime compilation/doc unique |
| **`tree_search`** (choisir des nœuds sur résumés/titres) | **✅ prompt du cookbook** | on **l'appelle** (niveau 1 sur fiches / niveau 2 sur sections) |
| `remove_fields(tree, ['text'])` (raisonner sans le texte) | ✅ | on l'utilise |
| **Citations à la page** (`<page_N>`, pastilles, visionneuse) | ✘ | **✅** |
| **Routing** (`decompose_query` : intention + `instructions`) | ✘ | **✅** |
| **Les 4 voies** (libre / mono-pièce / synthèse globale / corpus) | ✘ | **✅** `DocumentAgent` |
| **Map-reduce ciblé** + **fiches à chaud** persistées | ✘ | **✅** `_focused_summary` |
| **IDs de citation autorisés**, **pré-détection + vérification ciblée** (§10), **notes** | ✘ | **✅** |

### 3.1 Couches & fichiers

```
┌── IHM (navigateur) ──────── templates/index.html · static/js/app.js · static/css/app.css
├── Serveur ───────────────── app.py / main.py · routes/api.py (REST) · routes/socket_handlers.py (chat)
├── Application (LE CŒUR) ─── services/
│     · agent.py           → DocumentAgent : routing + 4 voies (§7-8)
│     · rag_service.py     → PageIndexService (tree_search, LLM/VLM) + RAGService
│     · indexing_service.py→ index_pdf : pilote l'indexation
│     · prompt_templates.py + prompts/*.jinja → prompts itérés/évalués (§3.2)
│     · skill_manager.py   → skills Markdown injectables
│   models/
│     · document.py        → Document / DocumentStore (arbre, node_map, images, NOTES, FICHES à chaud)
│     · session.py         → ChatSession / Message / SessionStore
├── Bibliothèque ──────────── pageindex/ (fork amont) : page_index.py, utils.py
└── Données (gitignored) ──── uploads/ · results/documents/<id>/{structure.json, images, notes.json, focused_fiches.json}
```

Le retrieval **ne passe plus** par un registre d'outils ni une boucle ReAct
(supprimés) : les voies appellent directement `tree_search` puis la lecture des nœuds.

### 3.2 Prompts externalisés (gabarits Jinja)

Les prompts qu'on **itère et évalue** vivent dans `services/prompts/*.jinja`, chargés
par `prompt_templates.render_prompt(name, **kw)` (Jinja `StrictUndefined` : variable
manquante = erreur). On édite **le gabarit**, pas une chaîne inline (diff lisible,
A/B simple) :

| Gabarit | Rôle | Règles clés |
|---|---|---|
| `grounding_single.jinja` | rédaction voie mono-pièce | citer `(node_<id>, page N)` (id réel) ; pas d'inversion de rôle ; dire si le contexte ne couvre pas |
| `grounding_kb.jinja` | rédaction voie corpus | citer `(doc, node_<id>, page N)` ; **pas d'affirmation d'exhaustivité/absence** ; **guillemets = verbatim exact** |
| `grounding_summary.jinja` | rédaction synthèse globale | citer **par thème** (pas par phrase) ; regrouper plusieurs pièces sous une citation |
| `decompose.jinja` | routing | sortie JSON `{needs_decomposition, items:[{question, intent, instructions}]}` |
| `focused_summary.jinja` | *map* du map-reduce | **chaque fait suivi de `(p. N)`** ; jamais deviner une page ; « (rien) » si la pièce n'apporte rien |

Les builders à flot de contrôle (`agent.py — _build_answer_prompt`, `_build_allowed_citations`…)
restent en Python et **interpolent** ces gabarits.

Les **trois gabarits grounding** portent une règle commune ajoutée après le test T8 :
**réfuter les présupposés faux** — ne pas désigner une entité/un rôle/une date *présupposé(e)
par la question* mais **non établi(e)** par les pièces (ex. « le mineur » alors que toutes les
personnes sont « Majeur ») ; l'expliciter au lieu d'en inventer un (cf. §10).

---

## 4. Indexation — la phase « à FROID »

Une fois par document, à l'import. Produit l'arbre **+** les fiches, **persistés**.
Fiches **« à froid »** = calculées une fois, figées, **neutres** (indépendantes de
toute question) — par opposition aux fiches **« à chaud »** du map-reduce (§8.4).

### 4.1 De l'upload à l'arbre (`routes/api.py` → `indexing_service` → `pageindex`)

1. **Upload** (`routes/api.py — upload_document()`) : PDF/DOCX accepté ; un **`.docx`**
   est converti en PDF (`_convert_to_pdf_with_libreoffice()`, `soffice --headless`).
   Indexation **séquentielle** : un seul document à la fois (`_INDEXING_GATE =
   Semaphore(1)`).
   - **`doc_id` STABLE, dérivé du contenu** : `doc_id = SHA-256(pdf)[:16]` (le PDF est
     d'abord sauvé en temporaire, converti si `.docx`, puis empreint). Réimporter **le
     même PDF redonne le même `doc_id`** → **réimport idempotent** (si le document existe
     déjà, on le réutilise, sans doublon ni réindexation). *Pourquoi :* une session de chat
     fige le `doc_id` des pièces citées (`doc_ids`, `doc_id::node`) ; un `doc_id` horodaté
     (ancien schéma) rendait les conversations **orphelines** après un supprimer/réimporter.
     Le scan de récupération lit le `doc_id` dans `metadata.json` (pas le nom de
     répertoire), donc un id non horodaté est sans impact.
2. **Cache de réimportation SHA-256** (`routes/api.py — _find_cached_index()` /
   `_sha256_file()`) : si un fichier `<nom>.pdf.pageindex.json` (à côté du PDF source,
   `SOURCE_DATA_DIR`, défaut `../data`) a un champ `pdf_sha256` égal à l'empreinte du
   PDF **et** une `structure` → arbre **restauré sans aucun appel LLM**. Sinon, après
   indexation, le résultat y est **réécrit** (`{pdf_sha256, page_count, structure}`).
3. **Construction de l'arbre** (`indexing_service.index_pdf()` →
   `pageindex.page_index_main()`, code dans `pageindex/page_index.py —
   page_index_builder()`). C'est l'étape la plus riche : elle **mêle des passes
   déterministes** (extraction, signets, balisage, fusion) **et des appels LLM** (un
   pour la segmentation, parfois une cascade pour le sommaire, N pour les fiches). Le
   détail des étapes — **et de ce qui est reproductible ou non** — est en **§4.1.1**.
4. **Résumé par pièce** (§4.3) — fait partie de la construction, détaillé à part car
   c'est lui qui porte la valeur du retrieval.
5. **Préparation** (`rag_service.prepare_document()`) : rendu JPEG des pages,
   `node_map`, surlignages (bbox) ; statut `ready`. Tout est écrit dans
   `results/documents/<id>/structure.json`.

### 4.1.1 La construction de l'arbre, étape par étape (déterministe vs non)

Tout se joue dans `page_index_builder()`. Lire ce schéma de haut en bas = lire le
code dans l'ordre. **`◆ déterministe`** = même PDF → même résultat, aucun LLM ;
**`◇ LLM`** = appel au modèle, donc **non reproductible** (température Modelfile).

```
PDF
 │
 ▼  ÉTAPE A — Extraction du texte des pages      get_page_tokens()        ◆ (+◇ si scan)
 │     · PyMuPDF page.get_text() page par page                            ◆
 │     · strip_repeated_page_furniture() : retire en-têtes/pieds RÉPÉTÉS  ◆
 │       (même ligne, chiffres normalisés, dans ≥60 % des pages)
 │     · page scannée (< 20 car., ou image + texte squelettique < 200) :
 │       OCR de SECOURS par le modèle vision                              ◇  ← seul LLM de l'étape
 │   ⇒ page_list = [(texte, nb_tokens)] par page
 │
 ▼  ÉTAPE B — Pré-segmentation en PIÈCES          segment_pieces()        ◇  UN appel LLM
 │     · « ce PDF réunit-il plusieurs documents ? sur quelles pages
 │       commence un NOUVEAU document ? » (on n'envoie que les premières
 │       lignes de chaque page, pas le texte intégral)
 │     · CONSERVATEUR : doute / échec / un seul document → 1 pièce
 │   ⇒ frontières [(start, end, titre)]  (1 seule ⇒ document simple)
 │
 ▼  ÉTAPE C — Arbre INTERNE de CHAQUE pièce       (3 cas mutuellement exclusifs)
 │     ├─ pièce ≤ SMALL_DOC_MAX_PAGES (=4)  → 1 seul nœud, AUCUNE détection ◆
 │     ├─ signets PDF présents (get_toc())  → tree_from_bookmarks()        ◆  gratuit, ~2 ms
 │     │     l'arbre EST la table des matières intégrée au PDF
 │     └─ sinon                              → tree_parser()               ◇  cascade LLM
 │           1. check_toc : y a-t-il un sommaire ? (20 PREMIÈRES pages)    ◇
 │           2. table « titre → page physique »                           ◇
 │           3. vérification + réparation  fix_incorrect_toc_with_retries ◇  (3 tentatives)
 │           4. hiérarchie (post_processing, list_to_tree)                ◆
 │   ⇒ structure : liste de nœuds {title, start_index, end_index, nodes}
 │
 ▼  ÉTAPE D — Finition commune (TOUS les cas ci-dessus)                    ◆  tout déterministe
 │     · write_node_id        → node_id 0000, 0001…
 │     · add_node_text_with_labels → texte des pages balisé <page_N>…</page_N>
 │     · split_shared_boundary_pages → une page partagée par 2 nœuds est
 │       DÉCOUPÉE (le texte d'un nœud ne contient que SA pièce — anti-contamination)
 │     · merge_redundant_children → un enfant au texte identique au parent est fusionné
 │
 ▼  ÉTAPE E — Résumé (FICHE) par pièce            generate_summaries_…()  ◇  N appels LLM
 │     · régime compilation/doc-unique décidé par is_compilation()        ◆  (sur les TITRES)
 │     · une fiche par pièce, concurrence bornée SUMMARY_CONCURRENCY=3     ◇
 │   ⇒ détaillé en §4.2-4.3
 ▼
structure.json
```

**Récapitulatif — qu'est-ce qui est reproductible ?**

| Étape | Rôle | Reproductible ? |
|---|---|---|
| A — extraction texte | pages → texte propre | **◆ oui** (◇ OCR vision **seulement** sur pages scannées) |
| B — pré-segmentation en pièces | frontières de niveau 1 | **◇ non** (1 appel LLM ; conservateur → souvent « 1 pièce ») |
| C — arbre interne (≤ 4 p.) | 1 nœud | **◆ oui** (aucune détection) |
| C — arbre interne (signets) | TdM intégrée → arbre | **◆ oui** (`get_toc()`, gratuit) |
| C — arbre interne (`tree_parser`) | sommaire reconstruit | **◇ non** (cascade LLM) |
| D — finition | ids, `<page_N>`, découpage, fusion | **◆ oui** |
| E — fiches | un résumé par pièce | **◇ non** (N appels LLM) |

Conséquence pratique (cf. §14, et `tests/tree_gate_theo.py`) : **deux indexations du
même PDF peuvent ne pas donner exactement le même arbre** — sauf si la pièce est
courte **ou** porte des signets PDF (cas C déterministes), où l'arbre est stable au
ms près. Le **cache SHA-256** (§4.1, étape 2) gèle de toute façon le premier arbre
obtenu :
réimporter ne rejoue aucun LLM, donc plus aucune variation.

> **Pourquoi pas de hiérarchie typographique (tailles de police) pour rendre l'étape C
> déterministe ?** Approche étudiée — c'est exactement ce que fait le pipeline
> `ocr_v2_src/src` (voir ci-dessous). Mesuré et **rejeté** : sur des PV de police, les
> intitulés de rubriques (« AFFAIRE : », « OBJET : », « SUR LES FAITS ») sont à la
> **même taille que le corps** — aucun signal typographique ne les distingue, donc la
> détection par seuils en rate l'essentiel. La sémantique « ceci est une rubrique »
> n'est accessible qu'au LLM (`ETUDE-PARSING-LAYOUT.md`).

### 4.1.2 Ce qui vient (ou non) de `ocr_v2_src/src`

`/Users/stephaneleroi/Dev/demo_pageindex/ocr_v2_src/src/legal_evidence` est le
pipeline d'un collègue sur le **même domaine** (pièces judiciaires, citations
auditables, tout en local). Il a été **lu intégralement et étudié avant toute
implémentation** (`ETUDE-PARSING-LAYOUT.md`, 12/06/2026). **Aucun code n'en a été
copié** : c'est un système RAG à **embeddings + BM25** (`retrieval.py`,
`layout.py` : chunks de taille fixe, hiérarchie par **seuils typographiques**), à
l'opposé du paradigme PageIndex pur (vectorless, arbre par raisonnement). Reprendre
son retrieval ou son chunking est exclu par décision structurante.

Ce que l'étude a **retenu comme idées** (réimplémentées à notre façon, pas reprises
telles quelles), et où elles atterrissent dans la construction de l'arbre :

| Idée venue de l'étude `ocr_v2_src` | Chez nous | Étape |
|---|---|---|
| Suppression des en-têtes/pieds répétés | `strip_repeated_page_furniture()` — **générique** (répétition inter-pages), pas le filtre **en dur** du collègue (« synthèses du rapport public annuel ») | A |
| OCR de secours sur pages scannées | LLM **vision** (notre `_ocr_page_with_vision`), là où lui utilise **Tesseract** ; seuils de déclenchement différents | A |
| Hiérarchie par typographie | **rejetée** comme décideuse (mesure §4.1.1) ; envisagée seulement comme *indice* pour le LLM (non implémenté) | C |
| bbox calculée à l'indexation | **non reprise** : notre surlignage est réattribué a posteriori (jugée caduque depuis la règle « un nœud par petite pièce », post-scriptum de l'étude) | préparation §4.1 (5) |

*En clair : de `ocr_v2_src` on a hérité de **problèmes bien posés** (furniture, OCR,
traçabilité) et de **contre-exemples utiles** (la typographie ne suffit pas sur ce
corpus), pas de lignes de code.*

### 4.2 Pourquoi un résumé **par pièce** (pas par nœud)

`generate_summaries_for_structure()` calcule **une fiche par pièce**, sur le **texte
concaténé** de tout le sous-arbre (tronqué à `PIECE_SUMMARY_MAX_CHARS = 60000`),
stockée sur le **nœud de tête**. Les sous-nœuds gardent leur titre, sans résumé
propre. Bénéfices : beaucoup moins d'appels LLM (4-5 fiches au lieu de 36-43 nœuds) et
une fiche **complète** (pas le seul préambule de l'en-tête).

### 4.3 Régime de résumé (`is_compilation`, détection asymétrique)

| Cas | Détection (`pageindex/utils.py — is_compilation()`) | Traitement |
|---|---|---|
| **Compilation** (pièces indépendantes — **défaut sûr**) | pièces **numérotées** (`Document/Pièce/Annexe N`), **ou** pas de majorité de mots de plan dans les titres | fiches **isolées**, en parallèle (`SUMMARY_CONCURRENCY = 3` — sinon N gros appels gèlent Ollama). Anti-contamination. |
| **Document unique** (plan cohérent) | la **majorité** des **titres** de têtes portent un mot de plan (chapitre/partie/section/titre/préface…) | fiches **cumulatives** : chaque section reçoit en contexte les fiches précédentes (continuité du fil) |

> **« Cumulatif » n'est PAS une ré-agrégation.** En document unique, chaque section
> est résumée **séquentiellement** avec, en contexte, **les fiches des sections
> précédentes** (`utils.py:1047-1061`, contexte borné aux **8000 derniers caractères**).
> Mais le prompt impose *« do NOT re-summarize them; summarize only the current part,
> but use them to resolve any back-reference »* : on résume **uniquement la section
> courante**, le contexte servant à **résoudre les renvois** (« comme vu au chapitre 2 »),
> **pas** à fusionner les résumés. En **compilation** (défaut), chaque fiche est au
> contraire produite **seule** (aucun contexte voisin) → anti-contamination.
>
> *(Précision transverse : le régime gouverne la fiche **entière** — les 7 champs —,
> pas seulement les « Points saillants » ; et le texte résumé est celui de **tout le
> sous-arbre** de la pièce, §4.2, pas le seul nœud de tête.)*

Décision sur les **titres** des têtes — c'est le **seul signal disponible à l'indexation**,
**avant** que les fiches existent. *(L'ancienne version lisait dates/auteurs/natures dans
les fiches : toujours vides à ce stade → tout document à ≥ 2 têtes basculait à tort en
compilation, y compris un vrai rapport unique à chapitres comme Synthèse.)* Mal classer une
compilation en document unique **contaminerait** les fiches : le défaut penche toujours vers
**compilation**.

---

## 5. ⭐ La sélection : `tree_search` (la brique centrale)

> **Réponse directe à la question la plus fréquente : oui, `tree_search` choisit les
> nœuds EN LISANT LES FICHES (résumés), pas en raisonnant sur la seule structure.**

### 5.1 Ce que `tree_search` reçoit exactement

`rag_service.py — tree_search(query, tree)` envoie au LLM l'arbre **privé de son seul
champ `text`** : `remove_fields(tree.copy(), ['text'])` — donc `node_id`, **`title`**
et **`summary` (la fiche) RESTENT**. Le prompt l'énonce noir sur blanc :

```
You are given a question and a tree structure of a document.
Each node contains a node id, node title, and a corresponding summary.   ← la FICHE
Your task is to find all nodes that are likely to contain the answer …
Document tree structure: { …arbre sans 'text', avec 'summary'… }
→ réponse JSON { "thinking": "<raisonnement en français>", "node_list": [ids] }
```

Donc la décision se fonde sur **titres + fiches**, jamais sur le texte intégral (qui
ne tiendrait pas dans le contexte, et qu'on veut justement éviter de lire pour
choisir). Le texte n'est lu **qu'après**, à l'étape de lecture (§6).

### 5.2 Deux échelles de sélection

| Échelle | Quoi choisir | Sur quoi le LLM raisonne |
|---|---|---|
| **Niveau 1** (entre pièces) | quelle(s) **pièce(s)** ? | **titres + FICHES** des pièces (signal principal) |
| **Niveau 2** (dans une grosse pièce) | quelles **sections** ? | **titres des sections** + la fiche de tête en contexte |

### 5.3 Comment on rend les fiches « visibles » par `tree_search`

`tree_search` est générique : il lit le champ `summary` des nœuds qu'on lui donne. Au
**niveau 1**, notre voie corpus ne lui passe pas l'arbre brut mais un **arbre de
sélection synthétique** dont chaque nœud-pièce porte, en `summary`, la fiche
construite par `agent.py — _piece_fiche()` / `_selection_fiche()` :

```
summary du nœud-pièce = FICHE de la pièce (résumé de tête)  +  "Sections :\n- titre…\n- titre…"
```

Le commentaire du code le dit : *« résumé du nœud de tête + titres des sous-sections,
**pour que le `tree_search` « voie » le contenu** »* — avec un cas réel cité (un en-tête
ministériel masquant un sujet de concours, **invisible** au niveau 1 sans cette
injection). C'est l'illustration concrète de la leçon fondatrice (§1) : **fiche pauvre
= pièce invisible**.

---

## 6. Les briques de réponse

Les voies recombinent **quatre briques** :

| Brique | Rôle | Origine |
|---|---|---|
| **`tree_search`** | *choisir* les nœuds (sur fiches niv.1 / titres niv.2) — ne lit jamais le texte | **PageIndex** |
| **Lecture du texte** | charger le **texte** des seuls nœuds retenus, pour la rédaction | notre couche |
| **Agrégation de fiches** | utiliser les **fiches déjà calculées** comme contenu (synthèse globale, inventaire en appui) | notre couche |
| **Map-reduce** | *recomposer à chaud* une fiche par pièce sous l'angle de la question, puis réduire | notre couche |

---

## 7. Routing & matrice voie × brique

Événement Socket.IO `agent_chat` → `rag_service.agent_chat_stream` (passthrough) →
`agent.py — run_session()`. Dispatch :

```
question
 ├─ mode kb SANS document ........................ → Conversation libre (modèle nu, §8.1)
 └─ documents sélectionnés
     └─ decompose_query (1 appel LLM, decompose.jinja) :
          • scinde SI plusieurs demandes de NATURES DIFFÉRENTES (→ sections ##)
          • classe l'INTENTION de chaque (sous-)question + une consigne `instructions`
        ┌─────────────────────────────────────────────────────────────┐
        │ "overview" → Synthèse globale → AGRÉGATION DES FICHES (§8.3)  │
        │ "detail"                                                      │
        │   ├─ 1 pièce  → Mono-pièce : tree_search + LECTURE TEXTE (§8.2)│
        │   └─ ≥ 2 pièces → Corpus (§8.4) : tree_search sur fiches →    │
        │        ├─ texte ≤ budget → LECTURE DIRECTE                    │
        │        └─ texte > budget → MAP-REDUCE (fiches à CHAUD)        │
        └─────────────────────────────────────────────────────────────┘
```

`decompose_query` renvoie `{needs_decomposition, items:[{question, intent, instructions}]}` ;
`intent` (`overview`/`detail`) **prime** sur l'ancienne heuristique de mots-clés
`_is_global_summary` (gardée en repli). `instructions` = *ce que le rédacteur / le map
doit extraire* (inspiré du « per-search instructions » d'Open Notebook).

**Matrice — quelle voie mobilise quelle brique** (seul `tree_search` est PageIndex) :

| Voie | Intention | `tree_search` n.1 (fiches) | `tree_search` n.2 (sections) | Lecture **texte** | **Fiches** |
|---|---|:--:|:--:|:--:|---|
| Conversation libre (§8.1) | — *(aucun doc)* | — | — | — | — |
| Mono-pièce (§8.2) | `detail`, 1 pièce | — | ✅ *interne à la pièce* | ✅ | — |
| Synthèse globale (§8.3) | `overview` | — | — | — | **agrégation de toutes** |
| Corpus — lecture directe (§8.4) | `detail`, ≥ 2 p. | ✅ | si pièce volumineuse | ✅ | inventaire en appui |
| Corpus — map-reduce (§8.4) | `detail`, ≥ 2 p., gros volume | ✅ | ✅ | *dans le map* | **fiches à chaud** + inventaire |

**Deux distinctions réglées d'après les tests :**
- **Pièce désignée vs dossier** : « résume *la note de M. X* » (pièce identifiée) =
  `detail` → on **lit le texte** ; « résume *le dossier* » = `overview` → fiches. Le
  mot « résume » seul ne tranche pas : c'est la **cible**.
- **Mono-nature sur N pièces ≠ décomposition** : « détaille **chaque** rapport » est
  **une** demande sur N pièces — **pas** décomposée (sinon le LLM devine un nombre de
  sous-questions et **sous-couvre** : cas réel 2 rapports sur 4). La voie corpus
  sélectionne elle-même toutes les pièces. La décomposition est réservée aux
  **natures différentes** (synthèse ET faits ET versions).

**Constantes (`agent.py`, classe `DocumentAgent`) :** `SIMPLE_CONTEXT_BUDGET = 60000`
(surchargeable par env `PAGEINDEX_CTX_BUDGET`), `SIMPLE_MAX_NODES = 10`,
`CORPUS_SELECT_BUDGET = 48000`, `CORPUS_INVENTORY_BUDGET = 45000`,
`CORPUS_MAX_PIECES_READ = 12`, `CORPUS_PIECE_DRILL_THRESHOLD = 20000`,
`MAP_CONCURRENCY = 3` (surchargeable par env `MAP_CONCURRENCY`),
`REFLECT_ACCEPT_THRESHOLD = 6`, `USE_PIECE_UNIT = True`.

---

## 8. Les voies, une par une

### 8.1 Conversation libre (`_run_free_chat`)

Mode kb **sans document** : dialogue direct avec le modèle, **aucune instruction
système, aucun style, aucune température** — parité avec un chat Ollama brut (un cas
réel, `DIAGNOSTIC-UEMO.md`, a montré que des consignes de style font confabuler).
Réponses « sans sources » (ni citation, ni note de qualité).

### 8.2 Mono-pièce (`_run_single_simple`) — `detail`, une pièce

Si l'intention est `overview` → délègue à la synthèse globale (§8.3). Sinon, étapes :
1. **un** `tree_search` sur l'arbre de la pièce → ≤ `SIMPLE_MAX_NODES = 10` nœuds ;
2. **lecture du texte** des nœuds (budget `SIMPLE_CONTEXT_BUDGET = 60000`, chaque
   section préfixée de son `node_<id>` réel) ;
3. **rédaction citée** (`grounding_single`, `_build_allowed_citations`) ; en mode
   Vision → images des nœuds + VLM ;
4. **pas de vérification automatique** — badge de qualité déterministe seul ; la
   vérification LLM est **à la demande** (§10).

### 8.3 Synthèse globale (`_run_global_summary`) — `overview`

**Aucun `tree_search`, aucune lecture de texte.** On **agrège les fiches de toutes les
pièces** (`_build_summary_entries`, budget par fiche adaptatif) et on rédige une vue
transversale **en un seul appel** (`grounding_summary`). Les fiches portant les
`(p. N)`, la synthèse **reste citée à la page**. Rapide, scalable.

> **Ne pas confondre avec le résumé *incrémental* de l'indexation (§4.3).** Le travail
> « fiches précédentes + section courante » a lieu **à froid, une fois**, pour
> *construire* les fiches d'un document unique. La synthèse globale, elle, **agrège
> des fiches déjà construites** ; « aucune lecture » = on ne relit pas le *texte*.

### 8.4 Corpus (`_run_corpus_simple`) — `detail`, ≥ 2 pièces

Le dossier est vu comme **un seul arbre** dont les enfants sont les pièces.
1. **Sélection niveau 1** : on construit l'**arbre de sélection** (chaque pièce = un
   nœud dont le `summary` est sa fiche + titres de sections, §5.3) et on lance **un**
   `tree_search` dessus (budget `CORPUS_SELECT_BUDGET = 48000`) → pièces retenues
   (≤ `CORPUS_MAX_PIECES_READ = 12`).
2. **Drill-down niveau 2** : une pièce composite **volumineuse**
   (> `CORPUS_PIECE_DRILL_THRESHOLD = 20000` car.) est affinée **section par section**
   (`tree_search` interne) — on ne lira que les sections pertinentes.
3. **Aiguillage selon le volume retenu** (`use_map_reduce = total_len >
   SIMPLE_CONTEXT_BUDGET and len(selected) > 1`) :
   - **lecture directe** du texte (défaut) ;
   - **map-reduce ciblé** sinon (ci-dessous).
4. **Rédaction** (`grounding_kb`) avec l'**inventaire complet** des fiches en appui
   (`_build_corpus_inventory`, `CORPUS_INVENTORY_BUDGET = 45000` — toute pièce reste
   citable même non lue) + `_build_allowed_citations`.
5. **Pas de vérification automatique** ; vérification LLM **à la demande** (§10).

**Map-reduce ciblé (fiches à CHAUD)** — *pourquoi* : le texte intégral de beaucoup de
pièces ne tient pas dans un contexte unique. *Comment* :
```
   fiches à froid (toutes les pièces) ── tree_search ──► pièces retenues
                                                          │ volume ?
   ≤ budget → LECTURE DIRECTE : texte des pièces ─────────┤
   > budget → MAP-REDUCE :                                 │
       MAP (1 appel / PIÈCE, ≤ MAP_CONCURRENCY=3 en //) :   ← _focused_summary (focused_summary.jinja)
          LEGRAND → « nie les faits (p.2), reconnaît la dispute (p.3) »   ← fiche à CHAUD
          LEPETIT → « accuse LEGRAND (p.1)… »
       REDUCE (1 appel) : confronte → réponse citée (doc, node, page)
```
- `_focused_summary()` résume **une pièce** sous l'angle de la question (+ la consigne
  `instructions`), **conserve les `(p. N)`** (→ citations préservées), renvoie `(rien)`
  → `None` si la pièce n'apporte rien.
- **Cache mémoire** `_focused_cache` (clé `(doc_id, head_id, query, instructions)`) :
  anti-recalcul intra-session.
- **Persistance disque** : chaque fiche est écrite via `store.save_focused_fiche()`
  (`focused_fiches.json`, §11) — elle **survit au redémarrage** et s'affiche dans la
  Vue Structure.

### 8.5 Décomposition (`_run_decomposed` / `_relay_subquery`)

Une question de **natures différentes** est scindée par `decompose_query` ; chaque
sous-question suit la voie de **son** intention, et les réponses sont assemblées en
**sections `##`** sous un seul cycle. `_relay_subquery` masque les marqueurs de cycle
et accumule texte + citations. **Pas** de boucle ReAct.

---

## 9. Citations, visionneuse, garde-fous

### 9.1 Citations & visionneuse (IHM, `static/js/app.js`)

- `linkifyCitations()` transforme les citations du modèle (variantes tolérées :
  `(doc: f.pdf, node_0007, page 3)`, `(node_0007, page 3)`, `(pages 5-6)`, `node_0007`
  nu… ; regex `CITE_RE`) en **pastilles « p. N » cliquables**.
- Clic → `showPagePreviewModal()` : images des pages, défilement à la page citée,
  **surlignage du nœud source** (bbox) ; pour une citation « pages seules », le nœud
  est déduit du `node_map`. Le badge dit **« Page N du PDF »** (folio ≠ index).
- **Robustesse aux citations incohérentes** (`showNodePreview`) : si la **page citée
  est hors de la plage du nœud cité** (le modèle a écrit le mauvais `node_id` à côté de
  pages correctes), on **se fie à la PAGE** — on associe le nœud qui la possède réellement
  (le plus spécifique), comme une citation « page seule ». Navigation, surlignage **et**
  prise de note pointent alors le bon nœud. *(Cas cohérent inchangé.)*
- **Visionneuse redimensionnable** : poignée sur le bord gauche (variable CSS
  `--preview-width`, bornée, persistée `localStorage`) — pilote largeur de la visionneuse
  **et** marge du chat.
- **Panneau « Structure »** (`togglePreviewStructure` / `renderStructureTree` en mode
  `readonly`) : table des matières navigable **à gauche** des pages, **réutilise** le rendu
  d'arbre de la Vue Structure (§11). Pièces avec **icône « résumé »** (fiche dépliable),
  **sous-nœuds dépliés** ; clic sur un nœud → `previewFocusNode` (défile à sa **page de
  début** + surligne). Chargé à la demande (`/tree`, cache `previewTreeCache`).

### 9.2 IDs de citation autorisés (`_build_allowed_citations`)

La rédaction reçoit la **liste explicite des `node_id` mobilisés** (« n'en cite AUCUNE
autre ») et ne peut citer **que ceux-là**, verbatim — **verrou anti-id-inventé et
anti-contamination**. L'évaluation A/B (`evaluations/RAPPORT_COMPARATIF.md`) a montré
que ce verrou réduit nettement la fuite de contenu entre pièces mal bornées d'un
fichier composite.

### 9.3 API & Socket.IO

**REST** (`routes/api.py`) : `documents` (CRUD, upload, retry, status, tree,
node-info, analysis, text-highlights, **`notes`** GET/POST/DELETE,
**`focused-fiches`** GET, édition titre/résumé d'un nœud),
**`folders/<folder>/structure`** GET (structure consolidée d'un répertoire, §10.1),
`sessions` (CRUD, truncate, messages, verify), `config/models`, `skills`.
**Socket.IO** (`routes/socket_handlers.py`) — entrée : `agent_chat`, `get_history`,
`stop_generating` ; sortie : `status` / `nodes` / `chunk` / `agent_step` /
`agent_reflect` / `answer_done` / `done` / `stopped` / `error`.

---

## 10. Vérification des réponses — alertes déterministes + vérification ciblée du fond

Une réponse sourcée peut être **bien formée mais fausse**. Principe : **ce qui est peu
coûteux (déterministe) est calculé et affiché d'office** comme *alertes* ; **ce qui exige
le modèle (le fond)** est **proposé** au clic, **ciblé** sur ce que la pré-détection a
repéré. Pas de relecture systématique, pas de réglage aveugle.

### 10.1 Les enjeux

- **Forme ≠ fond** : un contrôle déterministe (citations, verbatim) ne juge que le
  **sourçage/la forme**, jamais la **véracité**. Afficher un « 8/10 » donnerait une **fausse
  réassurance** → on n'affiche **pas** de score ; on lève des **alertes** précises.
- **Présupposé faux** : une question orientée (« **le mineur**… » alors qu'aucun n'existe)
  fait **confabuler** le modèle (cf. `DIAGNOSTIC-UEMO.md`) — il « trouve » l'entité au lieu
  de la **réfuter**. Défaut le plus pernicieux : réponse fluide et citée, fausse dès le 1ᵉʳ mot.
- **Coût** : juger le fond = appels LLM → **à la demande**, jamais automatique.
- **Dosage** : une vérification aveugle est lente *et* peu fiable → on **cible** par scope (la
  pré-détection dit *quoi* vérifier) au lieu d'un curseur de « niveau » trompeur.

### 10.2 Deux couches

| Couche | Quand | Coût | Sortie |
|---|---|---|---|
| **A — pré-détection** (`_predetect`) | à chaque réponse | **nul** (déterministe) | **alertes** précises (résolues) + **scope** recommandé |
| **B — vérification du fond** (`/verify`) | sur **clic** | LLM (ciblé) | verdict + **réponse corrigée** |

```
Réponse rédigée
   │
   ▼
[A] PRÉ-DÉTECTION  (déterministe, automatique, 0 appel LLM)   ── stockée sur message.quality
   ├─ alertes RÉSOLUES   : citations (renvoi/page) · verbatim (guillemets)  → affichées d'office
   └─ scope RECOMMANDÉ   : existence · « rien d'autre » · couverture         → proposé à l'agent
   │
   ▼  (clic « Vérifier le fond »)
[B] VÉRIFICATION CIBLÉE  (LLM, sur le scope ; ou « complète »)
   ├─ existence d'une entité  → _presupposition_violation (multi-vote)
   ├─ « rien d'autre » / omissions → reflect
   └─ défaut confirmé ?  →  RÉPONSE CORRIGÉE (affichée sous la réponse d'origine)
```

`_predetect` renvoie : `alerts` (anomalies **déjà tranchées**), `scope` (vérificateurs LLM
recommandés), `flags` (libellés en clair), `need_verify`.

### 10.3 Les détecteurs & scopes, un par un

Pour chacun : **le signal** (comment on détecte, déterministe), **ce qu'on vérifie**, et
**par quel moyen** (déterministe = tranché tout de suite ; LLM = au clic).

- **`citations`** — *alerte déterministe* (`_estimate_quality`). **Signal** : pour chaque
  renvoi `(node_X, page N)` extrait de la réponse, on vérifie que `node_X` fait partie des
  **nœuds lus** (`refs`) et que **N est dans la plage de TOUT le SOUS-ARBRE** de `node_X`
  (pas la seule plage de la tête), et que la forme n'est pas dégénérée (`source`/`【】`).
  *Pourquoi le sous-arbre :* en **synthèse globale**, une pièce est citée par sa **tête**
  (ex. `node_0006` « PREMIÈRE PARTIE », plage propre 15-18) mais ses faits sont aux pages de
  ses **sous-sections** (p. 19-47) ; valider sur la seule tête lèverait de **fausses alertes**.
  Les **feuilles** gardent leur plage propre → un vrai renvoi hors-pièce reste détecté.
  **Résultat** : alerte précise, **formulée pour l'agent** (« renvoi à une page hors de la
  section citée », « renvoi vers une section non consultée »). Tranché tout de suite, sans modèle.
- **`verbatim`** — *alerte déterministe* (`_verbatim_issues`). **Signal** : on extrait chaque
  segment **entre guillemets** `«…»`/`"…"` (≥ 12 car.), on normalise (espaces, casse) et on le
  **cherche dans le texte des pièces lues**. **Résultat** : tout passage **introuvable**
  → alerte « passage « … » introuvable tel quel dans les pièces (citation peut-être inexacte) »
  (= faux verbatim). Tranché sans modèle.
- **`presupposition`** — *vérificateur LLM recommandé*. **Signal du besoin** (déterministe,
  `_predetect`) : la question **présuppose** une entité/un rôle — `_question_presupposes`
  matche « qui est **le/la** … » ou un nom de rôle défini (« **le** mineur / **la** victime /
  **le** médecin / **le** mis en cause »…) — **ET** la réponse **ne réfute pas** déjà ce
  présupposé (`_REFUTES_RE` matche « **aucun** … n'est », « pas de … », « tous **majeurs** »…).
  Les deux ensemble = la réponse **affirme peut-être** une entité que les pièces n'établissent
  pas → on **recommande** la vérif. **Vérification** (au clic, `_presupposition_violation`) :
  appel LLM **étroit, multi-vote à la majorité** (3, ou 5 si *complet*) — « la réponse
  désigne-t-elle une entité/un rôle/une date que les sources n'**établissent** pas ? ».
- **`exhaustivity`** — *vérificateur LLM recommandé*. **Signal** (déterministe, `_EXHAUSTIVITY_RE`) :
  la réponse affirme une **absence/exhaustivité** (« aucun autre », « rien d'autre », « c'est
  tout », « il n'y a pas d'autre »…). Or le contexte peut être un **extrait partiel** (cf.
  map-reduce) → l'affirmation d'exhaustivité est invérifiable à la rédaction (règle grounding
  §3.2). **Vérification** (au clic, `reflect`) : confronte cette affirmation aux pièces.
- **`completeness`** — *vérificateur LLM recommandé*. **Signal** (déterministe) : la voie a
  produit la réponse sur un **contexte partiel** — **map-reduce** (corpus) ou **décomposition**
  (drapeau `partial_context`). Des éléments ont pu être omis. **Vérification** (au clic,
  `reflect`) : cherche les omissions.

### 10.4 Couche B — vérification du fond, ciblée (`POST …/verify`)

Champs : **`scope`** (liste des vérificateurs à lancer — par défaut celui pré-détecté) +
**`complete`** (booléen). Pas de « niveau ».

- **`complete = false` (ciblé, défaut)** : on lance les vérificateurs LLM du `scope`
  recommandé (présupposé : **3 votes**), plus `reflect` (couvre exhaustivité/omissions).
- **`complete = true`** : on lance le présupposé sur **toute** la réponse (**5 votes**) +
  `reflect`, quel que soit le scope.
- Dans les deux cas, les **contrôles déterministes** (citations, verbatim) sont **rejoués**
  pour **alimenter la réponse corrigée**.
- **Signaler + corriger** : si un présupposé faux, un faux verbatim ou un défaut est détecté
  (`reflect action:retry`, score < `REFLECT_ACCEPT_THRESHOLD = 6`) → une **réponse corrigée**
  (re-rédaction fondée sur les pièces) est proposée **sous** la réponse d'origine.
- **Contexte de vérification** : nœuds **cités d'abord**, puis les autres pièces de la session
  (borné 60k) — sinon un fait d'une pièce **non citée** passe pour une hallucination (faux
  positif).

> ⚠️ `reflect` est une **méthode d'instance** (utilise `self.pageindex`) — ne **jamais** la
> remettre `@staticmethod` : `self` capterait la question et l'éval renverrait toujours
> `accept/7` (morte). Ce bug a longtemps rendu l'auto-évaluation inopérante.

### 10.5 Côté IHM (`static/js/app.js`)

- **Alertes déterministes affichées d'office** (gratuites) : « N alerte(s) de forme » +
  liste précise (faux verbatim, page hors plage…).
- Si la pré-détection recommande un fond à vérifier : bloc **« Vérification du fond
  recommandée — \<scope\> »** + bouton **« Vérifier le fond (ciblé) »** (lance le scope
  recommandé) et **« Vérification complète »** (`complete`). Sinon : **« Forme cohérente —
  fond non vérifié »**. *(Plus de score « X/10 (auto) », plus de curseur de niveau.)*
- Après vérification : panneau **« Problèmes relevés »** (liste, un par problème) +
  éventuelle **réponse corrigée** sous la réponse d'origine.

### 10.6 Exemple de bout en bout (cas réel « le mineur »)

Question : **« Qui est le mineur mis en cause ? »** — or le dossier (Procédure) ne contient
**aucun mineur** : les deux mis en cause y sont explicitement **« Majeur »**.

1. **Rédaction.** Sans garde-fou, le modèle « trouve » un mineur (il désigne le plus jeune des
   deux) → réponse fluide et citée, mais **fausse dès le premier mot**.
2. **Pré-détection (auto, gratuite).** `_question_presupposes` repère « **le** mineur » et
   `_REFUTES_RE` ne trouve pas de réfutation → `scope = ["presupposition"]`. L'agent voit
   dans l'IHM : **« À faire vérifier — existence des personnes ou faits cités »** + le bouton
   **« Vérifier le fond (ciblé) »** (avec sa bulle d'explication).
3. **Clic.** L'agent lance la vérification ciblée.
4. **Vérification.** `_presupposition_violation` (multi-vote) confronte la réponse aux pièces
   et **constate qu'aucun mineur n'est établi** (tous majeurs).
5. **Correction proposée.** Sous la réponse d'origine : *« Aucun mineur n'est mis en cause :
   les personnes citées (LEGRAND, LEPETIT) sont toutes majeures (p. N). »*

*(Si la règle grounding a déjà fait réfuter le modèle dès l'étape 1 — « aucun mineur… » —
`_REFUTES_RE` matche, le scope reste vide, et l'IHM affiche « Forme cohérente — fond non
vérifié » : pas de fausse alerte.)*

---

## 11. Notes & annotations (persistées, sans toucher l'arbre)

Deux familles de **notes par pièce**, stockées **à part** de l'arbre PageIndex (qui
reste l'index de recherche **intact**), selon **le même motif** (`models/document.py`,
un JSON à côté de `structure.json`) :

| | Notes **utilisateur** | **Fiches à chaud** (map-reduce) |
|---|---|---|
| Origine | saisies (Vue Structure **ou visionneuse**, §11.3) | générées par le *map* (§8.4) |
| Fichier | `notes.json` | `focused_fiches.json` |
| Méthodes | `add_note` / `get_notes` / `delete_note` | `save_focused_fiche` / `get_focused_fiches` |
| Forme | `{node_id: [{id, text, kind, page, ts}]}` (`kind` ∈ `desc`/`consigne` ; `page` = n° PDF ou `null`) | `{head_id: [{query, text, nid, ts}]}` |
| Route | `/documents/<id>/nodes/<node>/notes` | `/documents/<id>/focused-fiches` |
| Persistance | disque (survit au redémarrage) | disque (survit au redémarrage) |

**Clé = tête de pièce.** Une note saisie sur un sous-nœud (une page) est **rangée
sous sa pièce** par `_piece_head_for_node` (`models/document.py`) — invariant « notes
par pièce » conservé partout (affichage, sélection). Les deux familles sont rendues
**par pièce** dans la **Vue Structure** (`app.js — srExtrasHtml` : bloc « 🔥 Fiches à
chaud » + bloc « Mes notes »). Les fiches à chaud sont **dédupliquées par (pièce,
question)** ; le cache mémoire `_focused_cache` ne sert qu'à **recalculer** moins — la
**source d'affichage est le disque**.

La **Vue Structure** elle-même est une vue deux panneaux (arbre des pièces persistant
à gauche, lecture du PDF + fiches + notes à droite), en plus des 3 pages
(Bibliothèque · conversation mono-document · questions-réponses KB). Sessions
persistées et **isolées par mode** (`single` / `kb`).

### 11.1 Structure consolidée d'un répertoire (Bibliothèque)

Conceptuellement, **un dossier de N pièces ≡ un document concaténant N pièces** —
c'est déjà ainsi que la voie corpus le traite (arbre synthétique « Dossier », §8.4).
La Bibliothèque le **reflète** : chaque groupe-dossier (« Mes documents ») offre un
aperçu dépliable **« Structure consolidée du dossier »** qui liste **les pièces de
niveau 1 de TOUS ses fichiers prêts** (titre + fiche + pages), cliquables vers la
pièce source (`app.js — loadFolderStructure` / `renderFolderPiece`, **chargé en
lazy** à l'ouverture). Données fournies par `GET /api/folders/<folder>/structure`,
qui agrège via la **détection canonique** `pageindex.piece_head_nodes` (lecture
seule, **0 appel LLM**). Un fichier lui-même composite y voit **toutes** ses pièces
remonter (ex. dossier de 25 fichiers → 30 pièces). **100 % présentation** — aucun
impact indexation/retrieval/citations ; les cartes par fichier restent.

### 11.2 Les notes : **descriptives** (sélection) ou **consignes** (rédaction)

Une note utilisateur **n'est ni une source ni une pièce** : c'est un apport humain
réinjecté dans le pipeline (`agent.py`) — **jamais** comme contexte sourcé ni
citable. À la saisie (Vue Structure), l'utilisateur choisit son **type** (`kind`),
qui détermine **où** la note agit :

| `kind` | Sens | Où elle agit |
|---|---|---|
| **`desc`** (descriptive) | *décrit* le contenu de la pièce (« cette pièce traite de X ») | **Sélection** (voie corpus) : fiche de niveau 1 **+** épinglage |
| **`consigne`** | *comment* répondre (« réponds en 3 points », « insiste sur les dates ») | **Rédaction** : orientation du rédacteur |

- **Sélection — notes `desc`** (voie corpus, niveau 1). Deux leviers **complémentaires** :
  - **Fiche de niveau 1** : les notes `desc` d'une pièce sont **injectées dans son
    `summary` de sélection** (`_piece_fiche` → `_piece_descr_notes`, sous-budget
    `PIECE_NOTES_BUDGET = 800`, ajouté **après** la troncature de la fiche → un signal
    humain n'est jamais évincé par une fiche longue). `tree_search` **raisonne donc
    dessus** : une pièce à fiche pauvre redevient *trouvable* sur le bon sujet. C'est
    le levier fondateur (§1) — *on enrichit l'arbre, on ne contourne pas le retrieval*.
  - **Épinglage (filet de sécurité)** : une pièce portant une note `desc` est
    **priorisée** (`_piece_has_notes`) même si `tree_search` ne l'a pas retenue.
- **Rédaction — notes `consigne`** : `_build_user_consignes(refs, tool_context)`
  (filtré sur `kind='consigne'`) construit un bloc « Consignes de l'utilisateur »
  joint aux prompts des trois voies (`_build_simple_answer_prompt`,
  `_build_answer_prompt`), **distinct** du contexte sourcé. Règle explicite : *ne
  jamais citer une consigne, ne pas la traiter comme une preuve ; si une consigne
  contredit le source, suivre le SOURCE*.

*Pourquoi cette séparation :* une consigne de forme n'a rien à faire dans le
raisonnement de sélection (elle ne décrit pas la pièce) ; une note descriptive ne
doit pas dicter le style. Le **niveau 1** n'existe qu'en **voie corpus** (sélection
*entre* pièces) — la mono-pièce et la synthèse globale n'ont pas de `tree_search`
niveau 1, donc l'injection en fiche ne les concerne pas.

Les **fiches à chaud** (map-reduce), elles, sont du **contenu sourcé** (cité à la
page) — leur réinjection éventuelle relèverait du contexte/inventaire, pas des
consignes (non implémenté : réserve « orientées par une question passée »).

### 11.3 Saisie des notes depuis la **visionneuse** (Questions/Réponses)

En plus de la Vue Structure, on saisit des notes **directement dans la visionneuse**
du chat (`app.js — showPagePreviewModal`, fonctions `renderViewerNotes` /
`viewerNoteAction`) :

- **Note sur une page** — bouton sous chaque page ; la note **conserve son n° de page**
  (`page = N`, page physique du PDF, cohérente avec les `(p. N)`). Concaténées, les notes
  d'une pièce forment un bloc **proche des « Points saillants »** d'une fiche.
- **Note de pièce** — bouton dans l'en-tête (carte du nœud actif) ; **globale**, sans page
  (`page = null`) — équivalent des notes de la Vue Structure.

Détails techniques :
- **Rattachement** : le front envoie le nœud propriétaire de la page (le plus spécifique,
  `bestNodeForPage`) ; le serveur **remonte à la tête de pièce** (`_piece_head_for_node`).
  Une page de **frontière** entre deux pièces est un cas limite (le nœud le plus étroit
  l'emporte).
- **Suppression** : la note est rangée sous la tête ; l'IHM garde `data-head` sur chaque
  note pour cibler la bonne clé.
- **Usage** : `page` accompagne la note `desc` **dans la fiche de sélection**
  (`_piece_descr_notes` → `texte (p. N)`) comme **contexte** — la note **reste
  non-citable** : elle n'entre **pas** dans le contexte sourcé, le principe §11.2 (« une
  note n'est pas une source ») tient. *(Évolution possible, non retenue : rendre ces
  notes-page citables comme de vrais points saillants.)*

**Documents ET répertoires, indistinctement.** Un **document composite** (1 fichier,
N pièces) et un **répertoire** (N fichiers) suivent la **même voie corpus** — le
dispatch ne compte que le **nombre total de pièces** (`agent.py`, `effective_single =
len(_extract_pieces) <= 1`), pas les fichiers. La saisie (visionneuse ouverte sur un
fichier précis, résolu par `docIdByName`), l'enrichissement de sélection
(`_piece_descr_notes`, `notes_by_doc` indexé **par doc_id**) et l'épinglage
fonctionnent donc identiquement dans les deux cas — conformément à l'équivalence
§1.2/§11.1.

---

## 12. Modèles & configuration (`config.py` → `config.json`, hors git)

| Profil | Usage | Modèle (déploiement local) |
|---|---|---|
| `text` **et** `light` | structure de l'arbre + fiches (indexation) + rédaction + étapes agent | **gpt-oss-120b-64k** |
| `vision` | réponses sur images de pages, OCR des scans | qwen3.6 |

- **Un seul modèle pour tout → zéro swap** Ollama (`text` = `light`). *(Les défauts du
  code `config.py` — `gpt-5-mini`/OpenAI — sont des placeholders ; le `config.json`
  local, hors git, fixe gpt-oss-120b-64k via Ollama.)*
- **Contexte** : l'app **ne passe pas de `num_ctx`** → la fenêtre est celle du
  **Modelfile**. `gpt-oss-120b-64k` = `FROM gpt-oss:120b` + `PARAMETER num_ctx 65536`
  (~76 Go VRAM). **Tout budget doit rester sous 65536**, sinon Ollama tronque
  silencieusement (citations faussées). `SIMPLE_CONTEXT_BUDGET` est surchargeable par
  env **`PAGEINDEX_CTX_BUDGET`** (sert à **forcer le map-reduce en test**, budget bas).
- **Aucune température imposée** (réglages du Modelfile). En contrepartie les réponses
  ne sont pas reproductibles → **évaluer sur plusieurs tirages** (cf. §14).

Tout serveur OpenAI-compatible fonctionne (Ollama, vLLM, LM Studio…). Serveur Flask +
Socket.IO sur le port `5001` (`config.py`, `debug=True`).

---

## 13. Modifications locales de `pageindex/` (fork)

`pageindex/` est une copie de [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex).
Le **paradigme** (arbre par raisonnement, prompts du cookbook pour `tree_search`)
n'est jamais modifié. Ajustements locaux : (1) extraction **PyMuPDF** + suppression
en-têtes/pieds ; (2) texte des nœuds balisé `<page_N>` ; (3) **découpage des pages de
frontière** (anti-contamination) ; (4) **résumé identitaire par PIÈCE**
(`generate_summaries_for_structure`), dans la langue du document ; (5) pages issues
des `<physical_index_X>` ; (6) réparation du sommaire ; (7) timeout LLM 180 s ;
(8) tokenizer avec repli `o200k_base` ; (9) **fusion des nœuds redondants** ;
(10) **aucune température imposée** ; (11) **régime compilation vs document unique**
(`is_compilation`, décidé sur les **titres** des têtes — §4.3) ; (12) **citations de
page dans les fiches** (`(p. N)`) ; (13) **concurrence bornée des résumés**
(`SUMMARY_CONCURRENCY = 3`, surchargeable par env du même nom — comme `MAP_CONCURRENCY`
côté requête) ; (14) **pré-segmentation en pièces** d'un fichier composite
(`segment_pieces`, **1 appel LLM**, conservateur) ; (15) **arbre interne depuis les
signets PDF** (`tree_from_bookmarks`, gratuit/déterministe, repli `tree_parser`).

---

## 14. Limites connues

- **Synthèse globale (`overview`) = niveau « fiches »** : structure et thèmes, pas le
  détail circonstancié — levier = richesse des fiches. *(Les questions de détail
  passent en `detail` → texte, voire map-reduce.)* Sous la pression du grounding, le
  modèle tend à **énumérer** les pièces plutôt qu'à les fondre.
- **Sélection tributaire de la fiche** : une pièce est jugée sur sa fiche (§5.3) —
  fiche pauvre → pièce potentiellement ratée.
- **Frontières de pièces posées par le LLM** (`segment_pieces`, 1 appel) à l'indexation
  — **non déterministes** sur une frontière subtile ; un fichier composite mal borné peut
  faire « déborder » une pièce sur sa voisine (atténué par les IDs de citation autorisés,
  §9.2). *(L'arbre **interne** d'une pièce, lui, est **déterministe** quand des signets
  PDF existent — `tree_from_bookmarks`, §4.1.)*
- Pages sans couche texte **transcrites par le modèle vision** (sinon page vide).
- Détection de sommaire limitée aux **20 premières pages**.
- Indexation et réponses **non déterministes** (LLM, température Modelfile) → évaluer
  sur **plusieurs tirages**.
- **`node_id` non stables à la réindexation** : le `doc_id` est désormais stable
  (dérivé du SHA, §4.1), mais réindexer un document **sans signets** peut **réassigner**
  les `node_id`/pages (segmentation/sommaire par LLM). Une **vieille** conversation peut
  donc citer un `node_id` dont le contenu a bougé. Atténuations : la visionneuse se **fie
  à la page** si nœud et page divergent (§9.1) ; les documents **à signets** ont un arbre
  **déterministe** (`tree_from_bookmarks`, §4.1). *(Une citation `(node, page)` peut aussi
  être simplement **fausse à la génération** — mauvais `node_id` écrit par le modèle ; c'est
  ce que signale le contrôle « page hors de la section citée », §10.3.)*

---

*Études & évaluation : `ETUDE-SEGMENTATION-PIECES.md` (pré-segmentation déterministe),
`ETUDE-MAP-REDUCE-CIBLE.md` (fiches à chaud), `ETUDE-OPEN-NOTEBOOK.md` (instructions
par recherche, prompts externalisés, IDs autorisés), `DIAGNOSTIC-UEMO.md` (dégradation
du modèle par les enrobages), `ETUDE-RAGFLOW.md` (comparatif). Évaluation :
`FONCTIONNEMENT-PAR-TESTS.md` (les voies par 4 cas réels) et le skill
`.claude/skills/evaluer-reponse-sourcee/` (audit sourcé + chaîne « lancer → évaluer » ;
résultats dans `evaluations/`).*
