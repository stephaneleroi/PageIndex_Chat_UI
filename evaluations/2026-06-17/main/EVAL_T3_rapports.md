# Évaluation — T3 Rapports_LSC — 2026-06-17

- **Question** : Fais moi un résumé des différents rapports
- **Source** : `../data/Rapports_LSC.docx` (.docx illisible par PyMuPDF) → texte indexé
  `results/documents/20260616_192819_0da4_Rapports_LSC.pdf/structure.json`
  (champ `text` balisé `<page_N>`, champ `summary` = fiche).
- **Voie / aiguillage** : décomposition (1 indice) → `global_summary`, 4 pièces/sections
  agrégées. Voie **overview** (agrégation des fiches, sans relecture du texte) —
  map-reduce : non. Nœuds : `0000`, `0014`, `0022`, `0029`.
- **Note globale** : **12/20** — Couverture complète des 4 rapports et faits exacts,
  mais l'app rapporte fidèlement une **fiche d'indexation défaillante** (node_0000) qui
  fusionne 3 rapports en un, d'où une **mauvaise attribution de nœud/document** et une
  **contradiction de date** (« le même jour, le 5 juillet 2025 »). Le défaut est en
  amont (segmentation de l'arbre), pas dans la rédaction de synthèse.

## Couverture des 4 rapports
| Rapport | Personne | Présent ? | Faits clés exacts ? |
|---|---|---|---|
| CAP 18/09/2025 (node 0000) | Hugo GIRARD | ✅ | ✅ (23 ans, cannabis 3 joints non dépendant, logistique, réservation DDSE 21/09/25) |
| CAP 05/07/2025 (node 0014) | Karim HASSAN | ✅ | ✅ (incarcéré 15/05/2025, vol récidive, SDF, CRI 02/07/2025, refus retour Maroc, avis défavorable) |
| SPIP 22/06/2025 (node 0022) | Diego GONZÁLEZ | ✅ | ✅ (TC Toulouse 18/07/2023, stupéfiants au volant, semi‑liberté/DDSE, hébergement sœur à Muret) |
| SPIP 27/07/2025 (node 0029) | OUALI Rayan | ✅ | ✅ (jugement 03/06/2025 Bordeaux, 6 mois, violences transport + outrage, Secours catholique Bordeaux) |

**Aucune contamination externe** : pas de nom/fait étranger au corpus introduit.
Les 4 personnes annoncées (« quatre personnes incarcérées ») sont bien les 4 réelles.

## Constats
| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app (indexation) | majeure | **Fusion de 3 rapports dans un seul nœud.** node_0005 (sous-section du rapport GIRARD, node_0000) a `start 1 / end 7` et son `text` déborde sur les pages 1→7, absorbant les rapports HASSAN (pp.3‑5) et GONZÁLEZ (pp.6‑7). La **fiche** de node_0000 reproduit cette fusion (« Le même document comporte également le dossier de Karim HASSAN (p.3‑5)… Diego GONZALEZ (p.6‑7) »). La synthèse hérite donc d'un « document » faux. | structure.json : node_0005 pages ['1'..'7'] ; fiche node_0000 |
| 2 | 🔴 app (citation/grounding) | majeure | **Mauvaise attribution de nœud** : la réponse (§4) cite **node_0000** pour HASSAN (p 3‑5) et GONZÁLEZ (p 6‑7), alors que ces contenus sont les pièces **node_0014** (5 juillet, HASSAN) et **node_0022** (22 juin, GONZÁLEZ). Viole la règle de grounding « identité du document non ambiguë ». Conséquence directe du constat #1. | pages physiques 3 (en‑tête « CAP DU 5 JUILLET 2025 … HASSAN »), 6 (« Avis SPIP … 22 juin 2025 … GONZALEZ ») |
| 3 | 🔴 app (rédaction) | moyenne | **Contradiction de date introduite** : §3 « Le même jour, **le 5 juillet 2025**, la Direction… a rendu un avis défavorable… HASSAN », juste après avoir daté l'avis GONZÁLEZ du « 22 juin 2025 ». « Le même jour » est faux (22 juin ≠ 5 juillet) ; la formule est une bavure de rédaction, le source ne l'impose pas. | node_0014 p.3 (« 5 JUILLET 2025 ») vs node_0022 p.6 (« 22 juin 2025 ») |
| 4 | 🟡 données / fiche | mineure | « avis **défavorable répété** » pour HASSAN (§ résumé final) : laisse entendre deux avis distincts, alors qu'il n'y a qu'**un** rapport HASSAN (node_0014). L'illusion de répétition vient de la fusion #1 (HASSAN apparaît « deux fois »). Non imputable à la rédaction. | structure.json (un seul nœud HASSAN : 0014) |
| 5 | 🔵 connu | — | Avis GIRARD : la réponse parle de « libération conditionnelle envisagée » sans mentionner que l'**AVIS** de la pièce est **FAVORABLE** et que le SPIP propose une **DDSE**. Survol attendu d'une voie `overview` (fiches), non un défaut de fidélité. | node_0000 p.1 (« AVIS : FAVORABLE »), p.2 (« Le SPIP propose une LSC sous la forme d'une DDSE ») |
| 6 | 🔵 connu | — | Citations « p 6‑7 », « p 3‑5 », « p 8 » = **pages physiques** du PDF d'indexation, vérifiées exactes ; pas de folio imprimé en jeu. | pages physiques 3,5,6,7,8 |

## Analyse par section / facette

**Faits (exactitude brute)** : excellente. Toutes les dates de naissance, condamnations,
quantums, lieux, dates d'audience, motifs d'infraction, hébergements et avis vérifiés
contre le texte indexé sont **exacts**. Aucune hallucination de fait, aucune
contamination par un nom externe.

**Structure / attribution** : c'est là que tout se joue. Le cœur du problème n'est pas
la synthèse mais **l'arbre** : la segmentation a rattaché les rapports HASSAN et
GONZÁLEZ comme « contenu » du rapport GIRARD (node_0005, end_index 7). La fiche de
node_0000 a donc décrit *trois* personnes ; en `overview`, la synthèse agrège les fiches
sans relire le texte, elle ne pouvait donc pas détecter que HASSAN/GONZÁLEZ sont des
documents distincts. D'où la double présentation de HASSAN/GONZÁLEZ (une fois sous
node_0014/0022, une fois ré-attribuée à node_0000) et la fausse formule « le même jour ».

**Distinction app vs données** : ce n'est **pas** un artefact des données — le `.docx`
contient bien 4 rapports nettement séparés (en-têtes distincts pp.1, 3, 6, 8). C'est un
**défaut d'indexation** (frontières de nœuds), donc actionnable et imputable à l'app.
La couche de rédaction, elle, est fidèle à ce que l'arbre lui a fourni.

## Corrections proposées (🔴 uniquement)

1. **Constat #1 (racine)** — Corriger les frontières de nœuds : node_0005 ne doit pas
   avoir `end_index = 7`. Les en-têtes pp.3, 6, 8 sont des **débuts de pièce** (niveau 1)
   et doivent rester les pièces 0014 / 0022 / 0029, pas être absorbés par le sous-arbre
   de GIRARD. Vérifier le découpage `USE_PIECE_UNIT` / la détection de frontière de pièce
   sur ce composite (en-têtes « RAPPORT LSC » / « Avis du Service pénitentiaire… »). Une
   fois l'arbre correct, la fiche de node_0000 ne décrira plus que GIRARD et les
   constats #2, #3 et #4 disparaissent mécaniquement.
2. **Constats #2 et #3** — pas de correctif rédactionnel propre : ils sont des
   symptômes de #1 et se résorbent en corrigeant la segmentation. Ne pas patcher la
   synthèse (qui reste fidèle à sa source).
