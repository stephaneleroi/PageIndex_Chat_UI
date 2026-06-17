# Évaluation — T2 — Procédure composite (Procedure-PN-1) — 2026-06-17

- **Question** : synthèse d'un dossier pénal (actes de procédure, chronologie,
  professionnels, personnes concernées) + résumé des faits reprochés + versions
  des différentes personnes concernées.
- **Voie / aiguillage** : décomposition en 3 sous-questions, map-reduce **non**.
  - Facette 1 « synthèse / acteurs » → **overview** (agrégation des fiches, 30 pièces).
  - Facette 2 « faits reprochés » → **detail** (lecture du texte ; 7 pièces retenues).
  - Facette 3 « versions » → **detail** (5 auditions relues : Legrand, Lepetit,
    Lebrun, Lemarron, Cardon).
  - Aiguillage **correct** : « versions » est bien parti en `detail`/texte.
- **Note globale** : **16/20** — réponse globalement fidèle et bien structurée ; les
  cinq versions sont restituées avec exactitude (voie `detail`). Trois défauts
  réels (🔴) restent : une contamination de montant sur la plainte Lebrun, un faux
  verbatim sur la qualification, une imprécision sur la position de Cardon. Le reste
  des « anomalies » apparentes (Lignier médecin) sont des artefacts de données (🟡).

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | moyenne | Plainte Lebrun : « il évoque également un différend d'un montant d'environ 1 000 € » — Lebrun ne mentionne **aucun** montant qu'il devrait ; il **nie** devoir quoi que ce soit. Le « 1000 € » vient de l'audition de **Legrand**, pas de la plainte → montant contaminé d'une pièce à l'autre, attribué à la mauvaise version. | Plainte LEBRUN p.2 : « Mr LEGRAND a indiqué […] que vous devriez 1500€ ? — Non je ne lui dois rien. […] différent au sujet de l'achat d'un appartement ». Montant 1000 € : audition LEGRAND p.2 « Plus de 1000€. C'est un problème d'appart. » |
| 2 | 🔴 app | faible | Faux verbatim : « violences qualifiées d'« aggravées par deux circonstances » ». Le source porte « VIOLENCE AGGRAVEE PAR DEUX CIRCONSTANCES » (titre de qualification), pas la formule guillemetée. La glose « (usage d'une arme par destination et présence de plusieurs agresseurs) » est une interprétation non écrite telle quelle. | `quote` → FAUX VERBATIM. Compte-rendu d'enquête p.1 : « 1 - VIOLENCE AGGRAVEE PAR DEUX CIRCONSTANCES SUIVIE D'INCAPACITE N'EXCEDANT PAS 8 JOURS » ; « VICTIME BLESSEE PAR ARME PAR DESTINATION (Batte de base ball) ». |
| 3 | 🔴 app | faible | Cardon décrit comme « dehors du même café aux environs de 8 h 00 ». Cardon est **attablé dans** le café à 08h00 ; il n'est « dehors » qu'au moment de la bagarre (« la bagarre a eu lieu dedans et moi j'étais dehors »). Inversion d'un détail de position en voie `detail`. | Audition CARDON p.1 : « j'étais attablé aux environs de 08h00 à prendre un café à "le temps Des secrets" » ; plus loin « moi j'étais dehors ». |
| 4 | 🟡 données | — | « Le médecin légiste Romuald Lignier […] a effectué un examen médical et certifié la compatibilité […] (certificat médical) ». Reproduction **fidèle** du certificat anormal : champ médecin vide, identité de LEGRAND (05/05/2000, 15 rue des iris) sur un fichier nommé LEPETIT, « Signé par ROMUALD LIGNIER » (nom de l'OPJ réutilisé). Artefact connu, **pas** une hallucination. | Certificat médical (LEPETIT) p.1 : « 05/05/2000 à LILLE / 15/15, rue des iris à LILLE / Signé […] par ROMUALD LIGNIER ». Aucune occurrence « Docteur » dans la réquisition. |
| 5 | 🟡 données | — | Témoins Lemarron et Cardon font état d'un montant de **1 500 €** réclamé par le patron, alors que Legrand parle de 1000 € et Lebrun nie tout : divergence **présente dans les données** (versions discordantes). L'app la restitue correctement par témoin. | LEMARRON p.1 « il lui devait 1500€, je crois » ; CARDON p.1 « lui devoir 1500€ ». |
| 6 | 🔵 connu | — | Citations `(p. N)` = pages physiques du PDF ; vérifiées exactes (Legrand p.1-2, Lebrun p.1-3, etc.). Pas de décalage imputable. | — |
| 7 | 🔵 connu | — | Facette « acteurs » en `overview` : ordre chronologique avec quelques glissements (lignes 17h25 / 17h45 / 17h00 mal ordonnées en fin de liste). Survol attendu de la voie fiches, données exactes par ailleurs. | — |

## Analyse par facette

**Facette 1 — synthèse / acteurs (overview).** Solide. Les rôles sont correctement
attribués : Romuald LIGNIER (major, OPJ), Marie INTERIEUR (vice-procureure près le
TJ de Lille, lève les GAV — confirmé sur les notifications de fin), le procureur
(COPJ), le bâtonnier (avis avocat). Les identités sensibles sont **toutes justes**,
y compris les noms-pièges : Victor LEGRAND fils de **LEGRAND Simon** et **LAPETITE
Jacqueline** ; Adrien LEPETIT fils de **LEPETIT Jean** et **LAGRANDE Jacqueline**
(vérifié sur audition + avis à magistrat + compte-rendu). Lebrun = victime,
SECRÉTAIRE ; Lemarron + Cardon = témoins. Aucune inversion de rôle introduite par
l'app. Les seuls défauts sont d'ordonnancement (🔵, attendu en overview).

**Facette 2 — faits reprochés (detail).** Fidèle dans l'ensemble : interpellation
08h35 au café « Le temps des secrets », 15 rue des Iris ; saisie de la batte ;
aveux de Legrand (poussé, insulté, coups de poing, batte « pour faire peur »,
couteau repris par le serveur, non utilisé) ; qualifications du compte-rendu
(violence aggravée par deux circonstances / arme par destination / ITT ≤ 8 jours).
Deux défauts : le **montant 1 000 € faussement prêté à la plainte Lebrun** (constat
n°1, contamination) et le **faux verbatim** sur la qualification (n°2).

**Facette 3 — versions (detail).** C'est la facette la mieux traitée. Les cinq
versions sont restituées avec exactitude par rapport au texte relu :
- **Legrand** : télé, poussée, insultes, coups, batte pour intimider, couteau repris
  par le serveur non utilisé, « plus de 1000 € », refus de confrontation, accord
  prélèvement — tout vérifié p.1-2.
- **Lepetit** : défense du patron, coups de poing, récupération du couteau rangé
  « avec les autres couteaux », batte présente au bar — vérifié p.1-2.
- **Lebrun** : venu récupérer la télé, « droite » reçue, couteau pointé/piqué à
  l'avant-bras, gourdin → deux coups à la tête, insultes/menaces, réfugié dans son
  véhicule — vérifié p.1-3.
- **Lemarron / Cardon** : trois personnes qui s'agrippent, patron frappe l'homme en
  chemise blanche, 1500 €, serveur qui s'interpose, coups échangés des deux côtés —
  vérifié. Seule scorie : la **position de Cardon** (constat n°3).

Enseignement conforme à l'attendu : sur ce dossier composite, la voie `detail`
(texte) est nettement plus fiable que la voie `overview` (fiches). Les défauts
résiduels sont localisés et de faible gravité ; aucune hallucination pure, aucune
identité ni rôle inventés.

## Corrections proposées (🔴 uniquement)

- **Constat n°1 (contamination de montant)** — défaut de grounding inter-pièces :
  un montant (1000 €) tiré de l'audition Legrand a été ré-attribué à la plainte
  Lebrun, qui dit l'inverse. Piste : renforcer dans le gabarit de grounding
  `detail` la consigne « rattacher chaque chiffre à la pièce/locuteur d'où il
  provient ; ne pas transférer un montant d'une version à une autre » (règle 5
  app-specifics, étendue aux chiffres). À évaluer sur plusieurs tirages.
- **Constat n°2 (faux verbatim)** — guillemets posés sur une quasi-paraphrase de
  l'intitulé de qualification. Piste : rappel du verrou « guillemets = verbatim
  exact uniquement » (règle 6) ; les libellés de qualification doivent être cités
  tels quels ou reformulés sans guillemets.
- **Constat n°3 (position de Cardon)** — détail de localisation inversé en voie
  `detail`. Mineur ; relève de la fidélité fine attendue de `detail`. Pas de
  changement structurel justifié pour ce seul écart ; à surveiller.

---

## Résumé

Réponse **fidèle dans l'ensemble et bien aiguillée** (décomposition correcte, les
trois facettes sur la bonne voie ; « versions » en `detail` = exactes). **Note :
16/20.** Trois vrais défauts d'app (🔴), tous de gravité faible à moyenne : (1)
contamination du montant « 1 000 € » prêté à tort à la plainte Lebrun alors que
Lebrun nie toute dette ; (2) faux verbatim sur « aggravées par deux circonstances » ;
(3) Cardon dit « dehors » à 8h00 alors qu'il était attablé dans le café. Les
apparentes anomalies « Lignier médecin / examen de Victor » et la divergence des
montants 1000/1500 € sont des **artefacts des données** (🟡), pas des hallucinations :
l'app reproduit fidèlement un certificat mal rempli et des versions discordantes.
Identités, parents (pièges LAPETITE/LAGRANDE), rôles et pages citées : tous justes.
