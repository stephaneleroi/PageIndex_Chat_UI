# Évaluation — T1 Théo / note CHAUVIN [Etude_ON] — 2026-06-17

- **Question** : « Résume moi la note écrite par Monsieur CHAUVIN, éducateur UEHC, à
  l'attention de Monsieur LEMOINE, juge des enfants au tribunal pour enfants de Limoges. »
- **Voie / aiguillage** : voie KB, **map-reduce : non**, **décomposition : 0** → question
  mono-intention de type `detail` (lecture du texte). 1 pièce retenue par `tree_search`
  (« Document 2 – NOTE D'INFORMATION »). Nœuds mobilisés : `…::0008` et `…::0009`.
  Citations dans la réponse : node_0008, pages 6, 7, 8.
- **Source** : `../data/Dossier Théo Blanchet.pdf` (14 pages). La note CHAUVIN = **Document 2**,
  pages physiques **6 à 8** (en-tête + 07.08.2023 p. 6 ; corps p. 6-7 ; conclusion + signature p. 8).
- **Note globale** : **18/20** — résumé fidèle, fait par fait traçable au texte, citations de
  page **exactes**, verbatim correct, aucune hallucination ni contamination. Les seuls points
  retirés sont des **omissions mineures** (nom de la mère, participants de la synthèse) tolérables
  pour un résumé, et une **imprécision d'ancrage de citation** (tout attribué à node_0008) qui
  relève d'un artefact d'indexation, pas de la rédaction.

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔵 connu | — | Citations `(p. 6/7/8)` = pages **physiques** : tous les faits cités tombent juste sur ces pages | en-tête + 07.08.2023, ITT > 8 j, CJ 22h-6h **p. 6** ; relation fusionnelle, œil, peintre **p. 7** ; conclusion + signature CHAUVIN **p. 8** |
| 2 | 🔵 connu | — | Le verbatim « en dents de scie » (seuls guillemets de la réponse) est un **vrai verbatim** | `quote` → présent tel quel **p. 6** |
| 3 | 🟡 données | — | La réponse cite **node_0008** pour tout, alors que le corps de la note est dans node_0009 ; le nœud 0008 indexé **déborde sur la p. 5** (fin du rapport K. LEFEVRE) — d'où une fiche 0008 « auteur CHAUVIN avec contribution de K. LEFEVRE ». Borne d'indexation, **pas** une erreur de rédaction : la réponse n'a **repris aucun contenu de la p. 5** | `structure.json` node 0008 `text` commence `<page_5>…K.LEFEVRE` ; page 5 = fin Document 1 (rapport LEFEVRE) |
| 4 | 🔴 app | mineure | **Omission** : la mère, nommée **Mme GERMAIN** dans la note (synthèse du 1er août, p. 7), n'est jamais nommée (« sa mère » / « relation mère-fils ») | `grep GERMAIN` → p. 7 « en présence de Théo, Mme GERMAIN » ; p. 2, 3, 4, 11 |
| 5 | 🔴 app | très mineure | **Omission** : la synthèse du 1er août s'est tenue « en présence de Théo, Mme GERMAIN et l'éducatrice de milieu ouvert » — participants non restitués | p. 7 |
| 6 | 🔵 connu | — | Imprécisions de résumé sans contresens : « consultation spécialisée prévue » (source : « …pour évaluer la possibilité d'une opération chirurgicale », p. 7) ; « 4 avril 2023 » (source : « 4 avril », l'année est inférée du contexte) | p. 7-8 |

## Analyse par section / facette

- **Identité de la pièce** (auteur, destinataire, date) : exacte. CHAUVIN, éducateur UEHC ;
  LEMOINE, juge des enfants, TPE Limoges ; 07.08.2023. La réponse précise « UEHC de **Tulle** »
  (p. 6 : « UEHC de Tulle ») — ajout correct, non contaminant. La signature finale CHAUVIN (p. 8)
  est bien rendue, sans inventer de co-signataire (la note CHAUVIN n'est pas de LEFEVRE :
  pas d'inversion de rôle).
- **Chronologie et faits** (placement 05.03.2023, faits du 13.02.2023, ITT > 8 j, CJ + couvre-feu
  22h-6h, notes des 23.04 / 26.06, fugue, famille relais à Tréouergat, UEAJ, retour UEHC le
  4 juillet, synthèse du 1er août) : **tous présents et exacts**, chacun sur la page citée.
- **Volet familial / santé / scolaire / conclusion** : fidèles. Œil quasi aveugle + MDPH (p. 7),
  ambition peintre + classe relais collège Vincent Bourdon + stages + alternance « dans la Vienne »
  (p. 7-8), conclusion (pas de retour immédiat, accompagnement psy, poursuite jusqu'au 27.11.2023,
  PEAD ou CER en cas d'évolution défavorable, accord du mineur et de la famille, p. 8) : conformes.
- **Pas de contamination** : aucun élément du **rapport K. LEFEVRE** (p. 1-5 : module réparation /
  Restos du Cœur, « 14 ans », « carapace », préconisation d'une MEJ d'un an) ni des autres documents
  (ordonnance p. 9-10, rapport CEF p. 11-13) n'a fui dans le résumé. C'est le point fort : malgré un
  nœud indexé dont le texte déborde sur la p. 5, la rédaction est restée cantonnée à la note CHAUVIN.
- **Grounding** : pas d'affirmation d'exhaustivité, pas de rôle inversé, pas de faux verbatim.

Verdict de voie : exécution `detail` conforme aux attentes (fidélité au texte) ; la fidélité prime
nettement sur les rares omissions de détail, normales pour un résumé.

## Corrections proposées (🔴 uniquement)

Les deux 🔴 sont des **omissions mineures de détail**, non des erreurs de fait ; aucune correction
de code n'est requise. Si l'on veut une restitution plus complète, un léger renforcement de
l'instruction de résumé pour **conserver les noms propres des personnes** (ici « Mme GERMAIN »)
et les **participants des réunions/synthèses** suffirait. Le constat #3 (ancrage node_0008 vs 0009
et débordement p. 5) est un **artefact d'indexation** (borne de pièce) : pour le citoyen-lecteur il
n'a pas d'effet ici, mais si l'on souhaite une citation au plus juste, resserrer la borne de la pièce
« Document 2 » pour qu'elle ne happe pas la fin du Document 1 (p. 5) améliorerait la précision des
`(p. N)` — hors périmètre de cette réponse, à traiter côté indexation, pas côté rédaction.
