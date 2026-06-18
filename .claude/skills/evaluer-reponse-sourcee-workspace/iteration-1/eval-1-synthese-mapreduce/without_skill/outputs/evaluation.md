# Évaluation de la réponse sourcée — Synthèse 2026 (Cour des comptes, RPA)

**Question évaluée :** « Détaille les principales recommandations du rapport et les constats chiffrés sur lesquels elles s'appuient, pour l'accès aux soins, les mobilités et le numérique. »

**Document source :** `data/Synthèse_2026.pdf` (114 pages)

**Réponse évaluée :** `case2_synthese_answer.md`

## Méthode

J'ai extrait le texte des pages citées (et de leurs voisines) avec PyMuPDF, puis confronté chaque chiffre, chaque recommandation et chaque citation de page au texte réel du PDF. Convention de pagination retenue (cf. CLAUDE.md) : `(p. N)` = page **physique** du PDF telle qu'ouverte dans la visionneuse, donc **1-based** (page N = `d[N-1]` en indexation PyMuPDF). Toutes les citations ont été vérifiées sous cette convention.

## 1. Accès aux soins

### Constats chiffrés (réponse → source)

| Affirmation de la réponse | Source réelle | Verdict |
|---|---|---|
| 2 380 sites hospitaliers en 2023 | p. 20 : « 2 380 sites hospitaliers en 2023 » | Exact |
| 75 % des patients à ≤ 43 km (≈ 48 min en voiture) | p. 20 : « 75 % … à 43 kilomètres maximum … en 2024 (48 minutes en voiture environ) » | Exact (la réponse omet « en 2024 », sans conséquence) |
| Obstétrique 25 km (33 min) → transplantations 119 km (1 h 36) | p. 20 : « 25 km (33 min) pour l'obstétrique … 119 km (1 h 36) pour les transplantations » | Exact |
| 44 spécialités aujourd'hui contre 8 en 1947 | p. 20 : « 44 spécialités actuellement (contre huit en 1947) » | Exact |
| 25 M de patients chroniques en 2023 (+ 7 % depuis 2015), dépense ≈ 126 Md€ | p. 20 : « 25 millions … en 2023, soit 7 % de plus qu'en 2015 … dépense d'environ 126 Md€ » | Exact |
| Déficit des hôpitaux publics de 2,4 Md€ | p. 20 : « un déficit des hôpitaux publics de 2,4 Md€ » | Exact |

Tous les chiffres « accès aux soins » sont exacts et correctement localisés (p. 20 = phys. idx 19, la page « Chiffres clés » du chapitre).

### Recommandations (réponse → source)

