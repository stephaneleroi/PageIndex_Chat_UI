# Évaluation — T3 — Rapports LSC [Etude_Open_Notebook] — 2026-06-17

- **Question** : Fais moi un résumé des différents rapports
- **Voie / aiguillage** : pas de décomposition utile (indices 1) → `global_summary`,
  agrégation des **4 fiches** (résumés de pièces) des nœuds 0000, 0014, 0022, 0029.
  Voie **overview / fiches** (pas de relecture du texte). Map-reduce : non.
- **Source** : `../data/Rapports_LSC.docx` (illisible PyMuPDF) → texte indexé
  `results/documents/20260616_192819_0da4_Rapports_LSC.pdf/structure.json`
  (4 pièces de niveau 1 : node 0000 = RAPPORT LSC 18/09/2025 GIRARD ;
  node 0014 = RAPPORT LSC 05/07/2025 HASSAN ; node 0022 = Avis SPIP 22/06/2025
  GONZALEZ ; node 0029 = Avis SPIP 27/07/2025 OUALI).
- **Note globale** : **16,5/20** — couverture **complète et fidèle des 4 rapports**,
  faits exacts, aucune contamination inter-personnes ; pénalisée par une
  **mauvaise catégorisation** du corpus (« les deux rapports » au lieu de 4 pièces,
  dont 2 avis SPIP) et par des **citations de nœud sur-attribuées** à node_0000.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | moyenne | La réponse réduit le corpus à « **les deux rapports** d'évaluation… 5 juillet et 18 septembre » et conclut sur « le cadre décisionnel commun aux **deux rapports** ». Or il y a **4 pièces** : 2 RAPPORT LSC **et 2 Avis du SPIP** (22/06 GONZALEZ, 27/07 OUALI), de nature différente. GONZALEZ/OUALI ne relèvent pas des « deux rapports ». | Titres sources : « RAPPORT LSC » (p.1, p.3) vs « Avis du Service pénitentiaire d'insertion et de Probation… CAP du 22 juin 2025 / 27 juillet 2025 » (p.6, p.8) |
| 2 | 🔴 app | faible | **Sur-attribution de citations à node_0000.** HASSAN cité « (node_0014, p. 3‑5 ; **node_0000, p. 3‑5**) » et GONZALEZ « (**node_0000, p. 6‑7** ; node_0022, p. 6‑7) ». Le sous-arbre réel de node_0000 ne couvre que **GIRARD, pages 1‑2** ; HASSAN = node_0014 (p.3‑5), GONZALEZ = node_0022 (p.6‑7). Le node_0000 ajouté est redondant et hors sujet. | Arbre : enfants de node_0000 (0001‑0013) bornés pages 1‑2, sujet GIRARD ; HASSAN sous node_0014 ; GONZALEZ sous node_0022 |
| 3 | 🔵 connu | — | Voie **overview** (fiches) : la réponse survole (pas de relecture du texte) ; c'est le comportement attendu pour « fais un résumé ». Aucune omission factuelle majeure constatée malgré cela. | `app-specifics.md §2` |
| 4 | 🔵 connu | — | `(p. N)` = page **physique** du PDF reconstruit depuis le .docx. Toutes les pages citées (1, 3, 6, 8 + plages) correspondent aux pages physiques des pièces. | structure.json balises `<page_N>` |

