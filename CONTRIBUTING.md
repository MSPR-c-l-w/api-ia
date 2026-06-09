# Guide de Contribution — HealthAI Coach API

Bienvenue ! Ce guide explique comment contribuer au projet.

## Avant de commencer

1. Cloner le dépôt et créer une branche feature :

   ```bash
   git clone https://github.com/MSPR-c-l-w/api-ia.git
   cd api-ia
   git checkout -b feature/issue-XXX-description
   ```

2. Configurer l'environnement local :

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # ou source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

3. Démarrer MongoDB (local ou Docker) :

   ```bash
   # Option Docker (recommandé)
   docker compose up mongo

   # OU MongoDB local sur localhost:27017
   ```

## Workflow de contribution

### 1. Identifier le contexte métier

Avant de coder, déterminer le **bounded context** affecté :

- **`workout`** — recommandations sportives, moteur multi-critères
- **`nutrition`** — analyse repas, recommandations alimentaires
- **`shared`** — MongoDB, exceptions applicatives

Exemple : une nouvelle fonctionnalité de récupération d'historique sport → `contexts/workout/`.

### 2. Suivre la clean architecture

Pour **ajouter une fonctionnalité** dans un contexte :

```
contexts/{context}/
  ├── domain/           [1] Définir entités/ports/services
  │   ├── entities/
  │   ├── repositories/ (Protocols, pas impl.)
  │   └── services/     (Logique métier pure)
  ├── application/      [2] Use case = orchestration
  │   └── use_cases/
  │       └── {feature}_use_case.py
  ├── infrastructure/   [3] Implémenter les Ports
  │   └── persistence/
  │       └── mongo_{entity}_repository.py
  └── presentation/     [4] DTOs Pydantic
      └── schemas.py
```

**Règles essentielles** :

| Couche             | ✅ Fait                                              | ❌ Éviter                      |
| ------------------ | ---------------------------------------------------- | ------------------------------ |
| **Domain**         | Logi…que pure, Entités, Services domaine, Protocols  | Flask, Motor, Données externes |
| **Application**    | Use cases, Orchestration, lève `ApplicationError`    | HTTP, Détails DB               |
| **Infrastructure** | Implémente Ports, adaptateurs DB                     | Logique métier                 |
| **Presentation**   | Blueprints, DTOs Pydantic, `@map_application_errors` | Logique métier                 |

### 3. Implémenter une feature complète

#### Exemple : ajouter « historique de progression »

**Étape 1: Domaine**

```python
# contexts/workout/domain/entities/workout_progression.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class WorkoutProgression:
    program_id: str
    user_id: int
    completed_date: datetime
    exercises_completed: list[str]
    difficulty_adjustment: float  # -0.2 à +0.2
```

**Étape 2: Port (Repository Protocol)**

```python
# contexts/workout/domain/repositories/protocols.py
from typing import Protocol

class WorkoutProgressionRepository(Protocol):
    async def save(self, progression: WorkoutProgression) -> None: ...
    async def find_by_user(self, user_id: int) -> list[WorkoutProgression]: ...
```

**Étape 3: Use case**

```python
# contexts/workout/application/use_cases/record_workout_completion_use_case.py
from app.shared.application.exceptions import ApplicationError

class RecordWorkoutCompletionUseCase:
    def __init__(self, repository: WorkoutProgressionRepository):
        self.repository = repository

    async def execute(self, program_id: str, user_id: int,
                      exercises_completed: list[str]) -> WorkoutProgression:
        progression = WorkoutProgression(
            program_id=program_id,
            user_id=user_id,
            completed_date=datetime.now(),
            exercises_completed=exercises_completed,
            difficulty_adjustment=0.0
        )
        await self.repository.save(progression)
        return progression
```

**Étape 4: Implémentation MongoDB**

```python
# contexts/workout/infrastructure/persistence/mongo_workout_progression_repository.py
from motor.motor_asyncio import AsyncIOMotorDatabase

class MongoWorkoutProgressionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def save(self, progression: WorkoutProgression) -> None:
        await self.db.workout_progressions.insert_one(
            progression.model_dump()
        )

    async def find_by_user(self, user_id: int) -> list[WorkoutProgression]:
        docs = await self.db.workout_progressions.find(
            {"user_id": user_id}
        ).to_list(None)
        return [WorkoutProgression(**doc) for doc in docs]
```

**Étape 5: Présentation (DTO)**

```python
# contexts/workout/presentation/schemas.py
from pydantic import BaseModel
from datetime import datetime

class WorkoutProgressionSchema(BaseModel):
    program_id: str
    user_id: int
    completed_date: datetime
    exercises_completed: list[str]
```

**Étape 6: Router Flask**

