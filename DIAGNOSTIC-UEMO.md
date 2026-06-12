# Diagnostic : hallucination sur « Qu'est-ce que les UEMO pour la DPJJ ? »

*Enquête des 10-12/06/2026, à la demande de l'utilisateur. Enjeu : ce POC sera
intégré dans une application disposant de nombreux outils et d'un system
prompt complet — comprendre précisément ce qui dégrade une réponse factuelle
est critique pour cette intégration.*

## Les faits

En conversation libre (sans document), l'application a répondu que les UEMO
sont des « unités d'éducation **militaire** et d'orientation » — faux. Le
terme officiel est **Unité Éducative de Milieu Ouvert** (unités des STEMO de
la DPJJ). L'utilisateur a constaté qu'en direct (`ollama run
nemotron-3-super`), le modèle donne la bonne définition.

## L'enquête, étape par étape

Tous les tests sur la même question, mot pour mot. Modèles servis par Ollama.

### 1. L'enrobage de prompt dégradait le modèle — PROUVÉ, CORRIGÉ

- La question rejouée avec le prompt complet de l'application (temp 0)
  reproduit *mot pour mot* la mauvaise réponse reçue par l'utilisateur →
  c'était bien Nemotron + l'enrobage.
- Les trois modèles (nemotron-3-super, qwen3.6, gpt-oss-20b) hallucinent
  chacun une expansion différente sous cet enrobage.
- Décomposition couche par couche (Nemotron, temp 0) : question nue →
  prudence (« il semble y avoir une confusion… ») ; + préambule assistant →
  **correct** ; + consigne de langue → fragilisé ; + **consignes de style →
  hallucination franche**. Le coupable principal : les règles de directivité
  (« réponds uniquement à la question, aucune digression ») suppriment le
  réflexe de doute du modèle ; contraint d'asséner une définition alors que
  sa connaissance est fragile, il confabule.

**Correctif** : la conversation libre interroge le modèle NU — aucune
instruction ajoutée, l'historique transmis comme vrais tours de dialogue
(`_run_free_chat` → `call_llm_stream(messages=…)`). Les consignes de style
restent réservées aux réponses documentées, où le modèle répond sur les
pièces fournies et non sur ses poids.

### 2. Hypothèse température — RÉFUTÉE

Le Modelfile de nemotron-3-super prescrit `temperature 1, top_p 0.95`
(recommandation NVIDIA) ; l'application forçait `temperature=0`. Test : avec
les réglages du Modelfile, la question nue échoue encore 3/3 (deux dénis de
l'existence des UEMO, une expansion inventée). La température ne rend pas la
connaissance fiable. Le correctif de parité est appliqué malgré tout : en
mode brut, l'application n'envoie plus de température — les réglages du
Modelfile s'appliquent, comme en direct.

### 3. Hypothèse raisonnement (thinking) — PARTIELLEMENT CONFIRMÉE

`nemotron-3-super` a la capacité `thinking`, activée par défaut dans
`ollama run` mais pas via l'endpoint OpenAI utilisé par l'application.
Test API native : `think=true` → 1 correct sur 3 ; `think=false` → 0 sur 1.
La phase de réflexion aide réellement (le modèle énumère les candidates et
écarte les douteuses — visible dans les traces), sans rien garantir.

### 4. Le verdict : la connaissance elle-même est une loterie

Condition exacte de l'utilisateur rejouée trois fois (`ollama run
nemotron-3-super:latest` + la question) : **2 correctes, 1 hallucination**
(« Unité d'Éducation Médiatisée Obligatoire », inventée). Dans une trace de
raisonnement, on voit le modèle hésiter explicitement entre « Unité
d'Éducation Militaire et Orientation » (l'hallucination d'origine) et la
bonne expansion. Les deux coexistent dans les poids à probabilités proches :
à température 1 chaque tirage est une loterie, à température 0 le résultat
est figé — sur un déni.

L'exécution correcte observée par l'utilisateur en direct était un tirage
favorable, pas une connaissance fiable du modèle.

## Conclusions

1. **Le bug réel** (enrobage qui supprime le doute) est corrigé : parité
   totale entre la conversation libre de l'application et le modèle nu.
2. **Aucun réglage** (température, raisonnement, mode d'appel) ne fiabilise
   une connaissance que les poids n'encodent que partiellement. Les acronymes
   métier rares sont typiquement dans cette zone grise.
3. **Pour les faits métier, la seule réponse robuste est l'ancrage
   documentaire** — la raison d'être de ce POC : une fiche de référence sur
   les structures de la PJJ dans la bibliothèque transforme cette loterie en
   réponse sourcée, pages vérifiées à l'appui.

## Implications pour l'intégration future (system prompt complet + outils)

1. **Tout system prompt de directivité augmente le risque de confabulation
   factuelle.** Prévoir explicitement l'exception : *« en cas d'incertitude
   factuelle, le signaler »* — une règle de directivité ne doit jamais
   interdire l'expression du doute.
2. **Évaluer les questions factuelles AVEC le system prompt de production**,
   jamais avec le modèle nu : les deux peuvent diverger du tout au tout.
3. **Évaluer sur plusieurs tirages**, jamais sur une exécution : à
   température 1, une réponse correcte isolée ne prouve rien (2/3 vs 1/3 ici).
   Panel de questions factuelles sensibles (acronymes métier, références
   réglementaires) joué en N exécutions, modèle nu vs modèle enrobé ; toute
   divergence systématique est une régression de l'enrobage.
4. **Les faits critiques doivent venir de documents, pas des poids** — avec
   une frontière visible pour l'utilisateur final entre réponse sourcée
   (badge de qualité, citations vérifiées) et conversation libre.