- (i) « réorganiser le maillage … groupements territoriaux à direction commune » — appuyé sur p. 22 (« fusionner les établissements … d'un groupement hospitalier de territoire ») et p. 21 (« directions communes dans les GHT »). Fidèle.
- (ii) « gradation des soins mieux financée … hôpitaux de proximité » — p. 21 : « gradation des soins … hôpitaux de proximité … missions devraient être mieux financées ». Fidèle.
- (iii) « impliquer les collectivités … reconversion d'une maternité » — p. 22 (idx 21) : « l'association des collectivités territoriales … (par exemple une reconversion de maternité) ». Fidèle.
- (iv) « renforcer la structuration des filières coordonnées … malgré le manque de personnel » — p. 22 : « La structuration des filières coordonnées de soins se heurte … nombre insuffisant de médecins ». Fidèle.

**Citation de pages :** « node_0003, page 20-22 » pour les recommandations et « page 20 » pour les chiffres → **exactes** sous convention 1-based.

**Omission notable :** la page « Chiffres clés » (p. 20) donne aussi « Seuls 26 groupements hospitaliers de territoire sur les 135 … direction commune » — chiffre central qui sous-tend directement la recommandation (i) sur les directions communes. Il n'est pas repris. Par ailleurs, la liste officielle des 4 recommandations datées (p. 23 : stratégie nationale, évaluation des parcours, recentrage du FIR, autorisations multisites) n'est pas reprise telle quelle ; la réponse reformule à partir de la synthèse rédactionnelle (p. 21-22), ce qui reste fidèle mais moins normé que l'encadré « Recommandations ».

## 2. Mobilités

### Constats chiffrés

| Affirmation | Source réelle | Verdict |
|---|---|---|
| 50 % des CC sont AOML | p. 54 : « 50 % des communautés de communes sont autorités organisatrices de la mobilité locale » | Exact |
| > 70 % des ruraux/périurbains sans choix modal | p. 54 / p. 56 : « Plus de 70 % … n'ont pas le choix entre différents modes de transport » | Exact |
| 30 % des jeunes ruraux ont renoncé à se rendre à leur lieu d'étude | p. 54 : identique | Exact |
| + 7,7 % d'offre km de transport collectif 2019-2023 | p. 54 / p. 56 : « + 7,7 % … entre 2019 et 2023 » | Exact |
| 12,8 M trajets covoiturage en 2024, ×8 vs 2021 | p. 54 : « 12,8 millions de trajets en covoiturage intermédié en 2024, soit huit fois plus qu'en 2021 » | Exact (« intermédiaire » dans la réponse au lieu de « intermédié » — coquille mineure) |
| 184 141 bornes de recharge fin nov. 2025 | p. 54 : identique | Exact |
| Collectivités = 2/3 du financement ; 35,6 Md€ courant + 21 Md€ invest. 2023 (+ 17 % vs 2019) | p. 56 : identique | Exact |
| Besoin de financement +3,7 à 6,7 Md€/an (Ambition France Transports) | p. 56 : identique | Exact |

Tous exacts. Citations « page 55-56-54 » → couvrent bien les pages « Chiffres clés » (p. 54) et le corps (p. 55-56). Correct.

### Recommandations

Les quatre recommandations citées correspondent **mot pour mot** à l'encadré « Recommandations » de la p. 58 (contrats opérationnels + plans mobilité solidaire ; clarifier syndicats mixtes/conventions ; priorité régénération + trajets du quotidien ; loi-cadre succédant à la LOM). **Citation « page 58 » exacte.** C'est la partie la mieux traitée : recommandations officielles reprises fidèlement et chiffres tous justes.

## 3. Numérique

### Constats chiffrés

| Affirmation | Source réelle | Verdict |
|---|---|---|
| 92 % des locaux raccordables à la fibre en 2025 | p. 69 : « Fin mars 2025, 92 % des 44,8 millions de locaux sont raccordables à la fibre » | Exact |
| 91 % des Français de + 12 ans ont un smartphone | p. 68 (Chiffres clés) : identique | Exact |
| 215 800 personnes en zone blanche | p. 68 : « Jusqu'à 215 800 personnes résident encore en zone blanche » | Exact (la réponse glose « absence de couverture Internet » ; la source ne précise pas la nature exacte — interprétation acceptable mais ajoutée) |

Citation « page 68-69 » → exacte (Chiffres clés p. 68 + corps p. 69).

### Recommandations

- (i) « accompagner le déploiement des services numériques pour qu'ils ne deviennent pas un symbole d'éloignement des services publics, surtout en zone rurale » — p. 16 (idx 15/16) : « symbole de l'éloignement des services publics. Son développement doit être suffisamment accompagné. » Fidèle.
- (ii) « renforcer la coordination … bailleurs … parcours des usagers dans le SNE » — p. 17 : « Une coordination accrue entre les acteurs publics et les bailleurs … parcours des usagers dans le système national d'enregistrement (SNE) … améliorer l'efficacité du traitement des demandes ». Fidèle. Citation « page 17 » **exacte**.

## Problèmes identifiés

### Problème majeur — incohérence de périmètre sur le « numérique »

La recommandation (ii) citée pour le numérique (coordination acteurs publics / **bailleurs sociaux** / parcours dans le **SNE**) **n'est pas une mesure relative au numérique** : c'est une recommandation du volet **logement social** (p. 17, paragraphe sur « le parc des 5,4 millions de logements sociaux »). Le SNE est le système national d'enregistrement des **demandes de logement social**, pas un dispositif numérique de cohésion territoriale. La réponse l'a rattachée au numérique par confusion thématique (proximité de paragraphes sur la même page de synthèse). C'est une **erreur de classement / hallucination de rattachement** : le contenu existe bien dans le document, mais il est attribué au mauvais thème. Le vrai chapitre numérique (chap. 5, p. 67-73) porte des recommandations distinctes (renforcer le contrôle qualité du régulateur ; intégrer les réseaux dans la planification de crise / schémas de résilience ; mieux documenter et suivre les usages), qui ne sont **pas** reprises.

### Problème — affirmation d'exhaustivité non fondée

Dernière phrase du volet numérique : « Aucun autre chiffre précis n'est fourni dans le texte concernant l'usage ou la pénétration du numérique au-delà de ces indicateurs. » C'est **faux** et c'est précisément le type d'affirmation d'absence proscrit (corollaire grounding CLAUDE.md : le contexte peut être un extrait partiel). La page « Chiffres clés » du chapitre numérique (p. 68) contient au moins deux chiffres ignorés : **« 22 Md€ investis dans les réseaux publics de fibre de 2010 à 2024 »** et **« 18 départements couverts par un schéma de résilience numérique au 1er août 2025 »**, plus **« 93,5 % de locaux raccordables au 30 septembre 2025 »** (donnée plus récente que le 92 % retenu) et **« zone blanche mobile passée de 11 % à 2 % entre 2018 et 2023 »** (p. 69). L'affirmation d'exhaustivité est donc à la fois interdite et matériellement démentie.

### Omissions secondaires

- Santé : chiffre « 26 GHT sur 135 à direction commune » (p. 20), directement lié à la reco sur les directions communes — non repris.
- Mobilités : « 1 seule région sur 7 avait adopté l'ensemble des contrats opérationnels de mobilité début 2025 » (p. 54), constat qui motive la reco (i) — non repris.
- Numérique : voir ci-dessus, recommandations propres au chapitre numérique non couvertes.

### Coquilles mineures (sans impact factuel)

- « covoiturage **intermédiaire** » au lieu de « intermédié » (p. 54).
- Glose « absence de couverture Internet » pour les zones blanches (la source dit seulement « zone blanche »).

## Synthèse des citations de page

| Bloc | Page citée | Page réelle (1-based) | Verdict |
|---|---|---|---|
| Soins — recommandations | 20-22 | 21-22 (corps) | Exact |
| Soins — chiffres | 20 | 20 (Chiffres clés) | Exact |
| Mobilités — recommandations | 58 | 58 | Exact |
| Mobilités — chiffres | 54-55-56 | 54 + 56 | Exact |
| Numérique — recommandations | 17 | 16-17 | Exact |
| Numérique — chiffres | 68-69 | 68-69 | Exact |

**Toutes les citations de page sont vérifiables et correctes.** C'est un point fort majeur : aucun renvoi de page n'est erroné, et chaque chiffre est traçable à la page indiquée.

## Note globale

**14 / 20** — Bonne réponse, fiable sur les chiffres et les citations, mais entachée d'une erreur de périmètre et d'une affirmation d'exhaustivité interdite.

Détail :
- **Exactitude des chiffres : excellente** — tous les chiffres cités sont rigoureusement exacts (aucun chiffre inventé ni déformé).
- **Citations de page : excellentes** — 6/6 blocs correctement localisés et vérifiables.
- **Fidélité des recommandations soins/mobilités : très bonne** — mobilités reprises mot pour mot ; soins reformulés fidèlement.
- **Volet numérique : défaillant** — recommandation (ii) mal classée (logement social présenté comme numérique), recommandations réelles du chapitre numérique omises, et affirmation d'exhaustivité fausse et proscrite.
- **Complétude : moyenne** — plusieurs chiffres structurants omis (26/135 GHT ; 1/7 régions ; 22 Md€ fibre ; 18 départements résilience).

---

## Résumé

La réponse est solide sur le plan factuel : tous les chiffres cités sont exacts et les six renvois de page sont vérifiables et corrects (aucune hallucination chiffrée). Les recommandations « accès aux soins » et « mobilités » sont fidèles, ces dernières reprises mot pour mot de l'encadré officiel (p. 58). Deux faiblesses pèsent sur le volet numérique : la 2e « recommandation numérique » relève en réalité du logement social (SNE = enregistrement des demandes de logement, pas un dispositif numérique), et la phrase finale affirme à tort qu'« aucun autre chiffre » n'existe alors que la p. 68 en contient plusieurs (22 Md€ fibre, 18 départements, 93,5 %). Note : 14/20.
