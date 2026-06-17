# Night T5 — MAP-REDUCE sur Synthèse_2026 (question detail)

Question detail : « Détaille les principales recommandations du rapport et les
constats chiffrés (soins, mobilités, numérique). » Document = 179 k caractères.

## Deux runs

**Run A — conditions réelles (seuil 60 000) : map-reduce NON déclenché.**
voie = corpus **lecture directe** | refs = 5 sections | **26 citations, 26/26
pages cohérentes** | 150 s. Le **drill-down niveau 2** a sélectionné ~5 sections
pertinentes (< 60 k) au lieu des parties entières → lecture directe. *Le
drill-down rend le map-reduce inutile sur un document structuré.*

**Run B — mécanique forcée (seuil abaissé à 8 000, non commité, restauré
ensuite) : map-reduce déclenché et validé.**
- session `sess_kb_1781680818_b1d938` | durée 165s
- **voie: MAP-REDUCE** | map-reduce déclenché: OUI
- refs (nœuds): 2 | citations: 6 | **pages cohérentes vs PDF: 6/6** ✅

Conclusion : la **mécanique map-reduce fonctionne** (bascule par volume → fiche
ciblée par pièce, pages conservées → reduce → citations cohérentes). En pratique,
sur un document bien structuré, le **drill-down l'évite** (run A).

*(Le bloc ci-dessous correspond au run B, forcé.)*

## Étapes map-reduce
  - 2 pièce(s) (37825 car.) > budget 8000 → synthèse ciblée par pièce
  - synthèses ciblées : 1/2 — 1 pièce(s) pertinente(s)
  - synthèses ciblées : 2/2 — 2 pièce(s) pertinente(s)

## Toutes les étapes
  - [tree_search] 2 pièce(s) retenue(s) : PREMIÈRE PARTIE - Garantir l’accès aux services essentiels, DEUXIÈME PARTIE 
  - [tree_search] [PREMIÈRE PARTIE - Garantir l’accès aux services essentiels] pièce volumineuse : 4 section(s) retenu
  - [tree_search] [DEUXIÈME PARTIE - Soutenir le développement des territoires] pièce volumineuse : 2 section(s) reten
  - [map_reduce] 2 pièce(s) (37825 car.) > budget 8000 → synthèse ciblée par pièce
  - [map_reduce] synthèses ciblées : 1/2 — 1 pièce(s) pertinente(s)
  - [map_reduce] synthèses ciblées : 2/2 — 2 pièce(s) pertinente(s)

## Réponse
Pour l’accès aux soins, le rapport recommande : (i) de réorganiser le maillage hospitalier en stimulant la création de groupements territoriaux à direction commune ; (ii) d’instaurer une gradation des soins mieux financée, avec un financement dédié aux hôpitaux de proximité ; (iii) d’impliquer les collectivités territoriales dans les projets d’évolution de l’offre, par exemple la reconversion d’une maternité ; (iv) de renforcer la structuration des filières coordonnées de soins malgré le manque de personnel (node_0003, page 20‑22). Ces recommandations s’appuient sur les constats suivants : la France compte 2 380 sites hospitaliers en 2023, un maillage dense mais peu évolué ; 75 % des patients sont hospitalisés à ≤ 43 km (environ 48 minutes en voiture) de leur domicile ; la distance moyenne varie de 25 km (33 minutes) pour l’obstétrique à 119 km (1 h 36) pour les transplantations ; le nombre de spécialités est passé de 8 en 1947 à 44 aujourd’hui ; 25 M de patients chroniques en 2023 (+ 7 % depuis 2015) génèrent une dépense d’environ 126 Md €, tandis que les hôpitaux publics affichent un déficit de 2,4 Md € (node_0003, page 20).

Pour les mobilités, le rapport formule plusieurs recommandations majeures : (i) mettre rapidement en place les contrats opérationnels de mobilité et les plans d’action pour la mobilité solidaire ; (ii) clarifier les dispositifs juridiques et fiscaux applicables aux syndicats mixtes et aux conventions afin de favoriser la coopération ; (iii) accorder la priorité à la régénération des réseaux existants et aux projets favorisant les trajets du quotidien ; (iv) prévoir une loi‑cadre succédant à la LOM, définissant les orientations de l’État et les modalités de financement des projets de transport, y compris pour les autorités organisatrices de mobilités régionales et locales (node_0009, page 58). Ces mesures reposent sur les constats chiffrés suivants : 50 % des communautés de communes sont désormais autorités organisatrices de la mobilité locale (AOML) ; plus de 70 % des habitants des zones rurales ou périurbaines ne disposent pas d’un choix entre différents modes de transport ; 30 % des jeunes ruraux ont déjà renoncé à se rendre à leur lieu d’étude ; entre 2019 et 2023, l’offre de transport collectif du quotidien a progressé de + 7,7 % en kilomètres parcourus au niveau national ; 12,8 M de trajets en covoiturage intermédiaire ont été réalisés en 2024, soit huit fois plus qu’en 2021 ; 184 141 bornes de recharge publiques pour véhicules électriques étaient disponibles fin novembre 2025 ; les collectivités territoriales financent les deux tiers du transport public, avec 35,6 Md € de dépenses courantes et 21 Md € d’investissements en 2023 (+ 17 % par rapport à 2019) ; la conférence « Ambition France Transports » estime un besoin de financement supplémentaire de 3,7 à 6,7 Md € par an (node_0009, page 55‑56‑54).

Pour le numérique, le rapport recommande : (i) d’accompagner le déploiement des services numériques afin qu’ils ne deviennent pas un symbole d’éloignement des services publics, surtout en zone rurale ; (ii) de renforcer la coordination entre acteurs publics et bailleurs pour faciliter le parcours des usagers dans le Système National d’Enregistrement (SNE) et améliorer l’efficacité du traitement des demandes (node_0003, page 17). Les constats chiffrés qui sous‑tendent ces recommandations sont : 92 % des locaux sont raccordables à la fibre optique en 2025 ; 91 % des Français de plus de 12 ans possèdent un smartphone ; toutefois, 215 800 personnes résident encore en zone blanche (absence de couverture Internet) (node_0009, page 68‑69). Aucun autre chiffre précis n’est fourni dans le texte concernant l’usage ou la pénétration du numérique au-delà de ces indicateurs.
