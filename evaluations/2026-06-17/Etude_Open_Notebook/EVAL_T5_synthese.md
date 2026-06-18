# Évaluation — T5 / Synthèse_2026 (map-reduce forcé 2000) — 2026-06-17

- **Question** : Détaille les principales recommandations du rapport et les constats chiffrés sur lesquels elles s'appuient, pour l'accès aux soins, les mobilités et le numérique.
- **Source** : `../data/Synthèse_2026.pdf` (114 pages, document unique, Cour des comptes — RPA).
- **Voie / aiguillage** : voie corpus, **décomposition** (2 indices) → 2 pièces retenues (node_0003 « PREMIÈRE PARTIE », node_0009 « DEUXIÈME PARTIE »), pièces volumineuses (5 + 2 sous-sections) → **map-reduce ciblé** déclenché (2 pièces = 84 907 car. > budget **forcé 2000** → fiche à chaud par pièce, puis reduce). Le texte de chaque pièce a donc été **tronqué au map**.
- **Note globale** : **15/20** — réponse globalement fidèle et bien sourcée à la page physique (tous les chiffres vérifiés exacts, aucune citation de page fausse, aucun faux verbatim), entachée d'**un seul vrai défaut app** : une **affirmation d'absence** sur le numérique (« ne formule pas de recommandation explicite »), interdite par les règles de grounding, alors que le rapport formule cinq recommandations numériques explicites (p. 72). La cause profonde (n'avoir pas *vu* ces recommandations) est un artefact de la troncature à 2000 ; mais **conclure à l'absence** sur un contexte tronqué est le défaut imputable.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | Majeure | « Concernant le numérique, le rapport **ne formule pas de recommandation explicite** […] **aucune mesure précise n'est proposée** dans la synthèse étudiée. » → fausse **affirmation d'absence** (viole §3 grounding : ne jamais affirmer exhaustivité/absence sur un contexte possiblement partiel). Le rapport formule **cinq recommandations numériques explicites**. | p. **72** : « La Cour formule **cinq recommandations** à mettre en œuvre dès 2026 : 1. identifier les zones sans accès à la fibre… 4. inciter les collectivités à établir des schémas de résilience numérique… ». Section numérique = node 0012 (p. 67-73), donc dans le périmètre de node_0009. |
| 2 | 🔵 connu | — | **Omission** des recommandations formelles (blocs « Recommandations » numérotés) pour les **trois** thèmes : soins (p. 25, 31), mobilités (p. 58), numérique (p. 72). L'app a reconstruit des « recommandations » à partir du **texte narratif / chiffres clés** vus en début de section. Ces pages-recommandations tombent **au-delà de la fenêtre de 2000 car./pièce** du *map* → omission = **artefact du seuil forcé**, pas un défaut de rédaction. | Blocs « La Cour formule les recommandations suivantes » localisés p. 29, 35, 42, **58**, 65, **72**, 83, 94, 99, 112 (grep). |
| 3 | 🔵 connu | — | Citations `(p. N)` = **page physique du PDF** (≠ folio imprimé). Ex. « page 20 » porte en folio imprimé « 22 », « page 53 » → folio « 55 ». **Aucune erreur** : les faits sont bien sur la page **physique** citée. | p. 20 (folio 22), p. 53 (folio 55), p. 72 (folio 74). Convention attendue (visionneuse). |
| 4 | 🟡 / mineur | Mineure | « 12,8 millions de **trajets intermédiaires** en 2024 » — léger reformulage ; le source dit « trajets en **covoiturage intermédié** ». Sens préservé (covoiturage organisé via plateforme), pas d'erreur factuelle ; simple appauvrissement du libellé. | p. 54 : « 12,8 millions de trajets en covoiturage **intermédié** en 2024, soit huit fois plus qu'en 2021 ». |

## Vérification des constats chiffrés (tous EXACTS)

**Accès aux soins** (cités node_0003, p. 20-21) — page physique 20-21 :
- 2 380 sites hospitaliers en 2023 ✓ ; 75 % à ≤ 43 km (~48 min) ✓ ; transplantations 119 km (1 h 36) ✓ ; obstétrique 25 km (33 min) ✓ (la réponse écrit « urgences obstétricales » ; source = « obstétrique » — nuance acceptable).
- 44 spécialités « contre huit en 1947 » ✓ ; 25 M de patients maladies chroniques en 2023, +7 % depuis 2015, ~126 Md€ ✓ ; 26 GHT sur 135 (≈19 %) en direction commune ✓ ; déficit hôpitaux publics 2,4 Md€ en 2023 ✓.

**Mobilités** (cités node_0009, p. 53-55) :
- LOM = loi du 24 décembre 2019, à compléter par un « cadre financier rénové » priorisant les trajets du quotidien ✓ (p. 53, verbatim de fait correct, sans guillemets abusifs).
- 50 % des communautés de communes / intercommunalités sont AOML ✓ (p. 54 chiffre clé + p. 55 narratif).
- > 70 % des résidents ruraux/périurbains sans choix de mode ✓ ; 30 % des jeunes ruraux ont renoncé à se rendre sur leur lieu d'étude ✓ ; 184 141 bornes de recharge publiques fin nov. 2025 ✓ ; +7,7 % d'offre kilométrique TC 2019-2023 ✓ ; covoiturage ×8 vs 2021 ✓ (tous p. 54).

**Numérique** (cités node_0009, p. 68-69) :
- 91 % des > 12 ans avec smartphone ✓ (p. 68) ; 215 800 personnes en zone blanche ✓ (p. 68) ; 92 % des locaux raccordables à la fibre ✓ (p. **69** : « Fin mars 2025, 92 % des 44,8 M de locaux… »). NB : la chiffre-clé p. 68 affiche 93,5 % au 30/09/2025 ; l'app a retenu le 92 % du narratif p. 69 — les deux figurent au source, citation « 68-69 » **correcte**.

**Guillemets** : la réponse n'emploie **aucun guillemet** → **aucun faux verbatim** possible. ✓

## Analyse par section / facette

- **Fidélité chiffrée** : excellente. 100 % des nombres, distances, durées, pourcentages et années sont retrouvés à l'identique sur la page physique citée. Aucune contamination inter-section, aucune inversion de rôle, aucun nombre halluciné.
- **Citations page** : toutes justes (page physique), conformes à la convention 🔵. Les `(p. N)` ont bien été conservées à travers le map-reduce — condition de viabilité respectée.
- **Couverture « recommandations »** : limitée par la troncature à 2000 car./pièce. L'app a su livrer des recommandations substantielles pour soins et mobilités à partir du narratif vu, mais **n'a pas atteint** les blocs « Recommandations » formels (au-delà de la fenêtre). C'est le comportement attendu d'un map tronqué (🔵) — sauf qu'au lieu de signaler une couverture partielle pour le numérique, elle a **affirmé l'absence** (constat #1, 🔴).
- **Pourquoi 🔴 et non 🔵 pour le numérique** : l'omission est 🔵 (troncature) ; mais la **règle de grounding §3** interdit explicitement d'affirmer « ne formule pas / aucune mesure ». Le rédacteur aurait dû écrire « la synthèse étudiée ne détaille pas de recommandation numérique » ou « non couvert par le contexte », et non nier l'existence. Sur un contexte tronqué, l'affirmation d'absence est précisément le piège que les consignes proscrivent.

## Corrections proposées (uniquement pour le 🔴, #1)

1. **Renforcer l'anti-exhaustivité dans le *reduce* du map-reduce.** Le gabarit de rédaction (grounding) interdit déjà l'affirmation d'absence, mais le map-reduce expose le rédacteur à un contexte sciemment partiel. Ajouter au prompt *reduce* (ou à `_build_answer_prompt` en mode map-reduce) un rappel ciblé : « Le contexte par pièce est **tronqué** (fiche à chaud) ; n'affirme jamais qu'un élément est *absent* ou *non formulé* — au plus, signale qu'il n'apparaît pas dans l'extrait étudié. » Modification minimale, dans `services/prompts/*.jinja` (gabarit *map*/*reduce*), sans toucher au paradigme.
2. **(Hors app, non actionnable)** Le défaut de fond — ne pas avoir vu les pages 72 (et 25, 31, 58) — disparaît dès que le budget n'est plus forcé à 2000 : c'est l'artefact du test signalé dans la consigne. Aucune action sur le code à ce titre.

Rien à corriger pour #2, #3 (🔵) ni #4 (🟡/mineur, fidélité de sens préservée).
