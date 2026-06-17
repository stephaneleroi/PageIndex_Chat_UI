# Évaluation — T5 / Synthèse_2026 (detail / lecture directe) — 2026-06-17

- **Question** : Détaille les principales recommandations du rapport et les constats chiffrés sur lesquels elles s'appuient, pour l'accès aux soins, les mobilités et le numérique.
- **Source** : `../data/Synthèse_2026.pdf` (114 p.), rapport public annuel de la Cour des comptes.
- **Voie / aiguillage** : décomposition (2 indices), voie corpus **detail** (lecture directe du texte). Le map-reduce **ne s'est PAS déclenché** malgré le budget forcé à 2000 : le `tree_search` a retenu 2 pièces (Partie I « accès aux services », Partie II « développement des territoires »), drill-down → 5 + 3 sections lues directement. 7 nœuds mobilisés, 26 citations (pages 20, 23, 26, 27, 29, 44, 47, 54, 56, 58, 68, 72). On juge donc en **fidélité de lecture** (exigence haute).
- **Note globale** : **15,5/20** — réponse globalement très fidèle et bien structurée (constats chiffrés + recommandations vérifiés un à un), mais **un passage numérique fabrique une comparaison année-sur-année que le source ne porte pas** (🔴) et **une citation de page est fausse** (🔴). Les autres écarts de page sont des approximations d'ancrage (facts présents à ±1 page).

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | majeur | Bloc fibre : « 92 % … raccordables **en 2025** (p. 68), **contre 93,5 % en 2024** (p. 68) ». Le source ne fait **aucune comparaison 2025 vs 2024** et **ne date pas 93,5 % de 2024**. Page 68 : « **93,5 %** de locaux raccordables à la fibre optique **au 30 septembre 2025** » ; le « 2024 » de la page se rapporte aux « **22 Md€** investis … **de 2010 à 2024** ». L'app a recollé le millésime 2024 au taux 93,5 % et inventé une dynamique en baisse (92 % vs 93,5 %) inexistante dans le texte. | p. 68 (chiffres clés : 93,5 % au 30/09/2025 ; 22 Md€ 2010-2024) |
| 2 | 🔴 app | mineur | « 92 % des **44,8 millions** de locaux … raccordables (page 68) » : la phrase exacte (« Fin mars 2025, 92 % des 44,8 millions de locaux sont raccordables ») est sur la **page physique 69**, pas 68. Citation de page fausse (≠ simple décalage folio). | p. 69 (texte) ; var. p. 50 |
| 3 | 🟡 / ancrage | mineur | Recommandations Outre-mer 5 (expérimentations art. 51) et 6 (télémédecine archipels) citées « (page 29) » alors qu'elles sont sur la **page 30** (les rec. 1-4 sont bien p. 29). Le fait existe, page voisine. | p. 30 |
| 4 | 🟡 / ancrage | mineur | Covoiturage « 12,8 millions … huit fois plus qu'en 2021 » rattaché à la page 56 ; le chiffre est dans les chiffres clés **page 54** (la p. 56 ne porte que le +7,7 %, qui lui est bien sur 54 ET 56). | p. 54 |
| 5 | 🟡 / ancrage | mineur | Difficultés « principalement liées à la littératie numérique et à la complexité du langage administratif » données (page 44) ; ce développement est le texte de la **page 45** (la p. 44 ne porte que les chiffres clés). Paraphrase fidèle du source. | p. 45 (« lecture, écriture, complexité du langage administratif … compétences numériques insuffisantes ») |

## Vérifications de fidélité (tout confirmé au source)

**Accès aux soins – maillage (p. 20)** : 2 380 sites (2023), 75 % à ≤43 km / ~48 min, 25 km obstétrique / 119 km transplantations, 44 spécialités (vs 8 en 1947), 25 M malades chroniques (+7 % depuis 2015, ~126 Md€), 26/135 GHT en direction commune, déficit 2,4 Md€ — **tous exacts**. Recommandations p. 23 (fusion GHT, stratégie nationale gradation, qualité des parcours, FIR recentré, autorisations multisites, échéance 2028) — **exactes**.

