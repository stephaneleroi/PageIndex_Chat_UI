# Rapport comparatif A/B — `main` vs `Etude_Open_Notebook` — 2026-06-17

Campagne d'évaluation **identique** rejouée sur les deux branches, chaîne
`evaluer-reponse-sourcee` : capture live (`run_test.py`, sessions KB visibles dans
l'IHM, tamponnées branche+commit) → évaluation par le skill (confrontation au texte
source, vérifs déterministes `verif_source.py`, discipline 🔴 défaut app / 🟡
artefact de données / 🔵 limite connue).

## Conditions (strictement identiques sur les deux branches)

- **Branches** : `main` @ `ed96178` (`DEMO_1-1`) vs `Etude_Open_Notebook` @ `52a6913` (`DEMO_1-4`).
- **Modèle** : gpt-oss-120b-64k (text+light, modèle unique).
- **Budget contexte** : T1-T4 = défaut `SIMPLE_CONTEXT_BUDGET`=60000 ; **T5 = forcé `PAGEINDEX_CTX_BUDGET=2000`** (pour exercer le chemin map-reduce).
- **Index** : mêmes arbres indexés (cache partagé, aucune réindexation entre les deux).
- **Données** : `../data/` (Dossier Théo, Procedure-PN-1 [25 pièces], Rapports_LSC, Synthèse_2026).

## Notes globales

| Cas | Question | `main` | `Etude_Open_Notebook` |
|---|---|---|---|
| T1 | note CHAUVIN (1 pièce désignée) | 15 | **18** |
| T2 | dossier pénal composite (synthèse+faits+versions) | 16,5 · 16,0 · 13,5 *(3 tirages, voir §T2)* | 12,5 · 13,5 *(2 tirages)* |
| T3 | les différents rapports (4 pièces) | 12 | **16,5** |
| T4 | résumé d'un gros document (overview) | 17 | **18** |
| T5 | recommandations+chiffres (budget forcé 2000) | 15,5 | 15 |
| **Moyenne** | | **15,2** | **16,0** |

> ⚠️ **Précaution de lecture** : 1 seul tirage par cellule, à température non nulle
> (cf. CLAUDE.md principe 6). Un écart ≤ 2-3 points peut relever du **bruit** ; seuls
> les écarts **structurels** (même cause à chaque tirage) sont fiables. Pour conclure
> fermement, rejouer chaque cellule 3×.

## Différences structurelles (fiables, même cause vérifiée)

1. **Anti-contamination de frontière d'index — avantage net `Etude_Open_Notebook`.**
   Les arbres indexés ont des **bornes de pièces imparfaites** sur les fichiers
   composites (le nœud d'une pièce déborde sur la pièce voisine) : Théo (nœud 0008
   happe la fin du Document 1, p. 5) et Rapports_LSC (nœud 0000 happe Hassan p.3-5 et
   Gonzalez p.6-7).
   - `main` **reproduit la contamination** : T1 intègre le « module réparation » du
     rapport LEFEVRE à la note CHAUVIN (15/20) ; T3 décrit Hassan/Gonzalez **deux
     fois** et mal attribués (12/20).
   - `Etude_Open_Notebook` **re-ventile correctement par personne**, sans fuite : T1
     = 18/20 (aucune contamination), T3 = 16,5/20 (4 rapports propres).
   → Cohérent avec le verrou **« IDs de citation autorisés »** d'Etude_Open_Notebook
   (`_build_allowed_citations`) : la rédaction ne peut citer que des nœuds autorisés,
   ce qui limite la diffusion d'un contenu mal borné.

2. **Routage T5 (même budget 2000) — comportement différent.**
   - `main` : le **drill-down** sélectionne des sections et l'app **lit directement**
     (pas de map-reduce ; 26 citations).
   - `Etude_Open_Notebook` : la bascule **map-reduce se déclenche** (2 pièces,
     84 907 car. > 2000 → fiche ciblée par pièce → reduce ; 10 citations, pages
     conservées).
   → À conditions égales, Etude_Open_Notebook route vers le map-reduce là où main
   l'évite. Le map-reduce **fonctionne** (citations à la page préservées), mais la
   troncature forcée réduit la couverture (attendu).

## §T2 — multi-tirages (l'écart apparent était surtout de la variance)

Le 1er tirage donnait `main` 16,5 vs `Etude_Open_Notebook` 12,5 — apparemment un net
avantage `main`. **Rejoué plusieurs fois, l'écart se dissout en grande partie :**

