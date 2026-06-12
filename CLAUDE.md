# CLAUDE.md — règles de travail sur ce projet

## Lancement et environnement

- Toujours lancer dans le venv : `.venv/bin/python main.py` (port 5001).
- Modèles locaux via Ollama (`config.json`, hors git) : `text` =
  nemotron-3-super (rédaction), `light` = gpt-oss-20b-128k (indexation +
  agent), `vision` = qwen3.6 (OCR, pages).

## ⚠️ Piège n°1 : ne JAMAIS modifier un fichier .py pendant une indexation

Le serveur de développement (Werkzeug) recharge à chaque modification d'un
fichier Python importé, ce qui **tue les indexations en cours** : les pièces
interrompues passent en erreur. Avant d'éditer du code, vérifier qu'aucun
document n'est en `pending`/`indexing` (`GET /api/documents`). Pièces en
erreur : bouton « Relancer » (ou `POST /api/documents/<id>/retry`).

## Principes structurants (décisions utilisateur, ne pas revenir dessus)

1. **Paradigme PageIndex pur** : le retrieval passe exclusivement par le
   raisonnement sur l'arbre (titres + résumés). `keyword_search`,
   `summarize_nodes` et le repli littéral de `cross_search` sont désactivés
   (code conservé). Quand une pièce est introuvable, le correctif est
   d'améliorer l'arbre (résumés identitaires), jamais la recherche littérale.
2. **L'application ne doit pas dégrader le modèle** : hors documents
   (conversation libre), le modèle est interrogé NU — aucune instruction
   système, aucun style, aucune température imposée. Voir DIAGNOSTIC-UEMO.md
   pour la démonstration (les consignes de directivité font confabuler).
   Aucune température n'est imposée nulle part : réglages Modelfile.
3. **Toujours vérifier les renvois aux pages** : toute évolution touchant
   citations/réponses se valide en contrôlant les pages citées contre le
   texte réel du PDF (cf. tests/accept_chauvin.py).
4. **Simplicité** : modifications minimales et ciblées, pas de
   sur-conception. Les évaluations factuelles de prompts se font sur
   PLUSIEURS tirages (les Modelfiles sont à température non nulle).

## Documentation à maintenir

- `ARCHITECTURE.md` : fonctionnement interne — à mettre à jour à chaque
  évolution structurelle ; indique précisément où PageIndex est utilisé et
  où il ne l'est pas, et la liste des modifications locales de `pageindex/`.
- `pageindex/` est une copie embarquée de VectifyAI/PageIndex (fork de
  fait) : toute modification s'y documente dans ARCHITECTURE.md, sans
  jamais toucher au paradigme ni aux prompts canoniques du cookbook.

## Tests

- `tests/accept_chauvin.py` : test d'acceptation de bout en bout (question
  réelle, 9 critères, pages vérifiées contre le PDF).
- `tests/tree_gate_theo.py` : contrôle de l'arbre après réindexation
  (l'indexation est non déterministe).
- L'IHM se teste visuellement via Chrome headless + CDP (websocket-client
  installé dans le venv). Après un push, recharger l'onglet (Cmd+R) sinon
  l'ancien JS reste actif.

## Données

- Corpus de référence : `../data/Procedure-PN-1-PDF/` (25 pièces réelles).
- Les arbres indexés sont cachés à côté des PDF sources
  (`<nom>.pdf.pageindex.json`, clé SHA-256) : réimporter ne refait aucun
  appel LLM. `SOURCE_DATA_DIR` (défaut `../data`) configure la racine.
