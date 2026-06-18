# Évaluation — T2 Procédure composite (tirage MAIN, run2) — 2026-06-18

- **Audit évalué** : `evaluations/2026-06-17/main/audits/T2_procedure_run2.md`
  (run live, branche `main` @ `08f6319`, code RAG identique à `ed96178` — tirage MAIN).
- **Source** : `../data/Procedure-PN-1-PDF/` (25 pièces réelles, dossier pénal).
- **Question** : synthèse composite — actes de procédure / chronologie / professionnels /
  personnes concernées + résumé des faits reprochés + versions de chaque personne.
- **Voie / aiguillage** : décomposition en 3 facettes (indice décomposition = 1).
  - Facette 1 (synthèse 4 axes) : `overview` — `global_summary` (30 pièces agrégées),
    citations « page 1 » sur les fiches.
  - Facette 2 (faits reprochés) : mixte, tree_search 6 pièces (COPJ, auditions, saisine, CR enquête).
  - Facette 3 (versions) : `detail` — tree_search 5 pièces (auditions lues au texte).
  - map-reduce : non.
- **Note globale** : **16/20** — la facette « versions » (detail) est très fidèle ;
  la facette « faits reprochés » contient **une conflation des rôles/sources avec
  mauvaise attribution de citation** (seul vrai 🔴 marquant), plus deux imprécisions
  mineures. Les deux circonstances aggravantes et l'attribution de la batte sont
  correctes. Aucun faux verbatim.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | moyenne | **Faits reprochés** : « il aurait toutefois exercé la **menace de mort en le pointant sur le ventre** » attribué à l'**audition de Legrand** (cité `MEC_1…AUDITION_MEC_LEGRAND_VICTOR.pdf, page 2`). Ce détail (couteau pointé sur le ventre) n'est PAS dans l'audition de Legrand — il vient de la **plainte de la victime**. Legrand dit seulement « je voulais lui faire peur ». Misattribution de source + sur-qualification (« menace de mort »). | Audition Legrand p. 2 : « je l'ai pris pour lui faire peur […] je ne l'ai pas utilisé, je voulais lui faire peur ». Plainte Lebrun p. 1 : « est revenu avec un couteau […] en me le pointant sur le ventre ». Menaces de mort = plainte p. 2 (« je vais te crever »). |
