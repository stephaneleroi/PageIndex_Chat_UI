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
| T2 | dossier pénal composite (synthèse+faits+versions) | **16,5** | 12,5 |
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

## Différences possiblement liées au bruit (à confirmer en multi-tirages)

3. **T2 (composite) — avantage apparent `main` (16,5 vs 12,5).** Sur ce tirage,
   `Etude_Open_Notebook` a inventé une heure de début de GAV (08 h 58) et **interverti
   des horaires** de la chronologie (facette `overview`). `main` était plus propre sur
   la chronologie. À rejouer : peut être un tirage défavorable plutôt qu'une régression.

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

À ce tirage, `Etude_Open_Notebook` est **devant en moyenne (16,0 vs 15,2)**, porté
par un **avantage structurel net sur l'anti-contamination** des fichiers composites
(T1, T3) — vraisemblablement le verrou « IDs autorisés ». `main` reste devant sur
T2 (à reconfirmer). Les défauts de fond (faux verbatims, exhaustivité en map-reduce,
contamination de chiffres en overview, bornes d'index) sont **communs** et
constituent la feuille de route. Détail par cas : `*/EVAL_T*.md` ; captures et
traces : `*/audits/T*.md`.
