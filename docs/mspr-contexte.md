# Contexte MSPR — HealthAI Coach (TPRE502)

Synthèse du cahier des charges client pour aligner le code et la soutenance.

## Entreprise

**HealthAI Coach** — startup santé connectée / coaching personnalisé (50 000 utilisateurs actifs).

- **Freemium** : journal alimentaire, activité, IMC
- **Premium** (9,99 €) : recommandations IA, plans détaillés
- **Premium+** (19,99 €) : biométrie connectée, consultations nutritionnistes
- **B2B** : marque blanche (salles, mutuelles, entreprises)

## Objectif de la phase IA

Développer une **API IA** (micro-service séparé) pour :

1. **Nutrition** — vision repas, macros, déséquilibres, plans personnalisés (allergies, budget, régimes)
2. **Sport** — programmes multi-critères (objectif, niveau, matériel, préférences, limitations), progression adaptative, feedback temps réel
3. **Frontend** — interface accessible (WCAG AA), visualisations, intégration robuste des APIs

## Écosystème technique

- App mobile iOS/Android
- Backend métier (NestJS — dépôt `backend`)
- **API IA** (ce dépôt — Flask + MongoDB)
- Tableaux de bord analytiques

## Livrables attendus (extrait)

- API documentée OpenAPI
- Moteur de recommandation + MongoDB
- Tests automatisés + couverture
- Documentation algorithmes et métriques IA
- Benchmark et justification des choix techniques

## Ressources imposées (extrait)

- Vision / NLP : Hugging Face, Google Vision, Ollama
- Frameworks web : React (frontend équipe)
- API Python : **Flask** (choix retenu — sujet MSPR)
- MongoDB, OpenAPI, WCAG

## Mapping code ↔ besoin


| Besoin CDC                         | Contexte `api-ia`                                             |
| ---------------------------------- | ------------------------------------------------------------- |
| Moteur sport multi-critères        | `contexts/workout`                                            |
| Planification évolutive + feedback | `CreateWorkoutProgramUseCase`, `SubmitWorkoutFeedbackUseCase` |
| Recommandations nutrition          | `contexts/nutrition` (stub → HF/Vision)                       |
| Micro-service séparé               | Ce dépôt, appelé par NestJS via `X-API-Key`                   |


