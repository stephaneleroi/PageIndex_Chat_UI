# Évaluation — T4 — Synthèse résumé — 2026-06-17

- **Question** : « Fais moi un résumé »
- **Source** : `../data/Synthèse_2026.pdf` (114 pages physiques) — Rapport public annuel 2026 de la Cour des comptes (synthèses), « Cohésion territoriale et attractivité des territoires ».
- **Voie / aiguillage** : décomposition = 1 (question simple, intention `overview`) ; **map-reduce : non** ; une seule étape `global_summary` agrégeant **6 fiches** (nœuds 0000, 0001, 0002, 0003, 0009, 0015). C'est une **agrégation de fiches sans relire le texte** → on attend un survol fidèle aux fiches, avec citations à la page justes, pas l'exhaustivité.
- **Note globale** : **14/20**. Résumé structuré, fidèle à l'arbre et globalement bien cité (la grande majorité des ~20 chiffres tombent juste à la bonne page physique). Deux **erreurs de rédaction propres à la réponse** plombent la note : « **524 milliards €** » au lieu de **524 M€** (erreur d'unité ×1000) et « **215 800 bornes de recharge** » au lieu de **184 141** (le chiffre des zones blanches dupliqué) — les deux fiches sources étaient pourtant **correctes**. Un troisième défaut (auteur « service de la mission… ») provient de l'**indexation** (fiche node_0000), pas de la rédaction. Hors ces points, la fidélité au survol est bonne.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app (rédaction) | majeure | « crédits de **524 milliards €** en 2024 » pour les QPV → en réalité **524 M€** (millions). Erreur d'unité ×1000. La **fiche node_0015 était correcte** (« 524 M€ en 2024 (p. 90-92) ») : la corruption vient de la rédaction. | p. 90 « **524 M€** exécutés en 2024 s'agissant des crédits de la politique de la ville » ; p. 92 idem. Fiche node_0015 : « 524 M€ ». |
| 2 | 🔴 app (rédaction) | majeure | « 215 800 personnes restent en zone blanche **et 215 800 bornes de recharge publiques** sont disponibles fin novembre 2025 » → le **même nombre dupliqué**. Le nombre de bornes est **184 141**. La **fiche node_0009 était correcte** (« 184 141 bornes… (p. 54) »). | p. 54 « **184 141** c'est le nombre de bornes de recharge publiques pour véhicules électriques » ; p. 68 « 215 800 personnes résident encore en zone blanche ». Fiche node_0009 : « 184 141 bornes ». |
| 3 | 🔴 app (indexation) | moyenne | « rédigé par **le service de la mission Cohésion territoriale et attractivité des territoires** (node_0000, page 1) ». La p. 1 ne porte que le **titre/thème** du rapport ; l'auteur est la **Cour des comptes**. « service de la mission… » est une **attribution fabriquée à l'indexation** (fiche node_0000 : « Auteur : Cour des comptes, service de la mission "Cohésion territoriale…" »). La réponse a reproduit fidèlement la fiche → défaut **introduit à l'indexation**, pas par la rédaction. | p. 1 (titre seul) ; p. 12 « mission Cohésion des territoires » = **mission budgétaire**, pas rédacteur. Fiche node_0000 (champ « Auteur »). |
| 4 | 🔵 connu (page physique) | — | Plages de pages citées légèrement décalées par rapport au lieu exact du fait : « LOM/AOM 50 % » cité p. 53-54 (fait p. 54-55) ; « 70 % mobilité » cité p. 53-54 (fait **p. 56**) ; « fibre 92 % » cité dans 68-69-54 (fait **p. 50**) ; recommandation « droit commun d'ici 2026 » cité p. 108-110-106 (fait **p. 94**). Imprécisions héritées des **fiches** (ex. fiche node_0009 situe « 70 % » p. 54). En `overview`, citation à la plage de pièce = comportement attendu. | p. 56 « plus de 70 % des personnes résidant en commune rurale ou périurbaine ne bénéficient pas d'une offre de mobilité diversifiée » ; p. 50 « 92 % des locaux raccordables à la fibre en 2025 » ; p. 94 « identifier… les actions de droit commun… (2026) ». |
| 5 | 🔵 connu (overview) | — | Survol : le résumé restitue la macro-structure (3 parties, chiffres clés) mais omet des chapitres (logement, accès numérique aux services publics, réindustrialisation, emploi). Attendu pour une agrégation de 6 fiches sans relire le texte. | Sommaire p. 4-5 (chapitres non repris). |

