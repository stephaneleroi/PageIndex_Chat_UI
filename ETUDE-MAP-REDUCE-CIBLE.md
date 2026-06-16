# Étude — Fiches spécifiques à chaud (map-reduce orienté requête)

> **Statut : IMPLÉMENTÉ** (voie corpus, `services/agent.py`). Le présent document
> reste comme note de conception. Réalisé : bascule par volume dans
> `_run_corpus_simple`, map par PIÈCE (`_focused_summary`, pages conservées —
> vérifié), reduce avec citations vérifiées, concurrence bornée
> (`MAP_CONCURRENCY`), cache (`_focused_cache`). Aiguillage : intention `detail`
> **et** volume débordant le budget. Voir `ARCHITECTURE.md` §6.3.

## 1. Problème

Les **fiches génériques** (résumés par pièce, figés à l'indexation par
`generate_summaries_for_structure`) ont **deux rôles** :
1. **informer** (survol : nature, auteur, date, points saillants) ;
2. **servir de support de SÉLECTION** : c'est sur elles que `tree_search`
   raisonne pour choisir les pièces/nœuds pertinents.

Mais elles sont **génériques** : elles résument « en général », pas sous l'angle
d'une question précise. Pour une demande transversale fine — typiquement
**« quelles sont les différentes versions des personnes ? »** — il faut le
**détail** de chaque audition, pas son survol.

Aujourd'hui, deux voies couvrent partiellement ce besoin :
- **`_run_corpus_simple`** lit le **texte intégral** des pièces retenues, mais
  dans **un seul contexte** plafonné (`SIMPLE_CONTEXT_BUDGET` = 60 000 car.,
  ≤ `CORPUS_MAX_PIECES_READ` = 12 pièces). **Validé E2E** (Théo, 2 pièces) : OK
  tant que les pièces pertinentes tiennent dans le budget.
- **`_run_global_summary`** agrège les fiches génériques → bon pour la structure,
  **insuffisant pour le détail** (pas le contenu des déclarations).

**Limite à corriger :** à l'échelle (beaucoup d'auditions, ou longues), le texte
des pièces pertinentes **déborde** le contexte unique de `corpus_simple` → on
tronque, et la couverture transversale (comparer TOUTES les versions) est perdue.

## 2. Idée : map-reduce orienté requête (fiches spécifiques à chaud)

