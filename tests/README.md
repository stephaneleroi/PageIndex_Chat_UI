# Tests de validation

Scripts utilisés pour valider le projet en conditions réelles (venv requis,
serveur lancé, Ollama actif) :

- `accept_chauvin.py` — test d'acceptation de bout en bout sur le « Dossier
  Théo Blanchet » : question sur la note de M. CHAUVIN, 9 critères dont la
  vérification de CHAQUE renvoi de page contre le texte réel du PDF.
- `tree_gate_theo.py` — contrôle qualité de l'arbre d'indexation du dossier
  Théo contre la vérité terrain du PDF (chaque pièce à sa vraie page).
- `make_corpus_50_pieces.py` — fabrique un corpus simulé de 50 pièces de
  procédure pré-indexées (sans coût LLM) pour tester le scénario
  multi-documents : inventaire complet, retrieval ciblé (la pièce n°47 porte
  un fait unique), plafond de cross_search. Redémarrer le serveur après
  génération ; supprimer les pièces depuis l'IHM après les tests.

Exécution : `PYTHONPATH=. .venv/bin/python tests/<script>.py`
