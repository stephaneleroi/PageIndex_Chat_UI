# Évaluation — T2 — Procédure composite [main] — 2026-06-17

- **Question** : Synthèse du dossier pénal (actes de procédure, déroulé chronologique, professionnels, personnes concernées) + résumé des faits reprochés + différentes versions des personnes concernées.
- **Voie / aiguillage** : voie corpus (mode kb, 25 pièces), **décomposition** en 3 sous-questions (indices décomposition : 1, map-reduce : non). 34 nœuds mobilisés, 2 passes `tree_search`. Facettes :
  - **Synthèse / acteurs / chronologie** → caractère `overview` (agrégation des fiches : citations massivement `(node_0000, page 1)`, parfois `pages 1‑2`).
  - **Faits reprochés** et **versions** → caractère `detail` (lecture du texte : citations à la page précise, doc nommé, p. 1‑2/1‑3, verbatims de PV).
- **Note globale** : **16,5/20** — réponse globalement fidèle et bien structurée ; les facettes `detail` (faits, versions) sont exactes au texte. Les rares défauts imputables à l'app sont **mineurs** (un faux verbatim, un âge calculé, « à la demande du parquet », inversion d'ordre dans une version, « le patron et lui » sur la batte). Aucune hallucination grave : la « confusion » médecin/Victor est le **🟡 artefact connu** du certificat, fidèlement reproduit.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | mineure | Faux verbatim : « *le MEC 2 a donné des coups de poings à la victime dans le même temps* » présenté entre guillemets. Le texte exact est « le MEC 2 **a quant à lui donnée** des coups de poings à la victime dans le même temps ». Paraphrase guillemetée. | Compte-rendu d'enquête, p. 1 (`quote` → FAUX VERBATIM) |
| 2 | 🔴 app | mineure | Version de Tom LEBRUN : ordre inversé. L'audit dit « coup de poing, **puis avec la batte**, **et qu'il a ensuite brandi un couteau** ». Le source donne l'ordre : droite (poing) → **couteau** (pointé sur le ventre/avant-bras) → couteau récupéré → **batte/gourdin** (2 coups à la tête). Le couteau précède la batte. | Plainte LEBRUN, p. 1‑2 |
| 3 | 🔴 app | mineure | Version d'Adrien LEPETIT : « le patron **et lui** ont ensuite utilisé… une **batte de baseball** pour intimider ». Adrien attribue la batte au seul patron (« Mon patron l'avait pris pour faire peur au gars ») ; lui-même dit avoir donné des coups de poing. Co-attribution de la batte non soutenue. | Audition LEPETIT, p. 1‑2 |
| 4 | 🔴 app | mineure | Guy CARDON « **âgé de 68 ans**, né le 05/05/1955 » : l'âge n'est pas dans le PV (aucune occurrence de « 68 ») et le calcul est faux (au 06/05/2024 il a 69 ans). Âge fabriqué/mal calculé par l'app. | Audition CARDON (grep « 68 » → aucune) |
| 5 | 🔴 app | très mineure | Certificat médical « **à la demande du parquet** » : la réquisition d'examen est prise par l'OPJ sur l'art. 60 CPP, pas par le parquet. | Réquisition examen LEPETIT, p. 1 (« Agissant en vertu de l'article 60… ») |
| 6 | 🟡 données | — | « Dr Romuald LIGNIER… certifie la compatibilité de l'état de santé de **Victor** avec la garde à vue » : le certificat médical (artefact connu) porte bien l'identité **LEGRAND Victor** (né 05/05/2000, 15/15 rue des iris), la mention « état de santé **compatible avec la garde à vue** », et est « Signé par ROMUALD LIGNIER » (nom de l'OPJ réutilisé). L'app reproduit fidèlement un document anormal — pas une hallucination. | Certificat médical, OCR `structure.json` node 3fb8 ; réquisition (compatibilité GAV) p. 1 |
| 7 | 🟡 données | — | « réalise l'examen médical d'**Adrien** » alors que le certificat porte l'identité de **Victor** : c'est exactement l'incohérence du formulaire (réquisition pour LEPETIT Adrien, certificat rempli au nom de LEGRAND Victor). Reproduction fidèle. | Réquisition (LEPETIT Adrien) p. 1 vs certificat (LEGRAND Victor) |
| 8 | 🔵 connu | — | Citations `(node_0000, page 1/2)` génériques (overview sur fiches) : node id non résolu et page peu discriminante. Attendu pour la facette synthèse agrégée sur fiches. | — (voir app-specifics §2) |
| 9 | 🔵 connu | — | Chronologie : « 08 h 35 : placement en garde à vue de Victor LEGRAND » — 08 h 35 est en réalité l'**interpellation** (la notification de début GAV est signée à 08 h 58). Survol/condensé de la facette overview, non un faux fait isolé (les deux heures figurent par ailleurs correctement dans la réponse). | Saisine p. 1 (interpellation 08 h 35) ; Notification début GAV Victor p. 3 (08 h 58) |

## Faits correctement sourcés (échantillon vérifié)

- Identités et filiations : Victor LEGRAND né 05/05/2000, fils de **LEGRAND Simon** et **LAPETITE Jacqueline** ; Adrien LEPETIT né 04/04/2004, fils de **LEPETIT Jean** et **LAGRANDE Jacqueline** — exacts, **noms-pièges correctement distingués** (LAPETITE/LAGRANDE). (CreI p. 1‑2)
- Professionnels : OPJ Major **Romuald LIGNIER** ; Commissaire **Gilbert MARRON** ; Gardiens **Albert VERT**, **Romain ORANGE** ; Vice-procureure **Marie INTERIEUR** — tous exacts. (Saisine p. 1 ; CR parquet p. 1)
- Qualification : « violence aggravée par **deux circonstances** », « **ITT n'excédant pas 8 jours** », arme par destination (batte) — exact. Articles **222-13, 222-44, 222-45, 222-47** AL.1 — présents dans les COPJ. (CreI p. 1 ; COPJ p. 1)
- Versions des témoins (Lemarron, Cardon) : trois individus, chemise blanche, 1500 €, échanges de coups, **aucune arme/morceau de bois vu** — fidèles. (Auditions TEM p. 1‑2)
- Aline TRUITE « apparaît mais n'est pas détaillée » : correct (présente en saisine p. 2). 
- Verbatim Victor « je ne l'ai pas utilisé, je voulais lui faire peur » : conforme au PV (p. 2).

## Analyse par facette

**Overview (synthèse / acteurs / chronologie)** — fidèle et complète sur les acteurs et la qualification ; les imprécisions sont du survol attendu (citations `node_0000/page 1` peu discriminantes, conflation interpellation/placement GAV à 08 h 35). Aucune affirmation d'exhaustivité abusive ; au contraire la réponse signale prudemment qu'Aline TRUITE n'est « pas détaillée ». Conforme aux attentes 🔵.

**Detail (faits reprochés, versions)** — c'est la partie la plus exigeante et elle tient bien : faits, motif financier, qualification et articles exacts, versions distinguées personne par personne avec citation du bon PV. Les 3 défauts 🔴 ici (faux verbatim #1, ordre couteau/batte #2, co-attribution batte #3) sont **réels mais de faible gravité** : ils ne changent pas le fond (les actes — poings, batte, couteau, menaces — sont bien rapportés et correctement attribués pour l'essentiel).

