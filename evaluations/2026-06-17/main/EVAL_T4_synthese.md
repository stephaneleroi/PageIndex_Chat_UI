# Évaluation — T4 — Synthèse résumé [main] — 2026-06-17

- **Question** : « Fais moi un résumé »
- **Voie / aiguillage** : `global_summary` / **overview** (agrégation de 6 fiches de
  nœuds-parties, sans relire le texte). Pas de map-reduce, pas de décomposition
  (1 indice). Nœuds mobilisés = en-têtes de grandes sections (node_0000 Préface,
  0002 Chapitre introductif, 0003 1re partie, 0009 2e partie, 0015 3e partie).
  C'est exactement la voie attendue pour une question de résumé : survol assumé.
- **Note globale** : **17/20** — résumé fidèle, dense et bien structuré ; tous les
  chiffres vérifiés existent dans le source ; un seul vrai défaut, mineur : une
  donnée (bornes de recharge) citée sous une plage de pages erronée. Aucune
  hallucination, aucun faux verbatim (aucun guillemet de citation employé).

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | mineure | « 184 141 bornes de recharge publiques fin novembre 2025 » cité **(node_0009, page 68‑69)** alors que le chiffre est physiquement **page 54**. Le node est correct (la 2e partie couvre p.49‑81), mais la plage de pages affichée est fausse (~14 pages d'écart). | Synthèse_2026.pdf **p.54** : « 184 141 … bornes de recharge publiques … fin novembre 2025 ». p.68‑69 ne contiennent pas ce chiffre. |
| 2 | 🔵 connu | — | « 50 % des intercommunalités devenues AOM locales » cité (page 53‑54) ; la donnée « 50 % » figure p.54 (communautés de communes) **et** p.55 (intercommunalités AOML). Décalage d'1 page, attendu en overview. | p.54 « 50 % des communautés de communes… » ; p.55 « 50 % des intercommunalités sont devenues AOML ». |
| 3 | 🔵 connu | — | « système de paiement aux agents le 1er mai » (page 113) : c'est un **courrier d'un directeur de la comptabilité** appendu en fin de PDF (corps étranger au rapport de la Cour). L'app le restitue fidèlement et cite la bonne page. Artefact du source, pas une invention. | OCR node 0019 `<page_113>` : « Le 1er mai … nouveau "Système de paiement aux agents" mis en place par le Secrétariat général ». |
| 4 | 🔵 connu | — | Citations « plage de pages » (8‑10, 11‑13, 16‑20, 23‑31, 53‑54, 80‑81, 90‑92, 101‑108) au lieu d'une page unique : conséquence de la synthèse sur fiches de sections ; les faits tombent bien dans les plages. | (voir vérifs ci-dessous) |

## Vérification des faits (tous tracés au source)

Faits contrôlés un à un (`verif_source.py page/grep`) — **tous présents et exacts** :

- p.1 titre « Rapport public annuel 2026 / Cohésion territoriale et attractivité » ✔
- p.8 (chiffres clés) : 23 départements 2015‑2021 ✔ ; PIB 69 288 € (IDF) / 32 652 €
  (Bourgogne‑FC) ✔ ; **RNB** 27 060 € / 19 509 € ✔ (la réponse écrit « revenu
  disponible brut » ; le source dit « revenu disponible brut (RNB) » — fidèle) ;
  FRR 57 % ✔ ; crédits UE 16,8 Md€ 2021‑2027 ✔.
- p.12 mission Cohésion des territoires 18,5 Md€ en 2024 ✔ (cité sous 11‑13).
- p.16 « ~2 500 établissements de santé en métropole » ✔.
- p.20 « 75 % des patients hospitalisés à 43 km maximum (2024) » ✔ (cité sous 16‑20).
- p.23 recommandations GHT / stratégie nationale gradation des soins d'ici 2028 ✔.
- p.27 outre‑mer : 34,6 % sous le seuil de pauvreté 2023 ✔ ; 42 jours cardiologie ✔.
- p.31 baisse de 12 % des collégiens à l'horizon 2036 ✔ (cité sous 23‑31).
- p.53 LOM 2019 ✔ ; p.54 « 30 % des jeunes ruraux renoncent » + « plus de 70 % … » ✔.
- p.69 « 92 % des locaux raccordables à la fibre, fin mars 2025 » ✔ ; p.68 smartphone
  91 % ✔, zone blanche 215 800 ✔. (La réponse a retenu le 92 % de p.69, pas le
  93,5 % de p.68 — choix cohérent, pas une erreur.)
- p.80‑81 sécurité : État 24,4 Md€ / +33 % depuis 2016 ✔ ; collectivités 2,3 Md€ /
  +41 % ✔ (p.81) ; 28 000 policiers municipaux 2023 ✔ ; +6,5 % délinquance depuis
  2016 ✔.
- p.86 articulation des politiques sectorielles (CPER/CRTE) ✔.
- p.90‑92 QPV : pauvreté ×3 ✔ ; 524 M€ exécutés 2024 ✔.
- p.95 OIN : 17 en IDF en 2025, 56 projets parmi 1 931 ✔.
- p.108‑109 péréquation verticale 10,2 Md€ / horizontale 4,2 Md€ (2024) ✔ (cité 101‑108).

Aucun chiffre inventé, aucune date fausse, aucune inversion de rôle. Aucun passage
entre guillemets n'est présenté comme verbatim → pas de risque de faux verbatim.

## Analyse par section / facette

La réponse suit fidèlement le plan du rapport (chapitre introductif → 1re/2e/3e
parties → synthèse) et l'attribue correctement aux nœuds‑parties mobilisés. La voie
**overview** fait son travail : elle agrège les « chiffres clés » de chaque section
(qui dans le source portent leur propre page) et les restitue avec leur page. La
seule faiblesse structurelle attendue de cette voie se manifeste au constat #1 : en
synthétisant la fiche de la 2e partie, l'app a accolé le chiffre des bornes (p.54) au
bloc fibre/numérique cité 68‑69, produisant une plage de pages inexacte pour cette
donnée précise. Le node reste correct ; seule la page affichée glisse. C'est
exactement le compromis documenté de l'overview (peut « ordonner approximativement »).

Le constat #3 mérite d'être souligné comme un **bon point** : le source contient un
courrier parasite en p.113 (sans rapport avec le travail de la Cour) ; l'app ne
l'invente pas et ne le maquille pas — elle le rapporte tel quel avec sa page. C'est
de la fidélité, pas une hallucination.

## Corrections proposées

Un seul 🔴, mineur et inhérent à la voie overview (synthèse sur fiches) :

- **Constat #1** — Rien à corriger côté données. Côté app, le seul levier conforme au
  paradigme est l'**amélioration de la fiche** de la 2e partie pour que chaque
  « Point saillant » conserve sa propre `(p. N)` (ici p.54 pour les bornes) plutôt
  qu'une page héritée du bloc voisin. Aucune modification de code de retrieval n'est
  justifiée pour ce seul écart : la note reste excellente et le défaut est cosmétique
  (page off, fait juste, node juste). À surveiller si récurrent sur d'autres résumés.
