# Contexte de la campagne d'évaluation

- **Date** : 2026-06-17
- **Branche testée (au run)** : `Etude_Open_Notebook`
- **Commit (au run)** : `6c98178` (describe : `DEMO_1-2-g6c98178-dirty`)
- **État du dépôt** : 1 fichier(s) modifié(s) (dirty) au lancement
- **Modèle** : gpt-oss-120b-64k (text+light, modèle unique)
- **Seuil contexte** : T1-T4 = défaut (`SIMPLE_CONTEXT_BUDGET`=60000) ; T5 = forcé `PAGEINDEX_CTX_BUDGET=8000` (déclenchement map-reduce)
- **Chaîne** : capture via `scripts/run_test.py` (session KB réelle, visible IHM) → évaluation via le skill `evaluer-reponse-sourcee`.

| Cas | Dossier | Question |
|---|---|---|
| T1 | Dossier Théo | note CHAUVIN → LEMOINE |
| T2 | Procedure-PN-1 (25 pièces) | synthèse composite (actes/chrono/pro/personnes + faits + versions) |
| T3 | Rapports_LSC (4 rapports) | résumé des différents rapports |
| T4 | Synthèse_2026 | résumé (overview) |
| T5 | Synthèse_2026 | recommandations + constats chiffrés (map-reduce forcé) |
