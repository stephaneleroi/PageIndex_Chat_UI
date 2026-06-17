# Comment l'application traite une question — expliqué par 4 cas réels

Ce document explique **toutes les fonctionnalités de traitement d'une requête**
(décomposition, aiguillage, choix de voie, lecture des documents, sourcing des
réponses) en s'appuyant sur les **4 tests réels** rejoués sur les dossiers
indexés. Pour le détail interne, voir `ARCHITECTURE.md` §5.

---

## 1. Le pipeline de traitement (rappel)

Toute question passe par les mêmes étapes :

```
Question
  │
  ▼  ① DÉCOMPOSITION + AIGUILLAGE  (decompose_query, 1 appel LLM)
  │     • découpe SI la question enchaîne plusieurs demandes de natures différentes
  │     • classe l'INTENTION de chaque (sous-)question :
  │         - overview = vue d'ensemble / synthèse du dossier  → FICHES
  │         - detail   = contenu factuel précis (fait, versions, contenu d'une pièce) → TEXTE
  ▼  ② VOIE choisie selon (nb de pièces) × (intention)
  │     - overview ........................ Synthèse globale (agrège les fiches)
  │     - detail, 1 pièce ................. Mono-pièce  (tree_search interne → lecture)
  │     - detail, ≥ 2 pièces .............. Corpus (tree_search sur fiches → lecture ;
  │                                          map-reduce si le texte déborde le budget)
  ▼  ③ SOURCING : citations (doc, node, page) vérifiées (_estimate_quality)
```

