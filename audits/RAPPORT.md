# Rapport d'analyse des tests — 2026-06-16 21:14

Réindexation complète (code actuel) puis 4 tests E2E. Sessions visibles dans
l'IHM (page Questions-réponses). Audits détaillés : `audits/test*.md`.

| Test | Voie / algo | Sous-q. | map-reduce | nœuds | citations | durée | session |
|---|---|---|---|---|---|---|---|
| Test 1 | synthèse globale (sur fiches à froid — aucun tree_search) | 0 | non | 6 | 6 | 50s | `sess_kb_1781636392_dd714e` |
| Test 2 | DÉCOMPOSÉE (3 sous-questions) → voie corpus / mono-pièce — tree_search + lecture du texte | 3 | non | 36 | 2 | 703s | `sess_kb_1781636442_0f8e94` |
| Test 3 | synthèse globale (sur fiches à froid — aucun tree_search) | 0 | non | 4 | 4 | 50s | `sess_kb_1781637145_20704b` |
| Test 4 | synthèse globale (sur fiches à froid — aucun tree_search) | 0 | non | 6 | 12 | 61s | `sess_kb_1781637195_bffbe1` |

## Lecture
- **Test 1 (Théo, pièce unique)** : doit citer la note CHAUVIN sans contamination ; vérif pages vs PDF dans l'audit.
- **Test 2 (Procedure, composite)** : doit être DÉCOMPOSÉ ; la facette « versions » doit mobiliser tree_search + lecture du texte (voire map-reduce si volumineux).
- **Test 3 (Rapports)** : doit distinguer les 4 rapports.
- **Test 4 (Synthèse)** : synthèse d'ensemble d'un gros document.

Chaque audit détaille : voie empruntée, étapes (tree_search/map_reduce), nœuds
utilisés, citations (node, page) et — pour le test 1 — la cohérence des pages
citées contre le PDF. À valider manuellement demain dans l'IHM.
