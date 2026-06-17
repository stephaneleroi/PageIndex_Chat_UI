# Évaluation — T2 Procédure composite [Etude_Open_Notebook] — 2026-06-17

- **Audit évalué** : `evaluations/2026-06-17/Etude_Open_Notebook/audits/T2_procedure.md`
  (run live, branche `Etude_Open_Notebook` @ `DEMO_1-4-g52a6913`, session `sess_kb_1781705133_2f1736`).
- **Source** : `../data/Procedure-PN-1-PDF/` (25 pièces). Vérifs déterministes
  dans le venv (`scripts/verif_source.py`).
- **Question** : synthèse composite (actes de procédure / chronologie /
  professionnels / personnes concernées) + résumé des faits reprochés +
  versions des différentes personnes.
- **Voie / aiguillage** : décomposition (1 indice) → voie corpus, `global_summary`
  (30 fiches agrégées) puis 2 passes `tree_search` (7 puis 5 pièces). map-reduce
  **non**. 34 nœuds mobilisés, 23 citations (pages 1–2). En clair : la 1re facette
  (synthèse/chronologie/acteurs) tire surtout de l'**overview/fiches** ; les facettes
  « faits reprochés » et « versions » lisent le **texte** des auditions (`detail`).
- **Note globale** : **12,5/20** — fidélité **forte sur la facette `detail`**
  (versions des auditions, identités, montants 1000/1500 €, dates GAV) ; facette
  **synthèse/chronologie (`overview`) entachée de plusieurs vrais défauts** :
  heure de début de GAV inventée pour Victor, chronologie aux horaires
  intervertis, faux verbatim + mauvaise qualification de la convocation, et une
  version (Adrien) déformée. Note app-imputable (les 🟡 ne pèsent pas).

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | majeur | « notification du **début** de la GAV de Victor Legrand (**08 h 58**) » (répété en chrono : « notification début 08 h 58 ») : **aucun 08 h 58** au dossier. La notif début Victor est dressée à **08 h 52** et la GAV prend effet à **08 h 35** (interpellation). Heure fabriquée (proche de l'avis avocat 08 h 59). | NOTIF DÉBUT GAV Victor p.1 : « Le six mai, à **huit heures cinquante deux** » ; « placé en garde à vue à compter du… **huit heures trente cinq** » |
| 2 | 🔴 app | majeur | Chronologie aux **horaires intervertis** : « **09 h 55** : carence vidéo (PV 1355) » → la carence est à **13 h 55** ; « **13 h 55** : avis à magistrat (PV 0910) » → l'avis magistrat est à **09 h 10 ». Les heures de la timeline contredisent les libellés PV cités. | Carence Vidéo p.1 : « à **treize heures cinquante cinq** » · Avis à Magistrat p.1 : « à **neuf heures dix** » |
| 3 | 🔴 app | majeur | Faux verbatim **et** mauvaise qualification : la convocation est citée entre guillemets « violences volontaires… avec deux circonstances aggravantes, **usage et menace d'arme** ». Verbatim introuvable (`quote` → faux verbatim). Surtout, les **2 circonstances aggravantes réelles** sont « **par plusieurs personnes** » + « **menace d'une arme par destination** (batte) » — pas « usage et menace d'arme ». | COPJ Victor (1705) p.1 : « 2 circonstances aggravantes en l'espèce **par plusieurs personnes avec menace d'une arme par destination**, en l'espèce une batte de baseball » ; `quote` « usage et menace d'arme » → FAUX VERBATIM |
| 4 | 🔴 app | moyen | Version d'**Adrien Lepetit déformée** : l'audit lui prête d'avoir « saisi… **ainsi que la batte de baseball, qu'ils ont tous deux utilisées pour intimider** ». Le source : Adrien a pris **le couteau** des mains du patron ; la **batte, c'est le patron qui l'a prise** « pour faire peur au gars ». Adrien ne dit nulle part avoir utilisé la batte. | Audition Lepetit p.2 : « Mon patron l'avait pris pour faire peur au gars » ; p.1 : « il a pris un couteau… Je l'ai pris de ses mains » |
| 5 | 🟡 données | — | « le médecin légiste **Romuald Lignier** a réalisé l'examen médical de **Victor Legrand** » : **fidélité à un certificat anormal** (artefact connu). Le certificat porte l'identité **LEGRAND Victor** (05/05/2000, 15 rue des iris) bien que le fichier soit nommé LEPETIT, et est « **Signé par ROMUALD LIGNIER** » (OPJ réutilisé). À noter : la *demande* d'examen (0912) concerne **Adrien** et requiert le **Dr MEDECINE DOUCE** — non hallucination, mais l'app suit le certificat, pas la demande. | Certificat (OCR `structure.json` node 0000) : « LEGRAND Victor, Né le 05/05/2000… Signé par ROMUALD LIGNIER » · Demande examen (0912) : « LEPETIT Adrien… requis Madame MEDECINE DOUCE, MÉDECIN LÉGISTE » |
| 6 | 🔵 connu | — | Imprécisions d'ordre/regroupement de la timeline (overview/fiches) hors horaires : attendu pour une synthèse agrégée sans relire le texte. | — (limite `overview`) |

## Non-constats (vérifiés exacts — à ne PAS reprocher)

- Identités : Victor né **05/05/2000**, fils de **Legrand Simon** / **Lapetite Jacqueline**, 15 rue des Iris ; Adrien né **04/04/2004**, fils de **Lepetit Jean** / **Lagrande Jacqueline**, 20 rue Macdonald Tourcoing — **exacts** (auditions + notifs début GAV).
- Montants : Victor déclare « **plus de 1000 €** » (son audition) ; témoins et OPJ parlent de **1500 €** (Lemarron, Cardon, question à Lebrun) — l'audit **distingue correctement** les deux.
- Versions **Lebrun** (droite → couteau au ventre/avant-bras → gourdin 2 coups tête), **Lemarron** et **Cardon** (≈8 h, 3 personnes, coup de poing au chemise blanche, dette 1500 €, « morceau de bois » → **Non**, échange de coups confirmé) : **fidèles** au texte.
- Fin de GAV : **Victor 17 h 25**, **Adrien 17 h 00** — **exacts**.
- **« Vice-procureure Marie INTERIEUR »** : personnage **réellement présent** au dossier (nom singulier mais authentique) → **pas** une hallucination. Convocation **chambre 105**, **10/11/2024 à 09 h 00** : exact.

## Analyse par facette

- **Facette `overview` (synthèse / chronologie / acteurs)** — la moins fiable, conforme
  à l'enseignement transverse (overview/fiches survole). Trois 🔴 s'y concentrent :
  l'heure de début GAV Victor **inventée** (08 h 58, #1), la **timeline aux horaires
  croisés** (#2), et la **convocation mal citée/mal qualifiée** (#3, faux verbatim +
  « usage et menace » au lieu de « par plusieurs personnes + menace d'arme par
  destination »). Ces écarts ne sont pas de simples omissions tolérées en overview :
  ce sont des **faits faux** (horaires, circonstances aggravantes), donc imputables.
- **Facette `detail` (faits reprochés / versions)** — globalement **fidèle**, voie de
  lecture du texte : Lebrun, Lemarron, Cardon et Victor sont restitués justement,
  avec le bon partage 1000 €/1500 €. Seul accroc : la version d'**Adrien** (#4) lui
  attribue un usage de la batte que le source réserve au patron — déformation
  d'attribution d'objet, plus grave en `detail`.
- **Citations à la page** : l'audit ne cite massivement que **p. 1–2** et émaille de
  `node_0000` génériques ; les pages cibles existent bien (pièces de 1–4 pages), donc
  pas de page fausse détectée, mais la granularité reste pauvre (peu de valeur de
  vérification page par page).

## Corrections proposées (🔴 uniquement)

1. **#1 / #2 — horaires de la chrono** : la voie overview agrège des fiches ; fiabiliser
   les **heures** suppose, pour la facette chronologie, de privilégier la **date/heure
   en-tête de chaque PV** (déjà extraite dans les fiches, champ « Date et heure ») et
   de **ne pas réécrire** un horaire de notification non présent. Vérifier que le
   gabarit de rédaction overview rappelle de **recopier l'heure de la fiche** plutôt que
   d'en déduire une (08 h 58 vient probablement d'une interpolation entre 08 h 52 et
   08 h 59).
2. **#3 — convocation** : règle grounding §6 (guillemets = verbatim) violée + fait faux.
   La rédaction doit **soit** citer le COPJ mot pour mot, **soit** paraphraser **sans
   guillemets**, et reprendre les **deux** circonstances aggravantes telles qu'écrites
   (« par plusieurs personnes » ; « menace d'une arme par destination »).
3. **#4 — version d'Adrien** : ne pas **fusionner** couteau et batte ni transférer
   l'usage de la batte (patron) à Adrien. Sur la facette `versions`, conserver
   l'attribution d'objet **par locuteur**.

Rien à corriger pour #5 (🟡, fidélité à un document anormal — la « corriger »
dégraderait la fidélité) ni #6 (🔵, limite overview).