## Contrôle des citations vérifiées (justes — page physique confirmée)

- 23 départements perte de population 2015-2021 ; PIB 69 288 € (IDF) / 32 652 € (Bourgogne-FC) ; RDB 27 060 € / 19 509 € ; 16,8 Md€ crédits UE 2021-2027 ; 57 % communes FRR → **tous p. 8** (cité p. 8). ✅
- Chapitre introductif (diversité = identité, défis climatiques/numériques/démographiques/crises) → **p. 7** (cité p. 7-10). ✅
- ~2 500 établissements de santé en métropole → **p. 16** (cité p. 16-20). ✅
- 75 % patients à 43 km max → **p. 20** (dans la plage 16-20). ✅
- 34,6 % pauvreté outre-mer 2023 ; 42 jours cardiologie → **p. 27** (cité p. 27). ✅
- Recommandations santé (fusion GHT, stratégie gradation d'ici 2028 ; données de santé centralisées) → **p. 23 et p. 29** (cité p. 23-29). ✅
- Baisse de 12 % collégiens à l'horizon 2036 → **p. 31** (cité p. 31). ✅
- 50 % intercommunalités AOML → p. 54-55 (cité p. 53-54, proche). ✅ (cf. #4)
- 91 % smartphone (p. 68) ; 215 800 zone blanche (p. 68) → cités p. 68. ✅
- Sécurité : 24,4 Md€ État, +33 % depuis 2016, 2,3 Md€ collectivités, +6,5 % délinquance 2016-2024 → **p. 80-81** (cité p. 80-81). ✅
- OIN : 17 OIN, 56 projets parmi 1 931 → **p. 95** (cité p. 95). ✅
- QPV pauvreté ×3 → **p. 90** (cité p. 90-92). ✅
- Péréquation verticale 10,2 Md€ / horizontale 4,2 Md€ en 2024 → **p. 108** (cité p. 108-110-106). ✅
- Titres des trois parties entre guillemets = **vrais titres** du rapport (sommaire p. 4, intertitres). ✅ (les « faux verbatim » signalés par le script venaient de l'apostrophe droite vs typographique, pas d'une paraphrase).

## Analyse par section / facette

La voie `overview` a fait son travail : ossature en 3 parties, chiffres clés correctement extraits des fiches, citations majoritairement justes à la **page physique**. C'est une bonne agrégation. Les imprécisions de page (#4) sont mineures et largement **héritées des fiches** (l'indexation situe certains chiffres à la page de leur encadré « Chiffres clés » plutôt qu'à la page du texte courant) — cohérent avec le caractère survolant de la voie.

Les deux vrais points noirs (#1, #2) sont des **erreurs numériques introduites par la rédaction du reduce**, et non par les données : les fiches portaient les bons chiffres (524 **M€** et **184 141** bornes). Ce sont donc des défauts d'app actionnables. Le #2 est typique d'une **contamination de proximité** (le rédacteur a recopié « 215 800 » de la phrase précédente). Le #1 (M€ → milliards) fausse l'ordre de grandeur d'un montant public — sévère pour un document de la Cour des comptes.

Le #3 (auteur fabriqué) est un défaut **d'indexation** : la fiche node_0000 a transformé le **thème** du rapport en « service de la mission » rédacteur. La rédaction a été fidèle à la fiche ; le correctif est côté indexation (résumé identitaire du nœud Preface).

## Corrections proposées (🔴 uniquement)

- **#1 / #2 (rédaction)** : ce sont des erreurs de recopie de chiffres au *reduce* `global_summary`. Pistes minimales, sans sur-conception : (a) rappeler dans le gabarit de synthèse globale de **recopier les nombres tels quels depuis les fiches, unité comprise**, et de **ne pas réutiliser un nombre déjà cité pour une autre grandeur** ; (b) à défaut, l'évaluation sur plusieurs tirages dira si c'est systématique ou un aléa de génération (température non nulle). Aucune validation d'exhaustivité ou d'unité côté code n'est justifiée pour ces cas ponctuels.
- **#3 (indexation)** : ajuster le résumé identitaire du nœud `Preface` pour que l'« Auteur » soit la **Cour des comptes** (le « service de la mission… » n'est pas un rédacteur identifiable en p. 1). Vérifier après réindexation que la fiche node_0000 ne réintroduit pas l'attribution.

Rien à corriger pour #4 et #5 (limites connues de la voie `overview` / convention page physique).
