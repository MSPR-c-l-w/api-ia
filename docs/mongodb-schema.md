# Schéma MongoDB — micro-service recommandations sportives

Base par défaut : `healthai_coach` (définie dans `MONGODB_URI`).

## Collections

| Collection | Modèle Pydantic | Description |
|------------|-----------------|-------------|
| `workout_programs` | `WorkoutProgram` | Programmes hebdomadaires générés |
| `user_fitness_profiles` | `UserFitnessProfile` | Profil sportif / préférences IA |
| `workout_feedbacks` | `WorkoutFeedback` | Retours utilisateur sur un programme |

## Index

| Collection | Index |
|------------|--------|
| `workout_programs` | `userId` |
| `user_fitness_profiles` | `userId` |
| `workout_feedbacks` | `userId`, `programId` |

Créés automatiquement au démarrage (`app/services/indexes.py`).

---

## `workout_programs`

```json
{
  "userId": 42,
  "programme": [
    {
      "jour": "lundi",
      "exercices": [
        { "id": "squat", "sets": 3, "reps": 10, "duree": null }
      ]
    }
  ],
  "statut": "ACTIVE",
  "generatedAt": "2026-05-16T12:00:00Z"
}
```

| Champ | Type | Notes |
|-------|------|--------|
| `userId` | int | FK logique vers `User.id` (NestJS / MySQL) |
| `programme` | array | Jours + exercices planifiés |
| `programme[].jour` | string | Ex. `lundi`, `mardi` |
| `programme[].exercices[].id` | string | Référence exercice |
| `programme[].exercices[].sets` | int? | Séries |
| `programme[].exercices[].reps` | int? | Répétitions |
| `programme[].exercices[].duree` | int? | Durée (minutes) |
| `statut` | string | `ACTIVE` \| `ARCHIVED` |
| `generatedAt` | datetime | Date de génération |

`_id` MongoDB : référencé côté relationnel par `AiWorkoutRecommendation.microservice_ref_id` (backend).

---

## `user_fitness_profiles`

```json
{
  "userId": 42,
  "objectif": "perte_de_poids",
  "niveau": "debutant",
  "materiel": ["tapis", "haltères"],
  "preferences": ["cardio", "faible impact"],
  "limitations": ["mal au genou"],
  "historique": []
}
```

| Champ | Type | Notes |
|-------|------|--------|
| `userId` | int | Utilisateur |
| `objectif` | string | Objectif sportif |
| `niveau` | string | Niveau de forme |
| `materiel` | string[] | Équipement disponible |
| `preferences` | string[] | Préférences d'entraînement |
| `limitations` | string[] | Blessures / contraintes |
| `historique` | array | Événements passés (structure libre JSON) |

---

## `workout_feedbacks`

```json
{
  "programId": "665a1b2c3d4e5f6789012345",
  "userId": 42,
  "rating": 4,
  "tropDifficile": false,
  "tropFacile": false,
  "exercicesProblematiques": ["squat"],
  "createdAt": "2026-05-16T18:30:00Z"
}
```

| Champ | Type | Notes |
|-------|------|--------|
| `programId` | string | `_id` du `WorkoutProgram` (ObjectId hex) |
| `userId` | int | Utilisateur |
| `rating` | int | 1–5 |
| `tropDifficile` | bool | Signal de difficulté |
| `tropFacile` | bool | Signal de facilité |
| `exercicesProblematiques` | string[] | IDs exercices à ajuster |
| `createdAt` | datetime | Horodatage du feedback |

---

## Seed de test

```bash
python scripts/seed_mongodb.py
```

Nécessite MongoDB accessible (`MONGODB_URI` ou `docker compose up mongo`).
