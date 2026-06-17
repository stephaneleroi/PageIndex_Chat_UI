# Spécificités de PageIndex_Chat_UI pour l'évaluation

Ce que l'évaluateur doit savoir de l'app pour classer correctement les constats.
Sources : `ARCHITECTURE.md`, `CLAUDE.md`, `FONCTIONNEMENT-PAR-TESTS.md`,
`services/agent.py` (`GROUNDING_INSTRUCTION_*`).

## 1. Convention de page (🔵 — ne jamais compter comme erreur)

`(p. N)` = **page physique du PDF** (index PyMuPDF, balises `<page_N>`), partagée
avec la visionneuse (le clic ouvre la page N). Elle peut **différer du folio
imprimé** sur la page (ex. pages de garde non numérotées → décalage). Vérifier une
citation = contrôler que le fait est sur la **page physique** N (`verif_source.py
page`). Un écart vs le numéro imprimé sur la page est **attendu**, pas un bug.

## 2. Voies d'aiguillage et attentes de fidélité

- **`overview`** (intention « vue d'ensemble / synthèse ») → **agrégation des
  fiches** (résumés de pièces), **sans relire le texte**. Rapide, passe à
  l'échelle, mais **survole** : peut omettre un détail/acteur et ordonner
  approximativement. Omission en overview = souvent 🔵 (limite), sauf si l'élément
  était explicitement dans une fiche mobilisée (alors 🔴 omission).
- **`detail`** (intention « contenu factuel précis ») → **lecture du texte** des
  pièces. C'est la voie **fidèle** : on attend l'exactitude (faits, versions,
  citations à la page). Un écart ici est plus grave (🔴).
- **map-reduce ciblé** (gros volume, voie corpus) → une **fiche à chaud par pièce**
  (texte tronqué au budget par pièce) puis *reduce*. Les **omissions** dues à la
  troncature du *map* sont en partie **artefact du test** quand le seuil a été
  forcé bas ; le noter. Les `(p. N)` doivent rester présentes.
- **décomposition** : une question composite est scindée en sous-questions de
  natures différentes, chacune sur sa voie. Vérifier que chaque facette a pris la
  bonne voie (ex. « versions » doit être `detail`/texte, pas `overview`/fiches).

Enseignement transverse : sur un dossier composite, **`detail` (texte) est plus
fiable que `overview` (fiches)**.

## 3. Artefacts de données connus du corpus (🟡 — l'app est fidèle)

Le corpus de test contient des incohérences ; l'app les **reproduit fidèlement**.
Ne jamais les signaler comme hallucinations sans avoir lu le source.

- **Dossier `Procedure-PN-1-PDF` — certificat médical**
  (`…Certificat medical_MEC_LEPETIT_Adrien.pdf`) : formulaire mal rempli. Le texte
  source porte l'**identité de LEGRAND** (né le 05/05/2000, 15 rue des iris) alors
  que le fichier est nommé **LEPETIT** ; le **champ médecin est vide** ; il est
  **« Signé par ROMUALD LIGNIER »** — le **nom de l'OPJ réutilisé**. Donc « Lignier
  médecin légiste » et « examen de Victor » = **fidélité à un document anormal**,
  pas une hallucination. (Vérifier : `verif_source.py page <certificat> 1`.)
- **Nom « LIGNIER » réutilisé** pour l'OPJ ET le signataire du certificat → toute
  « confusion de rôle » Lignier vient des **données**.
- **Noms-pièges proches** (corrects dans les données, à ne pas « corriger ») :
  mères **LAPETITE** (Victor) vs **LAGRANDE** (Adrien) ; mis en cause **Legrand**
  vs **Lepetit**.

Avant de qualifier une « contamination » ou une « hallucination », **lire la pièce
source** : si l'incohérence y est déjà, c'est 🟡.

## 4. Règles de grounding que la réponse doit respecter (un écart = 🔴)

D'après `GROUNDING_INSTRUCTION_KB` / `_SINGLE` (`services/agent.py`) :

1. Chaque fait concret est **cité** `(doc, node, page)` avec le vrai node id.
2. La page vient du marqueur `<page_N>` englobant — **jamais devinée**.
3. Si le contexte ne couvre pas la question → le **dire** ; ne rien fabriquer.
   **Ne jamais affirmer l'exhaustivité/absence** (« aucun autre chiffre », « rien
   d'autre ») : le contexte peut être partiel/condensé.
4. Comparaisons inter-documents : identité du document **non ambiguë**.
5. **Ne pas attribuer ni inverser un rôle** (auteur/destinataire, médecin/
   enquêteur, parent/enfant) non explicite, même si deux personnes partagent un
   nom → sinon « non précisé ».
6. **Guillemets réservés au verbatim exact** ; une paraphrase ne doit pas être
   présentée comme citation (`verif_source.py quote` pour trancher).

Une réponse qui viole une de ces règles **par sa propre rédaction** (et non parce
que le source l'impose) est un 🔴.

## 5. Où regarder dans le dépôt

- Réponses + traces de test : `audits/*.md` (question, voie, nœuds, citations,
  réponse complète).
- Arbre indexé + **OCR vision** (en-têtes, formulaires) :
  `results/documents/<id>_<nom>.pdf/structure.json` (champ `text`, balisé
  `<page_N>` ; champ `summary` = la **fiche** d'une pièce).
- PDF source : `../data/` (`SOURCE_DATA_DIR`).
