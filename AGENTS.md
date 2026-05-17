# Guide pour les agents IA — API IA (HealthAI Coach)

Micro-service de recommandations IA pour la MSPR TPRE502 (HealthAI Coach). Voir le sujet client dans `docs/mspr-contexte.md`.

## Stack

- **Python 3.12+**, **Flask 3** (couche présentation / HTTP, vues async)
- **MongoDB** (Motor) — persistance NoSQL du moteur sport
- **Pydantic** — DTOs et entités
- **pytest** — tests unitaires et d'intégration HTTP

> Stack HTTP : **Flask** (sujet MSPR) + **Hypercorn** en production (ASGI, Motor async).

## Clean architecture

Organisation par **bounded contexts** et **use cases** :

```text
app/
  contexts/
    workout/          # Moteur recommandations sport (MSPR § II.2)
      domain/         # Entités, value objects, services métier, ports (Protocol)
      application/    # Use cases
      infrastructure/ # Adaptateurs MongoDB, catalogue exercices
      presentation/   # Schémas API (DTOs)
    nutrition/        # Recommandations nutrition (MSPR § II.1)
      application/
      presentation/
  shared/             # Exceptions applicatives, MongoDB partagé
  composition/        # Container (injection de dépendances)
  routers/            # Blueprints Flask (minces)
  presentation/       # Mapping exceptions → HTTP
```

### Règles

1. **Domaine** : pas de FastAPI, pas de Motor. Logique pure (scoring, planification).
2. **Application** : un fichier = un use case (`execute`). Lève `ApplicationError` (jamais `HTTPException`).
3. **Infrastructure** : implémente les `Protocol` du domaine (ex. `MongoWorkoutProgramRepository`).
4. **Présentation** : blueprints Flask + DTOs Pydantic ; `@map_application_errors` pour le HTTP.
5. **Composition** : câblage dans `app/composition/container.py` uniquement.

### Ajouter une fonctionnalité

1. Identifier le contexte (`workout` ou `nutrition`).
2. Créer ou étendre entités / ports dans `domain/`.
3. Ajouter un use case dans `application/use_cases/`.
4. Implémenter l'adaptateur dans `infrastructure/` si besoin.
5. Exposer via router + enregistrer dans `Container`.
6. Tests : domaine (unitaires), use case (mocks des ports), router (httpx).

## Commandes

```bash
pip install -r requirements.txt
python run.py                    # API locale :8000
pytest                           # Tests
python scripts/export_openapi.py # Export openapi.json
python scripts/seed_mongodb.py   # Jeu de données MongoDB
```

## Compatibilité

Les chemins historiques (`app/models/`, `app/services/`, `app/data/`) réexportent le nouveau code. Préférer les imports depuis `app/contexts/...` pour tout nouveau code.

## Checklist après modification

- [ ] `pytest` vert
- [ ] Pas de dépendance domaine → infrastructure
- [ ] Use case testé si logique métier modifiée
- [ ] `openapi.json` régénéré si routes/schemas changent
