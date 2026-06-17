# Évaluation — Synthèse_2026 (run map-reduce, seuil forcé bas) — 2026-06-17

- **Question** : « Détaille les principales recommandations du rapport et les constats chiffrés sur lesquels elles s'appuient, pour l'accès aux soins, les mobilités et le numérique. »
- **Document source** : `/Users/stephaneleroi/Dev/demo_pageindex/data/Synthèse_2026.pdf` (114 pages physiques).
- **Voie / aiguillage** : voie corpus, **map-reduce ciblé** (le document unique est traité en pièces de niveau 1). Seuil de bascule **forcé bas** → le *map* (`_focused_summary`) a reçu un texte de pièce **tronqué**. Trois pièces mobilisées : `node_0003` (Première partie, accès aux services), `node_0009` (Deuxième partie, développement des territoires). Citations produites au format `(node_id, page N)`.
- **Note globale** : **16/20** — réponse très fidèle au texte (tous les chiffres et toutes les recommandations vérifiés exacts à la page près), pénalisée par **une affirmation d'exhaustivité interdite** (🔴) et des **attributions de node/pages incohérentes avec l'arbre indexé**, ces dernières largement imputables au test (seuil forcé) et à la fiche d'indexation, pas à la rédaction.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | Moyenne | Affirmation d'**exhaustivité/absence** : « Aucun autre chiffre précis n'est fourni dans le texte concernant l'usage ou la pénétration du numérique au-delà de ces indicateurs. » Viole la règle de grounding n°3. De plus c'est **faux** : la p. 68 porte d'autres chiffres numériques (22 Md€ investis fibre 2010-2024 ; 93,5 % de locaux raccordables au 30 sept. 2025 ; 18 départements couverts par un schéma de résilience numérique au 1er août 2025). | p. 68 (chiffres clés numérique) |
| 2 | 🔴 app | Faible | Gloss interprétatif ajouté par la rédaction : « 215 800 personnes … en zone blanche (**absence de couverture Internet**) ». Le source dit « zone blanche » sans préciser « Internet », et la p. 69 rattache la zone blanche à la **couverture mobile** (« la part du territoire en zone blanche a diminué de 11 % à 2 % »), pas à l'Internet fixe. Surinterprétation. | p. 68 (« 215 800 personnes résident encore en zone blanche ») ; p. 69 (zone blanche = mobile) |
| 3 | 🟡 données / app | Faible | **Attribution node/pages incohérente avec l'arbre indexé.** Les chiffres accès-aux-soins sont attribués à `node_0003, page 20-22` et les chiffres mobilités/numérique à `node_0009, page 54-56-58` et `68-69`. Or le **texte** stocké de `node_0003` ne couvre que les pages 15-19 et celui de `node_0009` que 49-53 ; les pages 20-22 / 54-58 / 68-69 ne figurent dans **aucun** nœud de l'arbre (29 pages indexées sur 114). Les chiffres proviennent en réalité des **fiches** (résumés de pièces) qui, elles, portent déjà ces pages. Le `node_id` accolé est donc la pièce de rattachement, pas le nœud contenant le texte. Non trompeur (les pages physiques citées sont justes), mais le couple (node, page) n'est pas strictement cohérent. | Arbre indexé : `…/structure.json` et `Synthèse_2026.pdf.pageindex.json` (texte node_0003 = pages 15-19, node_0009 = 49-53) ; fiches portant les pages : `node_0009.summary` (« 50 % … (p.53) … 92 % … 215 800 … (p.68-69) ») |
| 4 | 🔵 connu | — | **Page physique ≠ folio imprimé.** Toutes les pages citées sont des **pages physiques PDF** et tombent juste ; le folio imprimé est décalé de +2 (p. physique 20 = folio « 22 », p. 54 = folio « 56 », p. 68 = folio « 70 »). Comportement attendu, pas une erreur. | p. 20 (pied « 22 ») ; p. 54 (pied « 56 ») ; p. 68 (pied « 70 ») |
| 5 | 🔵 connu | — | **Omissions de constats** (sécurité, emploi, réindustrialisation présents dans la fiche node_0009 ; chiffres p. 68 ci-dessus). Attendu : run map-reduce **à seuil forcé bas** → texte des pièces tronqué au *map* ; la couverture des constats chiffrés est mécaniquement réduite. À ne pas imputer à la rédaction (sauf le constat #1, où l'omission est *affirmée comme exhaustive*). | Consigne du test (seuil forcé) ; fiche node_0009 (sécurité 24,4 Md€, 28 000 policiers municipaux…) |

## Vérification des faits cités (tous CONFORMES au texte source)

Accès aux soins — **node_0003 → pages physiques 20-22** :
- 2 380 sites hospitaliers en 2023 ✓ (p. 20) ; 75 % à ≤ 43 km / 48 min en 2024 ✓ (p. 20) ; obstétrique 25 km/33 min, transplantations 119 km/1 h 36 ✓ (p. 20/21) ; 44 spécialités « contre huit en 1947 » ✓ (p. 20) ; 25 M de patients chroniques en 2023, +7 % depuis 2015, ~126 Md€ ✓ (p. 20) ; déficit hôpitaux publics 2,4 Md€ ✓ (p. 20).
- Recommandations : groupements à direction commune, gradation des soins / hôpitaux de proximité mieux financés, association des collectivités (ex. reconversion de maternité), structuration des filières malgré le manque de personnel ✓ (p. 21-22).

Mobilités — **node_0009 → pages physiques 54-56 et 58** :
- 50 % des communautés de communes AOML ✓ (p. 54/55) ; > 70 % sans choix de mode ✓ (p. 54/56) ; 30 % des jeunes ruraux renoncent ✓ (p. 54) ; +7,7 % d'offre 2019-2023 ✓ (p. 54/56) ; 12,8 M de trajets covoiturage 2024, ×8 vs 2021 ✓ (p. 54) ; 184 141 bornes fin nov. 2025 ✓ (p. 54) ; deux tiers du financement public, 35,6 Md€ courantes + 21 Md€ investissements 2023, +17 % vs 2019 ✓ (p. 56) ; besoin 3,7-6,7 Md€/an (Ambition France Transports) ✓ (p. 56).
- Recommandations : contrats opérationnels de mobilité + plans mobilité solidaire ; clarifier dispositifs syndicats mixtes/conventions ; priorité régénération + trajets du quotidien ; loi-cadre suite LOM ✓ (les 4 recommandations sont **mot pour mot** p. 58).

Numérique — **node_0009 → pages physiques 68-69** (recos via node_0003 p. 17) :
- 92 % des locaux raccordables fibre fin mars 2025 ✓ (p. 69) ; 91 % des Français > 12 ans avec smartphone ✓ (p. 68) ; 215 800 personnes en zone blanche ✓ (p. 68, cf. constat #2 sur le gloss « Internet »).
- Recommandations : accompagner le déploiement (numérique = symbole d'éloignement, surtout en rural) ; coordination acteurs publics/bailleurs pour le SNE ✓ (p. 17).

Aucun **faux verbatim** : la réponse ne place pas de guillemets sur des paraphrases (citations chiffrées sans guillemets).

## Analyse par section / facette

- **Fidélité factuelle : excellente.** Sur ~30 constats chiffrés et 10 recommandations, **aucune erreur de valeur, de date ou d'unité** ; les recommandations mobilités sont reprises au plus près du texte (p. 58). La rédaction a même préféré la valeur la plus précise du source (2 380 sites, p. 20) à l'arrondi de la fiche (« 2 500 »).
- **Origine réelle des chiffres.** Le texte des nœuds de l'arbre ne contient PAS les pages des chiffres clés (pages 20-22, 54-58, 68-69 absentes de l'index). Les chiffres et leurs `(p. N)` proviennent des **fiches d'indexation** des pièces (`summary`), déjà riches et déjà paginées. C'est ce qui explique à la fois la justesse des pages physiques et l'incohérence node↔page (constat #3).
- **Effet du seuil forcé bas (test).** La troncature du *map* explique la couverture limitée des constats (sécurité, emploi, et les chiffres p. 68 non repris) : limite de test, non imputable à la rédaction — sauf le #1, où l'omission est transformée en affirmation d'exhaustivité, ce qui est un défaut de rédaction réel.
- **Citations à la page.** Bien présentes et vérifiables, conformément à la fonctionnalité centrale. Le seul accroc est la cohérence node↔page, atténuée par le fait que les pages physiques sont, elles, exactes.

## Corrections proposées (🔴 uniquement)

- **#1 (exhaustivité)** : supprimer la phrase « Aucun autre chiffre précis n'est fourni … au-delà de ces indicateurs. » et, si une clôture est souhaitée, la remplacer par une formulation non exhaustive (« sur la base des extraits mobilisés »). C'est le levier d'amélioration principal de la note.
- **#2 (gloss « Internet »)** : retirer le parenthétique interprétatif « (absence de couverture Internet) » ou le remplacer par « (zone blanche) » sans surqualifier le type de couverture, le source rattachant la zone blanche à la couverture mobile (p. 69).

(Les constats #3/#4/#5 ne donnent pas lieu à correction de rédaction : #4 et #5 sont des comportements attendus ; #3 relève de l'arbre/des fiches et de la consigne de test, pas d'un écart de la rédaction au source.)

---

**Résumé.** Réponse remarquablement fidèle : la totalité des chiffres et des recommandations des trois sections sont exacts à la page physique près (vérifiés sur pages 17, 20-22, 54-56, 58, 68-69 du PDF). Deux vrais défauts de rédaction seulement : une affirmation d'exhaustivité interdite et factuellement fausse pour le numérique (🔴, la p. 68 contient d'autres chiffres), et un gloss « absence de couverture Internet » que le source ne dit pas (🔴 mineur). L'incohérence node↔page et les omissions de constats relèvent des fiches d'indexation et du seuil de bascule forcé bas du test (29 pages sur 114 indexées en texte) — non imputables à la rédaction. Note : 16/20.
