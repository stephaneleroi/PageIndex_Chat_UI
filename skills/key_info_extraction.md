---
name: Lecture rapide de document (générique)
description: Génère une fiche de lecture rapide structurée pour tout type de document : articles de recherche / rapports techniques / livres blancs / manuels utilisateur / rapports financiers / contrats / documents de politique
enabled: true
---

## Conditions d'activation (Triggers)
Activer la skill lorsque la question de l'utilisateur correspond à l'un des schémas suivants :
- Type aperçu : `de quoi parle ce document / lis-moi ce document / summarize / TL;DR / résume-moi en une phrase`
- Type survol : `conclusions principales / contenu principal / points clés / les points forts de ce rapport`
- Type navigation : `quels sont les chapitres / structure du document`

## Cas de non-déclenchement (Anti-triggers)
Dans les situations suivantes, **ne pas** appliquer cette skill, mais répondre à la question spécifique posée :
- L'utilisateur demande un chiffre précis, une clause précise, une étape d'algorithme précise → suivre le flux de recherche exacte
- L'utilisateur a indiqué un nom de chapitre / un numéro de page → lire directement avec `read_node`, ne pas faire une lecture rapide de tout le document
- L'utilisateur demande une comparaison → basculer vers la skill « analyse comparative »

## Flux d'exécution
1. `tree_search` avec la question de l'utilisateur comme query (si l'utilisateur dit seulement « de quoi ça parle », utiliser les mots-clés du sujet du document comme query) : localiser 3 à 6 nœuds de premier niveau les plus représentatifs.
2. Appeler `summarize_nodes` sur les nœuds localisés, en **passant tous les node_ids en une seule fois par lot**, afin d'éviter des résumés fragmentés sur plusieurs tours.
3. En mode visuel, si le document contient des pages comportant des figures ou tableaux manifestes, ajouter un appel `view_pages(focus="conclusion générale/figure clé")` sur 1 ou 2 nœuds les plus importants.
4. Synthétiser toutes les observations et produire le résultat selon le format de sortie ci-dessous. **Ne pas** effectuer un 4e tour de `tree_search` de secours inutile — la convergence doit se faire en 3 tours.

## Structure de sortie adaptative
**Déterminer d'abord le type de document** (déduit du titre, de la table des matières, du résumé), puis choisir le modèle correspondant :

### A. Recherche / Académique
- **Type de document** : article de recherche / rapport technique
- **Lecture rapide en une phrase** : …
- **Question de recherche / problème résolu** : …
- **Méthode principale** : …
- **Conclusions clés** : … (lister 2 à 4 points)
- **Limites / perspectives futures** : …

### B. Commercial / Financier
- **Type de document** : rapport financier / livre blanc / analyse de marché
- **Lecture rapide en une phrase** : …
- **Indicateurs clés** : … (si des chiffres sont mentionnés, indiquer obligatoirement le numéro de nœud et la page)
- **Principaux risques / opportunités** : …
- **Recommandations finales** : …

### C. Ingénierie / Opérationnel
- **Type de document** : manuel utilisateur / spécification technique / mode opératoire standard (SOP)
- **Lecture rapide en une phrase** : …
- **Périmètre couvert** : produits / versions / scénarios applicables
- **Processus principal** : à détailler étape par étape
- **Points de vigilance / pièges courants** : …

### D. Juridique / Conformité
- **Type de document** : contrat / politique / clauses
- **Lecture rapide en une phrase** : …
- **Parties concernées** : …
- **Obligations / droits principaux** : …
- **Durée / conditions de résiliation / défaillance** : …

### E. Générique (lorsque le type n'est pas clair)
- **Type de document** : non classé
- **Lecture rapide en une phrase** : …
- **Chapitres principaux** : …
- **Informations clés** : lister 3 à 5 points
- **Questions de suivi potentielles** : lister 2 à 3 points

## Guardrails (anti-hallucination)
- **Interdit** d'inventer des conclusions absentes de l'Abstract / de l'Introduction.
- Si `summarize_nodes` renvoie un contenu trop maigre (< 100 caractères), il faut faire un appel supplémentaire à `read_node` avant de résumer, plutôt que de combler artificiellement.
- Tous les chiffres, années, pourcentages, noms de personnes → doivent être accompagnés du numéro de nœud source.
- Si après plusieurs tours de recherche l'information centrale reste introuvable, répondre honnêtement « cette information n'est pas explicitement mentionnée dans le document », sans remplir pour faire du volume.
