---
name: evaluer-reponse-sourcee
description: >-
  Évalue rigoureusement, dans Claude Code (lecture des PDF + vérifications
  déterministes, sans API de scoring), la qualité d'une réponse produite par
  PageIndex_Chat_UI à une question de test, en la confrontant pièce par pièce au
  texte source. À utiliser dès que l'utilisateur veut « évaluer / auditer /
  vérifier / noter la qualité » d'une réponse de l'app ou d'un test (test1..4,
  dossier Théo, Procedure-PN-1, Rapports_LSC, Synthèse_2026), d'un fichier
  audits/*.md, ou demande si une réponse contient des erreurs, hallucinations,
  omissions, contaminations, mauvaises citations de page ou faux verbatims.
  Vérifie chaque citation (p. N) contre la PAGE PHYSIQUE du PDF, contrôle les
  guillemets, repère omissions et contaminations, et — point central — distingue
  les vrais défauts de l'app des artefacts des données de test (l'app est fidèle
  au texte source, même incohérent). Ne PAS utiliser pour rejouer/lancer un test,
  ni pour évaluer du code ou des réponses de conversation libre (hors documents).
---

# Évaluer une réponse sourcée — PageIndex_Chat_UI

Ce skill sert à juger **si une réponse de l'app dit vrai par rapport aux documents**,
et à le faire de façon **fondée** : chaque reproche s'appuie sur un passage source
cité, avec sa page physique. Le piège classique (commis par des évaluateurs humains
ou IA) est de prendre une **incohérence des données** pour une hallucination de
l'app. L'app a pour mission la **fidélité au texte** ; bien l'évaluer, c'est séparer
ce qu'elle a *mal fait* de ce qu'elle a *fidèlement reproduit d'un source erroné*.

## Entrées attendues

- **La question** posée.
- **La réponse** de l'app — collée par l'utilisateur, ou lue dans un `audits/*.md`
  (qui contient aussi la trace d'aiguillage : voie, décomposition, nœuds, citations).
- **Le chemin du dossier source** (PDF). Dépôt : corpus sous `../data/`
  (`Procedure-PN-1-PDF/`, `Dossier Théo Blanchet.pdf`, `Rapports_LSC.docx`,
  `Synthèse_2026.pdf`).

Si une entrée manque, la demander avant de commencer — un audit sans le source est
sans valeur.

## Chaîne complète (lancer un test → l'évaluer)

Pour rejouer un test de bout en bout, **visible dans l'IHM**, et l'évaluer :

1. **Lancer le test** (capture) — `scripts/run_test.py` ouvre une vraie session KB
   (Socket.IO `agent_chat`, donc visible dans l'IHM) sur le dossier choisi et écrit
   un audit `.md` daté (réponse + trace : voie, décomposition, nœuds, citations,
   flag map-reduce) :
   ```
   .venv/bin/python .claude/skills/evaluer-reponse-sourcee/scripts/run_test.py \
       --dossier <theo|procedure|rapports|synthese> \
       --question-file <q.txt> --out evaluations/<date>/audits/<T>.md --title "<T>"
   ```
   **Map-reduce (T5)** : lancer l'app avec `PAGEINDEX_CTX_BUDGET=8000` pour forcer
   la bascule (sinon le drill-down l'évite). Seul le *lancement* change ; la
   sélection des pièces et l'évaluation sont **identiques aux autres cas**.
2. **Évaluer** (ce skill) : lire l'audit produit, le confronter au source, écrire
   le rapport d'éval daté `evaluations/<date>/EVAL_<T>.md` (format plus bas).
3. **Synthèse** : `evaluations/<date>/RAPPORT.md` agrège les cas (style
   `FONCTIONNEMENT-PAR-TESTS.md`).

Cas de référence : T1 Théo (note CHAUVIN) · T2 Procédure (composite) ·
T3 Rapports_LSC · T4 Synthèse (résumé) · T5 Synthèse (map-reduce forcé).

## Principe directeur : trois catégories de constats

Tout constat se range dans **exactement une** de ces catégories. C'est le cœur du
skill : sans cette discipline, l'évaluation sur-accuse ou sous-accuse.

- 🔴 **Vrai défaut de l'app** — la rédaction ou l'indexation **s'écarte du source** :
  citation de page fausse, faux verbatim (guillemets sur une paraphrase),
  contamination *introduite* par l'app (un fait d'une pièce attribué à une autre
  alors que les pièces sont correctes), hallucination absente de toute pièce,
  omission d'un élément pourtant présent dans une fiche/pièce, affirmation
  d'exhaustivité (« aucun autre… »).
- 🟡 **Artefact des données** — **le source lui-même** est incohérent/erroné et
  l'app le **reproduit fidèlement**. *Ce n'est PAS un bug.* « Corriger » l'app
  dégraderait la fidélité. Exemple connu : le certificat médical du dossier
  Procedure (formulaire mal rempli — voir `references/app-specifics.md`).
- 🔵 **Limite structurelle connue** — comportement **attendu**, documenté :
  `overview` (synthèse sur fiches) survole et peut omettre, là où `detail`
  (lecture du texte) est fidèle ; `(p. N)` = **page physique du PDF** ≠ folio
  imprimé. Voir `references/app-specifics.md`.

**Règle d'or** : ne jamais qualifier quelque chose d'erreur **sans citer le passage
source contradictoire** (avec sa page physique). Pas de verdict de mémoire ni
spéculatif. En cas de doute entre 🔴 et 🟡, **lire le texte source** tranche.

## Procédure d'audit

1. **Repérer l'aiguillage** (depuis l'audit si fourni) : décomposition ? quelle
   voie par section (`overview` fiches / `detail` texte / map-reduce) ? Cela
   calibre les attentes : on est plus exigeant sur la fidélité d'une section
   `detail` que sur l'exhaustivité d'une section `overview`.
2. **Lire le source** des pièces concernées (`verif_source.py grep` pour localiser,
   `page` pour lire une page). Pour un formulaire/page-image au texte vide, lire
   l'OCR du nœud indexé (`results/documents/<...>/structure.json`).
3. **Vérifier chaque citation `(… p. N)`** : le fait cité est-il bien sur la **page
   physique N** ? (`verif_source.py page <pdf> N`). Un décalage vs le folio imprimé
   n'est PAS une erreur (🔵).
4. **Contrôler chaque passage entre guillemets** : verbatim exact ?
   (`verif_source.py quote <dossier> "<phrase>"`). Une paraphrase guillemetée = 🔴.
5. **Contrôle factuel claim par claim** : noms, dates, **heures**, rôles
   (auteur/destinataire/médecin/OPJ…), chiffres. Chaque fait doit être traçable au
   source. Attention aux **noms proches** (LAPETITE/LAGRANDE, Legrand/Lepetit) et
   aux **rôles** (ne pas inverser auteur/destinataire, médecin/enquêteur).
6. **Omissions / contaminations** : un acteur ou un chiffre présent dans le source
   est-il absent de la réponse ? Un fait est-il attribué à la mauvaise personne ou
   pièce ? Vérifier si l'erreur vient de l'app (🔴) ou des données (🟡).
7. **Classer** chaque constat (🔴/🟡/🔵) avec sa **preuve** (citation source + page).

## Vérifications déterministes — `scripts/verif_source.py`

Lancer **dans le venv** :

```
.venv/bin/python .claude/skills/evaluer-reponse-sourcee/scripts/verif_source.py page  <pdf> <N>
.venv/bin/python .claude/skills/evaluer-reponse-sourcee/scripts/verif_source.py grep  <dossier|pdf> <terme>
.venv/bin/python .claude/skills/evaluer-reponse-sourcee/scripts/verif_source.py quote <dossier|pdf> "<phrase entre guillemets>"
```

- `page` rend le texte de la page **physique** N → vérifie une citation.
- `grep` localise un fait (fichier + page physique + contexte) → confirme présence,
  contamination, ou artefact de données.
- `quote` dit si une phrase est un verbatim exact → contrôle les guillemets.

Privilégier ces commandes à un jugement « de mémoire » : elles sont rapides,
reproductibles, et rendent l'audit fondé.

## Format du rapport

Produire un Markdown dans le style des `audits/*.md`. Structure :

```
# Évaluation — <test / dossier> — <date>

- **Question** : …
- **Voie / aiguillage** : … (décomposition ? overview/detail par section ? map-reduce ?)
- **Note globale** : X/20 — <une phrase de synthèse>

## Constats
| # | Catégorie | Sévérité | Constat | Preuve source (pièce, p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | … | citation p. 7 fausse : le fait est p. 9 | … |
| 2 | 🟡 données | — | « Lignier médecin » : le certificat source le dit | … p.1 |
| 3 | 🔵 connu | — | section synthèse survole (overview/fiches) | — |

## Analyse par section / facette
<ce qui est fidèle, ce qui survole ; pourquoi, selon la voie utilisée>

## Corrections proposées
<UNIQUEMENT pour les 🔴 ; minimales et ciblées ; rien pour 🟡/🔵>
```

Toujours **distinguer** dans la note ce qui relève de l'app (actionnable) et ce
qui relève des données ou des limites connues (non imputable à l'app). Une réponse
fidèle à un dossier incohérent peut mériter une **bonne** note.

## Pièges spécifiques à cette app

Lire **`references/app-specifics.md`** avant le premier audit d'une session : il
détaille la convention page physique, les voies et leurs attentes, les artefacts
de données connus du corpus, et les règles de grounding que la réponse doit
respecter (citations, pas d'inversion de rôle, pas d'exhaustivité, verbatims).