**Accès aux soins – Outre-mer (p. 27, 29-30)** : 34,6 % pauvreté (vs 15,4 % métropole, 2023), densité 8-90 vs 84/100 000, cardiologie 42 j vs 26 j — **exacts**. Les 6 recommandations (plateforme données 2027, postes partagés, filières locales, instances inter-régionales, art. 51, télémédecine) — **exactes**, ancrage 5-6 sur p. 30 (cf. constat 3).

**Mobilités (p. 54, 56, 58)** : 50 % des communautés de communes AOML, >70 % rural sans offre diversifiée, 30 % jeunes ruraux ayant renoncé, +7,7 % offre km 2019-2023, 12,8 M covoiturage 2024 (×8 vs 2021), 184 141 bornes fin nov. 2025 — **exacts**. Les 4 recommandations p. 58 (contrats opérationnels + mobilité solidaire, syndicats mixtes, régénération réseaux, loi-cadre 2027) — **exactes**.

**Numérique – services publics (p. 44, 45, 47)** : 32 % renoncé ≥1 fois, 8 % définitivement, 1,3 Md démarches/an (dont 506 M CNAF/CNAV/DGFiP), 73 % sur 12 mois, 44 % en difficulté — **exacts**. Les 3 recommandations p. 47 (vision consolidée budgets, feuilles de route opérationnelles, France services détection/orientation) — **exactes**.

**Numérique – très haut débit (p. 68, 72)** : 215 800 en zone blanche, 22 Md€ 2010-2024, 91 % smartphone (>12 ans), 18 départements schéma de résilience (1er août 2025) — **exacts**. Les 5 recommandations p. 72 (identifier zones sans fibre/mobile, contrôle débits ARCEP/DGCCRF, intégration crise, schémas de résilience, études qualitatives, dès 2026) — **exactes**. Seul le couple 92 %/93,5 % est mal traité (constats 1-2).

## Analyse

Réponse de bonne tenue pour une lecture directe : la structure (3 domaines × constats chiffrés + recommandations) est conforme à la question, les recommandations sont reproduites quasi mot pour mot et toutes les échéances sont justes. Les chiffres clés sont fidèles sur 4 des 5 pages de « Chiffres clés ».

Le seul **vrai défaut de rédaction** (🔴 #1) est l'invention d'une comparaison « 2025 vs 2024 » sur la fibre : le rédacteur a vu deux taux proches (92 % fin mars 2025 p. 69, 93,5 % au 30 sept. 2025 p. 68) et le millésime « 2024 » (qui appartient aux 22 Md€ d'investissement), et en a tiré une baisse year-over-year que le texte ne formule jamais. C'est exactement le type d'inférence non autorisée que le grounding proscrit. Le 🔴 #2 (page 68 au lieu de 69) est une citation fausse — pas un décalage folio, mais un renvoi à la mauvaise page physique.

Les constats 3-5 sont des **approximations d'ancrage** d'un point (les rédacteurs regroupent plusieurs chiffres sous une seule page voisine) : les faits sont bien présents, à ±1 page. À distinguer du décalage folio (🔵 connu, non compté) : ici le folio imprimé est systématiquement « page physique + 2 » (p. 20 → folio 22, p. 68 → folio 70), et l'app cite bien la page physique, conforme à la visionneuse.

Aucune hallucination de fait, aucune inversion de rôle, aucune affirmation d'exhaustivité abusive, aucun faux verbatim (la réponse ne met pas de guillemets sur les paraphrases).

## Corrections proposées (🔴 uniquement)

- **#1** : reformuler le bloc fibre sans comparaison temporelle non sourcée — p. ex. « 93,5 % des locaux raccordables à la fibre au 30 septembre 2025 (p. 68) ; 92 % des 44,8 millions de locaux raccordables fin mars 2025 (p. 69) » ; ne pas dater 93,5 % de 2024 (le 2024 = bornes des 22 Md€ d'investissement 2010-2024).
- **#2** : corriger l'ancrage de la phrase « 92 % des 44,8 millions de locaux » → page 69.

Les écarts 3-5 (🟡) ne sont pas imputables à un manquement de fidélité : facts exacts, page voisine ; pas de correction nécessaire au-delà d'un éventuel resserrement de l'ancrage.
