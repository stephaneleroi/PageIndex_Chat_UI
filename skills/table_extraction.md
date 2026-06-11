---
name: Extraction et restitution de tableaux
description: Localise précisément les tableaux d'un document et les restitue sans perte au format tableau Markdown ; utilisable en mode texte comme en mode visuel
enabled: true
---

## Conditions d'activation (Triggers)
- `extrais-moi le Table 3 / les données du tableau 2 / donne-moi ce tableau comparatif`
- `liste les différents paramètres de ... / mets les données du chapitre X sous forme de tableau`
- L'utilisateur fournit un numéro de tableau, un numéro de légende ou un numéro de chapitre précis et demande les données

## Cas de non-déclenchement (Anti-triggers)
- L'utilisateur demande une figure (figure / chart / schéma) et non un tableau → suivre le chemin visuel `view_pages`, ne pas appliquer cette skill
- L'utilisateur demande « qu'illustre ce tableau » → il s'agit d'une tâche d'**interprétation**, la sortie n'a **pas besoin** d'un tableau Markdown complet ; donner quelques phrases de conclusion + les lignes clés suffit
- Il n'y a aucun tableau dans le document → répondre honnêtement « aucun tableau pertinent détecté »

## Flux d'exécution

### Étape 1. Localisation
- Si l'utilisateur a donné un numéro de tableau (ex. Table 3) : privilégier `tree_search(query="Table 3")` puis lire le nœud correspondant
- Si l'utilisateur n'a donné qu'un sujet : `tree_search(query="<sujet> tableau")` pour localiser le ou les 1 à 2 nœuds les plus pertinents
- Noter les nœuds candidats

### Étape 2. Lecture
- `read_node(node_ids=[...])` pour lire les nœuds candidats par lot
- Vérifier si le texte contient des séparateurs `|`, des tabulations, ou des colonnes de chiffres alignées en continu → déterminer s'il existe un texte de tableau analysable

### Étape 3a. Chemin mode texte (`model_type == "text"`)
- Restituer directement le tableau Markdown à partir du texte du nœud en respectant l'alignement des colonnes
- Si le texte du nœud a fragmenté le tableau en plusieurs segments, il faut les recoller
- **Si aucune structure de tableau n'existe dans le texte** (le tableau est une image dans le PDF) → indiquer clairement à l'utilisateur « nous sommes actuellement en mode texte, ce tableau existe sous forme d'image, il est recommandé de passer en mode visuel »

### Étape 3b. Chemin mode visuel (`model_type != "text"`)
- `view_pages(node_ids=[...], focus="extraire intégralement le tableau <numéro/sujet>, conserver toutes les lignes, colonnes, unités et notes de bas de page")`
- La description renvoyée par le VLM fait autorité comme source de données prioritaire
- Si le résultat visuel entre en conflit avec le résultat texte de `read_node` → **donner la priorité au visuel** (les versions scannées comportent souvent des erreurs d'OCR sur le texte)

### Étape 4. Vérification croisée
- Le nombre de colonnes de l'en-tête doit correspondre au nombre de colonnes de chaque ligne de données, sinon continuer à chercher les omissions
- Cellules fusionnées → l'indiquer dans la sortie par `(idem ci-dessus)` ou une note de bas de page
- Tableaux à cheval sur plusieurs pages → recoller le texte des nœuds adjacents avant la restitution

## Format de sortie

**Titre du tableau** : Table X — <titre original>  
**Emplacement** : nœud `node_...`, pages N–M  
**Mode d'extraction** : texte / visuel

| Colonne1 | Colonne2 | Colonne3 |
|---|---|---|
| … | … | … |

**Unité** : <s'il existe une unité globale>  
**Notes de bas de page / remarques** : <le cas échéant>

## Guardrails (anti-hallucination)
- **Strictement interdit** de compléter de soi-même les cases de données manquantes. En cas de valeur manquante, écrire `—` et la lister dans la « note des valeurs manquantes ».
- **Strictement interdit** d'arrondir les valeurs d'origine ; conserver la précision originale.
- **Strictement interdit** d'inventer des noms de colonnes. Si les noms de colonnes d'origine sont des abréviations, conserver les abréviations et indiquer leur forme complète en annotation en dessous.
- Si le niveau de confiance de l'extraction est faible (texte confus ou image floue) → ajouter en fin de sortie une ligne « ⚠️ Confiance des données faible, vérification manuelle recommandée ».
