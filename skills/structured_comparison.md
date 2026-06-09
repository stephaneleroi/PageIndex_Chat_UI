---
name: Analyse comparative structurée
description: Réalise une comparaison multidimensionnelle entre deux objets ou plus au sein d'un document (chapitres / méthodes / clauses / versions / produits / données)
enabled: true
---

## Conditions d'activation (Triggers)
- `compare A et B / la différence entre les deux / lequel est le meilleur / écart / points communs et différences / avantages et inconvénients`
- `solution 1 vs solution 2 / ancienne version vs nouvelle version / baseline vs notre méthode`
- L'utilisateur énumère explicitement ≥ 2 objets à comparer

## Cas de non-déclenchement (Anti-triggers)
- L'utilisateur ne mentionne qu'1 seul objet → ne pas forcer une comparaison, répondre par un échange classique
- L'utilisateur interroge sur une « relation » et non une « différence » (ex. « A fait-il partie de B ? ») → ne pas appliquer cette skill

## Flux d'exécution

### Étape 1. Préciser les objets et les dimensions de comparaison
- Extraire de la question de l'utilisateur les **objets** à comparer (idéalement 2 à 4).
- Si l'utilisateur n'a pas précisé les dimensions de comparaison, appliquer par défaut selon le type d'objet :
  - Méthode / algorithme : `idée centrale / complexité / entrées-sorties / avantages / limites / scénarios d'application`
  - Produit / version : `fonctionnalités / performance / compatibilité / prix / public cible`
  - Clauses contractuelles : `périmètre d'application / obligations / durée / responsabilité en cas de manquement / conditions de résiliation`
  - Résultats expérimentaux : `jeu de données / métriques / configuration / valeurs / significativité`

### Étape 2. Rechercher chaque objet séparément
**Essentiel : appeler `tree_search` indépendamment pour chaque objet**, ne pas chercher plusieurs objets en une seule recherche (ils contaminent mutuellement le rappel).

- Pour l'objet A : `tree_search(query="<objet A>")` → `read_node(...)` ou `summarize_nodes(...)`
- Pour l'objet B : `tree_search(query="<objet B>")` → `read_node(...)` ou `summarize_nodes(...)`
- … et ainsi de suite

### Étape 3. Si les dimensions de comparaison impliquent des indicateurs chiffrés
- Effectuer en plus un `keyword_search(keyword="<nom de l'indicateur>")` pour s'assurer qu'aucun chiffre n'est omis
- En mode visuel, si l'indicateur provient d'une figure ou d'un tableau → `view_pages(focus="comparaison de <nom de l'indicateur>")`

### Étape 4. Sortie

## Format de sortie

**Objets comparés** : A = …, B = … (, C = …)  
**Dimensions de comparaison** : …

### Tableau comparatif global
| Dimension | A | B | C |
|---|---|---|---|
| … | … | … | … |

### Points de différence clés (2 à 4 points)
1. **<Point de différence 1>** : A est …, tandis que B est … ; cela signifie que …
2. **<Point de différence 2>** : …

### Points communs
- …

### Évaluation globale
Donner, sur la base des informations du document :
- **Scénarios où A est à privilégier** : …
- **Scénarios où B est à privilégier** : …
- Si le document fournit lui-même une conclusion (ex. la best method d'un article, la solution recommandée d'un contrat), la citer directement

## Guardrails (anti-hallucination)
- **Strictement interdit** d'inventer une information de dimension non mentionnée pour l'une des parties. Ce que l'objet A n'indique pas s'écrit `—` ou `non mentionné dans le document`.
- **Strictement interdit** de donner une préférence subjective de soi-même — sauf si le document exprime lui-même une position. Pour une question du type « lequel est le meilleur », vérifier d'abord si le document contient une conclusion d'évaluation.
- Chaque point de différence clé doit être accompagné d'une référence au numéro de nœud ou à la page.
- Si un seul des objets est trouvable dans le document et que l'autre est totalement absent → arrêter la comparaison et indiquer à l'utilisateur « aucune information relative à B trouvée dans le document, impossible de réaliser la comparaison ».