**Deux notions de « résumé » à ne pas confondre** : les **fiches** (résumés par
pièce, calculés *à froid* à l'indexation) servent à *informer et sélectionner* ;
le **texte** des pièces n'est lu (*à chaud*) que pour les questions `detail`.

---

## 2. Tableau récapitulatif — l'aiguillage de chaque test

| Test | Question | Décomposée ? | Intention(s) | Voie(s) | Source | Sourcing |
|---|---|---|---|---|---|---|
| **1** | « Résume la **note de M. CHAUVIN** » | non (1 demande) | `detail` | Corpus → 1 pièce | **texte** de la note | 6 cit. (node_0008, p. 5-8) |
| **2** | « Synthèse **+** faits reprochés **+** versions » | **oui → 3** | `overview` + `detail` + `detail` | Synthèse globale **puis** Corpus×2 | fiches **puis** texte | 14 cit. (34 nœuds) |
| **3** | « Résume **les différents rapports** » | non (1 demande, N pièces) | `detail` | Corpus → toutes les pièces | **texte** des 4 rapports | 25 cit. (35 nœuds) |
| **4** | « Fais moi un **résumé** » (gros doc) | non (1 demande) | `overview` | Synthèse globale | fiches (6 pièces) | 13 cit. |

---

## 3. Détail par test

### Test 1 — « Résume la note de M. CHAUVIN au juge LEMOINE » (Dossier Théo)

- **Décomposition** : aucune (une seule demande).
- **Aiguillage** : la question vise **une pièce désignée** (par auteur + destinataire
  + type « note ») → intention **`detail`** → il faut **lire le texte** de cette
  pièce (et non se contenter de sa fiche).
- **Voie & traitement des documents** : Dossier Théo = **fichier composite** (5-6
  pièces). Voie **corpus** : un `tree_search` raisonne sur les **fiches** des
  pièces et n'en retient **qu'une** — « Document 2 – NOTE D'INFORMATION »
  (`node_0008` + son sous-nœud) ; son **texte** est lu.
- **Sourcing** : 6 citations, toutes sur `node_0008`, pages **5 à 8** — vérifiées
  cohérentes contre le PDF (5/5, 8/8, 6/6 sur les tirages de contrôle).
- **Ce que ça illustre** : *cibler une seule pièce dans un dossier composite*,
  **sans contamination** des autres documents (le concours, les autres rapports ne
  sont pas mélangés), et la **lecture du texte** d'une pièce désignée.

### Test 2 — « Synthèse + faits reprochés + versions » (Procedure-PN-1, 25 pièces)

- **Décomposition** : **OUI → 3 sous-questions** (3 demandes de natures
  différentes), restituées en **3 sections** :
  1. *synthèse* (actes / chronologie / professionnels / personnes),
  2. *faits reprochés*,
  3. *versions des personnes concernées*.
- **Aiguillage (par sous-question)** :
  - 1. *synthèse* → **`overview`** → **Synthèse globale** : agrège les **fiches**
    des 25 pièces → vue structurée (les 4 facettes sont toutes présentes : actes,
    chronologie, professionnels, personnes).
  - 2. *faits reprochés* → **`detail`** → **Corpus** : `tree_search` → pièces
    pertinentes lues (convocation, audition, compte-rendu d'enquête) → faits cités
    (`COPJ…node_0000 p.1`, `AUDITION…node_0000 p.2`, `Compte-rendu…p.1`).
  - 3. *versions* → **`detail`** → **Corpus** : lecture des **auditions** →
    **confrontation** des déclarations (Legrand, Lepetit, Lebrun, témoins) citées
    à la page.
- **Traitement des documents** : 34 nœuds mobilisés ; les facettes `detail` ont
  **lu le texte** (le volume tenait dans le budget → lecture directe, sans
  map-reduce).
- **Sourcing** : 14 citations `(doc, node, page)`, aucune fuite de raisonnement.
- **Ce que ça illustre** : la **décomposition** d'une question composite et
  l'**aiguillage par sous-question** — chaque facette part sur la voie adaptée
  (survol sur fiches / détail sur texte), assemblées en une seule réponse.

### Test 3 — « Résume les différents rapports » (Rapports_LSC, 1 fichier = 4 rapports)

- **Décomposition** : aucune. C'est **une seule demande** portant sur **plusieurs
  pièces** (« les différents rapports ») — on **ne la découpe pas** (sinon le LLM
  devinerait un nombre de sous-questions et risquerait d'en oublier).
- **Aiguillage** : intention **`detail`** (on veut le contenu de chaque rapport,
  pas un survol) → **Corpus**.
- **Traitement des documents** : `tree_search` retient **toutes** les pièces
  pertinentes (35 nœuds), leur **texte** est lu → les **4 rapports** sont traités :
  Hugo **GIRARD** (avis favorable), Karim **HASSAN** (défavorable), Diego
  **GONZALEZ** (favorable), Rayan **OUALI** (favorable).
- **Sourcing** : 25 citations à la page (`node_0002 p.1`, `node_0014 p.3`,
  `node_0022 p.6`, `node_0030 p.8`…), un avis cité par rapport.
- **Ce que ça illustre** : une demande **mono-nature couvrant N pièces** → **non
  décomposée**, la voie corpus assure la **couverture complète** (4/4) en lisant
  le texte, **sans contamination** entre rapports.

### Test 4 — « Fais moi un résumé » (Synthèse_2026, 1 document de 114 p.)

- **Décomposition** : aucune (une seule demande).
- **Aiguillage** : « résume » **un gros document** sans cible factuelle précise →
  intention **`overview`** → **Synthèse globale**.
- **Traitement des documents** : **aucune lecture ni `tree_search`** — on **agrège
  les fiches** des 6 pièces de niveau 1 (Avertissement, Chapitre introductif, 3
  Parties…). *Note : ce document unique a été indexé en régime **cumulatif** ; ses
  6 fiches portent déjà la continuité du fil — voir `ARCHITECTURE.md` §4.2/§5.3.*
- **Sourcing** : 13 citations à la page (`node_0002 p.7-10`, `node_0003 p.16-23`,
  `node_0009 p.53`, `node_0015 p.86…`) reprises depuis les fiches.
- **Ce que ça illustre** : une **vue d'ensemble** rapide d'un long document, citée
  à la page **sans relire le texte** (les fiches suffisent), passant à l'échelle.

---

## 4. Ce que les 4 cas montrent de l'application

| Fonctionnalité | Illustrée par | Comportement |
|---|---|---|
| **Décomposition** d'une question composite | Test 2 | scinde en sous-questions de **natures différentes** uniquement ; assemble en sections |
| **Non-décomposition** d'une demande mono-nature multi-pièces | Tests 3 (et 1) | « chaque/les rapports » reste **une** demande → la voie corpus couvre tout |
| **Aiguillage `overview`** (fiches) | Tests 4, et facette 1 du 2 | vue d'ensemble → agrégation des fiches, **sans lecture** |
| **Aiguillage `detail`** (texte) | Tests 1, 3, facettes 2-3 du 2 | contenu factuel → `tree_search` + **lecture du texte** |
| **Pièce désignée** vs **dossier** | Test 1 vs Test 4 | « la note de X » (detail/texte) vs « le dossier » (overview/fiches) |
| **Couverture multi-pièces** | Test 3 | 4 rapports sur 4, lecture du texte |
| **Anti-contamination** | Tests 1, 3 | chaque pièce traitée isolément, pas de mélange |
| **Sourcing à la page** | les 4 | citations `(doc, node, page)` vérifiables contre le PDF |
| **Passage à l'échelle** | Tests 2 (25 pièces), 4 (114 p.) | sélection + budget de lecture ; map-reduce en réserve si débordement |

**En une phrase** : l'application **lit la question** (la découpe si plusieurs
demandes), **décide pour chaque demande** s'il faut un *survol* (fiches) ou le
*détail* (lecture du texte), **sélectionne les bonnes pièces** par raisonnement
sur les fiches, et **cite à la page** ce qu'elle affirme.

*(Données issues des audits `audits/night_test*.md` ; méthodologie et corrections
dans `audits/RAPPORT_NUIT.md`.)*