### Faits vérifiés (tous fidèles au source — aucun 🔴)
- **GIRARD** : né le **14/09/2002** à Metz ✓ ; **12 mois dont 6 mois sursis** probatoire ✓ (p.1) ; cannabis 3 joints/j, ne se déclare pas dépendant ✓ (p.2) ; projet logistique + réservation **DDSE 21/09/25** ✓ (p.2) ; avis **FAVORABLE** ✓ (p.1).
- **HASSAN** : né **30/09/1998** au Maroc ✓ ; 4 mois + 2 mois **vol en récidive** ✓ (p.3) ; **SDF**, **peintre non déclaré**, cannabis ✓ (p.4) ; **CRI 02/07/2025** détention/trafic/objets interdits ✓ (p.4) ; **avis DÉFAVORABLE** ✓ (p.5) ; rapport **05/07/2025** ✓.
- **GONZALEZ** : né **07/04/1983** à Muret ✓ ; **10 mois** pour conduite sous stupéfiants ✓ (p.6) ; **mesure de milieu ouvert** antérieure ✓ ; avis SPIP **22/06/2025** ✓ ; LSC possible (OUI) en **semi‑liberté / DDSE** ✓ ; hébergement **chez sa sœur à Muret** ✓ (p.6‑7).
- **OUALI** : né **21/02/1988** à Libourne ✓ ; **6 mois** pour **violences dans un moyen de transport collectif** + outrages ✓ (p.8) ; **SDF** ✓ ; avis SPIP **27/07/2025** ✓ ; LSC viable (OUI) ✓ ; **hébergement en demi‑liberté au Secours catholique de Bordeaux** ✓ (p.8).
- Synthèse favorable/défavorable (GIRARD, GONZALEZ, OUALI favorables ; HASSAN défavorable) : **exacte** au regard des 4 avis sources.

### Couverture et contamination
- **Couverture des 4 rapports : complète.** Les 4 personnes (GIRARD, HASSAN, GONZALEZ, OUALI) et les 4 dates (18/09, 05/07, 22/06, 27/07) sont présentes.
- **Aucune contamination inter-personnes** : chaque fait (dates de naissance, peines, hébergements, avis) est attribué à la bonne personne. Notamment, le piège du source — la **fiche de node_0000 mélange GIRARD/HASSAN/GONZALEZ** dans ses « Points saillants » (artefact d'indexation, le texte du .docx ayant débordé), et nomme à tort « **Youcef HASSAN** » et un « rapport d'avril 2025 » pour GONZALEZ — **n'a PAS contaminé** la réponse finale : l'app a correctement re‑ventilé les faits par personne et par bonne date. Bon point.

## Analyse par section / facette

La réponse est **factuellement très solide** : sur ~25 faits concrets (état civil, peines, infractions, addictions, incidents, hébergements, avis), **aucun fait erroné** n'a été trouvé contre le texte source ; toutes les pages physiques citées sont justes. C'est remarquable sachant que la voie est `overview` (fiches) et que **la fiche du nœud 0000 est elle‑même contaminée** (elle agrège GIRARD + HASSAN + GONZALEZ et porte des erreurs : « Youcef HASSAN », « rapport d'avril 2025 » pour GONZALEZ). L'app a **dé‑contaminé** correctement à la rédaction.

Les deux 🔴 sont des défauts de **cadrage/citation**, non de fond :
- Constat 1 : la **taxonomie** du corpus est fausse — l'app parle de « deux rapports » alors que la moitié des pièces sont des **avis SPIP**, de nature et d'auteur distincts (DAP vs SPIP). Cela affaiblit l'exactitude documentaire de l'intro et de la conclusion. C'est imputable à l'app (le source distingue clairement les titres).
- Constat 2 : node_0000 est **sur‑cité** pour HASSAN et GONZALEZ, dont le contenu appartient à node_0014 et node_0022. Lien de citation peu fiable (un clic IHM sur node_0000 n'ouvrirait pas la bonne pièce), même si la **page physique** citée reste correcte.

## Corrections proposées (🔴 uniquement)

- **Constat 1** : à la rédaction d'un résumé multi‑pièces, ne pas globaliser sous une étiquette unique (« les deux rapports ») quand les fiches portent des **natures (`Nature :`) et auteurs différents** (RAPPORT LSC / Avis SPIP). Le gabarit de synthèse (`services/prompts/*.jinja`) pourrait rappeler de **respecter la nature déclarée de chaque pièce** et le **nombre réel de pièces** (ici 4), plutôt que de les fusionner.
- **Constat 2** : la liste des node ids autorisés par fait (`_build_allowed_citations`) devrait empêcher d'attribuer à node_0000 des pages (3‑7) hors de son sous‑arbre réel (pages 1‑2). Piste : borner les pages citables d'un nœud à son `[start_index, end_index]` effectif. À noter que la cause racine est un **artefact d'indexation** (le texte du .docx a débordé dans le `text` de node_0000 au‑delà de ses pages), à corriger côté découpe plutôt que côté rédaction.