| Branche | Tirages | Moyenne | Plage |
|---|---|---|---|
| `main` | **16,5 · 16,0 · 13,5** | ~15,3 | [13,5 ; 16,5] |
| `Etude_Open_Notebook` | **12,5 · 13,5** | ~13,0 | [12,5 ; 13,5] |

- Les **plages se chevauchent** : le **pire tirage `main` (13,5)** rejoint le meilleur
  d'Etude_Open_Notebook. T2 est un cas à **forte variance** (rédaction à température ≠ 0).
- Le défaut de **qualification des circonstances aggravantes** (réduire les 2 — « par
  plusieurs personnes » + « menace d'arme par destination » — à une seule, ou « usage »
  au lieu de « menace ») apparaît **sur les deux branches selon le tirage**
  (Etude_ON tirages 1-2 ; `main` tirage 3) → **faiblesse commune**, pas une régression
  de branche.
- `main` a, en moyenne, des tirages un peu meilleurs, mais l'écart **n'est pas
  statistiquement séparé** sur 2-3 tirages. Conclusion : **pas de supériorité de branche
  fiable sur T2** ; c'est un cas instable à faiblesse commune. *(Leçon de méthode : ne
  jamais conclure une différence de branche sur un seul tirage — cf. principe 6.)*

## Défauts communs aux deux branches (indépendants de la branche)

- **Faux verbatims** : guillemets posés sur des paraphrases (T2 sur les deux
  branches). La règle de grounding « guillemets = verbatim exact » n'est pas
  toujours respectée par la rédaction.
- **Affirmation d'exhaustivité/absence en map-reduce** : T5 Etude_ON conclut « le
  rapport ne formule pas de recommandation numérique » alors que la p. 72 en porte
  cinq — le contexte par pièce était **tronqué** (budget 2000). La règle
  anti-exhaustivité (§3 grounding) **n'est pas répercutée dans le gabarit *reduce***
  du map-reduce.
- **Contamination de chiffres voisins en synthèse globale** (`overview`) : sur
  `main`, T4 a produit « 524 milliards » (au lieu de 524 M€) et « 215 800 bornes »
  (au lieu de 184 141) — recopie d'un nombre voisin à l'agrégation des fiches.
- **Pages en `overview`** : citations à la **plage de pièce**, parfois décalées de
  ±1-2 pages (limite connue 🔵, page physique ≠ folio).

## Correctifs actionnables (par ordre d'impact)

1. **Reborner les pièces à l'indexation** (fichiers composites Théo, Rapports_LSC) —
   c'est la cause racine des plus gros écarts (T1, T3) sur `main`. Contrôle :
   `tests/tree_gate_theo.py` après réindexation.
2. **Répercuter l'anti-exhaustivité dans le gabarit *reduce*** du map-reduce
   (`services/prompts/*.jinja`) : « contexte par pièce tronqué — ne jamais conclure
   à l'absence, signaler au plus que l'élément n'apparaît pas dans l'extrait ».
3. **Renforcer guillemets=verbatim** (déjà au grounding) — la rédaction le viole
   encore : à durcir/illustrer dans le gabarit.
4. **Anti-contamination de chiffres** en synthèse globale (T4 main) : rappeler de
   ne pas réutiliser un nombre d'un autre point saillant.

## Bilan

Le seul écart **structurel et fiable** est en faveur d'`Etude_Open_Notebook` :
l'**anti-contamination** des fichiers composites (T1, T3) — vraisemblablement le verrou
« IDs autorisés » — où `main` laisse fuir le contenu d'une pièce mal bornée et
Etude_Open_Notebook re-ventile proprement. L'avantage apparent de `main` sur **T2 s'est
révélé être surtout de la variance** (multi-tirages : plages qui se chevauchent,
faiblesse commune sur la qualification pénale — voir §T2). Le routage **T5** diffère
(map-reduce sur Etude_ON, lecture directe sur `main`, budget égal). Les défauts de fond
(faux verbatims, exhaustivité en map-reduce, contamination de chiffres en overview,
bornes d'index) sont **communs** et constituent la feuille de route.

> ⚠️ Comparaison à **2-3 tirages par cellule** : seul T1/T3 (anti-contamination) est
> un écart franc et répété. Pour T2/T4/T5, prévoir plus de tirages avant toute
> conclusion ferme de branche.

Détail par cas : `*/EVAL_T*.md` (T2 : `*/EVAL_T2_procedure*.md`) ; captures et
traces : `*/audits/T*.md`.