```python
# app/routers/recommendations.py (ajouter endpoint)
from flask import Blueprint, request
from app.presentation.http import handle_http_request
from app.composition.container import Container

blueprint = Blueprint('recommendations', __name__)

@blueprint.route('/recommendations/workout/<program_id>/complete', methods=['POST'])
async def record_completion(program_id):
    dto = RecordCompletionRequestDTO(**request.json)
    use_case = Container.workout_record_completion_use_case()

    result = await handle_http_request(
        lambda: use_case.execute(program_id, dto.user_id, dto.exercises_completed)
    )
    return result
```

**Étape 7: Container (injection)**

```python
# app/composition/container.py
def workout_record_completion_use_case(self) -> RecordWorkoutCompletionUseCase:
    repository = MongoWorkoutProgressionRepository(self.db)
    return RecordWorkoutCompletionUseCase(repository)
```

### 4. Tester

```bash
# Tests unitaires (domaine + logique pure)
pytest tests/contexts/workout/domain/test_progression.py

# Tests use case (mocks des dépendances)
pytest tests/contexts/workout/application/test_record_completion_use_case.py

# Tests d'intégration HTTP
pytest tests/contexts/workout/presentation/test_recommendations_router.py

# Coverage
pytest --cov=app
```

**Principes de test** :

- **Domaine** : test les entités, services — pas de dépendances externes
- **Use case** : mock les ports (repositories)
- **Router HTTP** : utiliser `httpx` client de test Flask
- **Intégration** : MongoDB réelle (container Docker dans CI)

### 5. Documenter et générer OpenAPI

```bash
# Régénérer openapi.json après modification des routes
python scripts/export_openapi.py

# Valider via Swagger UI (démarrer l'API)
python run.py
# → Ouvrir http://127.0.0.1:8000/docs
```

Ajouter des docstrings aux endpoints :

````python
@blueprint.route('/recommendations/workout', methods=['POST'])
async def create_recommendation():
    """Créer un programme d'entraînement personnalisé.

    **Authentification** : Header `X-API-Key` requis (partagée avec NestJS)

    **Pré-requis ** :
    - Profil utilisateur existant dans `user_fitness_profiles`

    **Réponse** (200 OK) :
    ```json
    {
      "id": "665a1b2c3d4e5f6789012345",
      "userId": 42,
      "programme": [...],
      "statut": "ACTIVE"
    }
    ```
    """
    # ...
````

### 6. Créer une PR

1. Pousser la branche :

   ```bash
   git add .
   git commit -m "feat: ajouter historique de progression sport"
   git push origin feature/issue-100-progression
   ```

2. Ouvrir une PR sur GitHub avec :
   - **Titre ** : `feat: ...` ou `fix: ...` (Conventional Commits)
   - **Description** :
     - Lien vers l'issue
     - Contexte métier
     - Tests ajoutés
     - Checklist :
       - [ ] Tests passe (`pytest`)
       - [ ] Pas de dépendances domaine → infra
       - [ ] `openapi.json` régénéré
       - [ ] Documentation mise à jour

3. Passer la revue de code → merge

## Conventions de code

### Imports

```python
# ✅ Bon : imports depuis app/contexts/...
from app.contexts.workout.domain.entities import WorkoutProgression
from app.contexts.workout.application.use_cases import RecordWorkoutCompletionUseCase

# ⚠️ Acceptable (chemins historiques pour compatibilité)
from app.models import UserProfile  # Réexporte depuis contexts/

# ❌ Éviter : imports cycliques
from app.routers.recommendations import blueprint  # Dans une use case !
```

### Nommage

| Élément         | Convention                | Exemple                         |
| --------------- | ------------------------- | ------------------------------- |
| Classe entité   | PascalCase                | `WorkoutProgram`                |
| Use case        | `{Action}{Noun}UseCase`   | `CreateWorkoutProgramUseCase`   |
| Service domaine | `{Noun}Service`           | `RecommendationEngine`          |
| Repository      | `Mongo{Entity}Repository` | `MongoWorkoutProgramRepository` |
| Schema DTO      | `{Entity}Schema`          | `WorkoutProgramSchema`          |
| Fichier         | snake_case                | `workout_progression.py`        |
| Port/Protocol   | `{Entity}Repository`      | `WorkoutProgressionRepository`  |

### Type hints

```python
# ✅ Bon
async def execute(self, user_id: int, objectives: list[str]) -> WorkoutProgram:
    ...

# ❌ Éviter
async def execute(self, user_id, objectives):
    ...
```

## Signaler un bug ou proposer une feature

1. Ouvrir une issue sur [GitHub](https://github.com/MSPR-c-l-w/api-ia/issues)
2. Utiliser les templates (bug report, feature request)
3. Ajouter des labels (`bug`, `enhancement`, `documentation`, etc.)
4. Linker vers la MSPR si pertinent (`mspr-contexte.md`)

## Ressources

- [Clean Architecture — Architecture.md](docs/architecture.md)
- [Guide MSPR/Cahier des charges](docs/mspr-contexte.md)
- [Schéma MongoDB](docs/mongodb-schema.md)
- [Guide agents IA (approche RAG)](AGENTS.md)
- Tests existants : `tests/`