Au moment de la question (pas à l'indexation), pour une sous-question ciblée :
1. **Sélection** (inchangée) : `tree_search` sur les **fiches génériques** →
   nœuds/pièces pertinents.
2. **MAP — fiche spécifique par nœud** : chaque nœud retenu est résumé **sous
   l'angle de la sous-question** (« que dit cette pièce des *versions de X* ? »),
   dans **son propre appel LLM** → plus de plafond de contexte unique.
3. **REDUCE** : compiler les fiches spécifiques en une réponse citée.

Les **fiches génériques restent l'index de sélection** ; les **fiches
spécifiques** sont l'extraction ciblée et jetable, calculée à la demande.

## 3. CONDITION DE VIABILITÉ — les citations (le point dur)

On avait **écarté le map-reduce naïf** car son *map* paraphrase le texte et
**perd les balises `<page_N>`** → le *reduce* ne peut plus citer la page (viole
le **critère 1**, le plus important — cf. `ARCHITECTURE.md`, `DIAGNOSTIC-UEMO.md`).

**La version ciblée ne tient QUE si le map conserve la page et l'identité :**
- le texte source d'un nœud est balisé `<page_N>…</page_N>` (déjà le cas) ;
- le prompt de map doit produire chaque fait **avec sa page** : *« HASSAN
  déclare X (p. 4) »*, pas *« HASSAN déclare X »* — exactement comme la ligne
  « Points saillants » de `generate_node_summary` ;
- la fiche spécifique porte le **`doc_id::node_id`** d'origine.
Alors le reduce cite `(doc, node, page)` et **`_estimate_quality`** vérifie
toujours les pages contre les plages réelles des nœuds. **map qui CITE ≠ map qui
paraphrase.**

## 4. Architecture & point d'insertion

Se branche sur la **décomposition** déjà en place (`run_session` →
`decompose_query` → `_run_decomposed`). Aujourd'hui `_run_decomposed` route
chaque sous-question vers `_run_single_simple` ou `_run_corpus_simple`. On ajoute
une **bascule par volume** à l'intérieur de la voie corpus :

```
_run_corpus_simple(sub_question)               # services/agent.py
  1. tree_search sur fiches génériques → picked        (≈ ligne 808, inchangé)
  2. volume = Σ len(texte des nœuds des pièces picked)  (réutilise le calcul ~826)
  3. SI volume ≤ SIMPLE_CONTEXT_BUDGET :
        → lecture directe + rédaction        (comportement ACTUEL, rapide)
     SINON  →  NOUVELLE voie map-reduce :
        map  : pour chaque nœud retenu, fiche_spécifique(texte_nœud, sub_question)
               — appels bornés par SUMMARY_CONCURRENCY (sinon Ollama gèle)
        reduce : rédaction sur la concaténation des fiches spécifiques
                 (+ inventaire générique en appui), citations (doc, node, page)
```

Briques réutilisables :
- **map** : nouvelle coroutine `_focused_summary(node_text, question, model)` dans
  l'agent (un `call_llm`, `services/rag_service.py:101`), prompt dérivé de
  `generate_node_summary` (`pageindex/utils.py:785`) **+ angle question + pages
  obligatoires**. Concurrence bornée comme `generate_summaries_for_structure`
  (`SUMMARY_CONCURRENCY = 3`).
- **sélection** : le `tree_search` + `picked` existant de `_run_corpus_simple`.
- **reduce** : `_build_answer_prompt` (existant), avec en contexte les fiches
  spécifiques au lieu du texte brut.
- **garde-fou** : `_estimate_quality` (existant) vérifie les pages.

Le **drill-down niveau 2** (sélection des sections d'une pièce volumineuse,
`CORPUS_PIECE_DRILL_THRESHOLD`) reste l'étape qui fournit la liste fine des nœuds
à mapper.

## 5. Quand l'activer (sélectivement)

- **Lecture directe** (`corpus_simple` actuel) par défaut : peu de pièces, tient
  dans 60 000 car. → rapide (1 rédaction).
- **Map-reduce** uniquement quand le volume des nœuds pertinents **déborde** le
  budget, ou quand la question exige une **couverture exhaustive** (« toutes les
  versions », « comparer l'ensemble »). Décision automatique par le seuil de
  volume ; éventuellement indice de la décomposition (verbe « comparer / toutes
  les… »).

## 6. Coûts & risques (honnêtes)

- **Latence** : map-reduce = **N appels (map) + 1 (reduce)** vs 1 rédaction.
  Mesure de référence : la décomposition à 2 sous-questions sur `gpt-oss:120b` a
  pris **190 s**. N appels de map alourdissent → réserver aux cas qui le
  justifient, **concurrence bornée** obligatoire (incident de gel d'Ollama déjà
  rencontré sans borne).
- **Propagation d'erreur** : le reduce cite depuis les fiches spécifiques ; si un
  map hallucine une page, le reduce la reprend. Atténué par `_estimate_quality`
  (page ∈ plage du nœud) — mais à surveiller.
- **Conformité paradigme (critère 3)** : on reste dans « raisonnement + résumés »
  (pas de vecteurs). Le résumé ciblé à chaud est une extension naturelle du
  résumé de nœud déjà fait à l'indexation. ✓
- **Qualité (critère 2)** : meilleure couverture transversale qu'une lecture
  tronquée ou que les fiches génériques. ✓

## 7. Décisions à trancher (avant implémentation)

1. **Seuil de bascule** : volume strict (> `SIMPLE_CONTEXT_BUDGET`) seul, ou
   aussi un indice sémantique (« toutes / comparer / différentes versions ») ?
2. **Granularité du map** : par **nœud** (fin, plus d'appels) ou par **pièce**
   (sous-arbre entier, moins d'appels mais map plus gros) ?
3. **Reduce** : une seule passe, ou reduce hiérarchique si N très grand
   (regrouper les fiches spécifiques par lots) ?
4. **Cache** : mémoriser les fiches spécifiques par (nœud, question) le temps de
   la session, pour ne pas re-mapper si la question est reformulée ?
5. **UX streaming** : montrer la progression du map (« 4/9 pièces analysées »)
   ou seulement la réponse finale ?

## 8. Prochaines étapes

1. Prototyper `_focused_summary(node_text, question)` + valider que les **pages
   sont conservées** dans le résumé ciblé (test isolé, vérif `_estimate_quality`).
2. Ajouter la **bascule par volume** dans `_run_corpus_simple` (lecture directe
   vs map-reduce), concurrence bornée.
3. Valider E2E sur un dossier **volumineux** (ex. Procedure-PN-1, 25 pièces,
   question « différentes versions ») : citations à la page, couverture des
   auditions, latence mesurée.
4. Documenter dans `ARCHITECTURE.md` (nouvelle voie) si retenu.
