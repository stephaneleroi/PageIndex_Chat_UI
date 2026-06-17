# Évaluation — T1 / Théo — note CHAUVIN [main] — 2026-06-17

- **Question** : « Résume moi la note écrite par Monsieur CHAUVIN, éducateur UEHC,
  à l'attention de Monsieur LEMOINE, juge des enfants au tribunal pour enfants de
  Limoges. »
- **Source** : `../data/Dossier Théo Blanchet.pdf` (14 pages physiques).
- **Voie / aiguillage** : pas de décomposition, pas de map-reduce. `tree_search`
  retient 1 pièce (« Document 2 – NOTE D'INFORMATION »), 2 nœuds mobilisés
  (`…::0008`, `…::0009`). Question ciblée sur une pièce → voie `detail` (lecture du
  texte des nœuds). On attend donc la fidélité au texte.
- **Note globale** : **15/20** — résumé largement fidèle et bien cité sur le corps
  de la note (p. 6-8) ; un seul vrai défaut, mais structurant : un paragraphe
  étranger à la note de CHAUVIN (le « module réparation », fin du Rapport
  K. LEFEVRE, p. 5) est intégré à la synthèse, à cause d'un découpage d'arbre qui
  fait commencer le nœud de la note à `<page_5>`. Bornes de citation un peu
  approximatives sur deux paragraphes. Aucun faux verbatim (pas de guillemets),
  aucune inversion de rôle, aucune affirmation d'exhaustivité.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app (indexation) | Majeur | Le « module réparation » (journée aux Restos du Cœur de Tulle, félicitations) est présenté comme un volet de la **note de CHAUVIN** et cité **(p. 5)**. Or ce paragraphe est la **fin du Document 1** (Rapport éducatif signé **K. LEFEVRE**, section « Module réparation »), pas de la note de CHAUVIN. La note CHAUVIN (Document 2) couvre p. 6-8 et **ne contient aucun module réparation**. Contamination Doc 1 → Doc 2. | « Module réparation … Restos du Cœur de Tulle le vendredi 2 septembre … » + « K.LEFEVRE, éducatrice » puis « Document 2 » : **p. 5**. La note CHAUVIN commence « A TULLE, le 07.08.2023 … Monsieur CHAUVIN Educateur UEHC … NOTE D'INFORMATION » : **p. 6**. |
| 2 | 🔴 app (rédaction) | Mineur | Citations de page un peu décalées : le bloc « 26 juin 2023 / réintégration 4 juillet » est cité **(p. 7)** alors que le 26 juin et le 4 juillet sont **p. 6** ; le bloc « peintre / classe relais Vincent Bourdon depuis le 4 avril » est cité **(p. 8)** alors que ces faits sont **p. 7** (seuls les 3 stages + alternance Vienne débordent p. 8). | « la dernière note du 26 juin 2023 » et « réintégré … le lundi 4 juillet » : **p. 6**. « ambition de devenir peintre … classe relais du collège Vincent Bourdon depuis le 4 avril » : **p. 7**. |
| 3 | 🟡 données / inférence | Négligeable | La réponse date le module réparation du « 2 septembre **2023** » ; le source ne porte que « vendredi 2 septembre » (sans année). Année plausible mais ajoutée. (Constat secondaire au #1 : le paragraphe n'aurait pas dû être attribué à CHAUVIN du tout.) | « le vendredi 2 septembre dans le cadre de la collecte nationale » : **p. 5** (pas d'année). |
| 4 | 🔵 connu | — | Convention page physique : toutes les `(p. N)` du corps de la note (5→8) sont des pages physiques PDF, non des folios imprimés. Le « P a g e 6 | 14 » imprimé coïncide ici avec la physique — pas d'écart à signaler. | en-têtes « P a g e N | 14 » sur chaque page. |

## Analyse par section / facette

**Identité de la pièce — fidèle.** Auteur (CHAUVIN, éducateur UEHC), destinataire
(LEMOINE, juge des enfants, Tribunal pour Enfants de Limoges), objet (parcours de
placement de Théo Blanchet, né le 23 septembre 2008) : exacts (p. 6). La réponse
ajoute « UEHC **de Tulle** » — correct (« UEHC de Tulle … Monsieur CHAUVIN
Educateur UEHC », p. 6). Le signataire final est bien CHAUVIN (p. 8).

**Chronologie de placement — fidèle et bien citée (p. 6).** Placement le 05 mars
2023, faits du 13 février 2023, ITT > 8 jours, contrôle judiciaire avec interdiction
de contact (victime Samuel Villard et son père), couvre-feu **22h-6h** : tout est
vérifié p. 6. Premier bilan 23 avril (début encourageant, stupéfiants, influence
négative, effort scolaire) : p. 6, citation p. 6 correcte.

**Suivi 26 juin / synthèse 1er août — contenu fidèle, bornes de page imprécises.**
Assiduité en dents de scie, cannabis quotidien malgré CSAPA, conflit + famille
relais + réintégration UEHC le 4 juillet : exacts, mais répartis p. 6-7 (le cœur
est p. 6, cité p. 7 → #2). Relation fusionnelle/tyrannique avec la mère, harcèlement
pour argent/vêtements de marque, appels téléphoniques, présence maternelle pour
s'endormir : exacts, p. 7, citation p. 7 correcte. Bon point : la réponse dit
« sa mère » sans la nommer ni inverser de rôle ; le source la nomme **Mme GERMAIN /
Germain Sophie** (p. 7, 9) — pas d'invention, conforme à la règle « pas
d'attribution non explicite ».

**Santé / projet pro — fidèle (p. 7), citation p. 8 un peu en avance.** Quasi-cécité
d'un œil suite à maladie, demande MDPH en cours, consultation spécialisée prévue :
p. 7. Devenir peintre, classe relais Vincent Bourdon depuis le 4 avril, stages,
alternance en Vienne : p. 7 (stages + Vienne p. 8) → #2.

**Conclusion — fidèle (p. 8).** Évolution trop instable pour un retour immédiat,
poursuite jusqu'au 27 novembre 2023, puis PEAD pour sécuriser le retour en Vienne,
ou CER si évolution défavorable, accord du mineur et de la famille : exacts, p. 8,
citation p. 8 correcte.

**Le défaut central (#1).** Le « module réparation » inséré dans la synthèse
n'appartient pas à la note de CHAUVIN. La cause n'est pas une hallucination de
rédaction : le nœud mobilisé `…::0009` (« NOTE D'INFORMATION ») a son `text`
**commençant à `<page_5>`** (vérifié dans `structure.json`), donc il a avalé la fin
du Document 1 (section « Module réparation » + conclusion signée K. LEFEVRE) avant le
vrai début de la note p. 6. Le découpage de l'arbre a mal placé la frontière entre
Document 1 et Document 2. L'agent a lu fidèlement le texte du nœud et a même cité la
bonne page physique (p. 5) — mais a hérité d'une frontière de pièce fausse et a donc
attribué à CHAUVIN un passage de K. LEFEVRE. C'est imputable à l'app (indexation),
d'où le 🔴, et non un artefact des données : le PDF, lui, sépare clairement les deux
documents (« K.LEFEVRE, éducatrice » puis « Document 2 », p. 5).

## Corrections proposées (🔴 uniquement)

- **#1 (frontière de nœud)** : revoir le découpage de l'arbre pour le
  `Dossier Théo Blanchet.pdf` afin que la note de CHAUVIN (Document 2) **débute à
  `<page_6>`** et non `<page_5>` — le nœud `…::0009` ne doit pas inclure la fin du
  Rapport K. LEFEVRE (module réparation + conclusion). Comme l'indexation est non
  déterministe, contrôler via `tests/tree_gate_theo.py` après réindexation
  (la section « Module réparation », nœud 0006, doit rester rattachée au Document 1,
  pas au nœud de la note). Aucune modification de la rédaction n'est requise : une
  fois la frontière corrigée, le module réparation ne remontera plus dans la note.
- **#2 (bornes de page)** : pas d'action structurelle nécessaire — décalage d'une
  page sur deux paragraphes à cheval, dans la marge de tolérance d'une voie `detail`.
  Si on veut resserrer, c'est un effet de bord de #1 (texte commençant trop tôt) :
  corriger #1 réaligne mécaniquement les attributions de page.
