# Évaluation — T2 Procédure composite (Etude_Open_Notebook, tirage 2) — 2026-06-17

- **Question** : Synthèse du dossier pénal en distinguant actes de procédure, déroulé chronologique, professionnels intervenus, personnes concernées ; résumé des faits reprochés ; différentes versions des personnes concernées.
- **Voie / aiguillage** : décomposition (3 sous-questions). Sous-Q1 (synthèse/acteurs/chrono) traitée en `overview` (agrégation des fiches — `global_summary` 30 pièces, puis `tree_search`), donc **fidélité d'exhaustivité non garantie, ordonnancement approximatif attendu** (🔵). Sous-Q2 (faits reprochés) et sous-Q3 (versions) traitées en `detail` (lecture du texte des auditions, p. 2) — **voie fidèle, exigence d'exactitude élevée**.
- **Note globale** : **13,5/20** — facette `detail` (versions) solide et fidèle au texte ; facette `overview`/qualification juridique entachée de 2 défauts d'app récurrents (circonstances aggravantes mal qualifiées, batte mal attribuée à Adrien) + un faux verbatim. Les défauts imputables à l'app sont concentrés, pas diffus.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | mineure | « notifiés à Victor (08 h 58) » : l'acte de notification GAV Victor est **daté 08 h 52** en en-tête ; le placement en GAV est à **08 h 35**. 08 h 58 = heure de **signature** de l'acte (p. 3), pas l'heure de la notification. Mélange de timestamps. | `MEC 1_…0852_NOTIFICATION DEBUT GAV…` p.1 « à huit heures cinquante deux » ; « placé en garde à vue … à huit heures trente cinq » ; p.3 « signe le présent … à huit heures cinquante huit » |
| 2 | 🔴 app | majeure | Circonstances aggravantes **sous-qualifiées** : la réponse n'en retient qu'**une** (« usage d'une batte… comme arme par destination »). Le source en porte **deux** : « par plusieurs personnes » + « menace d'une arme par destination ». La réponse omet « par plusieurs personnes » et écrit « usage » au lieu de « menace ». | `MEC 1_…1705_COPJ TJ…` p.1 « 2 circonstances aggravantes … par plusieurs personnes avec menace d'une arme par destination, en l'espèce une batte de baseball » ; `…1800_CreI…` p.1 « VIOLENCE AGGRAVEE PAR DEUX CIRCONSTANCES » |
| 3 | 🔴 app | majeure | Version d'Adrien : la batte lui est attribuée à tort — « avec le serveur, ils ont utilisé une batte de baseball … pour intimider ». Le source : c'est **le patron** qui a pris la batte ; Adrien dit avoir donné des coups de poing et avoir **pris le couteau des mains du patron**, jamais la batte. | `LEPETIT ADRIEN_…1135_AUDITION…` p.2 « Mon patron l'avait pris [la batte] pour faire peur au gars » ; p.1 « J'ai donné des coups de poings … il a pris un couteau … Je l'ai pris de ses mains » |
| 4 | 🔴 app | mineure | Faux verbatim : « armé d'une batte de baseball » mis entre guillemets (attribué à la saisine). Le source écrit « violences armées d'une batte de baseball » — pas le même libellé. | `…0820_SAISINE Interpellation` p.1 ; `verif_source.py quote` → FAUX VERBATIM |
| 5 | 🔴 app | mineure | Citation de page : versions des témoins (Lemarron « préfecture / 1 500 € », Cardon idem) citées « page 2 » ; les faits sont en réalité **page 1** des auditions (docs 2 p.). Citation générique appliquée en bloc. | `…1435_AUDITION TEM LEMARRON` p.1 « doit travailler à la préfecture » / « il ui devait 1500€ » ; `…0930_AUDITION TEM CARDON` p.1 idem |
| 6 | 🟡 données | — | « médecin légiste Dr Romuald Lignier » : nom de l'OPJ réutilisé comme signataire du certificat ; artefact connu du corpus, l'app reproduit fidèlement. **Pas un bug.** | cf. `references/app-specifics.md` §3 (certificat médical anormal) |
| 7 | 🔵 connu | — | Sous-Q1 (`overview`/fiches) ordonne la chronologie approximativement et tout est cité « page 1 » (en-têtes de pièces). Survol attendu de la voie overview ; pas d'inversion d'horaires constatée à ce tirage. | — |

## Analyse par facette

**Facette overview (Sous-Q1 — synthèse / chrono / acteurs).** Globalement fidèle aux en-têtes des pièces : GAV Victor 08 h 35 (✓), GAV Adrien 08 h 40 (✓ avis magistrat), notif Adrien 09 h 05 (✓ filename), auditions 10 h 25 / 11 h 35 / 12 h 35 / 14 h 35 / 09 h 30 (✓), levées GAV 17 h 25 / 17 h 00 (✓), clôture 17 h 45 (✓). Acteurs corrects : OPJ Lignier, Cmsr Marron, GPX Vert/Orange, vice-procureure Marie INTERIEUR, bâtonnier ; parents LAPETITE/LAGRANDE bien différenciés (piège évité). Le seul accroc chiffré est l'heure « 08 h 58 » (constat 1) — atténué car traçable au source (signature, p. 3), donc imprécision plutôt qu'hallucination. **Pas d'horaires intervertis** dans la frise à ce tirage : la carence vidéo (13 h 55) et l'avis magistrat (09 h 10) ne sont tout simplement pas portés dans la frise — donc l'inversion de run 1 ne se reproduit pas.

**Facette detail (Sous-Q3 — versions).** C'est la partie la plus solide et la plus fidèle, conforme à l'attente de la voie `detail`/texte :
- **Victor** : exact — il a pris la batte « pour lui faire peur » mais dit ne pas avoir frappé avec, couteau repris par le serveur, > 1 000 €, refuse confrontation, accepte prélèvement (✓ p. 2).
- **Tom** : exact — coup de poing, menace au couteau, **deux coups de gourdin à la tête**, insultes/menaces de mort, plainte contre Victor ET Adrien (✓ p. 2).
- **Lemarron / Cardon** : scène, patron frappant l'homme en chemise blanche, 1 500 €, « préfecture » — exacts (mais cités p. 2 au lieu de p. 1, constat 5).
- **Adrien** : seule version fautive — la batte lui est attribuée (constat 3). Le couteau pris des mains du patron est, lui, correct.

**Facette faits reprochés (Sous-Q2).** Les éléments factuels (batte, couteau, coups, > 1 000 €) sont fidèles, mais la **qualification juridique** est dégradée : faux verbatim (constat 4) et surtout réduction des deux circonstances aggravantes à une seule (constat 2) — c'est le défaut le plus pénalisant car il touche le cœur juridique de la pièce maîtresse (COPJ).

## Corrections proposées (🔴 uniquement)

- **Constat 2 (prioritaire)** : en voie `detail`/overview sur une qualification, restituer les circonstances aggravantes **telles qu'énumérées** dans la COPJ (les deux, verbatim : « par plusieurs personnes » + « menace d'une arme par destination »), sans synthèse réductrice.
- **Constat 3** : en restituant la version d'Adrien, n'attribuer que les actes qu'il **revendique** (coups de poing ; couteau pris des mains du patron) ; ne pas lui prêter l'usage de la batte (la batte est prise par le patron).
- **Constat 1** : pour une heure de « notification », préférer l'heure d'en-tête de l'acte (08 h 52), distincte de l'heure de signature (08 h 58) ; ne pas mélanger les deux.
- **Constats 4 et 5** : réserver les guillemets au verbatim exact (`verif_source.py quote`) ; faire pointer la page citée sur la page physique du fait (témoins : p. 1).

