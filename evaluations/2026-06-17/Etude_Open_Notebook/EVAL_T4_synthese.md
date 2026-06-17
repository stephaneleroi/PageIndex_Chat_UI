# Évaluation — T4 / Synthèse_2026 (résumé) — 2026-06-17

- **Question** : « Fais moi un résumé »
- **Voie / aiguillage** : `global_summary` (overview) — décomposition = 1 indice,
  map-reduce = non, 6 fiches agrégées (nœuds 0000, 0002, 0003, 0009, 0015 + 0001).
  Question de RÉSUMÉ → survol attendu : on juge la fidélité des faits portés par les
  fiches et l'exactitude des `(p. N)`, pas l'exhaustivité.
- **Note globale** : **18/20** — synthèse remarquablement fidèle ; tous les chiffres
  et dates vérifiés tombent juste, une seule citation a perdu une page (présente et
  correcte dans la fiche source). Aucune hallucination, aucun faux verbatim
  (réponse sans guillemets).

## Constats

| # | Catégorie | Sévérité | Constat | Preuve source (p. physique) |
|---|---|---|---|---|
| 1 | 🔴 app | mineure | « 75 % des patients hospitalisés à moins de 43 km … (node_0003, **page 16**) » : la page 16 ne porte que les « ~2 500 établissements » ; le fait 75 %/43 km est **page 20**. La fiche du nœud 0003 citait pourtant **« (p. 16, p. 20) »** — la rédaction de synthèse a **laissé tomber la page 20**. | p.16 (« quelques 2 500 établissements ») ; p.20 (« 75 % … à 43 kilomètres maximum … en 2024 »). Fiche node_0003 : « (p. 16, p. 20) ». |
| 2 | 🔵 connu | — | Citations en **plages** (7‑11, 23‑29, 53‑55, 68‑69, 80‑81, 90‑92, 101‑110) couvrant des chiffres-clés dispersés : c'est le survol overview/fiches. Chaque fait pointé tombe dans (ou à 1‑2 p. de) sa plage. | conforme voie overview |
| 3 | 🔵 connu | — | « actions de droit commun dans les QPV d'ici 2026 » rangé sous « (node_0015, pages 101‑110) » alors que la reco 2026 est **page 94** ; la plage 101‑110 vise la péréquation. Imprécision de plage en overview, pas une fausse page. | p.94 (« actions de droit commun … (2026) ») |

## Vérifications déterministes (toutes positives sauf #1)

Faits contrôlés un par un contre la page physique (`verif_source.py`) :

- node_0002 (p. 7‑11) : 23 départements 2015‑2021, PIB 69 288 €/32 652 €, RDB
  27 060 €/19 509 €, **16,8 Md€ crédits UE 2021‑2027** → tous **page 8** ✓.
- node_0003 : 2 500 établissements **p.16** ✓ ; 75 %/43 km **p.20** (cf. #1) ;
  34,6 % pauvreté outre-mer + 42 jours cardiologie **p.27** ✓ ; gradation/GHT
  « d'ici 2028 » **p.23** ✓ ; centralisation données santé « 2027 » **p.29** ✓ ;
  −12 % collégiens « horizon 2036 » **p.31** ✓.
- node_0009 : LOM 24/12/2019 **p.53** ✓ ; 50 % AOML **p.54‑55** ✓ ; 70 % ruraux/
  périurbains **p.54** ✓ ; 30 % jeunes ruraux **p.54** ✓ ; 92 % fibre 2025 **p.69**
  + 91 % smartphone + 215 800 zone blanche **p.68** ✓ ; sécurité 24,4 Md€ +33 % /
  2,3 Md€ +41 % / 28 000 policiers municipaux 2023 / +6,5 % délinquance 2016‑2024
  **p.80‑81** ✓.
- node_0015 : articulation politiques **p.86** ✓ ; 17 OIN / 56 projets / 1 931
  **p.95** ✓ ; pauvreté QPV ×3 + 524 M€ politique de la ville 2024 **p.90‑92** ✓ ;
  péréquation verticale 10,2 Md€ / horizontale 4,2 Md€ 2024 **p.108‑109** (dans
  101‑110) ✓ ; CPER/CRTE échéances 2027‑2028 **p.106** ✓.

Aucun chiffre inventé, aucune inversion de rôle, aucun verbatim guillemeté (la
réponse paraphrase partout). « 215 800 personnes » → rendu « 215 800 habitants » :
paraphrase acceptable.

## Analyse

La réponse est un excellent résumé sourcé : structure en trois parties fidèle au
sommaire (p.4‑5), chiffres-clés exacts, dates de recommandations exactes (2027,
2026, 2028), pas la moindre affirmation d'exhaustivité ni d'absence. Sur ~30 faits
chiffrés vérifiés, **un seul** présente un défaut de citation, et c'est une
**régression de la rédaction** : la fiche du nœud 0003 portait la double page
« (p. 16, p. 20) » correctement ; l'étape de synthèse globale n'en a conservé
qu'une, et la mauvaise pour le fait concerné. Le défaut est donc dans l'agrégation,
pas dans l'indexation ni dans les données. Impact réel faible (le clic ouvrirait
p.16 où figure bien la phrase « 2 500 établissements », fait voisin), mais c'est un
écart aux règles de grounding (§1 page exacte).

## Corrections proposées (uniquement le 🔴 #1)

Le matériau correct existe déjà : la fiche cite « (p. 16, p. 20) ». Le prompt de
synthèse globale (rédaction overview) devrait **conserver toutes les pages d'une
liste `(p. X, p. Y)`** d'un point saillant plutôt que d'en élire une seule — ou, a
minima, citer la page la plus spécifique au fait rapporté. Évaluer sur plusieurs
tirages (Modelfile à température non nulle) avant de conclure à un biais
systématique : ce peut être un aléa de rédaction sur ce tirage.