| 2 | 🔴 app | faible | **Faits reprochés** : « ont constaté la présence de la batte de baseball **dans les cuisines** (… SAISINEInterpellation.pdf, page 1) ». Le fait est exact mais figure **page physique 2** (« dans l'arrière cuisine »), pas page 1 ; la page 1 n'évoque la cuisine que comme lieu où la victime serait entrée. Citation de page décalée. | Saisine p. 2 : « le bâton utilisé […] se trouve dans l'arrière cuisine, écartons et appréhendons cet objet ». |
| 3 | 🟡 données | — | « Le **médecin légiste Romuald Lignier** a réalisé l'examen médical d'Adrien ». Le certificat médical du dossier est un formulaire anormal (signé ROMUALD LIGNIER = nom de l'OPJ réutilisé, identité Legrand). L'app reproduit fidèlement un document incohérent. **Artefact connu, pas une hallucination.** | `…Certificat medical_MEC_LEPETIT_Adrien.pdf` (cf. app-specifics §3). |
| 4 | 🟡 données | — | **Versions Lemarron** : « il a entendu que le patron réclamait **1 500 €** » — chiffre exact, mais le source dit que le patron **reprochait à la victime** de lui devoir 1500€ (sens inversé dans la formulation « réclamait … au patron », phrasé garbouillé). Le montant et la nature (dette) sont au source ; la maladresse reflète le PV. | Audition Lemarron p. 1 : « Il lui disait qu'il ui devait 1500€ ». Cardon p. 1 : « lui devoir 1500€ ». |
| 5 | 🟡/🔵 | — | **Versions Lepetit** : « le **groupe** a utilisé une batte de baseball pour intimider ». Atténuation : Lepetit attribue clairement la batte au **patron** (« Mon patron l'avait pris pour faire peur au gars »). Mais le couteau (« j'ai eu peur, je l'ai pris de ses mains ») est correctement attribué à Adrien. Imprécision de synthèse, non une inversion de rôle. | Audition Lepetit p. 1-2. |
| 6 | 🔵 connu | — | Facette overview : citations toutes en « page 1 / node_0000 » (agrégation des fiches, sans relecture). Convention page physique respectée ailleurs (les pages citées tombent juste là où vérifiées). | app-specifics §1-2. |

### Ce qui est CORRECT et vérifié (points récurrents surveillés)

- **Circonstances aggravantes de la COPJ** : les **deux vraies** sont citées exactement —
  « par plusieurs personnes » + « menace d'une arme par destination, en l'espèce une batte
  de baseball ». ✅ (COPJ Legrand p. 1 ; art. 222-13). Pas d'invention.
- **Attribution de la batte** : l'app dit bien que **Victor (le patron) a pris la batte**
  (« qu'il a saisi une batte de baseball pour intimider » côté Legrand ; « son patron l'avait
  pris » côté Lepetit). ✅ Pas d'attribution erronée à Adrien. (Auditions Legrand/Lepetit p. 2).
- **Faux verbatims** : aucun. Les seuls passages guillemetés (« Le temps des secrets »,
  « MEC 1 »/« MEC 2 ») sont des verbatims réels. ✅ (saisine p. 1, CR enquête p. 1).
- **Horaires de la chronologie** : tous recoupés aux horodatages/contenus des pièces —
  08h20 saisine, 08h35 GAV Victor, 08h40 GAV Adrien, 09h05 notif Adrien, 09h30 Cardon,
  10h25 plainte Lebrun, 11h35 Adrien, 12h35 Legrand, 14h35 Lemarron, 15h55 CR parquet,
  17h00/17h25 fins GAV, 17h45 clôture. ✅ Cohérents avec les en-têtes des PV.
- **Professionnels** : OPJ Lignier, vice-procureure INTERIEUR Marie, commissaire MARRON
  Gilbert, gardiens VERT/ORANGE — tous au source (CR parquet p. 1 ; saisine p. 1). ✅
- **Versions croisées** (facette detail) : témoins Lemarron/Cardon décrivant le **patron**
  comme agresseur et **niant l'usage d'un morceau de bois** — fidèlement rapporté, y
  compris cette divergence majeure avec la version officielle. ✅ Excellente fidélité.

## Analyse par facette

**Overview (facette 1 — synthèse 4 axes)** : agrégation des fiches, rapide et large.
Couvre l'ensemble des actes, la chronologie complète, les acteurs. Le médecin « Lignier »
(🟡) et la finesse « page 1 » partout sont des limites attendues de cette voie. Aucune
omission majeure d'acteur ; les noms-pièges (LAPETITE mère de Victor, LAGRANDE mère
d'Adrien, Legrand/Lepetit) sont **corrects**.

**Faits reprochés (facette 2)** : c'est ici que se concentrent les défauts. La voie a lu
des pièces (tree_search) mais la **rédaction synthétique a fusionné la version de la
victime dans une phrase attribuée à l'audition de Legrand** (constat #1) — violation de la
règle de grounding « ne pas attribuer/inverser un rôle ou une source ». Le décalage de
page sur la batte « cuisines » (#2) est mineur. En revanche, la qualification pénale (deux
circonstances aggravantes, art. 222-13, ITT ≤ 8 jours) est **exacte**.

**Versions (facette 3 — detail/texte)** : la plus réussie. Chaque version (Legrand, Lepetit,
Lebrun, Lemarron, Cardon) est fidèle au texte des auditions, y compris les divergences
gênantes (les témoins ne voient pas la batte ; ils voient le patron frapper). C'est la
démonstration que **detail > overview** sur ce dossier. Seule imprécision : « le groupe »
pour la batte côté Lepetit (#5).

## Corrections proposées (🔴 uniquement)

- **#1 (conflation de source)** : c'est le défaut actionnable principal. Dans la facette
  de synthèse, le détail « pointant sur le ventre » / « menace de mort » doit être rattaché
  à la **plainte de la victime**, pas à l'audition de Legrand. Piste : renforcer dans la
  rédaction de synthèse la règle « un détail factuel = la pièce qui le porte », en évitant
  d'agréger plusieurs versions sous une seule citation. Aucun changement de données.
- **#2 (page)** : décalage page 1 → page 2 sur la localisation de la batte. Faible impact ;
  ne pas sur-corriger.

Rien à corriger pour #3, #4, #5, #6 (artefacts de données ou limites de voie attendues).