## Verdict — les 4 défauts du tirage 1

- **(1) heure de début GAV Victor « 08h58 » inventée** : **partiellement reproduit**. Le « 08 h 58 » réapparaît, MAIS il n'est plus une invention pure : il correspond à l'heure de signature réelle de l'acte (p. 3). L'erreur résiduelle est un mélange de timestamps (notification 08 h 52 vs signature 08 h 58), pas une hallucination. Sévérité nettement moindre qu'au tirage 1.
- **(2) horaires de la frise intervertis (carence vidéo / avis magistrat)** : **absent**. Aucune inversion ; ces deux items ne figurent pas dans la frise de ce tirage.
- **(3) faux verbatim convocation + circonstances aggravantes mal qualifiées** : **reproduit**. Faux verbatim toujours présent (sur un autre libellé), et surtout les deux circonstances aggravantes sont réduites à une seule (« par plusieurs personnes » omis, « usage » au lieu de « menace »).
- **(4) version d'Adrien : usage de la batte attribué à tort** : **reproduit**. La batte est de nouveau attribuée à Adrien alors que c'est le patron qui l'a prise.

**Conclusion bruit vs régression** : sur 4 défauts du tirage 1, **2 reproduits (3 et 4), 1 partiellement atténué (1), 1 absent (2)**. Les deux défauts qui persistent à l'identique (qualification des circonstances aggravantes ; attribution de la batte à Adrien) ne sont **pas du bruit de tirage** : ce sont des **faiblesses structurelles récurrentes** de l'app sur la qualification juridique et l'attribution d'actes entre co-mis-en-cause, à corriger en priorité. Les défauts 1 et 2, eux, relèvent davantage du bruit / de la variabilité de la frise.
