# Rapport de la boucle nocturne (2026-06-16 → 17) — tests, diagnostic, corrections

Boucle autonome : jouer les 4 tests → auditer la qualité → corriger les vrais
problèmes → revalider → itérer. Indexation déjà faite (28 docs, 0 erreur).

## Cycle 1 — découverte
| Test | Verdict | Détail |
|---|---|---|
| T1 Théo (note CHAUVIN) | ✅ OK | lit le texte, pages cohérentes, pas de contamination |
| **T2 Procedure (composite)** | ❌ **PROBLÈME** | **non décomposé** → parti en synthèse globale (fiches), facettes faits/versions non lues |
| T3 Rapports | ✅ OK | lit le texte, 4/4 rapports |
| T4 Synthèse | ✅ OK | vue d'ensemble (fiches) |

## Diagnostic & corrections (2 itérations sur l'aiguillage)
**Problème** : la question composite « synthèse + faits + versions » n'était plus
décomposée, et son intention globale tombait en `overview` (fiches) → on perdait
la lecture du texte pour faits/versions.

1. **Cause 1** : le garde-fou anti-sur-décomposition (« dans le doute, ne découpe
   pas ») était trop inhibant. → **Correctif** : exemple explicite d'enchaînement
   de demandes à découper en 3, retrait du « dans le doute ».
   *Re-test* : 3/3 essais décomposés ✅… mais voie encore « fiches ».
2. **Cause 2** : `detail` était trop centré sur « pièce **désignée** » → « résume
   les faits », « quelles versions » (contenu factuel sans pièce nommée)
   retombaient en `overview`. → **Correctif** : `detail` = **contenu factuel
   précis** (faits, versions, déclarations, contenu d'une pièce), MÊME sur tout le
   dossier ; `overview` = seulement vue d'ensemble/synthèse.
   *Re-test* : 3/3 essais → **3 sections + lecture du texte** ✅ (stable).

## Cycle 2 — revalidation complète
| Test | Verdict |
|---|---|
| T1 | ⚠️→✅ voie OK, pas de contamination, 5/6 pages (1 tirage) |
| **T2** | ✅ **corrigé** — décomposé + lecture du texte (14 citations) |
| T3 | ✅ OK (pas de régression) |
| T4 | ✅ OK (pas de régression) |

## Vérification T1 (le 5/6 était-il un vrai problème ?)
3 tirages supplémentaires : **5/5, 8/8, 6/6** pages cohérentes, voie lecture,
aucune contamination. → **variabilité** (rédaction à température non nulle + check
heuristique strict), **pas un bug**. Aucune correction.

## État final
**Les 4 tests passent.** Seul vrai problème de la nuit (T2 non décomposé) corrigé
et validé stable. T1/T3/T4 sans régression. Faux signaux écartés après
vérification (compteur de citations, « Lignier » des données, 5/6 pages T1).

Corrections commitées (prompt `decompose_query` : décomposition + définition
overview/detail). Doc `ARCHITECTURE.md` §5.1/§5.5 à jour.
