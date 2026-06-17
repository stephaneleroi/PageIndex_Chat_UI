# Évaluation — T3 — Rapports LSC — 2026-06-17

- **Question** : « Fais moi un résumé des différents rapports »
- **Source** : `../data/Rapports_LSC.docx` (4 rapports, compilation). `.docx` illisible
  par PyMuPDF → confrontation au **texte indexé** (ce que le modèle a vu) :
  `results/documents/20260616_192819_0da4_Rapports_LSC.pdf/structure.json`
  (champ `text` balisé `<page_N>` ; champ `summary` = fiche par pièce).
- **Voie / aiguillage** : décomposition = 1 ; **global_summary** (overview) sur les
  **4 fiches** des pièces racines mobilisées (`::0000`, `::0014`, `::0022`, `::0029`).
  Pas de map-reduce. Citations détectées : pages [1, 3, 6, 8].
- **Note globale** : **15/20** — réponse **fidèle** aux 4 fiches, couverture complète des
  4 rapports et bonne polarité avis favorables/défavorables ; la qualité est plafonnée par
  deux faits **non imputables à la rédaction** : (a) un **chevauchement de l'index** (la
  pièce `0000` recouvre matériellement `0014` et `0022`), qui fait **décrire deux fois**
  Hassan et Gonzalez ; (b) un mot de **fiche** dévié du source (« demi‑liberté » au lieu
  de « semi‑liberté »), repris tel quel.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🟡 données / index | moyen | **Double description** de Karim HASSAN (sous « rapport 18 sept. » ET « rapport 5 juil. ») et de Diego GONZALEZ (sous « rapport 18 sept. » ET « avis 22 juin »). Vient de l'**index**, pas de la rédaction : la pièce racine `0000` (« 18 sept., p. 1‑7 ») contient en réalité Girard (p. 1‑2), Hassan (p. 3‑5) et Gonzalez (p. 6‑7), **les mêmes pages** que les pièces séparées `0014` (p. 3‑5) et `0022` (p. 6‑7). La réponse reproduit fidèlement les 4 fiches. | `0000` couvre pages {1..7} et contient GIRARD/HASSAN/GONZALEZ ; `0014` = {3,4,5} HASSAN ; `0022` = {6,7} GONZALEZ ; chevauchement réel des `<page_N>`. |
| 2 | 🔴 app (fiche) | mineur | « hébergement en **demi**‑liberté au Secours catholique de Bordeaux » (rapport 27 juil., Ouali). Le source dit **« semi‑liberté »** (0 occurrence de « demi‑liberté » dans tout le fichier, 7 de « semi‑liberté ») et « Domiciliation au secours catholique de BORDEAUX ». Le mot « demi‑liberté » a été **introduit par la fiche `0029`** (« hébergement en demi‑liberté ») puis recopié par la rédaction. Déviation app au stade fiche. | Pièce `0029` texte : « ✔ Centre ou quartier de **semi‑liberté** » ; « Domiciliation au **secours catholique de BORDEAUX** ». Fiche `0029` : « hébergement en **demi‑liberté** au Secours catholique ». |
| 3 | 🔵 connu | — | Pages citées en **plages** (« page 1‑7 », « 3‑5 », « 6‑7 », « 8 ») = pages **physiques** des sous‑arbres mobilisés, cohérentes avec la segmentation de l'index. Convention page physique (≠ folio) attendue. | Spans calculés : `0000`→1‑7, `0014`→3‑5, `0022`→6‑7, `0029`→8(‑9). |
| 4 | 🔵 connu | — | Voie **overview** (fiches, sans relire le texte) : survol assumé. Les détails fins (n° d'écrou, dates de naissance, quantums) présents dans les fiches ne sont pas tous repris — comportement normal d'un résumé global. | — |

## Vérification factuelle (claim par claim)

Tous vérifiés **conformes** au texte indexé :

- **Hugo GIRARD** : consommateur de cannabis, projet de réinsertion en **logistique**,
  **libération conditionnelle envisagée**. Source (pièce `0000`) : « consommation
  quotidienne de cannabis à hauteur de 3 joints », « réintégrerait son emploi en
  logistique », « Mr envisage une libération conditionnelle ». ✓
  (Nuance fidèle : le SPIP propose en fait une DDSE — la réponse rend « ce que le
  détenu envisage », pas une affirmation de décision.)
- **Karim HASSAN** : marocain, **récidiviste pour vol**, **SDF**, cannabis,
  **avis défavorable** ; rapport 5 juil. = **révocation de deux sursis**, emploi
  **non déclaré** (peintre), **incident du 2 juil. 2025** (détention/trafic/objets
  interdits). Source (`0014`) : « révocation d'un sursis… VOL… récidive » ×2,
  « peintre », « CRI… relevé le 02/07/2025 pour… détention, trafic, introduction
  d'objets interdits », « AVIS : DEFAVORABLE ». ✓
  (« possession » ≈ « détention » : paraphrase fidèle, pas guillemetée.)
- **Diego GONZALEZ** : condamné **2023** pour **conduite sous influence de
  stupéfiants**, semi‑liberté / DDSE envisagée, **hébergement chez sa sœur**.
  Source (`0022`) : « TC Toulouse **18/07/2023**… CONDUITE… SOUS USAGE DE…
  STUPEFIANTS », « ✔ Hébergement chez un tiers : **chez sa sœur** ». ✓
- **Rayan OUALI** : **6 mois** pour **violences dans les transports**, SDF, LSC
  possible, Secours catholique de Bordeaux. Source (`0029`) : « jugement… 03/06/2025…
  TC BORDEAUX… **VIOLENCE DANS UN MOYEN DE TRANSPORT**… : **6 mois** d'emprisonnement »,
  « secours catholique de BORDEAUX ». ✓

## Couverture et contamination

- **Couverture des 4 rapports** : complète — les 4 pièces racines sont chacune
  résumées (18 sept., 5 juil., 22 juin, 27 juil.).
- **Polarité avis** : correcte — favorables **Girard, Gonzalez, Ouali** / défavorable
  **Hassan**, conclusion explicite et conforme aux fiches/texte.
- **Contamination inter‑rapports** : **aucune introduite par la rédaction**. Aucune
  personne n'est attribuée à un mauvais rapport ; le seul recouvrement (Hassan/Gonzalez
  décrits deux fois) provient du **chevauchement de l'index** (constat #1), pas d'une
  erreur d'attribution de la réponse.