**Le point sensible — le médecin** : la phrase mêlant « examen d'Adrien » et « compatibilité de Victor » n'est **pas** une hallucination. Vérification source : la réquisition vise **Adrien LEPETIT** et demande un certificat de « compatibilité de l'état de santé… avec une mesure de garde à vue » ; le certificat lui-même est rempli au nom de **Victor LEGRAND** et porte « état de santé compatible avec la garde à vue », « Signé par ROMUALD LIGNIER ». L'app a donc fidèlement agrégé un document objectivement incohérent (artefact 🟡 documenté). Seul l'ajout « à la demande du parquet » (#5) est une scorie d'app, très mineure.

## Corrections proposées (🔴 uniquement)

- **#1** Retirer les guillemets autour de la reformulation du compte-rendu d'enquête, ou citer le verbatim exact (« a quant à lui donnée des coups de poings… »). Règle grounding §6.
- **#2** Respecter l'ordre chronologique de la déclaration de la victime (couteau avant batte) lors de la restitution de sa version.
- **#3** N'attribuer la batte qu'au patron dans la version d'Adrien (ou marquer « non précisé » pour Adrien), conformément au PV.
- **#4** Ne pas calculer/afficher un âge non présent dans le source (« âgé de 68 ans ») — s'en tenir à la date de naissance citée.
- **#5** Supprimer « à la demande du parquet » pour le certificat (réquisition OPJ, art. 60 CPP).

Aucune correction pour #6/#7 (🟡, fidélité à un document anormal) ni #8/#9 (🔵, limites overview / convention page).