- **Exhaustivité / absence** : la réponse n'affirme **aucune** clôture (« aucun autre… »)
  — règle de grounding respectée.
- **Guillemets** : la réponse n'emploie pas de verbatim guillemeté → pas de faux verbatim.

## Analyse par section / facette

La réponse est un **résumé global sur fiches** (overview). Sur ce mode, elle est
exemplaire en fidélité : chaque fait repris est traçable au texte source, la polarité
des avis est exacte, et le grounding (pas d'exhaustivité, pas de faux verbatim) est
respecté. La principale faiblesse perçue — « le même détenu apparaît dans deux
rapports » — n'est **pas un défaut de rédaction** mais le reflet d'un **index
chevauchant** : la pièce racine `0000` a été segmentée comme couvrant tout le
document (p. 1‑7) tout en coexistant avec des pièces séparées pour les sous‑documents
(p. 3‑5 et p. 6‑7). Une synthèse sur fiches **ne peut pas** déduire ce recouvrement et
le restitue donc en doublon. Second point : le mot « demi‑liberté » est une **dérive
de la fiche `0029`** (le source dit « semi‑liberté »), fidèlement recopiée — défaut au
stade indexation/fiche, pas au stade réponse.

## Corrections proposées (🔴 uniquement)

- **Constat #2 (fiche `0029`, « demi‑liberté »)** : c'est le seul 🔴, et il est au
  niveau **génération de fiche**, pas de la rédaction. Piste minimale : surveiller, dans
  le prompt de fiche (`generate_summaries_for_structure`), la substitution
  « semi‑liberté » → « demi‑liberté » (terme juridique distinct). Aucune action sur la
  voie de réponse n'est justifiée : elle a fidèlement repris la fiche.
- **Constat #1 (index chevauchant)** : 🟡 — relève de la **segmentation** du `.docx`
  (la pièce `0000` recouvre `0014`/`0022`). À traiter, le cas échéant, côté découpage
  des pièces à l'indexation ; ne **pas** corriger la rédaction, qui est fidèle aux
  fiches qu'on lui a données.

---

### Résumé

Réponse **fidèle et bien couvrante** (4 rapports, polarité favorable/défavorable
correcte, aucune contamination introduite, aucun faux verbatim, aucune affirmation
d'exhaustivité). **Note 15/20.** Deux limites **non imputables à la rédaction** :
(1) 🟡 un **index chevauchant** — la pièce `0000` recouvre matériellement `0014` et
`0022` — qui fait décrire **deux fois** Hassan et Gonzalez ; (2) 🔴 mineur au stade
**fiche** : « demi‑liberté » (fiche `0029`) là où le source dit « semi‑liberté »,
recopié tel quel. Toutes les autres affirmations factuelles (noms, dates, infractions,
quantums, hébergements, avis) sont vérifiées conformes au texte indexé.
